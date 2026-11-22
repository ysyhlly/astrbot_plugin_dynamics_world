"""Real-time SSE delta stream, WorldEventBus and domain revision assembler."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Any

from .life.core.narrative_io import WorldIO, WorldIOBusy, WorldIOClosed
from .series_panels import resolve_series_timezone_name
from .spatial import identity

try:
    from astrbot.api.web import StreamingResponse
except (
    Exception
):  # pragma: no cover - fallback when Starlette comes directly or in unit tests
    try:
        from starlette.responses import StreamingResponse  # type: ignore
    except Exception:  # pragma: no cover

        class StreamingResponse:  # type: ignore
            """Lightweight test-environment fallback preserving async body_iterator & headers."""

            def __init__(
                self,
                content,
                status_code: int = 200,
                headers: dict | None = None,
                media_type: str = "text/event-stream",
            ):
                self.body_iterator = content
                self.status_code = status_code
                self.headers = dict(headers or {})
                self.media_type = media_type


_FRAME_PIXEL_CACHE: dict[str, tuple[float, list[list[str]]]] = {}
MAX_TOTAL_SUBSCRIBERS = 24
MAX_IDENTITY_SUBSCRIBERS = 6
_HEARTBEAT_SECONDS = 18.0
_MIN_PROJECTION_RETRY_SECONDS = 0.2
_MAX_PROJECTION_RETRY_SECONDS = 2.0


def _short_rev_int(obj: Any) -> int:
    raw = json.dumps(
        obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return int.from_bytes(hashlib.blake2b(raw, digest_size=6).digest(), "big")


def parse_known_revisions(raw: str | None) -> dict[str, int] | None:
    """Parse compact 'k:v,k:v' or JSON revision map from query string."""
    if not raw or not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    if text.startswith("{"):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return {
                    str(k): int(v)
                    for k, v in parsed.items()
                    if isinstance(v, (int, float))
                }
        except Exception:
            return None
    out: dict[str, int] = {}
    for part in text.split(","):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        k = k.strip()
        try:
            out[k] = int(v.strip())
        except ValueError:
            continue
    return out or None


def _sample_pixel_frame(
    image_path: Path, cols: int = 16, rows: int = 12
) -> list[list[str]] | None:
    """Downsample an artwork image into a compact 16x12 hex grid for the 3D north-wall frame."""
    try:
        if not image_path.is_file():
            return None
        mtime = image_path.stat().st_mtime
        cache_key = str(image_path)
        cached = _FRAME_PIXEL_CACHE.get(cache_key)
        if cached and cached[0] == mtime:
            return cached[1]
        from PIL import Image

        with Image.open(image_path) as img:
            small = img.convert("RGB").resize((cols, rows), Image.Resampling.BILINEAR)
            grid = [
                [
                    f"#{r:02x}{g:02x}{b:02x}"
                    for x in range(cols)
                    for r, g, b in (small.getpixel((x, y)),)
                ]
                for y in range(rows)
            ]
        if len(_FRAME_PIXEL_CACHE) > 24:
            _FRAME_PIXEL_CACHE.clear()
        _FRAME_PIXEL_CACHE[cache_key] = (mtime, grid)
        return grid
    except Exception:
        return None


def _life_cues(db, scope, now, life_service=None):
    """Activity code, current plan entry, outfit tag, start timestamp and today's schedule."""
    from .life.core.narrative import _identity

    row = db.execute(
        "SELECT state FROM lives WHERE identity=?", (_identity(scope),)
    ).fetchone()
    outfit_now = ""
    horizons_desk = []
    if life_service is not None:
        try:
            horizons_svc = getattr(
                getattr(life_service, "narrative", None), "horizons", None
            )
            if horizons_svc is not None:
                horizons_desk = horizons_svc.desk_snapshot(db, scope, limit=2)
        except Exception:
            horizons_desk = []
        try:
            legacy_state, _ = life_service._select_current_state(life_service._now())
            if legacy_state:
                from .life.core.state import select_current_slot

                slot = select_current_slot(legacy_state, life_service._now())
                if slot and getattr(slot.entry, "outfit", ""):
                    outfit_now = str(slot.entry.outfit)[:80]
        except Exception:
            pass
    if not row:
        return {
            "activity_code": "unknown",
            "plan_now": "",
            "outfit_now": outfit_now,
            "activity_started_at": None,
            "plan_today": [],
            "horizons_desk": horizons_desk,
        }
    state = json.loads(row[0])
    current = float(state.get("valid_until", 0) or 0) > now
    plan_raw = state.get("plan") or []
    entry = next(
        (
            p
            for p in plan_raw
            if isinstance(p, dict)
            and float(p.get("start", 0) or 0) <= now < float(p.get("end", 0) or 0)
        ),
        None,
    )
    started = (
        float(entry["start"])
        if entry and isinstance(entry.get("start"), (int, float))
        else float(state["valid_from"])
        if current and isinstance(state.get("valid_from"), (int, float))
        else None
    )
    plan_today = [
        {
            "start": float(p.get("start", 0) or 0),
            "end": float(p.get("end", 0) or 0),
            "activity": str(p.get("activity", ""))[:120],
        }
        for p in plan_raw[:12]
        if isinstance(p, dict) and p.get("activity")
    ]
    if not outfit_now and entry and entry.get("outfit"):
        outfit_now = str(entry.get("outfit"))[:80]
    return {
        "activity_code": str(state.get("activity_code", "unknown"))
        if current
        else "unknown",
        "plan_now": str(entry.get("activity", ""))[:120] if entry else "",
        "outfit_now": outfit_now,
        "activity_started_at": started,
        "plan_today": plan_today,
        "horizons_desk": horizons_desk,
    }


