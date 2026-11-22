"""Additive, read-only v2.0 series capability hooks and Today's Living Journal aggregator."""

from __future__ import annotations

import asyncio
import inspect
import math
import time
from datetime import datetime, timedelta, timezone

from .series_panels import is_series_group_excluded, resolve_series_timezone

_TZ_SHANGHAI = timezone(timedelta(hours=8))
_INVALID_BOUNDS = object()
_UNBOUND_PERSONA_SENTINELS = frozenset({"__none__", "[%None]"})
_VALID_TONES = frozenset({"accent", "warm", "info", "danger", "muted"})
_VALID_CATEGORIES = frozenset(
    {
        "world",
        "horizons",
        "learning",
        "memory",
        "games",
        "visual_media",
        "group_chronicle",
    }
)

_JOURNAL_SIBLINGS = (
    ("astrbot_plugin_dynamics_horizons", "horizons", "群间见闻", "accent", "horizons"),
    ("astrbot_plugin_dynamics_learning", "learning", "群间学习", "warm", "review"),
    ("astrbot_plugin_dynamics_memory", "memory", "群间记忆", "accent", "dashboard"),
    ("astrbot_plugin_dynamics_games", "games", "群间游戏", "info", "games"),
    ("astrbot_plugin_visual_media", "visual_media", "视觉工坊", "warm", "workshop"),
    (
        "astrbot_plugin_group_chronicle",
        "group_chronicle",
        "群文化沿革",
        "info",
        "culture",
    ),
)


def _plugin_tz(plugin):
    cfg = getattr(plugin, "config", None)
    explicit = str(cfg.get("timezone", "") or "") if isinstance(cfg, dict) or hasattr(cfg, "get") else ""
    return resolve_series_timezone(getattr(plugin, "context", None), explicit_tz=explicit)


def _iso_from_ts(ts: float | int | None, *, tz=None) -> str:
    zone = tz or _TZ_SHANGHAI
    try:
        val = float(ts) if ts is not None else time.time()
        return datetime.fromtimestamp(val, tz=zone).isoformat(
            timespec="seconds"
        )
    except (OSError, OverflowError, TypeError, ValueError):
        return datetime.now(tz=zone).isoformat(timespec="seconds")


def _parse_occurred_at(raw, fallback_ts: float, *, tz=None) -> tuple[float, str, str]:
    zone = tz or _TZ_SHANGHAI
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        ts = float(raw)
        dt = datetime.fromtimestamp(ts, tz=zone)
        return ts, dt.isoformat(timespec="seconds"), dt.strftime("%H:%M")
    if isinstance(raw, str) and raw.strip():
        text = raw.strip()
        try:
            normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
            dt = datetime.fromisoformat(normalized)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=zone)
            dt_local = dt.astimezone(zone)
            return (
                dt_local.timestamp(),
                dt_local.isoformat(timespec="seconds"),
                dt_local.strftime("%H:%M"),
            )
        except ValueError:
            try:
                ts = float(text)
                dt = datetime.fromtimestamp(ts, tz=zone)
                return ts, dt.isoformat(timespec="seconds"), dt.strftime("%H:%M")
            except (OSError, OverflowError, ValueError):
                pass
    dt = datetime.fromtimestamp(fallback_ts, tz=zone)
    return fallback_ts, dt.isoformat(timespec="seconds"), dt.strftime("%H:%M")


def _coerce_explicit_bounds(
    start_ts: float | None, end_ts: float | None
) -> tuple[float, float] | None | object:
    """Validate optional explicit [start_ts, end_ts) timestamps shared across plugins."""
    if start_ts is None and end_ts is None:
        return None
    if start_ts is None or end_ts is None:
        return _INVALID_BOUNDS
    if isinstance(start_ts, bool) or isinstance(end_ts, bool):
        return _INVALID_BOUNDS
    try:
        start = float(start_ts)
        end = float(end_ts)
    except (TypeError, ValueError):
        return _INVALID_BOUNDS
    if not (math.isfinite(start) and math.isfinite(end)) or end <= start:
        return _INVALID_BOUNDS
    return start, end


