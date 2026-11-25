"""Batch 2 regression tests: P0-1 regen deadlock, storage bloat, pruning, and query plans."""

from __future__ import annotations

import asyncio
import copy
import datetime as dt
import json
import logging
import os
import sqlite3
import time
from pathlib import Path

from astrbot_plugin_dynamics_world.causal_life import CausalLifeService
from astrbot_plugin_dynamics_world.geography import switch_mode
from astrbot_plugin_dynamics_world.life.core.narrative import (
    CHINA,
    NarrativeEngine,
    _identity,
)
from astrbot_plugin_dynamics_world.life.core.narrative_types import _json
from astrbot_plugin_dynamics_world.spatial import MAX_MAP_VERSIONS, SpatialState


SCOPE = {
    "platform": "test",
    "umo": "test:GroupMessage:batch2",
    "persona_id": "p_batch2",
    "instance_id": "inst_batch2",
}


def _explain(db: sqlite3.Connection, sql: str, params: tuple = ()) -> str:
    rows = db.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
    return "\n".join(str(r[-1]) for r in rows)


def _sample_map(seed: str = "seed-1", img_kb: int = 128) -> dict:
    return {
        "schema_version": 1,
        "seed": seed,
        "generator": "test fixture",
        "width": 100,
        "height": 100,
        "image": "data:image/png;base64," + ("A" * (img_kb * 1024)),
        "seconds_per_unit": 10,
        "places": [
            {"id": "a", "name": "住所", "x": 10, "y": 10, "cell": 0},
            {"id": "b", "name": "书店", "x": 90, "y": 10, "cell": 2},
        ],
        "graph": {
            "points": [[10, 10], [50, 10], [90, 10], [50, 50]],
            "edges": [[1, 3], [0, 2, 3], [1, 3], [0, 1, 2]],
        },
        "roads": [],
    }


def _make_engine(tmp_path: Path, model_fn, now_box: list[float], db_name: str = "narrative.sqlite3"):
    cfg = {
        "mode": "narrative",
        "persona_id": SCOPE["persona_id"],
        "narrative_sessions": [SCOPE["umo"]],
        "narrative_timeout_seconds": 10,
        "hourly_budget": 10,
    }
    engine = NarrativeEngine(tmp_path / db_name, cfg, model_fn, clock=lambda: now_box[0])
    engine.spatial = SpatialState(engine)
    engine.causal = CausalLifeService(engine)
    return engine


# ---------------------------------------------------------------------------
# P0-1: regenerate_daily_plan stale-revision self-deadlock regression
# ---------------------------------------------------------------------------


def test_regenerate_daily_plan_stale_revision_no_deadlock_and_persists_state(tmp_path):
    now = [dt.datetime(2026, 11, 21, 9, 0, tzinfo=CHINA).timestamp()]
    ident = _identity(SCOPE)

    async def model_with_concurrent_revision_bump(req):
        # Simulate another writer advancing lives.revision while the LLM call is in flight
        with engine._db() as db:
            db.execute("UPDATE lives SET revision=revision+1 WHERE identity=?", (ident,))
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
                {"start": w["start"] + 60, "end": w["start"] + 3600, "activity": "泡茶阅读"},
            ],
            "next_check": w["start"] + 3600,
        }

    engine = _make_engine(tmp_path, model_with_concurrent_revision_bump, now)
    t0 = time.monotonic()
    result = asyncio.run(engine.regenerate_daily_plan(SCOPE))
    elapsed = time.monotonic() - t0

    # Must complete well under the 5s SQLite busy_timeout (no self-deadlock!)
    assert elapsed < 2.0, f"regenerate_daily_plan stale path took {elapsed:.2f}s (possible deadlock)"
    assert result["status"] == "stale"
    assert result["error"] == "stale_revision"
    assert result["plan_status"]["last_attempt_status"] == "stale"

    with engine._db(notify=False) as db:
        ev = db.execute(
            "SELECT status, error FROM events WHERE identity=? ORDER BY created DESC LIMIT 1",
            (ident,),
        ).fetchone()
        assert ev is not None and ev["status"] == "failed" and ev["error"] == "stale_revision"
        call = db.execute(
            "SELECT status, kind FROM calls WHERE identity=? ORDER BY started DESC LIMIT 1",
            (ident,),
        ).fetchone()
        assert call is not None and call["status"] == "stale" and call["kind"] == "plan_regen"


