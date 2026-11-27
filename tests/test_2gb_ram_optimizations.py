"""Focused 2GB RAM optimization tests for astrbot_plugin_dynamics_world."""
from __future__ import annotations

import asyncio
import base64
import json
import sys
import types
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from astrbot_plugin_dynamics_world import onboarding as onboarding_mod
from astrbot_plugin_dynamics_world import series_panels
from astrbot_plugin_dynamics_world.life.core.narrative import NarrativeEngine
from astrbot_plugin_dynamics_world.map_service import MapService
from astrbot_plugin_dynamics_world.postcard_renderer import (
    CHROMIUM_ARGS,
    PostcardRenderer,
    _load_font,
    _sanitize_snapshot_for_browser,
)
from astrbot_plugin_dynamics_world.spatial import SpatialState
from astrbot_plugin_dynamics_world.world.core.models import WorldBook
from astrbot_plugin_dynamics_world.world.core.store import WorldBookStore


def _make_profile_ctx(profile: str):
    owner = NS(
        get_series_shared_config=lambda: {
            "enabled": True,
            "resource_profile": profile,
        }
    )
    star = NS(activated=True, star_cls=owner, name="astrbot_plugin_chat_dynamics")
    return NS(
        get_all_stars=lambda: {"astrbot_plugin_chat_dynamics": star},
        get_registered_star=lambda name: star if name == "astrbot_plugin_chat_dynamics" else None,
    )


def _tiny_png_data_url() -> str:
    buf = BytesIO()
    Image.new("RGB", (4, 4), (40, 80, 120)).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def test_load_font_is_lru_cached():
    _load_font.cache_clear()
    f1 = _load_font(16)
    f2 = _load_font(16)
    assert f1 is f2
    info = _load_font.cache_info()
    assert info.maxsize == 16
    assert info.hits >= 1


def test_chromium_args_include_low_memory_flags():
    for flag in (
        "--js-flags=--max-old-space-size=128",
        "--renderer-process-limit=1",
        "--disable-extensions",
        "--disable-background-networking",
        "--mute-audio",
        "--no-first-run",
        "--disable-component-update",
    ):
        assert flag in CHROMIUM_ARGS


def test_sanitize_snapshot_strips_map_and_model_blobs():
    snap = {
        "scene": {"room_id": "r1"},
        "map": {"image": "data:image/png;base64," + "A" * 10000, "graph": {"points": [[0, 0]]}},
        "avatar_model": {"id": "m1", "blob": "B" * 5000},
        "guest_avatar_model": {"id": "g1", "blob": "C" * 5000},
        "cabin_style": "cottage",
    }
    slim = _sanitize_snapshot_for_browser(snap)
    assert "map" not in slim
    assert "avatar_model" not in slim
    assert "guest_avatar_model" not in slim
    assert slim["scene"] == {"room_id": "r1"}
    assert "map" in snap  # original untouched