def _day_bounds(date_spec: str, now_ts: float, *, tz=None) -> tuple[float, float] | None:
    zone = tz or _TZ_SHANGHAI
    clean = str(date_spec or "today").strip().lower()
    if clean in {"all", "*"}:
        return None
    if clean in {"", "today"}:
        now_dt = datetime.fromtimestamp(now_ts, tz=zone)
        start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return start.timestamp(), end.timestamp()
    if clean == "yesterday":
        now_dt = datetime.fromtimestamp(now_ts, tz=zone)
        end = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=1)
        return start.timestamp(), end.timestamp()
    try:
        parsed = datetime.strptime(clean[:10], "%Y-%m-%d").replace(tzinfo=zone)
        return parsed.timestamp(), (parsed + timedelta(days=1)).timestamp()
    except ValueError:
        now_dt = datetime.fromtimestamp(now_ts, tz=zone)
        start = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return start.timestamp(), (start + timedelta(days=1)).timestamp()


def _read_session_and_card(store, clean_umo: str):
    """Read-only lookup of (session_state, card, explicitly_disabled) without mutating sessions."""
    if store is None:
        return None, None, False
    snap_fn = getattr(store, "snapshot_context_inputs", None)
    if callable(snap_fn) and clean_umo:
        try:
            state, card, _ = snap_fn(clean_umo)
            disabled = (
                not getattr(state, "enabled", True)
                or not getattr(state, "inject_card_prompt", True)
                or getattr(state, "card_id", "") == "__none__"
            )
            return state, card, disabled
        except Exception:
            pass
    try:
        raw_sessions = getattr(getattr(store, "_store", None), "sessions", None)
        sess = (
            raw_sessions.get(clean_umo)
            if isinstance(raw_sessions, dict) and clean_umo
            else None
        )
        cid = getattr(sess, "card_id", "") if sess is not None else ""
        if sess is not None and (
            not getattr(sess, "enabled", True)
            or not getattr(sess, "inject_card_prompt", True)
            or cid == "__none__"
        ):
            return sess, None, True
        card = store.get_card(cid) if cid else None
        if card is None:
            default_id = store.get_default_card_id()
            if default_id:
                card = store.get_card(default_id)
        return sess, card, False
    except Exception:
        return None, None, False


def _card_persona_id(card) -> str:
    if card is None:
        return ""
    pid = str(getattr(card, "persona_id", "") or "").strip()
    if pid:
        return pid
    cid = str(getattr(card, "id", "") or "").strip()
    return f"wb_{cid}" if cid else ""


def _resolve_sync_scope(
    plugin, umo: str = "", persona: str = "", *, strict: bool = False
) -> dict | None:
    """Resolve a World narrative scope synchronously and read-only.

    When ``strict`` is True (used by Living Journal aggregation/queries), an
    explicitly unbound/disabled group or a group with no bound/default card in
    ``world.store`` returns ``None`` instead of broadening or guessing a card.
    """
    clean_umo = str(umo or "").strip()
    clean_persona = str(persona or "").strip()
    if clean_persona in _UNBOUND_PERSONA_SENTINELS:
        return None
    store = getattr(getattr(plugin, "world", None), "store", None)
    cfg = getattr(plugin, "config", None) or {}
    if not clean_umo and not (strict and clean_persona):
        sessions = list(cfg.get("narrative_sessions") or [])
        if sessions:
            clean_umo = str(sessions[0]).strip()
        elif store is not None:
            raw_sessions = getattr(getattr(store, "_store", None), "sessions", None)
            if isinstance(raw_sessions, dict) and raw_sessions:
                clean_umo = str(next(iter(raw_sessions.keys()))).strip()
    _, card, disabled = _read_session_and_card(store, clean_umo)
    if disabled:
        return None
    if not strict and card is None and store is not None:
        try:
            cards = store.list_cards()
            if cards:
                card = cards[0]
        except Exception:
            card = None
    card_persona = _card_persona_id(card)
    if strict:
        if clean_persona:
            persona_id = clean_persona
        elif card_persona:
            persona_id = card_persona
        elif store is None:
            persona_id = str(cfg.get("persona_id") or "").strip()
        else:
            return None
        if not persona_id or persona_id in _UNBOUND_PERSONA_SENTINELS:
            return None
    else:
        persona_id = (
            clean_persona
            or card_persona
            or str(cfg.get("persona_id") or "").strip()
            or "default"
        )
    platform = clean_umo.split(":", 1)[0] if ":" in clean_umo else ""
    return {
        "platform": platform,
        "umo": clean_umo,
        "persona_id": persona_id,
        "instance_id": persona_id,
    }


