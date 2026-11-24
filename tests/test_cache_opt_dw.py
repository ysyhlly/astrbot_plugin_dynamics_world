"""Regression tests for DW-1, DW-2, and DW-3 cache & background cost optimizations."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from test_spatial import GLOBAL, SCOPE
from test_world_integration import UMO, make_plugin, seed
from astrbot.core.provider.entities import ProviderRequest
from astrbot_plugin_dynamics_world.defaults import defaults
from astrbot_plugin_dynamics_world.life.core.narrative import NarrativeEngine
from astrbot_plugin_dynamics_world.life.core.narrative_prompt import (
    NARRATIVE_RULES,
    build_narrative_prompt,
    build_narrative_prompt_parts,
    build_narrative_prompt_segments,
)
from astrbot_plugin_dynamics_world.life.core.narrative_schema import narrative_schema
from astrbot_plugin_dynamics_world.life.core.narrative_types import (
    CHINA,
    NarrativeValidationError,
)
from astrbot_plugin_dynamics_world.resident_runtime import (
    DEFAULT_RESIDENT_HOURLY_BUDGET,
    RESIDENT_CARD_FIELD_LIMIT,
    RESIDENT_CARD_TOTAL_LIMIT,
    _truncate_resident_card,
    build_prompt_parts,
    decision_schema,
)
from astrbot_plugin_dynamics_world.world.core.character import CharacterCard
from astrbot_plugin_dynamics_world.world.core.models import WorldBook, WorldEntry
from astrbot_plugin_dynamics_world.world.core.settings import Settings


class _SimpleEvent:
    def __init__(self, umo: str, text: str):
        self.unified_msg_origin = umo
        self.message_str = text

    def get_session_id(self) -> str:
        return self.unified_msg_origin

    def get_extra(self, key: str, default=None):
        return default


def _seed_worldbook_with_two_keywords(plugin):
    plugin.world.store.upsert_card(
        CharacterCard(
            id="card",
            name="安安",
            persona_id="p",
            system_prompt="静态角色核心人设。",
            group_addendum="静态群聊适配规则。",
        )
    )
    plugin.world.store.set_default_card("card")
    book = WorldBook(id="wb", name="测试世界")
    book.entries = [
        WorldEntry(uid="k1", name="咖啡", keys=["咖啡"], content="海边咖啡馆设定。"),
        WorldEntry(uid="k2", name="图书馆", keys=["图书馆"], content="旧图书馆设定。"),
    ]
    plugin.world.store.upsert_book(book)
    plugin.world.store.set_global_active_books(["wb"])


# --------------------------------------------------------------------------- DW-1


def test_dw1_defaults_use_extra_inject_mode():
    schema = json.loads(
        (Path(__file__).parents[1] / "_conf_schema.json").read_text(encoding="utf-8")
    )
    assert schema["inject_mode"]["default"] == "extra"
    assert defaults()["inject_mode"] == "extra"
    assert Settings({}).inject_mode == "extra"


@pytest.mark.asyncio
async def test_dw1_default_extra_mode_keeps_system_prompt_clean_and_marks_temp(
    tmp_path, monkeypatch
):
    plugin, _, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    try:
        _seed_worldbook_with_two_keywords(plugin)
        req1 = ProviderRequest(system_prompt="HOST_SYSTEM")
        await plugin.world.on_llm_request(_SimpleEvent(UMO, "去喝咖啡吧"), req1)
        assert req1.system_prompt == "HOST_SYSTEM"
        assert len(req1.extra_user_content_parts) == 1
        part1 = req1.extra_user_content_parts[0]
        assert getattr(part1, "_no_save", False) is True
        assert "海边咖啡馆设定" in part1.text
        assert "静态角色核心人设" in part1.text

        req2 = ProviderRequest(system_prompt="HOST_SYSTEM")
        await plugin.world.on_llm_request(_SimpleEvent(UMO, "去图书馆看看"), req2)
        assert req2.system_prompt == req1.system_prompt == "HOST_SYSTEM"
        assert "旧图书馆设定" in req2.extra_user_content_parts[0].text
    finally:
        await plugin.terminate()


@pytest.mark.asyncio
async def test_dw1_both_mode_splits_static_card_and_dynamic_worldbook_without_duplication(
    tmp_path, monkeypatch
):
    plugin, _, _ = await make_plugin(
        tmp_path, monkeypatch, runtime_enabled=True, inject_mode="both"
    )
    try:
        _seed_worldbook_with_two_keywords(plugin)

        req1 = ProviderRequest(system_prompt="HOST_SYSTEM")
        await plugin.world.on_llm_request(_SimpleEvent(UMO, "喝咖啡"), req1)

        req2 = ProviderRequest(system_prompt="HOST_SYSTEM")
        await plugin.world.on_llm_request(_SimpleEvent(UMO, "去图书馆"), req2)

        # system_prompt holds ONLY static card_block -> byte-identical across keyword turns.
        assert req1.system_prompt == req2.system_prompt
        assert "静态角色核心人设" in req1.system_prompt
        assert "海边咖啡馆设定" not in req1.system_prompt
        assert "旧图书馆设定" not in req2.system_prompt

        # Dynamic worldbook goes ONLY to temp extra_user_content_parts (no card duplication).
        extra1 = "\n".join(p.text for p in req1.extra_user_content_parts)
        extra2 = "\n".join(p.text for p in req2.extra_user_content_parts)
        assert "海边咖啡馆设定" in extra1 and "静态角色核心人设" not in extra1
        assert "旧图书馆设定" in extra2 and "静态角色核心人设" not in extra2
        assert all(getattr(p, "_no_save", False) is True for p in req1.extra_user_content_parts)
    finally:
        await plugin.terminate()


@pytest.mark.asyncio
async def test_dw1_explicit_system_mode_still_injects_into_system_prompt(
    tmp_path, monkeypatch
):
    plugin, _, _ = await make_plugin(
        tmp_path, monkeypatch, runtime_enabled=True, inject_mode="system"
    )
    try:
        _seed_worldbook_with_two_keywords(plugin)
        req = ProviderRequest(system_prompt="HOST_SYSTEM")
        await plugin.world.on_llm_request(_SimpleEvent(UMO, "喝咖啡"), req)
        assert "静态角色核心人设" in req.system_prompt
        assert "海边咖啡馆设定" in req.system_prompt
        assert req.extra_user_content_parts == []
    finally:
        await plugin.terminate()


# --------------------------------------------------------------------------- DW-2


@pytest.mark.asyncio
async def test_dw2_narrative_model_splits_static_system_prompt_and_volatile_user_prompt(
    tmp_path, monkeypatch
):
    plugin, _, _ = await make_plugin(
        tmp_path, monkeypatch, runtime_enabled=True, narrative_provider_id="bg"
    )
    try:
        seed(plugin)
        captured = []

        async def text_chat(
            prompt=None,
            system_prompt=None,
            session_id=None,
            contexts=None,
            func_tool=None,
            request_max_retries=None,
            response_format=None,
        ):
            captured.append(
                {
                    "prompt": prompt,
                    "system_prompt": system_prompt,
                    "response_format": response_format,
                }
            )
            return NS(completion_text='{"no_change": true}')

        plugin.context.get_provider_by_id = lambda _: NS(
            text_chat=text_chat, provider_config={}
        )

        req1 = {
            "scope": GLOBAL,
            "now": 1_800_000_100.25,
            "day_end": 1_800_057_600.0,
            "snapshot": {"narrated_until": 1_800_000_000.0},
            "events": [{"event_id": "e1", "type": "life.tick", "text": "t1"}],
        }
        req2 = {
            "scope": GLOBAL,
            "now": 1_800_003_700.75,
            "day_end": 1_800_057_600.0,
            "snapshot": {"narrated_until": 1_800_003_600.0},
            "events": [{"event_id": "e2", "type": "life.tick", "text": "t2"}],
        }

        await plugin.life._narrative_model(req1)
        await plugin.life._narrative_model(req2)

        assert len(captured) == 2
        c1, c2 = captured
        assert c1["system_prompt"] == c2["system_prompt"]
        assert NARRATIVE_RULES in c1["system_prompt"]
        assert "Keep the character consistent." in c1["system_prompt"]
        assert "1800000100.25" not in c1["system_prompt"]
        assert "1800000100.25" in c1["prompt"]
        assert "1800003700.75" in c2["prompt"]
        assert NARRATIVE_RULES not in c1["prompt"]
        assert "Keep the character consistent." not in c1["prompt"]
        assert json.dumps(c1["response_format"], sort_keys=True) == json.dumps(
            c2["response_format"], sort_keys=True
        )
    finally:
        await plugin.terminate()


@pytest.mark.asyncio
async def test_dw2_narrative_model_resident_split_and_legacy_provider_fallback(
    tmp_path, monkeypatch
):
    plugin, _, _ = await make_plugin(
        tmp_path, monkeypatch, runtime_enabled=True
    )
    try:
        seed(plugin)
        # 1) Provider supporting system_prompt receives split resident_isolated prompt.
        seen_split = {}

        async def split_chat(prompt=None, system_prompt=None, **kwargs):
            seen_split["prompt"] = prompt
            seen_split["system_prompt"] = system_prompt
            seen_split["schema"] = kwargs.get("response_format")
            return NS(
                completion_text='{"actor_id":"r1","operation":"wait","reason":"安静待着","source_ids":["observation:r1"]}'
            )

        plugin.life.generator._get_provider = lambda: asyncio.sleep(
            0, result=NS(text_chat=split_chat, provider_config={})
        )
        resident_req = {
            "scope": GLOBAL,
            "now": 1_800_000_500.5,
            "local_datetime": "2027-01-15T12:00:00+08:00",
            "resident_isolated": True,
            "resident_context": {
                "acting_actor_id": "r1",
                "private_character": {"name": "艾玛", "personality": "温柔认真"},
                "available_source_ids": ["observation:r1", "profile:r1"],
            },
        }
        await plugin.life._narrative_model(resident_req)
        assert "温柔认真" in seen_split["system_prompt"]
        assert "1800000500.5" not in seen_split["system_prompt"]
        assert "1800000500.5" in seen_split["prompt"]
        assert "温柔认真" not in seen_split["prompt"]

        # 2) Provider without system_prompt parameter falls back to concatenated prompt.
        seen_fallback = {}

        async def legacy_chat(prompt=None, session_id=None, contexts=None):
            seen_fallback["prompt"] = prompt
            return NS(completion_text='{"no_change": true}')

        plugin.life.generator._get_provider = lambda: asyncio.sleep(
            0, result=NS(text_chat=legacy_chat, provider_config={})
        )
        await plugin.life._narrative_model(
            {"scope": GLOBAL, "now": 1_800_000_500.0, "events": []}
        )
        assert NARRATIVE_RULES in seen_fallback["prompt"]
        assert "1800000500.0" in seen_fallback["prompt"]
    finally:
        await plugin.terminate()


def test_dw2_build_narrative_prompt_backwards_compatible():
    req = {"scope": GLOBAL, "now": 1234.5, "events": []}
    char = {"persona_id": "p", "core_prompt": "核心设定"}
    sys_p, usr_p = build_narrative_prompt_parts(req, char)
    assert build_narrative_prompt(req, char) == f"{sys_p}\n{usr_p}"
    res_sys, res_usr = build_prompt_parts(
        {
            "now": 1234.5,
            "resident_context": {
                "acting_actor_id": "emma",
                "private_character": {"name": "艾玛"},
            },
        }
    )
    assert "艾玛" in res_sys and "1234.5" not in res_sys
    assert "1234.5" in res_usr and "艾玛" not in res_usr


def test_dw2_schemas_are_byte_identical_across_timestamps_and_dynamic_ids():
    global_req_1 = {
        "scope": GLOBAL,
        "now": 1_800_000_001.123,
        "day_end": 1_800_057_600.0,
        "needs_daily_plan": True,
        "weather_reassessment": False,
        "causal_revision": 1,
        "events": [{"event_id": "evt-alpha"}],
        "snapshot": {
            "narrated_until": 1_799_999_000.0,
            "scene": {
                "available": True,
                "rooms": [{"id": "room_a"}],
                "items": [{"id": "item_1"}],
                "room_designs": [{"furniture": [{"id": "desk_1"}]}],
                "projects": [{"id": "proj_1"}],
            },
            "spatial": {"available": True, "places": [{"id": "place_a"}]},
        },
        "background_world": {"actors": [{"id": "resident_alpha"}]},
    }
    global_req_2 = {
        "scope": GLOBAL,
        "now": 1_800_123_456.789,
        "day_end": 1_800_144_000.0,
        "needs_daily_plan": False,
        "weather_reassessment": True,
        "causal_revision": 99,
        "events": [{"event_id": "evt-beta"}, {"event_id": "evt-gamma"}],
        "snapshot": {
            "narrated_until": 1_800_120_000.0,
            "scene": {
                "available": True,
                "rooms": [{"id": "room_z"}],
                "items": [{"id": "item_99"}],
                "room_designs": [{"furniture": [{"id": "bed_9"}]}],
                "projects": [{"id": "proj_99"}],
            },
            "spatial": {"available": True, "places": [{"id": "place_z"}]},
        },
        "background_world": {"actors": [{"id": "resident_omega"}]},
    }
    s1 = json.dumps(narrative_schema(global_req_1), sort_keys=True)
    s2 = json.dumps(narrative_schema(global_req_2), sort_keys=True)
    assert s1 == s2
    assert "1800000001" not in s1
    assert "room_a" not in s1
    assert "place_a" not in s1
    assert "resident_alpha" not in s1

    # Scoped narrative schema
    scoped_1 = {
        "scope": SCOPE,
        "now": 1_800_000_001.5,
        "events": [{"event_id": "m1"}],
        "snapshot": {"narrated_until": 1_799_999_000.0},
        "care_policy": {"enabled": True},
    }
    scoped_2 = {
        "scope": SCOPE,
        "now": 1_800_099_999.25,
        "events": [],
        "snapshot": {"narrated_until": 1_800_090_000.0},
        "care_policy": {"enabled": True},
    }
    assert json.dumps(narrative_schema(scoped_1), sort_keys=True) == json.dumps(
        narrative_schema(scoped_2), sort_keys=True
    )

    # Outreach schema
    outreach_1 = {
        "scope": SCOPE,
        "now": 1_800_000_001.5,
        "outreach_only": True,
        "events": [{"event_id": "m1"}],
        "care_policy": {"enabled": True},
        "social_policy": {"enabled": True},
    }
    outreach_2 = {
        "scope": SCOPE,
        "now": 1_800_555_555.75,
        "outreach_only": True,
        "events": [{"event_id": "m2"}, {"event_id": "m3"}],
        "care_policy": {"enabled": True},
        "social_policy": {"enabled": True},
    }
    assert json.dumps(narrative_schema(outreach_1), sort_keys=True) == json.dumps(
        narrative_schema(outreach_2), sort_keys=True
    )

    # Resident isolated schema
    res_1 = {
        "scope": GLOBAL,
        "now": 1_800_000_001.5,
        "resident_isolated": True,
        "resident_context": {
            "acting_actor_id": "emma",
            "available_source_ids": ["observation:emma", "ev1"],
        },
    }
    res_2 = {
        "scope": GLOBAL,
        "now": 1_800_999_999.9,
        "resident_isolated": True,
        "resident_context": {
            "acting_actor_id": "hiro",
            "available_source_ids": ["observation:hiro", "ev99"],
        },
    }
    rs1 = json.dumps(narrative_schema(res_1), sort_keys=True)
    rs2 = json.dumps(narrative_schema(res_2), sort_keys=True)
    assert rs1 == rs2
    assert rs1 == json.dumps(decision_schema(), sort_keys=True)
    assert "emma" not in rs1 and "ev1" not in rs1 and "1800000001" not in rs1


def test_dw2_python_post_parse_still_strictly_rejects_invalid_timestamps_and_ids(rig):
    engine, now, _ = rig
    t = now[0]
    day = dt.datetime.fromtimestamp(t, CHINA).date()
    day_end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(), CHINA).timestamp()

    with engine._db() as db:
        snap = engine._snapshot(db, GLOBAL, t)
    ev = engine._event(
        {
            "event_id": "tick-1",
            "type": "life.tick",
            "occurred_at": t,
            "received_at": t,
            "scope": GLOBAL,
            "text": "tick",
            "fact_kind": "fiction",
        },
        t,
    )
    req = {
        "scope": GLOBAL,
        "now": t,
        "day_end": day_end,
        "snapshot": snap,
        "events": [ev],
        "needs_daily_plan": True,
    }

    # valid_until <= now rejected
    with pytest.raises(NarrativeValidationError):
        engine._validate_change({"state": {"valid_until": t}}, req)
    with pytest.raises(NarrativeValidationError):
        engine._validate_change({"state": {"valid_until": t + 86401}}, req)

    # next_check <= now rejected
    with pytest.raises(NarrativeValidationError):
        engine._validate_change({"next_check": t - 1}, req)

    # diary occurred_at in future rejected
    with pytest.raises(NarrativeValidationError):
        engine._validate_change(
            {
                "diary": [
                    {
                        "text": "未来日记",
                        "occurred_at": t + 10,
                        "fact_kind": "fiction",
                        "source_ids": ["tick-1"],
                    }
                ]
            },
            req,
        )

    # unknown source_id rejected
    with pytest.raises(NarrativeValidationError):
        engine._validate_change(
            {
                "diary": [
                    {
                        "text": "伪造来源",
                        "occurred_at": t,
                        "fact_kind": "fiction",
                        "source_ids": ["forged-event-id"],
                    }
                ]
            },
            req,
        )

    # daily_plan past start rejected
    with pytest.raises(NarrativeValidationError):
        engine._validate_change(
            {"daily_plan": [{"start": t - 10, "end": t + 60, "activity": "过去安排"}]},
            req,
        )

    # movement with unknown place_id or past not_before rejected
    with pytest.raises(ValueError, match="目的地不存在"):
        engine._validate_change(
            {"movement": {"kind": "locate", "target_id": "nonexistent_place"}}, req
        )
    with pytest.raises(ValueError, match="未来一天以内"):
        engine._validate_change(
            {"movement": {"kind": "locate", "target_id": "a", "not_before": t - 5}}, req
        )

    # Scoped: mood expires_at <= now & care_waits not_before < now + 1800 rejected
    scoped_ev = engine._event(
        {
            "event_id": "chat-1",
            "type": "message.received",
            "occurred_at": t,
            "received_at": t,
            "scope": SCOPE,
            "actor_id": "u1",
            "text": "我今天头疼先睡会",
            "data": {"directed_to_bot": True},
        },
        t,
    )
    with engine._db() as db:
        scoped_snap = engine._snapshot(db, SCOPE, t)
    scoped_req = {
        "scope": SCOPE,
        "now": t,
        "snapshot": scoped_snap,
        "events": [scoped_ev],
        "needs_daily_plan": False,
    }
    with pytest.raises(NarrativeValidationError):
        engine._validate_change(
            {
                "humanlike": {
                    "moods": [
                        {
                            "subject_id": "u1",
                            "text": "担心",
                            "expires_at": t,
                            "source_ids": ["chat-1"],
                        }
                    ]
                }
            },
            scoped_req,
        )
    with pytest.raises(NarrativeValidationError):
        engine._validate_change(
            {
                "care_waits": [
                    {
                        "subject_id": "u1",
                        "reason_kind": "health_concern",
                        "reason": "关心头痛",
                        "waiting_for": "报平安",
                        "evidence_quote": "我今天头疼先睡会",
                        "source_ids": ["chat-1"],
                        "not_before": t + 600,
                        "expires_at": t + 7200,
                    }
                ]
            },
            scoped_req,
        )


# --------------------------------------------------------------------------- DW-3


def test_dw3_default_resident_hourly_budget_is_6():
    schema = json.loads(
        (Path(__file__).parents[1] / "_conf_schema.json").read_text(encoding="utf-8")
    )
    assert schema["resident_hourly_budget"]["default"] == 6
    assert defaults()["resident_hourly_budget"] == 6
    assert DEFAULT_RESIDENT_HOURLY_BUDGET == 6


def test_dw3_resident_card_truncation_caps():
    huge_card = {
        "name": "N" * 10_000,
        "description": "D" * 10_000,
        "personality": "P" * 10_000,
        "scenario": "S" * 10_000,
        "system_prompt": "Y" * 10_000,
        "post_history_instructions": "H" * 10_000,
    }
    truncated = _truncate_resident_card(huge_card)
    assert all(len(v) <= RESIDENT_CARD_FIELD_LIMIT for v in truncated.values())
    assert sum(len(v) for v in truncated.values()) <= RESIDENT_CARD_TOTAL_LIMIT
    assert len(truncated["name"]) == RESIDENT_CARD_FIELD_LIMIT == 1200
    assert len(truncated["description"]) == RESIDENT_CARD_FIELD_LIMIT == 1200
    assert len(truncated["personality"]) == RESIDENT_CARD_TOTAL_LIMIT - 2 * RESIDENT_CARD_FIELD_LIMIT == 400
    assert truncated["scenario"] == ""
    assert truncated["system_prompt"] == ""
    assert truncated["post_history_instructions"] == ""


@pytest.mark.asyncio
async def test_dw3_narrative_quiet_period_backoff_and_activity_reset(tmp_path):
    now = [1_800_000_000.0]

    async def model(request):
        return {"no_change": True}

    engine = NarrativeEngine(
        tmp_path / "life.sqlite3",
        {"mode": "narrative", "persona_id": "p", "narrative_sessions": [UMO]},
        model,
        lambda: now[0],
    )
    try:
        # Initial tick runs background scan -> quiet_ticks["narrative"] becomes 1 -> 15m interval.
        await engine.tick()
        assert engine.effective_tick_interval(300, kind="narrative", now=now[0]) == 900.0

        # 5m later: still quiet, background timestamp must NOT advance (900s required).
        now[0] += 300
        await engine.tick()
        with engine._db(notify=False) as db:
            last_bg = db.execute(
                "SELECT last FROM maintenance WHERE kind='background'"
            ).fetchone()[0]
        assert last_bg == 1_800_000_000.0

        # At +15m total (900s): background scan fires and steps up to 30m (1800s).
        now[0] += 600
        await engine.tick()
        assert engine.effective_tick_interval(300, kind="narrative", now=now[0]) == 1800.0
        with engine._db(notify=False) as db:
            last_bg = db.execute(
                "SELECT last FROM maintenance WHERE kind='background'"
            ).fetchone()[0]
        assert last_bg == 1_800_000_900.0

        # 15m later (900s < 1800s): still backed off.
        now[0] += 900
        await engine.tick()
        with engine._db(notify=False) as db:
            last_bg = db.execute(
                "SELECT last FROM maintenance WHERE kind='background'"
            ).fetchone()[0]
        assert last_bg == 1_800_000_900.0

        # New chat message arrives -> immediately resets backoff to 5m (300s)!
        await engine.ingest_events(
            [
                {
                    "event_id": "chat-wake",
                    "type": "chat.message",
                    "occurred_at": now[0],
                    "received_at": now[0],
                    "scope": SCOPE,
                    "actor_id": "u1",
                    "text": "回来啦",
                }
            ]
        )
        assert engine.effective_tick_interval(300, kind="narrative", now=now[0]) == 300.0
        await engine.tick()
        with engine._db(notify=False) as db:
            status = db.execute(
                "SELECT status FROM events WHERE event_id='chat-wake'"
            ).fetchone()[0]
        assert status == "processed"
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_dw3_resident_backoff_budget_and_post_parse_validation(
    tmp_path, monkeypatch
):
    plugin, _, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    try:
        for task in (
            plugin.life._resident_task,
            plugin.life._narrative_task,
            plugin.life._outreach_task,
        ):
            task.cancel()
        await asyncio.gather(
            plugin.life._resident_task,
            plugin.life._narrative_task,
            plugin.life._outreach_task,
            return_exceptions=True,
        )
        seed(plugin)
        # Seed a resident card with oversized fields & register resident on map.
        plugin.world.store.upsert_card(
            CharacterCard(
                id="res_card",
                name="艾玛",
                persona_id="p_emma",
                description="A" * 5000,
                personality="B" * 5000,
                scenario="C" * 5000,
                system_prompt="D" * 5000,
            )
        )
        engine = plugin.life.narrative
        clock_now = [1_800_000_000.0]
        monkeypatch.setattr(engine, "clock", lambda: clock_now[0])
        engine.spatial.install(
            GLOBAL,
            {
                "schema_version": 1,
                "seed": "s",
                "generator": "test",
                "width": 100,
                "height": 100,
                "image": "data:image/png;base64,",
                "seconds_per_unit": 10,
                "places": [
                    {"id": "home", "name": "住所", "x": 10, "y": 10, "cell": 0},
                    {"id": "park", "name": "公园", "x": 90, "y": 10, "cell": 2},
                ],
                "graph": {"points": [[10, 10], [50, 10], [90, 10]], "edges": [[1], [0, 2], [1]]},
                "roads": [],
            },
        )
        with engine._db() as db:
            rev, doc = engine.causal.load(db, GLOBAL)
            doc["residents"]["emma"] = {
                "id": "emma",
                "name": "艾玛",
                "card_id": "res_card",
                "enabled": True,
                "place_id": "home",
                "busy_until": 0,
                "last_served": 0,
                "revision": 1,
                "knowledge": [],
                "profile": {},
            }
            engine.causal.save(db, GLOBAL, rev, doc)

        # Verify card truncation inside ResidentRunner.context()
        with engine._db(notify=False) as db:
            pub, _ = plugin.life.residents.context(db, GLOBAL, "emma", clock_now[0])
        pc = pub["private_character"]
        assert all(len(v) <= RESIDENT_CARD_FIELD_LIMIT for v in pc.values())
        assert sum(len(v) for v in pc.values()) <= RESIDENT_CARD_TOTAL_LIMIT

        # Stub _narrative_model to return configurable resident responses.
        next_reply = {
            "actor_id": "emma",
            "operation": "wait",
            "reason": "安静整理思绪",
            "source_ids": ["observation:emma"],
        }

        async def fake_model(req):
            return dict(next_reply)

        monkeypatch.setattr(plugin.life, "_narrative_model", fake_model)

        # 1) First quiet tick runs -> backoff steps up to 15m (900s).
        r1 = await plugin.life.residents.tick()
        assert r1["status"] == "no_change"
        clock_now[0] += 300
        assert (await plugin.life.residents.tick())["status"] == "not_due"

        # 2) At +15m (900s): runs -> backoff steps up to 30m (1800s).
        clock_now[0] += 600
        r2 = await plugin.life.residents.tick()
        assert r2["status"] == "no_change"
        clock_now[0] += 900
        assert (await plugin.life.residents.tick())["status"] == "not_due"

        # 3) Chat activity resets backoff immediately to 5m (300s).
        plugin.life.note_activity(clock_now[0])
        assert engine.effective_tick_interval(300, kind="resident", now=clock_now[0]) == 300.0
        r3 = await plugin.life.residents.tick()
        assert r3["status"] == "no_change"

        # 4) Post-parse rejection of wrong actor_id, bad source_id, and past `when`.
        next_reply = {
            "actor_id": "other_actor",
            "operation": "wait",
            "reason": "冒名顶替",
            "source_ids": ["observation:emma"],
        }
        assert (await plugin.life.residents.tick(manual=True))["status"] == "invalid"

        next_reply = {
            "actor_id": "emma",
            "operation": "wait",
            "reason": "伪造来源",
            "source_ids": ["forged:source"],
        }
        assert (await plugin.life.residents.tick(manual=True))["status"] == "invalid"

        next_reply = {
            "actor_id": "emma",
            "operation": "wait",
            "reason": "过去时间戳",
            "source_ids": ["observation:emma"],
            "when": clock_now[0] - 60,
        }
        assert (await plugin.life.residents.tick(manual=True))["status"] == "invalid"

        # 5) Default resident_hourly_budget == 6: we just used 6 calls in this hour -> 7th exhausted!
        next_reply = {
            "actor_id": "emma",
            "operation": "wait",
            "reason": "第7次应超额",
            "source_ids": ["observation:emma"],
        }
        assert (await plugin.life.residents.tick(manual=True))["status"] == "budget_exhausted"

        # Raising config budget allows the 7th call.
        engine.config["resident_hourly_budget"] = 10
        assert (await plugin.life.residents.tick(manual=True))["status"] == "no_change"
    finally:
        await plugin.terminate()


# --------------------------------------------------------------------------- Phase 2 prefix ordering


def _common_prefix_len(a: bytes, b: bytes) -> int:
    limit = min(len(a), len(b))
    idx = 0
    while idx < limit and a[idx] == b[idx]:
        idx += 1
    return idx


def test_phase2_narrative_prompt_slow_to_fast_key_ordering_and_prefix_ratio():
    character = {
        "persona_id": "p",
        "fingerprint": "f" * 64,
        "core_prompt": "角色核心人设。" * 80,
        "group_rules": "群聊边界与节奏规范。" * 40,
        "world_items": [
            {"source_id": "wb:1", "title": "海边小镇", "text": "小镇常驻设定。" * 40}
        ],
    }

    def make_req(now_ts: float, rev: int, trigger: str, event_id: str, extra: dict | None = None):
        req = {
            "now": now_ts,
            "trigger": trigger,
            "local_datetime": f"2026-11-20T02:{int((now_ts % 3600) // 60):02d}:00+08:00",
            "events": [
                {
                    "event_id": event_id,
                    "type": "life.tick",
                    "occurred_at": now_ts,
                    "received_at": now_ts,
                    "text": f"tick {event_id}",
                    "data": {"trigger": trigger},
                }
            ],
            "plan_window": {"start": now_ts, "end": 1_800_057_600.0},
            "schema_version": 1,
            "scope": GLOBAL,
            "timezone": "Asia/Shanghai",
            "local_date": "2026-11-20",
            "day_end": 1_800_057_600.0,
            "needs_daily_plan": False,
            "offline_catchup": False,
            "causal_revision": 7,
            "plan": [
                {"start": 1_800_000_000.0 + i * 3600, "end": 1_800_003_600.0 + i * 3600, "activity": f"日常安排片段 {i}：阅读并记录灵感笔记"}
                for i in range(6)
            ],
            "background_world": {
                "revision": 3,
                "map_revision": 1,
                "map_world_id": "w1",
                "places": [{"id": "home", "name": "住所"}, {"id": "cafe", "name": "海边咖啡馆"}],
                "actors": [
                    {
                        "last_served": now_ts - 600,
                        "place_id": "cafe",
                        "id": "emma",
                        "name": "艾玛",
                        "card_id": "card_emma",
                        "card_fingerprint": "a" * 64,
                        "enabled": True,
                        "profile": {"description": "温柔细心的邻居。" * 30},
                    }
                ],
                "invitations": [],
            },
            "recent_diary": [
                {"occurred": 1_799_996_400.0, "text": "午后整理了书桌。", "fact_kind": "fiction", "source_ids": ["prev"]}
            ],
            "snapshot": {
                "energy": {"energy": 0.72 - (rev * 0.01), "settled_at": now_ts, "basis": "confirmed_activity_interval"},
                "narrated_until": now_ts - 300,
                "revision": rev,
                "scope_revision": rev,
                "state": {"activity_code": "reading", "availability": "available"},
                "activity": "在书房翻看小说",
                "availability": "available",
                "mailbox": {"unopened_count": 0, "parcels": []},
                "spatial": {
                    "progress": 0.0,
                    "place_id": "home",
                    "place_name": "住所",
                    "phase": "located",
                    "available": True,
                    "map_type": "virtual",
                    "map_revision": 1,
                    "places": [{"id": "home", "name": "住所"}, {"id": "cafe", "name": "海边咖啡馆"}],
                },
                "causal_life": {
                    "server_time": now_ts,
                    "last_settled_at": now_ts,
                    "body": {"energy": 0.72 - (rev * 0.01), "settled_at": now_ts},
                    "events": [{"id": "ce1", "kind": "step.completed", "summary": "倒了一杯茶", "occurred_at": 1_799_995_000.0, "source_ids": ["s1"]}],
                    "agenda": [
                        {"id": f"plan_{i}", "activity": f"阅读章节 {i}", "status": "planned", "start": 1_800_000_000.0 + i * 3600, "end": 1_800_003_600.0 + i * 3600}
                        for i in range(6)
                    ],
                    "viewer": "actor",
                    "actor_id": "self",
                    "baseline": "已确认活动与完成回执",
                    "paused": False,
                    "growth": {"reading": {"sessions": 5}},
                    "revision": 7,
                },
                "environment": {
                    "current": {"temperature": 21.5, "label": "晴", "effect": "clear"},
                    "forecast": [{"hour": h, "temp": 20 + (h % 4), "label": "晴"} for h in range(24)],
                    "sunset": "17:42",
                    "sunrise": "06:18",
                    "stale": False,
                    "available": True,
                    "timezone": "Asia/Shanghai",
                    "location": "海边小镇",
                    "status": "ready",
                    "fact_kind": "fiction",
                    "source": "world_sim",
                    "mode": "fiction",
                },
                "ecology": {
                    "vitality": {"body": 0.8},
                    "veg_patch": {"stage": "growing"},
                    "flowerbed": {"stage": "blooming"},
                    "pantry": {"tea": 3, "berries": 4},
                    "season": {"solar_term": "小雪"},
                    "recent_meals": [{"name": "热汤"}],
                },
                "scene": {
                    "action": None,
                    "available_actions": [{"kind": "read", "target_id": "book_1"}],
                    "receipts": [{"event_id": "r1", "kind": "step.completed", "occurred_at": 1_799_994_000.0}],
                    "rooms": [{"id": "study", "name": "书房", "place_id": "home"}],
                    "places": {"home": {"kind": "home", "sheltered": True, "open": True, "opens": 0, "closes": 24}},
                    "room_designs": [{"room_id": "study", "furniture": [{"id": "desk_1", "kind": "desk", "position": "near_window"}]}],
                    "items": [{"id": "book_1", "name": "旧笔记", "kind": "book", "page": 12, "pages": 120, "carried": False}],
                    "projects": [{"id": "proj_1", "title": "海边随笔", "stage": "draft", "outline_excerpt": "大纲内容。" * 40}],
                    "available": True,
                    "fact_kind": "fiction",
                },
                "commitments": [{"commitment_id": "c1", "description": "整理书架", "status": "proposed"}],
                "humanlike": {
                    "moods": [],
                    "goals": [{"id": "g1", "text": "读完第二章", "status": "planned"}],
                    "interests": [{"id": "i1", "topic": "推理小说", "text": "关注结局伏笔", "status": "active"}],
                    "preferences": [{"id": "p1", "text": "喜欢靠窗的安静角落", "status": "active"}],
                },
                "world_space": {"shared": True, "active_guest": None, "recent_encounters": []},
                "scope": GLOBAL,
                "managed": True,
                "schema_version": 1,
            },
        }
        if extra:
            req.update(extra)
        return req

    t0 = 1_800_000_000.0
    req1 = make_req(t0, rev=10, trigger="scheduled_tick", event_id="tick:1")
    req2 = make_req(
        t0 + 300.0,
        rev=11,
        trigger="interval_tick",
        event_id="tick:2",
        extra={"previous_validation_failure": {"reason_code": "validation.test", "attempt": 1}},
    )
    sys1, usr1 = build_narrative_prompt_parts(req1, character)
    sys2, usr2 = build_narrative_prompt_parts(req2, character)

    # Caller inputs must not be mutated.
    assert req1["snapshot"]["spatial"]["places"]
    assert req1["snapshot"]["scene"]["rooms"]

    # System prompt is 100% byte-identical and includes immutable map places (not volatile rooms).
    assert sys1 == sys2
    assert "静态世界基础信息：" in sys1
    assert "海边咖啡馆" in sys1
    assert "书房" not in sys1
    assert "书房" in usr1

    # Verify strict slow-to-fast key order in projected JSON.
    raw_json = usr2.split("有类型与来源的状态和事件：\n", 1)[1]
    parsed = json.loads(raw_json)
    top_keys = list(parsed.keys())
    assert top_keys[0] == "citation_rule"
    assert top_keys.index("scope") < top_keys.index("snapshot")
    assert top_keys.index("snapshot") < top_keys.index("trigger")
    assert top_keys.index("trigger") < top_keys.index("now")
    assert top_keys.index("now") < top_keys.index("events")
    assert top_keys[-1] == "previous_validation_failure"

    snap_keys = list(parsed["snapshot"].keys())
    for slow_k in ("world_space", "commitments", "humanlike", "ecology", "environment", "scene"):
        assert snap_keys.index(slow_k) < snap_keys.index("narrated_until")
        assert snap_keys.index(slow_k) < snap_keys.index("mailbox")
        assert snap_keys.index(slow_k) < snap_keys.index("spatial")
    assert snap_keys.index("narrated_until") < snap_keys.index("causal_life")
    assert snap_keys.index("causal_life") < snap_keys.index("energy")

    env_keys = list(parsed["snapshot"]["environment"].keys())
    assert env_keys.index("forecast") < env_keys.index("current")
    assert env_keys[-1] == "current"

    eco_keys = list(parsed["snapshot"]["ecology"].keys())
    assert eco_keys.index("season") < eco_keys.index("vitality")
    assert eco_keys[-1] == "vitality"

    causal_keys = list(parsed["snapshot"]["causal_life"].keys())
    assert causal_keys.index("agenda") < causal_keys.index("events")
    assert causal_keys.index("events") < causal_keys.index("body")
    assert causal_keys[-1] == "server_time"

    # Common byte-identical prefix across system_prompt + user_prompt MUST be >= 60%.
    full1 = (sys1 + "\n" + usr1).encode("utf-8")
    full2 = (sys2 + "\n" + usr2).encode("utf-8")
    full_ratio = _common_prefix_len(full1, full2) / max(len(full1), len(full2))
    assert full_ratio >= 0.60, f"Expected >=60% shared prefix, got {full_ratio:.1%}"

    # User prompt alone should also preserve a high shared prefix across consecutive 5m ticks.
    u1, u2 = usr1.encode("utf-8"), usr2.encode("utf-8")
    user_ratio = _common_prefix_len(u1, u2) / max(len(u1), len(u2))
    assert user_ratio >= 0.60, f"Expected >=60% shared user_prompt prefix, got {user_ratio:.1%}"


def test_phase2_resident_and_outreach_prompts_maximize_common_prefix():
    base_resident_ctx = {
        "acting_actor_id": "emma",
        "observation_rule": "无指定房间的背景居民位于已登记地点的公共入口；其他房间内人物不可见。",
        "places": [
            {"id": "home", "name": "住所"},
            {"id": "cafe", "name": "海边咖啡馆"},
            {"id": "library", "name": "旧图书馆"},
        ],
        "private_character": {
            "name": "艾玛",
            "description": "喜欢在海边散步和烘焙的温柔居民。" * 30,
            "personality": "细致、温和、守信。" * 20,
            "scenario": "海边小镇日常。" * 10,
            "system_prompt": "",
            "post_history_instructions": "",
        },
        "own_knowledge": [
            {"id": f"k{i}", "text": f"记住了第 {i} 条小镇见闻与约定。"} for i in range(8)
        ],
        "available_source_ids": [f"k{i}" for i in range(8)] + ["observation:emma", "profile:emma"],
        "invitations": [],
        "public_peers": [{"id": "self", "label": "当前世界的主人", "visible": True, "contactable": True, "place_id": "home"}],
        "own_state": {"id": "emma", "place_id": "home", "activity": "休息"},
    }
    r1 = {
        "now": 1_800_000_000.0,
        "local_datetime": "2026-11-20T02:00:00+08:00",
        "resident_context": {
            **base_resident_ctx,
            "own_recent_decisions": [{"at": 1_799_999_700.0, "status": "no_change", "operation": "wait", "reason": "安静看海"}],
        },
    }
    r2 = {
        "now": 1_800_000_300.0,
        "local_datetime": "2026-11-20T02:05:00+08:00",
        "resident_context": {
            **base_resident_ctx,
            "own_recent_decisions": [
                {"at": 1_800_000_000.0, "status": "no_change", "operation": "wait", "reason": "整理笔记"},
                {"at": 1_799_999_700.0, "status": "no_change", "operation": "wait", "reason": "安静看海"},
            ],
        },
    }
    rsys1, rusr1 = build_prompt_parts(r1)
    rsys2, rusr2 = build_prompt_parts(r2)
    assert rsys1 == rsys2
    assert "海边咖啡馆" in rsys1 and "无指定房间的背景居民" in rsys1

    rparsed = json.loads(rusr2.split("当前个人视角：\n", 1)[1])
    assert list(rparsed.keys()) == ["resident_context", "local_datetime", "now"]
    rc_keys = list(rparsed["resident_context"].keys())
    assert rc_keys[0] == "acting_actor_id"
    assert rc_keys[-1] == "own_recent_decisions"

    rf1 = (rsys1 + "\n" + rusr1).encode("utf-8")
    rf2 = (rsys2 + "\n" + rusr2).encode("utf-8")
    assert _common_prefix_len(rf1, rf2) / max(len(rf1), len(rf2)) >= 0.80

    # Outreach prompt also places volatile local_datetime / now / events at the tail.
    o1 = {
        "schema_version": 1,
        "scope": SCOPE,
        "now": 1_800_000_000.0,
        "outreach_only": True,
        "local_datetime": "2026-11-20T02:00:00+08:00",
        "care_policy": {"enabled": True, "min_wait_seconds": 1800},
        "social_policy": {"enabled": True, "topic_candidates": [], "quiet_members": ["u1"], "opportunity_members": []},
        "snapshot": {"humanlike": {"interests": []}, "availability": "available"},
        "recent_intents": [],
        "events": [{"event_id": "m1", "type": "message.received", "text": "晚安"}],
    }
    o2 = {**o1, "now": 1_800_000_300.0, "local_datetime": "2026-11-20T02:05:00+08:00", "events": o1["events"] + [{"event_id": "m2", "type": "message.received", "text": "明天见"}]}
    osys1, ousr1 = build_narrative_prompt_parts(o1, {"persona_id": "p", "core_prompt": "人设"})
    osys2, ousr2 = build_narrative_prompt_parts(o2, {"persona_id": "p", "core_prompt": "人设"})
    assert osys1 == osys2
    oparsed = json.loads(ousr2.split("有类型与来源的状态和事件：\n", 1)[1])
    okeys = list(oparsed.keys())
    assert okeys[0] == "citation_rule"
    assert okeys[-3:] == ["local_datetime", "now", "events"]


# --------------------------------------------------------------------------- Phase 3 overnight/quiet gating & conciseness


@pytest.mark.asyncio
async def test_phase3_outreach_stops_30min_overnight_no_change_loop_and_wakes_on_activity(
    tmp_path,
):
    now = [dt.datetime(2026, 11, 20, 2, 0, tzinfo=CHINA).timestamp()]
    calls = []

    async def model(request):
        calls.append(request)
        return {"no_change": True}

    engine = NarrativeEngine(
        tmp_path / "life.sqlite3",
        {
            "mode": "narrative",
            "persona_id": "p",
            "narrative_sessions": [UMO],
            "contextual_care_sessions": [UMO],
            "social_chat_sessions": [UMO],
        },
        model,
        lambda: now[0],
    )
    try:
        # Seed a chat message from 40 minutes ago (01:20).
        await engine.ingest_events(
            [
                {
                    "event_id": "m-old",
                    "type": "message.received",
                    "occurred_at": now[0] - 2400,
                    "received_at": now[0] - 2400,
                    "scope": SCOPE,
                    "actor_id": "u1",
                    "text": "晚安，明天聊",
                    "data": {"directed_to_bot": True},
                }
            ]
        )

        # 1) Initial outreach review at 02:00 returns no_change.
        res1 = await engine.review_outreach()
        assert res1 == [{"status": "ok", "candidates": 0}]
        assert len(calls) == 1

        # 2) While character is asleep with unchanged evidence, polling every 30m
        #    for 4 hours fires ZERO extra outreach calls (even if fiction diary grows).
        with engine._db() as db:
            row = db.execute("SELECT state FROM lives").fetchone()
            life = json.loads(row[0])
            life.update(
                availability="asleep",
                activity_code="sleeping",
                valid_from=now[0],
                valid_until=now[0] + 5 * 3600,
            )
            db.execute("UPDATE lives SET state=?", (json.dumps(life),))
        for _ in range(8):
            now[0] += 1800
            assert await engine.review_outreach() == []
        assert len(calls) == 1

        # 3) Character wakes up at 06:00 -> availability flips back to awake ->
        #    2nd check on unchanged fingerprint fires -> no_change_streak becomes 2 (TTL=2h),
        #    so polling every 30m at 06:30, 07:00, 07:30 fires ZERO LLM calls!
        with engine._db() as db:
            row = db.execute("SELECT state FROM lives").fetchone()
            life = json.loads(row[0])
            life.update(
                availability="available",
                activity_code="reading",
                valid_from=now[0],
                valid_until=now[0] + 6 * 3600,
            )
            db.execute("UPDATE lives SET state=?", (json.dumps(life),))

        assert len(await engine.review_outreach()) == 1  # 06:00 wake review (streak=2, TTL=2h)
        assert len(calls) == 2

        # Next three 30m polls (06:30, 07:00, 07:30 — all < 2h TTL and before 08:00 flip) -> ZERO calls!
        for _ in range(3):
            now[0] += 1800
            assert await engine.review_outreach() == []
        assert len(calls) == 2

        # 4) A new chat message arrives -> wakes outreach IMMEDIATELY!
        now[0] += 300
        await engine.ingest_events(
            [
                {
                    "event_id": "m-new",
                    "type": "message.received",
                    "occurred_at": now[0],
                    "received_at": now[0],
                    "scope": SCOPE,
                    "actor_id": "u1",
                    "text": "早上好，我有点头疼先休息一下",
                    "data": {"directed_to_bot": True},
                }
            ]
        )
        res_wake = await engine.review_outreach()
        assert res_wake == [{"status": "ok", "candidates": 0}]
        assert len(calls) == 3
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_phase3_sleep_plan_skips_hourly_no_change_loop_and_wakes_on_schedule(
    tmp_path,
):
    t_sleep = dt.datetime(2026, 11, 20, 2, 0, tzinfo=CHINA).timestamp()
    t_wake = dt.datetime(2026, 11, 20, 7, 0, tzinfo=CHINA).timestamp()
    now = [t_sleep]
    calls = []

    async def model(request):
        calls.append(request)
        return {"no_change": True}

    engine = NarrativeEngine(
        tmp_path / "life.sqlite3",
        {"mode": "narrative", "persona_id": "p", "narrative_sessions": [UMO]},
        model,
        lambda: now[0],
    )
    try:
        # Put character asleep with a 02:00-07:00 sleep plan entry, even with short 1h valid_until.
        with engine._db() as db:
            engine._ensure(db, GLOBAL, now[0])
            row = db.execute("SELECT state FROM lives").fetchone()
            life = json.loads(row[0])
            life.update(
                availability="asleep",
                activity_code="sleeping",
                activity="深夜熟睡安歇",
                valid_from=t_sleep,
                valid_until=t_sleep + 3600,
                next_check=t_sleep + 3600,
                narrated_until=t_sleep,
                plan_date="2026-11-20",
                plan=[{"start": t_sleep, "end": t_wake, "activity": "深夜熟睡安歇", "fact_kind": "plan"}],
            )
            db.execute("UPDATE lives SET state=?,revision=1", (json.dumps(life),))
            db.execute(
                "INSERT OR REPLACE INTO maintenance VALUES(?,'hourly',?)",
                ('["p","p"]', t_sleep),
            )

        # Polling at 03:00, 04:00, 05:00, 06:00 while inside sleep plan -> ZERO LLM calls!
        for hour_offset in (1, 2, 3, 4):
            now[0] = t_sleep + hour_offset * 3600
            await engine.tick()
        assert len(calls) == 0

        # At 07:00 scheduled wake-up transition -> fires IMMEDIATELY!
        now[0] = t_wake
        await engine.tick()
        assert len(calls) == 1
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_phase3_deep_quiet_backoff_and_concise_rules(tmp_path, monkeypatch):
    plugin, _, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    try:
        seed(plugin)
        engine = plugin.life.narrative
        t0 = 1_800_000_000.0
        monkeypatch.setattr(engine, "clock", lambda: t0)

        # Escalates 5m -> 15m -> 30m -> 2h -> 4h on consecutive quiet ticks.
        assert engine.effective_tick_interval(300, kind="resident", now=t0) == 300.0
        assert engine.record_background_tick(kind="resident", now=t0) == 900.0
        assert engine.record_background_tick(kind="resident", now=t0) == 1800.0
        assert engine.record_background_tick(kind="resident", now=t0) == 7200.0
        assert engine.record_background_tick(kind="resident", now=t0) == 14400.0

        # Explicit tool query (read_current_world_state) immediately resets quiet backoff to 5m.
        await plugin.life.read_current_world_state(SCOPE, "activity")
        assert engine.effective_tick_interval(300, kind="resident", now=t0) == 300.0

        # Verify conciseness instructions exist in all narrative & resident system prompts.
        assert "输出简洁要求" in NARRATIVE_RULES
        out_sys, _ = build_narrative_prompt_parts(
            {"scope": SCOPE, "now": t0, "outreach_only": True, "events": []}, {}
        )
        assert "输出简洁要求" in out_sys
        bg_sys, _ = build_narrative_prompt_parts(
            {"scope": GLOBAL, "now": t0, "background_only": True, "events": []}, {}
        )
        assert "不做冗长推敲" in bg_sys
        res_sys, _ = build_prompt_parts({"now": t0, "resident_context": {"acting_actor_id": "r1"}})
        assert "输出简洁要求" in res_sys
    finally:
        await plugin.terminate()


# --------------------------------------------------------------------------- Phase 4 static cache-anchor contexts


@pytest.mark.asyncio
async def test_phase4_static_contexts_anchor_for_narrative_and_resident_calls(
    tmp_path, monkeypatch
):
    import hashlib

    plugin, _, _ = await make_plugin(
        tmp_path, monkeypatch, runtime_enabled=True, narrative_provider_id="bg"
    )
    try:
        seed(plugin)
        captured = []

        async def text_chat(
            prompt=None,
            system_prompt=None,
            session_id=None,
            contexts=None,
            func_tool=None,
            request_max_retries=None,
            response_format=None,
        ):
            captured.append(
                {
                    "prompt": prompt,
                    "system_prompt": system_prompt,
                    "session_id": session_id,
                    "contexts": contexts,
                }
            )
            return NS(completion_text='{"no_change": true}')

        plugin.context.get_provider_by_id = lambda _: NS(
            text_chat=text_chat, provider_config={}
        )

        # 1) Two consecutive narrative calls with different volatile now/events.
        await plugin.life._narrative_model(
            {
                "scope": GLOBAL,
                "now": 1_800_000_100.0,
                "events": [{"event_id": "e1", "type": "life.tick", "text": "t1"}],
            }
        )
        await plugin.life._narrative_model(
            {
                "scope": GLOBAL,
                "now": 1_800_000_400.0,
                "events": [{"event_id": "e2", "type": "life.tick", "text": "t2"}],
            }
        )
        assert len(captured) == 2
        c1, c2 = captured
        assert c1["system_prompt"] == c2["system_prompt"]
        assert c1["prompt"] != c2["prompt"]
        expected_hash = hashlib.sha256(c1["system_prompt"].encode("utf-8")).hexdigest()[:12]
        expected_contexts = [
            {
                "role": "user",
                "content": f"[cache_anchor task=dynamics_world.narrative prefix={expected_hash}]",
            },
            {"role": "assistant", "content": "OK"},
        ]
        assert c1["contexts"] == c2["contexts"] == expected_contexts
        assert c1["session_id"] == c2["session_id"] == f"dynamics_world_narrative_{expected_hash}"

        # 2) Two consecutive resident_isolated calls with different volatile now.
        captured.clear()
        base_res = {
            "scope": GLOBAL,
            "resident_isolated": True,
            "resident_context": {
                "acting_actor_id": "emma",
                "private_character": {"name": "艾玛", "personality": "温柔认真"},
                "available_source_ids": ["observation:emma"],
            },
        }
        await plugin.life._narrative_model({**base_res, "now": 1_800_001_000.0})
        await plugin.life._narrative_model({**base_res, "now": 1_800_001_300.0})
        r1, r2 = captured
        assert r1["system_prompt"] == r2["system_prompt"]
        assert r1["prompt"] != r2["prompt"]
        res_hash = hashlib.sha256(r1["system_prompt"].encode("utf-8")).hexdigest()[:12]
        assert res_hash != expected_hash
        assert r1["contexts"] == r2["contexts"] == [
            {
                "role": "user",
                "content": f"[cache_anchor task=dynamics_world.narrative prefix={res_hash}]",
            },
            {"role": "assistant", "content": "OK"},
        ]
        assert r1["session_id"] == r2["session_id"] == f"dynamics_world_narrative_{res_hash}"
    finally:
        await plugin.terminate()


@pytest.mark.asyncio
async def test_phase4_strict_mock_without_contexts_param_works_cleanly(
    tmp_path, monkeypatch
):
    plugin, _, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    try:
        seed(plugin)
        seen = {}

        async def strict_chat(prompt=None, system_prompt=None):
            seen["prompt"] = prompt
            seen["system_prompt"] = system_prompt
            return NS(completion_text='{"no_change": true}')

        plugin.life.generator._get_provider = lambda: asyncio.sleep(
            0, result=NS(text_chat=strict_chat, provider_config={})
        )
        res = await plugin.life._narrative_model(
            {"scope": GLOBAL, "now": 1_800_000_500.0, "events": []}
        )
        assert res == {"no_change": True}
        assert NARRATIVE_RULES in seen["system_prompt"]
        assert "1800000500.0" in seen["prompt"]
    finally:
        await plugin.terminate()


# --------------------------------------------------------------------------- Phase 5 cross-group prefix sharing & ambient throttling


@pytest.mark.asyncio
async def test_phase5_two_different_groups_share_byte_identical_system_prompt_and_contexts0(
    tmp_path, monkeypatch
):
    plugin, _, _ = await make_plugin(
        tmp_path,
        monkeypatch,
        runtime_enabled=True,
        narrative_provider_id="bg",
        narrative_all_groups=True,
    )
    try:
        seed(plugin)
        # Add constant worldbook entry so get_character_context produces per-scope world_items + unique fingerprint!
        book = WorldBook(
            id="shared_wb",
            name="共享世界书",
            entries=[
                WorldEntry(uid="c1", name="背景一", constant=True, content="小镇共有背景设定。" * 40),
                WorldEntry(uid="c2", name="背景二", constant=True, content="角色共同记忆与世界观。" * 40),
            ],
        )
        plugin.world.store.upsert_book(book)
        plugin.world.store.set_global_active_books(["shared_wb"])

        scope_a = {"platform": "qq", "umo": "qq:GroupMessage:111111", "persona_id": "p", "instance_id": "p"}
        scope_b = {"platform": "qq", "umo": "qq:GroupMessage:222222", "persona_id": "p", "instance_id": "p"}

        # Confirm get_character_context itself produces DIFFERENT per-group fingerprints
        # (because world_items embed scope.umo), yet _narrative_model strips scope metadata!
        char_a = await plugin.life._character(scope_a)
        char_b = await plugin.life._character(scope_b)
        assert char_a["fingerprint"] != char_b["fingerprint"]

        captured = []

        async def text_chat(
            prompt=None,
            system_prompt=None,
            session_id=None,
            contexts=None,
            func_tool=None,
            request_max_retries=None,
            response_format=None,
        ):
            captured.append(
                {
                    "prompt": prompt,
                    "system_prompt": system_prompt,
                    "session_id": session_id,
                    "contexts": contexts,
                }
            )
            return NS(completion_text='{"no_change": true}')

        plugin.context.get_provider_by_id = lambda _: NS(
            text_chat=text_chat, provider_config={}
        )

        shared_snapshot_base = {
            "world_space": {"shared": True, "active_guest": None, "recent_encounters": []},
            "ecology": {
                "season": {"solar_term": "小雪"},
                "pantry": {"tea": 4, "berries": 5},
                "flowerbed": {"stage": "blooming"},
                "veg_patch": {"stage": "growing"},
                "recent_meals": [{"name": "热汤"}],
                "vitality": {"body": 0.8},
            },
            "environment": {
                "mode": "fiction",
                "source": "world_sim",
                "fact_kind": "fiction",
                "status": "ready",
                "location": "海边小镇",
                "timezone": "Asia/Shanghai",
                "available": True,
                "stale": False,
                "sunrise": "06:18",
                "sunset": "17:42",
                "forecast": [{"hour": h, "temp": 20 + (h % 3)} for h in range(24)],
                "current": {"temperature": 21.0, "label": "晴"},
            },
            "scene": {
                "available": True,
                "fact_kind": "fiction",
                "map_revision": 1,
                "rooms": [{"id": "study", "name": "书房", "lighting": "warm"}],
                "places": {"home": {"kind": "home", "open": True}},
                "room_designs": [{"room_id": "study", "furniture": [{"id": "desk_1", "kind": "desk"}]}],
                "items": [{"id": "book_1", "name": "笔记", "kind": "book"}],
                "projects": [{"id": "proj_1", "title": "海边随笔", "outline_excerpt": "大纲。" * 40}],
                "action": None,
            },
            "spatial": {
                "available": True,
                "map_type": "virtual",
                "map_revision": 1,
                "place_id": "home",
                "places": [
                    {"id": "cafe", "name": "咖啡馆"},
                    {"id": "home", "name": "住所"},
                ],
            },
            "causal_life": {
                "viewer": "actor",
                "actor_id": "self",
                "baseline": "已确认活动与完成回执",
                "paused": False,
                "growth": {"reading": {"sessions": 5}},
                "agenda": [
                    {"id": f"plan_{i}", "activity": f"阅读章节 {i}", "status": "planned", "start": 1_800_000_000.0 + i * 3600, "end": 1_800_003_600.0 + i * 3600}
                    for i in range(6)
                ],
                "events": [{"id": "ce1", "kind": "step.completed", "summary": "倒茶", "occurred_at": 1_799_999_000.0, "source_ids": ["s1"]}],
                "server_time": 1_800_000_100.0,
            },
            "humanlike": {
                "preferences": [
                    {"id": "p_global", "text": "喜欢靠窗看海", "status": "active", "origin": "personal"},
                ],
                "interests": [
                    {"id": "i_global", "topic": "推理小说", "text": "在读新章节", "status": "active", "origin": "personal"},
                ],
                "goals": [],
                "moods": [],
                "nicknames": [],
                "corrections": [],
            },
        }

        req_a = {
            "scope": scope_a,
            "timezone": "Asia/Shanghai",
            "local_date": "2026-11-21",
            "day_end": 1_800_057_600.0,
            "plan": [{"start": 1_800_000_000.0, "end": 1_800_003_600.0, "activity": "阅读与记录灵感"}],
            "now": 1_800_000_100.0,
            "local_datetime": "2026-11-21T09:00:00+08:00",
            "events": [{"event_id": "evt_a", "type": "message.received", "text": "群A消息"}],
            "snapshot": {
                **shared_snapshot_base,
                "scope": scope_a,
                "commitments": [{"commitment_id": "c_a", "description": "群A约定", "status": "proposed"}],
                "mailbox": {"unopened_count": 1},
                "narrated_until": 1_800_000_000.0,
                "humanlike": {
                    **shared_snapshot_base["humanlike"],
                    "preferences": shared_snapshot_base["humanlike"]["preferences"]
                    + [{"id": "p_a", "text": "群A局部偏好", "status": "active", "origin": "conversation"}],
                },
            },
        }
        req_b = {
            "scope": scope_b,
            "timezone": "Asia/Shanghai",
            "local_date": "2026-11-21",
            "day_end": 1_800_057_600.0,
            "plan": [{"start": 1_800_000_000.0, "end": 1_800_003_600.0, "activity": "阅读与记录灵感"}],
            "now": 1_800_000_400.0,
            "local_datetime": "2026-11-21T09:05:00+08:00",
            "events": [{"event_id": "evt_b", "type": "message.received", "text": "群B消息"}],
            "snapshot": {
                **shared_snapshot_base,
                "scope": scope_b,
                "commitments": [{"commitment_id": "c_b", "description": "群B约定", "status": "proposed"}],
                "mailbox": {"unopened_count": 3},
                "narrated_until": 1_800_000_300.0,
                "humanlike": {
                    **shared_snapshot_base["humanlike"],
                    "preferences": shared_snapshot_base["humanlike"]["preferences"]
                    + [{"id": "p_b", "text": "群B局部偏好", "status": "active", "origin": "conversation"}],
                },
            },
        }

        await plugin.life._narrative_model(req_a)
        await plugin.life._narrative_model(req_b)
        assert len(captured) == 2
        ca, cb = captured

        # 1) 100% byte-identical system_prompt, contexts[0..1], and session_id across DIFFERENT groups!
        assert ca["system_prompt"] == cb["system_prompt"]
        assert ca["contexts"] == cb["contexts"]
        assert ca["session_id"] == cb["session_id"]
        assert "111111" not in ca["system_prompt"] and "222222" not in ca["system_prompt"]
        assert "111111" not in ca["contexts"][0]["content"] and "222222" not in ca["contexts"][0]["content"]
        assert "群A约定" not in ca["contexts"][0]["content"] and "群A局部偏好" not in ca["contexts"][0]["content"]
        assert "书房" not in ca["system_prompt"] and "书房" in ca["contexts"][0]["content"]
        assert "咖啡馆" in ca["system_prompt"]
        assert "群A消息" in ca["prompt"] and "群B消息" in cb["prompt"]
        assert "群A约定" in ca["prompt"] and "群B约定" in cb["prompt"]

        # 2) system_prompt + contexts[0] accounts for >= 60% of total prompt bytes!
        shared_bytes = len((ca["system_prompt"] + ca["contexts"][0]["content"]).encode("utf-8"))
        total_bytes_a = shared_bytes + len(ca["prompt"].encode("utf-8"))
        total_bytes_b = shared_bytes + len(cb["prompt"].encode("utf-8"))
        assert shared_bytes / max(total_bytes_a, total_bytes_b) >= 0.60

        # Also verify build_narrative_prompt_segments directly.
        s1, ctx1, u1 = build_narrative_prompt_segments(req_a, char_a)
        s2, ctx2, u2 = build_narrative_prompt_segments(req_b, char_b)
        assert s1 == s2 and ctx1 == ctx2 and u1 != u2
    finally:
        await plugin.terminate()


@pytest.mark.asyncio
async def test_phase5_low_signal_group_ambient_chatter_skips_llm_while_real_signals_fire(
    tmp_path,
):
    now = [1_800_000_000.0]
    calls = []

    async def model(request):
        calls.append(request)
        return {"no_change": True}

    private_scope = {
        "platform": "qq",
        "umo": "qq:FriendMessage:999",
        "persona_id": "p",
        "instance_id": "p",
    }
    engine = NarrativeEngine(
        tmp_path / "life.sqlite3",
        {
            "mode": "narrative",
            "persona_id": "p",
            "narrative_sessions": [UMO],
            "narrative_private_chat_enabled": True,
            "contextual_care_sessions": [UMO, private_scope["umo"]],
            "social_chat_sessions": [UMO, private_scope["umo"]],
        },
        model,
        lambda: now[0],
    )
    try:
        # 1) Low-signal ambient group chat.message explicitly marked directed_to_bot=False
        #    skips narrative LLM cleanly, marks observed_only, and advances observed_until!
        res = await engine.advance(
            [
                {
                    "event_id": "amb-1",
                    "type": "chat.message",
                    "occurred_at": now[0],
                    "received_at": now[0],
                    "scope": SCOPE,
                    "actor_id": "u1",
                    "text": "哈哈哈今天天气不错",
                    "data": {"directed_to_bot": False, "event_impact": "none"},
                }
            ]
        )
        assert res["status"] == "no_change"
        assert len(calls) == 0
        with engine._db(notify=False) as db:
            st = db.execute("SELECT status FROM events WHERE event_id='amb-1'").fetchone()[0]
        assert st == "observed_only"

        # 2) Low-signal ambient group social_opportunity (dir=False, short filler) skips outreach LLM!
        await engine.ingest_events(
            [
                {
                    "event_id": "amb-soc",
                    "type": "message.received",
                    "occurred_at": now[0],
                    "received_at": now[0],
                    "scope": SCOPE,
                    "actor_id": "u2",
                    "text": "哈哈哈",
                    "data": {"directed_to_bot": False, "social_opportunity": True},
                }
            ]
        )
        assert await engine.review_outreach() == []
        assert len(calls) == 0

        # 3) Bot-directed message with care/commitment signal STILL fires narrative LLM!
        now[0] += 10
        res_dir = await engine.advance(
            [
                {
                    "event_id": "dir-1",
                    "type": "message.received",
                    "occurred_at": now[0],
                    "received_at": now[0],
                    "scope": SCOPE,
                    "actor_id": "u1",
                    "text": "我今天头疼先去睡会儿，晚点跟你报平安",
                    "data": {"directed_to_bot": True},
                }
            ]
        )
        assert res_dir["status"] == "no_change"
        assert len(calls) == 1

        # 4) Bot-directed message in group STILL triggers outreach LLM immediately!
        now[0] += 30
        out_res = await engine.review_outreach()
        assert out_res == [{"status": "ok", "candidates": 0}]
        assert len(calls) == 2

        # 5) Bot-only delivery.success after no_change does NOT trigger another wasted outreach call!
        now[0] += 310
        await engine.ingest_events(
            [
                {
                    "event_id": "bot-reply-1",
                    "type": "delivery.success",
                    "occurred_at": now[0],
                    "received_at": now[0],
                    "scope": SCOPE,
                    "actor_id": "bot",
                    "text": "好好休息哦",
                    "data": {"recipient_user_id": "u1"},
                }
            ]
        )
        assert await engine.review_outreach() == []
        assert len(calls) == 2

        # 6) Private chat message STILL triggers outreach LLM cleanly!
        await engine.ingest_events(
            [
                {
                    "event_id": "priv-1",
                    "type": "message.received",
                    "occurred_at": now[0],
                    "received_at": now[0],
                    "scope": private_scope,
                    "actor_id": "999",
                    "text": "我出门坐高铁啦，到了跟你说",
                    "data": {"directed_to_bot": True},
                }
            ]
        )
        priv_out = await engine.review_outreach()
        assert priv_out == [{"status": "ok", "candidates": 0}]
        assert len(calls) == 3
    finally:
        await engine.close()




