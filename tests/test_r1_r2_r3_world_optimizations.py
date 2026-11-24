"""Focused regression tests for B.1 (P0 event-loop non-blocking) and B.2 (P1 prompt cache & residents)."""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
import threading
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from astrbot_plugin_dynamics_world.life.core.narrative import CHINA, NarrativeEngine
from astrbot_plugin_dynamics_world.life.core.narrative_prompt import (
    NARRATIVE_RULES,
    PLAN_REGENERATION_RULES,
    SCOPED_NARRATIVE_RULES,
    build_narrative_prompt_segments,
)
from astrbot_plugin_dynamics_world.resident_runtime import (
    RESIDENT_CARD_TOTAL_LIMIT,
    RESIDENT_MAX_KNOWLEDGE,
    RULES as RESIDENT_RULES,
    ResidentRunner,
    _truncate_resident_card,
    build_prompt_parts,
)
from astrbot_plugin_dynamics_world.causal_life import CausalLifeService
from astrbot_plugin_dynamics_world.scenes import SceneService
from astrbot_plugin_dynamics_world.spatial import SpatialState
from astrbot_plugin_dynamics_world.visual_profiles import VisualProfiles
from astrbot_plugin_dynamics_world.weather import EnvironmentService


def _make_engine(tmp_path: Path, model_fn=None):
    now = [dt.datetime(2026, 11, 24, 10, 0, tzinfo=CHINA).timestamp()]
    scope = {
        "platform": "qq",
        "umo": "qq:GroupMessage:1001",
        "persona_id": "anan",
        "instance_id": "anan",
    }
    cfg = {
        "mode": "narrative",
        "persona_id": "anan",
        "narrative_sessions": [scope["umo"]],
        "contextual_care_enabled": True,
        "social_chat_enabled": True,
    }

    async def default_model(request):
        return {"schema_version": 1, "no_change": True}

    engine = NarrativeEngine(
        tmp_path / "world_opt.sqlite3",
        cfg,
        model_fn or default_model,
        lambda: now[0],
    )
    engine.spatial = SpatialState(engine)
    engine.scenes = SceneService(engine)
    engine.environment = EnvironmentService(engine)
    engine.causal = CausalLifeService(engine)
    return engine, scope, now


@pytest.mark.asyncio
async def test_b1_weather_schedule_all_async_and_refresh_offload_to_thread(tmp_path, monkeypatch):
    engine, scope, _ = _make_engine(tmp_path)
    try:
        main_tid = threading.get_ident()
        observed_tids = []
        orig_collect = engine.environment._collect_schedule_all_envs

        def spy_collect():
            observed_tids.append(("collect", threading.get_ident()))
            return orig_collect()

        monkeypatch.setattr(engine.environment, "_collect_schedule_all_envs", spy_collect)
        await engine.environment.schedule_all_async()
        assert observed_tids and observed_tids[0][1] != main_tid

        # Verify _fetch_weather error path offloads record_failure off main loop thread
        fail_tids = []
        orig_rec = engine.environment.record_failure

        def spy_rec(key, exc, limit_key="forecast"):
            fail_tids.append(threading.get_ident())
            return orig_rec(key, exc, limit_key)

        async def broken_fetch(*_a, **_kw):
            raise RuntimeError("network down")

        monkeypatch.setattr(engine.environment, "record_failure", spy_rec)
        monkeypatch.setattr(engine.environment, "fetch", broken_fetch)
        await engine.environment._fetch_weather(
            "k-fail",
            {"latitude": 35.0, "longitude": 139.0, "settings": {}},
            provider="open_meteo",
        )
        assert fail_tids and fail_tids[0] != main_tid
    finally:
        await engine.environment.close()
        await engine.close()