def _now_ts(plugin) -> float:
    narrative = getattr(getattr(plugin, "life", None), "narrative", None)
    clock = getattr(narrative, "clock", None)
    if callable(clock):
        try:
            return float(clock())
        except Exception:
            pass
    return time.time()


def build_series_summary(plugin) -> dict:
    """Public synchronous summary for series_presence v2 badges and live pulse."""
    now = _now_ts(plugin)
    tz = _plugin_tz(plugin)
    updated_at = _iso_from_ts(now, tz=tz)
    try:
        conflicts = list(plugin.conflicts()) if callable(getattr(plugin, "conflicts", None)) else []
        ready = bool(plugin.runtime_allowed()) if callable(getattr(plugin, "runtime_allowed", None)) else False
        store = getattr(getattr(plugin, "world", None), "store", None)
        card_count = (
            len(store.list_cards())
            if store is not None and callable(getattr(store, "list_cards", None))
            else 0
        )
        sessions = list((getattr(plugin, "config", None) or {}).get("narrative_sessions") or [])

        if conflicts:
            return {
                "badge": {
                    "count": len(conflicts),
                    "tone": "danger",
                    "label": f"{len(conflicts)} 项旧插件冲突",
                },
                "pulse": {
                    "headline": f"检测到旧插件冲突：{'、'.join(conflicts[:2])}",
                    "updated_at": updated_at,
                },
            }

        pending_outreach = 0
        room_label = ""
        activity_label = ""
        weather_label = ""
        paused = False

        narrative = getattr(getattr(plugin, "life", None), "narrative", None)
        scope = _resolve_sync_scope(plugin)
        if narrative is not None and scope is not None:
            try:
                from .life.core.narrative import _identity

                ident = _identity(scope)
                with narrative._db() as db:
                    try:
                        pending_outreach = int(
                            db.execute(
                                "SELECT COUNT(*) FROM intents WHERE identity=? AND status='pending' AND expires>?",
                                (ident, now),
                            ).fetchone()[0]
                        )
                    except Exception:
                        pending_outreach = 0
                    try:
                        scene = narrative.scenes.snapshot(db, scope, now)
                        if isinstance(scene, dict):
                            paused = bool(scene.get("paused"))
                            room_label = str(
                                scene.get("room_name") or scene.get("place_name") or ""
                            ).strip()
                            action = scene.get("action")
                            if isinstance(action, dict) and action.get("label"):
                                activity_label = str(action["label"]).strip()
                    except Exception:
                        pass
                    try:
                        actor = narrative.spatial.snapshot(db, scope, now)
                        env = narrative.environment.snapshot(db, scope, now, actor)
                        cur = (env or {}).get("current") or {}
                        if (env or {}).get("available") and cur.get("label"):
                            temp = cur.get("temperature")
                            weather_label = str(cur.get("label")) + (
                                f" {temp}°C" if isinstance(temp, (int, float)) else ""
                            )
                    except Exception:
                        pass
            except Exception:
                pass

        if not ready:
            headline = f"编辑模式 · {card_count} 张角色卡 · {len(sessions)} 个会话"
            return {
                "badge": {"count": 0, "tone": "muted", "label": "编辑模式"},
                "pulse": {"headline": headline, "updated_at": updated_at},
            }

        headline_parts = [p for p in (room_label, activity_label, weather_label) if p]
        if not headline_parts:
            headline_parts = [f"{card_count} 张角色卡", f"{len(sessions)} 个活跃会话"]
        headline = " · ".join(headline_parts)[:120]

        if pending_outreach > 0:
            return {
                "badge": {
                    "count": pending_outreach,
                    "tone": "warm",
                    "label": f"{pending_outreach} 条待联系",
                },
                "pulse": {"headline": headline, "updated_at": updated_at},
            }
        if paused:
            return {
                "badge": {"count": 0, "tone": "muted", "label": "生活已暂停"},
                "pulse": {"headline": headline, "updated_at": updated_at},
            }
        short_label = (activity_label or room_label or "小屋运行中")[:24]
        return {
            "badge": {"count": 0, "tone": "accent", "label": short_label},
            "pulse": {"headline": headline, "updated_at": updated_at},
        }
    except Exception:
        return {
            "badge": {"count": 0, "tone": "muted", "label": "状态读取中"},
            "pulse": {"headline": "群间世界", "updated_at": updated_at},
        }


