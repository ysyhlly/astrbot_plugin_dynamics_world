"""Behavior regressions using a deterministic provider and an injectable clock."""
from __future__ import annotations

import asyncio
import copy
import datetime as dt
import importlib.util
import json
import sqlite3
import tempfile
import threading
import unittest
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("dls_narrative_under_test", Path(__file__).parents[1] / "life" / "core" / "narrative.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
NarrativeEngine, CHINA = MODULE.NarrativeEngine, MODULE.CHINA


class NarrativeTests(unittest.IsolatedAsyncioTestCase):
    """Exercise persistence, truthful evidence and real concurrency boundaries."""

    def setUp(self):
        scratch = Path(__file__).parent / ".tmp"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.path = Path(self.temp.name) / "narrative.sqlite3"
        self.now = dt.datetime(2026, 10, 10, 10, tzinfo=CHINA).timestamp()
        self.scope = {"platform": "qq", "umo": "qq:GroupMessage:a", "persona_id": "anan", "instance_id": "anan"}
        self.other = dict(self.scope, umo="qq:GroupMessage:b")
        self.config = {"mode": "narrative", "narrative_sessions": [self.scope["umo"], self.other["umo"]], "persona_id": "anan"}
        self.requests = []
        self.response = {"no_change": True}

        async def model(request):
            self.requests.append(request)
            return copy.deepcopy(self.response)

        self.model = model
        self.engine = NarrativeEngine(self.path, self.config, model, lambda: self.now)

    async def asyncTearDown(self):
        await self.engine.close()
        self.temp.cleanup()

    def event(self, event_id="e1", *, scope=None, kind="chat.message", text="你好", fact_kind="observation", data=None):
        return {"event_id": event_id, "type": kind, "occurred_at": self.now, "received_at": self.now,
                "scope": scope or self.scope, "text": text, "fact_kind": fact_kind, "data": data or {}}

    def query(self, sql, args=()):
        from contextlib import closing
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute(sql, args).fetchall()

    async def test_default_legacy_and_empty_allowlist_are_unmanaged(self):
        self.config["mode"] = "legacy"
        self.assertFalse((await self.engine.get_snapshot(self.scope))["managed"])
        self.config["mode"] = "narrative"
        self.config["narrative_sessions"] = []
        self.assertEqual((await self.engine.tick())["status"], "disabled")

    async def test_explicit_all_groups_only_enables_group_scopes_and_matching_persona(self):
        self.config["narrative_sessions"] = []
        self.config["narrative_all_groups"] = True
        new_scope = dict(self.scope, umo="other-instance:GroupMessage:new-room")
        self.assertTrue((await self.engine.get_snapshot(new_scope))["managed"])
        for bad in [dict(new_scope, umo="other-instance:FriendMessage:user"),
                    dict(new_scope, umo="new-room"), dict(new_scope, persona_id="other")]:
            self.assertFalse((await self.engine.get_snapshot(bad))["managed"])
        await self.engine.ingest_events([self.event("new", scope=new_scope)])
        await self.engine.tick()
        self.assertEqual(self.query("SELECT status FROM events WHERE event_id='new'"), [("processed",)])

    async def test_all_groups_defaults_false_and_cannot_override_legacy(self):
        self.config["narrative_sessions"] = []
        self.assertFalse((await self.engine.get_snapshot(self.scope))["managed"])
        self.config["narrative_all_groups"] = True
        self.config["mode"] = "legacy"
        self.assertFalse((await self.engine.get_snapshot(self.scope))["managed"])

    async def test_full_umo_and_persona_match_are_required(self):
        for scope in [dict(self.scope, umo="other:GroupMessage:a"), dict(self.scope, persona_id="other"), dict(self.scope, umo="a")]:
            self.assertFalse((await self.engine.get_snapshot(scope))["managed"])

    async def test_snapshot_never_calls_model_and_stale_is_unknown(self):
        snapshot = await self.engine.get_snapshot(self.scope)
        self.assertEqual(snapshot["availability"], "unknown")
        self.assertEqual(snapshot["activity"], "未知")
        self.assertEqual(self.requests, [])

    async def test_snapshot_runs_while_default_executor_is_busy(self):
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
        occupied = asyncio.Event()
        release = threading.Event()

        def occupy_default():
            loop.call_soon_threadsafe(occupied.set)
            release.wait(5)

        blocker = loop.run_in_executor(None, occupy_default)
        try:
            await asyncio.wait_for(occupied.wait(), 2)
            snapshot = await asyncio.wait_for(self.engine.get_snapshot(self.scope), 2)
            self.assertTrue(snapshot["managed"])
            self.assertFalse(blocker.done())
        finally:
            release.set()
            await blocker

    async def test_snapshot_shares_only_unfinished_work_for_the_full_scope(self):
        loop = asyncio.get_running_loop()
        entered = asyncio.Event()
        release = threading.Event()
        reads = []
        read = self.engine._read_snapshot

        def delayed_read(scope):
            reads.append(scope)
            loop.call_soon_threadsafe(entered.set)
            if not release.wait(5):
                raise AssertionError("snapshot worker did not resume")
            return read(scope)

        self.engine._read_snapshot = delayed_read
        scopes = [
            self.scope, self.scope, self.other,
            dict(self.scope, platform="another"), dict(self.scope, instance_id="another"),
        ]
        tasks = [asyncio.create_task(self.engine.get_snapshot(scope)) for scope in scopes]
        try:
            await asyncio.wait_for(entered.wait(), 2)
            await asyncio.sleep(0)
        finally:
            release.set()
        snapshots = await asyncio.gather(*tasks)
        for scope, snapshot in zip(scopes, snapshots):
            self.assertEqual(snapshot["scope"], MODULE.normalize_scope(scope))
        self.assertEqual(
            Counter(tuple(scope.values()) for scope in reads),
            Counter(tuple(MODULE.normalize_scope(scope).values()) for scope in scopes[1:]),
        )
        snapshots[0]["humanlike"]["goals"].append("caller-private")
        self.assertEqual(snapshots[1]["humanlike"]["goals"], [])
        await self.engine.get_snapshot(self.scope)
        self.assertEqual(len(reads), 5)

    async def test_cancelled_snapshot_caller_does_not_duplicate_running_sqlite_work(self):
        loop = asyncio.get_running_loop()
        entered = asyncio.Event()
        release = threading.Event()
        reads = []
        read = self.engine._read_snapshot

        def delayed_read(scope):
            reads.append(scope)
            loop.call_soon_threadsafe(entered.set)
            if not release.wait(5):
                raise AssertionError("snapshot worker did not resume")
            return read(scope)

        self.engine._read_snapshot = delayed_read
        request = asyncio.create_task(self.engine.get_snapshot(self.scope))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            request.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await request
            next_request = asyncio.create_task(self.engine.get_snapshot(self.scope))
            await asyncio.sleep(0)
        finally:
            release.set()
        self.assertTrue((await next_request)["managed"])
        self.assertEqual(len(reads), 1)

    async def test_snapshot_rechecks_allowlist_and_owner_before_delivering(self):
        loop = asyncio.get_running_loop()
        read = self.engine._read_snapshot
        allowed = self.config["narrative_sessions"]
        owner_active = True
        self.engine._owner_active = lambda: owner_active
        expected = {"schema_version": 1, "managed": False, "scope": MODULE.normalize_scope(self.scope)}

        for revoke in ("allowlist", "owner"):
            with self.subTest(revoke=revoke):
                projected = asyncio.Event()
                release = threading.Event()

                def delayed_read(scope):
                    result = read(scope)
                    loop.call_soon_threadsafe(projected.set)
                    if not release.wait(5):
                        raise AssertionError("snapshot worker did not resume")
                    return result

                self.engine._read_snapshot = delayed_read
                task = asyncio.create_task(self.engine.get_snapshot(self.scope))
                try:
                    await asyncio.wait_for(projected.wait(), 2)
                    if revoke == "allowlist":
                        self.config["narrative_sessions"] = []
                    else:
                        owner_active = False
                    self.assertEqual(await self.engine.get_snapshot(self.scope), expected)
                finally:
                    release.set()
                self.assertEqual(await task, expected)
                self.config["narrative_sessions"] = allowed
                owner_active = True

    async def test_snapshot_close_drains_running_and_drops_queued_projections(self):
        await self.engine._snapshot_io.close()
        self.engine._snapshot_io = MODULE.WorldIO(max_workers=1)
        loop = asyncio.get_running_loop()
        projected = asyncio.Event()
        release = threading.Event()
        reads = []
        read = self.engine._read_snapshot

        def delayed_read(scope):
            reads.append(scope)
            result = read(scope)
            loop.call_soon_threadsafe(projected.set)
            if not release.wait(5):
                raise AssertionError("snapshot worker did not resume")
            return result

        self.engine._read_snapshot = delayed_read
        running = asyncio.create_task(self.engine.get_snapshot(self.scope))
        try:
            await asyncio.wait_for(projected.wait(), 2)
            queued = asyncio.create_task(self.engine.get_snapshot(self.other))
            await asyncio.sleep(0)
            closed = asyncio.create_task(self.engine.close())
            queued_result = await asyncio.wait_for(queued, 2)
            self.assertEqual(set(queued_result), {"schema_version", "managed", "scope"})
            self.assertFalse(queued_result["managed"])
            self.assertFalse(closed.done())
        finally:
            release.set()
        await closed
        running_result = await running
        self.assertEqual(set(running_result), {"schema_version", "managed", "scope"})
        self.assertFalse(running_result["managed"])
        self.assertEqual(reads, [MODULE.normalize_scope(self.scope)])

    async def test_world_io_bounds_waiters_and_drops_unobserved_queued_work(self):
        pool = MODULE.WorldIO(max_workers=1, max_pending=1, max_waiters=3)
        loop = asyncio.get_running_loop()
        entered = asyncio.Event()
        release = threading.Event()

        def block():
            loop.call_soon_threadsafe(entered.set)
            if not release.wait(5):
                raise AssertionError("World worker did not resume")

        def unexpected_work():
            self.fail("cancelled queued work ran")

        running = asyncio.create_task(pool.run(block, key="running"))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            waiting = asyncio.create_task(pool.run(unexpected_work, key="waiting"))
            await asyncio.sleep(0)
            with self.assertRaisesRegex(MODULE._io_mod.WorldIOBusy, "queue is full"):
                await pool.run(unexpected_work, key="queue is full")
            joined = asyncio.create_task(pool.run(unexpected_work, key="running"))
            await asyncio.sleep(0)
            with self.assertRaisesRegex(MODULE._io_mod.WorldIOBusy, "waiter limit"):
                await pool.run(block, key="running")
            waiting.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await waiting
            next_waiting = asyncio.create_task(pool.run(lambda: "next", key="next"))
            await asyncio.sleep(0)
            release.set()
            self.assertEqual(await next_waiting, "next")
            await asyncio.gather(running, joined)
        finally:
            release.set()
            await pool.close()

    async def test_world_io_submission_failure_does_not_strand_shutdown(self):
        pool = MODULE.WorldIO()
        with patch.object(pool._executor, "submit", side_effect=RuntimeError):
            with self.assertRaises(MODULE._io_mod.WorldIOBusy):
                await pool.run(lambda: None)
        with self.assertRaises(MODULE._io_mod.WorldIOBusy):
            await pool.run(lambda: None)
        await asyncio.wait_for(pool.close(), 2)

    async def test_queued_snapshot_of_disabled_owner_skips_sqlite(self):
        await self.engine._snapshot_io.close()
        self.engine._snapshot_io = MODULE.WorldIO()
        loop = asyncio.get_running_loop()
        entered = asyncio.Event()
        release = threading.Event()
        owner_active = True
        self.engine._owner_active = lambda: owner_active

        def occupy_worker():
            loop.call_soon_threadsafe(entered.set)
            if not release.wait(5):
                raise AssertionError("snapshot worker did not resume")

        blocker = asyncio.create_task(self.engine._snapshot_io.run(occupy_worker))
        with patch.object(
            self.engine, "_db", side_effect=AssertionError("unexpected SQLite access")
        ) as open_db:
            try:
                await asyncio.wait_for(entered.wait(), 2)
                queued = asyncio.create_task(self.engine.get_snapshot(self.scope))
                await asyncio.sleep(0)
                owner_active = False
            finally:
                release.set()
                await blocker
            self.assertFalse((await asyncio.wait_for(queued, 2))["managed"])
            open_db.assert_not_called()

    async def test_snapshot_rechecks_permissions_after_waiting_for_sqlite_writer(self):
        loop = asyncio.get_running_loop()
        owner_active = True
        self.engine._owner_active = lambda: owner_active
        raw_db = self.engine._db
        read_projection = self.engine._snapshot
        scope = MODULE.normalize_scope(self.scope)
        notifications = []
        self.engine.on_db_write = lambda: notifications.append("committed")

        def project(db, scope, now):
            db.execute("INSERT INTO metadata VALUES('snapshot_effect','settled')")
            return read_projection(db, scope, now)

        def observe_begin(statement):
            if statement == "BEGIN IMMEDIATE":
                loop.call_soon_threadsafe(begun.set)

        @contextmanager
        def tracked_db(**kwargs):
            with raw_db(**kwargs) as db:
                db.set_trace_callback(observe_begin)
                yield db

        self.engine._snapshot = project
        self.engine._db = tracked_db
        for revoke in ("owner", "allowlist"):
            with self.subTest(revoke=revoke):
                begun = asyncio.Event()
                with closing(sqlite3.connect(self.path)) as writer:
                    writer.execute("BEGIN IMMEDIATE")
                    request = asyncio.create_task(self.engine.get_snapshot(scope))
                    await asyncio.wait_for(begun.wait(), 2)
                    self.assertFalse(request.done())
                    if revoke == "owner":
                        owner_active = False
                    else:
                        self.config["narrative_sessions"] = []
                    writer.commit()
                    self.assertEqual(
                        await asyncio.wait_for(request, 2),
                        {"schema_version": 1, "managed": False, "scope": scope},
                    )
                self.assertEqual(self.query("SELECT * FROM lives"), [])
                self.assertEqual(self.query("SELECT * FROM scopes"), [])
                self.assertEqual(self.query("SELECT * FROM metadata WHERE key='snapshot_effect'"), [])
                self.assertEqual(notifications, [])
                owner_active = True
                self.config["narrative_sessions"] = [self.scope["umo"], self.other["umo"]]

    async def test_snapshot_rolls_back_if_owner_is_disabled_during_settlement(self):
        loop = asyncio.get_running_loop()
        owner_active = True
        self.engine._owner_active = lambda: owner_active
        read_projection = self.engine._snapshot
        projected = asyncio.Event()
        release = threading.Event()
        notifications = []
        self.engine.on_db_write = lambda: notifications.append("committed")

        def project(db, scope, now):
            result = read_projection(db, scope, now)
            db.execute("INSERT INTO metadata VALUES('snapshot_effect','settled')")
            loop.call_soon_threadsafe(projected.set)
            if not release.wait(5):
                raise AssertionError("snapshot worker did not resume")
            return result

        self.engine._snapshot = project
        request = asyncio.create_task(self.engine.get_snapshot(self.scope))
        try:
            await asyncio.wait_for(projected.wait(), 2)
            owner_active = False
        finally:
            release.set()
        self.assertFalse((await request)["managed"])
        self.assertEqual(self.query("SELECT * FROM lives"), [])
        self.assertEqual(self.query("SELECT * FROM scopes"), [])
        self.assertEqual(self.query("SELECT * FROM metadata WHERE key='snapshot_effect'"), [])
        self.assertEqual(notifications, [])

    async def test_snapshot_admitted_after_a_committed_pause_reads_the_pause(self):
        loop = asyncio.get_running_loop()
        committed = asyncio.Event()
        release = threading.Event()

        def block_write_notification():
            loop.call_soon_threadsafe(committed.set)
            release.wait(5)

        self.engine.on_db_write = block_write_notification
        first = asyncio.create_task(self.engine.get_snapshot(self.scope))
        try:
            await asyncio.wait_for(committed.wait(), 2)
            self.assertFalse(first.done())
            with self.engine._db(notify=False) as db:
                db.execute("INSERT INTO metadata VALUES('paused','true')")
            later = await asyncio.wait_for(self.engine.get_snapshot(self.scope), 2)
            self.assertTrue(later["paused"])
            self.assertFalse(first.done())
        finally:
            release.set()
        self.assertFalse((await first)["paused"])

    async def test_snapshot_reads_committed_state_after_sqlite_writer_releases(self):
        loop = asyncio.get_running_loop()
        entered = asyncio.Event()
        read = self.engine._read_snapshot

        def read_while_locked(scope):
            loop.call_soon_threadsafe(entered.set)
            return read(scope)

        self.engine._read_snapshot = read_while_locked
        scope = MODULE.normalize_scope(self.scope)
        identity = MODULE._identity(scope)
        with closing(sqlite3.connect(self.path)) as writer:
            writer.execute("BEGIN IMMEDIATE")
            self.engine._ensure(writer, scope, self.now)
            row = writer.execute("SELECT state FROM lives WHERE identity=?", (identity,)).fetchone()
            changed = dict(json.loads(row[0]), summary="committed", valid_until=self.now + 300)
            writer.execute("UPDATE lives SET state=? WHERE identity=?", (json.dumps(changed), identity))
            task = asyncio.create_task(self.engine.get_snapshot(scope))
            await asyncio.wait_for(entered.wait(), 2)
            await asyncio.sleep(0.05)
            self.assertFalse(task.done())
            writer.commit()
            self.assertEqual((await asyncio.wait_for(task, 2))["summary"], "committed")

    async def test_snapshot_rolls_back_scope_initialization_if_projection_fails(self):
        notifications = []
        self.engine.on_db_write = lambda: notifications.append("commit")

        def fail_after_ensure(db, scope, now):
            self.engine._ensure(db, scope, now)
            raise RuntimeError("projection failed")

        self.engine._snapshot = fail_after_ensure
        with self.assertRaisesRegex(RuntimeError, "projection failed"):
            await self.engine.get_snapshot(self.scope)
        self.assertEqual(self.query("SELECT COUNT(*) FROM lives"), [(0,)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM scopes"), [(0,)])
        self.assertEqual(notifications, [])

    async def test_db_notifies_only_after_committed_rows_and_honors_opt_out(self):
        notifications = []
        self.engine.on_db_write = lambda: notifications.append(
            self.query("SELECT value FROM metadata WHERE key='test_notify'")
        )
        generation = self.engine.peek_context_revision(self.scope)["generation"]
        with self.engine._db() as db:
            db.execute("UPDATE metadata SET value='missed' WHERE key='test_notify'")
        self.assertGreater(self.engine.peek_context_revision(self.scope)["generation"], generation)
        with self.assertRaisesRegex(RuntimeError, "rollback"):
            with self.engine._db() as db:
                db.execute("INSERT INTO metadata VALUES('test_notify','rolled back')")
                raise RuntimeError("rollback")
        with self.engine._db() as db:
            db.execute("INSERT INTO metadata VALUES('test_notify','rolled back')")
            db.rollback()
            db.execute("UPDATE metadata SET value='missed' WHERE key='test_notify'")
        self.assertEqual(notifications, [])
        with self.engine._db() as db:
            db.execute("INSERT INTO metadata VALUES('test_notify','visible')")
        self.assertEqual(notifications, [[("visible",)]])
        with self.engine._db(notify=False) as db:
            db.execute("UPDATE metadata SET value='quiet' WHERE key='test_notify'")
        self.assertEqual(notifications, [[("visible",)]])
        with self.assertRaisesRegex(RuntimeError, "after commit"):
            with self.engine._db() as db:
                db.execute("UPDATE metadata SET value='explicit' WHERE key='test_notify'")
                db.commit()
                raise RuntimeError("after commit")
        self.assertEqual(notifications, [[("visible",)], [("explicit",)]])
        with self.engine._db() as db:
            db.execute("CREATE TABLE notify_parent(id INTEGER PRIMARY KEY)")
            db.execute(
                "CREATE TABLE notify_child(parent INTEGER REFERENCES notify_parent(id)"
                " DEFERRABLE INITIALLY DEFERRED)"
            )
        with self.assertRaises(sqlite3.IntegrityError):
            with self.engine._db() as db:
                db.execute("UPDATE metadata SET value='failed commit' WHERE key='test_notify'")
                db.execute("INSERT INTO notify_child VALUES(1)")
        self.assertEqual(notifications, [[("visible",)], [("explicit",)]])
        self.assertEqual(self.query("SELECT value FROM metadata WHERE key='test_notify'"), [("explicit",)])

    async def test_duplicate_event_id_is_idempotent_and_content_mismatch_rejected(self):
        event = self.event()
        result = await self.engine.ingest_events([event, event])
        self.assertEqual(result["accepted"], ["e1"])
        self.assertEqual(result["duplicate"], ["e1"])
        with self.assertRaises(ValueError):
            await self.engine.ingest_events([dict(event, text="changed")])
        self.assertEqual(self.query("SELECT COUNT(*) FROM events")[0][0], 1)

    async def test_invalid_event_batch_is_atomic(self):
        with self.assertRaises(ValueError):
            await self.engine.ingest_events([self.event(), self.event("broken", fact_kind="confirmed_guess")])
        self.assertEqual(self.query("SELECT COUNT(*) FROM events")[0][0], 0)

    async def test_no_change_processes_queue_without_diary(self):
        result = await self.engine.advance([self.event()])
        self.assertEqual(result["status"], "no_change")
        self.assertEqual(self.query("SELECT status FROM events"), [("processed",)])
        self.assertEqual(self.query("SELECT COUNT(*) FROM diary")[0][0], 0)

    async def test_private_summary_does_not_leak_into_global_or_other_group(self):
        self.response = {"state": {"activity_code": "writing", "activity": "Alice's secret", "summary": "Alice's private message", "subjective_state": "对Alice有疑虑"},
                         "event_impact": "relationship"}
        result = await self.engine.advance([self.event(text="Alice's secret")])
        self.assertEqual(result["status"], "advanced")
        self.assertEqual(result["snapshot"]["summary"], "Alice's private message")
        other = await self.engine.get_snapshot(self.other)
        self.assertEqual(other["activity"], "独自写作")
        self.assertNotIn("Alice", json.dumps(other))
        global_data = self.query("SELECT state FROM lives")[0][0]
        self.assertNotIn("Alice", global_data)
        self.assertNotIn("e1", global_data)

    def wait_retry(self):
        # The current engine persists retry backoff; advance the test clock, not the queue.
        retry = self.query("SELECT MAX(next_retry) FROM events WHERE status='pending'")[0][0]
        if retry:
            self.now = max(self.now, retry + 0.01)

    async def test_concurrent_groups_serialize_without_lost_updates(self):
        first, second = await asyncio.gather(self.engine.advance([self.event("a")]), self.engine.advance([self.event("b", scope=self.other)]))
        # The second scoped event first advances expired global life, adding its own revision.
        self.assertEqual({first["snapshot"]["revision"], second["snapshot"]["revision"]}, {1, 3})
        self.assertEqual(self.query("SELECT COUNT(*) FROM events WHERE event_id IN ('a','b') AND status='processed'")[0][0], 2)
        self.assertEqual((await self.engine.get_snapshot(self.scope))["scope_revision"], 1)
        self.assertEqual((await self.engine.get_snapshot(self.other))["scope_revision"], 1)

    async def test_expected_revision_rejects_stale_and_retains_queued_event(self):
        await self.engine.advance([self.event("a")])
        result = await self.engine.advance([self.event("b")], expected_revision=0)
        self.assertEqual(result["status"], "stale")
        self.assertEqual(self.query("SELECT status FROM events WHERE event_id='b'"), [("pending",)])

    async def test_admin_correction_invalidates_in_flight_model(self):
        entered, release = asyncio.Event(), asyncio.Event()

        async def slow(request):
            entered.set()
            await release.wait()
            return {"state": {"activity_code": "gaming"}}

        self.engine.model = slow
        task = asyncio.create_task(self.engine.advance([self.event()]))
        await entered.wait()
        result = await self.engine.correct_state(self.scope, {"activity_code": "resting"})
        self.assertEqual(result["status"], "corrected")
        release.set()
        late = await task
        self.assertEqual(late["status"], "stale")
        self.assertEqual(late["snapshot"]["activity"], "休息")
        self.assertEqual(self.query("SELECT COUNT(*) FROM diary")[0][0], 1)

    async def test_timeout_retains_queue_and_state(self):
        async def slow(request):
            await asyncio.sleep(10)

        self.config["narrative_timeout_seconds"] = 1
        self.engine.model = slow
        result = await self.engine.advance([self.event()])
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["snapshot"]["revision"], 0)
        self.assertEqual(self.query("SELECT status FROM events"), [("pending",)])

    async def test_cancelled_call_cannot_commit_late_result(self):
        entered = asyncio.Event()

        async def slow(request):
            entered.set()
            await asyncio.Event().wait()

        self.engine.model = slow
        task = asyncio.create_task(self.engine.advance([self.event()]))
        await entered.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(self.query("SELECT revision FROM lives"), [(0,)])
        self.assertEqual(self.query("SELECT status FROM events"), [("pending",)])

    async def test_invalid_model_output_preserves_prior_state(self):
        await self.engine.correct_state(self.scope, {"activity_code": "writing"})
        self.response = {"state": {"core_personality": "changed"}}
        result = await self.engine.advance([self.event()])
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["snapshot"]["activity"], "独自写作")

    async def test_diary_cannot_rewrite_prior_time_or_describe_future(self):
        event = self.event()
        for offset in [-1, 1]:
            self.wait_retry()
            at = event["occurred_at"] - 1 if offset < 0 else self.now + 1
            self.response = {"diary": [{"occurred_at": at, "text": "invented", "source_ids": ["e1"], "fact_kind": "subjective"}]}
            self.assertEqual((await self.engine.advance([event]))["status"], "invalid")
        self.assertEqual(self.query("SELECT COUNT(*) FROM diary")[0][0], 0)

    async def test_guess_cannot_be_promoted_to_observation(self):
        self.response = {"diary": [{"text": "用户确实生气了", "source_ids": ["e1"], "fact_kind": "observation"}]}
        result = await self.engine.advance([self.event(fact_kind="subjective")])
        self.assertEqual(result["status"], "invalid")

    async def test_unsent_commitment_and_completed_without_receipt_rejected(self):
        event = self.event()
        for status in ["committed", "completed"]:
            self.wait_retry()
            self.response = {"commitments": [{"description": "do work", "status": status, "source_ids": ["e1"]}]}
            self.assertEqual((await self.engine.advance([event]))["status"], "invalid")
        self.assertEqual((await self.engine.get_snapshot(self.scope))["commitments"], [])

    async def test_only_successful_delivered_segment_can_confirm_promise(self):
        candidate = {"commitment_id": "p1", "description": "帮忙看看", "evidence_quote": "我晚点帮你看看"}
        await self.engine.ingest_events([self.event("failure", kind="delivery.failure", text="", data={"commitments": [candidate]})])
        await self.engine.ingest_events([self.event("partial", kind="delivery.success", text="嗯", data={"commitments": [candidate]})])
        self.assertEqual((await self.engine.get_snapshot(self.scope))["commitments"], [])
        await self.engine.ingest_events([self.event("sent", kind="delivery.success", text="我晚点帮你看看", data={"commitments": [candidate]})])
        promises = (await self.engine.get_snapshot(self.scope))["commitments"]
        self.assertEqual(len(promises), 1)
        self.assertEqual(promises[0]["source_ids"], ["sent"])
        self.assertEqual(promises[0]["status"], "committed")
        self.assertEqual((await self.engine.get_snapshot(self.other))["commitments"], [])

    async def test_six_extra_calls_per_hour_persist_across_restart(self):
        for index in range(6):
            self.assertEqual((await self.engine.advance([self.event(str(index))]))["status"], "no_change")
        await self.engine.close()
        self.engine = NarrativeEngine(self.path, self.config, self.model, lambda: self.now)
        result = await self.engine.advance([self.event("seventh")])
        self.assertEqual(result["status"], "budget_exhausted")
        self.now += 3600
        result = await self.engine.advance([self.event("eighth")])
        self.assertEqual(result["status"], "no_change")
        self.assertEqual(self.query("SELECT status FROM events WHERE event_id='seventh'"), [("processed",)])

    async def test_hourly_global_does_not_receive_chat_history_and_runs_once(self):
        await self.engine.ingest_events([self.event(text="private secret")])
        await self.engine.tick()
        global_calls = [request for request in self.requests if not request["scope"]["umo"]]
        self.assertEqual(len(global_calls), 1)
        self.assertNotIn("private secret", json.dumps(global_calls))
        first = len(self.requests)
        await self.engine.tick()
        self.assertEqual(len(self.requests), first)

    async def test_background_coalesces_at_five_minutes(self):
        await self.engine.tick()
        await self.engine.ingest_events([self.event()])
        await self.engine.tick()
        self.assertEqual(self.query("SELECT status FROM events WHERE event_id='e1'"), [("pending",)])
        self.now += 300
        await self.engine.tick()
        self.assertEqual(self.query("SELECT status FROM events WHERE event_id='e1'"), [("processed",)])

    async def test_fake_day_hourly_acceptance_and_bounded_offline_resume(self):
        for _ in range(24):
            await self.engine.tick()
            self.now += 3600
        global_calls = [request for request in self.requests if not request["scope"]["umo"]]
        self.assertEqual(len(global_calls), 24)
        self.assertEqual(self.query("SELECT COUNT(*) FROM intents")[0][0], 0)
        self.now += 7 * 86400
        await self.engine.tick()
        self.assertEqual(len(self.requests), 25)
        self.assertTrue(self.requests[-1]["offline_catchup"])

    async def test_sleep_skips_only_life_calls_and_does_not_drop_at_event(self):
        global_scope = dict(self.scope, platform="", umo="")
        self.response = {"state": {"activity_code": "sleeping", "availability": "asleep", "valid_until": self.now + 7200}, "next_check": self.now + 7200}
        await self.engine.advance([self.event("sleep", scope=global_scope, kind="life.tick", fact_kind="fiction")])
        self.now += 3600
        self.response = {"no_change": True}
        await self.engine.tick()
        self.assertEqual(len(self.requests), 1)
        result = await self.engine.ingest_events([self.event("at", data={"addressed": True})])
        self.assertEqual(result["accepted"], ["at"])

    async def test_intent_scope_cancellation_and_no_precomposed_message(self):
        self.response = {"contact_intents": [{"intent_id": "i1", "reason": "约定有进展", "source_ids": ["e1"]}]}
        self.assertEqual((await self.engine.advance([self.event()]))["status"], "advanced")
        due = await self.engine.list_due_intents()
        self.assertEqual(due[0]["target_umo"], self.scope["umo"])
        self.assertNotIn("text", due[0])
        await self.engine.cancel_intent("i1")
        self.assertEqual(await self.engine.list_due_intents(), [])
        claimed = await self.engine.update_intent("i1", "claimed")
        self.assertFalse(claimed["changed"])

    async def test_contact_cannot_target_another_group_or_store_message(self):
        event = self.event()
        for extra in [{"target_umo": self.other["umo"]}, {"message": "old draft"}]:
            self.wait_retry()
            self.response = {"contact_intents": [dict(intent_id="i1", reason="约定进展", source_ids=["e1"], **extra)]}
            self.assertEqual((await self.engine.advance([event]))["status"], "invalid")
        self.assertEqual(await self.engine.list_due_intents(), [])

    async def test_claimed_intent_becomes_uncertain_on_restart(self):
        self.response = {"contact_intents": [{"intent_id": "i1", "reason": "约定进展", "source_ids": ["e1"]}]}
        await self.engine.advance([self.event()])
        self.assertTrue((await self.engine.update_intent("i1", "claimed"))["changed"])
        await self.engine.close()
        self.engine = NarrativeEngine(self.path, self.config, self.model, lambda: self.now)
        self.assertEqual(await self.engine.list_due_intents(), [])
        result = await self.engine.update_intent("i1", "pending")
        self.assertEqual(result["status"], "uncertain")

    async def test_existing_reminder_does_not_create_second_send(self):
        self.response = {"contact_intents": [{"intent_id": "i1", "reason": "提醒", "source_ids": ["e1"], "reminder_id": "existing"}]}
        await self.engine.advance([self.event()])
        self.assertEqual(await self.engine.list_due_intents(), [])

    async def test_pause_and_unload_revoke_model_commit(self):
        await self.engine.set_paused(True)
        result = await self.engine.advance([self.event()])
        self.assertEqual(result["status"], "paused")
        self.assertEqual(self.requests, [])
        await self.engine.set_paused(False)
        await self.engine.close()
        self.assertFalse((await self.engine.get_snapshot(self.scope))["managed"])

    async def test_legacy_migration_hash_backup_idempotent_no_sends(self):
        source = Path(self.temp.name) / "life_state.json"
        payload = {"date": "2026-10-10", "timeline": [{"time": "23:00", "schedule": "future plan"}]}
        original = json.dumps(payload, ensure_ascii=False).encode()
        source.write_bytes(original)
        result = self.engine.migrate_legacy(source)
        self.assertEqual(result["imported"], [str(source)])
        backup = list(Path(result["backup_dir"]).glob("*"))[0]
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(self.engine.migrate_legacy(source)["skipped"], [str(source)])
        archive = json.loads(self.query("SELECT payload FROM legacy_imports")[0][0])
        self.assertEqual(archive["timeline_kind"], "plan")
        self.assertEqual(self.query("SELECT COUNT(*) FROM intents")[0][0], 0)

    async def test_forty_fixed_evidence_and_scope_cases(self):
        """Forty deterministic cases are synthetic behavior checks, not LLM acceptance."""
        for index in range(40):
            with self.subTest(case=index):
                self.now += 3600
                scope = self.scope if index % 2 == 0 else self.other
                secret = f"private-person-{index}"
                self.response = {"state": {"activity_code": list(MODULE.ACTIVITIES)[index % len(MODULE.ACTIVITIES)],
                                           "summary": secret, "subjective_state": "猜测并非事实"},
                    "diary": [{"text": secret, "source_ids": [str(index)], "fact_kind": "subjective"}]}
                result = await self.engine.advance([self.event(str(index), scope=scope, text=secret)])
                self.assertEqual(result["status"], "advanced")
                other = await self.engine.get_snapshot(self.other if index % 2 == 0 else self.scope)
                self.assertNotIn(secret, json.dumps(other))
                self.assertNotIn(secret, self.query("SELECT state FROM lives")[0][0])
                self.assertEqual(self.query("SELECT fact_kind FROM diary ORDER BY occurred DESC LIMIT 1")[0][0], "subjective")

    async def test_overdue_life_precedes_event_without_chat_or_stale_revision(self):
        self.response = {"no_change": True}
        await self.engine.tick()
        baseline = (await self.engine.get_snapshot(self.scope))["revision"]
        self.now += 7200
        self.requests.clear()
        result = await self.engine.advance([self.event("important", text="secret current disruption")], expected_revision=baseline)
        self.assertEqual(result["status"], "no_change")
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[0]["scope"]["umo"], "")
        self.assertNotIn("secret current disruption", json.dumps(self.requests[0]))
        self.assertEqual(self.requests[1]["scope"]["umo"], self.scope["umo"])
        self.assertEqual(self.requests[1]["snapshot"]["revision"], baseline + 1)

    async def test_outreach_pause_is_scoped_and_narrative_still_runs(self):
        self.response = {"contact_intents": [{"intent_id": "i1", "reason": "约定进展", "source_ids": ["e1"]}]}
        await self.engine.advance([self.event()])
        await self.engine.set_outreach_paused(True, self.other)
        self.assertEqual(len(await self.engine.list_due_intents()), 1)
        await self.engine.set_outreach_paused(True, self.scope)
        self.assertEqual(await self.engine.list_due_intents(), [])
        self.response = {"no_change": True}
        self.assertEqual((await self.engine.advance([self.event("e2")]))["status"], "no_change")

    async def test_invalid_cross_scope_commit_rolls_back_whole_batch(self):
        self.response = {"commitments": [{"commitment_id": "same", "description": "first", "source_ids": ["a"]}]}
        await self.engine.advance([self.event("a")])
        self.response = {"state": {"summary": "must not commit"}, "commitments": [{"commitment_id": "same", "description": "second", "source_ids": ["b"]}]}
        before = (await self.engine.get_snapshot(self.other))["revision"]
        result = await self.engine.advance([self.event("b", scope=self.other)])
        self.assertEqual(result["status"], "invalid")
        self.assertEqual(result["snapshot"]["revision"], before)
        self.assertEqual(result["snapshot"]["summary"], "")
        self.assertEqual(self.query("SELECT status FROM events WHERE event_id='b'"), [("pending",)])

    async def test_completion_receipt_must_match_the_actual_commitment(self):
        self.response = {"commitments": [{"commitment_id": "work", "description": "work", "status": "completed", "source_ids": ["tool"]}]}
        result = await self.engine.advance([self.event("tool", kind="tool.success", data={"commitment_id": "unrelated"})])
        self.assertEqual(result["status"], "invalid")
        self.wait_retry()
        self.response["commitments"][0]["source_ids"] = ["tool2"]
        result = await self.engine.advance([self.event("tool2", kind="tool.success", data={"commitment_id": "work", "effect_confirmed": True})])
        self.assertEqual(result["status"], "advanced")
        self.assertEqual(result["snapshot"]["commitments"][0]["status"], "completed")

    async def test_observed_utterance_cannot_be_promoted_to_verified_user_state(self):
        self.response = {"diary": [{"text": "用户真的生气了", "source_ids": ["e1"], "fact_kind": "observation"}]}
        event = self.event(text="我可能有点生气")
        self.assertEqual((await self.engine.advance([event]))["status"], "invalid")
        self.wait_retry()
        self.response["diary"][0]["text"] = event["text"]
        result = await self.engine.advance([event])
        self.assertEqual(result["status"], "advanced")
        entry = (await self.engine.get_narrative_admin(self.scope))["diary"][0]
        self.assertIn("发言记录", entry["text"])
        self.assertIn("我可能有点生气", entry["text"])

    async def test_actual_receipt_recovers_missed_final_intent_update(self):
        self.response = {"contact_intents": [{"intent_id": "i1", "reason": "约定进展", "source_ids": ["e1"]}]}
        await self.engine.advance([self.event()])
        self.assertTrue((await self.engine.update_intent("i1", "claimed"))["changed"])
        await self.engine.ingest_events([self.event("sent", kind="delivery.success", text="有进展了", data={"intent_id": "i1", "message_id": "p1"})])
        self.assertEqual((await self.engine.get_intent("i1"))["item"]["status"], "sent")
        await self.engine.close()
        self.engine = NarrativeEngine(self.path, self.config, self.model, lambda: self.now)
        self.assertEqual(await self.engine.list_due_intents(), [])
        self.assertEqual((await self.engine.get_intent("i1"))["item"]["status"], "sent")

    async def test_receipt_replay_resolves_restart_uncertainty_without_reopening(self):
        self.response = {"contact_intents": [{"intent_id": "i1", "reason": "约定进展", "source_ids": ["e1"]}]}
        await self.engine.advance([self.event()])
        await self.engine.update_intent("i1", "claimed")
        await self.engine.close()
        self.engine = NarrativeEngine(self.path, self.config, self.model, lambda: self.now)
        self.assertEqual((await self.engine.get_intent("i1"))["item"]["status"], "uncertain")
        receipt = self.event("sent", kind="delivery.success", text="有进展了", data={"intent_id": "i1", "attempt_id": "attempt", "message_id": "p1"})
        await self.engine.ingest_events([receipt])
        self.assertEqual((await self.engine.get_intent("i1"))["item"]["status"], "sent")
        self.assertEqual(await self.engine.list_due_intents(), [])

    async def test_program_plan_window_uses_exact_china_midnight(self):
        self.now = dt.datetime(2026, 10, 10, 23, 55, tzinfo=CHINA).timestamp()
        expected_end = dt.datetime(2026, 10, 11, 0, tzinfo=CHINA).timestamp()

        async def model(request):
            self.assertEqual(request["plan_window"], {"start": self.now, "end": expected_end})
            self.assertEqual(request["day_end"], expected_end)
            return {"daily_plan": [{"start": request["plan_window"]["start"], "end": request["plan_window"]["end"], "activity": "准备休息"}]}

        self.engine.model = model
        result = await self.engine.tick()
        self.assertEqual(result["results"][0]["status"], "advanced")
        admin = await self.engine.get_narrative_admin(self.scope)
        self.assertEqual(admin["daily_plan"][0]["end"], expected_end)

    async def test_daily_plan_crossing_program_window_remains_invalid(self):
        self.now = dt.datetime(2026, 10, 10, 23, 55, tzinfo=CHINA).timestamp()

        async def model(request):
            return {"daily_plan": [{"start": request["plan_window"]["start"], "end": request["plan_window"]["end"] + 1, "activity": "明天的计划"}]}

        self.engine.model = model
        result = await self.engine.tick()
        self.assertEqual(result["results"][0]["status"], "invalid")
        self.assertEqual((await self.engine.get_narrative_admin(self.scope))["daily_plan"], [])


if __name__ == "__main__":
    unittest.main()
