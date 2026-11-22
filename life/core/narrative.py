"""Persistent narrative state and scoped events for Dynamics World.

Only this module writes narrative data. Public methods accept schema-v1 plain
dictionaries; every SQLite operation closes its connection before returning.
"""

from __future__ import annotations

import asyncio
import copy
import datetime as dt
import hashlib
import json
import re
import sqlite3
import threading
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from astrbot.api import logger

if __package__:
    from ...series_panels import (
        is_series_group_excluded,
        is_series_in_quiet_hours,
        resolve_series_timezone,
        resolve_series_timezone_name,
    )
    from .narrative_ddl import NarrativeSchemaMixin
    from .narrative_io import WorldIO, WorldIOClosed
    from .narrative_outreach import NarrativeOutreachMixin
    from .narrative_types import (
        ACTIVITIES,
        AVAILABILITIES,
        CHINA,
        COMMITMENT_STATUSES,
        FACT_KINDS,
        INTENT_STATUSES,
        TERMINAL_INTENTS,
        NarrativeValidationError,
        _identity,
        _json,
        _text,
        _timestamp,
        normalize_scope,
    )
    from .narrative_validation import NarrativeValidationMixin
else:
    import importlib.util as _ilu
    import sys as _sys

    def _load_sibling(mod_key: str, filename: str):
        mod = _sys.modules.get(mod_key)
        if mod is None:
            spec = _ilu.spec_from_file_location(
                mod_key, Path(__file__).with_name(filename)
            )
            mod = _ilu.module_from_spec(spec)
            _sys.modules[mod_key] = mod
            spec.loader.exec_module(mod)
        return mod

    _types_mod = _load_sibling("_dls_narrative_types", "narrative_types.py")
    _outreach_mod = _load_sibling("_dls_narrative_outreach", "narrative_outreach.py")
    _schema_mod = _load_sibling("_dls_narrative_ddl", "narrative_ddl.py")
    _io_mod = _load_sibling("_dls_narrative_io", "narrative_io.py")
    _validation_mod = _load_sibling(
        "_dls_narrative_validation", "narrative_validation.py"
    )
    CHINA = _types_mod.CHINA
    FACT_KINDS = _types_mod.FACT_KINDS
    AVAILABILITIES = _types_mod.AVAILABILITIES
    ACTIVITIES = _types_mod.ACTIVITIES
    COMMITMENT_STATUSES = _types_mod.COMMITMENT_STATUSES
    INTENT_STATUSES = _types_mod.INTENT_STATUSES
    TERMINAL_INTENTS = _types_mod.TERMINAL_INTENTS
    NarrativeValidationError = _types_mod.NarrativeValidationError
    _json = _types_mod._json
    _text = _types_mod._text
    _timestamp = _types_mod._timestamp
    normalize_scope = _types_mod.normalize_scope
    _identity = _types_mod._identity

    def is_series_group_excluded(context, umo: str = "", group_id: str = "") -> bool:
        return False

    def is_series_in_quiet_hours(context) -> bool:
        return False

    def resolve_series_timezone_name(
        context, explicit_tz: str = "", default_tz: str = "Asia/Shanghai"
    ) -> str:
        return str(explicit_tz or default_tz or "Asia/Shanghai").strip() or "Asia/Shanghai"

    def resolve_series_timezone(
        context, explicit_tz: str = "", default_tz: str = "Asia/Shanghai"
    ):
        return CHINA
    NarrativeOutreachMixin = _outreach_mod.NarrativeOutreachMixin
    NarrativeSchemaMixin = _schema_mod.NarrativeSchemaMixin
    NarrativeValidationMixin = _validation_mod.NarrativeValidationMixin
    WorldIO = _io_mod.WorldIO
    WorldIOClosed = _io_mod.WorldIOClosed

_DEBUG_LEVEL = 10
_INFO_LEVEL = 20