def build_series_scope_status(plugin, umo: str) -> dict:
    """Public read-only status for a specific group/session scope in series_matrix."""
    clean_umo = str(umo or "").strip()
    cfg = getattr(plugin, "config", None) or {}
    sessions = [str(s).strip() for s in (cfg.get("narrative_sessions") or []) if s]
    all_groups = bool(cfg.get("narrative_all_groups"))
    store = getattr(getattr(plugin, "world", None), "store", None)
    unbound = False
    persona_id = str(cfg.get("persona_id") or "")
    if store is not None and clean_umo:
        _, card, disabled = _read_session_and_card(store, clean_umo)
        if disabled:
            unbound = True
            persona_id = ""
        else:
            card_persona = _card_persona_id(card)
            if card_persona:
                persona_id = card_persona
    in_scope = bool(clean_umo and not unbound and (all_groups or clean_umo in sessions))
    ready = bool(plugin.runtime_allowed()) if callable(getattr(plugin, "runtime_allowed", None)) else False
    excluded_by_core = bool(
        clean_umo and is_series_group_excluded(getattr(plugin, "context", None), umo=clean_umo)
    )
    enabled = bool(ready and in_scope and not excluded_by_core)

    activity_today: int | None = None
    if excluded_by_core:
        summary = "主控排除"
    elif enabled:
        summary = "已接入持续生活"
    elif unbound:
        summary = "该会话已解绑角色"
    else:
        summary = "未绑定持续生活"
    narrative = getattr(getattr(plugin, "life", None), "narrative", None)
    scope = _resolve_sync_scope(plugin, umo=clean_umo)
    if narrative is not None and scope is not None:
        try:
            now = _now_ts(plugin)
            tz = _plugin_tz(plugin)
            bounds = _day_bounds("today", now, tz=tz)
            start_ts = bounds[0] if bounds else 0.0
            from .spatial import identity as spatial_identity

            owner = spatial_identity(scope)
            with narrative._db() as db:
                scene_key = narrative.scenes.key(db, scope)
                c_scene = int(
                    db.execute(
                        "SELECT COUNT(*) FROM world_scene_events WHERE identity=? AND occurred>=?",
                        (scene_key, start_ts),
                    ).fetchone()[0]
                )
                c_map = int(
                    db.execute(
                        "SELECT COUNT(*) FROM world_map_events WHERE identity=? AND occurred>=?",
                        (owner, start_ts),
                    ).fetchone()[0]
                )
                activity_today = c_scene + c_map
                scene = narrative.scenes.snapshot(db, scope, now)
                if enabled and isinstance(scene, dict):
                    place = scene.get("room_name") or scene.get("place_name") or ""
                    if scene.get("paused"):
                        summary = "持续生活已暂停"
                    elif place:
                        summary = f"已接入 · {place}"
        except Exception:
            pass

    version = "0"
    onboarding = getattr(plugin, "onboarding", None)
    if onboarding is not None and callable(getattr(onboarding, "revision", None)):
        try:
            version = str(onboarding.revision())
        except Exception:
            version = "0"

    return {
        "enabled": enabled,
        "supported": False,
        "excluded_by_core": excluded_by_core,
        "persona_id": persona_id,
        "activity_today": activity_today,
        "summary": summary,
        "version": version,
    }