class _Subscriber:
    def __init__(self, identity_key: str, loop: asyncio.AbstractEventLoop):
        self.identity_key = identity_key
        self.loop = loop
        self.event = asyncio.Event()
        self.closed = False

    def signal(self) -> None:
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        if self.loop is current:
            self.event.set()
        elif self.loop.is_running():
            try:
                self.loop.call_soon_threadsafe(self.event.set)
            except RuntimeError:
                pass

    async def wait(self, timeout: float) -> bool:
        if self.closed:
            return False
        if self.event.is_set():
            self.event.clear()
            return True
        try:
            await asyncio.wait_for(self.event.wait(), timeout=timeout)
            self.event.clear()
            return not self.closed
        except asyncio.TimeoutError:
            return False


class WorldEventBus:
    """In-memory pub/sub bus waking active SSE streams immediately on world state writes."""

    def __init__(self):
        self._subs: dict[_Subscriber, None] = {}
        self._lock = Lock()
        self._closed = False
        self._generation = 0
        self._projection_io = self._new_projection_io()

    @staticmethod
    def _new_projection_io():
        return WorldIO(
            max_workers=1,
            max_pending=MAX_TOTAL_SUBSCRIBERS,
            max_waiters=2 * MAX_TOTAL_SUBSCRIBERS,
            thread_name_prefix="world-panel",
        )

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subs)

    @property
    def generation(self) -> int:
        """Publications that may supersede an in-flight panel projection."""
        with self._lock:
            return self._generation

    def subscribe(self, identity_key: str) -> _Subscriber | None:
        with self._lock:
            if self._closed:
                return None
            same_key = [s for s in self._subs if s.identity_key == identity_key]
            victim = (
                same_key[0]
                if len(same_key) >= MAX_IDENTITY_SUBSCRIBERS
                else next(iter(self._subs))
                if len(self._subs) >= MAX_TOTAL_SUBSCRIBERS
                else None
            )
            if victim is not None:
                self._subs.pop(victim)
                victim.closed = True
                victim.signal()
            sub = _Subscriber(identity_key, asyncio.get_running_loop())
            self._subs[sub] = None
            return sub

    def unsubscribe(self, sub: _Subscriber | None) -> None:
        if sub is None:
            return
        with self._lock:
            if sub in self._subs:
                self._subs.pop(sub)
                sub.closed = True
                sub.signal()

    def notify(self, identity_key: str | None = None) -> None:
        """Thread-safe notification invoked on SQLite write commit or avatar update."""
        with self._lock:
            self._generation += 1
            for sub in self._subs:
                if identity_key is None or sub.identity_key in (identity_key, "*"):
                    sub.signal()

    async def drain_projections(self) -> None:
        """Retire panel work before replacing the World services."""
        projection_io = self._projection_io

        async def retire():
            await projection_io.close()
            with self._lock:
                if not self._closed and self._projection_io is projection_io:
                    self._projection_io = self._new_projection_io()

        retirement = asyncio.create_task(retire())
        cancellation = None
        # Keep the migration gate active until the old transaction has drained.
        while not retirement.done():
            try:
                await asyncio.shield(retirement)
            except asyncio.CancelledError as exc:
                cancellation = exc
        retirement.result()
        if cancellation is not None:
            raise cancellation

    async def close(self) -> None:
        with self._lock:
            self._closed = True
            for sub in self._subs:
                sub.closed = True
                sub.signal()
            self._subs.clear()
        await self._projection_io.close()


