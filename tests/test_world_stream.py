"""World panel projections keep I/O off the loop and respect live bindings."""

import asyncio
import copy
import json
import sqlite3
from contextlib import closing
from threading import Event, get_ident

import pytest
import pytest_asyncio

from astrbot_plugin_dynamics_world import world_stream as stream
from astrbot_plugin_dynamics_world.world.core.store import SESSION_CARD_NONE
from test_spatial import document
from test_world_integration import UMO, make_plugin, seed


@pytest_asyncio.fixture
async def panel(tmp_path, monkeypatch):
    plugin, _, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    try:
        tasks = (
            plugin.life._resident_task,
            plugin.life._narrative_task,
            plugin.life._outreach_task,
        )
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        seed(plugin)
        yield plugin
    finally:
        await plugin.terminate()


def data(frame):
    assert frame.startswith("data: ")
    return json.loads(frame[6:])


@pytest.mark.asyncio
async def test_busy_sqlite_keeps_loop_responsive_and_disconnect_keeps_other_waiter(
    panel, monkeypatch
):
    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    worker_threads = []
    original = stream._read_world_projection

    def read(*args):
        worker_threads.append(get_ident())
        loop.call_soon_threadsafe(started.set)
        return original(*args)

    monkeypatch.setattr(stream, "_read_world_projection", read)
    first = (await stream.open_sse_stream(panel.web, UMO)).body_iterator
    second = (await stream.open_sse_stream(panel.web, UMO)).body_iterator
    database = sqlite3.connect(panel.life.narrative.path)
    database.execute("BEGIN IMMEDIATE")
    pending = [
        asyncio.create_task(anext(first)),
        asyncio.create_task(anext(second)),
    ]
    try:
        await asyncio.wait_for(started.wait(), 2)
        await asyncio.sleep(0.02)
        assert len(worker_threads) == 1
        assert worker_threads[0] != get_ident()
        assert not pending[1].done()
        pending[0].cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending[0]
    finally:
        database.rollback()
        database.close()
    try:
        payload = data(await asyncio.wait_for(pending[1], 3))
        assert payload["character"]["id"] == "card"
        assert len(worker_threads) == 1
        # A later request starts a new read even with the same revision token.
        await stream.assemble_world_payload(
            panel.web, UMO, known_revisions=payload["revisions"]
        )
        assert len(worker_threads) == 2
    finally:
        await asyncio.gather(*pending, return_exceptions=True)
        await first.aclose()
        await second.aclose()


@pytest.mark.asyncio
async def test_world_commit_wakes_stream_and_keeps_per_client_revisions(
    panel, monkeypatch
):
    engine = panel.life.narrative
    monkeypatch.setattr(engine, "clock", lambda: 1_800_000_000.0)
    first = (await stream.open_sse_stream(panel.web, UMO)).body_iterator
    full = data(await anext(first))
    second = (
        await stream.open_sse_stream(
            panel.web, UMO, known_raw=json.dumps(full["revisions"])
        )
    ).body_iterator
    try:
        initial_generation = panel.web.bus.generation
        assert data(await anext(second))["unchanged"]
        assert panel.web.bus.generation == initial_generation
        scope, _ = await panel.web.scope(UMO)
        engine.spatial.install(scope, document())
        assert panel.web.bus.generation == initial_generation + 1
        fresh = await stream.assemble_world_payload(panel.web, UMO)
        third = (
            await stream.open_sse_stream(
                panel.web, UMO, known_raw=json.dumps(fresh[1]["revisions"])
            )
        ).body_iterator
        try:
            old_frame, older_frame, current_frame = await asyncio.wait_for(
                asyncio.gather(anext(first), anext(second), anext(third)), 3
            )
            for frame in (old_frame, older_frame):
                payload = data(frame)
                assert "map" in payload["changed_domains"]
                assert payload["map"]["world_id"] == fresh[1]["map"]["world_id"]
            assert data(current_frame)["unchanged"]
        finally:
            await third.aclose()
    finally:
        await first.aclose()
        await second.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["unbind", "instance", "services", "publish"])
