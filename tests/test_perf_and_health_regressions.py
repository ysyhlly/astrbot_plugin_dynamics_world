"""Regression tests for P0/P1/P2 performance, slimming, budget, and health improvements."""

from __future__ import annotations

import asyncio
import datetime as dt
import importlib.util
import json
import threading
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from astrbot_plugin_dynamics_world import series_hooks, series_panels
from astrbot_plugin_dynamics_world.garden_ecology import EcologyService
from astrbot_plugin_dynamics_world.keepsakes import KeepsakeTimelineService
from astrbot_plugin_dynamics_world.life.core.generator import Generator
from astrbot_plugin_dynamics_world.life.core.narrative import (
    CHINA,
    NarrativeEngine,
    _identity,
)
from astrbot_plugin_dynamics_world.life.core.narrative_prompt import (
    NARRATIVE_RULES,
    build_narrative_prompt_segments,
)
from astrbot_plugin_dynamics_world.life.core.state import DataManager
from astrbot_plugin_dynamics_world.mailbox_visitors import MailboxVisitorService
from astrbot_plugin_dynamics_world.scenes import SceneService
from astrbot_plugin_dynamics_world.spatial import SpatialState
from astrbot_plugin_dynamics_world.weather import EnvironmentService
from astrbot_plugin_dynamics_world.world_spaces import WorldSpaceService
from test_world_integration import UMO, make_plugin, seed

ROOT = Path(__file__).parents[1]


def _make_engine(tmp_path: Path, config_extra: dict | None = None, model_fn=None):
    now = [dt.datetime(2026, 11, 21, 10, 0, tzinfo=CHINA).timestamp()]
    scope = {
        "platform": "qq",
        "umo": "qq:GroupMessage:1001",
        "persona_id": "anan",
        "instance_id": "anan",
    }
    cfg = {
        "mode": "narrative",
        "persona_id": "anan",
        "narrative_sessions": [scope["umo"], "qq:GroupMessage:1002"],
        "contextual_care_enabled": True,
        "social_chat_enabled": True,
    }
    if config_extra:
        cfg.update(config_extra)

    calls: list[dict] = []

    async def default_model(req):
        calls.append(req)
        return {"no_change": True}

    engine = NarrativeEngine(
        tmp_path / "narrative.sqlite3",
        cfg,
        model_fn or default_model,
        lambda: now[0],
    )
    return engine, scope, now, calls