def compute_domain_revisions(
    *,
    doc: dict | None,
    actor: dict,
    environment: dict,
    scene: dict,
    life: dict,
    cues: dict,
    ecology: dict,
    keepsakes: dict,
    timeline: list,
    mailbox: dict,
    world_space: dict,
    companions: dict,
    avatar_rev: int = 0,
) -> dict[str, int]:
    """Compute content-addressed tokens for the projections sent in deltas."""
    map_rev = (
        _short_rev_int((doc.get("world_id"), doc.get("map_type"), doc.get("revision")))
        if doc
        else 0
    )
    pos_step = (
        int(round(float(actor.get("progress") or 0.0) * 25))
        if actor.get("journey")
        else 0
    )
    pos_rev = (
        int(actor.get("revision") or 0) * 64
        + pos_step
        + (1 if actor.get("paused") else 0)
    )

    room_design_rev = sum(
        int(d.get("revision") or 0) for d in (scene.get("room_designs") or [])
    )
    act = scene.get("action")
    act_step = (
        int(round(float(act.get("progress") or 0.0) * 20))
        + int(act.get("index") or 0) * 32
        if isinstance(act, dict)
        else 0
    )
    scene_rev = _short_rev_int(
        (
            scene.get("revision"),
            room_design_rev,
            act_step,
            scene.get("paused"),
            scene.get("visual_profile"),
        )
    )

    life_rev = _short_rev_int(
        (
            life.get("revision", 0),
            life.get("activity", ""),
            life.get("availability", ""),
            cues.get("activity_code", ""),
            cues.get("plan_now", ""),
            cues.get("outfit_now", ""),
            cues.get("activity_started_at"),
            cues.get("plan_today"),
            cues.get("horizons_desk"),
            avatar_rev,
        )
    )
    cur_wx = environment.get("current") or {}
    eco_rev = _short_rev_int(
        (
            environment.get("revision", 0),
            environment.get("credentials", {}).get("revision", 0),
            environment.get("status"),
            environment.get("provider"),
            environment.get("location"),
            environment.get("error"),
            environment.get("primary_error"),
            environment.get("retry_at"),
            environment.get("sunrise"),
            environment.get("sunset"),
            environment.get("updated_at")
            if environment.get("mode") == "real"
            else None,
            cur_wx.get("effect"),
            cur_wx.get("temperature"),
            cur_wx.get("is_day"),
            cur_wx.get("label"),
            (ecology.get("season") or {}).get("solar_term"),
            ecology.get("revision"),
            (ecology.get("veg_patch") or {}).get("stage"),
            (ecology.get("flower_bed") or {}).get("stage"),
            (ecology.get("cat") or {}).get("spot"),
            round(float((ecology.get("vitality") or {}).get("energy") or 0), 1),
            round(float((ecology.get("vitality") or {}).get("inspiration") or 0), 1),
            (ecology.get("vitality") or {}).get("mood"),
        )
    )
    mailbox_rev = _short_rev_int(
        (
            mailbox.get("unopened_count", 0),
            mailbox.get("visitor_mode", ""),
            [
                (v.get("user_id"), v.get("spot"), v.get("form"))
                for v in (mailbox.get("visitors") or [])
            ],
            [(p.get("id"), p.get("status")) for p in (mailbox.get("recent") or [])[:6]],
        )
    )
    keepsakes_rev = _short_rev_int(
        (
            [(k.get("id"), k.get("slot")) for k in (keepsakes.get("displayed") or [])],
            len(keepsakes.get("archive") or []),
            len(keepsakes.get("booklets") or []),
            timeline[0].get("id") if timeline else "",
            timeline[-1].get("id") if timeline else "",
            len(timeline),
        )
    )
    world_space_rev = _short_rev_int(
        (
            world_space.get("world_id"),
            world_space.get("shared"),
            world_space.get("active_guest"),
            [
                (m.get("name"), m.get("place_id"), m.get("travelling"))
                for m in (world_space.get("members") or [])
            ],
            world_space.get("label"),
            world_space.get("recent_encounters"),
        )
    )
    companions_rev = _short_rev_int(companions)
    return {
        "map": map_rev,
        "position": pos_rev,
        "scene": scene_rev,
        "life": life_rev,
        "ecology": eco_rev,
        "mailbox": mailbox_rev,
        "keepsakes": keepsakes_rev,
        "world_space": world_space_rev,
        "companions": companions_rev,
    }


