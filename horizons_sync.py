"""Lightweight bidirectional reading-bookmark sync from Dynamics Horizons (群间见闻)."""

from __future__ import annotations

import importlib.util as _ilu
import math
from pathlib import Path
import re
import sys as _sys
from typing import Any

if __package__:
    from .life.core.narrative_types import (
        NarrativeValidationError,
        _identity,
        normalize_scope,
    )
else:
    _types_mod = _sys.modules.get("_dls_narrative_types")
    if _types_mod is None:
        _spec = _ilu.spec_from_file_location(
            "_dls_narrative_types",
            Path(__file__).resolve().parent / "life" / "core" / "narrative_types.py",
        )
        _types_mod = _ilu.module_from_spec(_spec)
        _sys.modules["_dls_narrative_types"] = _types_mod
        _spec.loader.exec_module(_types_mod)
    NarrativeValidationError = _types_mod.NarrativeValidationError
    _identity = _types_mod._identity
    normalize_scope = _types_mod.normalize_scope

MAX_BOOKMARKS_PER_IDENTITY = 30
DESK_PROJECTION_LIMIT = 2

_RAW_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]+")
_SOURCE_KIND_RE = re.compile(r"^[a-z0-9_-]{1,40}$")


def _clean_field(value: Any, *, field: str, limit: int, required: bool = False) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise NarrativeValidationError("text_type", f"{field} must be a string")
    if len(value) > 4096:
        raise NarrativeValidationError(
            "text_length", f"{field} exceeds maximum wire size"
        )
    stripped = _RAW_URL_RE.sub("", value)
    stripped = _CTRL_RE.sub(" ", stripped).strip()
    if len(stripped) > limit:
        stripped = stripped[:limit].rstrip()
    if required and not stripped:
        raise NarrativeValidationError("field_required", f"{field} cannot be empty")
    return stripped


class HorizonSyncReceipt(dict):
    """Dict result that also supports optional `await` for sync/async caller compatibility."""

    def __await__(self):
        if False:
            yield None
        return self