def test_postcard_low_memory_gate_strip_and_instant_teardown(tmp_path, monkeypatch):
    ctx = _make_profile_ctx("low_memory")
    monkeypatch.setenv("ASTRBOT_TEST_RSS_MB", "300")
    renderer = PostcardRenderer(tmp_path / "data", context=ctx)
    assert renderer.idle_timeout == 0.0

    bundle = tmp_path / "pages" / "world" / "cabin3d.min.js"
    bundle.parent.mkdir(parents=True)
    bundle.write_text("export function createCabin3D(){}", encoding="utf-8")

    eval_args = []
    closed = {"page": 0, "browser": 0, "pw": 0}

    class FakePage:
        def is_closed(self):
            return False

        async def set_content(self, _html):
            return None

        async def evaluate(self, _script, arg):
            eval_args.append(arg)
            if len(eval_args) == 1:
                return True
            return _tiny_png_data_url()

        async def close(self):
            closed["page"] += 1

    class FakeBrowser:
        async def new_page(self, **_kw):
            return FakePage()

        async def close(self):
            closed["browser"] += 1

    class FakePW:
        chromium = NS(launch=lambda **_kw: asyncio.sleep(0, result=FakeBrowser()))

        async def stop(self):
            closed["pw"] += 1

    fake_mod = types.ModuleType("playwright.async_api")
    fake_mod.async_playwright = lambda: NS(start=lambda: asyncio.sleep(0, result=FakePW()))
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_mod)

    snap = {
        "server_time": 1_800_000_000.0,
        "cabin_style": "cottage",
        "map": {"image": "data:image/png;base64," + "X" * 4096},
        "avatar_model": {"id": "custom_ysm"},
        "scene": {"place_id": "home", "room_id": "study", "rooms": [{"place_id": "home"}]},
    }

    before_acquired = series_panels.get_heavy_subprocess_snapshot(ctx)["total_acquired"]
    res = asyncio.run(renderer.render(snap, plugin_dir=tmp_path, prefer_3d=True))
    after_acquired = series_panels.get_heavy_subprocess_snapshot(ctx)["total_acquired"]

    assert res["renderer"] == "3d"
    assert after_acquired == before_acquired + 1
    assert "map" not in eval_args[1]["snapshot"]
    assert "avatar_model" not in eval_args[1]["snapshot"]
    # Zero idle RAM in low_memory: Chromium is closed immediately after capture
    assert renderer.is_warm is False
    assert closed == {"page": 1, "browser": 1, "pw": 1}


def test_postcard_hard_watermark_and_aggressive_profile_fallback(tmp_path, monkeypatch):
    ctx_low = _make_profile_ctx("low_memory")
    renderer_low = PostcardRenderer(tmp_path / "d1", context=ctx_low)
    called = {"capture": 0}

    async def fake_capture(_snap, _pdir, _plan):
        called["capture"] += 1
        return Image.new("RGB", (720, 460), (20, 30, 40))

    monkeypatch.setattr(renderer_low, "_try_playwright_capture", fake_capture)
    monkeypatch.setenv("ASTRBOT_TEST_RSS_MB", "950")  # > 820 MiB hard watermark
    res = asyncio.run(
        renderer_low.render(
            {"server_time": 1_800_000_000.0, "scene": {"place_id": "home", "rooms": [{"place_id": "home"}]}},
            plugin_dir=tmp_path,
            prefer_3d=True,
        )
    )
    assert res["renderer"] == "2d_fallback"
    assert called["capture"] == 0

    # low_memory_aggressive defaults to 2D unless force_3d=True
    ctx_agg = _make_profile_ctx("low_memory_aggressive")
    renderer_agg = PostcardRenderer(tmp_path / "d2", context=ctx_agg)
    monkeypatch.setattr(renderer_agg, "_try_playwright_capture", fake_capture)
    monkeypatch.setenv("ASTRBOT_TEST_RSS_MB", "250")
    res_default = asyncio.run(
        renderer_agg.render(
            {"server_time": 1_800_000_001.0, "scene": {"place_id": "home", "rooms": [{"place_id": "home"}]}},
            plugin_dir=tmp_path,
            prefer_3d=True,
        )
    )
    assert res_default["renderer"] == "2d_fallback"
    assert called["capture"] == 0

    res_forced = asyncio.run(
        renderer_agg.render(
            {"server_time": 1_800_000_002.0, "scene": {"place_id": "home", "rooms": [{"place_id": "home"}]}},
            plugin_dir=tmp_path,
            prefer_3d=True,
            force_3d=True,
        )
    )
    assert res_forced["renderer"] == "3d"
    assert called["capture"] == 1


def test_travel_postcard_cache_cap_tightened_in_low_memory(tmp_path, monkeypatch):
    ctx = _make_profile_ctx("low_memory")
    renderer = PostcardRenderer(tmp_path / "travel", context=ctx, cache_ttl_seconds=60.0)
    for i in range(12):
        asyncio.run(
            renderer.render(
                {
                    "server_time": 1_800_000_000.0 + i,
                    "scene": {"phase": "travelling", "destination": f"地标{i}"},
                    "actor": {"phase": "travelling"},
                },
                shot_mode="travel",
                caption=f"旅途明信片 {i}",
            )
        )
    assert len(renderer._render_cache) <= 8


