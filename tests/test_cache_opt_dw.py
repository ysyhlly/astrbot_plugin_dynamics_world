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
    assert len(truncated["name"]) == 1800
    assert len(truncated["description"]) == 1800
    assert len(truncated["personality"]) == 1800
    assert len(truncated["scenario"]) == 600
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