class _ScopeUnavailable(ValueError):
    pass


class _ProjectionUnavailable(ValueError):
    pass


def _projection_stopped(api) -> bool:
    return api.bus.closed or api.plugin._terminating or api.plugin._migrating


def _projection_services(api):
    life = api.plugin.life
    return api.plugin.world, life, life.narrative


def _same_services(before, after) -> bool:
    return all(old is new for old, new in zip(before, after))


def _projection_binding(scope, character, can_write) -> tuple:
    return (
        identity(scope),
        scope.get("umo"),
        scope.get("platform"),
        character["card_id"],
        character["name"],
        character.get("fingerprint"),
        can_write,
    )


def _read_world_projection(api, services, scope, character, key, can_write):
    """Settle clocks and build the projection shared by current waiters."""
    world, life_service, engine = services
    spatial = engine.spatial
    avatar_rev = 0
    scene_key = ""
    pending_outreach = 0
    causal = None
    # Snapshot reads settle clock state. Broadcasting their incidental SQL
    # writes would wake every stream, which would then do the same reads again.
    # Keep disk JSON, Pillow sampling and cross-plugin summaries outside the write lock.
    with engine._db(notify=False) as db:
        db.execute("BEGIN IMMEDIATE")
        if _projection_stopped(api):
            raise _ProjectionUnavailable("世界正在切换，请稍后重试")
        if not _same_services(services, _projection_services(api)):
            raise _ScopeUnavailable("世界实例已切换，请刷新")
        generation = api.bus.generation
        now = engine.clock()
        life = engine._snapshot(db, scope, now) if engine._allowed(scope) else {}
        cues = _life_cues(db, scope, now, life_service)
        actor = life.get("spatial")
        if actor is None:
            spatial.settle(db, scope, now)
            actor = spatial.snapshot(db, scope, now)
        doc = spatial.document(db, key)
        environment = engine.environment.snapshot(db, scope, now, actor)
        environment["credentials"] = engine.environment.credentials.public(db)
        engine.scenes.settle(db, scope, now)
        scene = engine.scenes.snapshot(db, scope, now, admin=True)
        scene["visual_profile"] = engine.visuals.profiles.admin(db, scope)
        scene["visual_profile"]["can_write"] = can_write
        scene_key, _, raw_scene_state = engine.scenes.load(db, scope)
        if engine.ecology is not None:
            engine.ecology.settle(db, scope, environment, raw_scene_state, now)
        if engine.mailbox is not None:
            engine.mailbox.settle(db, scope, raw_scene_state, actor, now)
        if engine.world_spaces is not None:
            engine.world_spaces.settle(db, scope, now, actor, character.get("name", ""))
        recent_mail_at = (
            engine.mailbox.latest_opened_at(db, scope)
            if engine.mailbox is not None
            else 0.0
        )
        ecology = (
            engine.ecology.snapshot(
                db,
                scope,
                now,
                life_state=life,
                scene_state=raw_scene_state,
                env=environment,
                actor=actor,
                recent_mail_at=recent_mail_at,
            )
            if engine.ecology is not None
            else {}
        )
        keepsakes = (
            engine.keepsakes.snapshot(db, scope, raw_scene_state, now)
            if engine.keepsakes is not None
            else {}
        )
        mailbox = (
            engine.mailbox.snapshot(db, scope, now, character)
            if engine.mailbox is not None
            else {}
        )
        world_space = (
            engine.world_spaces.snapshot(db, scope, now)
            if engine.world_spaces is not None
            else {}
        )
        if engine.keepsakes is not None and scene.get("available"):
            cur_env = (environment or {}).get("current") or {}
            r_designs = scene.get("room_designs") or (
                [scene["room_design"]] if scene.get("room_design") else []
            )
            active_rd = next(
                (
                    d
                    for d in r_designs
                    if isinstance(d, dict)
                    and d.get("room_id") == scene.get("room_id")
                    and d.get("furniture")
                ),
                next(
                    (
                        d
                        for d in r_designs
                        if isinstance(d, dict) and d.get("furniture")
                    ),
                    r_designs[0] if r_designs else {},
                ),
            )
            act_step = None
            sc_act = scene.get("action")
            if isinstance(sc_act, dict) and isinstance(sc_act.get("steps"), list):
                idx = sc_act.get("index", 0)
                if isinstance(idx, int) and 0 <= idx < len(sc_act["steps"]):
                    act_step = sc_act["steps"][idx]
            amb_pose = (
                "sleep"
                if life.get("availability") == "asleep"
                or cues.get("activity_code") == "sleeping"
                else (
                    act_step.get("kind")
                    if isinstance(act_step, dict) and act_step.get("kind")
                    else None
                )
                or {
                    "eating": "eat",
                    "gaming": "game",
                    "chores": "sweep",
                    "reading": "read",
                    "writing": "write",
                    "resting": "rest",
                    "walking": "stroll",
                }.get(str(cues.get("activity_code") or ""), "idle")
            )
            amb_loc = (
                "away"
                if scene.get("phase") == "travelling"
                or actor.get("phase") == "travelling"
                else ("room" if scene.get("room_id") else "garden")
            )
            from .cabin_life import ACTIVITIES as CABIN_ACTIVITIES
            if amb_pose in CABIN_ACTIVITIES and amb_loc != "away":
                amb_loc = CABIN_ACTIVITIES[amb_pose].zone
            amb_summary = (
                sc_act.get("label") if isinstance(sc_act, dict) else None
            ) or str(cues.get("plan_now") or life.get("activity") or "日常片刻").split(
                "；环境参考"
            )[0].strip()
            engine.keepsakes.record_keyframe(
                db,
                scope,
                "ambient",
                amb_summary,
                {
                    "timezone": (environment or {}).get("timezone")
                    or (
                        engine._timezone_name()
                        if hasattr(engine, "_timezone_name")
                        else resolve_series_timezone_name(
                            getattr(engine, "host_context", None)
                        )
                    ),
                    "weather": cur_env.get("effect", "clear"),
                    "weather_label": cur_env.get("label", "晴"),
                    "temperature": cur_env.get("temperature"),
                    "curtains": (
                        active_rd.get("curtains")
                        if isinstance(active_rd, dict)
                        else None
                    )
                    or "open",
                    "lighting": (
                        active_rd.get("lighting")
                        if isinstance(active_rd, dict)
                        else None
                    )
                    or "warm",
                    "furniture": active_rd.get("furniture")
                    if isinstance(active_rd, dict)
                    else None,
                    "location": amb_loc,
                    "place_name": scene.get("place_name")
                    or actor.get("place_name")
                    or "",
                    "pose": amb_pose,
                    "cabin_style":scene.get("cabin_style","cottage"),
                    "cat_spot": ((ecology or {}).get("cat") or {}).get(
                        "spot", "bed_nap"
                    ),
                    "outfit_now": cues.get("outfit_now", ""),
                },
                now,
            )
        timeline = (
            engine.keepsakes.timeline_snapshot(db, scope, now)
            if engine.keepsakes is not None
            else []
        )
        try:
            pending_outreach = int(
                db.execute(
                    "SELECT COUNT(*) FROM intents WHERE identity=? AND status='pending' AND expires>?",
                    (key, now),
                ).fetchone()[0]
            )
        except Exception:
            pending_outreach = 0
        saved_modes = [
            r[0]
            for r in db.execute(
                "SELECT mode FROM world_mode_saves WHERE identity=?", (key,)
            )
        ]
        if getattr(engine, "causal", None) is not None:
            causal = engine.causal.projection(db, scope, now)

    try:
        avatar_rev = int(
            api.avatar_library().catalog(scene_key)["selection"].get("revision") or 0
        )
    except Exception:
        avatar_rev = 0
    companions = api._companion_summary(
        scope.get("umo", ""),
        pending_outreach=pending_outreach,
    )

    revisions = compute_domain_revisions(
        doc=doc,
        actor=actor,
        environment=environment,
        scene=scene,
        life=life,
        cues=cues,
        ecology=ecology,
        keepsakes=keepsakes,
        timeline=timeline,
        mailbox=mailbox,
        world_space=world_space,
        companions=companions,
        avatar_rev=avatar_rev,
    )
    revisions.update(
        binding=_short_rev_int((key, scope.get("umo"), character["card_id"])),
        metadata=_short_rev_int((character["name"], saved_modes, can_write)),
    )

    if causal is not None:
        revisions["causal"] = _short_rev_int(
            {
                k: v
                for k, v in causal.items()
                if k not in {"server_time", "last_settled_at"}
            }
        )
    document = (
        None
        if doc is None
        else {k: copy.deepcopy(v) for k, v in doc.items() if k != "graph"}
    )
    suggested_places = (
        api.plugin.maps._suggest(scope, world.store) if document is None else []
    )
    return generation, {
        "schema_version": 1,
        "revisions": revisions,
        "avatar_revision": avatar_rev,
        "causal_life": causal,
        "map": document,
        "actor": actor,
        "environment": environment,
        "scene": scene,
        "saved_modes": saved_modes,
        "character": {"id": character["card_id"], "name": character["name"]},
        "activity": life.get("activity", "生活未启用"),
        "availability": life.get("availability", "unknown"),
        "activity_code": cues["activity_code"],
        "plan_now": cues["plan_now"],
        "outfit_now": cues.get("outfit_now", ""),
        "activity_started_at": cues["activity_started_at"],
        "plan_today": cues["plan_today"],
        "horizons_desk": cues.get("horizons_desk", []),
        "companions": companions,
        "ecology": ecology,
        "keepsakes": keepsakes,
        "mailbox": mailbox,
        "world_space": world_space,
        "timeline": timeline,
        "can_write": can_write,
        "suggested_places": suggested_places,
    }


