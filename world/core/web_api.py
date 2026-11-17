"""Web API handlers behind the plugin management page.

The page at pages/worldbook talks to these routes through the AstrBot plugin
page bridge, so every read and write the dashboard performs lands here. Writes
are gated by the web_panel.allow_write config switch and validated against a
per-endpoint field whitelist; reads never mutate the store.
"""

from __future__ import annotations

from astrbot.api import logger
import time
from typing import Any

try:
    from astrbot.api.web import error_response, json_response, request
except Exception:  # pragma: no cover - older hosts expose Quart instead
    try:
        from quart import jsonify, request  # type: ignore

        def json_response(data=None, *, status_code=200, headers=None):
            response = jsonify({} if data is None else data)
            if headers:
                for key, value in headers.items():
                    response.headers[key] = value
            return response, status_code

        def error_response(message, *, status_code=400, data=None, headers=None):
            return json_response(
                {"status": "error", "message": message, "data": data},
                status_code=status_code,
                headers=headers,
            )
    except Exception:  # pragma: no cover - last resort, keeps imports alive
        request = None  # type: ignore

        def json_response(data=None, *, status_code=200, headers=None):
            return {} if data is None else data

        def error_response(message, *, status_code=400, data=None, headers=None):
            return {"status": "error", "message": message, "data": data}

from .character import CharacterCard
from .matcher import MatchedEntry, MatchResult, build_injection_text, match_entries
from .models import SESSION_CARD_NONE, WorldBook, WorldEntry, new_uid


PLUGIN_NAME = "astrbot_plugin_dynamics_world"

_MAX_BODY_BYTES = 512 * 1024
_READ_LIMIT_PER_MINUTE = 240
_WRITE_LIMIT_PER_MINUTE = 120

# Field whitelists: anything outside these sets is rejected with 400 so a
# malformed panel request can never smuggle unexpected keys into the store.
_BOOK_FIELDS = {
    "action",
    "book_id",
    "name",
    "description",
    "enabled",
    "auto_scenario",
    "book_ids",
}
_ENTRY_FIELDS = {
    "action",
    "book_id",
    "entry_id",
    "entry",
    "name",
    "keys",
    "secondary_keys",
    "content",
    "behavior",
    "scenarios",
    "constant",
    "enabled",
    "priority",
    "case_sensitive",
    "match_whole_word",
    "selective",
    "comment",
    "direction",
}
_CARD_FIELDS = {
    "action",
    "card_id",
    "name",
    "description",
    "personality",
    "scenario",
    "system_prompt",
    "post_history_instructions",
    "first_mes",
    "mes_example",
    "group_addendum",
    "linked_book_id",
    "tags",
}
_SESSION_FIELDS = {
    "action",
    "session_id",
    "id",
    "scenario",
    "book_ids",
    "enabled",
    "card_id",
}
_IMPORT_FIELDS = {"kind", "name", "payload", "text", "overwrite"}


def _query(name: str, default: str = "") -> str:
    """Read a query parameter across the request shapes AstrBot 4.x exposes.

    AstrBot's own PluginRequest carries the mapping on the "query" attribute;
    older or Quart-backed hosts use "query_params" / "args". Reading only the
    latter two silently returned the default for every parameter, which made
    every id lookup answer "not found".

    Args:
        name: Query parameter name.
        default: Returned when the parameter is absent or unreadable.

    Returns:
        The parameter value, stripped, or the default.
    """
    for attr in ("query", "query_params", "args"):
        try:
            source = getattr(request, attr, None)
        except Exception:
            continue
        if source is None or not hasattr(source, "get"):
            continue
        try:
            value = source.get(name)
        except Exception:
            continue
        if value is None:
            return default
        return str(value).strip()
    return default


def _client_id() -> str:
    """Dashboard username for rate-limit buckets, or a shared guest bucket."""
    try:
        value = getattr(request, "username", None)
    except Exception:
        value = None
    return str(value or "anonymous")[:128]