def test_map_service_acquires_gate_hibernates_postcards_and_spatial_install_no_mutate(tmp_path, monkeypatch):
    ctx = _make_profile_ctx("low_memory")
    engine = NarrativeEngine(
        tmp_path / "narrative.sqlite3",
        {"mode": "narrative", "persona_id": "p1", "narrative_sessions": ["qq:GroupMessage:1"]},
        AsyncMock(return_value={"no_change": True}),
        host_context=ctx,
    )
    engine.spatial = SpatialState(engine)
    order: list[str] = []

    class FakePostcards:
        async def hibernate_now(self):
            order.append("hibernate")

    async def fake_exec(*args, **kwargs):
        order.append("spawn")
        out_path = Path(args[3])
        raw = {
            "width": 100,
            "height": 100,
            "image": "data:image/png;base64,iVBORw0KGgo=",
            "points": [[10, 10], [50, 50]],
            "edges": [[1], [0]],
            "heights": [30, 30],
            "burgs": [{"cell": 0, "name": "A"}, {"cell": 1, "name": "B"}],
        }
        out_path.write_text(json.dumps(raw), encoding="utf-8")

        class FakeProc:
            returncode = 0

            async def communicate(self):
                return b"", b""

        return FakeProc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    plugin = NS(
        context=ctx,
        _terminating=False,
        postcards=FakePostcards(),
        world=NS(get_character_context=AsyncMock(return_value={"available": True, "fingerprint": "fp1"})),
        life=NS(narrative=engine),
    )
    svc = MapService(plugin)
    scope = {"persona_id": "p1", "instance_id": "p1", "umo": "", "platform": ""}
    before_acq = series_panels.get_heavy_subprocess_snapshot(ctx)["total_acquired"]
    try:
        asyncio.run(svc._generate(scope, "seed-1", ["小屋", "湖畔"], 10, 0, "fp1"))
        assert svc.job["status"] == "complete"
        assert order == ["hibernate", "spawn"]
        assert series_panels.get_heavy_subprocess_snapshot(ctx)["total_acquired"] == before_acq + 1

        # Verify spatial.install does not mutate caller's document dict
        doc = {
            "schema_version": 1,
            "seed": "seed-2",
            "map_type": "virtual",
            "width": 100,
            "height": 100,
            "seconds_per_unit": 10,
            "places": [{"id": "place_x", "name": "X", "x": 10, "y": 10, "cell": 0}],
            "roads": [],
            "graph": {"points": [[10, 10]], "edges": [[]]},
            "image": "data:image/png;base64,iVBORw0KGgo=",
        }
        res = engine.spatial.install(scope, doc, expected_revision=1)
        assert res["revision"] == 2
        assert "revision" not in doc
        assert "world_id" not in doc
    finally:
        asyncio.run(engine.close())


def test_onboarding_browser_status_uses_fs_probe_and_300s_cache(tmp_path, monkeypatch):
    browsers_root = tmp_path / "ms-playwright"
    chrome_bin = browsers_root / "chromium-1148" / "chrome-linux" / "chrome"
    chrome_bin.parent.mkdir(parents=True)
    chrome_bin.write_bytes(b"ELF")
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(browsers_root))

    def _boom():
        raise AssertionError("async_playwright must not be spawned when fs probe succeeds")

    fake_pw_mod = types.ModuleType("playwright.async_api")
    fake_pw_mod.async_playwright = _boom
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_pw_mod)

    onb = onboarding_mod.Onboarding(NS())
    st1 = asyncio.run(onb.browser_status())
    assert st1 == {"installed": True, "module_available": True}

    # Remove binary on disk; cached result still returns True within 300s TTL
    chrome_bin.unlink()
    st2 = asyncio.run(onb.browser_status())
    assert st2 == {"installed": True, "module_available": True}