@pytest.mark.asyncio
async def test_b1_outreach_uses_lightweight_snapshot_only(tmp_path, monkeypatch):
    engine, scope, now = _make_engine(tmp_path)
    try:
        await engine.ingest_events(
            [
                {
                    "event_id": "msg-out-1",
                    "scope": scope,
                    "type": "message.received",
                    "actor_id": "u1",
                    "occurred_at": now[0] - 60,
                    "received_at": now[0] - 60,
                    "fact_kind": "observation",
                    "text": "最近胃不太舒服，明天去复查",
                    "data": {"directed_to_bot": True},
                }
            ]
        )

        def forbidden_full_snapshot(*_args, **_kwargs):
            raise AssertionError("review_outreach must use _outreach_snapshot, not full _snapshot")

        outreach_calls = []
        orig_outreach_snap = engine._outreach_snapshot

        def spy_outreach_snap(db, sc, ts):
            outreach_calls.append(sc["umo"])
            return orig_outreach_snap(db, sc, ts)

        monkeypatch.setattr(engine, "_snapshot", forbidden_full_snapshot)
        monkeypatch.setattr(engine, "_outreach_snapshot", spy_outreach_snap)
        res = await engine.review_outreach()
        assert isinstance(res, list)
        assert outreach_calls == [scope["umo"]]
    finally:
        await engine.environment.close()
        await engine.close()


def test_b1_visual_profiles_assets_caches_by_manifest_and_detects_tamper(tmp_path, monkeypatch):
    engine, _, _ = _make_engine(tmp_path)
    try:
        profiles = VisualProfiles(engine)
        profiles.asset_root.mkdir(parents=True, exist_ok=True)
        img_bytes = b"\x89PNG\r\n\x1a\nvalid-room-image-data"
        img_path = profiles.asset_root / "room.png"
        img_path.write_bytes(img_bytes)
        digest = hashlib.sha256(img_bytes).hexdigest()
        (profiles.asset_root / "index.json").write_text(
            json.dumps(
                {
                    "room": {
                        "file": "room.png",
                        "role": "layout",
                        "sha256": digest,
                        "label": "书房参考图",
                    }
                }
            ),
            encoding="utf-8",
        )

        # First call populates cache
        first = profiles.assets()
        assert "room" in first

        # Second call hits cache: zero json.loads and zero sha256 hashes!
        loads_calls = 0
        orig_loads = json.loads

        def spy_loads(*a, **kw):
            nonlocal loads_calls
            loads_calls += 1
            return orig_loads(*a, **kw)

        sha_calls = 0
        orig_sha = hashlib.sha256

        def spy_sha(*a, **kw):
            nonlocal sha_calls
            sha_calls += 1
            return orig_sha(*a, **kw)

        monkeypatch.setattr("astrbot_plugin_dynamics_world.visual_profiles.json.loads", spy_loads)
        monkeypatch.setattr("astrbot_plugin_dynamics_world.visual_profiles.hashlib.sha256", spy_sha)

        second = profiles.assets()
        assert second == first
        assert loads_calls == 0
        assert sha_calls == 0

        # Tampering the file invalidates cache immediately and fails closed
        img_path.write_bytes(b"tampered-bytes")
        third = profiles.assets()
        assert third == {}
        assert sha_calls == 1
    finally:
        asyncio.run(engine.environment.close())
        asyncio.run(engine.close())


@pytest.mark.asyncio
async def test_b1_narrative_admin_and_intents_run_off_event_loop(tmp_path, monkeypatch):
    engine, scope, now = _make_engine(tmp_path)
    try:
        main_tid = threading.get_ident()
        db_tids = []
        orig_db = engine._db

        def spy_db(*args, **kwargs):
            db_tids.append(threading.get_ident())
            return orig_db(*args, **kwargs)

        monkeypatch.setattr(engine, "_db", spy_db)
        ro_flags = []
        orig_snap = engine._snapshot

        def spy_snap(db, sc, ts, *, read_only=False):
            ro_flags.append(read_only)
            return orig_snap(db, sc, ts, read_only=read_only)

        monkeypatch.setattr(engine, "_snapshot", spy_snap)

        assert await engine.list_due_intents(now[0]) == []
        assert (await engine.get_intent("missing"))["available"] is False
        await engine.set_paused(True, scope)
        await engine.set_paused(False, scope)
        admin = await engine.get_narrative_admin(scope)
        assert admin["managed"] is True
        assert ro_flags and ro_flags[-1] is True
        assert db_tids and all(tid != main_tid for tid in db_tids)
    finally:
        await engine.environment.close()
        await engine.close()