def search_world_items(
    plugin, query: str, scope: str = "", limit: int = 8
) -> list[dict]:
    """Read-only fast search across World cards, worldbooks, entries, places and diary."""
    q = str(query or "").strip().lower()
    if not q:
        return []
    try:
        cap = max(1, min(50, int(limit or 8)))
    except (TypeError, ValueError):
        cap = 8

    results: list[dict] = []
    plugin_id = "astrbot_plugin_dynamics_world"
    store = getattr(getattr(plugin, "world", None), "store", None)

    if store is not None:
        try:
            for card in store.list_cards():
                if len(results) >= cap:
                    break
                name = str(getattr(card, "name", "") or "")
                persona = str(getattr(card, "persona_id", "") or "")
                prompt = str(getattr(card, "system_prompt", "") or "")
                hay = f"{name} {persona} {prompt}".lower()
                if q in hay:
                    results.append(
                        {
                            "kind": "character_card",
                            "title": name or card.id,
                            "subtitle": f"角色卡 · {persona or card.id}",
                            "plugin_id": plugin_id,
                            "page": "world",
                            "deep_link": {"view": "cards", "id": card.id},
                        }
                    )
        except Exception:
            pass

        try:
            for book in store.list_books():
                if len(results) >= cap:
                    break
                b_name = str(getattr(book, "name", "") or "")
                b_desc = str(getattr(book, "description", "") or "")
                if q in f"{b_name} {b_desc}".lower():
                    results.append(
                        {
                            "kind": "worldbook",
                            "title": b_name or book.id,
                            "subtitle": (b_desc[:60] or "世界书"),
                            "plugin_id": plugin_id,
                            "page": "world",
                            "deep_link": {"view": "books", "id": book.id},
                        }
                    )
                for entry in getattr(book, "entries", None) or []:
                    if len(results) >= cap:
                        break
                    e_name = str(getattr(entry, "name", "") or "")
                    e_keys = " ".join(str(k) for k in (getattr(entry, "keys", None) or []))
                    e_content = str(getattr(entry, "content", "") or "")
                    if q in f"{e_name} {e_keys} {e_content}".lower():
                        results.append(
                            {
                                "kind": "worldbook_entry",
                                "title": e_name or e_keys[:40] or "世界书条目",
                                "subtitle": f"{b_name or book.id} · {e_content[:56]}",
                                "plugin_id": plugin_id,
                                "page": "world",
                                "deep_link": {
                                    "view": "books",
                                    "id": book.id,
                                    "entry_uid": str(getattr(entry, "uid", "") or ""),
                                },
                            }
                        )
        except Exception:
            pass

    if len(results) < cap:
        narrative = getattr(getattr(plugin, "life", None), "narrative", None)
        resolved = _resolve_sync_scope(plugin, umo=scope)
        if narrative is not None and resolved is not None:
            try:
                from .life.core.narrative import _identity
                from .spatial import identity as spatial_identity

                owner = spatial_identity(resolved)
                ident = _identity(resolved)
                with narrative._db() as db:
                    doc = narrative.spatial.document(db, owner) or {}
                    for place in doc.get("places") or []:
                        if len(results) >= cap:
                            break
                        pname = str(place.get("name") or "")
                        if pname and q in pname.lower():
                            results.append(
                                {
                                    "kind": "world_place",
                                    "title": pname,
                                    "subtitle": "世界地图地点",
                                    "plugin_id": plugin_id,
                                    "page": "world",
                                    "deep_link": {
                                        "view": "map",
                                        "umo": resolved.get("umo", ""),
                                        "place_id": str(place.get("id") or ""),
                                    },
                                }
                            )
                    if len(results) < cap:
                        rows = db.execute(
                            "SELECT occurred, text FROM diary WHERE identity=? ORDER BY occurred DESC LIMIT 40",
                            (ident,),
                        ).fetchall()
                        for row in rows:
                            if len(results) >= cap:
                                break
                            text = str(row["text"] or "")
                            if q in text.lower():
                                results.append(
                                    {
                                        "kind": "world_diary",
                                        "title": text[:48],
                                        "subtitle": f"生活故事 · {_iso_from_ts(row['occurred'], tz=_plugin_tz(plugin))[:16]}",
                                        "plugin_id": plugin_id,
                                        "page": "world",
                                        "deep_link": {
                                            "view": "stories",
                                            "umo": resolved.get("umo", ""),
                                        },
                                    }
                                )
            except Exception:
                pass

    return results[:cap]


