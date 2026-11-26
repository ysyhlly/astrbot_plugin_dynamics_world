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

    def test_hourly_top_of_hour_rounding_and_full_day_trim_normalized(self):
        # Simulate hourly tick right after 01:00:00 with fractional seconds (01:00:25.97)
        now = dt.datetime(2026, 11, 27, 1, 0, 25, 970000, tzinfo=CHINA).timestamp()
        midnight = dt.datetime(2026, 11, 27, 0, 0, tzinfo=CHINA).timestamp()
        one_am = dt.datetime(2026, 11, 27, 1, 0, tzinfo=CHINA).timestamp()
        eight_am = dt.datetime(2026, 11, 27, 8, 0, tzinfo=CHINA).timestamp()
        day_end = dt.datetime(2026, 11, 28, 0, 0, tzinfo=CHINA).timestamp()
        scope = {"platform": "test", "umo": "test:GroupMessage:1", "persona_id": "p_test", "instance_id": "p_test"}

        async def rounded_model(req):
            return {
                "schema_version": 1,
                "no_change": False,
                "daily_plan": [
                    # Already-elapsed same-day block (00:00 -> 01:00)
                    {"start": midnight, "end": one_am, "activity": "深夜睡前整理"},
                    # Rounded-down top-of-hour spanning block (01:00:00 < 01:00:25.97 < 08:00:00)
                    {"start": one_am, "end": eight_am, "activity": "安稳熟睡到早晨"},
                    {"start": eight_am, "end": day_end, "activity": "日常写作阅读与休息"},
                ],
                "next_check": now + 3600,
            }

        with tempfile.TemporaryDirectory() as d:
            engine = self._make_engine(Path(d), rounded_model, now)
            tick = asyncio.run(engine.tick())
            self.assertEqual(tick["results"][0]["status"], "advanced")
            admin = asyncio.run(engine.get_narrative_admin(scope))
            self.assertEqual(admin["plan_date"], "2026-11-27")
            self.assertEqual(len(admin["daily_plan"]), 2)
            self.assertEqual(admin["daily_plan"][0]["start"], now)
            self.assertEqual(admin["daily_plan"][0]["end"], eight_am)
            self.assertEqual(admin["plan_status"]["status"], "ready")

    def test_hourly_retries_once_on_wrong_day_daily_plan(self):
        now = dt.datetime(2026, 11, 27, 1, 0, 25, 500000, tzinfo=CHINA).timestamp()
        yesterday_start = dt.datetime(2026, 11, 26, 8, 0, tzinfo=CHINA).timestamp()
        yesterday_end = dt.datetime(2026, 11, 26, 12, 0, tzinfo=CHINA).timestamp()
        day_end = dt.datetime(2026, 11, 28, 0, 0, tzinfo=CHINA).timestamp()
        scope = {"platform": "test", "umo": "test:GroupMessage:1", "persona_id": "p_test", "instance_id": "p_test"}
        seen = []

        async def retry_model(req):
            seen.append(req)
            if len(seen) == 1:
                return {
                    "schema_version": 1,
                    "no_change": False,
                    "daily_plan": [
                        {"start": yesterday_start, "end": yesterday_end, "activity": "昨日旧安排"},
                    ],
                }
            bounds = req["previous_validation_failure"]["plan_window_int"]
            return {
                "schema_version": 1,
                "no_change": False,
                "daily_plan": [
                    {"start": bounds["min_start"], "end": bounds["max_end"], "activity": "今日剩余安排"},
                ],
            }

        with tempfile.TemporaryDirectory() as d:
            engine = self._make_engine(Path(d), retry_model, now)
            tick = asyncio.run(engine.tick())
            self.assertEqual(len(seen), 2)
            self.assertEqual(tick["results"][0]["status"], "advanced")
            admin = asyncio.run(engine.get_narrative_admin(scope))
            self.assertEqual(admin["plan_date"], "2026-11-27")
            self.assertEqual(admin["daily_plan"][0]["end"], day_end)

    def test_regenerate_daily_plan_survives_concurrent_resident_causal_revision(self):
        now = dt.datetime(2026, 11, 27, 1, 59, 11, tzinfo=CHINA).timestamp()
        scope = {"platform": "test", "umo": "test:GroupMessage:1", "persona_id": "p_test", "instance_id": "inst"}
        global_scope = dict(scope, umo="", platform="")
        engine_holder = {}

        async def model_with_resident_tick(req):
            # Simulate independent resident_runner bumping world_life_documents.revision mid-call
            eng = engine_holder["engine"]
            with eng._db() as db:
                rev, doc = eng.causal.load(db, global_scope)
                eng.causal.save(db, global_scope, rev, doc, bump=True)
            w = req["plan_window"]
            return {
                "schema_version": 1,
                "no_change": False,
                "source_ids": [req["events"][0]["event_id"]],
                "daily_plan": [
                    {"start": w["start"] + 49, "end": w["end"], "activity": "熟睡与白日日常"},
                ],
                "next_check": w["start"] + 3600,
            }

        with tempfile.TemporaryDirectory() as d:
            engine = self._make_engine(Path(d), model_with_resident_tick, now)
            engine_holder["engine"] = engine
            res = asyncio.run(engine.regenerate_daily_plan(scope))
            self.assertEqual(res["status"], "regenerated")
            self.assertEqual(res["plan_date"], "2026-11-27")
            self.assertEqual(res["plan_status"]["status"], "ready")


if __name__ == "__main__":
    unittest.main()
