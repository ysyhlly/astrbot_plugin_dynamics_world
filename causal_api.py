"""Authenticated observation and revision-checked life administration."""
from .world.core.web_api import _body, _err, _ok, _query


class CausalAPIMixin:
    async def causal_get(self):
        guard = self.guard("life")
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
                result["cards"] = [{"id": c.id, "name": c.name} for c in self.plugin.world.store.list_cards() if c.persona_id != scope["persona_id"]]
            return _ok(result)
        except (ValueError, TypeError) as exc:
            return _err(str(exc), 409)

    async def causal_post(self):
        async with self.plugin._migration_lock:
            guard = self.guard("life", True)
            if guard is not None:
                return guard
            try:
                body = await _body()
                allowed = {"umo", "action", "expected_revision", "request_id", "changes", "card_id", "place_id", "actor_id", "enabled", "invitation_id"}
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
                card = self.plugin.world.store.get_card(body.get("card_id")) if body.get("action") == "resident" else None
                result = self.plugin.life.narrative.causal.administer(scope, body, card=card.to_dict() if card else None)
                self.bus.notify()
                return _ok(result)
            except (ValueError, TypeError) as exc:
                return _err(str(exc), 409)