async def _body(max_bytes: int = _MAX_BODY_BYTES) -> dict[str, Any]:
    """Parse the JSON request body, returning a sentinel dict on any failure."""
    try:
        declared = getattr(request, "content_length", None)
        if declared is None:
            try:
                declared = request.headers.get("content-length")
            except Exception:
                declared = None
        if declared is not None and int(declared) > max_bytes:
            return {"__invalid__": "请求体过大"}
    except (TypeError, ValueError):
        pass
    try:
        loader = getattr(request, "json", None)
        if not callable(loader):
            return {"__invalid__": "请求体格式不正确"}
        try:
            payload = loader(default=None)
        except TypeError:
            payload = loader()
        if hasattr(payload, "__await__"):
            payload = await payload
    except Exception:
        return {"__invalid__": "请求体不是合法 JSON"}
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        return {"__invalid__": "请求体必须是 JSON 对象"}
    return payload


def _ok(data: Any):
    return json_response(
        {"status": "ok", "ok": True, "data": data, "error": None, "message": None},
        status_code=200,
    )


def _err(message: str, status_code: int = 400):
    return error_response(message, status_code=status_code, data=None)


def _text(value: Any, limit: int = 200000) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value[:limit]
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def _str_list(value: Any, limit: int = 200) -> list[str]:
    """Coerce a panel value into a de-duplicated list of short strings."""
    if isinstance(value, str):
        items = value.replace("，", ",").replace("\n", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        items = list(value)
    else:
        items = []
    result: list[str] = []
    for item in items[:limit]:
        text = str(item if item is not None else "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off", ""}:
            return False
    return default


def _int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class WorldBookWebAPI:
    """Registers and serves the management-page endpoints."""

    def __init__(self, plugin: Any) -> None:
        self.plugin = plugin
        self.registered = False
        self._buckets: dict[tuple[str, str], list[float]] = {}

    # ----------------------------------------------------------- lifecycle

    @property
    def settings(self):
        return self.plugin.settings

    @property
    def store(self):
        return self.plugin.store

    def register(self) -> None:
        """Publish every route on the host Web server (idempotent)."""
        context = getattr(self.plugin, "context", None)
        if context is None or not hasattr(context, "register_web_api"):
            logger.warning("%s: host context has no register_web_api", PLUGIN_NAME)
            return
        routes = [
            ("overview", self.overview, ["GET"], "世界书面板总览"),
            ("book", self.book_get, ["GET"], "世界书详情"),
            ("book", self.book_post, ["POST"], "世界书新建/改名/开关/删除"),
            ("entry", self.entry_post, ["POST"], "世界书条目增删改"),
            ("card", self.card_get, ["GET"], "角色卡详情"),
            ("card", self.card_post, ["POST"], "角色卡改/设默认/删除"),
            ("session", self.session_post, ["POST"], "会话世界书开关与场景"),
            ("preview", self.preview, ["GET"], "注入效果预览"),
            ("import", self.import_post, ["POST"], "导入世界书或角色卡 JSON"),
        ]
        for endpoint, handler, methods, desc in routes:
            try:
                if methods == ["POST"] and hasattr(self.plugin, "owner"):
                    original = handler
                    async def serialized(original=original):
                        async with self.plugin.owner._migration_lock:
                            if self.plugin is not self.plugin.owner.world:
                                return _err("世界已重新加载，请刷新后重试", 409)
                            return await original()
                    handler = serialized
                context.register_web_api(f"/{PLUGIN_NAME}/{endpoint}", handler, methods, desc)
            except Exception as e:
                logger.warning("%s: register %s failed: %s", PLUGIN_NAME, endpoint, e)
        self.registered = True

    # ------------------------------------------------------------- guards

    def _rate_limited(self, endpoint: str, limit: int) -> bool:
        now = time.monotonic()
        key = (endpoint, _client_id())
        bucket = [stamp for stamp in self._buckets.get(key, []) if now - stamp < 60.0]
        if len(bucket) >= limit:
            self._buckets[key] = bucket
            return True
        bucket.append(now)
        self._buckets[key] = bucket
        if len(self._buckets) > 2048:
            self._buckets = {
                k: v for k, v in self._buckets.items() if v and v[-1] >= now - 60.0
            }
        return False

    def _guard(self, endpoint: str, *, write: bool):
        """Return an error response when the call must not proceed, else None."""
        owner = getattr(self.plugin, "owner", None)
        if owner is not None and (owner._migrating or owner._terminating):
            return _err("世界正在切换，请稍后重试", 409)
        limit = _WRITE_LIMIT_PER_MINUTE if write else _READ_LIMIT_PER_MINUTE
        if self._rate_limited(endpoint, limit):
            return _err("请求过于频繁，请稍后再试", 429)
        if not self.settings.web_panel_enabled:
            return _err("面板接口已在插件配置 web_panel.enabled 中关闭", 403)
        if write and not self.settings.web_panel_allow_write:
            return _err("面板处于只读模式（web_panel.allow_write=false）", 403)
        return None

    @staticmethod
    def _reject_unknown(body: dict[str, Any], allowed: set[str]):
        if "__invalid__" in body:
            return _err(str(body["__invalid__"]))
        unknown = sorted(set(body) - allowed)
        if unknown:
            return _err("不支持的字段：" + ", ".join(unknown))
        return None

    # --------------------------------------------------------------- read

    async def overview(self):
        limited = self._guard("overview", write=False)
        if limited is not None:
            return limited
        try:
            return _ok(self._overview_payload())
        except Exception as e:
            logger.error("%s: overview failed: %s", PLUGIN_NAME, e, exc_info=True)
            return _err("读取世界书数据失败", 500)

    def _overview_payload(self) -> dict[str, Any]:
        raw_store = getattr(self.store, "_store", None)
        books = self.store.list_books()
        cards = self.store.list_cards()
        sessions_raw = getattr(raw_store, "sessions", {}) or {}
        ordered = sorted(sessions_raw.items(), key=lambda kv: kv[1].last_active, reverse=True)
        scenarios: set[str] = set()
        for book in books:
            scenarios.update(book.list_scenarios())
        return {
            "capabilities": {
                "panel_enabled": self.settings.web_panel_enabled,
                "write": bool(
                    self.settings.web_panel_enabled and self.settings.web_panel_allow_write
                ),
            },
            "config": self.settings.panel_snapshot(),
            "books": [self._book_summary(b) for b in books],
            "cards": [self._card_summary(c) for c in cards],
            "default_card_id": self.store.get_default_card_id(),
            "active_book_ids": list(getattr(raw_store, "active_book_ids", []) or []),
            "sessions": [self._session_row(sid, st) for sid, st in ordered[:80]],
            "scenarios": sorted(scenarios),
        }

    def _book_summary(self, book: WorldBook) -> dict[str, Any]:
        return {
            "id": book.id,
            "name": book.name,
            "description": book.description,
            "enabled": book.enabled,
            "auto_scenario": book.auto_scenario,
            "entry_count": len(book.entries),
            "enabled_entry_count": sum(1 for e in book.entries if e.enabled),
            "constant_count": sum(1 for e in book.entries if e.constant),
            "scenarios": book.list_scenarios(),
            "updated_at": book.updated_at,
        }

    def _card_summary(self, card: Any) -> dict[str, Any]:
        return {
            "id": card.id,
            "name": card.name,
            "source": card.source,
            "tags": list(card.tags),
            "linked_book_id": card.linked_book_id,
            "persona_id": card.persona_id,
            "has_group_addendum": bool(card.group_addendum),
            "has_examples": bool(card.mes_example),
            "updated_at": card.updated_at,
        }

    def _session_row(self, sid: str, state: Any) -> dict[str, Any]:
        card_id = str(state.card_id or "")
        if card_id == SESSION_CARD_NONE:
            card_label = "已关闭"
        elif card_id:
            card = self.store.get_card(card_id)
            card_label = card.name if card else "(已删除)"
        else:
            default_id = self.store.get_default_card_id()
            card = self.store.get_card(default_id) if default_id else None
            card_label = f"{card.name}（默认）" if card else "无"
        return {
            "session_id": sid,
            "enabled": state.enabled,
            "scenario": state.scenario,
            "scenario_auto": state.scenario_auto,
            "book_ids": list(state.book_ids),
            "card_id": card_id,
            "card_label": card_label,
            "last_matched": list(state.last_matched),
            "last_active": state.last_active,
        }

    async def book_get(self):
        limited = self._guard("book_get", write=False)
        if limited is not None:
            return limited
        book_id = _query("book_id") or _query("id")
        book = self.store.get_book(book_id) if book_id else None
        if book is None:
            return _err("未找到该世界书", 404)
        return _ok({"book": self._book_detail(book)})

    async def card_get(self):
        limited = self._guard("card_get", write=False)
        if limited is not None:
            return limited
        card_id = _query("card_id") or _query("id")
        card = self.store.get_card(card_id) if card_id else None
        if card is None:
            return _err("未找到该角色卡", 404)
        return _ok({"card": self._card_detail(card)})

    async def preview(self):
        limited = self._guard("preview", write=False)
        if limited is not None:
            return limited
        book_id = _query("book_id")
        book = self.store.get_book(book_id) if book_id else None
        if book is None:
            return _err("未找到该世界书", 404)
        text = _query("keys") or _query("text")
        scenario = _query("scenario")
        wanted = _str_list(_query("entry_ids"))
        limit = _int(_query("limit") or 10, 10)
        if wanted:
            wanted_set = set(wanted)
            chosen = [e for e in book.entries if e.uid in wanted_set]
        else:
            result = match_entries(
                [book],
                text,
                active_scenario=scenario,
                max_entries=limit,
                allow_auto_scenario=self.settings.auto_scenario,
                dedupe_same_content=self.settings.dedupe_same_content,
            )
            chosen = [m.entry for m in result.matched]
        rendered = MatchResult(
            matched=[MatchedEntry(book=book, entry=e) for e in chosen],
            auto_scenario=scenario,
        )
        return _ok(
            {
                "matched": [
                    {"uid": e.uid, "title": e.display_name(), "constant": e.constant}
                    for e in chosen
                ],
                "text": build_injection_text(
                    rendered, active_scenario=scenario, style=self.settings
                ),
            }
        )

    # -------------------------------------------------------------- write

    async def book_post(self):
        limited = self._guard("book_post", write=True)
        if limited is not None:
            return limited
        body = await _body()
        invalid = self._reject_unknown(body, _BOOK_FIELDS)
        if invalid is not None:
            return invalid
        action = _text(body.get("action")).strip().lower()
        try:
            return self._apply_book_action(action, body)
        except Exception as e:
            logger.error(
                "%s: book action %s failed: %s", PLUGIN_NAME, action, e, exc_info=True
            )
            return _err("保存世界书失败", 500)

    def _apply_book_action(self, action: str, body: dict[str, Any]):
        if action == "create":
            name = _text(body.get("name")).strip()
            if not name:
                return _err("世界书名称不能为空")
            if self.store.find_book_by_name(name) is not None:
                return _err("已存在同名世界书")
            book = WorldBook(
                name=name,
                description=_text(body.get("description")).strip(),
                enabled=_bool(body.get("enabled"), True),
                auto_scenario=_bool(body.get("auto_scenario"), True),
            )
            self.store.upsert_book(book)
            return _ok({"book": self._book_detail(book)})

        if action == "set_global_active":
            ids = _str_list(body.get("book_ids"))
            known = {b.id for b in self.store.list_books()}
            unknown = [i for i in ids if i not in known]
            if unknown:
                return _err("未知世界书 id：" + ", ".join(unknown))
            self.store.set_global_active_books(ids)
            return _ok({"active_book_ids": ids})

        book_id = _text(body.get("book_id")).strip()
        book = self.store.get_book(book_id) if book_id else None
        if book is None:
            return _err("未找到该世界书", 404)

        if action == "update":
            if "name" in body:
                name = _text(body.get("name")).strip()
                if not name:
                    return _err("世界书名称不能为空")
                book.name = name
            if "description" in body:
                book.description = _text(body.get("description")).strip()
            if "enabled" in body:
                book.enabled = _bool(body.get("enabled"), book.enabled)
            if "auto_scenario" in body:
                book.auto_scenario = _bool(body.get("auto_scenario"), book.auto_scenario)
            self.store.upsert_book(book)
            return _ok({"book": self._book_detail(book)})

        if action == "delete":
            self.store.delete_book(book.id)
            return _ok({"deleted": book.id})

        return _err("未知操作：" + (action or "(空)"))

    async def entry_post(self):
        limited = self._guard("entry_post", write=True)
        if limited is not None:
            return limited
        body = await _body()
        invalid = self._reject_unknown(body, _ENTRY_FIELDS)
        if invalid is not None:
            return invalid
        book_id = _text(body.get("book_id")).strip()
        book = self.store.get_book(book_id) if book_id else None
        if book is None:
            return _err("未找到该世界书", 404)
        action = _text(body.get("action")).strip().lower()
        try:
            if action == "create":
                entry = self._entry_from_body(WorldEntry(uid=new_uid()), body)
                if not entry.content and not entry.behavior:
                    return _err("条目正文不能为空")
                self.store.add_entry(book.id, entry)
                return _ok({"entry": entry.to_dict()})

            entry_id = _text(body.get("entry_id") or body.get("entry")).strip()
            entry = book.get_entry(entry_id) if entry_id else None
            if entry is None:
                return _err("未找到该条目", 404)

            if action == "update":
                updated = self._entry_from_body(WorldEntry.from_dict(entry.to_dict()), body)
                if not updated.content and not updated.behavior:
                    return _err("条目正文不能为空")
                self.store.add_entry(book.id, updated)
                return _ok({"entry": updated.to_dict()})

            if action == "delete":
                self.store.remove_entry(book.id, entry.uid)
                return _ok({"deleted": entry.uid})

            if action == "duplicate":
                clone = WorldEntry.from_dict(entry.to_dict())
                clone.uid = new_uid()
                clone.name = (clone.name or clone.display_name()) + " 副本"
                self.store.add_entry(book.id, clone)
                return _ok({"entry": clone.to_dict()})

            if action == "move":
                return self._move_entry(book, entry.uid, _text(body.get("direction")).lower())

            return _err("未知操作：" + (action or "(空)"))
        except Exception as e:
            logger.error(
                "%s: entry action %s failed: %s", PLUGIN_NAME, action, e, exc_info=True
            )
            return _err("保存条目失败", 500)

    def _move_entry(self, book: WorldBook, uid: str, direction: str):
        uids = [e.uid for e in book.entries]
        if uid not in uids:
            return _err("未找到该条目", 404)
        index = uids.index(uid)
        target = index - 1 if direction == "up" else index + 1
        if target < 0 or target >= len(uids):
            entry = book.get_entry(uid)
            return _ok({"entry": entry.to_dict() if entry else None})
        entries = list(book.entries)
        entries[index], entries[target] = entries[target], entries[index]
        book.entries = entries
        self.store.upsert_book(book)
        entry = book.get_entry(uid)
        return _ok({"entry": entry.to_dict() if entry else None})

    @staticmethod
    def _entry_from_body(target: WorldEntry, body: dict[str, Any]) -> WorldEntry:
        """Apply whitelisted body fields onto an entry, leaving the rest intact."""
        if "name" in body:
            target.name = _text(body.get("name"), 500).strip()
        if "keys" in body:
            target.keys = _str_list(body.get("keys"))
        if "secondary_keys" in body:
            target.secondary_keys = _str_list(body.get("secondary_keys"))
        if "content" in body:
            target.content = _text(body.get("content")).strip()
        if "behavior" in body:
            target.behavior = _text(body.get("behavior"), 20000).strip()
        if "scenarios" in body:
            target.scenarios = _str_list(body.get("scenarios"))
        if "constant" in body:
            target.constant = _bool(body.get("constant"), target.constant)
        if "enabled" in body:
            target.enabled = _bool(body.get("enabled"), target.enabled)
        if "priority" in body:
            target.priority = _int(body.get("priority"), target.priority)
        if "case_sensitive" in body:
            target.case_sensitive = _bool(body.get("case_sensitive"), target.case_sensitive)
        if "match_whole_word" in body:
            target.match_whole_word = _bool(
                body.get("match_whole_word"), target.match_whole_word
            )
        if "selective" in body:
            target.selective = _bool(body.get("selective"), target.selective)
        if "comment" in body:
            target.comment = _text(body.get("comment"), 2000).strip()
        return target

    async def card_post(self):
        limited = self._guard("card_post", write=True)
        if limited is not None:
            return limited
        body = await _body()
        invalid = self._reject_unknown(body, _CARD_FIELDS)
        if invalid is not None:
            return invalid
        action = _text(body.get("action")).strip().lower()
        card_id = _text(body.get("card_id")).strip()
        try:
            if action == "create":
                return self._create_card(body)

            if action == "set_default":
                if card_id and self.store.get_card(card_id) is None:
                    return _err("未找到该角色卡", 404)
                self.store.set_default_card(card_id)
                return _ok({"default_card_id": self.store.get_default_card_id()})

            card = self.store.get_card(card_id) if card_id else None
            if card is None:
                return _err("未找到该角色卡", 404)

            if action == "update":
                self._card_from_body(card, body)
                self.store.upsert_card(card)
                return _ok({"card": self._card_detail(card)})

            if action == "delete":
                self.store.delete_card(card.id)
                return _ok({"deleted": card.id})

            return _err("未知操作：" + (action or "(空)"))
        except Exception as e:
            logger.error(
                "%s: card action %s failed: %s", PLUGIN_NAME, action, e, exc_info=True
            )
            return _err("保存角色卡失败", 500)

    def _create_card(self, body: dict[str, Any]):
        """Build a card from panel fields so one can be written without JSON.

        Args:
            body: Request body already narrowed to the card field whitelist.

        Returns:
            A JSON response carrying the stored card.
        """
        name = _text(body.get("name"), 200).strip()
        if not name:
            return _err("角色卡名称不能为空")
        if self.store.find_card_by_name(name) is not None:
            return _err("已存在同名角色卡：" + name)

        card = self._card_from_body(CharacterCard(name=name), body)
        self.store.upsert_card(card)
        # 库里还没有默认卡时顺手顶上，省得新建完还要再点一次「设为默认」
        if not self.store.get_default_card_id():
            self.store.set_default_card(card.id)
        return _ok({"card": self._card_detail(card)})

    @staticmethod
    def _card_from_body(card: Any, body: dict[str, Any]) -> Any:
        text_fields = {
            "description": 60000,
            "personality": 60000,
            "scenario": 60000,
            "system_prompt": 60000,
            "post_history_instructions": 60000,
            "first_mes": 60000,
            "mes_example": 200000,
            "group_addendum": 60000,
            "linked_book_id": 200,
        }
        for field, limit in text_fields.items():
            if field in body:
                setattr(card, field, _text(body.get(field), limit))
        if "name" in body:
            name = _text(body.get("name"), 200).strip()
            if name:
                card.name = name
        if "tags" in body:
            card.tags = _str_list(body.get("tags"))
        return card

    async def session_post(self):
        limited = self._guard("session_post", write=True)
        if limited is not None:
            return limited
        body = await _body()
        invalid = self._reject_unknown(body, _SESSION_FIELDS)
        if invalid is not None:
            return invalid
        session_id = _text(body.get("session_id") or body.get("id")).strip()
        if not session_id:
            return _err("缺少 session_id")
        if len(session_id) > 256:
            return _err("session_id 过长")
        action = _text(body.get("action")).strip().lower()
        try:
            if action == "enable":
                state = self.store.update_session(session_id, enabled=True)
            elif action == "disable":
                state = self.store.update_session(session_id, enabled=False)
            elif action == "set_scenario":
                state = self.store.set_scenario(session_id, _text(body.get("scenario"), 200))
            elif action == "clear_scenario":
                state = self.store.clear_scenario(session_id)
            elif action == "set_card":
                card_id = _text(body.get("card_id")).strip()
                if (
                    card_id
                    and card_id != SESSION_CARD_NONE
                    and self.store.get_card(card_id) is None
                ):
                    return _err("未找到该角色卡", 404)
                state = self.store.update_session(session_id, card_id=card_id)
            elif action == "bind_books":
                ids = _str_list(body.get("book_ids"))
                known = {b.id for b in self.store.list_books()}
                unknown = [i for i in ids if i not in known]
                if unknown:
                    return _err("未知世界书 id：" + ", ".join(unknown))
                state = self.store.update_session(session_id, book_ids=ids)
            elif action == "forget":
                raw_store = getattr(self.store, "_store", None)
                if raw_store is not None:
                    raw_store.sessions.pop(session_id, None)
                    self.store.save()
                return _ok({"deleted": session_id})
            else:
                return _err("未知操作：" + (action or "(空)"))
        except Exception as e:
            logger.error(
                "%s: session action %s failed: %s", PLUGIN_NAME, action, e, exc_info=True
            )
            return _err("保存会话状态失败", 500)
        return _ok({"session": self._session_row(session_id, state)})

    async def import_post(self):
        limited = self._guard("import_post", write=True)
        if limited is not None:
            return limited
        body = await _body()
        invalid = self._reject_unknown(body, _IMPORT_FIELDS)
        if invalid is not None:
            return invalid
        kind = _text(body.get("kind")).strip().lower()
        name = _text(body.get("name"), 200).strip()
        raw = body.get("payload")
        text = _text(body.get("text"))
        source = raw if raw is not None else text
        overwrite = _bool(body.get("overwrite"), False)
        try:
            if kind in {"worldbook", "book", "世界书"}:
                from .importer import import_worldbook

                book = import_worldbook(source, default_name=name or "导入的世界书")
                if name:
                    book.name = name
                existing = self.store.find_book_by_name(book.name)
                if existing is not None and not overwrite:
                    return _err("已存在同名世界书：" + book.name + "（勾选覆盖后再试）", 409)
                if existing is not None:
                    book.id = existing.id
                self.store.upsert_book(book)
                return _ok({"book": self._book_detail(book)})

            if kind in {"card", "character", "角色卡"}:
                from .character import import_character_card

                card = import_character_card(source, default_name=name)
                if name:
                    card.name = name
                existing = self.store.find_card_by_name(card.name)
                if existing is not None and not overwrite:
                    return _err("已存在同名角色卡：" + card.name + "（勾选覆盖后再试）", 409)
                if existing is not None:
                    card.id = existing.id
                    card.persona_id = existing.persona_id
                self.store.upsert_card(card)
                return _ok({"card": self._card_detail(card)})

            return _err("kind 必须是 worldbook 或 card")
        except Exception as e:
            logger.error("%s: import failed: %s", PLUGIN_NAME, e, exc_info=True)
            return _err("导入失败：" + str(e))

    # --------------------------------------------------------- serializers

    def _book_detail(self, book: WorldBook) -> dict[str, Any]:
        data = self._book_summary(book)
        data["entries"] = [e.to_dict() for e in book.entries]
        return data

    def _card_detail(self, card: Any) -> dict[str, Any]:
        data = self._card_summary(card)
        data.update(
            {
                "description": card.description,
                "personality": card.personality,
                "scenario": card.scenario,
                "system_prompt": card.system_prompt,
                "post_history_instructions": card.post_history_instructions,
                "first_mes": card.first_mes,
                "mes_example": card.mes_example,
                "group_addendum": card.group_addendum,
                "alternate_greetings": list(card.alternate_greetings),
                "creator_notes": card.creator_notes,
            }
        )
        return data


__all__ = ["WorldBookWebAPI"]