def collect_world_journal_events(
    plugin,
    persona: str = "",
    scope: str = "",
    date: str = "today",
    limit: int = 20,
    *,
    start_ts: float | None = None,
    end_ts: float | None = None,
    _resolved: dict | None = None,
) -> list[dict]:
    """Collect World's own living journal events from committed receipts and diary."""
    explicit = _coerce_explicit_bounds(start_ts, end_ts)
    if explicit is _INVALID_BOUNDS:
        return []
    try:
        cap = max(1, min(50, int(limit or 20)))
    except (TypeError, ValueError):
        cap = 20
    narrative = getattr(getattr(plugin, "life", None), "narrative", None)
    resolved = (
        _resolved
        if _resolved is not None
        else _resolve_sync_scope(plugin, umo=scope, persona=persona, strict=True)
    )
    if narrative is None or resolved is None:
        return []

    now = _now_ts(plugin)
    tz = _plugin_tz(plugin)
    bounds = explicit if explicit is not None else _day_bounds(date, now, tz=tz)
    events: list[dict] = []
    plugin_id = "astrbot_plugin_dynamics_world"

    try:
        from .activity_feed import page as feed_page
        from .life.core.narrative import _identity

        ident = _identity(resolved)
        with narrative._db() as db:
            # 1. Committed program receipts (room actions, ecology, map travel, projects)
            try:
                feed = feed_page(narrative, db, resolved, limit=min(50, cap * 2), category="all")
                for row in feed.get("events") or []:
                    ts, iso_str, hhmm = _parse_occurred_at(row.get("occurred_at"), now, tz=tz)
                    if bounds is not None and not (bounds[0] <= ts < bounds[1]):
                        continue
                    status = str(row.get("status") or "completed")
                    tone = "danger" if status in {"failed", "rejected"} else "info"
                    route = (
                        "projects"
                        if row.get("project_id")
                        else "map"
                        if row.get("scope") == "角色地图历史"
                        else "activity"
                    )
                    events.append(
                        {
                            "id": f"world:{row.get('id', '')}",
                            "category": "world",
                            "source_label": "群间世界",
                            "tone": tone,
                            "occurred_at": iso_str,
                            "timestamp": ts,
                            "time_label": hhmm,
                            "title": str(row.get("title") or "小屋动态")[:120],
                            "subtitle": str(
                                row.get("description") or row.get("scope") or ""
                            )[:160],
                            "target_plugin": plugin_id,
                            "target_route": route,
                            "target_id": str(row.get("project_id") or row.get("id") or ""),
                        }
                    )
            except Exception:
                pass

            # 2. Committed diary entries for the day
            try:
                umo_val = resolved.get("umo") or ""
                rows = db.execute(
                    "SELECT rowid, occurred, text, fact_kind FROM diary WHERE identity=? AND umo IN (?, '') ORDER BY occurred DESC LIMIT 20",
                    (ident, umo_val),
                ).fetchall()
                for row in rows:
                    ts, iso_str, hhmm = _parse_occurred_at(row["occurred"], now, tz=tz)
                    if bounds is not None and not (bounds[0] <= ts < bounds[1]):
                        continue
                    text = str(row["text"] or "").strip()
                    if not text:
                        continue
                    events.append(
                        {
                            "id": f"diary:{row['rowid']}",
                            "category": "world",
                            "source_label": "群间世界",
                            "tone": "accent",
                            "occurred_at": iso_str,
                            "timestamp": ts,
                            "time_label": hhmm,
                            "title": text[:88] + ("…" if len(text) > 88 else ""),
                            "subtitle": "生活故事记录",
                            "target_plugin": plugin_id,
                            "target_route": "stories",
                            "target_id": str(row["rowid"]),
                        }
                    )
            except Exception:
                pass
    except Exception:
        return []

    events.sort(key=lambda item: item.get("timestamp", 0.0), reverse=True)
    return events[:cap]


