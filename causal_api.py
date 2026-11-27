"""Authenticated observation and revision-checked life administration."""
from .world.core.character import CharacterCard
from .world.core.models import new_uid
from .world.core.web_api import _body, _err, _ok, _query


def _worldbook_neighbor_candidates(store, *, exclude_names: set[str], limit: int = 8) -> list[dict]:
    """Extract candidate neighbor character names/descriptions from enabled worldbooks."""
    out: list[dict] = []
    seen = {n.strip().lower() for n in exclude_names if n}
    try:
        books = store.list_books()
    except Exception:
        return []
    for book in books:
        if not getattr(book, "enabled", True):
            continue
        for entry in getattr(book, "entries", []) or []:
            if not getattr(entry, "enabled", True):
                continue
            raw_name = str(getattr(entry, "name", "") or "").strip()
            if not raw_name or len(raw_name) > 24:
                continue
            if any(skip in raw_name for skip in ("规则", "说明", "设定", "世界观", "目录", "附录", "系统", "提示")):
                continue
            low = raw_name.lower()
            if low in seen:
                continue
            content = str(getattr(entry, "content", "") or "").strip()
            keys = [str(k).strip() for k in (getattr(entry, "keys", None) or []) if str(k).strip()]
            # Prefer entries that look like character profiles or short named entities
            looks_char = any(
                tok in (raw_name + " " + content[:80])
                for tok in ("角色", "人物", "性格", "外貌", "同学", "邻居", "友人", "同伴", "魔女", "老师", "少女", "少年")
            ) or (1 <= len(raw_name) <= 8 and len(keys) >= 1)
            if not looks_char:
                continue
            seen.add(low)
            out.append(
                {
                    "name": raw_name,
                    "book_name": str(getattr(book, "name", "") or ""),
                    "description": content[:260],
                }
            )
            if len(out) >= limit:
                return out
    return out


class CausalAPIMixin:
    async def causal_get(self):
        guard = await self.guard("life")
        if guard is not None:
            return guard
        try:
            scope, _ = await self.scope(_query("umo"))
            engine = self.plugin.life.narrative
            viewer = _query("viewer") or "admin"
            with engine._db() as db:
                result = engine.causal.projection(db, scope, engine.clock(), viewer=viewer, actor_id=_query("actor_id") or "self")
            result["can_write"] = self.plugin.world.web.settings.web_panel_allow_write and viewer == "admin"
            if viewer == "admin":
                cards = self.plugin.world.store.list_cards()
                result["cards"] = [{"id": c.id, "name": c.name} for c in cards if c.persona_id != scope["persona_id"]]
                exclude = {c.name for c in cards}
                exclude.update(str(r.get("name") or "") for r in (result.get("residents") or []))
                result["worldbook_characters"] = _worldbook_neighbor_candidates(
                    self.plugin.world.store, exclude_names=exclude, limit=8
                )
                result["plan_status"] = engine.get_plan_status(scope)
            return _ok(result)
        except (ValueError, TypeError) as exc:
            return _err(str(exc), 409)

    async def causal_post(self):
        async with self.plugin._migration_lock:
            guard = await self.guard("life", True)
            if guard is not None:
                return guard
            try:
                body = await _body()
                allowed = {
                    "umo",
                    "action",
                    "expected_revision",
                    "request_id",
                    "changes",
                    "card_id",
                    "place_id",
                    "actor_id",
                    "enabled",
                    "invitation_id",
                    "name",
                    "description",
                    "personality",
                }
                if not isinstance(body, dict) or set(body) - allowed:
                    raise ValueError("未知生活管理字段")
                scope, _ = await self.scope(body.get("umo", ""))
                if body.get("action") == "evaluate_resident":
                    rid=body.get("request_id")
                    if not isinstance(rid,str) or not 8<=len(rid)<=100 or not isinstance(body.get("actor_id"),str):
                        raise ValueError("需要居民标识和幂等请求标识")
                    if scope["persona_id"] != self.plugin.life.narrative.config.get("persona_id"):
                        raise ValueError("仅可推进当前运行世界的居民")
                    result=await self.plugin.life.residents.tick(actor_id=body["actor_id"],request_id=rid,manual=True)
                    self.bus.notify()
                    return _ok(result)
                if body.get("action") == "quick_register_neighbor":
                    name = str(body.get("name") or "").strip()[:32]
                    if not name:
                        raise ValueError("请填写邻居角色名称")
                    place_id = str(body.get("place_id") or "").strip()
                    if not place_id:
                        raise ValueError("请选择邻居的初始地点")
                    store = self.plugin.world.store
                    existing = store.find_card(name)
                    if existing is not None and existing.persona_id == scope.get("persona_id"):
                        raise ValueError("该名称与当前主角色相同，请换一位人物")
                    if existing is None:
                        card_obj = CharacterCard(
                            id=new_uid("card"),
                            name=name,
                            description=str(body.get("description") or f"{name}，住在附近世界里的邻里人物。")[:1200],
                            personality=str(body.get("personality") or "")[:600],
                            source="worldbook_neighbor",
                        )
                        store.upsert_card(card_obj)
                    else:
                        card_obj = existing
                    reg_body = {
                        "action": "resident",
                        "expected_revision": body.get("expected_revision"),
                        "card_id": card_obj.id,
                        "place_id": place_id,
                    }
                    result = self.plugin.life.narrative.causal.administer(
                        scope, reg_body, card=card_obj.to_dict()
                    )
                    result["created_card"] = {"id": card_obj.id, "name": card_obj.name}
                    self.bus.notify()
                    return _ok(result)
                card = self.plugin.world.store.get_card(body.get("card_id")) if body.get("action") == "resident" else None
                result = self.plugin.life.narrative.causal.administer(scope, body, card=card.to_dict() if card else None)
                self.bus.notify()
                return _ok(result)
            except (ValueError, TypeError) as exc:
                return _err(str(exc), 409)
