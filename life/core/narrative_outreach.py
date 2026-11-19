"""Outreach consent, contextual care and social chat review mixin for NarrativeEngine."""
from __future__ import annotations

import asyncio
import copy
import datetime as dt
import hashlib
import json
import re
import time
import uuid

if __package__:
    from .narrative_types import (
        CHINA,
        NarrativeValidationError,
        _identity,
        _json,
        _text,
        _timestamp,
        normalize_scope,
    )
else:
    import importlib.util as _ilu
    import sys as _sys
    from pathlib import Path as _Path

    _types_mod = _sys.modules.get("_dls_narrative_types")
    if _types_mod is None:
        _types_spec = _ilu.spec_from_file_location("_dls_narrative_types", _Path(__file__).with_name("narrative_types.py"))
        _types_mod = _ilu.module_from_spec(_types_spec)
        _sys.modules["_dls_narrative_types"] = _types_mod
        _types_spec.loader.exec_module(_types_mod)
    CHINA = _types_mod.CHINA
    NarrativeValidationError = _types_mod.NarrativeValidationError
    _identity = _types_mod._identity
    _json = _types_mod._json
    _text = _types_mod._text
    _timestamp = _types_mod._timestamp
    normalize_scope = _types_mod.normalize_scope


class NarrativeOutreachMixin:
    """Contextual care, social chat openers, member consent and outreach review."""

    _outreach_settings = {"care_wait": "contextual_care", "social_chat": "social_chat"}

    def _outreach_sessions(self, kind: str) -> list | tuple | None:
        setting = self._outreach_settings[kind]
        if self.config.get(setting + "_enabled", True) is not True:
            return None
        sessions = self.config.get(setting + "_sessions", [])
        return sessions if isinstance(sessions, (list, tuple)) else None

    def _outreach_enabled(self, kind: str, scope: dict) -> bool:
        sessions = self._outreach_sessions(kind)
        return (
            sessions is not None
            and self.is_managed(scope)
            and (not sessions or scope["umo"] in sessions)
        )

    def _outreach_scope(self, umo: str) -> dict:
        return dict(self._global_scope(), umo=umo, platform=umo.split(":", 1)[0])

    @staticmethod
    def _has_social_opportunity(event, peer):
        data = event.get("data", {})
        if peer:
            return (
                event.get("actor_id") == peer
                and data.get("directed_to_bot") is True
                and data.get("private_social_opportunity") is True
            )
        return data.get("social_opportunity") is True

    def _outreach_paused(self, db, scope: dict) -> bool:
        keys = ["proactive_paused", "proactive_paused:" + _identity(scope) + ":" + scope["umo"]]
        for key in keys:
            row = db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()
            if row and row[0] == "true":
                return True
        return False

    async def set_outreach_paused(self, paused: bool, scope: dict | None = None) -> dict:
        """Persist per-UMO outreach pauses independently from narrative progression."""
        key = "proactive_paused"
        if scope:
            scope = normalize_scope(scope)
            key += ":" + _identity(scope) + ":" + scope["umo"]
        with self._db() as db:
            db.execute("INSERT INTO metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, "true" if paused else "false"))
        return {"schema_version": 1, "outreach_paused": bool(paused)}

    @staticmethod
    def _explicit_outreach_preference(event):
        """Only a complete, self-authored addressed instruction changes consent.

        Quoted instructions, third-person reports and ordinary subsequent chat
        cannot clear a refusal. Store the event ID, not another copy of text.
        """
        if (event.get("type") not in {"message.received","chat.message"}
                or event.get("actor_id") in {"",None,"bot","system"}
                or event.get("data",{}).get("directed_to_bot") is not True):
            return None
        text = re.sub(r"\s+", "", event.get("text","")).strip("，,。.!！~～")
        target = r"(?:来)?(?:找我(?:聊天|说话)?|联系我|给我发(?:消息|信息)|跟我(?:聊天|说话)|关心我)"
        prefix = r"(?:请|麻烦你|你)?(?:以后|今后|从现在起|现在)?(?:请)?"
        if re.fullmatch(prefix+r"(?:不要|别|不用|停止)(?:再)?主动"+target+r"(?:了)?", text):
            return False
        if re.fullmatch(prefix+r"(?:可以|允许|恢复|重新允许)(?:你)?(?:再)?主动"+target+r"(?:了)?", text):
            return True
        return None

    def _contact_allowed(self, db, scope, uid):
        row = db.execute("SELECT allowed FROM outreach_preferences WHERE identity=? AND umo=? AND user_id=?",
                         (_identity(scope),scope["umo"],str(uid))).fetchone()
        return row is None or bool(row[0])

    @staticmethod
    def _topic_candidate_id(scope, basis, source_key):
        anchor = _json([_identity(scope), scope["umo"], basis, source_key])
        return "topic:" + hashlib.sha256(anchor.encode()).hexdigest()[:32]

    def _grounded_topic_candidates(self, db, scope, now, snapshot=None):
        """Project only durable personal interests and recent personal life facts."""
        snapshot = snapshot or self._snapshot(db, scope, now)
        humanlike = snapshot.get("humanlike", {})
        personal_candidates = []
        for key in ("interests", "preferences"):
            for item in humanlike.get(key, ()):
                if item.get("origin") != "personal" or item.get("status", "active") != "active":
                    continue
                label = _text(item.get("topic") or item.get("text", ""), 120).strip()
                detail = _text(item.get("text", ""), 300).strip()
                source_ids = item.get("source_ids", [])
                if not isinstance(source_ids, list) or not source_ids:
                    continue
                source_key = str(item.get("id") or (source_ids[0] if source_ids else ""))
                if len(label) < 2 or not source_key:
                    continue
                basis = "interest" if key == "interests" else "preference"
                candidate_id = self._topic_candidate_id(scope, basis, source_key)
                personal_candidates.append({
                    "topic_candidate_id": candidate_id,
                    "basis": basis,
                    "topic": label,
                    "context": detail or label,
                    "source_ids": [str(v) for v in source_ids[:8]],
                    "source_fingerprint": hashlib.sha256(_json([
                        basis, source_key, label, detail, source_ids
                    ]).encode()).hexdigest(),
                })

        # Only private-to-the-character global fiction entries can ground an
        # opener from recent experience. Scoped conversations and user claims
        # never become the character's own experience.
        rows = db.execute(
            "SELECT entry_id,text,fact_kind,source_ids FROM diary "
            "WHERE identity=? AND umo='' AND occurred>=? AND occurred<=? "
            "AND fact_kind='fiction' ORDER BY occurred DESC,entry_id DESC LIMIT 12",
            (_identity(scope), now - 86400, now),
        ).fetchall()
        experience_candidates = []
        for row in rows:
            entry_id, body, fact_kind, source_blob = row
            body = _text(body, 300).strip()
            if fact_kind != "fiction" or len(body) < 12:
                continue
            try:
                source_ids = json.loads(source_blob)
            except (TypeError, ValueError):
                source_ids = []
            if not isinstance(source_ids, list) or not source_ids:
                continue
            candidate_id = self._topic_candidate_id(scope, "recent_experience", entry_id)
            experience_candidates.append({
                "topic_candidate_id": candidate_id,
                "basis": "recent_experience",
                "topic": body[:120],
                "context": body,
                "source_ids": [str(v) for v in source_ids[:8]],
                "source_fingerprint": hashlib.sha256(_json([
                    "fiction", entry_id, body, source_ids
                ]).encode()).hexdigest(),
            })
        # Reserve room for recent experiences even if many stable preferences
        # have accumulated; neither source category can crowd out the other.
        return personal_candidates[:4] + experience_candidates[:2]

    def _current_topic_candidate(self, db, scope, now, item):
        if not self._outreach_enabled("social_chat", scope):
            return None
        candidates = self._grounded_topic_candidates(db, scope, now)
        candidate = next((c for c in candidates if c["topic_candidate_id"] == item.get("topic_candidate_id")), None)
        if not candidate:
            return None
        if (candidate["basis"] != item.get("topic_basis")
                or candidate["source_ids"] != item.get("topic_source_ids")
                or candidate["source_fingerprint"] != item.get("topic_source_fingerprint")):
            return None
        return candidate

    def _social_slot_available(self, db, scope, now, candidate_id):
        rows = db.execute(
            "SELECT payload,status,updated FROM intents WHERE identity=? AND umo=? "
            "AND json_extract(payload,'$.kind')='social_chat'",
            (_identity(scope), scope["umo"]),
        ).fetchall()
        for row in rows:
            prior = json.loads(row["payload"])
            if row["status"] in {"pending", "claimed"}:
                return False
            if row["updated"] > now - 7200:
                return False
            if (candidate_id and prior.get("topic_candidate_id") == candidate_id
                    and row["updated"] > now - 86400):
                return False
        return True

    def _observe_outreach_preference(self, db, event):
        allowed = self._explicit_outreach_preference(event)
        if allowed is None:
            return
        scope, uid = event["scope"], event["actor_id"]
        changed = db.execute("INSERT INTO outreach_preferences VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(identity,umo,user_id) DO UPDATE SET allowed=excluded.allowed,occurred=excluded.occurred,event_id=excluded.event_id "
            "WHERE excluded.occurred>=outreach_preferences.occurred",
            (_identity(scope),scope["umo"],uid,int(allowed),event["occurred_at"],event["event_id"])).rowcount
        if changed and not allowed:
            db.execute("UPDATE intents SET status='cancelled',updated=? WHERE identity=? AND umo=? "
                "AND status IN ('pending','claimed') AND json_extract(payload,'$.recipient_user_id')=?",
                (self.clock(),_identity(scope),scope["umo"],uid))

    def _migrate_outreach_preferences(self, db):
        if db.execute("SELECT 1 FROM metadata WHERE key='outreach_preferences_v1'").fetchone():
            return
        latest = {}
        # Small, one-time filtered scan. Preserve every original event/status.
        for row in db.execute("SELECT payload FROM events WHERE json_extract(payload,'$.text') LIKE '%主动%' "
                              "ORDER BY occurred,received,event_id"):
            event = json.loads(row[0])
            if self._explicit_outreach_preference(event) is not None:
                latest[(_identity(event["scope"]),event["scope"]["umo"],event["actor_id"])] = event
        for event in latest.values():
            self._observe_outreach_preference(db,event)
        db.execute("INSERT INTO metadata VALUES('outreach_preferences_v1','1')")

    def _care_wait(self, raw, scope, sources, now):
        """A member's actual addressed statement authorizes one delayed check-in."""
        if not self._outreach_enabled("care_wait", scope):
            raise NarrativeValidationError("contextual_care_disabled_for_this_conversation", "Contextual care disabled for this conversation")
        if not isinstance(raw, dict):
            raise NarrativeValidationError("invalid_care_wait", "Invalid care wait")
        uid = _text(raw.get("subject_id", ""), 300, "subject_id")
        with self._db() as db:
            if not self._contact_allowed(db, scope, uid):
                raise NarrativeValidationError("outreach_member_opted_out", "Member declined proactive contact")
        peer = self._private_peer(scope["umo"])
        if not uid or uid in {"bot", "system"} or (peer and uid != peer):
            raise NarrativeValidationError("care_needs_a_concrete_member", "Care needs a concrete member")
        ids = self._sources(raw.get("source_ids"), sources)
        quote = _text(raw.get("evidence_quote", ""), 600, "evidence_quote")
        evidence = [sources[s] for s in ids if sources[s]["type"] in {"message.received", "chat.message"}
                    and sources[s]["actor_id"] == uid and quote and quote in sources[s]["text"]
                    and sources[s].get("data", {}).get("directed_to_bot") is True]
        if not evidence:
            raise NarrativeValidationError("care_needs_an_exact_self_authored_addressed_source_quote", "Care needs an exact, self-authored, addressed source quote")
        source = max(evidence, key=lambda e: (e["occurred_at"], e["received_at"]))
        if source["occurred_at"] < now - 86400:
            raise NarrativeValidationError("old_queued_evidence_cannot_start_a_new_care_wait", "Old queued evidence cannot start a new care wait")
        reason_kind = raw.get("reason_kind")
        if reason_kind not in {"health_concern", "travel_checkin", "agreed_checkin"}:
            raise NarrativeValidationError("ordinary_silence_is_not_a_care_reason", "Ordinary silence is not a care reason")
        item = self._intent(raw, scope, sources, now)
        if item["not_before"] < now + 1800:
            raise NarrativeValidationError("care_must_allow_at_least_thirty_minutes", "Care must allow at least thirty minutes")
        anchor = _json([_identity(scope), scope["umo"], uid, source["event_id"]])
        item.update(intent_id="care:" + hashlib.sha256(anchor.encode()).hexdigest()[:32],
                    kind="care_wait", recipient_user_id=uid, reason_kind=reason_kind,
                    evidence_quote=quote, source_event_id=source["event_id"],
                    source_occurred_at=source["occurred_at"],
                    source_message_id=str(source.get("data", {}).get("care_activity_id") or source["source_ids"][0]),
                    waiting_for=_text(raw.get("waiting_for", ""), 300, "waiting_for"))
        return item

    def _cancel_care_on_input(self, db, event, now):
        if event["type"] not in {"message.received", "chat.message"} or event["actor_id"] in {"", "bot", "system"}:
            return
        scope = event["scope"]
        changed = False
        rows = db.execute("SELECT intent_id,payload FROM intents WHERE identity=? AND umo=? AND status IN ('pending','claimed')",
                          (_identity(scope), scope["umo"])).fetchall()
        for row in rows:
            item = json.loads(row["payload"])
            if (item.get("kind") not in {"care_wait","social_chat"} or item.get("recipient_user_id") != event["actor_id"]
                    or event["event_id"] in item["source_ids"]
                    or event["occurred_at"] < item.get("source_occurred_at", 0)):
                continue
            item.update(status="cancelled", resolution="member_returned", resolved_by=event["event_id"])
            db.execute("UPDATE intents SET status='cancelled',payload=?,updated=? WHERE intent_id=?",
                       (_json(item), now, row["intent_id"]))
            changed = True
        if changed:
            db.execute("UPDATE lives SET revision=revision+1 WHERE identity=?", (_identity(scope),))
            db.execute("UPDATE scopes SET revision=revision+1 WHERE identity=? AND umo=?", (_identity(scope), scope["umo"]))

    def _care_current(self, db, item):
        kind = item.get("kind")
        if kind not in self._outreach_settings:
            return True
        scope = item["scope"]
        if not self._outreach_enabled(kind, scope):
            return False
        peer = self._private_peer(scope["umo"])
        if peer and item["recipient_user_id"] != peer:
            return False
        if kind == "social_chat" and item.get("topic_candidate_id"):
            candidate = self._current_topic_candidate(db, scope, self.clock(), item)
            if candidate is None:
                return False
        if not self._contact_allowed(db, scope, item["recipient_user_id"]):
            return False
        presence = db.execute("SELECT value FROM metadata WHERE key=?",
                              ("care_presence:" + _json([scope["umo"], item["recipient_user_id"]]),)).fetchone()
        if presence:
            value = json.loads(presence[0])
            if (value["occurred_at"] >= item["source_occurred_at"]
                    and value["message_id"] != item.get("source_message_id")):
                return False
        anchor = db.execute(
            "SELECT rowid FROM events WHERE event_id=? AND identity=? AND umo=?",
            (item["source_event_id"], _identity(scope), scope["umo"]),
        ).fetchone()
        if not anchor:
            return False
        for row in db.execute("SELECT payload FROM events WHERE identity=? AND umo=? AND rowid>?",
                              (_identity(scope), scope["umo"], anchor[0])):
            event = json.loads(row[0])
            if (event["type"] in {"message.received", "chat.message"}
                    and event["actor_id"] == item["recipient_user_id"]
                    and event["event_id"] not in item["source_ids"]
                    and event["occurred_at"] >= item["source_occurred_at"]):
                return False
        return True

    def _social_chat(self, raw, scope, sources, now):
        """An opener needs repeated, reciprocal topic evidence, never just silence."""
        if not self._outreach_enabled("social_chat", scope):
            raise NarrativeValidationError(
                "social_chat_disabled", "Social chat is not enabled here"
            )
        uid = _text(raw.get("subject_id", ""), 100)
        with self._db() as db:
            if not self._contact_allowed(db, scope, uid):
                raise NarrativeValidationError("outreach_member_opted_out", "Member declined proactive contact")
        candidate_id = _text(raw.get("topic_candidate_id", ""), 100)
        topic = _text(raw.get("topic", ""), 120)
        quote = _text(raw.get("evidence_quote", ""), 600)
        peer = self._private_peer(scope["umo"])
        if (
            uid in {"", "bot", "system"}
            or (peer and uid != peer)
            or len(topic) < 2
            or len(quote) < (4 if candidate_id else 8)
            or (not candidate_id and topic not in quote)
            or topic.casefold() in {"你好", "在吗", "聊天", "关心", "hello", "hi"}
        ):
            raise NarrativeValidationError(
                "social_topic_evidence_required", "A concrete shared topic is required"
            )
        ids = self._sources(raw.get("source_ids"), sources)
        evidence = [
            sources[s]
            for s in ids
            if sources[s]["type"] in {"message.received", "chat.message"}
            and sources[s]["actor_id"] == uid
            and (self._has_social_opportunity(sources[s], peer)
                 if candidate_id else sources[s].get("data", {}).get("directed_to_bot") is True)
            and quote in sources[s]["text"]
        ]
        if not evidence:
            raise NarrativeValidationError(
                "social_exact_member_quote_required",
                "An exact addressed member quote is required",
            )
        source = max(evidence, key=lambda e: e["occurred_at"])
        if candidate_id and not now - 900 <= source["occurred_at"] <= now:
            raise NarrativeValidationError("social_source_not_recent", "A grounded opener needs a current interaction")
        if not candidate_id and not now - 86400 <= source["occurred_at"] <= now - 1800:
            raise NarrativeValidationError(
                "social_source_not_ready",
                "Wait for a natural break in the current conversation",
            )
        with self._db() as db:
            history = [
                json.loads(r[0])
                for r in db.execute(
                    "SELECT payload FROM events WHERE identity=? AND umo=? AND occurred>=? AND occurred<=? "
                    "AND status NOT IN ('blocked_policy') ORDER BY occurred DESC LIMIT 1000",
                    (_identity(scope), scope["umo"], now - 7 * 86400, now),
                )
            ]
        if candidate_id:
            with self._db() as db:
                candidate = next((c for c in self._grounded_topic_candidates(
                    db, scope, now
                ) if c["topic_candidate_id"] == candidate_id), None)
        else:
            candidate = None
        if candidate_id and candidate is None:
            raise NarrativeValidationError("social_topic_candidate_missing", "The grounded topic is no longer available")
        if candidate_id and topic != candidate["topic"]:
            raise NarrativeValidationError("social_topic_must_match_candidate", "The selected topic must match its program-provided candidate")
        if not candidate_id:
            own = [
                e for e in history
                if e["type"] in {"message.received", "chat.message"}
                and e["actor_id"] == uid
                and e.get("data", {}).get("directed_to_bot") is True
                and topic in e["text"]
            ]
            replies = [
                e for e in history
                if e["type"] == "delivery.success"
                and e.get("data", {}).get("recipient_user_id") == uid
                and not e.get("data", {}).get("intent_id")
                and topic in e["text"]
            ]
            distinct = {str(e.get("data", {}).get("care_activity_id") or (e.get("source_ids") or [e["event_id"]])[0]) for e in own}
            if len(distinct) < 2 or not replies:
                raise NarrativeValidationError("social_reciprocal_topic_required", "The topic must have been discussed with this member")
        if any(
            any(
                cue in e["text"]
                for cue in (
                    "别主动",
                    "不要主动",
                    "别找我",
                    "别打扰",
                    "不要打扰",
                    "不想聊",
                    "我要睡",
                    "我去睡",
                    "在忙",
                )
            )
            for e in history
            if e.get("actor_id") == uid and e["occurred_at"] >= source["occurred_at"]
        ):
            raise NarrativeValidationError(
                "social_member_unavailable", "Member has declined or is unavailable"
            )
        item = self._intent(raw, scope, sources, now)
        with self._db() as db:
            if not self._social_slot_available(db, scope, now, candidate_id):
                raise NarrativeValidationError("social_chat_cooldown", "A recent social invitation already uses this conversation slot")
        if candidate and (
            item["not_before"] < now + 60
            or item["not_before"] > now + 1800
            or item["expires_at"] > now + 7200
        ):
            raise NarrativeValidationError(
                "grounded_social_window_invalid", "A grounded opener must use a short current window"
            )
        anchor = _json([_identity(scope), scope["umo"], uid, topic, source["event_id"]])
        item.update(
            intent_id="social:" + hashlib.sha256(anchor.encode()).hexdigest()[:32],
            kind="social_chat",
            recipient_user_id=uid,
            topic=topic,
            topic_candidate_id=candidate_id or None,
            topic_basis=candidate["basis"] if candidate else "shared_topic",
            topic_source_ids=candidate["source_ids"] if candidate else [],
            topic_source_fingerprint=candidate["source_fingerprint"] if candidate else "",
            topic_context=candidate["context"] if candidate else "",
            topic_fact_kind="fiction" if candidate and candidate["basis"] == "recent_experience" else "",
            evidence_quote=quote,
            source_event_id=source["event_id"],
            source_occurred_at=source["occurred_at"],
            source_message_id=str(
                source.get("data", {}).get("care_activity_id") or source["source_ids"][0]
            ),
        )
        if not candidate and item["not_before"] < now + 1800:
            raise NarrativeValidationError("legacy_social_must_wait_for_quiet", "An opener without a grounded topic must wait for a quiet break")
        item["expires_at"] = min(item["expires_at"], now + (7200 if candidate else 86400))
        if item["not_before"] >= item["expires_at"]:
            raise NarrativeValidationError("social_invalid_window", "Invalid opener window")
        item["topic_source"] = {
            "candidate_id": candidate["topic_candidate_id"] if candidate else "",
            "basis": candidate["basis"] if candidate else "shared_topic",
            "text": candidate["context"] if candidate else topic,
            "fact_kind": (
                "fiction" if candidate and candidate["basis"] == "recent_experience"
                else "subjective" if candidate else ""
            ),
            "source_ids": candidate["source_ids"] if candidate else list(source.get("source_ids", [])),
            "fingerprint": candidate["source_fingerprint"] if candidate else "",
        }
        return item

    async def review_outreach(self):
        """Inspect fresh evidence independently of the life FIFO and its budget.

        Persist no drafts and do not send. Review a changed evidence set at most
        once per five minutes; failures retry after fifteen minutes.
        """
        if (
            self._closed
            or self.config.get("mode") != "narrative"
            or not self.config.get("persona_id")
            or not self._has_targets()
            or all(self._outreach_sessions(kind) is None for kind in self._outreach_settings)
        ):
            return []
        results = []
        async with self._outreach_lock:
            now = self.clock()
            with self._db() as db:
                sessions = [
                    row[0] for row in db.execute(
                        "SELECT DISTINCT umo FROM events WHERE identity=? AND umo<>'' "
                        "AND occurred BETWEEN ? AND ? AND status!='blocked_policy' "
                        "AND json_extract(payload,'$.type') IN ('message.received','chat.message') "
                        "AND (json_extract(payload,'$.data.directed_to_bot')=1 "
                        "OR json_extract(payload,'$.data.social_opportunity')=1) ORDER BY umo",
                        (_identity(self._global_scope()), now - 86400, now),
                    )
                ]
            for umo in sessions:
                scope = self._outreach_scope(umo)
                care_enabled = self._outreach_enabled("care_wait", scope)
                social_enabled = self._outreach_enabled("social_chat", scope)
                if not (care_enabled or social_enabled):
                    continue
                now = self.clock()
                identity = _identity(scope)
                peer = self._private_peer(umo)
                key = "outreach_review:" + _json([identity, umo])
                policy_key = hashlib.sha256(_json([
                    care_enabled,
                    social_enabled,
                    self.config.get("narrative_provider_id",""),
                    dt.datetime.fromtimestamp(now,CHINA).hour >= 8,
                ]).encode()).hexdigest()
                with self._db() as db:
                    if self._paused(db, scope) or self._outreach_paused(db, scope):
                        continue
                    saved = db.execute(
                        "SELECT value FROM metadata WHERE key=?", (key,)
                    ).fetchone()
                    marker = json.loads(saved[0]) if saved else {}
                    if marker.get("next_at", 0) > now and marker.get("policy_key") == policy_key:
                        continue
                    rows = db.execute(
                        "SELECT payload FROM events WHERE identity=? AND umo=? AND occurred>=? AND occurred<=? "
                        "AND status!='blocked_policy' AND (json_extract(payload,'$.type')='delivery.success' OR "
                        "(json_extract(payload,'$.type') IN ('message.received','chat.message') AND "
                        "(json_extract(payload,'$.data.directed_to_bot')=1 OR json_extract(payload,'$.data.social_opportunity')=1))) "
                        "ORDER BY occurred DESC,event_id DESC LIMIT 80",
                        (identity, umo, now - 86400, now),
                    ).fetchall()
                    events, size = [], 0
                    for row in rows:
                        e = json.loads(row[0])
                        target = (e.get("data",{}).get("recipient_user_id") if e["type"]=="delivery.success"
                                  else e.get("actor_id"))
                        if peer and target != peer:
                            continue
                        if target and not self._contact_allowed(db,scope,target):
                            continue
                        length = len(e.get("text", ""))
                        if len(events) >= 40 or size + length > 16000:
                            break
                        events.append(e)
                        size += length
                    events.reverse()
                    members = {
                        e["actor_id"]
                        for e in events
                        if e["type"] in {"message.received", "chat.message"}
                        and e["actor_id"] not in {"", "bot", "system"}
                    }
                    if not members:
                        continue
                    quiet = [
                        uid
                        for uid in sorted(members)
                        if max(e["occurred_at"] for e in events if e.get("actor_id") == uid)
                        <= now - 1800
                    ]
                    snapshot = self._snapshot(db, scope, now)
                    topic_candidates = (
                        self._grounded_topic_candidates(db, scope, now, snapshot)
                        if social_enabled else []
                    )
                    opportunity_members = sorted({
                        e["actor_id"] for e in events
                        if e["type"] in {"message.received", "chat.message"}
                        and e["actor_id"] not in {"", "bot", "system"}
                        and self._has_social_opportunity(e, peer)
                        and now - 900 <= e.get("occurred_at", 0) <= now
                        and self._contact_allowed(db, scope, e["actor_id"])
                    })
                    evidence_key = hashlib.sha256(_json([e["event_id"] for e in events]).encode()).hexdigest()
                    if marker.get("status") == "policy_refusal" and marker.get("evidence_key") == evidence_key:
                        continue
                    fingerprint = hashlib.sha256(_json([
                        [e["event_id"] for e in events], quiet, policy_key,
                        opportunity_members, [
                            [c["topic_candidate_id"], c["source_fingerprint"]]
                            for c in topic_candidates
                        ],
                        snapshot.get("availability"), snapshot.get("scope_revision"),
                    ]).encode()).hexdigest()
                    if (
                        marker.get("fingerprint") == fingerprint
                        and marker.get("status") == "ok"
                        and now - marker.get("last_at",0) < 1800
                    ):
                        continue
                    recent_intents = [
                        dict(json.loads(r["payload"]), status=r["status"])
                        for r in db.execute(
                            "SELECT payload,status FROM intents WHERE identity=? AND umo=? AND updated>?",
                            (identity, umo, now - 86400),
                        )
                    ]
                    db.execute(
                        "INSERT INTO metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (
                            key,
                            _json(
                                {
                                    "last_at": now,
                                    "next_at": now + 900,
                                    "fingerprint": fingerprint,
                                    "status": "running",
                                    "policy_key": policy_key,
                                    "evidence_key": evidence_key,
                                }
                            ),
                        ),
                    )
                request = {
                    "schema_version": 1,
                    "scope": scope,
                    "now": now,
                    "outreach_only": True,
                    "events": events,
                    "snapshot": {
                        "humanlike": snapshot.get("humanlike", {}),
                        "availability": snapshot.get("availability"),
                    },
                    "care_policy": {
                        "enabled": care_enabled,
                        "min_wait_seconds": 1800,
                    },
                    "social_policy": {
                        "enabled": social_enabled,
                        "quiet_members": quiet,
                        "opportunity_members": opportunity_members,
                        "topic_candidates": topic_candidates,
                    },
                    "recent_intents": [
                        {
                            k: i.get(k)
                            for k in (
                                "kind",
                                "status",
                                "recipient_user_id",
                                "topic",
                                "source_event_id",
                            )
                        }
                        for i in recent_intents
                    ],
                    "local_datetime": dt.datetime.fromtimestamp(now, CHINA).isoformat(),
                    "inference_call_id": str(uuid.uuid4()),
                }
                started = time.monotonic()
                status = "ok"
                added = 0
                rejected = []
                sources = {e["event_id"]: e for e in events}
                try:
                    raw = await asyncio.wait_for(
                        self.model(copy.deepcopy(request)),
                        min(
                            90,
                            max(1, float(self.config.get("narrative_timeout_seconds", 90))),
                        ),
                    )
                    if not isinstance(raw, dict) or set(raw) - {
                        "schema_version",
                        "no_change",
                        "care_waits",
                        "chat_openers",
                    }:
                        raise NarrativeValidationError(
                            "outreach_effects_only", "Unexpected outreach effects"
                        )
                    intents = []
                    for field, validator in (
                        ("care_waits", self._care_wait),
                        ("chat_openers", self._social_chat),
                    ):
                        values = raw.get(field, [])
                        if not isinstance(values, list) or len(values) > 2:
                            rejected.append("outreach_candidate_limit")
                            continue
                        for value in values:
                            try:
                                if not isinstance(value,dict):
                                    raise NarrativeValidationError("outreach_candidate_shape","Candidate must be an object")
                                intents.append(validator(value, scope, sources, now))
                            except (ValueError,TypeError,AttributeError) as exc:
                                rejected.append(getattr(exc,"code",type(exc).__name__))
                    if raw.get("no_change") is True and intents:
                        raise NarrativeValidationError(
                            "outreach_no_change_conflict", "no_change cannot create intents"
                        )
                    if rejected:
                        status = "partial" if intents else "invalid"
                    with self._db() as db:
                        db.execute("BEGIN IMMEDIATE")
                        if (
                            not self.is_managed(scope)
                            or self._paused(db, scope)
                            or self._outreach_paused(db, scope)
                        ):
                            continue
                        for code in rejected:
                            db.execute("INSERT INTO validation_failures VALUES(?,?,?,?)",
                                (str(uuid.uuid4()),_json(list(sources)),"outreach."+str(code)[:80],now))
                        for item in intents:
                            if not self._care_current(db, item):
                                continue
                            if (item.get("kind") == "social_chat"
                                    and not self._social_slot_available(
                                        db, scope, now, item.get("topic_candidate_id", "")
                                    )):
                                continue
                            previous = [
                                dict(json.loads(r["payload"]), status=r["status"])
                                for r in db.execute(
                                    "SELECT payload,status FROM intents WHERE identity=? AND umo=?",
                                    (identity, umo),
                                )
                            ]
                            if any(
                                old.get("source_ids") == item["source_ids"]
                                or (
                                    old.get("recipient_user_id")
                                    == item["recipient_user_id"]
                                    and (
                                        old["status"] in {"pending", "claimed"}
                                        or (
                                            item["kind"] == "social_chat"
                                            and old.get("created_at", 0) > now - 86400
                                        )
                                    )
                                )
                                for old in previous
                            ):
                                continue
                            added += db.execute(
                                "INSERT OR IGNORE INTO intents VALUES(?,?,?,?,?,?,?,?)",
                                (
                                    item["intent_id"],
                                    identity,
                                    umo,
                                    _json(item),
                                    "pending",
                                    item["not_before"],
                                    item["expires_at"],
                                    now,
                                ),
                            ).rowcount
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    status = "timeout" if isinstance(exc, TimeoutError) else "invalid"
                    if self._is_policy_refusal(exc):
                        status = "policy_refusal"
                    error = getattr(exc, "code", type(exc).__name__)
                    with self._db() as db:
                        db.execute(
                            "INSERT INTO validation_failures VALUES(?,?,?,?)",
                            (
                                str(uuid.uuid4()),
                                _json(list(sources)),
                                "outreach." + str(error)[:80],
                                now,
                            ),
                        )
                with self._db() as db:
                    db.execute(
                        "INSERT INTO metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (
                            key,
                            _json(
                                {
                                    "last_at": now,
                                    "next_at": now + (300 if status in {"ok","partial"} else 900),
                                    "fingerprint": fingerprint,
                                    "status": "ok"
                                    if status == "partial"
                                    else status,
                                    "candidates": added,
                                    "rejected": len(rejected),
                                    "policy_key": policy_key,
                                    "evidence_key": evidence_key,
                                }
                            ),
                        ),
                    )
                self._call(
                    request["inference_call_id"],
                    identity,
                    umo,
                    now,
                    started,
                    status,
                    "outreach",
                )
                results.append({"status": status, "candidates": added})
        return results

    def observe_member_activity(self, umo, uid, message_id, occurred_at):
        """Content-free presence watermark, including inputs that never trigger a reply."""
        if (
            not self.config.get("persona_id")
            or not isinstance(umo, str)
            or not umo
            or not uid
            or uid in {"bot", "system"}
            or not message_id
        ):
            return {"accepted": False}
        scope = self._outreach_scope(umo)
        if not any(self._outreach_enabled(kind, scope) for kind in self._outreach_settings):
            return {"accepted": False}
        uid, message_id = str(uid), str(message_id)
        peer = self._private_peer(umo)
        if peer and uid != peer:
            return {"accepted": False}
        stamp = min(_timestamp(occurred_at), self.clock())
        key = "care_presence:" + _json([umo, uid])
        value = _json({"occurred_at": stamp, "message_id": message_id})
        cancelled = False
        with self._db(notify=False) as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT value FROM metadata WHERE key=?", (key,)
            ).fetchone()
            if previous and json.loads(previous[0])["occurred_at"] > stamp:
                return {"accepted": False}
            if not previous or previous[0] != value:
                db.execute(
                    "INSERT INTO metadata VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (key, value),
                )
            for row in db.execute(
                "SELECT intent_id,payload FROM intents WHERE umo=? AND status IN ('pending','claimed')",
                (umo,),
            ).fetchall():
                item = json.loads(row["payload"])
                if (
                    item.get("kind") in {"care_wait", "social_chat"}
                    and item.get("recipient_user_id") == uid
                    and not self._care_current(db, item)
                ):
                    item.update(
                        status="cancelled",
                        resolution="member_returned",
                        resolved_by=message_id,
                    )
                    updated = db.execute(
                        "UPDATE intents SET status='cancelled',payload=?,updated=? WHERE intent_id=?",
                        (_json(item), self.clock(), row["intent_id"]),
                    )
                    cancelled = updated.rowcount > 0 or cancelled
        if cancelled:
            self._notify_db_write()
        if hasattr(self, "note_activity"):
            self.note_activity(stamp)
        return {"accepted": True}