async def test_pending_projection_is_revalidated_before_sending(
    panel, monkeypatch, change
):
    loop = asyncio.get_running_loop()
    projected = asyncio.Event()
    pause = Event()
    original_read = stream._read_world_projection
    original_scope = panel.web.scope
    original_world = panel.world
    instance = None
    calls = 0

    async def scope(umo):
        resolved, character = await original_scope(umo)
        if instance is not None:
            resolved = {**resolved, "instance_id": instance}
        return resolved, character

    def read(*args):
        nonlocal calls
        calls += 1
        generation, payload = original_read(*args)
        payload["test_projection"] = calls
        if calls == 1:
            loop.call_soon_threadsafe(projected.set)
            assert pause.wait(2)
        return generation, payload

    monkeypatch.setattr(panel.web, "scope", scope)
    monkeypatch.setattr(stream, "_read_world_projection", read)
    body = (await stream.open_sse_stream(panel.web, UMO)).body_iterator
    pending = asyncio.create_task(anext(body))
    try:
        await asyncio.wait_for(projected.wait(), 2)
        if change == "unbind":
            panel.world.store.update_session(UMO, card_id=SESSION_CARD_NONE)
        elif change == "instance":
            instance = "new-instance"
        elif change == "services":
            panel.world = copy.copy(original_world)
        else:
            panel.web.bus.notify()
        pause.set()
        payload = data(await asyncio.wait_for(pending, 3))
        if change in {"unbind", "services"}:
            assert payload == {"reset": True}
            assert calls == 1
        else:
            assert payload["test_projection"] == 2
            assert calls == 2
    finally:
        panel.world = original_world
        pause.set()
        await asyncio.gather(pending, return_exceptions=True)
        await body.aclose()


@pytest.mark.asyncio
async def test_different_sessions_of_same_character_use_separate_reads(
    panel, monkeypatch
):
    first_projected = asyncio.Event()
    release_first = Event()
    loop = asyncio.get_running_loop()
    original_read = stream._read_world_projection

    def read(api, services, scope, *args):
        generation, payload = original_read(api, services, scope, *args)
        payload["test_scope"] = scope["umo"]
        if scope["umo"] == UMO:
            loop.call_soon_threadsafe(first_projected.set)
            assert release_first.wait(2)
        return generation, payload

    monkeypatch.setattr(stream, "_read_world_projection", read)
    other_umo = "qq:GroupMessage:other"
    first = asyncio.create_task(stream.assemble_world_payload(panel.web, UMO))
    try:
        await asyncio.wait_for(first_projected.wait(), 2)
        other = asyncio.create_task(
            stream.assemble_world_payload(panel.web, other_umo)
        )
        await asyncio.sleep(0)
        release_first.set()
        [(first_identity, first_payload), (other_identity, other_payload)] = (
            await asyncio.wait_for(asyncio.gather(first, other), 3)
        )
        assert first_identity == other_identity
        assert first_payload["test_scope"] == UMO
        assert other_payload["test_scope"] == other_umo
    finally:
        release_first.set()
        await asyncio.gather(first, return_exceptions=True)


@pytest.mark.asyncio
async def test_unchanged_world_heartbeat_uses_existing_interval(panel, monkeypatch):
    monkeypatch.setattr(panel.life.narrative, "clock", lambda: 1_800_000_000.0)
    intervals = []

    async def wait(_subscriber, timeout):
        intervals.append(timeout)
        return False

    monkeypatch.setattr(stream._Subscriber, "wait", wait)
    body = (await stream.open_sse_stream(panel.web, UMO)).body_iterator
    try:
        data(await anext(body))
        assert await anext(body) == ": keepalive 1800000000\n\n"
        assert intervals == [18.0]
    finally:
        await body.aclose()


@pytest.mark.asyncio
async def test_generation_races_keep_stream_open_and_preserve_known_revisions(
    panel, monkeypatch
):
    engine = panel.life.narrative
    original_read = stream._read_world_projection
    races_remaining = 0

    def read(api, *args):
        nonlocal races_remaining
        generation, projection = original_read(api, *args)
        if races_remaining:
            races_remaining -= 1
            api.bus.notify("another-identity")
        return generation, projection

    monkeypatch.setattr(stream, "_read_world_projection", read)
    body = (await stream.open_sse_stream(panel.web, UMO)).body_iterator
    try:
        first = data(await anext(body))
        assert first["map"] is None
        scope, _ = await panel.web.scope(UMO)
        engine.spatial.install(scope, document())
        races_remaining = 3
        assert (await asyncio.wait_for(anext(body), 3)).startswith(": keepalive ")
        assert races_remaining == 0
        assert panel.web.bus.subscriber_count == 1
        recovered = data(await asyncio.wait_for(anext(body), 3))
        assert recovered["delta"]
        assert "map" in recovered["changed_domains"]
        assert recovered["revisions"]["binding"] == first["revisions"]["binding"]
    finally:
        await body.aclose()