# ---------------------------------------------------------------------------
# P1-#3a: legacy auto_vacuum=NONE detection & controlled conversion
# ---------------------------------------------------------------------------


def test_legacy_auto_vacuum_none_detected_and_safely_converted(tmp_path, caplog):
    now = [1_795_000_000.0]
    db_path = tmp_path / "legacy.sqlite3"

    # Pre-create a legacy SQLite DB with auto_vacuum=NONE (mode 0) and an existing table
    raw = sqlite3.connect(db_path)
    raw.execute("PRAGMA auto_vacuum=NONE")
    raw.execute("CREATE TABLE legacy_marker(id INTEGER PRIMARY KEY)")
    raw.commit()
    raw.close()

    async def noop_model(_req):
        return {"schema_version": 1, "no_change": True}

    with caplog.at_level(logging.WARNING):
        engine = _make_engine(tmp_path, noop_model, now, db_name="legacy.sqlite3")

    assert any("auto_vacuum=NONE" in rec.message for rec in caplog.records)

    status = engine.storage_vacuum_status()
    assert status["auto_vacuum"] == 0
    assert status["needs_conversion"] is True

    # Seed old rows that create freelist pages when deleted
    ident = _identity(SCOPE)
    old_ts = now[0] - 90 * 86400
    big_blob = "X" * 8000
    with engine._db(notify=False) as db:
        for i in range(40):
            db.execute(
                "INSERT INTO diary VALUES(?,?,?,?,?,?,?,?)",
                (f"d-old-{i}", ident, SCOPE["umo"], old_ts, big_blob, "observation", "[]", 1),
            )

    # Below threshold & conversion disabled -> must NOT falsely claim vacuumed=True
    res1 = engine.prune_history(
        retention_days=60,
        now=now[0],
        allow_auto_vacuum_conversion=False,
        auto_vacuum_threshold_bytes=20 * 1024 * 1024,
    )
    assert res1["diary"] == 40
    assert res1["auto_vacuum"] == 0
    assert res1["vacuumed"] is False
    assert res1["auto_vacuum_needed"] is True
    assert res1["auto_vacuum_converted"] is False
    assert res1["freelist_bytes"] > 0

    # Controlled conversion via enable_incremental_vacuum(force=True)
    conv = engine.enable_incremental_vacuum(force=True)
    assert conv["changed"] is True
    assert conv["auto_vacuum"] == 2
    assert conv["after_freelist_bytes"] == 0

    # Subsequent prune on converted DB performs real incremental_vacuum
    with engine._db(notify=False) as db:
        db.execute(
            "INSERT INTO diary VALUES(?,?,?,?,?,?,?,?)",
            ("d-old-post", ident, SCOPE["umo"], old_ts, big_blob, "observation", "[]", 1),
        )
    res2 = engine.prune_history(retention_days=60, now=now[0])
    assert res2["diary"] == 1
    assert res2["auto_vacuum"] == 2
    assert res2["vacuumed"] is True
    assert res2["auto_vacuum_needed"] is False


def test_legacy_auto_vacuum_converts_when_freelist_exceeds_threshold(tmp_path):
    now = [1_795_000_000.0]
    db_path = tmp_path / "legacy_thresh.sqlite3"
    raw = sqlite3.connect(db_path)
    raw.execute("PRAGMA auto_vacuum=NONE")
    raw.execute("CREATE TABLE legacy_marker(id INTEGER PRIMARY KEY)")
    raw.commit()
    raw.close()

    async def noop_model(_req):
        return {"schema_version": 1, "no_change": True}

    engine = _make_engine(tmp_path, noop_model, now, db_name="legacy_thresh.sqlite3")
    ident = _identity(SCOPE)
    old_ts = now[0] - 90 * 86400
    with engine._db(notify=False) as db:
        for i in range(25):
            db.execute(
                "INSERT INTO diary VALUES(?,?,?,?,?,?,?,?)",
                (f"d-old-{i}", ident, SCOPE["umo"], old_ts, "Y" * 8000, "observation", "[]", 1),
            )

    res = engine.prune_history(
        retention_days=60,
        now=now[0],
        auto_vacuum_threshold_bytes=16 * 1024,
    )
    assert res["auto_vacuum"] == 2
    assert res["auto_vacuum_converted"] is True
    assert res["vacuumed"] is True