class HorizonsSyncService:
    """Persist verified external reading bookmarks per character identity with zero LLM calls."""

    def __init__(self, engine: Any) -> None:
        self.engine = engine
        with self.engine._db() as db:
            self.ensure_table(db)

    @staticmethod
    def ensure_table(db: Any) -> None:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS world_horizon_bookmarks(
                log_id TEXT PRIMARY KEY,
                identity TEXT NOT NULL,
                source_kind TEXT NOT NULL,
                title TEXT NOT NULL,
                creator TEXT NOT NULL DEFAULT '',
                chapter_label TEXT NOT NULL DEFAULT '',
                digest TEXT NOT NULL,
                reflection TEXT NOT NULL DEFAULT '',
                occurred_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_world_horizon_bookmarks_identity_time
                ON world_horizon_bookmarks(identity, occurred_at DESC, log_id DESC);
            """
        )
        columns = {
            r[1] for r in db.execute("PRAGMA table_info(world_horizon_bookmarks)")
        }
        if "revision" not in columns:
            db.execute(
                "ALTER TABLE world_horizon_bookmarks ADD COLUMN revision INTEGER NOT NULL DEFAULT 1"
            )
        if "status" not in columns:
            db.execute(
                "ALTER TABLE world_horizon_bookmarks ADD COLUMN status TEXT NOT NULL DEFAULT 'active'"
            )

    def normalize_bookmark_scope(self, scope: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(scope, dict):
            raise NarrativeValidationError(
                "unsupported_scope_schema", "Scope must be a dict"
            )
        configured_persona = str(
            (self.engine.config or {}).get("persona_id") or ""
        ).strip()
        raw_persona = str(scope.get("persona_id") or "").strip()
        if not raw_persona or (
            raw_persona == "default"
            and configured_persona
            and configured_persona != "default"
        ):
            persona_id = configured_persona or raw_persona
        else:
            persona_id = raw_persona
        raw_instance = str(scope.get("instance_id") or "").strip()
        if not raw_instance or (
            raw_persona == "default"
            and raw_instance == "default"
            and persona_id != "default"
        ):
            instance_id = persona_id
        else:
            instance_id = raw_instance
        umo = str(scope.get("umo") or "").strip()
        platform = str(
            scope.get("platform") or (umo.split(":", 1)[0] if ":" in umo else "")
        ).strip()
        candidate = {
            "schema_version": scope.get("schema_version", 1),
            "platform": platform,
            "umo": umo,
            "persona_id": persona_id,
            "instance_id": instance_id,
        }
        return normalize_scope(candidate)

    def record_reading(
        self, scope: dict[str, Any], payload: dict[str, Any], *, owner: Any = None
    ) -> dict[str, Any]:
        """Validate & upsert one reading bookmark (bounded 30 per identity, zero LLM calls)."""
        if getattr(self.engine, "_closed", False):
            raise RuntimeError("Narrative engine is closed")
        norm_scope = self.normalize_bookmark_scope(scope)
        if not isinstance(payload, dict):
            raise NarrativeValidationError(
                "invalid_payload", "Bookmark payload must be a dict"
            )

        log_id = _clean_field(
            payload.get("log_id"), field="log_id", limit=160, required=True
        )
        revision = payload.get("revision", 1)
        if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
            raise NarrativeValidationError(
                "revision_type", "revision must be positive integer"
            )
        ident = _identity(norm_scope)
        with self.engine._db() as db:
            self.ensure_table(db)
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT identity,revision,status FROM world_horizon_bookmarks WHERE log_id=?",
                (log_id,),
            ).fetchone()
            if existing and existing["identity"] != ident:
                raise NarrativeValidationError(
                    "identity_mismatch", "Bookmark identity cannot change"
                )
            if existing and (
                revision < existing["revision"]
                or revision == existing["revision"]
                and existing["status"] == "revoked"
            ):
                return HorizonSyncReceipt(
                    {
                        "schema_version": 1,
                        "ok": True,
                        "recorded": False,
                        "stale": True,
                        "log_id": log_id,
                    }
                )
            if payload.get("operation") == "revoke":
                db.execute(
                    "INSERT INTO world_horizon_bookmarks(log_id,identity,source_kind,title,digest,occurred_at,revision,status) VALUES(?,?,'manual','','',?,?, 'revoked') ON CONFLICT(log_id) DO UPDATE SET revision=excluded.revision,status='revoked'",
                    (log_id, ident, float(self.engine.clock()), revision),
                )
                return HorizonSyncReceipt(
                    {"schema_version": 1, "ok": True, "revoked": True, "log_id": log_id}
                )
        raw_kind = _clean_field(
            payload.get("source_kind"), field="source_kind", limit=40, required=True
        ).lower()
        if not _SOURCE_KIND_RE.fullmatch(raw_kind):
            raise NarrativeValidationError("invalid_source_kind", "Invalid source_kind")
        title = _clean_field(
            payload.get("title"), field="title", limit=200, required=True
        )
        creator = _clean_field(
            payload.get("creator", ""), field="creator", limit=120, required=False
        )
        chapter_label = _clean_field(
            payload.get("chapter_label", ""),
            field="chapter_label",
            limit=120,
            required=False,
        )
        digest = _clean_field(
            payload.get("digest"), field="digest", limit=600, required=True
        )
        reflection = _clean_field(
            payload.get("reflection", ""), field="reflection", limit=600, required=False
        )

        raw_ts = payload.get("occurred_at")
        if raw_ts is None:
            occurred_at = float(self.engine.clock())
        else:
            if (
                isinstance(raw_ts, bool)
                or not isinstance(raw_ts, (int, float))
                or not math.isfinite(float(raw_ts))
                or float(raw_ts) < 0
            ):
                raise NarrativeValidationError(
                    "timestamp_type",
                    "occurred_at must be a non-negative finite timestamp",
                )
            occurred_at = float(raw_ts)

        ident = _identity(norm_scope)
        with self.engine._db() as db:
            self.ensure_table(db)
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute(
                "SELECT identity,revision,status FROM world_horizon_bookmarks WHERE log_id=?",
                (log_id,),
            ).fetchone()
            if existing and (
                existing["identity"] != ident
                or revision < existing["revision"]
                or revision == existing["revision"]
                and existing["status"] == "revoked"
            ):
                return HorizonSyncReceipt(
                    {
                        "schema_version": 1,
                        "ok": True,
                        "recorded": False,
                        "stale": True,
                        "log_id": log_id,
                    }
                )
            db.execute(
                """
                INSERT INTO world_horizon_bookmarks(
                    log_id, identity, source_kind, title, creator, chapter_label, digest, reflection, occurred_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(log_id) DO UPDATE SET
                    identity = excluded.identity,
                    source_kind = excluded.source_kind,
                    title = excluded.title,
                    creator = excluded.creator,
                    chapter_label = excluded.chapter_label,
                    digest = excluded.digest,
                    reflection = excluded.reflection,
                    occurred_at = excluded.occurred_at
                """,
                (
                    log_id,
                    ident,
                    raw_kind,
                    title,
                    creator,
                    chapter_label,
                    digest,
                    reflection,
                    occurred_at,
                ),
            )
            db.execute(
                "UPDATE world_horizon_bookmarks SET revision=?,status='active' WHERE log_id=?",
                (revision, log_id),
            )
            db.execute(
                """
                UPDATE world_horizon_bookmarks SET status='archived'
                WHERE identity = ? AND status='active'
                  AND log_id NOT IN (
                      SELECT log_id FROM world_horizon_bookmarks
                      WHERE identity = ? AND status='active'
                      ORDER BY occurred_at DESC, log_id DESC
                      LIMIT ?
                  )
                """,
                (ident, ident, MAX_BOOKMARKS_PER_IDENTITY),
            )
            retained = int(
                db.execute(
                    "SELECT COUNT(*) FROM world_horizon_bookmarks WHERE identity = ? AND status='active' ",
                    (ident,),
                ).fetchone()[0]
            )
            desk = self.desk_snapshot(db, norm_scope, limit=DESK_PROJECTION_LIMIT)

        owner_cb = getattr(owner, "on_db_write", None) if owner is not None else None
        if callable(owner_cb) and owner_cb is not getattr(
            self.engine, "on_db_write", None
        ):
            try:
                owner_cb()
            except Exception:
                pass

        return HorizonSyncReceipt(
            {
                "schema_version": 1,
                "ok": True,
                "recorded": True,
                "log_id": log_id,
                "identity": ident,
                "retained": retained,
                "horizons_desk": desk,
            }
        )

    def desk_snapshot(
        self, db: Any, scope: dict[str, Any], limit: int = DESK_PROJECTION_LIMIT
    ) -> list[dict[str, Any]]:
        """Return latest bounded reading bookmarks for snapshot['horizons_desk'] and 3D cabin."""
        try:
            norm_scope = self.normalize_bookmark_scope(scope)
        except Exception:
            return []
        ident = _identity(norm_scope)
        bounded = max(1, min(10, int(limit or DESK_PROJECTION_LIMIT)))
        try:
            rows = db.execute(
                """
                SELECT log_id, source_kind, title, creator, chapter_label, digest, reflection, occurred_at
                FROM world_horizon_bookmarks
                WHERE identity = ? AND status='active'
                ORDER BY occurred_at DESC, log_id DESC
                LIMIT ?
                """,
                (ident, bounded),
            ).fetchall()
        except Exception:
            return []
        return [
            {
                "log_id": str(row["log_id"]),
                "source_kind": str(row["source_kind"]),
                "title": str(row["title"]),
                "creator": str(row["creator"] or ""),
                "chapter_label": str(row["chapter_label"] or ""),
                "digest": str(row["digest"]),
                "reflection": str(row["reflection"] or ""),
                "occurred_at": float(row["occurred_at"]),
            }
            for row in rows
        ]
