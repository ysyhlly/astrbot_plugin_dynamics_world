"""Wave 1 optimization regressions for astrbot_plugin_dynamics_world."""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sqlite3
from types import SimpleNamespace as NS

import pytest

from test_spatial import GLOBAL, state
from test_world_integration import UMO, make_plugin, seed
from astrbot_plugin_dynamics_world import world_stream as stream
from astrbot_plugin_dynamics_world.life.core.narrative import _identity
from astrbot_plugin_dynamics_world.weather import EnvironmentService
from astrbot_plugin_dynamics_world.weather_life import WeatherLifeObserver


@pytest.mark.asyncio
async def test_resident_tick_skips_causal_write_when_not_due(tmp_path, monkeypatch):
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
        engine = plugin.life.narrative
        scope = engine._global_scope()
        now = 1_800_000_000.0
        monkeypatch.setattr(engine, "clock", lambda: now)

        writes = 0

        def count_write():
            nonlocal writes
            writes += 1

        engine.on_db_write = count_write

        # Prime resident_tick maintenance timestamp.
        with engine._db(notify=False) as db:
            db.execute(
                "INSERT INTO maintenance VALUES(?,'resident_tick',?) "
                "ON CONFLICT(identity,kind) DO UPDATE SET last=excluded.last",
                (_identity(scope), now - 10),
            )

        res = await plugin.life.residents.tick()
        assert res["status"] == "not_due"
        assert writes == 0

        # When paused, tick also returns immediately without writing causal doc.
        await engine.set_paused(True)
        writes = 0
        res_paused = await plugin.life.residents.tick()
        assert res_paused["status"] == "paused"
        assert writes == 0
    finally:
        await plugin.terminate()


@pytest.mark.asyncio
async def test_idle_ticks_emit_zero_db_writes(tmp_path, monkeypatch):
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
        engine = plugin.life.narrative
        scope = engine._global_scope()
        clock_now = [1_800_000_000.0]
        monkeypatch.setattr(engine, "clock", lambda: clock_now[0])

        # Setup initial life/causal/weather state.
        engine.environment = EnvironmentService(engine)
        state(engine, GLOBAL)
        with engine._db(notify=False) as db:
            db.execute(
                "INSERT OR REPLACE INTO maintenance VALUES(?,'hourly',?)",
                (_identity(scope), clock_now[0]),
            )
            db.execute(
                "INSERT OR REPLACE INTO maintenance VALUES(?,'background',?)",
                (_identity(scope), clock_now[0]),
            )

        # Warm up initial causal/weather_life/scene/queue-compaction records.
        await engine.tick(now=clock_now[0])
        clock_now[0] += 30
        await engine.tick(now=clock_now[0])
        writes = 0

        def count_write():
            nonlocal writes
            writes += 1

        engine.on_db_write = count_write

        # Subsequent 30s idle ticks (spanning >120s so ecology/weather intervals cross 72s) must not write DB.
        for _ in range(5):
            clock_now[0] += 30
            await engine.tick(now=clock_now[0])
        assert writes == 0

        # WeatherLifeObserver idle poll with stable environment writes nothing either.
        observer = WeatherLifeObserver(engine.environment)
        writes = 0
        clock_now[0] += 30
        with engine._db() as db:
            assert observer.poll(db, GLOBAL, clock_now[0]) is None
        assert writes == 0
    finally:
        await plugin.terminate()


@pytest.mark.asyncio
async def test_projection_releases_write_lock_before_companions_and_uses_public_summary(
    tmp_path, monkeypatch
):
    plugin, entries, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
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

        class PublicVisualStub:
            def get_dynamics_capabilities(self):
                return {"schema_version": 1, "ready": True, "enabled": True}

            def get_dynamics_summary(self, umo=""):
                # Verify SQLite write lock is NOT held when reading companion summaries.
                probe = sqlite3.connect(plugin.life.narrative.path, timeout=0.05)
                try:
                    probe.execute("BEGIN IMMEDIATE")
                    probe.rollback()
                finally:
                    probe.close()
                return {
                    "characters": 2,
                    "running": 1,
                    "recent": 3,
                    "summary": "公开摘要 · 角色档案 2 个",
                }

        entries.append(
            NS(
                name="astrbot_plugin_visual_media",
                activated=True,
                star_cls=PublicVisualStub(),
            )
        )
        # Missing summary method degrades safely without crashing or reading private attrs.
        entries.append(
            NS(
                name="astrbot_plugin_chat_dynamics",
                activated=True,
                star_cls=NS(
                    get_dynamics_capabilities=lambda: {
                        "schema_version": 1,
                        "ready": True,
                        "enabled": True,
                    }
                ),
            )
        )

        _, payload = await stream.assemble_world_payload(plugin.web, UMO)
        assert payload["companions"]["visual"]["characters"] == 2
        assert payload["companions"]["visual"]["running"] == 1
        assert payload["companions"]["visual"]["summary"] == "公开摘要 · 角色档案 2 个"
        assert payload["companions"]["chat"]["installed"] is True
        assert payload["companions"]["chat"]["ready"] is True
    finally:
        await plugin.terminate()


@pytest.mark.asyncio
async def test_world_public_reference_and_summary_apis(tmp_path, monkeypatch):
    plugin, _, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    try:
        seed(plugin)
        metadata = (Path(__file__).parents[1] / "metadata.yaml").read_text(encoding="utf-8")
        assert f'version: {plugin.get_dynamics_capabilities()["version"]}' in metadata.splitlines()
        ref_dir = plugin.get_reference_assets_directory()
        assert Path(ref_dir).resolve() == (plugin.data_dir / "visual-assets").resolve()
        summary = plugin.get_dynamics_summary(UMO)
        assert summary["ready"] is True
        assert summary["card_count"] == 1
        assert summary["visual_assets_dir"] == ref_dir
    finally:
        await plugin.terminate()


def test_build_release_accepts_sdk_logger_and_prunes_assets(tmp_path):
    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location(
        "world_build_wave1", root / "build_release.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    pkg = tmp_path / "plugin"
    (pkg / "life/core").mkdir(parents=True)
    (pkg / "life/core/narrative.py").write_text(
        'from astrbot.api import logger\nlogger.debug("snapshot ready")\n',
        encoding="utf-8",
    )
    res = mod.build(pkg, tmp_path / "ok.zip")
    assert res["files"] == 1

    # Pruned redundant dead cabin3d.js & non-zh/en Azgaar locale chunks, keeping zh/en.
    assert not (root / "pages/world/cabin3d.js").exists()
    azgaar = root / "vendor/azgaar"
    assert (azgaar / "en-BpPoOois.js").is_file()
    assert (azgaar / "zh-r7nepuD_.js").is_file()
    assert (azgaar / "zh-TW-DksifhB6.js").is_file()
    assert not (azgaar / "ja-BqMqXWtj.js").exists()
    assert not (azgaar / "hi-Ci9XUuxp.js").exists()