def test_narrative_pragmas_workers_retry_cap_and_prune_counts(tmp_path):
    ctx = _make_profile_ctx("low_memory")
    now = [1_800_000_000.0]
    scope = {"platform": "qq", "umo": "qq:GroupMessage:g1", "persona_id": "p1", "instance_id": "p1"}
    cfg = {"mode": "narrative", "persona_id": "p1", "narrative_sessions": [scope["umo"]]}
    engine = NarrativeEngine(
        tmp_path / "narrative.sqlite3",
        cfg,
        AsyncMock(return_value={"no_change": True}),
        lambda: now[0],
        host_context=ctx,
    )
    try:
        # 1) Snapshot workers sized by profile (low_memory -> 1)
        assert engine._snapshot_io._executor._max_workers == 1

        # 2) SQLite PRAGMAs applied in _db()
        with engine._db(notify=False) as db:
            assert db.execute("PRAGMA cache_size").fetchone()[0] == -1024
            assert db.execute("PRAGMA temp_store").fetchone()[0] == 1  # FILE
            assert db.execute("PRAGMA mmap_size").fetchone()[0] == 0
            assert db.execute("PRAGMA journal_size_limit").fetchone()[0] == 4 * 1024 * 1024

        # 3) _record_failure caps retry_attempt at 10 -> status='failed'
        ev = {
            "event_id": "ev-stuck",
            "type": "chat.message",
            "occurred_at": now[0] - 40 * 86400,
            "received_at": now[0] - 40 * 86400,
            "scope": scope,
            "text": "hello",
            "fact_kind": "observation",
            "data": {},
        }
        asyncio.run(engine.ingest_events([ev]))
        for i in range(9):
            engine._record_failure([ev], now[0] - 35 * 86400 + i, "validation.bad")
            with engine._db(notify=False) as db:
                row = db.execute("SELECT status, retry_attempt FROM events WHERE event_id='ev-stuck'").fetchone()
            assert row["status"] == "pending"
            assert row["retry_attempt"] == i + 1

        engine._record_failure([ev], now[0] - 35 * 86400 + 9, "validation.bad")
        with engine._db(notify=False) as db:
            row = db.execute("SELECT status, retry_attempt, next_retry FROM events WHERE event_id='ev-stuck'").fetchone()
        assert row["status"] == "failed"
        assert row["retry_attempt"] == 10
        assert row["next_retry"] == 0

        # 4) _maybe_prune_history respects low_memory 30d retention & counts validation_failure_events
        ident = json.dumps(["p1", "p1"], separators=(",", ":"))
        summary = engine._maybe_prune_history(ident, now[0])
        assert summary is not None
        assert summary["retention_days"] == 30
        assert summary["validation_failure_events"] == 10
        assert summary["total_deleted"] >= 10
        assert summary["wal_checkpointed"] is True
    finally:
        asyncio.run(engine.close())


def test_life_service_idle_backoff_uses_profile_limits():
    # Load life/service.py helper logic without importing optional holidays/apscheduler
    service_path = Path(__file__).parents[1] / "life" / "service.py"
    source = service_path.read_text(encoding="utf-8")
    assert "world_loop_idle_s" in source
    assert '"outreach": asyncio.Event()' in source
    assert '_loop_sleep_seconds(self, "outreach")' in source

    ctx_low = _make_profile_ctx("low_memory")
    ctx_agg = _make_profile_ctx("low_memory_aggressive")
    assert series_panels.get_series_resource_limits(ctx_low)["world_loop_idle_s"] == 180.0
    assert series_panels.get_series_resource_limits(ctx_agg)["world_loop_idle_s"] == 300.0


def test_worldbook_store_no_permanent_shadow_copy_and_disk_rollback(tmp_path):
    path = tmp_path / "worldbook.json"
    store = WorldBookStore(str(path))
    assert not hasattr(store, "_committed")
    store.upsert_book(WorldBook(id="b1", name="Committed"))
    with patch(
        "astrbot_plugin_dynamics_world.world.core.store.os.replace",
        side_effect=OSError("disk full"),
    ):
        with pytest.raises(OSError, match="worldbook_save_failed"):
            store.upsert_book(WorldBook(id="b2", name="Uncommitted"))
    assert store.get_book("b2") is None
    assert store.get_book("b1") is not None
    assert store.get_book("b1").name == "Committed"