# ---------------------------------------------------------------------------
# P1-#3b: world_map_versions dedup, compaction & retention cap
# ---------------------------------------------------------------------------


def test_world_map_versions_dedup_compaction_and_cap(tmp_path):
    now = [1_795_000_000.0]

    async def noop_model(_req):
        return {"schema_version": 1, "no_change": True}

    engine = _make_engine(tmp_path, noop_model, now)
    base_doc = _sample_map(img_kb=128)
    engine.spatial.install(SCOPE, base_doc, expected_revision=0)

    # Re-installing identical content must be deduplicated in world_map_versions
    engine.spatial.install(SCOPE, copy.deepcopy(base_doc), expected_revision=1)
    with engine._db(notify=False) as db:
        assert db.execute("SELECT COUNT(*) FROM world_map_versions").fetchone()[0] == 1

    # Perform 8 distinct save_place edits -> versions capped at MAX_MAP_VERSIONS and blobs compacted
    rev = 2
    for idx in range(8):
        now[0] += 10
        res = engine.spatial.save_place(
            SCOPE,
            {
                "name": f"书店_{idx}",
                "place_id": "b",
                "x": 90,
                "y": 10,
                "expected_revision": rev,
            },
        )
        rev = res["revision"]

    with engine._db(notify=False) as db:
        rows = db.execute(
            "SELECT revision, LENGTH(document) AS sz, document FROM world_map_versions ORDER BY revision"
        ).fetchall()
        assert len(rows) == MAX_MAP_VERSIONS
        # Every save_place archived row must strip duplicated base64 image & graph
        for row in rows:
            archived = json.loads(row["document"])
            assert archived["image"] == ""
            assert "image_ref_sha256" in archived
            assert "graph" not in archived
            assert "graph_ref_sha256" in archived
            assert row["sz"] < 4096

        # Live world_maps row still retains the complete image and graph
        live = json.loads(
            db.execute("SELECT document FROM world_maps WHERE identity=?", (_identity(SCOPE),)).fetchone()[0]
        )
        assert len(live["image"]) > 128 * 1024
        assert "points" in live["graph"]

    # Mode switch also respects MAX_MAP_VERSIONS
    real_doc = {
        "schema_version": 1,
        "seed": "real",
        "map_type": "real",
        "places": [{"id": "home", "name": "家", "lat": 31.2, "lon": 121.5}],
    }
    switch_mode(engine.spatial, SCOPE, "real", rev, document=real_doc)
    with engine._db(notify=False) as db:
        assert db.execute("SELECT COUNT(*) FROM world_map_versions").fetchone()[0] <= MAX_MAP_VERSIONS


# ---------------------------------------------------------------------------
# P1-#3c: 6 missing append-only tables + .bak backup pruning
# ---------------------------------------------------------------------------