@pytest.mark.asyncio
async def test_b1_resident_tick_offloads_db_to_thread(tmp_path, monkeypatch):
    engine, scope, now = _make_engine(tmp_path)
    try:
        service = NS(
            narrative=engine,
            is_active=lambda: True,
            context=None,
            _narrative_model=None,
        )
        runner = ResidentRunner(service)
        main_tid = threading.get_ident()
        db_tids = []
        orig_db = engine._db

        def spy_db(*args, **kwargs):
            db_tids.append(threading.get_ident())
            return orig_db(*args, **kwargs)

        monkeypatch.setattr(engine, "_db", spy_db)
        res = await runner.tick()
        assert res["status"] in {"no_ready_resident", "not_due", "paused"}
        assert db_tids and all(tid != main_tid for tid in db_tids)
    finally:
        await engine.environment.close()
        await engine.close()


def test_b2_system_prompt_inverts_order_and_sinks_group_and_volatile_fields():
    character = {
        "persona_id": "anan",
        "core_prompt": "安静细致的海边小镇主角。" * 40,
        "group_rules": "本群专属群聊节奏边界规范",
        "world_items": [
            {"source_id": "wb:global:1", "title": "主世界", "text": "海边小镇全局常驻设定"},
            {"source_id": "wb:group:9", "title": "群专属", "text": "仅某群可见设定", "scope_only": True},
        ],
        "scoped_world_source_ids": ["wb:group:9"],
    }
    base_snapshot = {
        "world_space": {
            "shared": True,
            "active_guest": {"name": "访客甲"},
            "recent_encounters": [{"id": "enc1", "summary": "刚刚遇见"}],
        },
        "horizons_desk": [{"id": "hz1", "title": "今日见闻"}],
        "ecology": {
            "season": {"solar_term": "小雪"},
            "pantry": {"tea": 3},
            "flowerbed": {"stage": "sprout"},
            "veg_patch": {"stage": "growing"},
            "recent_meals": [{"name": "番茄蛋汤"}],
            "vitality": {"body": 0.8},
        },
        "environment": {
            "mode": "real",
            "source": "open_meteo",
            "fact_kind": "observation",
            "status": "ready",
            "location": "东京",
            "timezone": "Asia/Tokyo",
            "available": True,
            "stale": False,
            "sunrise": "06:20",
            "sunset": "16:30",
            "current": {"temperature": 14.0},
            "forecast": [{"hour": 0, "temp": 14}],
        },
        "scene": {
            "available": True,
            "fact_kind": "fiction",
            "map_revision": 2,
            "rooms": [{"id": "study", "name": "书房"}],
            "places": {"home": {"kind": "home"}},
            "room_designs": [{"room_id": "study", "furniture": [{"id": "desk_x"}]}],
            "removed_items": [{"id": "old_cup"}],
            "archived_items": [{"id": "archive_1"}],
            "projects": [{"id": "proj_x", "title": "随笔"}],
        },
        "spatial": {
            "available": True,
            "places": [{"id": "cafe", "name": "咖啡馆"}, {"id": "home", "name": "住所"}],
        },
        "causal_life": {
            "viewer": "actor",
            "actor_id": "self",
            "baseline": "已确认活动",
            "paused": False,
            "growth": {"reading": {"sessions": 7}},
            "agenda": [{"id": "a1", "activity": "看书", "status": "planned"}],
            "events": [],
        },
        "commitments": [{"commitment_id": "c1", "description": "明天整理笔记"}],
        "goals": [{"id": "g1", "text": "写完一章"}],
        "interests": [{"id": "i1", "topic": "摄影"}],
        "relationships": [{"id": "r1", "name": "好友"}],
        "humanlike": {
            "preferences": [
                {"id": "p_personal", "text": "爱喝热茶", "origin": "personal"},
                {"id": "p_conv", "text": "群内偏好", "origin": "conversation"},
            ]
        },
    }

    global_req = {
        "scope": {"platform": "", "umo": "", "persona_id": "anan", "instance_id": "anan"},
        "now": 1_800_000_000.0,
        "timezone": "Asia/Shanghai",
        "local_date": "2026-11-24",
        "snapshot": base_snapshot,
        "events": [{"event_id": "e1", "type": "life.tick", "text": ""}],
    }
    scoped_req = {
        **global_req,
        "scope": {"platform": "qq", "umo": "qq:GroupMessage:1001", "persona_id": "anan", "instance_id": "anan"},
        "events": [{"event_id": "e2", "type": "chat.message", "text": "晚上好"}],
    }
    outreach_req = {
        **scoped_req,
        "outreach_only": True,
        "snapshot": {"availability": "available", "humanlike": base_snapshot["humanlike"]},
    }
    regen_req = {
        **global_req,
        "manual_plan_regeneration": True,
        "needs_daily_plan": True,
    }

    g_sys, g_ctx, g_dyn = build_narrative_prompt_segments(global_req, character)
    s_sys, s_ctx, s_dyn = build_narrative_prompt_segments(scoped_req, character)
    o_sys, _o_ctx, o_dyn = build_narrative_prompt_segments(outreach_req, character)
    r_sys, _r_ctx, _r_dyn = build_narrative_prompt_segments(regen_req, character)

    # 1) Universal 角色资料 + 静态世界基础信息 come FIRST, mode-specific rules AFTER
    for prompt_text in (g_sys, s_sys, o_sys, r_sys):
        assert prompt_text.startswith("角色资料：\n")
        assert "本群专属群聊节奏边界规范" not in prompt_text
        assert "仅某群可见设定" not in prompt_text
    assert g_sys.index("角色资料：") < g_sys.index("静态世界基础信息：") < g_sys.index(NARRATIVE_RULES)
    assert s_sys.index("角色资料：") < s_sys.index("静态世界基础信息：") < s_sys.index(SCOPED_NARRATIVE_RULES)
    assert r_sys.index("角色资料：") < r_sys.index("静态世界基础信息：") < r_sys.index(PLAN_REGENERATION_RULES)

    # Exact byte-identical leading prefix across ALL 4 modes (角色资料) and across global/scoped/regen (+ 静态世界基础信息)
    char_prefix_end = o_sys.index("\n你只评估")
    assert g_sys[:char_prefix_end] == s_sys[:char_prefix_end] == o_sys[:char_prefix_end] == r_sys[:char_prefix_end]
    world_prefix_end = g_sys.index("\n" + NARRATIVE_RULES)
    assert g_sys[:world_prefix_end] == s_sys[:world_prefix_end] == r_sys[:world_prefix_end]

    # Per-group group_rules and scoped_world_items live in dynamic prompt, NEVER system_prompt or contexts[0]
    assert "本群专属群聊节奏边界规范" in s_dyn and "本群专属群聊节奏边界规范" not in s_ctx
    assert "仅某群可见设定" in s_dyn and "仅某群可见设定" not in s_ctx
    assert "本群专属群聊节奏边界规范" in o_dyn

    # 2) Volatile & scope-conditional fields sunk out of shared_tier1 (contexts[0]) into dynamic_projected
    for volatile_token in (
        "访客甲",
        "刚刚遇见",
        "今日见闻",
        '"pantry"',
        '"flower_stage"',
        '"veg_stage"',
        '"recent_meals"',
        '"status":"ready"',
        '"stale":false',
        "desk_x",
        "old_cup",
        "proj_x",
        '"growth"',
        "明天整理笔记",
        "写完一章",
        "摄影",
        "好友",
        "群内偏好",
    ):
        assert volatile_token not in g_ctx, f"{volatile_token} leaked into global contexts[0]"
        assert volatile_token not in s_ctx, f"{volatile_token} leaked into scoped contexts[0]"
    assert "访客甲" in g_dyn and "今日见闻" in g_dyn and "desk_x" in g_dyn and '"growth"' in g_dyn
    assert "爱喝热茶" in g_ctx and "爱喝热茶" in s_ctx
    # Global tick and scoped advance share identical tier-1 snapshot body (ignoring prefix hash in anchor)
    assert g_ctx.split("\n共享世界基础状态：\n", 1)[1] == s_ctx.split("\n共享世界基础状态：\n", 1)[1]