@pytest.mark.asyncio
async def test_saturated_projection_retries_with_backoff_on_same_connection(
    panel, monkeypatch
):
    pool = panel.web.bus._projection_io
    engine = panel.life.narrative
    loop = asyncio.get_running_loop()
    entered = asyncio.Event()
    attempted_three = asyncio.Event()
    release = Event()
    original_run = pool.run
    attempts = []

    def hold_worker():
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(4)

    async def track_projection(call, *args, **kwargs):
        if call is stream._read_world_projection:
            attempts.append(loop.time())
            if len(attempts) == 3:
                attempted_three.set()
        return await original_run(call, *args, **kwargs)

    body = (await stream.open_sse_stream(panel.web, UMO)).body_iterator
    first = data(await anext(body))
    monkeypatch.setattr(pool, "_max_waiters", 1)
    monkeypatch.setattr(pool, "run", track_projection)
    busy = asyncio.create_task(pool.run(hold_worker))
    pending = None
    try:
        await asyncio.wait_for(entered.wait(), 2)
        scope, _ = await panel.web.scope(UMO)
        engine.spatial.install(scope, document())
        assert (await asyncio.wait_for(anext(body), 3)).startswith(": keepalive ")
        pending = asyncio.create_task(anext(body))
        await asyncio.wait_for(attempted_three.wait(), 3)
        assert attempts[1] - attempts[0] >= 0.15
        assert attempts[2] - attempts[1] >= 0.35
        assert not pending.done()
        assert panel.web.bus.subscriber_count == 1
        release.set()
        await busy
        recovered = data(await asyncio.wait_for(pending, 3))
        assert recovered["delta"]
        assert "map" in recovered["changed_domains"]
        assert recovered["revisions"]["binding"] == first["revisions"]["binding"]
    finally:
        release.set()
        if pending is not None and not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        await asyncio.gather(busy, return_exceptions=True)
        await body.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True], ids=["reopen", "cancel"])
async def test_apply_imported_settings_waits_for_panel_transaction_before_reopen(
    panel, monkeypatch, cancel
):
    bus = panel.web.bus
    original_pool = bus._projection_io
    engine = panel.life.narrative
    loop = asyncio.get_running_loop()
    entered, reopened = asyncio.Event(), asyncio.Event()
    release = Event()
    original_snapshot = engine._snapshot
    original_open = panel._open_services
    previous_config = dict(panel.host_config)
    previous_saved_config = getattr(panel.host_config, "saved", None)

    def snapshot(db, scope, now):
        assert db.in_transaction
        loop.call_soon_threadsafe(entered.set)
        assert release.wait(5)
        result = original_snapshot(db, scope, now)
        db.execute("INSERT INTO metadata VALUES('test_old_panel_worker', 'committed')")
        return result

    async def open_services():
        with closing(sqlite3.connect(engine.path)) as db:
            assert db.execute(
                "SELECT value FROM metadata WHERE key='test_old_panel_worker'"
            ).fetchone() == ("committed",)
        assert bus._projection_io is not original_pool
        await original_open()
        reopened.set()

    monkeypatch.setattr(engine, "_snapshot", snapshot)
    monkeypatch.setattr(panel, "_open_services", open_services)
    body = (await stream.open_sse_stream(panel.web, UMO)).body_iterator
    pending = asyncio.create_task(anext(body))
    applying = None
    try:
        await asyncio.wait_for(entered.wait(), 2)
        panel.config["runtime_enabled"] = False
        (panel.data_dir / "migration-settings.json").write_text(
            '{"persona_id": "p"}', encoding="utf-8"
        )
        applying = asyncio.create_task(panel.apply_imported_settings())
        await asyncio.sleep(0.02)
        assert panel._migrating
        assert not applying.done()
        assert not reopened.is_set()
        assert panel.life.narrative is engine
        if cancel:
            for cancellation_count in (1, 2):
                applying.cancel()
                await asyncio.sleep(0)
                assert applying.cancelling() == cancellation_count
                assert panel._migrating
                assert not applying.done()
                assert not reopened.is_set()
                assert panel.life.narrative is engine
                assert dict(panel.host_config) == previous_config
                assert getattr(panel.host_config, "saved", None) == previous_saved_config
            monkeypatch.setattr(engine, "_snapshot", original_snapshot)
        release.set()
        if cancel:
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(applying, 8)
            assert not reopened.is_set()
            assert panel.life.narrative is engine
            assert dict(panel.host_config) == previous_config
            assert getattr(panel.host_config, "saved", None) == previous_saved_config
        else:
            assert (await asyncio.wait_for(applying, 8))["runtime_enabled"] is False
            assert reopened.is_set()
            assert panel.life.narrative is not engine
        assert panel._ready and not panel._migrating
        assert panel.web.bus is bus
        assert bus._projection_io is not original_pool
        try:
            stale_frame = await asyncio.wait_for(pending, 3)
        except StopAsyncIteration:
            pass
        else:
            if not cancel:
                assert data(stale_frame) == {"reset": True}
        _, current = await stream.assemble_world_payload(panel.web, UMO)
        assert current["character"]["id"] == "card"
    finally:
        release.set()
        tasks = (pending,) if applying is None else (pending, applying)
        await asyncio.gather(*tasks, return_exceptions=True)
        await body.aclose()