def _normalize_journal_item(
    raw: dict,
    *,
    default_plugin: str,
    default_category: str,
    default_source_label: str,
    default_tone: str,
    default_route: str,
    now_ts: float,
    tz=None,
) -> dict | None:
    if not isinstance(raw, dict):
        return None
    title = str(raw.get("title") or "").strip()
    if not title:
        return None
    ts, iso_str, hhmm = _parse_occurred_at(raw.get("occurred_at"), now_ts, tz=tz)
    category = str(raw.get("category") or default_category).strip().lower()
    if category not in _VALID_CATEGORIES:
        category = default_category
    tone = str(raw.get("tone") or default_tone).strip().lower()
    if tone not in _VALID_TONES:
        tone = default_tone
    source_label = str(raw.get("source_label") or default_source_label).strip()[:32]
    target_plugin = str(raw.get("target_plugin") or default_plugin).strip()
    target_route = str(raw.get("target_route") or default_route).strip()
    target_id = str(raw.get("target_id") or "").strip()[:120]
    item_id = str(raw.get("id") or f"{target_plugin}:{int(ts)}:{title[:16]}").strip()[:120]
    subtitle = str(raw.get("subtitle") or "").strip()[:180]
    return {
        "id": item_id,
        "category": category,
        "source_label": source_label,
        "tone": tone,
        "occurred_at": iso_str,
        "timestamp": ts,
        "time_label": hhmm,
        "title": title[:140],
        "subtitle": subtitle,
        "target_plugin": target_plugin,
        "target_route": target_route,
        "target_id": target_id,
    }


def _sibling_journal_kwargs(
    hook,
    *,
    persona: str,
    scope: str,
    date: str,
    limit: int,
    bounds: tuple[float, float] | None,
) -> dict:
    kwargs: dict = {
        "persona": persona,
        "scope": scope,
        "date": date,
        "limit": limit,
    }
    if bounds is None:
        return kwargs
    try:
        params = inspect.signature(hook).parameters
    except (TypeError, ValueError):
        return kwargs
    accepts_varkw = any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
    )
    if accepts_varkw or ("start_ts" in params and "end_ts" in params):
        kwargs["start_ts"] = bounds[0]
        kwargs["end_ts"] = bounds[1]
    return kwargs


async def _query_sibling_journal(
    owner,
    *,
    plugin_id: str,
    category: str,
    source_label: str,
    tone: str,
    default_route: str,
    persona: str,
    scope: str,
    date: str,
    limit: int,
    now_ts: float,
    bounds: tuple[float, float] | None,
    tz=None,
) -> tuple[str, dict, list[dict]]:
    hook = getattr(owner, "get_journal_events", None)
    if not callable(hook):
        return category, {"available": False, "count": 0}, []
    call_kwargs = _sibling_journal_kwargs(
        hook,
        persona=persona,
        scope=scope,
        date=date,
        limit=limit,
        bounds=bounds,
    )
    try:
        if inspect.iscoroutinefunction(hook):
            raw_items = await asyncio.wait_for(
                hook(**call_kwargs),
                timeout=0.35,
            )
        else:
            raw_items = hook(**call_kwargs)
            if inspect.isawaitable(raw_items):
                raw_items = await asyncio.wait_for(raw_items, timeout=0.35)
    except Exception:
        return category, {"available": False, "count": 0}, []

    if not isinstance(raw_items, (list, tuple)):
        return category, {"available": True, "count": 0}, []

    out: list[dict] = []
    for entry in raw_items[:limit]:
        normalized = _normalize_journal_item(
            entry,
            default_plugin=plugin_id,
            default_category=category,
            default_source_label=source_label,
            default_tone=tone,
            default_route=default_route,
            now_ts=now_ts,
            tz=tz,
        )
        if normalized is None:
            continue
        if bounds is not None and not (bounds[0] <= normalized["timestamp"] < bounds[1]):
            continue
        out.append(normalized)
    return category, {"available": True, "count": len(out)}, out