@pytest.mark.asyncio
async def test_p0_db_pragmas_and_readonly_snapshot_without_write_lock(tmp_path):
    engine, scope, now, _ = _make_engine(tmp_path)
    engine.spatial = SpatialState(engine)
    engine.environment = EnvironmentService(engine)
    engine.scenes = SceneService(engine)
    engine.ecology = EcologyService(engine)
    engine.keepsakes = KeepsakeTimelineService(engine)
    engine.mailbox = MailboxVisitorService(engine)
    engine.world_spaces = WorldSpaceService(engine)
    try:
        with engine._db(notify=False) as db:
            assert db.execute("PRAGMA synchronous").fetchone()[0] == 1  # NORMAL
            assert db.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
            assert db.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
            assert db.execute("PRAGMA foreign_keys").fetchone()[0] == 1

        writes = 0

        def on_write():
            nonlocal writes
            writes += 1

        engine.on_db_write = on_write
        traced: list[str] = []
        raw_db = engine._db

        def tracked_db(**kwargs):
            cm = raw_db(**kwargs)

            class _Wrap:
                def __enter__(self):
                    conn = cm.__enter__()
                    conn.set_trace_callback(traced.append)
                    return conn

                def __exit__(self, *args):
                    return cm.__exit__(*args)

            return _Wrap()

        engine._db = tracked_db

        global_scope = dict(scope, umo="", platform="")
        snap = await engine.get_snapshot(global_scope)
        assert snap["managed"] is True
        assert writes == 0
        assert not any("BEGIN IMMEDIATE" in sql.upper() for sql in traced)
        assert not any(
            sql.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
            for sql in traced
        )

        # Verify lives/scopes/keyframes were not written by read-only get_snapshot.
        with raw_db(notify=False) as db:
            assert db.execute("SELECT COUNT(*) FROM lives").fetchone()[0] == 0
            assert db.execute("SELECT COUNT(*) FROM scopes").fetchone()[0] == 0
            assert (
                db.execute("SELECT COUNT(*) FROM world_timeline_keyframes").fetchone()[0]
                == 0
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_p0_async_db_operations_run_off_event_loop_thread(tmp_path):
    engine, scope, now, _ = _make_engine(tmp_path)
    try:
        main_tid = threading.get_ident()
        seen_tids: dict[str, set[int]] = {
            "ingest": set(),
            "advance": set(),
            "tick": set(),
            "outreach": set(),
        }
        phase = ["ingest"]
        raw_db = engine._db

        def observing_db(**kwargs):
            seen_tids[phase[0]].add(threading.get_ident())
            return raw_db(**kwargs)

        engine._db = observing_db

        ev = {
            "event_id": "e-thread-1",
            "type": "chat.message",
            "occurred_at": now[0],
            "received_at": now[0],
            "scope": scope,
            "actor_id": "u1",
            "text": "我今天有点头疼，晚点再说",
            "fact_kind": "observation",
            "data": {"directed_to_bot": True},
        }
        phase[0] = "ingest"
        await engine.ingest_events([ev])
        assert seen_tids["ingest"] and main_tid not in seen_tids["ingest"]

        phase[0] = "advance"
        await engine.advance([ev])
        assert seen_tids["advance"] and main_tid not in seen_tids["advance"]

        phase[0] = "tick"
        await engine.tick()
        assert seen_tids["tick"] and main_tid not in seen_tids["tick"]

        phase[0] = "outreach"
        await engine.review_outreach()
        assert seen_tids["outreach"] and main_tid not in seen_tids["outreach"]
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_p0_prune_history_deletes_old_terminal_rows_in_batches_and_preserves_active(
    tmp_path,
):
    engine, scope, now, _ = _make_engine(tmp_path)
    try:
        ident = _identity(scope)
        old_ts = now[0] - 70 * 86400
        fresh_ts = now[0] - 5 * 86400
        old_hour = int(old_ts // 3600)
        fresh_hour = int(fresh_ts // 3600)

        with engine._db(notify=False) as db:
            for idx in range(5):
                db.execute(
                    "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,0,0)",
                    (f"ev-old-done-{idx}", ident, scope["umo"], old_ts, old_ts, "{}", "processed", "", old_ts),
                )
            db.execute(
                "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,0,0)",
                ("ev-old-pending", ident, scope["umo"], old_ts, old_ts, "{}", "pending", "", old_ts),
            )
            db.execute(
                "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,0,0)",
                ("ev-fresh-done", ident, scope["umo"], fresh_ts, fresh_ts, "{}", "processed", "", fresh_ts),
            )
            for idx in range(3):
                db.execute(
                    "INSERT INTO calls VALUES(?,?,?,?,?,?,?)",
                    (f"c-old-{idx}", ident, scope["umo"], old_ts, 0.2, "ok", "extra"),
                )
            db.execute(
                "INSERT INTO calls VALUES(?,?,?,?,?,?,?)",
                ("c-fresh", ident, scope["umo"], fresh_ts, 0.2, "ok", "extra"),
            )
            db.execute("INSERT INTO budgets VALUES(?,?,?,?)", (ident, old_hour, "extra", 3))
            db.execute("INSERT INTO budgets VALUES(?,?,?,?)", (ident, fresh_hour, "extra", 2))
            db.execute(
                "INSERT INTO validation_failures VALUES(?,?,?,?)",
                ("vf-old", "[]", "err", old_ts),
            )
            db.execute(
                "INSERT INTO validation_failures VALUES(?,?,?,?)",
                ("vf-fresh", "[]", "err", fresh_ts),
            )
            db.execute(
                "INSERT INTO intents VALUES(?,?,?,?,?,?,?,?)",
                ("in-old-sent", ident, scope["umo"], "{}", "sent", old_ts, old_ts + 60, old_ts),
            )
            db.execute(
                "INSERT INTO intents VALUES(?,?,?,?,?,?,?,?)",
                ("in-old-pending", ident, scope["umo"], "{}", "pending", old_ts, old_ts + 60, old_ts),
            )
            db.execute(
                "INSERT INTO intents VALUES(?,?,?,?,?,?,?,?)",
                ("in-fresh-sent", ident, scope["umo"], "{}", "sent", fresh_ts, fresh_ts + 60, fresh_ts),
            )

        summary = engine.prune_history(retention_days=60, batch_size=2, now=now[0])
        assert summary["events"] == 5
        assert summary["calls"] == 3
        assert summary["budgets"] == 1
        assert summary["validation_failures"] == 1
        assert summary["intents"] == 1
        assert summary["total_deleted"] == 11
        assert summary["vacuumed"] is True

        with engine._db(notify=False) as db:
            ev_ids = {r[0] for r in db.execute("SELECT event_id FROM events").fetchall()}
            assert ev_ids == {"ev-old-pending", "ev-fresh-done"}
            assert [r[0] for r in db.execute("SELECT call_id FROM calls").fetchall()] == ["c-fresh"]
            assert [r[0] for r in db.execute("SELECT hour FROM budgets").fetchall()] == [fresh_hour]
            assert [r[0] for r in db.execute("SELECT failure_id FROM validation_failures").fetchall()] == ["vf-fresh"]
            in_ids = {r[0] for r in db.execute("SELECT intent_id FROM intents").fetchall()}
            assert in_ids == {"in-old-pending", "in-fresh-sent"}
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_p0_outreach_intents_filter_and_composite_index(tmp_path):
    engine, scope, now, _ = _make_engine(tmp_path)
    try:
        with engine._db(notify=False) as db:
            idx_names = {
                r[0]
                for r in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='intents'"
                ).fetchall()
            }
            assert "intent_scope_status_updated" in idx_names
            assert "intent_status_updated" in idx_names

        # Insert an old terminal intent (>24h ago) for same recipient, then ensure
        # outreach query filters with (status IN ('pending','claimed') OR updated>?).
        ident = _identity(scope)
        ev = {
            "event_id": "e-care-1",
            "type": "message.received",
            "occurred_at": now[0] - 60,
            "received_at": now[0] - 60,
            "scope": scope,
            "actor_id": "u1",
            "text": "我发烧不太舒服，先去躺会儿",
            "fact_kind": "observation",
            "data": {"directed_to_bot": True},
        }
        await engine.ingest_events([ev])
        with engine._db(notify=False) as db:
            db.execute(
                "INSERT INTO intents VALUES(?,?,?,?,?,?,?,?)",
                (
                    "old-care",
                    ident,
                    scope["umo"],
                    json.dumps(
                        {
                            "intent_id": "old-care",
                            "kind": "care_wait",
                            "recipient_user_id": "u1",
                            "source_ids": ["ancient-evt"],
                            "created_at": now[0] - 200000,
                        }
                    ),
                    "sent",
                    now[0] - 200000,
                    now[0] - 100000,
                    now[0] - 100000,
                ),
            )

        async def outreach_model(_req):
            return {
                "schema_version": 1,
                "no_change": False,
                "care_waits": [
                    {
                        "subject_id": "u1",
                        "reason_kind": "health_concern",
                        "reason": "成员提到发烧不舒服",
                        "waiting_for": "对方休息后回复",
                        "evidence_quote": "我发烧不太舒服",
                        "source_ids": ["e-care-1"],
                        "not_before": now[0] + 3600,
                        "expires_at": now[0] + 86400,
                    }
                ],
            }

        engine.model = outreach_model
        traced: list[str] = []
        raw_db = engine._db

        def tracked_db(**kwargs):
            cm = raw_db(**kwargs)

            class _Wrap:
                def __enter__(self):
                    conn = cm.__enter__()
                    conn.set_trace_callback(traced.append)
                    return conn

                def __exit__(self, *args):
                    return cm.__exit__(*args)

            return _Wrap()

        engine._db = tracked_db
        res = await engine.review_outreach()
        assert res == [{"status": "ok", "candidates": 1}]
        assert any(
            "FROM intents WHERE" in s
            and "status IN ('pending','claimed') OR updated>" in s
            for s in traced
        )
    finally:
        await engine.close()


def test_p1_build_release_excludes_unused_azgaar_assets_and_keeps_core(tmp_path):
    spec = importlib.util.spec_from_file_location("br_p1", ROOT / "build_release.py")
    br = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(br)

    out_zip = tmp_path / "dw_release.zip"
    res = br.build(ROOT, out_zip)
    assert res["bytes"] <= 16_000_000

    with zipfile.ZipFile(out_zip) as zf:
        names = set(zf.namelist())
        for prefix in (
            "icons-charges-",
            "view-3d-renderer",
            "Dropbox-sdk",
            "notes-editor",
            "assistant-",
            "Knowledge Base",
            "jszip",
            "battle-screen",
            "ui-tour",
        ):
            assert not any(
                n.startswith("vendor/azgaar/") and n.rsplit("/", 1)[-1].startswith(prefix)
                for n in names
            ), f"Unexpected excluded Azgaar asset leaked: {prefix}"
        assert not any(
            n.startswith("vendor/azgaar/heightmaps/") and n.endswith(".png")
            for n in names
        )
        # Core headless rendering files must remain intact.
        for required in (
            "vendor/azgaar/index.html",
            "vendor/azgaar/index-CH0Rm5id.js",
            "vendor/azgaar/app-BvZbQ29j.js",
            "vendor/azgaar/layers-BiK81IJP.js",
            "vendor/azgaar/en-BpPoOois.js",
            "vendor/azgaar/zh-r7nepuD_.js",
        ):
            assert required in names


def test_p1_whale_maid_image_compressed_under_150kb():
    img_path = ROOT / "pages" / "world" / "deepseek-whale-maid.jpg"
    assert img_path.is_file()
    raw = img_path.read_bytes()
    assert raw[:3] == b"\xff\xd8\xff"
    assert len(raw) <= 150 * 1024


def test_p1_frontend_lazy_loads_leaflet_and_non_first_screen_views():
    html = (ROOT / "pages" / "world" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "pages" / "world" / "app.js").read_text(encoding="utf-8")

    # Blocking <script src="./vendor/leaflet/leaflet.js"> removed from <head>
    assert '<script src="./vendor/leaflet/leaflet.js"></script>' not in html

    # No eager top-level static imports for map/setup/creative-world
    assert 'import "./map.js' not in app_js
    assert 'import "./setup.js' not in app_js
    assert 'import "./creative-world.js' not in app_js

    # Dynamic on-demand script injection and dynamic import() present
    assert "./vendor/leaflet/leaflet.js" in app_js
    assert 'import("./map.js?v=round2.1")' in app_js
    assert 'import("./setup.js?v=series-audit.1")' in app_js
    assert 'import("./creative-world.js?v=wb-iso.1")' in app_js


def test_p1_prompt_pruning_for_manual_regen_and_scoped_advance():
    character = {"persona_id": "anan", "core_prompt": "安静但细心的角色。"}
    base_snapshot = {
        "scene": {
            "available": True,
            "rooms": [{"id": "study", "name": "书房"}],
            "room_designs": [{"room_id": "study", "furniture": [{"id": "desk_1"}]}],
            "items": [{"id": "book_1", "name": "旧笔记", "kind": "book"}],
            "projects": [{"id": "proj_1", "title": "海边随笔", "stage": "draft"}],
        },
        "environment": {
            "available": True,
            "stale": False,
            "mode": "fiction",
            "location": "海边小镇",
            "forecast": [{"hour": h, "temp": 20} for h in range(12)],
            "current": {"temperature": 21, "label": "晴"},
        },
        "causal_life": {
            "viewer": "actor",
            "actor_id": "self",
            "baseline": "已确认活动",
            "agenda": [{"id": "p1", "activity": "阅读", "status": "planned"}],
            "events": [],
        },
    }

    regen_req = {
        "scope": {"platform": "", "umo": "", "persona_id": "anan", "instance_id": "anan"},
        "now": 1_800_000_000.0,
        "manual_plan_regeneration": True,
        "needs_daily_plan": True,
        "snapshot": base_snapshot,
        "events": [{"event_id": "regen1", "type": "life.tick", "text": ""}],
    }
    r_sys, r_ctx, r_dyn = build_narrative_prompt_segments(regen_req, character)
    assert len(r_sys) < len(NARRATIVE_RULES)
    assert "project_start" not in r_sys and "move_furniture" not in r_sys
    for pruned in ("room_designs", "desk_1", "book_1", "proj_1"):
        assert pruned not in r_ctx and pruned not in r_dyn

    scoped_req = {
        "scope": {"platform": "qq", "umo": "qq:GroupMessage:888", "persona_id": "anan", "instance_id": "anan"},
        "now": 1_800_000_000.0,
        "snapshot": base_snapshot,
        "events": [{"event_id": "m1", "type": "chat.message", "text": "晚上好"}],
    }
    s_sys, s_ctx, s_dyn = build_narrative_prompt_segments(scoped_req, character)
    assert len(s_sys) < len(NARRATIVE_RULES)
    assert "project_start" not in s_sys and "move_furniture" not in s_sys
    for pruned in ("room_designs", "desk_1", "book_1", "proj_1"):
        assert pruned not in s_ctx and pruned not in s_dyn
    assert "书房" in s_ctx

    global_req = {
        "scope": {"platform": "", "umo": "", "persona_id": "anan", "instance_id": "anan"},
        "now": 1_800_000_000.0,
        "snapshot": base_snapshot,
        "events": [{"event_id": "t1", "type": "life.tick", "text": ""}],
    }
    g_sys, g_ctx, g_dyn = build_narrative_prompt_segments(global_req, character)
    assert NARRATIVE_RULES in g_sys
    assert "desk_1" in g_dyn and "proj_1" in g_dyn
    assert "desk_1" not in g_ctx and "proj_1" not in g_ctx
    assert "book_1" in g_dyn and "book_1" not in g_ctx


def test_p1_kv_cache_sinks_volatile_fields_from_contexts0_to_dynamic_prompt():
    character = {"persona_id": "anan", "core_prompt": "角色设定"}

    def make_req(page: int, agenda_status: str, forecast_temp: int):
        return {
            "scope": {"platform": "", "umo": "", "persona_id": "anan", "instance_id": "anan"},
            "now": 1_800_000_000.0 + page * 60,
            "timezone": "Asia/Shanghai",
            "local_date": "2026-11-21",
            "day_end": 1_800_057_600.0,
            "snapshot": {
                "scene": {
                    "available": True,
                    "rooms": [{"id": "study", "name": "书房"}],
                    "items": [{"id": "book_1", "page": page}],
                },
                "environment": {
                    "available": True,
                    "stale": False,
                    "mode": "fiction",
                    "location": "海边小镇",
                    "forecast": [{"hour": 0, "temp": forecast_temp}],
                    "current": {"temperature": 21, "label": "晴"},
                },
                "causal_life": {
                    "viewer": "actor",
                    "actor_id": "self",
                    "baseline": "已确认活动",
                    "agenda": [{"id": "p1", "activity": "阅读", "status": agenda_status}],
                    "events": [],
                },
            },
            "events": [{"event_id": f"e{page}", "type": "life.tick", "text": ""}],
        }

    sys1, ctx1, dyn1 = build_narrative_prompt_segments(make_req(10, "planned", 20), character)
    sys2, ctx2, dyn2 = build_narrative_prompt_segments(make_req(25, "done", 15), character)
    assert sys1 == sys2
    assert ctx1 == ctx2
    assert '"items"' not in ctx1
    assert '"agenda"' not in ctx1
    assert '"forecast"' not in ctx1
    assert '"items"' in dyn1 and '"agenda"' in dyn1 and '"forecast"' in dyn1
    assert dyn1 != dyn2


@pytest.mark.asyncio
async def test_p1_global_hourly_budget_and_outreach_budget_cap(tmp_path):
    calls: list[dict] = []

    async def model_fn(req):
        calls.append(req)
        return {
            "no_change": False,
            "state": {
                "activity_code": "reading",
                "availability": "available",
                "valid_until": req["now"] + 7200,
            },
            "next_check": req["now"] + 7200,
        }

    engine, scope_a, now, _ = _make_engine(
        tmp_path,
        config_extra={
            "narrative_global_hourly_budget": 3,
            "narrative_outreach_hourly_budget": 1,
        },
        model_fn=model_fn,
    )
    scope_b = dict(scope_a, umo="qq:GroupMessage:1002")
    try:
        # 2 calls in group A + 1 call in group B => hits global cap of 3
        for idx, sc in enumerate((scope_a, scope_a, scope_b)):
            now[0] += 1
            res = await engine.advance(
                [
                    {
                        "event_id": f"gb-{idx}",
                        "type": "chat.message",
                        "occurred_at": now[0],
                        "received_at": now[0],
                        "scope": sc,
                        "actor_id": "u1",
                        "text": f"约定第{idx}件事",
                        "fact_kind": "observation",
                        "data": {"directed_to_bot": True},
                    }
                ]
            )
            assert res["status"] == "advanced"

        # 4th call in group B must be blocked by cross-group global hourly cap (even though group B used 1/6)
        now[0] += 1
        res_cap = await engine.advance(
            [
                {
                    "event_id": "gb-overflow",
                    "type": "chat.message",
                    "occurred_at": now[0],
                    "received_at": now[0],
                    "scope": scope_b,
                    "actor_id": "u1",
                    "text": "再约定一件",
                    "fact_kind": "observation",
                    "data": {"directed_to_bot": True},
                }
            ]
        )
        assert res_cap["status"] == "budget_exhausted"
        assert len(calls) == 3

        # Next hour: test outreach budget cap = 1 per session
        now[0] += 3600

        async def outreach_model_fn(req):
            calls.append(req)
            return {"no_change": True}

        engine.model = outreach_model_fn
        await engine.ingest_events(
            [
                {
                    "event_id": "out-1",
                    "type": "message.received",
                    "occurred_at": now[0],
                    "received_at": now[0],
                    "scope": scope_a,
                    "actor_id": "u1",
                    "text": "我今天发烧不太舒服",
                    "fact_kind": "observation",
                    "data": {"directed_to_bot": True},
                }
            ]
        )
        out1 = await engine.review_outreach()
        assert len(out1) == 2
        assert all(item == {"status": "ok", "candidates": 0} for item in out1)

        # Advance 6 minutes + new message so marker & fingerprint allow re-review within same hour
        now[0] += 360
        await engine.ingest_events(
            [
                {
                    "event_id": "out-2",
                    "type": "message.received",
                    "occurred_at": now[0],
                    "received_at": now[0],
                    "scope": scope_a,
                    "actor_id": "u1",
                    "text": "现在还在发烧，等会儿再说",
                    "fact_kind": "observation",
                    "data": {"directed_to_bot": True},
                }
            ]
        )
        calls_before = len(calls)
        out2 = await engine.review_outreach()
        assert out2 == [{"status": "budget_exhausted", "candidates": 0}]
        assert len(calls) == calls_before
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_p1_generator_enforces_explicit_llm_timeout(tmp_path):
    async def slow_text_chat(prompt, session_id=None):
        await asyncio.sleep(5)
        return NS(completion_text="{}")

    provider = NS(
        text_chat=slow_text_chat,
        provider_config={"id": "slow-p", "model": "slow"},
    )
    ctx = NS(
        get_provider_by_id=lambda pid: provider if pid == "slow-p" else None,
        get_using_provider=lambda: provider,
        get_all_stars=lambda: [],
        persona_manager=None,
    )
    cfg = {
        "llm_provider_id": "slow-p",
        "narrative_timeout_seconds": 1,
        "history_reference_days": 0,
    }
    data_mgr = DataManager(tmp_path / "life_state")
    gen = Generator(ctx, cfg, data_mgr)

    started = time.monotonic()
    res = await gen.generate(dt.date(2026, 11, 21), force=True)
    elapsed = time.monotonic() - started
    assert res.succeeded is False
    assert elapsed < 3.0


@pytest.mark.asyncio
async def test_p2_series_hooks_isolates_blocking_sync_hooks_and_records_diagnostics(
    tmp_path, monkeypatch
):
    plugin, entries, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    try:
        seed(plugin)
        main_tid = threading.get_ident()
        world_tids: list[int] = []
        orig_collect = series_hooks.collect_world_journal_events

        def tracked_collect(*args, **kwargs):
            world_tids.append(threading.get_ident())
            return orig_collect(*args, **kwargs)

        monkeypatch.setattr(series_hooks, "collect_world_journal_events", tracked_collect)

        class BlockingSyncSibling:
            def get_journal_events(self, **_kwargs):
                time.sleep(0.7)
                return [{"id": "late", "title": "too slow"}]

        class CrashingSyncSibling:
            def get_journal_events(self, **_kwargs):
                raise RuntimeError("boom_sync")

        entries.append(
            NS(
                name="astrbot_plugin_dynamics_memory",
                activated=True,
                star_cls=BlockingSyncSibling(),
            )
        )
        entries.append(
            NS(
                name="astrbot_plugin_dynamics_games",
                activated=True,
                star_cls=CrashingSyncSibling(),
            )
        )

        # Verify event loop stays responsive while blocking sibling runs in worker thread.
        ticks = 0

        async def ticker():
            nonlocal ticks
            for _ in range(5):
                await asyncio.sleep(0.03)
                ticks += 1

        started = time.monotonic()
        feed, _ = await asyncio.gather(
            series_hooks.aggregate_journal_feed(plugin, scope=UMO, date="today", limit=20),
            ticker(),
        )
        elapsed = time.monotonic() - started
        assert ticks == 5
        assert elapsed < 0.65
        assert world_tids and main_tid not in world_tids
        assert feed["sources"]["memory"]["available"] is False
        assert feed["sources"]["memory"].get("error") == "TimeoutError"
        assert feed["sources"]["games"]["available"] is False
        assert feed["sources"]["games"].get("error") == "RuntimeError"

        diag = series_hooks.get_hook_diagnostics()
        assert "sibling_journal:astrbot_plugin_dynamics_memory" in diag
        assert "sibling_journal:astrbot_plugin_dynamics_games" in diag
    finally:
        await plugin.terminate()


@pytest.mark.asyncio
async def test_p2_get_series_health_contract_and_silent_provider_check(
    tmp_path, monkeypatch
):
    plugin, _, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    try:
        seed(plugin)
        warn_calls = []

        def fail_if_called(pid):
            warn_calls.append(pid)
            raise AssertionError("get_provider_by_id must not be called by get_series_health")

        plugin.context.get_provider_by_id = fail_if_called
        plugin.context.provider_manager = NS(
            inst_map={"p-narr": NS(id="p-narr"), "p-daily": NS(id="p-daily")}
        )
        plugin.config["narrative_provider_id"] = "p-narr"
        plugin.config["llm_provider_id"] = "p-daily"

        health = series_panels.read_plugin_health("astrbot_plugin_dynamics_world", plugin)
        assert health is not None
        assert health["plugin_id"] == "astrbot_plugin_dynamics_world"
        assert health["ready"] is True
        assert health["degraded"] is False
        assert health["issues"] == []
        by_role = {p["role"]: p for p in health["providers"]}
        assert by_role["narrative"]["status"] == "ok"
        assert by_role["narrative"]["provider_id"] == "p-narr"
        assert by_role["daily_life"]["status"] == "ok"
        assert by_role["daily_life"]["provider_id"] == "p-daily"
        assert isinstance(health["metrics"], dict)
        assert health["metrics"]["card_count"] >= 1
        assert warn_calls == []

        # Missing provider marks degraded without calling get_provider_by_id.
        plugin.config["narrative_provider_id"] = "missing-provider"
        degraded = series_panels.read_plugin_health("astrbot_plugin_dynamics_world", plugin)
        assert degraded is not None
        assert degraded["degraded"] is True
        assert any("provider_missing:narrative:missing-provider" in i for i in degraded["issues"])
        assert warn_calls == []
    finally:
        await plugin.terminate()
