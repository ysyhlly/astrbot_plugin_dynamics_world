"""SQLite schema initialization, migration receipts and pre-upgrade snapshots for NarrativeEngine."""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

try:
    from astrbot.api import logger
except Exception:  # pragma: no cover
    logger = logging.getLogger(__name__)

if __package__:
    from .narrative_types import (
        NarrativeValidationError,
        _json,
    )
else:
    import importlib.util as _ilu
    import sys as _sys

    _types_mod = _sys.modules.get("_dls_narrative_types")
    if _types_mod is None:
        _types_spec = _ilu.spec_from_file_location("_dls_narrative_types", Path(__file__).with_name("narrative_types.py"))
        _types_mod = _ilu.module_from_spec(_types_spec)
        _sys.modules["_dls_narrative_types"] = _types_mod
        _types_spec.loader.exec_module(_types_mod)
    NarrativeValidationError = _types_mod.NarrativeValidationError
    _json = _types_mod._json


class NarrativeSchemaMixin:
    """Database table creation, schema extension backups, clock v2 migration and legacy archive import."""

    def _prune_migration_backups(self, *, keep_latest: int = 1) -> int:
        """Keep at most ``keep_latest`` newest pre-migration .bak snapshots for this DB."""
        parent = self.path.parent
        if not parent.is_dir():
            return 0
        keep = max(0, int(keep_latest))
        candidates: list[Path] = []
        for pattern in (
            f"{self.path.name}.pre-v20-*.bak",
            f"{self.path.name}.pre-retry-*.bak",
        ):
            candidates.extend(p for p in parent.glob(pattern) if p.is_file())
        if len(candidates) <= keep:
            return 0

        def _sort_key(path: Path) -> tuple[float, str]:
            try:
                mtime = path.stat().st_mtime
            except OSError:
                mtime = 0.0
            return (mtime, path.name)

        ordered = sorted(candidates, key=_sort_key, reverse=True)
        removed = 0
        for stale in ordered[keep:]:
            try:
                stale.unlink()
                removed += 1
            except OSError:
                pass
        return removed

    def _backup_before_v20_extension(self) -> None:
        """Take an SQLite-consistent snapshot before initializing v0.20 virtual world tables."""
        if not self.path.is_file():
            return
        uri = self.path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as source:
            meta = source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='metadata'").fetchone()
            if meta is None:
                return
            ready = source.execute("SELECT value FROM metadata WHERE key='virtual_world_v20'").fetchone()
            if ready is not None:
                return
            backup = self.path.with_name(
                f"{self.path.name}.pre-v20-{int(self.clock())}-{uuid.uuid4().hex[:8]}.bak"
            )
            with closing(sqlite3.connect(backup, timeout=5)) as destination:
                source.backup(destination)
                check = destination.execute("PRAGMA quick_check").fetchone()
                if not check or check[0] != "ok":
                    raise sqlite3.DatabaseError("v20 migration backup failed quick_check")
        self._prune_migration_backups(keep_latest=1)

    def _backup_before_retry_extension(self) -> None:
        """Take an SQLite-consistent scoped backup before adding retry columns."""
        if not self.path.is_file():
            return
        uri = self.path.resolve().as_uri() + "?mode=ro"
        with closing(sqlite3.connect(uri, uri=True, timeout=5)) as source:
            table = source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='events'").fetchone()
            if table is None:
                return
            version = source.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
            if version is None or version[0] != "1":
                return
            columns = {row[1] for row in source.execute("PRAGMA table_info(events)")}
            if {"retry_attempt", "next_retry"} <= columns:
                return
            backup = self.path.with_name(
                f"{self.path.name}.pre-retry-{int(self.clock())}-{uuid.uuid4().hex[:8]}.bak"
            )
            with closing(sqlite3.connect(backup, timeout=5)) as destination:
                source.backup(destination)
                check = destination.execute("PRAGMA quick_check").fetchone()
                if not check or check[0] != "ok":
                    raise sqlite3.DatabaseError("Retry migration backup failed quick_check")
        self._prune_migration_backups(keep_latest=1)

    def _initialize(self) -> None:
        with self._db() as db:
            has_tables = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1"
            ).fetchone()
            if has_tables is None:
                db.execute("PRAGMA auto_vacuum=INCREMENTAL")
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS lives(identity TEXT PRIMARY KEY,scope TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0,state TEXT NOT NULL,updated REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS scopes(identity TEXT NOT NULL,umo TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0,state TEXT NOT NULL,
                    PRIMARY KEY(identity,umo));
                CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY,identity TEXT NOT NULL,
                    umo TEXT NOT NULL,occurred REAL NOT NULL,received REAL NOT NULL,
                    payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',
                    error TEXT NOT NULL DEFAULT '',created REAL NOT NULL,
                    retry_attempt INTEGER NOT NULL DEFAULT 0,
                    next_retry REAL NOT NULL DEFAULT 0);
                CREATE INDEX IF NOT EXISTS event_queue ON events(identity,umo,status,received);
                CREATE INDEX IF NOT EXISTS event_fifo ON events(identity,umo,status,occurred,received,event_id);
                CREATE INDEX IF NOT EXISTS event_recent_scopes ON events(identity,occurred,umo);
                CREATE INDEX IF NOT EXISTS event_pending_identity ON events(identity,status) WHERE status='pending';
                CREATE INDEX IF NOT EXISTS event_status_created ON events(status,created);
                CREATE INDEX IF NOT EXISTS event_outreach_window ON events(identity,occurred,umo) WHERE umo<>'' AND status!='blocked_policy';
                CREATE INDEX IF NOT EXISTS event_outreach_type ON events(identity,json_extract(payload,'$.type'),occurred) WHERE umo<>'' AND status!='blocked_policy';
                CREATE TABLE IF NOT EXISTS validation_failures(
                    failure_id TEXT PRIMARY KEY, event_ids TEXT NOT NULL,
                    reason_code TEXT NOT NULL, occurred REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS validation_failure_time ON validation_failures(occurred DESC);
                CREATE TABLE IF NOT EXISTS validation_failure_events(
                    event_id TEXT NOT NULL, failure_id TEXT NOT NULL, occurred REAL NOT NULL,
                    PRIMARY KEY(event_id, occurred, failure_id));
                CREATE INDEX IF NOT EXISTS validation_failure_events_time ON validation_failure_events(occurred);
                CREATE INDEX IF NOT EXISTS validation_failure_events_failure ON validation_failure_events(failure_id);
                CREATE TABLE IF NOT EXISTS diary(entry_id TEXT PRIMARY KEY,identity TEXT NOT NULL,
                    umo TEXT NOT NULL,occurred REAL NOT NULL,text TEXT NOT NULL,
                    fact_kind TEXT NOT NULL,source_ids TEXT NOT NULL,revision INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS diary_identity_occurred ON diary(identity,occurred DESC);
                CREATE INDEX IF NOT EXISTS diary_occurred ON diary(occurred);
                CREATE TABLE IF NOT EXISTS commitments(commitment_id TEXT PRIMARY KEY,
                    identity TEXT NOT NULL,umo TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS intents(intent_id TEXT PRIMARY KEY,identity TEXT NOT NULL,
                    umo TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,
                    not_before REAL NOT NULL,expires REAL NOT NULL,updated REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS intent_due ON intents(status,not_before,expires);
                CREATE INDEX IF NOT EXISTS intent_scope_status_updated ON intents(identity,umo,status,updated);
                CREATE INDEX IF NOT EXISTS intent_status_updated ON intents(status,updated);
                CREATE INDEX IF NOT EXISTS intent_scope_sources ON intents(identity,umo,json_extract(payload,'$.source_ids'));
                CREATE TABLE IF NOT EXISTS outreach_preferences(
                    identity TEXT NOT NULL,umo TEXT NOT NULL,user_id TEXT NOT NULL,
                    allowed INTEGER NOT NULL,occurred REAL NOT NULL,event_id TEXT NOT NULL,
                    PRIMARY KEY(identity,umo,user_id));
                CREATE TABLE IF NOT EXISTS budgets(identity TEXT NOT NULL,hour INTEGER NOT NULL,
                    kind TEXT NOT NULL,used INTEGER NOT NULL,PRIMARY KEY(identity,hour,kind));
                CREATE INDEX IF NOT EXISTS budgets_hour ON budgets(hour);
                CREATE TABLE IF NOT EXISTS maintenance(identity TEXT NOT NULL,kind TEXT NOT NULL,
                    last REAL NOT NULL,PRIMARY KEY(identity,kind));
                CREATE TABLE IF NOT EXISTS calls(call_id TEXT PRIMARY KEY,identity TEXT NOT NULL,
                    umo TEXT NOT NULL,started REAL NOT NULL,duration REAL NOT NULL,
                    status TEXT NOT NULL,kind TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS calls_started ON calls(started);
                CREATE TABLE IF NOT EXISTS legacy_imports(source_hash TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,payload TEXT NOT NULL,fact_kind TEXT NOT NULL,
                    imported REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS world_horizon_bookmarks(
                    log_id TEXT PRIMARY KEY,
                    identity TEXT NOT NULL,
                    source_kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    creator TEXT NOT NULL DEFAULT '',
                    chapter_label TEXT NOT NULL DEFAULT '',
                    digest TEXT NOT NULL,
                    reflection TEXT NOT NULL DEFAULT '',
                    occurred_at REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_world_horizon_bookmarks_identity_time
                    ON world_horizon_bookmarks(identity, occurred_at DESC, log_id DESC);
            """)
            db.execute("INSERT OR IGNORE INTO metadata VALUES('schema_version','1')")
            version = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0]
            if version != "1":
                raise NarrativeValidationError("unsupported_narrative_database_schema", "Unsupported narrative database schema")
            event_columns = {row[1] for row in db.execute("PRAGMA table_info(events)")}
            if "retry_attempt" not in event_columns:
                db.execute("ALTER TABLE events ADD COLUMN retry_attempt INTEGER NOT NULL DEFAULT 0")
            if "next_retry" not in event_columns:
                db.execute("ALTER TABLE events ADD COLUMN next_retry REAL NOT NULL DEFAULT 0")
            event_info = {row[1]: row for row in db.execute("PRAGMA table_info(events)")}
            for name, expected_type in (("retry_attempt", "INTEGER"), ("next_retry", "REAL")):
                column = event_info[name]
                if column[2].upper() != expected_type or int(column[3]) != 1 or str(column[4]) != "0":
                    raise ValueError(f"Invalid retry column definition: {name}")
            extension = db.execute("SELECT value FROM metadata WHERE key='retry_extension_version'").fetchone()
            if extension is None:
                db.execute("INSERT INTO metadata(key,value) VALUES('retry_extension_version','1')")
            elif extension[0] != "1":
                raise NarrativeValidationError("unsupported_narrative_retry_extension", "Unsupported narrative retry extension")
            db.execute("UPDATE intents SET status='uncertain' WHERE status='claimed'")
            self._migrate_outreach_preferences(db)
            self._migrate_clock(db)
            if not db.execute("SELECT 1 FROM metadata WHERE key='structured_contract_version'").fetchone():
                db.execute("UPDATE events SET next_retry=0 WHERE status='pending' AND error='ValueError'")
                db.execute("INSERT INTO metadata VALUES('structured_contract_version','1')")
            if not db.execute("SELECT 1 FROM metadata WHERE key='validation_failure_events_v1'").fetchone():
                rows = db.execute(
                    "SELECT failure_id, event_ids, occurred FROM validation_failures"
                ).fetchall()
                backfill: list[tuple[str, str, float]] = []
                for row in rows:
                    try:
                        parsed = json.loads(row["event_ids"])
                    except Exception:
                        continue
                    if isinstance(parsed, list):
                        for eid in parsed:
                            if isinstance(eid, str) and eid:
                                backfill.append((eid, row["failure_id"], float(row["occurred"])))
                if backfill:
                    db.executemany(
                        "INSERT OR IGNORE INTO validation_failure_events(event_id, failure_id, occurred) VALUES(?,?,?)",
                        backfill,
                    )
                db.execute("INSERT INTO metadata VALUES('validation_failure_events_v1','1')")
            existing_tables = {
                row[0]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            optional_indexes = (
                ("world_map_events", "CREATE INDEX IF NOT EXISTS world_map_events_scope ON world_map_events(identity,occurred)"),
                ("world_map_events", "CREATE INDEX IF NOT EXISTS world_map_events_occurred ON world_map_events(occurred)"),
                ("world_map_versions", "CREATE INDEX IF NOT EXISTS world_map_versions_created ON world_map_versions(created)"),
                ("world_scene_events", "CREATE INDEX IF NOT EXISTS world_scene_events_occurred ON world_scene_events(occurred)"),
                ("world_life_receipts", "CREATE INDEX IF NOT EXISTS world_life_receipts_occurred ON world_life_receipts(occurred)"),
                ("world_resident_evaluations", "CREATE INDEX IF NOT EXISTS world_resident_evaluations_started ON world_resident_evaluations(started)"),
            )
            for table_name, index_sql in optional_indexes:
                if table_name in existing_tables:
                    db.execute(index_sql)
            db.execute("INSERT OR IGNORE INTO metadata VALUES('virtual_world_v20','1')")
            auto_vacuum_mode = int((db.execute("PRAGMA auto_vacuum").fetchone() or [0])[0])
            if auto_vacuum_mode == 0:
                page_size = int((db.execute("PRAGMA page_size").fetchone() or [4096])[0])
                freelist_count = int((db.execute("PRAGMA freelist_count").fetchone() or [0])[0])
                freelist_mib = (freelist_count * page_size) / (1024 * 1024)
                logger.warning(
                    "[DynamicsWorld] narrative DB %s has auto_vacuum=NONE "
                    "(freelist=%d pages, %.2f MiB); incremental_vacuum cannot reclaim pages "
                    "until converted via enable_incremental_vacuum() or automatic maintenance threshold.",
                    self.path,
                    freelist_count,
                    freelist_mib,
                )

    def _migrate_clock(self, db):
        """Invalidate legacy group-refreshed deadlines once, with a durable receipt."""
        now = self.clock()
        for row in db.execute("SELECT identity,scope,state FROM lives").fetchall():
            state = json.loads(row["state"])
            if state.get("clock_schema_version") == 2:
                continue
            state["clock_schema_version"] = 2
            if "narrated_until" not in state:
                last = db.execute(
                    "SELECT MAX(started) FROM calls WHERE identity=? AND umo='' "
                    "AND kind='hourly' AND status IN ('advanced','no_change')",
                    (row["identity"],),
                ).fetchone()[0]
                state["narrated_until"] = min(now, last) if last is not None else now
                state["valid_until"] = min(now, state["valid_until"])
                state["next_check"] = now
                state.pop("activity_started_at", None)
                event_id = "clock.migration.v2:" + row["identity"]
                event = {
                    "schema_version": 1,
                    "event_id": event_id,
                    "type": "clock.migration",
                    "scope": json.loads(row["scope"]),
                    "occurred_at": now,
                    "received_at": now,
                    "actor_id": "system",
                    "text": "旧版时钟有效期作废，等待重新检查；历史记录保留。",
                    "source_ids": [event_id],
                    "fact_kind": "receipt",
                    "data": {"effect_confirmed": True},
                }
                db.execute(
                    "INSERT OR IGNORE INTO events(event_id,identity,umo,occurred,received,payload,status,created) VALUES(?,?,'',?,?,?,'observed_only',?)",
                    (event_id, row["identity"], now, now, _json(event), now),
                )
            db.execute("UPDATE lives SET state=?,revision=revision+1 WHERE identity=?", (_json(state), row["identity"]))

    def migrate_legacy(self, source: Path) -> dict:
        """Back up exact legacy bytes and import them as archival fiction/plans."""
        source = Path(source)
        paths = [source] if source.exists() else []
        history = source.parent / "history"
        if history.is_dir():
            paths.extend(sorted(history.glob("*.json")))
        imported, skipped = [], []
        now = self.clock()
        backup = self.path.parent / "legacy-backup"
        for path in paths:
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            payload = json.loads(raw.decode("utf-8-sig"))
            with self._db() as db:
                if db.execute("SELECT 1 FROM legacy_imports WHERE source_hash=?", (digest,)).fetchone():
                    skipped.append(str(path))
                    continue
                backup.mkdir(parents=True, exist_ok=True)
                target = backup / (digest[:16] + "-" + path.name)
                if not target.exists():
                    shutil.copyfile(path, target)
                if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                    raise NarrativeValidationError("legacy_backup_verification_failed", "Legacy backup verification failed")
                annotated = {
                    "schema_version": 1,
                    "source_path": str(path),
                    "sha256": digest,
                    "fact_kind": "fiction",
                    "status": "legacy",
                    "timeline_kind": "plan",
                    "original": payload,
                }
                db.execute(
                    "INSERT INTO legacy_imports VALUES(?,?,?,?,?)",
                    (digest, str(path), _json(annotated), "fiction", now),
                )
                imported.append(str(path))
        return {"schema_version": 1, "imported": imported, "skipped": skipped, "backup_dir": str(backup)}
