"""Durable, debounced environment observations; never sends chat messages."""

import hashlib
import json
import math
import uuid

from .spatial import identity, encode

SETTLE_SECONDS = 120
COOLDOWN_SECONDS = 1800
MAX_GAP_SECONDS = 900


def sample(environment):
    if (
        not isinstance(environment, dict)
        or environment.get("available") is not True
        or environment.get("stale")
        or environment.get("status") != "ready"
    ):
        return None
    current = environment.get("current") or {}
    temperature = current.get("temperature")
    wind = current.get("wind_speed")
    if type(temperature) not in (int, float) or not math.isfinite(temperature):
        return None
    return {
        "temperature": temperature,
        "wind_speed": wind
        if type(wind) in (int, float) and math.isfinite(wind)
        else None,
        "precipitation_kind": current.get("effect")
        if current.get("effect") in {"rain", "snow"}
        else "dry",
        "is_day": current.get("is_day")
        if type(current.get("is_day")) is bool
        else None,
        "label": str(current.get("label", "未知"))[:40],
    }


def changes(before, after):
    result = []
    if before["precipitation_kind"] != after["precipitation_kind"]:
        result.append("precipitation_changed")
    delta = after["temperature"] - before["temperature"]
    if abs(delta) >= 5:
        result.append("temperature_rise" if delta > 0 else "temperature_drop")
    a, b = before.get("wind_speed"), after.get("wind_speed")
    if a is not None and b is not None:
        # Separate enter/exit thresholds prevent jitter near 30 km/h.
        if a < 30 and b >= 30:
            result.append("wind_increased")
        elif a >= 30 and b <= 20:
            result.append("wind_eased")
    if (
        before.get("is_day") is not None
        and after.get("is_day") is not None
        and before["is_day"] != after["is_day"]
    ):
        result.append("daylight_changed")
    return result


class WeatherLifeObserver:
    def __init__(self, environment):
        self.environment = environment
        self.engine = environment.engine
        with self.engine._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS world_weather_life(identity TEXT PRIMARY KEY,state TEXT NOT NULL)"
            )

    def _save(self, db, key, state):
        db.execute(
            "INSERT INTO world_weather_life VALUES(?,?) ON CONFLICT(identity) DO UPDATE SET state=excluded.state",
            (key, encode(state)),
        )

    @staticmethod
    def _cancel(db, pending, reason):
        if pending:
            db.execute(
                "UPDATE events SET status='observed_only',error=? WHERE event_id=? AND status='pending'",
                ("weather:" + reason, pending["event_id"]),
            )

    def poll(self, db, scope, now, *, suspended=False):
        """Called only by the existing global life scheduler inside its transaction."""
        if scope.get("umo"):
            return None
        key = identity(scope)
        row = db.execute(
            "SELECT state FROM world_weather_life WHERE identity=?", (key,)
        ).fetchone()
        state = json.loads(row[0]) if row else {}
        env = self.environment.snapshot(db, scope, now)
        current = sample(env)
        context = json.dumps(
            [
                env.get("mode"),
                env.get("provider"),
                env.get("latitude"),
                env.get("longitude"),
                env.get("timezone"),
                env.get("revision"),
            ],
            sort_keys=True,
        )
        reset = (
            suspended
            or current is None
            or not state.get("baseline")
            or state.get("context") != context
            or now < state.get("seen_at", now)
            or now - state.get("seen_at", now) > MAX_GAP_SECONDS
        )
        if reset:
            self._cancel(db, state.get("pending"), "observation_reset")
            if (
                row is not None
                and not state.get("pending")
                and state.get("context") == context
                and state.get("baseline") is None
                and state.get("sample") is None
                and state.get("candidate") is None
                and 0 <= now - float(state.get("seen_at") or 0) < 300
            ):
                return None
            state = {
                "context": context,
                "baseline": current,
                "sample": current,
                "seen_at": now,
                "last_emit": state.get("last_emit", 0),
                "candidate": None,
                "pending": None,
            }
            self._save(db, key, state)
            return None
        prev_sample = state.get("sample")
        prev_seen_at = float(state.get("seen_at") or 0)
        prev_candidate = state.get("candidate")
        state.update(sample=current, seen_at=now)
        pending = state.get("pending")
        if pending:
            record = db.execute(
                "SELECT status,next_retry FROM events WHERE event_id=?",
                (pending["event_id"],),
            ).fetchone()
            after = pending["data"]["environment_change"]["after"]
            if now - pending["occurred_at"] > 1800 or changes(after, current):
                self._cancel(db, pending, "superseded")
                state["pending"] = None
            elif record and record["status"] != "pending":
                state["pending"] = None
            else:
                if prev_sample != current or not (0 <= now - prev_seen_at < 300):
                    self._save(db, key, state)
                return pending if not record or record["next_retry"] <= now else None
        reasons = changes(state["baseline"], current)
        if not reasons:
            state["candidate"] = None
            if (
                prev_candidate is not None
                or prev_sample != current
                or not (0 <= now - prev_seen_at < 300)
            ):
                self._save(db, key, state)
            return None
        signature = json.dumps(
            [reasons, current["precipitation_kind"], current["is_day"]]
        )
        candidate = state.get("candidate")
        if not candidate or candidate["signature"] != signature:
            state["candidate"] = {"signature": signature, "since": now}
            self._save(db, key, state)
            return None
        if (
            now - candidate["since"] < SETTLE_SECONDS
            or now - state.get("last_emit", 0) < COOLDOWN_SECONDS
        ):
            self._save(db, key, state)
            return None
        event = {
            "schema_version": 1,
            "event_id": "life.weather:"
            + hashlib.sha256(key.encode()).hexdigest()[:16]
            + ":"
            + uuid.uuid4().hex,
            "type": "life.tick",
            "scope": dict(scope),
            "occurred_at": now,
            "received_at": now,
            "fact_kind": "fiction",
            "text": "角色环境有明显变化，请评估是否需要调整当前日常或未来安排；可以保持不变，不发送天气播报。",
            "data": {
                "trigger": "weather_change",
                "environment_change": {
                    "reasons": reasons,
                    "before": state["baseline"],
                    "after": current,
                    "source": env.get("source"),
                    "fact_kind": env.get("fact_kind"),
                    "location": env.get("location"),
                    "observed_at": now,
                    "no_contact_authorization": True,
                },
            },
        }
        state.update(pending=event, baseline=current, candidate=None, last_emit=now)
        self._save(db, key, state)
        return event

    def acknowledge(self, scope, observed_at):
        """A regular hourly evaluation already considered this observation."""
        with self.engine._db() as db:
            key = identity(scope)
            row = db.execute(
                "SELECT state FROM world_weather_life WHERE identity=?", (key,)
            ).fetchone()
            if not row:
                return
            state = json.loads(row[0])
            if state.get("seen_at") != observed_at:
                return
            pending = state.get("pending")
            if pending:
                event = db.execute(
                    "SELECT status FROM events WHERE event_id=?", (pending["event_id"],)
                ).fetchone()
                if not event or event[0] == "pending":
                    return
            state.update(baseline=state.get("sample"), candidate=None, pending=None)
            self._save(db, key, state)