_DELTA_FIELDS = {
    "causal": ("causal_life",),
    "map": ("actor", "scene"),
    "position": ("actor", "scene"),
    "scene": ("actor", "scene"),
    "life": (
        "activity",
        "availability",
        "activity_code",
        "plan_now",
        "outfit_now",
        "activity_started_at",
        "plan_today",
        "horizons_desk",
        "avatar_revision",
    ),
    "ecology": ("environment", "ecology"),
    "keepsakes": ("keepsakes", "timeline"),
    "mailbox": ("mailbox",),
    "world_space": ("world_space",),
    "companions": ("companions",),
}


def _unchanged_map(doc: dict) -> dict:
    return {
        "revision": doc["revision"],
        "world_id": doc["world_id"],
        "unchanged": True,
    }


def _format_world_payload(
    projection,
    job,
    server_time,
    known_revisions,
    known_map_rev,
    world_id_hash,
) -> dict:
    revisions = dict(projection["revisions"], job=_short_rev_int(job))
    if known_revisions and known_revisions.get("binding") != revisions["binding"]:
        known_revisions = None
        known_map_rev = None
    common = {
        "schema_version": projection["schema_version"],
        "revisions": revisions,
        "server_time": server_time,
        "job": job,
    }
    doc = projection["map"]
    if not known_revisions:
        if (
            doc is not None
            and known_map_rev == doc["revision"]
            and world_id_hash == doc.get("world_id")
        ):
            doc = _unchanged_map(doc)
        return {**projection, **common, "map": doc}

    changed = sorted(
        domain
        for domain, rev in revisions.items()
        if known_revisions.get(domain) != rev
    )
    if not changed:
        return dict(common, delta=True, unchanged=True)
    changed_fields = {
        field for domain in changed for field in _DELTA_FIELDS.get(domain, ())
    }
    if doc is not None and "map" not in changed:
        doc = _unchanged_map(doc)
    return {
        **common,
        **{field: projection[field] for field in changed_fields},
        "delta": True,
        "changed_domains": changed,
        "map": doc,
        "saved_modes": projection["saved_modes"],
        "character": projection["character"],
        "can_write": projection["can_write"],
        "suggested_places": projection["suggested_places"],
    }