def test_b2_resident_knowledge_cap_card_dedup_and_shared_prefix(tmp_path):
    # 1) Card trimming & deduplication <= RESIDENT_CARD_TOTAL_LIMIT (2800)
    repeated_line = "这是一段在多个字段中重复出现的人设约束说明。"
    card = {
        "name": "艾玛",
        "description": "\n".join([repeated_line, "喜欢海边散步。"] + [f"细节{i}" * 20 for i in range(40)]),
        "personality": "\n".join([repeated_line, "温和细致。"] + [f"性格{i}" * 20 for i in range(40)]),
        "scenario": "\n".join([repeated_line, "海边小镇。"]),
        "system_prompt": repeated_line,
        "post_history_instructions": "",
    }
    trimmed = _truncate_resident_card(card)
    assert sum(len(v) for v in trimmed.values()) <= RESIDENT_CARD_TOTAL_LIMIT <= 3000
    assert repeated_line in trimmed["description"]
    assert repeated_line not in trimmed["personality"]
    assert repeated_line not in trimmed["scenario"]
    assert repeated_line not in trimmed["system_prompt"]

    # 2) Two different residents share common static RULES + 世界基础信息 prefix before private_character
    places = [{"id": "cafe", "name": "咖啡馆"}, {"id": "home", "name": "住所"}]
    r_a, _ = build_prompt_parts(
        {
            "now": 1_800_000_000.0,
            "resident_context": {
                "acting_actor_id": "emma",
                "observation_rule": "公共入口可见",
                "places": places,
                "private_character": {"name": "艾玛", "personality": "温柔", "system_prompt": ""},
            },
        }
    )
    r_b, _ = build_prompt_parts(
        {
            "now": 1_800_000_000.0,
            "resident_context": {
                "acting_actor_id": "hiro",
                "observation_rule": "公共入口可见",
                "places": list(reversed(places)),
                "private_character": {"name": "希罗", "personality": "冷静", "system_prompt": ""},
            },
        }
    )
    assert r_a.startswith(RESIDENT_RULES)
    priv_idx = r_a.index("\nprivate_character：\n")
    assert r_a[:priv_idx] == r_b[:priv_idx]
    assert '"system_prompt"' not in r_a  # empty fields omitted in serialized private_character

    # 3) ResidentRunner.context() caps own_knowledge to latest RESIDENT_MAX_KNOWLEDGE (25) entries
    engine, scope, now = _make_engine(tmp_path)
    try:
        service = NS(narrative=engine, is_active=lambda: True, context=None, _narrative_model=None)
        runner = ResidentRunner(service)
        global_scope = engine._global_scope()
        engine.causal.card_resolver = lambda cid: {"name": "艾玛", "description": "居民描述", "personality": "温和"}
        with engine._db() as db:
            rev, doc = engine.causal.load(db, global_scope)
            doc["residents"]["emma"] = {
                "id": "emma",
                "name": "艾玛",
                "card_id": "card_emma",
                "enabled": True,
                "revision": 1,
                "place_id": "home",
                "knowledge": [{"id": f"k{i}", "text": f"见闻 {i}"} for i in range(45)],
            }
            engine.causal.save(db, global_scope, rev, doc)
            public, _ctx = runner.context(db, global_scope, "emma", now[0])
        assert len(public["own_knowledge"]) == RESIDENT_MAX_KNOWLEDGE == 25
        assert public["own_knowledge"][0]["id"] == "k20"
        assert public["own_knowledge"][-1]["id"] == "k44"
    finally:
        asyncio.run(engine.environment.close())
        asyncio.run(engine.close())