def test_prune_history_covers_all_append_tables_and_bak_files(tmp_path):
    now = [1_795_000_000.0]

    async def noop_model(_req):
        return {"schema_version": 1, "no_change": True}

    engine = _make_engine(tmp_path, noop_model, now)
    ident = _identity(SCOPE)
    old_ts = now[0] - 90 * 86400
    fresh_ts = now[0] - 5 * 86400

    # Create optional world_resident_evaluations and world_scene_events tables too
    with engine._db(notify=False) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS world_scene_events(
                event_id TEXT PRIMARY KEY, identity TEXT NOT NULL, kind TEXT NOT NULL,
                occurred REAL NOT NULL, payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS world_scene_events_occurred ON world_scene_events(occurred);
            CREATE TABLE IF NOT EXISTS world_resident_evaluations(
                call_id TEXT PRIMARY KEY, identity TEXT NOT NULL, actor_id TEXT NOT NULL,
                started REAL NOT NULL, status TEXT NOT NULL, evidence TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS world_resident_evaluations_started ON world_resident_evaluations(started);
        """)
        # 1. diary
        db.execute("INSERT INTO diary VALUES('d-old',?,?,?,'old','observation','[]',1)", (ident, SCOPE["umo"], old_ts))
        db.execute("INSERT INTO diary VALUES('d-fresh',?,?,?,'fresh','observation','[]',2)", (ident, SCOPE["umo"], fresh_ts))
        # 2. world_scene_events
        db.execute("INSERT INTO world_scene_events VALUES('se-old',?,'step.completed',?,'{}')", (ident, old_ts))
        db.execute("INSERT INTO world_scene_events VALUES('se-fresh',?,'step.completed',?,'{}')", (ident, fresh_ts))
        # 3. world_life_receipts
        db.execute("INSERT INTO world_life_receipts VALUES('lr-old',?,?,'action','{}')", (ident, old_ts))
        db.execute("INSERT INTO world_life_receipts VALUES('lr-fresh',?,?,'action','{}')", (ident, fresh_ts))
        # 4. world_resident_evaluations
        db.execute("INSERT INTO world_resident_evaluations VALUES('re-old',?,'actor1',?,'ok','{}')", (ident, old_ts))
        db.execute("INSERT INTO world_resident_evaluations VALUES('re-fresh',?,'actor1',?,'ok','{}')", (ident, fresh_ts))
        # 5. world_map_events
        db.execute("INSERT INTO world_map_events VALUES('me-old',?,'movement.arrived','{}',?)", (ident, old_ts))
        db.execute("INSERT INTO world_map_events VALUES('me-fresh',?,'movement.arrived','{}',?)", (ident, fresh_ts))
        # 6. world_map_versions: 7 old versions -> must trim down to 1 latest (preserved even if old)
        for rev in range(1, 8):
            db.execute(
                "INSERT INTO world_map_versions VALUES(?,?,?,?)",
                (ident, rev, "{}", old_ts + rev),
            )
        # 7. events across all terminal statuses + pending
        for idx, st in enumerate(("processed", "observed_only", "historical_only", "failed", "blocked_policy")):
            db.execute(
                "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,0,0)",
                (f"ev-old-{idx}", ident, SCOPE["umo"], old_ts, old_ts, "{}", st, "", old_ts),
            )
        db.execute(
            "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,0,0)",
            ("ev-old-pending", ident, SCOPE["umo"], old_ts, old_ts, "{}", "pending", "", old_ts),
        )
        # 8. intents across terminal statuses + pending/claimed
        for idx, st in enumerate(("sent", "cancelled", "expired", "uncertain", "failed")):
            db.execute(
                "INSERT INTO intents VALUES(?,?,?,?,?,?,?,?)",
                (f"in-old-{idx}", ident, SCOPE["umo"], '{"source_ids":[]}', st, old_ts, old_ts + 60, old_ts),
            )
        db.execute(
            "INSERT INTO intents VALUES(?,?,?,?,?,?,?,?)",
            ("in-old-pending", ident, SCOPE["umo"], '{"source_ids":[]}', "pending", old_ts, old_ts + 60, old_ts),
        )
        # 9. validation_failures + validation_failure_events
        engine._insert_validation_failure(db, ["ev-old-0", "ev-old-1"], "bad_old", old_ts)
        engine._insert_validation_failure(db, ["ev-fresh-0"], "bad_fresh", fresh_ts)

    # Create 4 migration .bak files + 1 unrelated file
    baks = [
        tmp_path / "narrative.sqlite3.pre-v20-1000-aaaa1111.bak",
        tmp_path / "narrative.sqlite3.pre-v20-2000-bbbb2222.bak",
        tmp_path / "narrative.sqlite3.pre-retry-3000-cccc3333.bak",
        tmp_path / "narrative.sqlite3.pre-retry-4000-dddd4444.bak",
    ]
    for idx, bak in enumerate(baks):
        bak.write_bytes(b"backup")
        os.utime(bak, (1000 + idx * 10, 1000 + idx * 10))
    unrelated = tmp_path / "keep_me.bak"
    unrelated.write_bytes(b"keep")

    summary = engine.prune_history(
        retention_days=60,
        batch_size=3,
        max_map_versions=5,
        max_backups=1,
        now=now[0],
    )
    assert summary["events"] == 5
    assert summary["intents"] == 5
    assert summary["validation_failures"] == 1
    assert summary["diary"] == 1
    assert summary["world_scene_events"] == 1
    assert summary["world_life_receipts"] == 1
    assert summary["world_resident_evaluations"] == 1
    assert summary["world_map_events"] == 1
    assert summary["world_map_versions"] == 6  # 7 old -> 1 latest kept
    assert summary["backups_deleted"] == 3
    assert summary["vacuumed"] is True

    # Newest backup & unrelated file preserved
    assert baks[-1].exists()
    assert not any(p.exists() for p in baks[:-1])
    assert unrelated.exists()

    with engine._db(notify=False) as db:
        assert [r[0] for r in db.execute("SELECT entry_id FROM diary").fetchall()] == ["d-fresh"]
        assert [r[0] for r in db.execute("SELECT event_id FROM world_scene_events").fetchall()] == ["se-fresh"]
        assert [r[0] for r in db.execute("SELECT id FROM world_life_receipts").fetchall()] == ["lr-fresh"]
        assert [r[0] for r in db.execute("SELECT call_id FROM world_resident_evaluations").fetchall()] == ["re-fresh"]
        assert [r[0] for r in db.execute("SELECT id FROM world_map_events").fetchall()] == ["me-fresh"]
        assert [r[0] for r in db.execute("SELECT revision FROM world_map_versions").fetchall()] == [7]
        assert [r[0] for r in db.execute("SELECT event_id FROM events").fetchall()] == ["ev-old-pending"]
        assert [r[0] for r in db.execute("SELECT intent_id FROM intents").fetchall()] == ["in-old-pending"]
        assert [r[0] for r in db.execute("SELECT event_id FROM validation_failure_events").fetchall()] == ["ev-fresh-0"]


# ---------------------------------------------------------------------------
# P1-#3d: EXPLAIN QUERY PLAN index verification & functional dedup/isolation
# ---------------------------------------------------------------------------


def test_explain_query_plan_eliminates_full_table_scans(tmp_path):
    now = [1_795_000_000.0]

    async def noop_model(_req):
        return {"schema_version": 1, "no_change": True}

    engine = _make_engine(tmp_path, noop_model, now)
    ident = _identity(SCOPE)

    with engine._db(notify=False) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS world_scene_events(
                event_id TEXT PRIMARY KEY, identity TEXT NOT NULL, kind TEXT NOT NULL,
                occurred REAL NOT NULL, payload TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS world_scene_events_occurred ON world_scene_events(occurred);
            CREATE TABLE IF NOT EXISTS world_resident_evaluations(
                call_id TEXT PRIMARY KEY, identity TEXT NOT NULL, actor_id TEXT NOT NULL,
                started REAL NOT NULL, status TEXT NOT NULL, evidence TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS world_resident_evaluations_started ON world_resident_evaluations(started);
        """)

        # 1. events cleanup uses event_status_created (not SCAN events)
        plan_events = _explain(
            db,
            "SELECT rowid FROM events WHERE status IN ('processed','observed_only','historical_only','failed','blocked_policy') AND created<? AND occurred<? LIMIT 500",
            (now[0], now[0]),
        )
        assert "event_status_created" in plan_events and "SCAN events" not in plan_events, plan_events

        # 2. intents cleanup uses intent_status_updated (not SCAN intents)
        plan_intents_prune = _explain(
            db,
            "SELECT rowid FROM intents WHERE status IN ('sent','cancelled','expired','uncertain','failed') AND updated<? AND expires<? LIMIT 500",
            (now[0], now[0]),
        )
        assert "intent_status_updated" in plan_intents_prune and "SCAN intents" not in plan_intents_prune, plan_intents_prune

        # 3. intents source_ids dedup uses covering index intent_scope_sources
        plan_intents_dedup = _explain(
            db,
            "SELECT 1 FROM intents WHERE identity=? AND umo=? AND json_extract(payload,'$.source_ids')=? LIMIT 1",
            (ident, SCOPE["umo"], _json(["ev-1"])),
        )
        assert "intent_scope_sources" in plan_intents_dedup and "SCAN intents" not in plan_intents_dedup, plan_intents_dedup

        # 4. validation_failures lookup uses validation_failure_events PK + validation_failures PK (no SCAN / no json_each)
        plan_vf = _explain(
            db,
            "SELECT vf.event_ids FROM validation_failure_events vfe "
            "JOIN validation_failures vf ON vf.failure_id = vfe.failure_id "
            "WHERE vfe.event_id = ? ORDER BY vfe.occurred DESC LIMIT 1",
            ("ev-1",),
        )
        assert "SCAN " not in plan_vf and "json_each" not in plan_vf, plan_vf

        # 5. Append-only table cleanup queries all use time indexes
        for tbl, sql in (
            ("diary", "SELECT rowid FROM diary WHERE occurred<? LIMIT 500"),
            ("budgets", "SELECT rowid FROM budgets WHERE hour<? LIMIT 500"),
            ("world_map_events", "SELECT rowid FROM world_map_events WHERE occurred<? LIMIT 500"),
            ("world_scene_events", "SELECT rowid FROM world_scene_events WHERE occurred<? LIMIT 500"),
            ("world_life_receipts", "SELECT rowid FROM world_life_receipts WHERE occurred<? LIMIT 500"),
            ("world_resident_evaluations", "SELECT rowid FROM world_resident_evaluations WHERE started<? LIMIT 500"),
        ):
            plan = _explain(db, sql, (now[0],))
            assert f"SCAN {tbl}" not in plan, f"{tbl} fell back to full scan: {plan}"


def test_validation_failure_lookup_backfill_and_intent_dedup_behavior(tmp_path):
    now = [1_795_000_000.0]

    async def noop_model(_req):
        return {"schema_version": 1, "no_change": True}

    engine = _make_engine(tmp_path, noop_model, now)
    ident = _identity(SCOPE)

    # Verify _record_failure populates indexed validation_failure_events and _pending_state isolates properly
    ev1 = {
        "schema_version": 1,
        "event_id": "ev-fail-1",
        "type": "chat.message",
        "scope": SCOPE,
        "occurred_at": now[0] - 10,
        "received_at": now[0] - 10,
        "text": "hello",
        "fact_kind": "user_claim",
    }
    ev2 = dict(ev1, event_id="ev-fail-2", occurred_at=now[0] - 5, received_at=now[0] - 5)
    asyncio.run(engine.ingest_events([ev1, ev2]))
    engine._record_failure([ev1, ev2], now[0], "validation.bad_output")

    # Fast-forward past retry backoff
    now[0] += 3600
    with engine._db(notify=False) as db:
        rows = db.execute(
            "SELECT event_id FROM validation_failure_events WHERE event_id IN ('ev-fail-1','ev-fail-2')"
        ).fetchall()
        assert {r[0] for r in rows} == {"ev-fail-1", "ev-fail-2"}
        batch, state = engine._pending_state(db, SCOPE, now[0])
        assert state == "ready"
        assert [e["event_id"] for e in batch] == ["ev-fail-1"]

    # Verify indexed intent source_ids dedup in _commit blocks duplicate source_ids end-to-end
    with engine._db() as db:
        engine._ensure(db, SCOPE, now[0])
        snap = engine._snapshot(db, SCOPE, now[0])
        db.execute(
            "INSERT INTO intents VALUES(?,?,?,?,?,?,?,?)",
            (
                "intent-existing",
                ident,
                SCOPE["umo"],
                _json({"intent_id": "intent-existing", "source_ids": ["ev-dup-1"], "status": "sent"}),
                "sent",
                now[0],
                now[0] + 3600,
                now[0],
            ),
        )
        base_change = {
            "no_change": True,
            "state": {},
            "next_check": now[0] + 600,
            "daily_plan": None,
            "diary": [],
            "commitments": [],
            "contact_intents": [
                {
                    "intent_id": "intent-dup-should-skip",
                    "source_ids": ["ev-dup-1"],
                    "status": "pending",
                    "not_before": now[0],
                    "expires_at": now[0] + 3600,
                },
                {
                    "intent_id": "intent-unique-should-insert",
                    "source_ids": ["ev-new-99"],
                    "status": "pending",
                    "not_before": now[0],
                    "expires_at": now[0] + 3600,
                },
            ],
        }
        engine._commit(db, SCOPE, base_change, [], now[0], snap["revision"] + 1)
        intent_ids = {r[0] for r in db.execute("SELECT intent_id FROM intents").fetchall()}
        assert "intent-dup-should-skip" not in intent_ids
        assert "intent-unique-should-insert" in intent_ids

    # Verify startup backfill on legacy DB with validation_failures but no validation_failure_events_v1 marker
    with engine._db() as db:
        db.execute("DELETE FROM validation_failure_events")
        db.execute("DELETE FROM metadata WHERE key='validation_failure_events_v1'")
    engine2 = _make_engine(tmp_path, noop_model, now)
    with engine2._db(notify=False) as db:
        rows = db.execute(
            "SELECT event_id FROM validation_failure_events WHERE event_id IN ('ev-fail-1','ev-fail-2')"
        ).fetchall()
        assert {r[0] for r in rows} == {"ev-fail-1", "ev-fail-2"}