async def _resolve_stream_scope(api, umo):
    try:
        return await api.scope(umo)
    except ValueError as exc:
        raise _ScopeUnavailable(str(exc)) from exc


async def assemble_world_payload(
    api,
    umo: str,
    *,
    scope: dict | None = None,
    character: dict | None = None,
    known_map_rev: int | None = None,
    world_id_hash: str = "",
    known_revisions: dict[str, int] | None = None,
) -> tuple[str, dict]:
    """Project in a bounded worker and format revisions for this caller."""
    for _ in range(3):
        projection_io = api.bus._projection_io
        if _projection_stopped(api):
            raise _ProjectionUnavailable("世界正在切换，请稍后重试")
        services = _projection_services(api)
        world, _, engine = services
        if scope is None or character is None:
            scope, character = await _resolve_stream_scope(api, umo)
        scope, character = dict(scope), dict(character)
        can_write = world.web.settings.web_panel_allow_write
        binding = _projection_binding(scope, character, can_write)
        identity_key = binding[0]
        projection_key = (
            tuple(map(id, services)),
            umo,
            binding,
            api.bus.generation,
        )
        try:
            generation, projection = await projection_io.run(
                _read_world_projection,
                api,
                services,
                scope,
                character,
                identity_key,
                can_write,
                key=projection_key,
            )
        except (WorldIOBusy, WorldIOClosed) as exc:
            raise _ProjectionUnavailable("世界正在更新，请稍后重试") from exc
        except sqlite3.OperationalError as exc:
            code = getattr(exc, "sqlite_errorcode", 0) & 0xFF
            if code not in {
                sqlite3.SQLITE_BUSY,
                sqlite3.SQLITE_LOCKED,
            }:
                raise
            raise _ProjectionUnavailable("世界正在更新，请稍后重试") from exc
        if _projection_stopped(api):
            raise _ProjectionUnavailable("世界正在切换，请稍后重试")
        next_scope, next_character = await _resolve_stream_scope(api, umo)
        if _projection_stopped(api):
            raise _ProjectionUnavailable("世界正在切换，请稍后重试")
        current_binding = _projection_binding(
            next_scope,
            next_character,
            api.plugin.world.web.settings.web_panel_allow_write,
        )
        if not _same_services(services, _projection_services(api)):
            raise _ScopeUnavailable("世界实例已切换，请刷新")
        if binding != current_binding:
            # Discard a projection for a binding that changed during the read.
            scope, character = next_scope, next_character
            known_revisions = None
            known_map_rev = None
            continue
        if generation != api.bus.generation:
            # A real publication during the read may have superseded the projection.
            scope, character = next_scope, next_character
            continue

        engine.environment.schedule_projected(projection["environment"])
        job = api.plugin.maps.status(scope)
        return identity_key, _format_world_payload(
            projection,
            job,
            engine.clock(),
            known_revisions,
            known_map_rev,
            world_id_hash,
        )
    raise _ProjectionUnavailable("世界正在更新，请稍后重试")


