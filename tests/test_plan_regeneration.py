"""Tests for failed daily schedule detection and manual regeneration in NarrativeEngine."""
from __future__ import annotations

import asyncio
import datetime as dt
import tempfile
import unittest
from pathlib import Path

from astrbot_plugin_dynamics_world.causal_life import CausalLifeService
from astrbot_plugin_dynamics_world.life.core.narrative import CHINA, NarrativeEngine
from astrbot_plugin_dynamics_world.spatial import SpatialState


class PlanRegenerationTest(unittest.TestCase):
    def _make_engine(self, tmp: Path, model_fn, clock_ts: float):
        cfg = {
            "mode": "narrative",
            "persona_id": "p_test",
            "narrative_sessions": ["test:GroupMessage:1"],
            "narrative_timeout_seconds": 10,
            "hourly_budget": 1,
        }
        engine = NarrativeEngine(tmp / "narrative.sqlite3", cfg, model_fn, clock=lambda: clock_ts)
        engine.spatial = SpatialState(engine)
        engine.causal = CausalLifeService(engine)
        return engine

    def test_failed_then_regenerated_preserves_history(self):
        # 2026-11-21 09:00 CST
        now = dt.datetime(2026, 11, 21, 9, 0, tzinfo=CHINA).timestamp()
        scope = {"platform": "test", "umo": "test:GroupMessage:1", "persona_id": "p_test", "instance_id": "inst"}
        calls = []

        async def flaky_model(req):
            calls.append(req)
            if len(calls) == 1:
                return "not-a-dict"  # invalid response -> triggers failure
            if len(calls) == 2:
                return {"schema_version": 1, "no_change": True}  # empty daily_plan -> rejected
            w = req["plan_window"]
            return {
                "schema_version": 1,
                "no_change": False,
                "source_ids": [req["events"][0]["event_id"]],
                "state": {
                    "activity": "在房间泡茶看书",
                    "activity_code": "reading",
                    "availability": "available",
                    "valid_until": w["start"] + 3600,
                },
                "daily_plan": [
                    {"start": w["start"] + 60, "end": w["start"] + 3600, "activity": "泡一壶热茶并阅读随身读物"},
                    {"start": w["start"] + 3600, "end": w["start"] + 7200, "activity": "整理书桌并写一段今日随笔"},
                ],
                "world_action": {
                    "operation": "start",
                    "steps": [{"kind": "read", "target_id": "nonexistent_item"}],
                },
                "next_check": w["start"] + 3600,
            }

        with tempfile.TemporaryDirectory() as d:
            engine = self._make_engine(Path(d), flaky_model, now)

            # Initially missing for today
            st0 = engine.get_plan_status(scope)
            self.assertEqual(st0["status"], "missing")
            self.assertFalse(st0["is_today"])

            # Attempt 1 fails with unsupported_narrative_response
            r1 = asyncio.run(engine.regenerate_daily_plan(scope))
            self.assertEqual(r1["status"], "invalid")
            self.assertIn("unsupported_narrative_response", r1["error"])
            self.assertEqual(r1["plan_status"]["status"], "failed")

            # Attempt 2 returns no_change without daily_plan -> rejected honestly
            r2 = asyncio.run(engine.regenerate_daily_plan(scope))
            self.assertEqual(r2["status"], "invalid")
            self.assertIn("empty_daily_plan_on_regeneration", r2["error"])
            self.assertEqual(r2["plan_status"]["status"], "failed")

            # Attempt 3 succeeds and populates daily_plan + causal agenda
            r3 = asyncio.run(engine.regenerate_daily_plan(scope, extra="多安排一点室内阅读"))
            self.assertEqual(r3["status"], "regenerated")
            self.assertEqual(r3["plan_date"], "2026-11-21")
            self.assertEqual(r3["count"], 2)
            self.assertEqual(r3["plan_status"]["status"], "ready")
            self.assertTrue(r3["plan_status"]["is_today"])
            self.assertTrue(calls[2]["manual_plan_regeneration"])
            self.assertEqual(calls[2]["regeneration_hint"], "多安排一点室内阅读")

            admin = asyncio.run(engine.get_narrative_admin(scope))
            self.assertEqual(admin["plan_date"], "2026-11-21")
            self.assertEqual(len(admin["daily_plan"]), 2)
            self.assertEqual(admin["plan_status"]["status"], "ready")

    def test_paused_blocks_regeneration(self):
        now = dt.datetime(2026, 11, 21, 9, 0, tzinfo=CHINA).timestamp()
        scope = {"platform": "test", "umo": "test:GroupMessage:1", "persona_id": "p_test", "instance_id": "inst"}

        async def unused_model(req):
            raise AssertionError("model should not be called when paused")

        with tempfile.TemporaryDirectory() as d:
            engine = self._make_engine(Path(d), unused_model, now)
            asyncio.run(engine.set_paused(True, scope))
            res = asyncio.run(engine.regenerate_daily_plan(scope))
            self.assertEqual(res["status"], "paused")


if __name__ == "__main__":
    unittest.main()