def _snapshot_scope_hash(scope: dict) -> str:
    encoded = json.dumps(scope, sort_keys=True, allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()[:32]


class _NarrativeConnection(sqlite3.Connection):
    """Track committed rows even when a caller explicitly commits mid-operation."""

    _previous_changes = 0
    explicitly_committed_changes = False

    @property
    def pending_changes(self) -> bool:
        return self.in_transaction and self.total_changes > self._previous_changes

    def commit(self) -> None:
        changed = self.pending_changes
        super().commit()
        self.explicitly_committed_changes |= changed
        self._previous_changes = self.total_changes

    def rollback(self) -> None:
        super().rollback()
        self._previous_changes = self.total_changes


def _resolve_horizons_sync_cls():
    if __package__:
        try:
            from ...horizons_sync import HorizonsSyncService

            return HorizonsSyncService
        except Exception:
            pass
    import importlib.util as _ilu
    import sys as _sys

    mod = _sys.modules.get("_dw_horizons_sync")
    if mod is None:
        sync_path = Path(__file__).resolve().parents[2] / "horizons_sync.py"
        spec = _ilu.spec_from_file_location("_dw_horizons_sync", sync_path)
        mod = _ilu.module_from_spec(spec)
        _sys.modules["_dw_horizons_sync"] = mod
        spec.loader.exec_module(mod)
    return mod.HorizonsSyncService


class NarrativeEngine(
    NarrativeSchemaMixin, NarrativeValidationMixin, NarrativeOutreachMixin
):
    """Own durable life, revisions, budgets and intents for one configured persona.

    Args:
        path: Narrative database file.
        config: Live plugin config, including explicit narrative session allowlist.
        model: Async callback receiving the isolated narrative input dictionary.
        clock: Injectable epoch clock for deterministic simulation.
        owner_active: Current World runtime permission check for public snapshots.
    """

    _world_map_v1 = True
    _horizons_sync_v1 = True

    def __init__(
        self,
        path: Path,
        config: Any,
        model: Callable[[dict], Awaitable[dict]],
        clock: Callable[[], float] = time.time,
        *,
        owner_active: Callable[[], bool] | None = None,
        host_context: Any = None,
    ):
        self.path, self.config, self.model, self.clock = (
            Path(path),
            config,
            model,
            clock,
        )
        self.host_context = host_context
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, asyncio.Lock] = {}
        self._plan_regens: set[str] = set()
        self._outreach_lock = asyncio.Lock()
        self._closed = False
        self._owner_active = owner_active
        self._snapshot_io = WorldIO(
            max_workers=2,
            max_pending=32,
            max_waiters=64,
            thread_name_prefix="world-snapshot",
        )
        self.spatial = None
        self.environment = None
        self.scenes = None
        self.visuals = None
        self.causal = None
        self.world_spaces = None
        self.ecology = None
        self.keepsakes = None
        self.mailbox = None
        self.horizons = None
        self._context_generation = 0
        self.on_db_write: Callable[[], None] | None = None
        self.on_activity: Callable[[], None] | None = None
        self._last_activity_at: float | None = None
        self._quiet_ticks: dict[str, int] = {"narrative": 0, "resident": 0}
        self._last_tick_activity_seen: dict[str, float | None] = {
            "narrative": None,
            "resident": None,
        }
        self._generation_lock = threading.Lock()
        self._backup_before_retry_extension()
        self._backup_before_v20_extension()
        self._initialize()
        self.horizons = _resolve_horizons_sync_cls()(self)

    @contextmanager
    def _db(self, *, notify=True):
        conn = sqlite3.connect(self.path, timeout=5, factory=_NarrativeConnection)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        wrote = False

        def authorize(action, _first, _second, _database, _trigger):
            nonlocal wrote
            if not wrote and action in {
                sqlite3.SQLITE_INSERT,
                sqlite3.SQLITE_UPDATE,
                sqlite3.SQLITE_DELETE,
                sqlite3.SQLITE_CREATE_TABLE,
                sqlite3.SQLITE_ALTER_TABLE,
                sqlite3.SQLITE_DROP_TABLE,
            }:
                wrote = True
                with self._generation_lock:
                    self._context_generation += 1
            return sqlite3.SQLITE_OK

        conn.set_authorizer(authorize)
        committed = False
        try:
            with conn:
                yield conn
                pending = conn.pending_changes
            committed = pending
        finally:
            committed |= conn.explicitly_committed_changes
            conn.close()
            if wrote:
                with self._generation_lock:
                    self._context_generation += 1
            if notify and committed:
                self._notify_db_write()

    def _notify_db_write(self) -> None:
        cb = self.on_db_write
        if callable(cb):
            try:
                cb()
            except Exception:
                pass

    def note_activity(self, now: float | None = None) -> float:
        """Record real chat or member interaction and reset quiet tick backoff."""
        ts = self.clock() if now is None else float(now)
        if self._last_activity_at is None or ts >= self._last_activity_at:
            self._last_activity_at = ts
        for kind in self._quiet_ticks:
            self._quiet_ticks[kind] = 0
        cb = self.on_activity
        if callable(cb):
            try:
                cb()
            except Exception:
                pass
        return self._last_activity_at

    def effective_tick_interval(
        self,
        base_seconds: float = 300.0,
        *,
        kind: str = "narrative",
        now: float | None = None,
    ) -> float:
        """Step up background tick interval (5m -> 15m -> 30m -> 2h -> 4h) during quiet periods."""
        base = max(60.0, float(base_seconds))
        steps = (base, base * 3.0, base * 6.0, base * 24.0, base * 48.0)
        ts = self.clock() if now is None else float(now)
        streak = max(0, int(self._quiet_ticks.get(kind, 0)))
        time_stage = 0
        if self._last_activity_at is not None:
            idle = max(0.0, ts - self._last_activity_at)
            if idle >= base * 48.0:
                time_stage = 4
            elif idle >= base * 24.0:
                time_stage = 3
            elif idle >= base * 9.0:
                time_stage = 2
            elif idle >= base * 3.0:
                time_stage = 1
        stage = min(len(steps) - 1, max(streak, time_stage))
        return steps[stage]

    def record_background_tick(
        self,
        *,
        kind: str = "narrative",
        now: float | None = None,
    ) -> float:
        """Advance quiet streak when no new member activity occurred since last tick."""
        had_new_activity = (
            self._last_activity_at is not None
            and self._last_activity_at != self._last_tick_activity_seen.get(kind)
        )
        if had_new_activity:
            self._quiet_ticks[kind] = 0
            self._last_tick_activity_seen[kind] = self._last_activity_at
        else:
            self._quiet_ticks[kind] = min(4, int(self._quiet_ticks.get(kind, 0)) + 1)
        return self.effective_tick_interval(300.0, kind=kind, now=now)

    def peek_context_revision(self, scope):
        """Return an in-memory epoch before/after writes without touching SQLite."""
        scope = normalize_scope(scope)
        if not self._allowed(scope):
            return {"schema_version": 1, "available": False}
        with self._generation_lock:
            return {
                "schema_version": 1,
                "available": True,
                "generation": self._context_generation,
            }

    def _timezone_name(self, explicit_tz: str = "") -> str:
        cfg_tz = str(self.config.get("timezone", "") or "") if isinstance(self.config, dict) or hasattr(self.config, "get") else ""
        return resolve_series_timezone_name(
            getattr(self, "host_context", None),
            explicit_tz=str(explicit_tz or cfg_tz or ""),
        )

    def _timezone(self, explicit_tz: str = ""):
        cfg_tz = str(self.config.get("timezone", "") or "") if isinstance(self.config, dict) or hasattr(self.config, "get") else ""
        return resolve_series_timezone(
            getattr(self, "host_context", None),
            explicit_tz=str(explicit_tz or cfg_tz or ""),
        )

    def is_managed(self, scope: dict) -> bool:
        """Return whether the concrete persona manages this full UMO."""
        try:
            scope = normalize_scope(scope)
        except ValueError:
            return False
        if (
            self._closed
            or self.config.get("mode", "legacy") != "narrative"
            or scope["persona_id"] != str(self.config.get("persona_id", ""))
        ):
            return False
        umo = scope["umo"]
        if is_series_group_excluded(getattr(self, "host_context", None), umo=umo):
            return False
        if self._private_peer(umo):
            return (
                self.config.get("narrative_private_chat_enabled", False) is True
                and scope["platform"] == umo.split(":", 1)[0]
            )
        return self._group_scope(umo) and (
            self.config.get("narrative_all_groups", False) is True
            or umo in (self.config.get("narrative_sessions", []) or [])
        )

    @staticmethod
    def _session_id(umo: str, message_type: str) -> str:
        parts = umo.split(":", 2)
        return parts[2] if len(parts) == 3 and parts[0] and parts[1].lower() == message_type else ""

    @classmethod
    def _group_scope(cls, umo: str) -> bool:
        return bool(cls._session_id(umo, "groupmessage"))

    @classmethod
    def _private_peer(cls, umo: str) -> str:
        return cls._session_id(umo, "friendmessage")

    def _has_targets(self) -> bool:
        return (
            self.config.get("narrative_all_groups", False) is True
            or self.config.get("narrative_private_chat_enabled", False) is True
            or any(
                isinstance(item, str) and self._group_scope(item)
                for item in (self.config.get("narrative_sessions", []) or [])
            )
        )

    def _global_scope(self) -> dict:
        return normalize_scope(
            {
                "platform": "",
                "umo": "",
                "persona_id": str(self.config.get("persona_id", "")),
            }
        )

    def _allowed(self, scope: dict) -> bool:
        return self.is_managed(scope) or (
            not scope["umo"]
            and self.config.get("mode", "legacy") == "narrative"
            and scope["persona_id"] == str(self.config.get("persona_id", ""))
            and self._has_targets()
            and not self._closed
        )

    def _ensure(self, db, scope: dict, now: float) -> None:
        identity = _identity(scope)
        if (
            db.execute("SELECT 1 FROM lives WHERE identity=?", (identity,)).fetchone()
            and db.execute(
                "SELECT 1 FROM scopes WHERE identity=? AND umo=?",
                (identity, scope["umo"]),
            ).fetchone()
        ):
            return
        global_scope = dict(scope, umo="", platform="")
        state = {
            "activity": "未知",
            "activity_code": "unknown",
            "availability": "unknown",
            "subjective_state": "",
            "summary": "",
            "source_ids": [],
            "valid_from": now,
            "valid_until": now,
            "next_check": now,
            "plan": [],
            "plan_date": "",
            "clock_schema_version": 2,
        }
        db.execute(
            "INSERT OR IGNORE INTO lives(identity,scope,state,updated) VALUES(?,?,?,?)",
            (identity, _json(global_scope), _json(state), now),
        )
        db.execute(
            "INSERT OR IGNORE INTO scopes(identity,umo,state) VALUES(?,?,?)",
            (
                identity,
                scope["umo"],
                _json({"subjective_state": "", "summary": "", "source_ids": []}),
            ),
        )

    def _snapshot(self, db, scope: dict, now: float) -> dict:
        self._ensure(db, scope, now)
        if self.causal is not None:
            self.causal.advance(db, scope, now)
        if self.spatial is not None:
            self.spatial.settle(db, scope, now)
        if self.scenes is not None:
            self.scenes.settle(db, scope, now)
        scene = (
            self.scenes.snapshot(db, scope, now) if self.scenes is not None else None
        )
        spatial = (
            self.spatial.snapshot(db, scope, now) if self.spatial is not None else None
        )
        environment = (
            self.environment.snapshot(db, scope, now, spatial)
            if self.environment is not None
            else None
        )
        visual = (
            self.visuals.snapshot(db, scope, now, spatial, scene, environment)
            if self.visuals is not None
            else None
        )
        identity = _identity(scope)
        row = db.execute("SELECT * FROM lives WHERE identity=?", (identity,)).fetchone()
        local = db.execute(
            "SELECT * FROM scopes WHERE identity=? AND umo=?", (identity, scope["umo"])
        ).fetchone()
        state, scoped = json.loads(row["state"]), json.loads(local["state"])
        raw_scene_state = (
            self.scenes.load(db, scope)[2] if self.scenes is not None else None
        )
        if self.ecology is not None:
            self.ecology.settle(db, scope, environment, raw_scene_state, now)
        if self.mailbox is not None:
            self.mailbox.settle(db, scope, raw_scene_state, spatial, now)
        if self.world_spaces is not None:
            self.world_spaces.settle(db, scope, now, spatial)
        recent_mail_at = (
            self.mailbox.latest_opened_at(db, scope)
            if self.mailbox is not None
            else 0.0
        )
        ecology_snap = (
            self.ecology.snapshot(
                db,
                scope,
                now,
                life_state=state,
                scene_state=raw_scene_state,
                env=environment,
                actor=spatial,
                recent_mail_at=recent_mail_at,
            )
            if self.ecology is not None
            else None
        )
        keepsakes_snap = (
            self.keepsakes.snapshot(db, scope, raw_scene_state, now)
            if self.keepsakes is not None
            else None
        )
        mailbox_snap = (
            self.mailbox.snapshot(db, scope, now) if self.mailbox is not None else None
        )
        world_space_snap = (
            self.world_spaces.snapshot(db, scope, now)
            if self.world_spaces is not None
            else None
        )
        horizons_desk = (
            self.horizons.desk_snapshot(db, scope, limit=2)
            if getattr(self, "horizons", None) is not None
            else []
        )
        if self.keepsakes is not None and not scope["umo"]:
            cur = (environment or {}).get("current") or {}
            designs = (scene or {}).get("room_designs") or []
            self.keepsakes.record_keyframe(
                db,
                scope,
                "ambient",
                str(
                    (scene or {}).get("action", {}).get("label")
                    if (scene or {}).get("action")
                    else state.get("activity", "")
                ),
                {
                    "timezone": (environment or {}).get("timezone")
                    or self._timezone_name(),
                    "weather": cur.get("effect", "clear"),
                    "weather_label": cur.get("label", "晴"),
                    "temperature": cur.get("temperature"),
                    "curtains": (designs[0].get("curtains") if designs else None)
                    or "open",
                    "lighting": (designs[0].get("lighting") if designs else None)
                    or "warm",
                    "location": "away"
                    if (spatial or {}).get("phase") == "travelling"
                    else ("room" if (scene or {}).get("room_id") else "garden"),
                    "place_name": (scene or {}).get("place_name")
                    or (spatial or {}).get("place_name")
                    or "",
                    "pose": "sleep"
                    if state.get("availability") == "asleep"
                    else "idle",
                    "cat_spot": ((ecology_snap or {}).get("cat") or {}).get(
                        "spot", "bed_nap"
                    ),
                },
                now,
            )
        activity_revision = state.get("activity_revision", row["revision"])
        scoped_current = (
            scoped.get("activity_revision") == activity_revision
            and float(scoped.get("valid_until", 0)) > now
        )
        commitments = [
            json.loads(item[0])
            for item in db.execute(
                "SELECT payload FROM commitments WHERE identity=? AND umo=? ORDER BY commitment_id",
                (identity, scope["umo"]),
            )
        ]
        for commitment in commitments:
            if commitment.get("status") not in {"committed", "conditional", "proposed"}:
                continue
            participants = set(commitment.get("participant_ids") or [])
            for source in commitment.get("source_ids", [])[:50]:
                evidence = db.execute(
                    "SELECT payload FROM events WHERE event_id=? AND identity=? AND umo=?",
                    (source, identity, scope["umo"]),
                ).fetchone()
                if evidence:
                    item = json.loads(evidence[0])
                    if item.get("type") in {
                        "message.received",
                        "chat.message",
                    } and item.get("actor_id") not in {"", "bot", "system", None}:
                        participants.add(item["actor_id"])
                    if item.get("type") == "delivery.success" and item.get(
                        "data", {}
                    ).get("recipient_user_id"):
                        participants.add(item["data"]["recipient_user_id"])
            commitment["participant_ids"] = sorted(participants)
        expired = float(state["valid_until"]) <= now
        if scene and scene.get("action"):
            # A program-owned action remains authoritative even if the last
            # narrative prose expired during a long journey or global pause.
            current_step = scene["action"]["steps"][scene["action"]["index"]]["kind"]
            state = dict(
                state,
                availability="available"
                if current_step in {"read", "read_notes", "rest", "dry"}
                or scene["action"].get("activity_code") == "gaming"
                else "busy",
                valid_until=max(now + 60, scene["action"]["step_ends_at"]),
            )
            expired = False
        # Personal interests can outlive an activity. Conversation-derived
        # material remains local; no participant text enters shared life.
        humanlike = {
            key: []
            for key in (
                "preferences",
                "goals",
                "moods",
                "nicknames",
                "corrections",
                "interests",
            )
        }
        for owner, saved in (("personal", state), ("conversation", scoped)):
            if owner == "conversation" and not scope["umo"]:
                continue
            for key in humanlike:
                for item in saved.get("humanlike", {}).get(key, {}).values():
                    if key in {"goals", "moods"} and (
                        item.get("expires_at", 0) <= now
                        or item.get("status") == "settled"
                    ):
                        continue
                    presentation = dict(item, origin=owner)
                    if key == "moods":
                        presentation["strength"] = round(
                            2 ** (-max(0, now - item["updated_at"]) / 600), 3
                        )
                    humanlike[key].append(presentation)
        return {
            "schema_version": 1,
            "managed": self._allowed(scope),
            "scope": copy.deepcopy(scope),
            "revision": row["revision"],
            "scope_revision": local["revision"],
            "activity": (
                self.scenes.activity(
                    scene,
                    self.spatial.activity(
                        spatial, state["activity"] if not expired else "未知"
                    )
                    if spatial
                    else state["activity"]
                    if not expired
                    else "未知",
                )
                if self.scenes is not None
                else self.spatial.activity(
                    spatial, state["activity"] if not expired else "未知"
                )
                if spatial
                else state["activity"]
                if not expired
                else "未知"
            )
            + (
                self.environment.brief(environment)
                if self.environment is not None
                else ""
            ),
            "spatial": spatial,
            "environment": environment,
            "scene": scene,
            "visual_sharing": visual,
            "ecology": ecology_snap,
            "keepsakes": keepsakes_snap,
            "mailbox": mailbox_snap,
            "world_space": world_space_snap,
            "horizons_desk": horizons_desk,
            "availability": state["availability"] if not expired else "unknown",
            "subjective_state": (scoped["subjective_state"] if scoped_current else "")
            or (state["subjective_state"] if not expired else ""),
            "summary": (scoped["summary"] if scoped_current else "")
            or (state["summary"] if not expired else ""),
            "commitments": commitments,
            "global_presentation": {
                k: state.get(k, "") if not expired else ""
                for k in ("subjective_state", "summary")
            },
            "scoped_presentation": (
                {
                    **{
                        k: scoped.get(k)
                        for k in (
                            "subjective_state",
                            "summary",
                            "source_ids",
                            "participant_ids",
                            "occurred_at",
                        )
                    },
                    "valid_until": scoped.get("valid_until", 0),
                }
                if scoped_current
                else {}
            ),
            "source_ids": list(
                dict.fromkeys(
                    state["source_ids"]
                    + (scoped["source_ids"] if scoped_current else [])
                )
            ),
            "scoped_presentation_stale": bool(
                scoped["summary"] or scoped["subjective_state"]
            )
            and not scoped_current,
            "valid_from": state["valid_from"],
            "valid_until": state["valid_until"],
            "activity_started_at": state.get("activity_started_at"),
            "narrated_until": state.get("narrated_until", state["valid_from"]),
            "energy": (
                self.causal.projection(db, scope, now)["body"]
                if self.causal is not None
                else self._energy(state, now)
            ),
            "causal_life": self.causal.projection(db, scope, now, viewer="actor")
            if self.causal is not None
            else None,
            "humanlike": humanlike,
            "stale": expired,
            "paused": self._paused(db, scope),
            "outreach_paused": self._outreach_paused(db, scope),
        }

    @staticmethod
    def _energy(state, now):
        # Only the confirmed interval counts. Legacy refreshed valid_from is not
        # evidence of when rest started, and expired time is never inferred.
        start = state.get("activity_started_at")
        if start is None:
            return {
                "level": "unknown",
                "fact_kind": "subjective",
                "basis": "activity_start_unknown",
            }
        elapsed = max(0, min(now, state["valid_until"]) - start)
        resting = (
            state.get("activity_code") in {"sleeping", "resting"}
            or state.get("availability") == "asleep"
        )
        threshold = 4 * 3600 if state.get("availability") == "asleep" else 1800
        level = (
            ("recovered" if elapsed >= threshold else "recovering")
            if resting
            else "normal"
        )
        return {
            "level": level,
            "confirmed_activity_seconds": round(elapsed),
            "fact_kind": "subjective",
            "basis": "confirmed_activity_interval",
            "previous_rest_seconds": state.get("previous_rest_seconds", 0),
        }

    async def get_snapshot(self, scope: dict) -> dict:
        """Return scoped state without making a model call or inventing a life."""
        scope = normalize_scope(scope)
        unavailable = {"schema_version": 1, "managed": False, "scope": scope}
        if not self._snapshot_allowed(scope):
            return unavailable
        key = tuple(scope[name] for name in ("platform", "umo", "persona_id", "instance_id"))
        try:
            result = await self._snapshot_io.run(
                self._read_snapshot, scope, key=key, scope_hash=_snapshot_scope_hash(scope)
            )
        except WorldIOClosed:
            return unavailable
        if not self._snapshot_allowed(scope) or not result["managed"]:
            return unavailable
        return copy.deepcopy(result)

    def _snapshot_allowed(self, scope: dict) -> bool:
        return self._allowed(scope) and (
            self._owner_active is None or self._owner_active()
        )

    def _read_snapshot(self, scope: dict) -> dict:
        unavailable = {"schema_version": 1, "managed": False, "scope": scope}
        if not self._snapshot_allowed(scope):
            return unavailable
        started = time.perf_counter()
        began = executed = None
        stage = "begin"
        try:
            with self._db() as db:
                db.execute("BEGIN IMMEDIATE")
                began = time.perf_counter()
                stage = "permission"
                if not self._snapshot_allowed(scope):
                    return unavailable
                stage = "execute"
                result = self._snapshot(db, scope, self.clock())
                executed = time.perf_counter()
                # Seal before releasing the writer lock. A later caller may follow
                # an intervening committed pause or correction.
                self._snapshot_io.seal_current()
                stage = "permission"
                if not self._snapshot_allowed(scope):
                    db.rollback()
                    return unavailable
                stage = "commit"
            stage = "done"
            return result
        finally:
            finished = time.perf_counter()
            begin_ms = ((began or finished) - started) * 1000
            level = _INFO_LEVEL if begin_ms >= 500 or finished - started >= 1 else _DEBUG_LEVEL
            if logger.isEnabledFor(level):
                logger.log(
                    level,
                    "World snapshot scope_hash=%s session_id=%s stage=%s "
                    "begin_ms=%.1f execute_ms=%.1f finish_ms=%.1f",
                    _snapshot_scope_hash(scope),
                    hashlib.sha256(scope["umo"].encode()).hexdigest()[:32],
                    stage,
                    begin_ms,
                    ((executed or finished) - began) * 1000 if began is not None else 0,
                    (finished - executed) * 1000 if executed is not None else 0,
                )

    def _paused(self, db, scope: dict) -> bool:
        keys = (
            "paused",
            "paused:" + _identity(scope),
            "paused:" + _identity(scope) + ":" + scope["umo"],
        )
        rows = db.execute(
            "SELECT value FROM metadata WHERE key IN (?,?,?)", keys
        ).fetchall()
        return any(row[0] == "true" for row in rows)

    def _event(self, event: dict, now: float) -> dict:
        if not isinstance(event, dict) or event.get("schema_version", 1) != 1:
            raise NarrativeValidationError(
                "unsupported_event_schema", "Unsupported event schema"
            )
        scope = normalize_scope(event.get("scope", {}))
        event_id = _text(event.get("event_id", ""), 300, "event_id")
        kind = _text(event.get("type", ""), 100, "type")
        if not event_id or not kind:
            raise NarrativeValidationError(
                "event_id_and_type_are_required", "Event ID and type are required"
            )
        occurred = _timestamp(event.get("occurred_at", now), "occurred_at")
        received = _timestamp(event.get("received_at", now), "received_at")
        fact_kind = event.get("fact_kind", "observation")
        if fact_kind not in FACT_KINDS:
            raise NarrativeValidationError("unknown_fact_kind", "Unknown fact kind")
        if kind.startswith("delivery."):
            fact_kind = "receipt"
        data = event.get("data", {})
        if not isinstance(data, dict) or len(_json(data)) > 24000:
            raise NarrativeValidationError("invalid_event_data", "Invalid event data")
        source_ids = event.get("source_ids", [event_id])
        if (
            not isinstance(source_ids, list)
            or len(source_ids) > 50
            or not all(isinstance(item, str) for item in source_ids)
        ):
            raise NarrativeValidationError(
                "invalid_event_sources", "Invalid event sources"
            )
        return {
            "schema_version": 1,
            "event_id": event_id,
            "type": kind,
            "occurred_at": occurred,
            "received_at": received,
            "scope": scope,
            "actor_id": _text(event.get("actor_id", ""), 300, "actor_id"),
            "text": _text(event.get("text", ""), 12000),
            "source_ids": source_ids,
            "fact_kind": fact_kind,
            "data": copy.deepcopy(data),
        }

    async def ingest_events(self, events: list[dict]) -> dict:
        """Persist observed input and delivery receipts idempotently before inference."""
        now = self.clock()
        validated = [self._event(event, now) for event in events]
        accepted, duplicate, ignored = [], [], []
        saw_activity = False
        with self._db() as db:
            for event in validated:
                scope, event_id = event["scope"], event["event_id"]
                if not self._allowed(scope):
                    ignored.append(event_id)
                    continue
                peer = self._private_peer(scope["umo"])
                if peer and (
                    (event["type"] in {"message.received", "chat.message"} and event["actor_id"] != peer)
                    or (event["type"] == "delivery.success" and event["data"].get("recipient_user_id") != peer)
                ):
                    ignored.append(event_id)
                    continue
                payload = _json(event)
                old = db.execute(
                    "SELECT payload FROM events WHERE event_id=?", (event_id,)
                ).fetchone()
                if old:
                    if old[0] != payload:
                        raise NarrativeValidationError(
                            "an_event_id_cannot_be_reused_with_different_content",
                            "An event ID cannot be reused with different content",
                        )
                    duplicate.append(event_id)
                    continue
                self._ensure(db, scope, now)
                db.execute(
                    "INSERT INTO events(event_id,identity,umo,occurred,received,payload,created) VALUES(?,?,?,?,?,?,?)",
                    (
                        event_id,
                        _identity(scope),
                        scope["umo"],
                        event["occurred_at"],
                        event["received_at"],
                        payload,
                        now,
                    ),
                )
                accepted.append(event_id)
                if scope["umo"] and event["type"] in {
                    "message.received",
                    "chat.message",
                    "delivery.success",
                }:
                    saw_activity = True
                self._observe_outreach_preference(db, event)
                self._cancel_care_on_input(db, event, now)
                # Explicit self-address objections take effect on ingestion,
                # even when narrative inference is paused or out of budget.
                if (
                    scope["umo"]
                    and event["type"] in {"message.received", "chat.message"}
                    and event["actor_id"] not in {"", "bot", "system"}
                ):
                    local = json.loads(
                        db.execute(
                            "SELECT state FROM scopes WHERE identity=? AND umo=?",
                            (_identity(scope), scope["umo"]),
                        ).fetchone()[0]
                    )
                    names = local.get("humanlike", {}).get("nicknames", {})
                    previous_name = names.get(event["actor_id"], {})
                    spoken = event["text"].strip().rstrip("。.!！,，~～")
                    explicit = bool(
                        previous_name.get("nickname")
                        and re.fullmatch(
                            r"(?:别|不要|别再|不要再)叫我"
                            + re.escape(previous_name["nickname"]),
                            spoken,
                        )
                    )
                    addressed = event["data"].get(
                        "directed_to_bot"
                    ) is True and spoken in {
                        "别这么叫我",
                        "别再这么叫我",
                        "不要这么叫我",
                        "别这样叫我",
                        "不要这样叫我",
                        "别给我起外号",
                        "不要给我起外号",
                    }
                    if (explicit or addressed) and event[
                        "occurred_at"
                    ] >= previous_name.get("updated_at", 0):
                        names = local.setdefault("humanlike", {}).setdefault(
                            "nicknames", {}
                        )
                        if event["actor_id"] in names or len(names) < 1024:
                            names[event["actor_id"]] = {
                                "subject_id": event["actor_id"],
                                "nickname": previous_name.get("nickname", ""),
                                "status": "rejected",
                                "evidence_quote": spoken,
                                "source_ids": [event_id],
                                "participant_ids": [event["actor_id"]],
                                "updated_at": now,
                                "fact_kind": "observation",
                            }
                            db.execute(
                                "UPDATE scopes SET state=?,revision=revision+1 WHERE identity=? AND umo=?",
                                (_json(local), _identity(scope), scope["umo"]),
                            )
                            db.execute(
                                "UPDATE lives SET revision=revision+1 WHERE identity=?",
                                (_identity(scope),),
                            )
                self._ingest_behavior_feedback(db, event, now)
                if event["type"] in {
                    "delivery.success",
                    "delivery.failure",
                    "delivery.uncertain",
                }:
                    self._delivery_intent(db, event, now)
                if event["type"] == "delivery.success":
                    self._confirm_delivery(db, event, now)
                if (
                    event["type"] == "execution.success"
                    and event["data"].get("effect_confirmed") is True
                ):
                    self._apply_reminder_effect(db, event)
                if self._record_only(event):
                    db.execute(
                        "UPDATE events SET status='observed_only' WHERE event_id=?",
                        (event_id,),
                    )
        if saw_activity:
            self.note_activity(now)
        return {
            "schema_version": 1,
            "accepted": accepted,
            "duplicate": duplicate,
            "ignored": ignored,
        }

    def _record_only(self, event):
        """Evidence stays stored even if no narrative inference is warranted."""
        if self._private_peer(event["scope"]["umo"]):
            return True
        data = event.get("data", {})
        if event["type"] in {"delivery.failure", "delivery.uncertain", "tool.receipt"}:
            return True
        if event["type"] != "message.received":
            return False
        if data.get("event_impact") in {
            "activity",
            "commitment",
            "relationship",
        } or data.get("directed_to_bot"):
            return False
        # For old queues without classifier metadata, keep potential commitments
        # and boundaries. Do not claim the narrator processed discarded chatter.
        text = event.get("text", "")
        signals = (
            "答应",
            "约定",
            "取消",
            "提醒",
            "别再",
            "不要再",
            "不喜欢",
            "承诺",
            "说好了",
            "安安",
        )
        return not any(word in text for word in signals)

    _GROUP_SIGNAL_CUES = (
        "答应",
        "约定",
        "取消",
        "提醒",
        "别再",
        "不要再",
        "不喜欢",
        "承诺",
        "说好了",
        "头疼",
        "头痛",
        "发烧",
        "生病",
        "不舒服",
        "难受",
        "医院",
        "吃药",
        "出门",
        "出差",
        "回家",
        "到家",
        "报平安",
        "路上",
        "飞机",
        "高铁",
        "火车",
        "叫我",
        "外号",
        "昵称",
        "纠正",
        "误会",
        "简短",
        "不要主动",
        "别主动",
    )

    _GROUP_SIGNAL_DATA_KEYS = (
        "commitment_id",
        "commitments",
        "completed_commitment_ids",
        "reminder_id",
        "intent_id",
        "goal_id",
        "interest_id",
        "care_activity_id",
    )

    def _is_low_signal_group_batch(self, scope: dict, pending: list[dict]) -> bool:
        """Return True when a group-chat batch is strictly non-bot-directed ambient chatter."""
        if not pending or not self._group_scope(scope.get("umo", "")):
            return False
        for event in pending:
            etype = event.get("type", "")
            if etype not in {"message.received", "chat.message"}:
                return False
            data = event.get("data") or {}
            if (
                data.get("directed_to_bot") is True
                or data.get("addressed") is True
                or bool(data.get("quoted_message_id"))
                or data.get("event_impact") in {"activity", "commitment", "relationship"}
                or any(data.get(k) for k in self._GROUP_SIGNAL_DATA_KEYS)
            ):
                return False
            # Preserve legacy chat.message callers that omit directed_to_bot metadata;
            # only treat chat.message as ambient when explicitly marked directed_to_bot=False.
            if etype == "chat.message" and data.get("directed_to_bot") is not False:
                return False
            text = str(event.get("text") or "")
            if any(cue in text for cue in self._GROUP_SIGNAL_CUES):
                return False
        return True

    def _apply_reminder_effect(self, db, event):
        data, scope = event["data"], event["scope"]
        action = data.get("effect_kind")
        if action not in {"reminder.sent", "reminder.cancelled"} or not data.get(
            "reminder_id"
        ):
            return
        changed = False
        for row in db.execute(
            "SELECT payload FROM commitments WHERE identity=? AND umo=?",
            (_identity(scope), scope["umo"]),
        ).fetchall():
            item = json.loads(row[0])
            if item.get("reminder_id") != data["reminder_id"] or item["status"] in {
                "completed",
                "cancelled",
                "expired",
            }:
                continue
            item["status"] = "completed" if action == "reminder.sent" else "cancelled"
            item["source_ids"] = list(
                dict.fromkeys(item["source_ids"] + [event["event_id"]])
            )
            self._store_commitment(db, scope, item)
            changed = True
        if changed:
            db.execute(
                "UPDATE lives SET revision=revision+1 WHERE identity=?",
                (_identity(scope),),
            )
            db.execute(
                "UPDATE scopes SET revision=revision+1 WHERE identity=? AND umo=?",
                (_identity(scope), scope["umo"]),
            )

    def _compact_old_queue(self, db, identity, limit=500):
        # Rotate through the queue: a protected first page must not starve later
        # rows forever. Historical evidence is retained, never called processed.
        key = "queue_compaction_cursor:" + identity
        saved = db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
        prev_cursor = int(saved[0]) if saved else 0
        rows = db.execute(
            "SELECT rowid,event_id,payload FROM events WHERE identity=? AND status='pending' AND rowid>? ORDER BY rowid LIMIT ?",
            (identity, prev_cursor, limit),
        ).fetchall()
        now = self.clock()
        for row in rows:
            event = json.loads(row["payload"])
            if self._record_only(event):
                db.execute(
                    "UPDATE events SET status='observed_only',error='routing:no_significant_impact' WHERE event_id=?",
                    (row["event_id"],),
                )
            elif self._obsolete_chatter(event, now):
                db.execute(
                    "UPDATE events SET status='historical_only',error='routing:expired_live_context' WHERE event_id=?",
                    (row["event_id"],),
                )
        cursor = rows[-1]["rowid"] if len(rows) == limit else 0
        if cursor != prev_cursor or (rows and saved is None):
            db.execute(
                "INSERT INTO metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, str(cursor)),
            )

    @staticmethod
    def _obsolete_chatter(event, now):
        if event["occurred_at"] >= now - 86400 or event["type"] not in {
            "message.received",
            "chat.message",
            "delivery.success",
        }:
            return False
        data = event.get("data", {})
        if data.get("event_impact") in {"commitment", "relationship"} or any(
            data.get(k)
            for k in (
                "commitment_id",
                "commitments",
                "reminder_id",
                "intent_id",
                "completed_commitment_ids",
                "interest_id",
            )
        ):
            return False
        # Preserve explicit agreements, corrections and boundaries for review.
        protected = (
            "答应",
            "约定",
            "提醒",
            "承诺",
            "说好了",
            "别",
            "不要",
            "不喜欢",
            "以后",
            "撤销",
            "纠正",
            "理解错",
            "误会",
            "叫我",
        )
        return not any(word in event.get("text", "") for word in protected)

    def _delivery_intent(self, db, event: dict, now: float) -> None:
        """Recover an interrupted final status update from the durable receipt."""
        intent_id = event["data"].get("intent_id")
        if not isinstance(intent_id, str) or not intent_id:
            return
        row = db.execute(
            "SELECT * FROM intents WHERE intent_id=?", (intent_id,)
        ).fetchone()
        if (
            row is None
            or row["identity"] != _identity(event["scope"])
            or row["umo"] != event["scope"]["umo"]
        ):
            return
        status = {
            "delivery.success": "sent",
            "delivery.failure": "failed",
            "delivery.uncertain": "uncertain",
        }[event["type"]]
        item = json.loads(row["payload"])
        if row["status"] not in {"claimed", "uncertain"} and not (
            row["status"] == "cancelled"
            and item.get("kind") in {"care_wait", "social_chat"}
            and item.get("claimed_at")
        ):
            return
        # An actual receipt may resolve crash uncertainty without ever reopening
        # the intention for another send. Public status updates alone cannot.
        previous_attempt = item.get("receipt", {}).get("attempt_id")
        incoming_attempt = event["data"].get("attempt_id")
        if previous_attempt and incoming_attempt != previous_attempt:
            return
        item.update(
            status=status,
            receipt={
                "event_id": event["event_id"],
                "attempt_id": event["data"].get("attempt_id"),
                "message_id": event["data"].get("message_id"),
                "type": event["type"],
            },
        )
        db.execute(
            "UPDATE intents SET status=?,payload=?,updated=? WHERE intent_id=?",
            (status, _json(item), now, intent_id),
        )

    def _confirm_delivery(self, db, event: dict, now: float) -> None:
        """Confirm proposed commitments only from a matched actual sent segment."""
        scope, data = event["scope"], event["data"]
        candidates = data.get("commitments", [])
        if not isinstance(candidates, list):
            return
        changed = False
        for candidate in candidates[:10]:
            if not isinstance(candidate, dict):
                continue
            quote = candidate.get("evidence_quote", "")
            if not quote or quote not in event["text"]:
                continue
            candidate = dict(
                candidate, source_ids=[event["event_id"]], status="committed"
            )
            try:
                item = self._commitment(
                    candidate, scope, {event["event_id"]: event}, now
                )
                self._store_commitment(db, scope, item)
                changed = True
            except ValueError:
                # Invalid extracted promises do not erase the actual receipt.
                continue
        if changed:
            db.execute(
                "UPDATE lives SET revision=revision+1 WHERE identity=?",
                (_identity(scope),),
            )
            db.execute(
                "UPDATE scopes SET revision=revision+1 WHERE identity=? AND umo=?",
                (_identity(scope), scope["umo"]),
            )

    def _reserve(
        self, db, identity: str, kind: str, now: float, *, umo: str = ""
    ) -> bool:
        hour = int(now // 3600)
        maximum = 1 if kind == "hourly" else 2 if kind == "weather" else 6
        if kind == "extra" and umo:
            # Separate conversation queues must not consume each other's six
            # inference slots. Global life/weather retain their original budgets.
            kind = "extra:" + hashlib.sha256(umo.encode()).hexdigest()[:16]
        row = db.execute(
            "SELECT used FROM budgets WHERE identity=? AND hour=? AND kind=?",
            (identity, hour, kind),
        ).fetchone()
        if row and row[0] >= maximum:
            return False
        db.execute(
            "INSERT INTO budgets VALUES(?,?,?,1) ON CONFLICT(identity,hour,kind) DO UPDATE SET used=used+1",
            (identity, hour, kind),
        )
        return True

    @staticmethod
    def _retry_delay(attempt: int) -> float:
        """Return the durable backoff for the just-failed attempt."""
        return (600, 1200, 2400, 3600)[min(max(int(attempt), 1), 4) - 1]

    def _pending_state(self, db, scope: dict, now: float) -> tuple[list[dict], str]:
        """Read one complete FIFO batch; a deferred/blocked head stops this scope."""
        rows = db.execute(
            "SELECT event_id,payload,occurred,received,retry_attempt,next_retry,error,LENGTH(CAST(payload AS BLOB)) payload_bytes "
            "FROM events WHERE identity=? AND umo=? AND status='pending' "
            "ORDER BY occurred,received,event_id LIMIT 33",
            (_identity(scope), scope["umo"]),
        ).fetchall()
        if not rows:
            return [], "no_change"
        head = rows[0]
        backlog = float(head["occurred"]) < now - 86400
        batch_limit, byte_limit = (32, 24000) if backlog else (16, 12000)
        if float(head["occurred"]) > now or float(head["received"]) > now:
            return [], "not_due"
        if float(head["next_retry"]) > now:
            return [], "retry_deferred"
        if str(head["error"]).startswith("oversized_payload_bytes:"):
            return [], "oversized_blocked"
        if int(head["payload_bytes"]) > 60000:
            db.execute(
                "UPDATE events SET error=? WHERE event_id=? AND status='pending'",
                (
                    f"oversized_payload_bytes:{int(head['payload_bytes'])}",
                    head["event_id"],
                ),
            )
            return [], "oversized_blocked"

        isolate = False
        if str(head["error"]).startswith("validation."):
            previous = db.execute(
                "SELECT event_ids FROM validation_failures WHERE EXISTS "
                "(SELECT 1 FROM json_each(event_ids) WHERE value=?) ORDER BY occurred DESC LIMIT 1",
                (head["event_id"],),
            ).fetchone()
            failed_ids = set(json.loads(previous[0])) if previous else set()
            # New evidence may supply the missing execution receipt or a
            # correction. Keep that dependency closure in the next FIFO batch.
            isolate = bool(
                failed_ids and all(row["event_id"] in failed_ids for row in rows)
            )
        result, size = [], 0
        for row in rows:
            if (
                float(row["occurred"]) > now
                or float(row["received"]) > now
                or float(row["next_retry"]) > now
            ):
                break
            if str(row["error"]).startswith("oversized_payload_bytes:"):
                break
            payload_bytes = int(row["payload_bytes"])
            if payload_bytes > 60000:
                db.execute(
                    "UPDATE events SET error=? WHERE event_id=? AND status='pending'",
                    (f"oversized_payload_bytes:{payload_bytes}", row["event_id"]),
                )
                break
            if result and (
                len(result) >= batch_limit or size + payload_bytes > byte_limit
            ):
                break
            if not result and payload_bytes > byte_limit:
                # Complete oversized-to-target events go alone, never truncated.
                result.append(json.loads(row["payload"]))
                break
            result.append(json.loads(row["payload"]))
            size += payload_bytes
            if isolate:
                # Isolate invalid batches while preserving FIFO and all source
                # dependencies. A bad model output is not a bad source event.
                break
        return result, "ready" if result else "oversized_blocked"

    def _pending(self, db, scope: dict, now: float) -> list[dict]:
        """Compatibility helper for callers that only need eligible events."""
        return self._pending_state(db, scope, now)[0]

    def _record_failure(self, events: list[dict], now: float, error: str) -> None:
        """Persist a bounded retry deadline without resolving any queue item."""
        if not events:
            return
        with self._db() as db:
            db.execute(
                "INSERT INTO validation_failures VALUES(?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    _json([e["event_id"] for e in events]),
                    error[:100],
                    now,
                ),
            )
            for event in events:
                row = db.execute(
                    "SELECT retry_attempt FROM events WHERE event_id=? AND status='pending'",
                    (event["event_id"],),
                ).fetchone()
                if row is None:
                    continue
                attempt = int(row[0]) + 1
                retry_at = now + self._retry_delay(attempt)
                db.execute(
                    "UPDATE events SET retry_attempt=?,next_retry=?,error=? WHERE event_id=? AND status='pending'",
                    (attempt, retry_at, error[:80], event["event_id"]),
                )

    def _block_policy_refusal(self, events: list[dict]) -> None:
        """Retain policy-refused evidence outside the automatic inference queue."""
        if not events:
            return
        with self._db() as db:
            for event in events:
                db.execute(
                    "UPDATE events SET status='blocked_policy',error='policy_refusal' "
                    "WHERE event_id=? AND status='pending'",
                    (event["event_id"],),
                )

    @staticmethod
    def _is_policy_refusal(exc: Exception) -> bool:
        """Match only the provider's explicit PROHIBITED_CONTENT refusal marker."""
        values = [
            getattr(exc, name, None)
            for name in ("code", "status", "reason", "finish_reason", "block_reason")
        ]
        for value in values:
            if value is None:
                continue
            name = getattr(value, "name", None)
            candidates = (str(value), str(name) if name is not None else "")
            if any(
                candidate.strip().upper() == "PROHIBITED_CONTENT"
                for candidate in candidates
            ):
                return True
        error_text = str(exc).strip()
        return error_text.upper() == "PROHIBITED_CONTENT" or bool(
            re.search(
                r"(?:reason|finish_reason|block_reason|code|status)\s*['\"]?\s*[=:]\s*['\"]?PROHIBITED_CONTENT\b",
                error_text,
                re.IGNORECASE,
            )
        )

    def _hourly_event(self, scope: dict, when: float) -> dict:
        """Reuse the exact first tick bytes for a persona/hour on retries."""
        event_id = f"life.tick:{_identity(scope)}:{int(when // 3600)}"
        with self._db() as db:
            row = db.execute(
                "SELECT payload FROM events WHERE event_id=?", (event_id,)
            ).fetchone()
            if row:
                return json.loads(row[0])
        return {
            "event_id": event_id,
            "type": "life.tick",
            "occurred_at": when,
            "received_at": when,
            "scope": scope,
            "text": "Advance life only until this time, without conversation data.",
            "fact_kind": "fiction",
        }

    async def advance(
        self,
        events: list[dict],
        expected_revision: int | None = None,
        *,
        _as_of: float | None = None,
    ) -> dict:
        """Advance one scope; inference never holds a database transaction open.

        Cancellation or timeout leaves the queue durable. A concurrent correction
        invalidates the model result by a final optimistic revision check.
        """
        if not events:
            return {"schema_version": 1, "status": "no_events", "event_impact": "none"}
        scope = normalize_scope(events[0]["scope"])
        if any(normalize_scope(event["scope"]) != scope for event in events):
            raise NarrativeValidationError(
                "a_narrative_batch_must_have_exactly_one_scope",
                "A narrative batch must have exactly one scope",
            )
        await self.ingest_events(events)
        if not self._allowed(scope):
            return {
                "schema_version": 1,
                "status": "unmanaged",
                "snapshot": {"managed": False},
                "event_impact": "none",
            }
        if self._private_peer(scope["umo"]):
            # Private messages provide scoped outreach evidence without changing shared life.
            return self._result("no_change", await self.get_snapshot(scope))
        identity = _identity(scope)
        if scope["umo"]:
            # Advance overdue private-free life to the incoming event boundary
            # first. Inference below still processes only this conversation.
            boundary = min(
                self.clock(),
                min(
                    _timestamp(event.get("occurred_at", self.clock()))
                    for event in events
                ),
            )
            with self._db() as db:
                before = self._snapshot(db, scope, self.clock())
                life = json.loads(
                    db.execute(
                        "SELECT state FROM lives WHERE identity=?", (identity,)
                    ).fetchone()[0]
                )
                due = (
                    before["revision"] > 0
                    and life["valid_from"] <= boundary
                    and min(life["valid_until"], life["next_check"]) <= boundary
                    and not self._paused(db, scope)
                )
                if (
                    expected_revision is not None
                    and expected_revision != before["revision"]
                ):
                    return self._result("stale", before)
            if due:
                global_scope = dict(scope, umo="", platform="")
                tick = self._hourly_event(global_scope, boundary)
                result = await self.advance(
                    [tick], expected_revision=before["revision"], _as_of=boundary
                )
                if result["status"] in {"advanced", "no_change"}:
                    with self._db() as db:
                        db.execute(
                            "INSERT INTO maintenance VALUES(?,'hourly',?) ON CONFLICT(identity,kind) DO UPDATE SET last=MAX(last,excluded.last)",
                            (identity, boundary),
                        )
                    if expected_revision is not None:
                        expected_revision = result["snapshot"]["revision"]
        async with self._locks.setdefault(identity, asyncio.Lock()):
            now = self.clock() if _as_of is None else min(self.clock(), _as_of)
            with self._db() as db:
                snapshot = self._snapshot(db, scope, now)
                if self._paused(db, scope):
                    return self._result("paused", snapshot)
                if (
                    expected_revision is not None
                    and expected_revision != snapshot["revision"]
                ):
                    return self._result("stale", snapshot)
                pending, queue_status = self._pending_state(db, scope, now)
                if not pending:
                    if queue_status == "no_change" and any(
                        db.execute(
                            "SELECT 1 FROM events WHERE event_id=? AND identity=? AND umo=? AND status='blocked_policy'",
                            (event["event_id"], identity, scope["umo"]),
                        ).fetchone()
                        for event in events
                    ):
                        return self._result("policy_refusal", snapshot)
                    return self._result(queue_status, snapshot)
                if self._is_low_signal_group_batch(scope, pending):
                    for event in pending:
                        db.execute(
                            "UPDATE events SET status='observed_only',error='routing:low_signal_group_ambient' WHERE event_id=?",
                            (event["event_id"],),
                        )
                    local_row = db.execute(
                        "SELECT state FROM scopes WHERE identity=? AND umo=?",
                        (identity, scope["umo"]),
                    ).fetchone()
                    if local_row:
                        local_state = json.loads(local_row[0])
                        local_state["observed_until"] = now
                        db.execute(
                            "UPDATE scopes SET state=? WHERE identity=? AND umo=?",
                            (_json(local_state), identity, scope["umo"]),
                        )
                    return self._result("no_change", self._snapshot(db, scope, now))
                triggers = {event.get("data", {}).get("trigger") for event in pending}
                if not all(event["type"] == "life.tick" for event in pending):
                    kind = "extra"
                elif triggers - {"world_action_completed", "weather_change"}:
                    kind = "hourly"
                elif "world_action_completed" in triggers:
                    kind = "action"
                else:
                    kind = "weather"
                if not self._reserve(db, identity, kind, now, umo=scope["umo"]):
                    return self._result("budget_exhausted", snapshot)
                life = json.loads(
                    db.execute(
                        "SELECT state FROM lives WHERE identity=?", (identity,)
                    ).fetchone()[0]
                )
                diary = [
                    dict(row)
                    for row in db.execute(
                        "SELECT occurred,text,fact_kind,source_ids FROM diary WHERE identity=? AND umo=? ORDER BY occurred DESC LIMIT 8",
                        (identity, scope["umo"]),
                    )
                ]
                care_waits = [
                    dict(json.loads(r["payload"]), status=r["status"])
                    for r in db.execute(
                        "SELECT payload,status FROM intents WHERE identity=? AND umo=? ORDER BY updated DESC LIMIT 100",
                        (identity, scope["umo"]),
                    )
                    if json.loads(r["payload"]).get("kind") == "care_wait"
                ]
            tz = self._timezone()
            tz_name = self._timezone_name()
            local_date = dt.datetime.fromtimestamp(now, tz).date()
            day_end = dt.datetime.combine(
                local_date + dt.timedelta(days=1), dt.time(), tz
            ).timestamp()
            request = {
                "schema_version": 1,
                "scope": scope,
                "now": now,
                "day_end": day_end,
                "local_datetime": dt.datetime.fromtimestamp(now, tz).isoformat(),
                "timezone": tz_name,
                "local_date": local_date.isoformat(),
                "plan_window": {"start": now, "end": day_end},
                "snapshot": snapshot,
                "events": pending,
                "recent_diary": diary,
                "plan": life["plan"],
                "needs_daily_plan": life["plan_date"] != local_date.isoformat(),
                "weather_reassessment": not scope["umo"]
                and any(
                    e["type"] == "life.tick"
                    and e.get("data", {}).get("trigger") == "weather_change"
                    for e in pending
                ),
                "offline_catchup": bool(
                    life["valid_from"] < now - 7200 and life["valid_from"] > 0
                ),
            }
            if self.causal is not None and not scope["umo"]:
                with self._db() as db:
                    request["background_world"] = (
                        None
                        if getattr(self, "resident_runner", None) is not None
                        else self.causal.background_request(db, scope, now)
                    )
                    request["causal_revision"] = self.causal.load(db, scope)[0]
                    request["background_only"] = bool(
                        request["background_world"]
                        and snapshot.get("availability") == "asleep"
                    )
            # Keep earlier scoped affect as attributed evidence, not the next
            # turn's assumed starting mood. Global life remains authoritative.
            request["snapshot"] = dict(
                snapshot, **snapshot.get("global_presentation", {})
            )
            participants = {
                str(e.get("actor_id", ""))
                for e in pending
                if e["type"] in {"message.received", "chat.message"}
            }
            participants.update(
                str(e.get("data", {}).get("recipient_user_id", ""))
                for e in pending
                if e["type"] == "delivery.success"
            )
            request["snapshot"]["humanlike"] = copy.deepcopy(snapshot["humanlike"])
            request["care_policy"] = {
                "enabled": self._outreach_enabled("care_wait", scope),
                "min_wait_seconds": 1800,
            }
            request["snapshot"]["care_waits"] = [
                r for r in care_waits if r.get("recipient_user_id") in participants
            ]
            with self._db() as db:
                failed = db.execute(
                    "SELECT error,retry_attempt FROM events WHERE event_id=?",
                    (pending[0]["event_id"],),
                ).fetchone()
            if failed and failed["error"].startswith("validation."):
                request["previous_validation_failure"] = {
                    "reason_code": failed["error"],
                    "attempt": failed["retry_attempt"],
                    "instruction": "Correct this field using only current evidence; omit unsupported effects. no_change is valid.",
                }
            for key in ("moods", "nicknames", "corrections"):
                request["snapshot"]["humanlike"][key] = [
                    r
                    for r in snapshot["humanlike"][key]
                    if r["subject_id"] in participants
                ]
            request["snapshot"]["humanlike"]["interests"] = [
                r
                for r in snapshot["humanlike"]["interests"]
                if r.get("origin") != "conversation"
                or set(r.get("participant_ids", [])) <= participants
            ]
            started = time.monotonic()
            call_id = str(uuid.uuid4())
            request["inference_call_id"] = call_id
            raw = None
            try:
                timeout = max(
                    1.0,
                    min(float(self.config.get("narrative_timeout_seconds", 90)), 90.0),
                )
                raw = await asyncio.wait_for(
                    self.model(copy.deepcopy(request)), timeout
                )
                change = self._validate_change(raw, request)
            except asyncio.CancelledError:
                self._call(
                    call_id, identity, scope["umo"], now, started, "cancelled", kind
                )
                raise
            except Exception as exc:
                if self._is_policy_refusal(exc):
                    self._call(
                        call_id,
                        identity,
                        scope["umo"],
                        now,
                        started,
                        "policy_refusal",
                        kind,
                    )
                    self._block_policy_refusal(pending)
                    return self._result(
                        "policy_refusal", await self.get_snapshot(scope)
                    )
                requested_status = getattr(exc, "status_code", "")
                status = (
                    requested_status
                    if requested_status == "provider_unavailable"
                    else ("timeout" if isinstance(exc, TimeoutError) else "invalid")
                )
                self._call(call_id, identity, scope["umo"], now, started, status, kind)
                code = (
                    "validation." + exc.code
                    if isinstance(exc, NarrativeValidationError)
                    else type(exc).__name__
                )
                http_status = getattr(exc, "code", None)
                if type(http_status) is int and 400 <= http_status <= 599:
                    # Preserve actionable status without logging request bodies,
                    # provider URLs, credentials or arbitrary error messages.
                    code = f"provider.http_{http_status}.{type(exc).__name__}"
                self._record_failure(pending, self.clock(), code)
                if (
                    self.causal is not None
                    and not scope["umo"]
                    and isinstance(raw, dict)
                    and raw.get("world_updates")
                ):
                    with self._db() as db:
                        self.causal.receipt(
                            db,
                            scope,
                            "rejected:" + call_id,
                            "proposal.rejected",
                            self.clock(),
                            {
                                "summary": "居民提案未执行",
                                "reason": code,
                                "origin": "system",
                                "observers": [],
                            },
                        )
                if self.scenes is not None:
                    self.scenes.record_rejection(scope, raw, code, pending)
                return self._result(status, await self.get_snapshot(scope))
            # A config switch or unload revokes permission before commit.
            if not self._allowed(scope):
                self._call(
                    call_id, identity, scope["umo"], now, started, "unmanaged", kind
                )
                return self._result("unmanaged", {"managed": False})
            try:
                with self._db() as db:
                    db.execute("BEGIN IMMEDIATE")
                    current = self._snapshot(db, scope, self.clock())
                    if current["revision"] != snapshot["revision"] or self._paused(
                        db, scope
                    ):
                        status = "stale"
                    else:
                        self._commit(
                            db, scope, change, pending, now, snapshot["revision"] + 1
                        )
                        status = "no_change" if change["no_change"] else "advanced"
                    result = self._snapshot(db, scope, self.clock())
            except (ValueError, sqlite3.Error) as exc:
                # A late invalid ownership/transition must roll back the whole
                # update, leave events queued, and preserve usable prior state.
                status = "invalid"
                code = (
                    "validation." + exc.code
                    if isinstance(exc, NarrativeValidationError)
                    else type(exc).__name__
                )
                self._record_failure(pending, self.clock(), code)
                if self.scenes is not None:
                    self.scenes.record_rejection(scope, raw, code, pending)
                result = await self.get_snapshot(scope)
            self._call(call_id, identity, scope["umo"], now, started, status, kind)
            return self._result(
                status, result, change["event_impact"] if status != "stale" else "none"
            )

    @staticmethod
    def _result(status: str, snapshot: dict, impact: str = "none") -> dict:
        return {
            "schema_version": 1,
            "status": status,
            "snapshot": snapshot,
            "event_impact": impact,
        }

    def _call(
        self,
        call_id: str,
        identity: str,
        umo: str,
        now: float,
        started: float,
        status: str,
        kind: str,
    ) -> None:
        with self._db() as db:
            db.execute(
                "INSERT INTO calls VALUES(?,?,?,?,?,?,?)",
                (
                    call_id,
                    identity,
                    umo,
                    now,
                    max(0.0, time.monotonic() - started),
                    status,
                    kind,
                ),
            )

    def _commit(
        self,
        db,
        scope: dict,
        change: dict,
        events: list[dict],
        now: float,
        revision: int,
    ) -> None:
        identity = _identity(scope)
        life = json.loads(
            db.execute(
                "SELECT state FROM lives WHERE identity=?", (identity,)
            ).fetchone()[0]
        )
        if self.causal is not None:
            if (
                change.get("causal_revision") is not None
                and self.causal.load(db, scope)[0] != change["causal_revision"]
            ):
                raise ValueError("生活日程或居民在推演期间已变化")
            self.causal.advance(db, scope, now)
            self.causal.commit_updates(db, scope, change.get("world_updates"), now)
            if change.get("served_residents"):
                cr, cd = self.causal.load(db, scope)
                for aid in change["served_residents"]:
                    if aid in cd["residents"]:
                        cd["residents"][aid]["last_served"] = now
                self.causal.save(db, scope, cr, cd, bump=False)
            if change.get("agenda_changes"):
                causal_rev, causal_doc = self.causal.load(db, scope)
                self.causal.revise_agenda(causal_doc, change["agenda_changes"], now)
                self.causal.save(db, scope, causal_rev, causal_doc)
                life["plan"] = self.causal.projected_plan(causal_doc)
        if change.get("background_only"):
            for event in events:
                db.execute(
                    "UPDATE events SET status='processed',error='',retry_attempt=0,next_retry=0 WHERE event_id=?",
                    (event["event_id"],),
                )
            return
        old_activity = (life.get("activity_code"), life.get("availability"))
        old_valid_until = life["valid_until"]
        previous_revision = db.execute(
            "SELECT revision FROM lives WHERE identity=?", (identity,)
        ).fetchone()[0]
        life.setdefault("activity_revision", previous_revision)
        local_row = db.execute(
            "SELECT state,revision FROM scopes WHERE identity=? AND umo=?",
            (identity, scope["umo"]),
        ).fetchone()
        local = json.loads(local_row[0])
        source_ids = [event["event_id"] for event in events]
        target = local if scope["umo"] else life
        saved = target.setdefault("humanlike", {})
        for kind, rows in change.get("humanlike", {}).items():
            bucket = saved.setdefault(kind, {})
            for item in rows:
                item_id = (
                    item.get("id")
                    if kind in {"corrections", "interests"}
                    else item.get("subject_id", item.get("id"))
                )
                previous = bucket.get(item_id, {})
                if (
                    kind == "interests"
                    and previous
                    and set(previous.get("participant_ids", []))
                    != set(item.get("participant_ids", []))
                ):
                    raise NarrativeValidationError(
                        "interest_owner_changed", "Interest ownership cannot change"
                    )
                if kind in {"corrections", "interests", "moods"} and previous.get(
                    "updated_at", 0
                ) > item.get("updated_at", 0):
                    continue
                if item.get("status") in {"removed", "dropped"}:
                    bucket.pop(item_id, None)
                else:
                    bucket[item_id] = item
            if kind in {"goals", "moods"}:
                saved[kind] = bucket = {
                    k: v for k, v in bucket.items() if v["expires_at"] > now
                }
            # Never evict nickname objections to make room for another name.
            capacity = {
                "preferences": 8,
                "goals": 4,
                "moods": 128,
                "nicknames": 1024,
                "corrections": 2048,
                "interests": 32,
            }[kind]
            if len(bucket) > capacity:
                raise NarrativeValidationError(
                    "humanlike_storage_capacity_reached",
                    "Humanlike storage capacity reached",
                )
        for key, value in change["state"].items():
            if change["no_change"] and key == "valid_until" and old_valid_until <= now:
                # The model saw an unknown/expired snapshot. An empty response
                # cannot silently resurrect its historical activity or sleep.
                continue
            if scope["umo"] and key in {"summary", "subjective_state"}:
                local[key] = value
            elif not scope["umo"] or (
                not change["no_change"]
                and any(k in change["state"] for k in ("activity_code", "availability"))
            ):
                life[key] = value
        projected = bool(
            scope["umo"]
            and not change["no_change"]
            and any(k in change["state"] for k in ("activity_code", "availability"))
        )
        if not scope["umo"] or projected:
            life.update(valid_from=now, next_check=change["next_check"])
        if not scope["umo"]:
            life["narrated_until"] = now
        else:
            local["observed_until"] = now
        if (life.get("activity_code"), life.get("availability")) != old_activity:
            life["activity_revision"] = revision
            if (
                old_activity[1] == "asleep" or old_activity[0] == "resting"
            ) and life.get("activity_started_at") is not None:
                life["previous_rest_seconds"] = max(
                    0, min(now, old_valid_until) - life["activity_started_at"]
                )
            life["activity_started_at"] = now
        elif (
            not scope["umo"]
            and not change["no_change"]
            and "activity_code" in change["state"]
        ):
            life.setdefault("activity_started_at", now)
        if scope["umo"]:
            if any(key in change["state"] for key in ("summary", "subjective_state")):
                # A partial new presentation must not inherit the old speaker's
                # other field and relabel it with this batch's sources.
                for key in ("summary", "subjective_state"):
                    if key not in change["state"]:
                        local[key] = ""
                local["source_ids"] = source_ids
                local["activity_revision"] = life["activity_revision"]
                local["valid_until"] = min(float(life["valid_until"]), now + 600)
                local["occurred_at"] = now
                local["participant_ids"] = sorted(
                    {
                        str(e.get("actor_id"))
                        for e in events
                        if e.get("type") in {"message.received", "chat.message"}
                        and e.get("actor_id") not in {None, "", "bot", "system"}
                    }
                    | {
                        str(e.get("data", {}).get("recipient_user_id"))
                        for e in events
                        if e.get("type") == "delivery.success"
                        and e.get("data", {}).get("recipient_user_id")
                    }
                )
            # Global state keeps no private source IDs, text, names or summaries.
        else:
            life["source_ids"] = source_ids
        if change["daily_plan"] is not None:
            life["plan"] = change["daily_plan"]
            if self.causal is not None:
                self.causal.sync_plan(db, scope, life["plan"], now)
            life["plan_date"] = dt.datetime.fromtimestamp(now, self._timezone()).date().isoformat()
        db.execute(
            "UPDATE lives SET revision=?,state=?,updated=? WHERE identity=?",
            (revision, _json(life), now, identity),
        )
        db.execute(
            "UPDATE scopes SET revision=revision+1,state=? WHERE identity=? AND umo=?",
            (_json(local), identity, scope["umo"]),
        )
        for row in change["diary"]:
            db.execute(
                "INSERT INTO diary VALUES(?,?,?,?,?,?,?,?)",
                (
                    str(uuid.uuid4()),
                    identity,
                    scope["umo"],
                    row["occurred_at"],
                    row["text"],
                    row["fact_kind"],
                    _json(row["source_ids"]),
                    revision,
                ),
            )
        for item in change["commitments"]:
            self._store_commitment(db, scope, item)
        for item in change["contact_intents"]:
            if not self._care_current(db, item):
                continue
            item["revision"] = revision
            old = db.execute(
                "SELECT identity,umo FROM intents WHERE intent_id=?",
                (item["intent_id"],),
            ).fetchone()
            if old and (old[0] != identity or old[1] != scope["umo"]):
                raise NarrativeValidationError(
                    "an_intent_cannot_change_ownership",
                    "An intent cannot change ownership",
                )
            # Identical source motivation cannot create unlimited follow-ups.
            duplicates = db.execute(
                "SELECT payload FROM intents WHERE identity=? AND umo=?",
                (identity, scope["umo"]),
            )
            if any(
                json.loads(row[0])["source_ids"] == item["source_ids"]
                for row in duplicates
            ):
                continue
            if item.get("reminder_id"):
                item["status"] = "cancelled"
            db.execute(
                "INSERT OR IGNORE INTO intents VALUES(?,?,?,?,?,?,?,?)",
                (
                    item["intent_id"],
                    identity,
                    scope["umo"],
                    _json(item),
                    item["status"],
                    item["not_before"],
                    item["expires_at"],
                    now,
                ),
            )
        for event in events:
            db.execute(
                "UPDATE events SET status='processed',error='',retry_attempt=0,next_retry=0 WHERE event_id=?",
                (event["event_id"],),
            )
        if change.get("movement"):
            self.spatial.commit(db, scope, change["movement"], now)
        if change.get("world_action"):
            self.scenes.commit(
                db,
                scope,
                change["world_action"],
                now,
                origin="life_model",
                source_event_ids=[e["event_id"] for e in events],
            )
            if self.causal is not None and change.get("plan_id"):
                flow = self.scenes.load(db, scope)[2].get("flow")
                if flow:
                    self.causal.attach_action(
                        db, scope, change["plan_id"], flow["id"], now
                    )
        elif self.causal is not None and change.get("plan_id"):
            self.causal.attach_interval(db, scope, change["plan_id"], life, now)
        if change["daily_plan"] is not None and self.scenes is not None and self.causal is not None:
            from ...cabin_life import reconcile_committed_plan
            reconcile_committed_plan(self, db, scope, now)

    async def list_due_intents(self, now: float | None = None) -> list[dict]:
        """Return current pending motivations; caller must claim before sending."""
        now = self.clock() if now is None else _timestamp(now)
        if is_series_in_quiet_hours(getattr(self, "host_context", None)):
            return []
        result = []
        with self._db() as db:
            db.execute(
                "UPDATE intents SET status='expired',updated=? WHERE expires<=? AND status IN ('pending','failed')",
                (now, now),
            )
            for row in db.execute(
                "SELECT * FROM intents WHERE status='pending' AND not_before<=? AND expires>? ORDER BY not_before LIMIT 100",
                (now, now),
            ):
                item = json.loads(row["payload"])
                if not self.is_managed(item["scope"]) or self._paused(
                    db, item["scope"]
                ):
                    continue
                if self._outreach_paused(db, item["scope"]):
                    continue
                if not self._care_current(db, item):
                    db.execute(
                        "UPDATE intents SET status='cancelled',updated=? WHERE intent_id=?",
                        (now, item["intent_id"]),
                    )
                    continue
                item.update(status=row["status"])
                result.append(item)
        return result

    async def update_intent(
        self, intent_id: str, status: str, receipt: dict | None = None
    ) -> dict:
        """Perform durable intent lifecycle transitions without automatic resends."""
        if status not in INTENT_STATUSES:
            raise NarrativeValidationError(
                "unsupported_intent_status", "Unsupported intent status"
            )
        now = self.clock()
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM intents WHERE intent_id=?", (intent_id,)
            ).fetchone()
            if not row:
                return {"schema_version": 1, "status": "missing"}
            item = json.loads(row["payload"])
            if row["status"] in TERMINAL_INTENTS:
                return {"schema_version": 1, "status": row["status"], "changed": False}
            if status == "claimed":
                if not self._care_current(db, item):
                    db.execute(
                        "UPDATE intents SET status='cancelled',updated=? WHERE intent_id=?",
                        (now, intent_id),
                    )
                    return {
                        "schema_version": 1,
                        "status": "cancelled",
                        "changed": False,
                    }
                if (
                    row["status"] != "pending"
                    or row["not_before"] > now
                    or row["expires"] <= now
                ):
                    return {
                        "schema_version": 1,
                        "status": row["status"],
                        "changed": False,
                    }
                if (
                    not self.is_managed(item["scope"])
                    or self._paused(db, item["scope"])
                    or self._outreach_paused(db, item["scope"])
                ):
                    return {"schema_version": 1, "status": "disabled", "changed": False}
                if item.get("kind") in {"care_wait", "social_chat"}:
                    item["claimed_at"] = now
            if status == "pending" and row["status"] in {"claimed", "failed"}:
                raise NarrativeValidationError(
                    "a_send_attempt_cannot_automatically_return_to_pending",
                    "A send attempt cannot automatically return to pending",
                )
            if receipt is not None:
                item["receipt"] = copy.deepcopy(receipt)
            item["status"] = status
            db.execute(
                "UPDATE intents SET payload=?,status=?,updated=? WHERE intent_id=?",
                (_json(item), status, now, intent_id),
            )
            return {
                "schema_version": 1,
                "status": status,
                "changed": True,
                "intent": item,
            }

    async def get_intent(self, intent_id: str) -> dict:
        """Read one authority record even while it is paused or not yet due."""
        now = self.clock()
        with self._db() as db:
            row = db.execute(
                "SELECT * FROM intents WHERE intent_id=?", (intent_id,)
            ).fetchone()
            if row is None:
                return {"schema_version": 1, "available": False, "item": None}
            status = row["status"]
            item = json.loads(row["payload"])
            if status in {"pending", "claimed"} and not self._care_current(db, item):
                status = "cancelled"
                db.execute(
                    "UPDATE intents SET status='cancelled',updated=? WHERE intent_id=?",
                    (now, intent_id),
                )
            if status in {"pending", "failed"} and row["expires"] <= now:
                status = "expired"
                db.execute(
                    "UPDATE intents SET status='expired',updated=? WHERE intent_id=?",
                    (now, intent_id),
                )
            item = json.loads(row["payload"])
            item.update(
                status=status,
                managed=self.is_managed(item["scope"]),
                paused=self._paused(db, item["scope"]),
                outreach_paused=self._outreach_paused(db, item["scope"]),
            )
            return {"schema_version": 1, "available": True, "item": item}

    async def cancel_intent(self, intent_id: str) -> dict:
        """Cancel a motivation before sending, preserving its historical record."""
        return await self.update_intent(intent_id, "cancelled")

    async def set_paused(
        self, paused: bool, scope: dict | None = None, *, proactive_only: bool = False
    ) -> dict:
        """Persist global or scoped pause state across plugin reloads."""
        if proactive_only:
            result = await self.set_outreach_paused(paused, scope)
            return dict(result, paused=bool(paused), proactive_only=True)
        key = "proactive_paused" if proactive_only else "paused"
        if scope and not proactive_only:
            scope = normalize_scope(scope)
            key += ":" + _identity(scope) + ":" + scope["umo"]
        with self._db() as db:
            db.execute(
                "INSERT INTO metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, "true" if paused else "false"),
            )
            if (
                self.spatial is not None
                and not proactive_only
                and (scope is None or not scope["umo"])
            ):
                self.spatial.pause(
                    db, scope or self._global_scope(), bool(paused), self.clock()
                )
        return {
            "schema_version": 1,
            "paused": bool(paused),
            "proactive_only": proactive_only,
        }

    async def correct_state(self, scope: dict, patch: dict) -> dict:
        """Apply an administrator correction as a new, append-only event."""
        scope, now = normalize_scope(scope), self.clock()
        if not self._allowed(scope):
            return self._result("unmanaged", {"managed": False})
        if not isinstance(patch, dict) or set(patch) - {
            "activity_code",
            "activity",
            "availability",
            "subjective_state",
            "summary",
        }:
            raise NarrativeValidationError(
                "unsupported_correction_fields", "Unsupported correction fields"
            )
        manual_activity = (
            _text(patch["activity"], 220, "activity") if "activity" in patch else None
        )
        patch = {key: value for key, value in patch.items() if key != "activity"}
        correction_data = dict(patch)
        if manual_activity is not None:
            correction_data["activity"] = manual_activity
        event = {
            "event_id": "correction:" + str(uuid.uuid4()),
            "scope": scope,
            "type": "admin.correction",
            "occurred_at": now,
            "received_at": now,
            "fact_kind": "observation",
            "text": "管理员纠正了当前状态。",
            "data": correction_data,
        }
        await self.ingest_events([event])
        # Corrections intentionally do not acquire the model lock, so a stale
        # in-flight result fails its revision comparison instead of blocking UI.
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            snapshot = self._snapshot(db, scope, now)
            request = {
                "scope": scope,
                "now": now,
                "snapshot": snapshot,
                "events": [self._event(event, now)],
                "needs_daily_plan": False,
            }
            change = self._validate_change(
                {
                    "state": patch,
                    "diary": [
                        {
                            "text": "管理员纠正了当前状态。",
                            "source_ids": [event["event_id"]],
                            "fact_kind": "observation",
                        }
                    ],
                },
                request,
            )
            self._commit(
                db, scope, change, request["events"], now, snapshot["revision"] + 1
            )
            if manual_activity is not None:
                identity = _identity(scope)
                state = json.loads(
                    db.execute(
                        "SELECT state FROM lives WHERE identity=?", (identity,)
                    ).fetchone()[0]
                )
                state["activity"] = manual_activity
                db.execute(
                    "UPDATE lives SET state=? WHERE identity=?",
                    (_json(state), identity),
                )
            return self._result("corrected", self._snapshot(db, scope, now))

    async def get_narrative_admin(self, scope: dict) -> dict:
        """Return administrator diagnostics for one explicit conversation only."""
        scope, now = normalize_scope(scope), self.clock()
        if not self._allowed(scope):
            return {
                "schema_version": 1,
                "managed": False,
                "available": True,
                "reason": "not_enabled",
                "paused": False,
                "outreach_paused": False,
            }
        identity = _identity(scope)
        with self._db() as db:
            snapshot = self._snapshot(db, scope, now)
            diary = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM diary WHERE identity=? AND umo IN (?, '') ORDER BY occurred DESC LIMIT 100",
                    (identity, scope["umo"]),
                )
            ]
            intents = [
                dict(json.loads(row["payload"]), status=row["status"])
                for row in db.execute(
                    "SELECT * FROM intents WHERE identity=? AND umo=? ORDER BY updated DESC LIMIT 100",
                    (identity, scope["umo"]),
                )
            ]
            pending = db.execute(
                "SELECT COUNT(*) FROM events WHERE identity=? AND umo=? AND status='pending'",
                (identity, scope["umo"]),
            ).fetchone()[0]
            routing = dict(
                db.execute(
                    "SELECT status,COUNT(*) FROM events WHERE identity=? AND umo=? GROUP BY status",
                    (identity, scope["umo"]),
                ).fetchall()
            )
            oldest = db.execute(
                "SELECT MIN(occurred) FROM events WHERE identity=? AND umo=? AND status='pending'",
                (identity, scope["umo"]),
            ).fetchone()[0]
            retry_due = db.execute(
                "SELECT COUNT(*) FROM events WHERE identity=? AND umo=? AND status='pending' AND next_retry>?",
                (identity, scope["umo"], now),
            ).fetchone()[0]
            oversized = db.execute(
                "SELECT COUNT(*) FROM events WHERE identity=? AND umo=? AND status='pending' AND error LIKE 'oversized_payload_bytes:%'",
                (identity, scope["umo"]),
            ).fetchone()[0]
            blocked_policy = db.execute(
                "SELECT COUNT(*) FROM events WHERE identity=? AND umo=? AND status='blocked_policy'",
                (identity, scope["umo"]),
            ).fetchone()[0]
            queue_head = db.execute(
                "SELECT retry_attempt,next_retry,error,LENGTH(CAST(payload AS BLOB)) payload_bytes "
                "FROM events WHERE identity=? AND umo=? AND status='pending' ORDER BY occurred,received,event_id LIMIT 1",
                (identity, scope["umo"]),
            ).fetchone()
            budget = dict(
                db.execute(
                    "SELECT kind,used FROM budgets WHERE identity=? AND hour=?",
                    (identity, int(now // 3600)),
                ).fetchall()
            )
            scoped_budget = (
                "extra:" + hashlib.sha256(scope["umo"].encode()).hexdigest()[:16]
            )
            budget = {k: v for k, v in budget.items() if not k.startswith("extra:")} | {
                "extra": budget.get(scoped_budget, 0)
            }
            calls = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM calls WHERE identity=? AND umo IN (?, '') ORDER BY started DESC LIMIT 100",
                    (identity, scope["umo"]),
                )
            ]
            life = json.loads(
                db.execute(
                    "SELECT state FROM lives WHERE identity=?", (identity,)
                ).fetchone()[0]
            )
            queue_diagnostics = {
                "pending_count": pending,
                "deferred_count": retry_due,
                "oversized_blocked_count": oversized,
                "blocked_policy_count": blocked_policy,
                "next_retry_at": (
                    db.execute(
                        "SELECT MIN(next_retry) FROM events WHERE identity=? AND umo=? AND status='pending' AND next_retry>?",
                        (identity, scope["umo"], now),
                    ).fetchone()[0]
                ),
                "head": (
                    {
                        "attempt": queue_head["retry_attempt"],
                        "next_retry_at": queue_head["next_retry"],
                        "error": queue_head["error"],
                        "payload_bytes": queue_head["payload_bytes"],
                    }
                    if queue_head
                    else None
                ),
            }
            review = db.execute(
                "SELECT value FROM metadata WHERE key=?",
                ("outreach_review:" + _json([identity, scope["umo"]]),),
            ).fetchone()
            review = json.loads(review[0]) if review else {}
            queue_diagnostics["outreach_review"] = {
                k: review.get(k) for k in ("last_at", "next_at", "status", "candidates")
            }
            return {
                "schema_version": 1,
                "managed": True,
                "available": True,
                "reason": "",
                "paused": self._paused(db, scope),
                "outreach_paused": self._outreach_paused(db, scope),
                "snapshot": snapshot,
                "diary": diary,
                "intents": intents,
                "pending_count": pending,
                "routing_counts": routing,
                "oldest_pending_at": oldest,
                "queue_diagnostics": queue_diagnostics,
                "hourly_budget_used": budget,
                "calls": calls,
                "daily_plan": life["plan"],
                "plan_date": life["plan_date"],
                "plan_status": self._plan_status(db, scope, life, now),
                "source_ids": snapshot["source_ids"],
            }

    def _plan_status(
        self,
        db,
        scope: dict,
        life: dict,
        now: float,
        *,
        generating: bool | None = None,
    ) -> dict:
        identity = _identity(scope)
        tz = self._timezone()
        local_date = dt.datetime.fromtimestamp(now, tz).date()
        today = local_date.isoformat()
        midnight = dt.datetime.combine(local_date, dt.time(), tz).timestamp()
        plan_date = str(life.get("plan_date") or "")
        plan_items = life.get("plan") if isinstance(life.get("plan"), list) else []
        is_today = bool(plan_date == today and len(plan_items) > 0)
        last_call = db.execute(
            "SELECT status,started FROM calls "
            "WHERE identity=? AND umo='' AND kind IN ('hourly','plan_regen') AND started>=? "
            "ORDER BY started DESC LIMIT 1",
            (identity, midnight),
        ).fetchone()
        last_err_row = db.execute(
            "SELECT error,occurred FROM events "
            "WHERE identity=? AND umo='' AND error!='' AND occurred>=? "
            "ORDER BY occurred DESC LIMIT 1",
            (identity, midnight),
        ).fetchone()
        last_call_status = str(last_call["status"]) if last_call else ""
        last_call_at = float(last_call["started"]) if last_call else None
        last_error = str(last_err_row["error"]) if last_err_row else ""
        is_gen = (
            identity in self._plan_regens if generating is None else bool(generating)
        )
        if is_gen:
            status = "generating"
        elif is_today:
            status = "ready"
        elif last_call_status in {
            "invalid",
            "timeout",
            "policy_refusal",
            "provider_unavailable",
            "failed",
        } or last_error:
            status = "failed"
        else:
            status = "missing"
        return {
            "today": today,
            "plan_date": plan_date,
            "is_today": is_today,
            "status": status,
            "last_attempt_at": last_call_at,
            "last_attempt_status": last_call_status,
            "last_error": last_error,
            "generating": is_gen,
        }

    def get_plan_status(
        self, scope: dict, *, generating: bool | None = None
    ) -> dict:
        scope = normalize_scope(scope)
        global_scope = dict(scope, umo="", platform="")
        now = self.clock()
        with self._db() as db:
            self._ensure(db, global_scope, now)
            row = db.execute(
                "SELECT state FROM lives WHERE identity=?", (_identity(global_scope),)
            ).fetchone()
            life = json.loads(row[0]) if row else {"plan": [], "plan_date": ""}
            return self._plan_status(
                db, global_scope, life, now, generating=generating
            )

    async def regenerate_daily_plan(
        self,
        scope: dict,
        *,
        extra: str = "",
    ) -> dict:
        """Manually regenerate today's remaining daily plan without rewriting past history."""
        scope = normalize_scope(scope)
        if self._closed or not self._allowed(scope):
            return {
                "schema_version": 1,
                "status": "unmanaged",
                "message": "当前会话未启用持续叙事生活。",
                "plan_status": self.get_plan_status(scope),
            }
        global_scope = dict(scope, umo="", platform="")
        identity = _identity(global_scope)
        if identity in self._plan_regens:
            return {
                "schema_version": 1,
                "status": "generating",
                "message": "今日日程正在重新生成中，请稍候。",
                "plan_status": self.get_plan_status(global_scope),
            }
        clean_extra = str(extra or "").strip()[:200]
        self._plan_regens.add(identity)
        try:
            async with self._locks.setdefault(identity, asyncio.Lock()):
                now = self.clock()
                with self._db() as db:
                    self._ensure(db, global_scope, now)
                    if self._paused(db, scope) or self._paused(db, global_scope):
                        row = db.execute(
                            "SELECT state FROM lives WHERE identity=?", (identity,)
                        ).fetchone()
                        paused_life = (
                            json.loads(row[0]) if row else {"plan": [], "plan_date": ""}
                        )
                        return {
                            "schema_version": 1,
                            "status": "paused",
                            "message": "持续叙事已暂停，请先恢复后再重新生成日程。",
                            "plan_status": self._plan_status(
                                db, global_scope, paused_life, now, generating=False
                            ),
                        }
                    if self.causal is not None and self.spatial is not None:
                        self.causal.advance(db, global_scope, now)
                    if self.scenes is not None and self.spatial is not None:
                        self.spatial.settle(db, global_scope, now)
                        self.scenes.settle(db, global_scope, now)
                    snapshot = self._snapshot(db, global_scope, now)
                    life = json.loads(
                        db.execute(
                            "SELECT state FROM lives WHERE identity=?", (identity,)
                        ).fetchone()[0]
                    )
                    diary = [
                        dict(row)
                        for row in db.execute(
                            "SELECT occurred,text,fact_kind,source_ids FROM diary "
                            "WHERE identity=? AND umo='' ORDER BY occurred DESC LIMIT 8",
                            (identity,),
                        )
                    ]
                    event_id = f"admin.regen_plan:{identity}:{uuid.uuid4().hex[:12]}"
                    event = {
                        "event_id": event_id,
                        "type": "life.tick",
                        "scope": global_scope,
                        "occurred_at": now,
                        "received_at": now,
                        "actor_id": "admin",
                        "fact_kind": "fiction",
                        "data": {
                            "trigger": "admin_regenerate_plan",
                            **(
                                {"hint": clean_extra}
                                if clean_extra
                                else {}
                            ),
                        },
                    }
                    db.execute(
                        "INSERT INTO events VALUES(?,?,?,?,?,?,'pending','',?,0,0)",
                        (event_id, identity, "", now, now, _json(event), now),
                    )
                    causal_rev = (
                        self.causal.load(db, global_scope)[0]
                        if self.causal is not None
                        else None
                    )
                tz = self._timezone()
                tz_name = self._timezone_name()
                local_date = dt.datetime.fromtimestamp(now, tz).date()
                day_end = dt.datetime.combine(
                    local_date + dt.timedelta(days=1), dt.time(), tz
                ).timestamp()
                request = {
                    "schema_version": 1,
                    "scope": global_scope,
                    "now": now,
                    "day_end": day_end,
                    "local_datetime": dt.datetime.fromtimestamp(now, tz).isoformat(),
                    "timezone": tz_name,
                    "local_date": local_date.isoformat(),
                    "plan_window": {"start": now, "end": day_end},
                    "trigger": "admin_regenerate_plan",
                    "snapshot": dict(
                        snapshot, **snapshot.get("global_presentation", {})
                    ),
                    "events": [event],
                    "recent_diary": diary,
                    "plan": life["plan"],
                    "needs_daily_plan": True,
                    "manual_plan_regeneration": True,
                    **(
                        {"regeneration_hint": clean_extra}
                        if clean_extra
                        else {}
                    ),
                    "weather_reassessment": False,
                    "offline_catchup": False,
                }
                if causal_rev is not None:
                    request["causal_revision"] = causal_rev
                request["snapshot"]["humanlike"] = copy.deepcopy(snapshot["humanlike"])
                started = time.monotonic()
                call_id = str(uuid.uuid4())
                request["inference_call_id"] = call_id
                kind = "plan_regen"
                raw = None
                plan_only_keys = {
                    "schema_version",
                    "no_change",
                    "source_ids",
                    "state",
                    "daily_plan",
                    "next_check",
                }
                try:
                    timeout = max(
                        1.0,
                        min(
                            float(self.config.get("narrative_timeout_seconds", 90)),
                            90.0,
                        ),
                    )
                    change = None
                    for attempt_idx in range(2):
                        raw = await asyncio.wait_for(
                            self.model(copy.deepcopy(request)), timeout
                        )
                        sanitized = (
                            {k: v for k, v in raw.items() if k in plan_only_keys}
                            if isinstance(raw, dict)
                            else raw
                        )
                        try:
                            change = self._validate_change(sanitized, request)
                            if not change.get("daily_plan"):
                                raise NarrativeValidationError(
                                    "empty_daily_plan_on_regeneration",
                                    "Model did not return a daily plan",
                                )
                            break
                        except NarrativeValidationError as v_exc:
                            if attempt_idx == 0 and v_exc.code not in {
                                "unsupported_narrative_response",
                                "empty_daily_plan_on_regeneration",
                            }:
                                request["previous_validation_failure"] = {
                                    "reason_code": "validation." + v_exc.code,
                                    "attempt": 1,
                                    "instruction": "Return only valid daily_plan entries strictly within plan_window (start < end, non-overlapping) and optional state/next_check; omit world_action and movement.",
                                }
                                continue
                            raise
                except asyncio.CancelledError:
                    self._call(call_id, identity, "", now, started, "cancelled", kind)
                    raise
                except Exception as exc:
                    if self._is_policy_refusal(exc):
                        self._call(
                            call_id, identity, "", now, started, "policy_refusal", kind
                        )
                        self._block_policy_refusal([event])
                        return {
                            "schema_version": 1,
                            "status": "policy_refusal",
                            "error": "policy_refusal",
                            "message": "模型拒绝了本次日程生成请求，请稍后重试。",
                            "plan_status": self.get_plan_status(
                                global_scope, generating=False
                            ),
                        }
                    requested_status = getattr(exc, "status_code", "")
                    err_status = (
                        requested_status
                        if requested_status == "provider_unavailable"
                        else ("timeout" if isinstance(exc, TimeoutError) else "invalid")
                    )
                    self._call(call_id, identity, "", now, started, err_status, kind)
                    code = (
                        "validation." + exc.code
                        if isinstance(exc, NarrativeValidationError)
                        else type(exc).__name__
                    )
                    http_status = getattr(exc, "code", None)
                    if type(http_status) is int and 400 <= http_status <= 599:
                        code = f"provider.http_{http_status}.{type(exc).__name__}"
                    with self._db() as db:
                        db.execute(
                            "UPDATE events SET status='failed',error=?,retry_attempt=retry_attempt+1 WHERE event_id=?",
                            (code, event_id),
                        )
                    msg_map = {
                        "timeout": "日程生成超时，请稍后重试。",
                        "provider_unavailable": "当前模型服务不可用，请检查模型配置后重试。",
                    }
                    return {
                        "schema_version": 1,
                        "status": err_status,
                        "error": code,
                        "message": msg_map.get(
                            err_status, f"日程重新生成失败（{code}），请重试。"
                        ),
                        "plan_status": self.get_plan_status(
                            global_scope, generating=False
                        ),
                    }
                if not self._allowed(global_scope):
                    self._call(call_id, identity, "", now, started, "unmanaged", kind)
                    return {
                        "schema_version": 1,
                        "status": "unmanaged",
                        "message": "当前会话未启用持续叙事生活。",
                        "plan_status": self.get_plan_status(
                            global_scope, generating=False
                        ),
                    }
                stale_response = None
                try:
                    with self._db() as db:
                        db.execute("BEGIN IMMEDIATE")
                        current = self._snapshot(db, global_scope, self.clock())
                        if current["revision"] != snapshot["revision"] or self._paused(
                            db, global_scope
                        ):
                            db.execute(
                                "UPDATE events SET status='failed',error='stale_revision' WHERE event_id=?",
                                (event_id,),
                            )
                            stale_row = db.execute(
                                "SELECT state FROM lives WHERE identity=?", (identity,)
                            ).fetchone()
                            stale_life = (
                                json.loads(stale_row[0])
                                if stale_row
                                else {"plan": [], "plan_date": ""}
                            )
                            stale_response = {
                                "schema_version": 1,
                                "status": "stale",
                                "error": "stale_revision",
                                "message": "生成期间生活状态已变化，请再次点击重新生成。",
                                "plan_status": self._plan_status(
                                    db,
                                    global_scope,
                                    stale_life,
                                    self.clock(),
                                    generating=False,
                                ),
                            }
                        else:
                            self._commit(
                                db,
                                global_scope,
                                change,
                                [event],
                                now,
                                snapshot["revision"] + 1,
                            )
                            result_snap = self._snapshot(db, global_scope, self.clock())
                            updated_life = json.loads(
                                db.execute(
                                    "SELECT state FROM lives WHERE identity=?",
                                    (identity,),
                                ).fetchone()[0]
                            )
                            plan_st = self._plan_status(
                                db,
                                global_scope,
                                updated_life,
                                self.clock(),
                                generating=False,
                            )
                except (ValueError, sqlite3.Error) as exc:
                    code = (
                        "validation." + exc.code
                        if isinstance(exc, NarrativeValidationError)
                        else type(exc).__name__
                    )
                    with self._db() as db:
                        db.execute(
                            "UPDATE events SET status='failed',error=? WHERE event_id=?",
                            (code, event_id),
                        )
                    self._call(call_id, identity, "", now, started, "invalid", kind)
                    return {
                        "schema_version": 1,
                        "status": "invalid",
                        "error": code,
                        "message": f"日程校验未通过（{code}），请重试。",
                        "plan_status": self.get_plan_status(
                            global_scope, generating=False
                        ),
                    }
                if stale_response is not None:
                    self._call(call_id, identity, "", now, started, "stale", kind)
                    return stale_response
                self._call(call_id, identity, "", now, started, "advanced", kind)
                return {
                    "schema_version": 1,
                    "status": "regenerated",
                    "plan_date": updated_life.get("plan_date", local_date.isoformat()),
                    "count": len(updated_life.get("plan", [])),
                    "daily_plan": updated_life.get("plan", []),
                    "snapshot": result_snap,
                    "plan_status": plan_st,
                }
        finally:
            self._plan_regens.discard(identity)

    async def tick(self, now: float | None = None) -> dict:
        """Check hourly life and five-minute scoped queues without catch-up storms."""
        now = self.clock() if now is None else _timestamp(now)
        if (
            self.config.get("mode", "legacy") != "narrative"
            or not self.config.get("persona_id")
            or not self._has_targets()
            or self._closed
        ):
            return {"schema_version": 1, "status": "disabled", "results": []}
        scope = self._global_scope()
        identity = _identity(scope)
        results = []
        with self._db() as db:
            self._ensure(db, scope, now)
            self._compact_old_queue(db, identity)
            if self.scenes is not None and self.causal is not None:
                from ...cabin_life import tick_homes
                tick_homes(self.scenes, db, now)
            if self.causal is not None:
                self.causal.advance(db, scope, now)
            if self.scenes is not None:
                self.spatial.settle(db, scope, now)
                self.scenes.settle(db, scope, now)
            if self._paused(db, scope):
                if self.environment is not None:
                    self.environment.life_observer.poll(db, scope, now, suspended=True)
                return {"schema_version": 1, "status": "paused", "results": []}
            row = db.execute(
                "SELECT state FROM lives WHERE identity=?", (identity,)
            ).fetchone()
            life = json.loads(row[0])
            last = db.execute(
                "SELECT last FROM maintenance WHERE identity=? AND kind='hourly'",
                (identity,),
            ).fetchone()
            deadline = min(life["valid_until"], life["next_check"])
            boundaries = [
                float(p[k])
                for p in life.get("plan", [])
                for k in ("start", "end")
                if float(p[k]) > life.get("narrated_until", life["valid_from"])
            ]
            if boundaries:
                deadline = min(deadline, min(boundaries))
            due = not last or int(last[0] // 3600) < int(now // 3600) or deadline <= now
            sleep_deadline = deadline
            if life["availability"] == "asleep" and not any(b <= now for b in boundaries):
                active_plan_ends = [
                    float(p["end"])
                    for p in life.get("plan", [])
                    if float(p["start"]) <= now < float(p["end"])
                ]
                if active_plan_ends:
                    sleep_deadline = max(sleep_deadline, min(active_plan_ends))
            asleep = life["availability"] == "asleep" and sleep_deadline > now
            weather_event = (
                self.environment.life_observer.poll(db, scope, now, suspended=asleep)
                if self.environment is not None
                else None
            )
            scene_event = (
                self.scenes.completion_event(db, scope, now)
                if self.scenes is not None
                else None
            )
            background = db.execute(
                "SELECT last FROM maintenance WHERE identity=? AND kind='background'",
                (identity,),
            ).fetchone()
            batch_interval = self.effective_tick_interval(
                300.0, kind="narrative", now=now
            )
            batch_due = not background or now - background[0] >= batch_interval
            scopes = []
            if batch_due:
                db.execute(
                    "INSERT INTO maintenance VALUES(?,'background',?) ON CONFLICT(identity,kind) DO UPDATE SET last=excluded.last",
                    (identity, now),
                )
                self.record_background_tick(kind="narrative", now=now)
                for row in db.execute(
                    "SELECT e.payload FROM events e WHERE e.identity=? AND e.umo<>'' AND e.status='pending' "
                    "AND e.occurred<=? AND e.received<=? AND e.event_id=(SELECT h.event_id FROM events h "
                    "WHERE h.identity=e.identity AND h.umo=e.umo AND h.status='pending' "
                    "ORDER BY h.occurred,h.received,h.event_id LIMIT 1) AND e.next_retry<=? "
                    "AND e.error NOT LIKE 'oversized_payload_bytes:%' ORDER BY e.occurred,e.received,e.event_id",
                    (identity, now, now, now),
                ):
                    candidate = json.loads(row[0])["scope"]
                    if self.is_managed(candidate):
                        scopes.append(candidate)

                def last_served(candidate):
                    row = db.execute(
                        "SELECT last FROM maintenance WHERE identity=? AND kind=?",
                        (identity, "served:" + candidate["umo"]),
                    ).fetchone()
                    return row[0] if row else 0

                scopes.sort(key=last_served)
        background_due = False
        if (
            asleep
            and due
            and self.causal is not None
            and getattr(self, "resident_runner", None) is None
        ):
            with self._db() as db:
                background_due = bool(self.causal.background_request(db, scope, now))
        if (not asleep or background_due) and (due or weather_event or scene_event):
            events = (
                ([self._hourly_event(scope, now)] if due else [])
                + ([weather_event] if weather_event else [])
                + ([scene_event] if scene_event else [])
            )
            result = await self.advance(events)
            results.append(result)
            if result["status"] in {"advanced", "no_change"}:
                if due:
                    with self._db() as db:
                        db.execute(
                            "INSERT INTO maintenance VALUES(?,'hourly',?) ON CONFLICT(identity,kind) DO UPDATE SET last=excluded.last",
                            (identity, now),
                        )
                if self.environment is not None:
                    self.environment.life_observer.acknowledge(scope, now)
        for candidate in scopes:
            with self._db() as db:
                pending = self._pending(db, candidate, now)
            if pending:
                result = await self.advance(pending)
                results.append(result)
                if result["status"] == "budget_exhausted":
                    continue
                with self._db() as db:
                    db.execute(
                        "INSERT INTO maintenance VALUES(?,?,?) ON CONFLICT(identity,kind) DO UPDATE SET last=excluded.last",
                        (identity, "served:" + candidate["umo"], now),
                    )
        return {"schema_version": 1, "status": "checked", "results": results}

    def record_horizon_reading(
        self, scope: dict, payload: dict, *, owner: Any = None
    ) -> dict:
        if getattr(self, "horizons", None) is None:
            self.horizons = _resolve_horizons_sync_cls()(self)
        return self.horizons.record_reading(scope, payload, owner=owner)

    async def close(self) -> None:
        """Invalidate permissions; no persistent connection or private task survives."""
        self._closed = True
        await self._snapshot_io.close()