async def open_sse_stream(api, umo: str, known_raw: str = ""):
    """Return a Starlette StreamingResponse pushing instant world deltas + 18s heartbeats."""
    services = _projection_services(api)
    initial_scope, _ = await _resolve_stream_scope(api, umo)
    initial_key = identity(initial_scope)
    initial_known = parse_known_revisions(known_raw)

    async def event_generator():
        last_revisions = initial_known
        identity_key = initial_key
        # The response may be discarded before its iterable is consumed.
        sub = api.bus.subscribe(identity_key)
        first = True
        retry_delay = 0.0
        unavailable_streak = 0
        loop = asyncio.get_running_loop()
        next_heartbeat = loop.time() + _HEARTBEAT_SECONDS
        try:
            while sub is not None and not sub.closed and not _projection_stopped(api):
                if retry_delay:
                    await asyncio.sleep(retry_delay)
                elif not first:
                    woken = await sub.wait(timeout=_HEARTBEAT_SECONDS)
                    if woken:
                        await asyncio.sleep(0.06)
                if sub.closed or _projection_stopped(api):
                    return
                if not _same_services(services, _projection_services(api)):
                    yield 'data: {"reset":true}\n\n'
                    return
                try:
                    next_key, payload = await assemble_world_payload(
                        api, umo, known_revisions=last_revisions
                    )
                except _ScopeUnavailable:
                    if not sub.closed and not _projection_stopped(api):
                        yield 'data: {"reset":true}\n\n'
                    return
                except _ProjectionUnavailable:
                    if sub.closed or _projection_stopped(api):
                        return
                    if not _same_services(services, _projection_services(api)):
                        yield 'data: {"reset":true}\n\n'
                        return
                    now = loop.time()
                    heartbeat_due = now >= next_heartbeat or (
                        not first and not retry_delay
                    )
                    unavailable_streak += 1
                    if unavailable_streak >= 5:
                        # After saturated backoff rounds, wait for bus/heartbeat instead of spinning.
                        retry_delay = 0.0
                    else:
                        retry_delay = min(
                            _MAX_PROJECTION_RETRY_SECONDS,
                            max(_MIN_PROJECTION_RETRY_SECONDS, 2 * retry_delay),
                        )
                    if heartbeat_due:
                        next_heartbeat = now + _HEARTBEAT_SECONDS
                        yield f": keepalive {int(services[2].clock())}\n\n"
                    continue
                except Exception:
                    return
                if sub.closed or _projection_stopped(api):
                    return
                if not _same_services(services, _projection_services(api)):
                    yield 'data: {"reset":true}\n\n'
                    return
                if next_key != identity_key:
                    api.bus.unsubscribe(sub)
                    sub = api.bus.subscribe(next_key)
                    if sub is None:
                        return
                    identity_key = next_key
                retry_delay = 0.0
                unavailable_streak = 0
                next_heartbeat = loop.time() + _HEARTBEAT_SECONDS
                if first or not payload.get("unchanged"):
                    last_revisions = dict(payload["revisions"])
                    yield f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"
                else:
                    yield f": keepalive {int(payload.get('server_time') or 0)}\n\n"
                first = False
        finally:
            api.bus.unsubscribe(sub)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