async def aggregate_journal_feed(
    plugin,
    *,
    persona: str = "",
    scope: str = "",
    date: str = "today",
    limit: int = 30,
    start_ts: float | None = None,
    end_ts: float | None = None,
) -> dict:
    """Aggregate today's living journal across World and optional ready sibling plugins."""
    try:
        cap = max(1, min(60, int(limit or 30)))
    except (TypeError, ValueError):
        cap = 30
    clean_date = str(date or "today").strip() or "today"
    clean_scope = str(scope or "").strip()
    clean_persona = str(persona or "").strip()
    now = _now_ts(plugin)
    explicit = _coerce_explicit_bounds(start_ts, end_ts)
    if explicit is _INVALID_BOUNDS:
        return {
            "events": [],
            "total": 0,
            "date": clean_date,
            "persona": "",
            "scope": clean_scope,
            "sources": {"world": {"available": True, "count": 0}},
            "server_time": now,
        }
    tz = _plugin_tz(plugin)
    bounds = explicit if explicit is not None else _day_bounds(clean_date, now, tz=tz)

    # Resolve effective group scope and bound persona ONCE before querying World
    # or any sibling plugin so persona switches never leak prior-persona records
    # and unbound groups never broaden to all personas.
    resolved = _resolve_sync_scope(
        plugin, umo=clean_scope, persona=clean_persona, strict=True
    )
    find_owner = getattr(getattr(plugin, "web", None), "_find_companion_owner", None)
    if resolved is None:
        empty_sources: dict[str, dict] = {"world": {"available": True, "count": 0}}
        for plugin_id, cat, _, _, _ in _JOURNAL_SIBLINGS:
            owner, activated = (
                find_owner(plugin_id) if callable(find_owner) else (None, False)
            )
            has_hook = bool(
                activated
                and owner is not None
                and callable(getattr(owner, "get_journal_events", None))
            )
            empty_sources[cat] = {"available": has_hook, "count": 0}
        return {
            "events": [],
            "total": 0,
            "date": clean_date,
            "persona": "",
            "scope": clean_scope,
            "sources": empty_sources,
            "server_time": now,
        }

    effective_scope = resolved["umo"]
    effective_persona = resolved["persona_id"]

    world_events = collect_world_journal_events(
        plugin,
        persona=effective_persona,
        scope=effective_scope,
        date=clean_date,
        limit=cap,
        start_ts=bounds[0] if bounds is not None else None,
        end_ts=bounds[1] if bounds is not None else None,
        _resolved=resolved,
    )
    sources: dict[str, dict] = {
        "world": {"available": True, "count": len(world_events)}
    }
    combined: list[dict] = list(world_events)

    tasks = []
    per_sibling = min(20, cap)
    for plugin_id, cat, label, tone, default_route in _JOURNAL_SIBLINGS:
        owner, activated = (
            find_owner(plugin_id) if callable(find_owner) else (None, False)
        )
        if not activated or owner is None:
            sources[cat] = {"available": False, "count": 0}
            continue
        tasks.append(
            _query_sibling_journal(
                owner,
                plugin_id=plugin_id,
                category=cat,
                source_label=label,
                tone=tone,
                default_route=default_route,
                persona=effective_persona,
                scope=effective_scope,
                date=clean_date,
                limit=per_sibling,
                now_ts=now,
                bounds=bounds,
                tz=tz,
            )
        )

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, Exception) or not isinstance(res, tuple):
                continue
            cat, meta, items = res
            sources[cat] = meta
            combined.extend(items)

    # Deduplicate by (target_plugin, id) and sort descending by timestamp
    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    combined.sort(key=lambda item: item.get("timestamp", 0.0), reverse=True)
    for item in combined:
        key = (item.get("target_plugin", ""), item.get("id", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= cap:
            break

    return {
        "events": deduped,
        "total": len(deduped),
        "date": clean_date,
        "persona": effective_persona,
        "scope": effective_scope,
        "sources": sources,
        "server_time": now,
    }
