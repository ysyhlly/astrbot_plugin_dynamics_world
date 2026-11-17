"""Structured LLM output, humanlike memory, behavior feedback and commitment validation mixin."""
from __future__ import annotations

import copy
import datetime as dt
import json
import re
import uuid
from typing import Any

if __package__:
    from .narrative_types import (
        ACTIVITIES,
        AVAILABILITIES,
        CHINA,
        COMMITMENT_STATUSES,
        FACT_KINDS,
        TERMINAL_INTENTS,
        NarrativeValidationError,
        _identity,
        _json,
        _text,
        _timestamp,
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
    ACTIVITIES = _types_mod.ACTIVITIES
    AVAILABILITIES = _types_mod.AVAILABILITIES
    CHINA = _types_mod.CHINA
    COMMITMENT_STATUSES = _types_mod.COMMITMENT_STATUSES
    FACT_KINDS = _types_mod.FACT_KINDS
    TERMINAL_INTENTS = _types_mod.TERMINAL_INTENTS
    NarrativeValidationError = _types_mod.NarrativeValidationError
    _identity = _types_mod._identity
    _json = _types_mod._json
    _text = _types_mod._text
    _timestamp = _types_mod._timestamp


class NarrativeValidationMixin:
    """Evidence-attributed validation for state transitions, humanlike traits, commitments and intents."""

    def _sources(self, value: Any, source_map: dict) -> list[str]:
        if not isinstance(value, list) or not value or len(value) > 50:
            raise NarrativeValidationError("a_change_requires_source_event_ids", "A change requires source event IDs")
        if not all(isinstance(item, str) and item in source_map for item in value):
            raise NarrativeValidationError("changes_may_only_reference_events_in_this_scope", "Changes may only reference events in this scope")
        return list(dict.fromkeys(value))

    def _validate_change(self, raw: dict, request: dict) -> dict:
        if not isinstance(raw, dict) or raw.get("schema_version", 1) != 1:
            raise NarrativeValidationError("unsupported_narrative_response", "Unsupported narrative response")
        scope, now = request["scope"], request["now"]
        if request.get("background_only"):
            if set(raw) - {"schema_version", "no_change", "world_updates"}:
                raise ValueError("主角色熟睡时只能推演背景居民，不得改写其状态")
            if any(u.get('actor_id') == 'self' for u in raw.get('world_updates', []) if isinstance(u, dict)):
                raise ValueError("熟睡主角色不能参与新的互动")
        sources = {event["event_id"]: event for event in request["events"]}
        no_change = raw.get("no_change", False)
        if not isinstance(no_change, bool):
            raise NarrativeValidationError("no_change_must_be_boolean", "no_change must be boolean")
        impact = raw.get("event_impact", "none")
        if impact not in {"none", "activity", "commitment", "relationship"}:
            raise NarrativeValidationError("unsupported_impact", "Unsupported impact")
        state = raw.get("state", {})
        if not isinstance(state, dict) or set(state) - {"activity_code", "activity", "availability", "subjective_state", "summary", "valid_until"}:
            raise NarrativeValidationError("unsupported_state_changes", "Unsupported state changes")
        clean = {}
        if "activity_code" in state:
            if state["activity_code"] not in ACTIVITIES:
                raise NarrativeValidationError("unknown_activity_code", "Unknown activity code")
            clean["activity_code"] = state["activity_code"]
            # Scoped events can project only finite generic activity names, so
            # private participant names and conversation text cannot leak.
            clean["activity"] = ACTIVITIES[state["activity_code"]]
        if "activity" in state and not scope["umo"]:
            clean["activity"] = _text(state["activity"], 80, "activity")
        if "availability" in state:
            if state["availability"] not in AVAILABILITIES:
                raise NarrativeValidationError("unknown_availability", "Unknown availability")
            clean["availability"] = state["availability"]
        for key in ("subjective_state", "summary"):
            if key in state:
                clean[key] = _text(state[key], 300, key)
        valid_until = _timestamp(state.get("valid_until", now + 3600), "valid_until")
        if not now < valid_until <= now + 86400:
            raise NarrativeValidationError("state_horizon_must_be_within_the_next_day", "State horizon must be within the next day")
        clean["valid_until"] = valid_until
        next_check = _timestamp(raw.get("next_check", now + 3600), "next_check")
        if not now < next_check <= now + 86400:
            raise NarrativeValidationError("invalid_next_check_time", "Invalid next check time")
        diary = []
        for row in raw.get("diary", []):
            if not isinstance(row, dict):
                raise NarrativeValidationError("invalid_diary_entry", "Invalid diary entry")
            occurred = _timestamp(row.get("occurred_at", now), "diary.occurred_at")
            if occurred > now or occurred < request["snapshot"].get("narrated_until", request["snapshot"]["valid_from"]):
                raise NarrativeValidationError("diary_cannot_rewrite_the_past_or_prewrite_the_future", "Diary cannot rewrite the past or prewrite the future")
            fact_kind = row.get("fact_kind", "fiction" if not scope["umo"] else "subjective")
            if fact_kind not in FACT_KINDS:
                raise NarrativeValidationError("invalid_diary_fact_kind", "Invalid diary fact kind")
            source_ids = self._sources(row.get("source_ids"), sources)
            if scope["umo"] and fact_kind == "fiction":
                raise NarrativeValidationError("chat_participants_cannot_be_used_as_fictional_life_actors", "Chat participants cannot be used as fictional life actors")
            diary_text = _text(row.get("text", ""), 300)
            # An observed chat event proves its utterance, not the described
            # world. Verified diary categories accept only exact source quotes,
            # and the program itself supplies attribution and event type.
            if fact_kind in {"observation", "receipt"}:
                if any(sources[source]["fact_kind"] != fact_kind for source in source_ids):
                    raise NarrativeValidationError("a_diary_cannot_promote_the_evidence_category", "A diary cannot promote the evidence category")
                if len(source_ids) != 1 or diary_text != sources[source_ids[0]]["text"] or not diary_text:
                    raise NarrativeValidationError("observed_diary_text_must_be_an_exact_source_quotation", "Observed diary text must be an exact source quotation")
                event = sources[source_ids[0]]
                label = "发言记录" if fact_kind == "observation" else "执行回执"
                diary_text = f"{label}（{event['actor_id'] or event['type']}）：{diary_text}"
                if len(diary_text) > 300:
                    raise NarrativeValidationError("attributed_diary_entry_exceeds_its_length_limit", "Attributed diary entry exceeds its length limit")
            if not scope["umo"] and fact_kind != "fiction" and not all(sources[source]["type"] == "admin.correction" for source in source_ids):
                raise NarrativeValidationError("global_hourly_diaries_are_explicitly_fictional", "Global hourly diaries are explicitly fictional")
            diary.append({"occurred_at": occurred, "text": diary_text,
                          "fact_kind": fact_kind, "source_ids": source_ids})
        if len(diary) > 4:
            raise NarrativeValidationError("too_many_diary_entries", "Too many diary entries")
        commitments = [self._commitment(row, scope, sources, now) for row in raw.get("commitments", [])]
        intents = [self._intent(row, scope, sources, now) for row in raw.get("contact_intents", [])]
        for care in raw.get('care_waits', []):
            intents.append(self._care_wait(care, scope, sources, now))
        if len(commitments) > 10 or len(intents) > 4:
            raise NarrativeValidationError("too_many_planned_actions", "Too many planned actions")
        plan = []
        if "daily_plan" in raw:
            if scope["umo"] or not (request["needs_daily_plan"] or request.get("weather_reassessment")):
                raise NarrativeValidationError("daily_plans_may_be_created_once_per_day_by_global_life", "Daily plans may be created once per day by global life")
            for row in raw["daily_plan"]:
                if not isinstance(row, dict):
                    raise NarrativeValidationError("invalid_plan", "Invalid plan")
                start, end = _timestamp(row.get("start")), _timestamp(row.get("end"))
                day = dt.datetime.fromtimestamp(now, CHINA).date()
                day_end = dt.datetime.combine(day + dt.timedelta(days=1), dt.time(), CHINA).timestamp()
                if not now <= start < end <= day_end:
                    raise NarrativeValidationError("a_daily_plan_must_be_future_only_in_today_s_china_date", "A daily plan must be future-only in today's China date")
                plan.append({"start": start, "end": end, "activity": _text(row.get("activity", ""), 120), "fact_kind": "plan"})
            if len(plan) > 12:
                raise NarrativeValidationError("too_many_daily_plan_entries", "Too many daily plan entries")
            if request.get("weather_reassessment") and not request["needs_daily_plan"]:
                locked=[copy.deepcopy(p) for p in request.get("plan",[]) if p["start"]<now]
                if any(p["start"]<max((old["end"] for old in locked),default=now) for p in plan):
                    raise NarrativeValidationError("weather_plan_overlaps_started_activity", "Weather replanning cannot rewrite an already started schedule entry")
                plan=locked+plan
        if no_change and (diary or commitments or intents or any(key != "valid_until" for key in clean)):
            raise NarrativeValidationError("no_change_cannot_also_declare_effects", "no_change cannot also declare effects")
        humanlike = self._humanlike_change(raw.get("humanlike", {}), request, sources)
        if no_change and any(humanlike.values()):
            raise NarrativeValidationError("no_change_cannot_update_humanlike_state", "no_change cannot update humanlike state")
        movement = None
        world_action=None
        existing_action=(request['snapshot'].get('scene') or {}).get('action')
        if (request['snapshot'].get('scene') or {}).get('available') and not existing_action and 'world_action' not in raw and clean.get('activity_code')=='reading':
            raise NarrativeValidationError('reading_requires_scene_action','Tracked reading must start through world_action; ordinary chat cannot invent it')
        if existing_action and 'world_action' not in raw:
            current_kind=existing_action['steps'][existing_action['index']]['kind']
            current_code=existing_action.get('activity_code') or {'read':'reading','rest':'resting','travel':'walking'}.get(current_kind,'chores')
            if clean.get('availability')=='asleep' or 'activity_code' in clean and clean['activity_code']!=current_code:
                raise ValueError('程序行动仍在执行，请先等待或取消，不能直接改写成另一种已发生的活动')
        if "world_action" in raw:
            if self.scenes is None or no_change or "movement" in raw:raise ValueError('世界行动不能与 no_change 或独立移动同时提交')
            world_action=self.scenes.validate(raw['world_action'],request)
            if world_action['operation']=='start':
                # Execute the validated proposal, but never persist a model's
                # prewritten account of an action that has not happened yet.
                world_action['deferred_diary_count']=len(diary)
                diary=[]
        if "movement" in raw:
            if self.spatial is None or no_change:
                raise ValueError("移动需要地图且不能与 no_change 并用")
            movement = self.spatial.validate(raw["movement"], request)
        world_updates = self.causal.validate_updates(raw, request) if self.causal is not None else None
        agenda_changes = raw.get("agenda_changes")
        plan_id = raw.get("plan_id")
        if agenda_changes or plan_id:
            if self.causal is None or scope["umo"] or no_change:
                raise ValueError("日程调整仅允许全局生活推演")
            with self._db() as db:
                rev, document = self.causal.load(db, scope)
            if rev != request.get("causal_revision"):
                raise ValueError("日程已改变")
            if agenda_changes:
                self.causal.revise_agenda(document, agenda_changes, now)
            if agenda_changes and 'daily_plan' in raw:
                raise ValueError('不能同时替换整日日程和调整已有条目')
            if plan_id and (not isinstance(plan_id, str) or not (world_action or clean.get('activity_code') in {'sleeping','resting','chores','walking'}) or not any(p["id"] == plan_id and p['end'] > now and p['start'] <= now for p in document["agenda"])):
                raise ValueError("日程关联需要合法行动和已有日程")
        return {
            "served_residents": [a["id"] for a in (request.get("background_world") or {}).get("actors", []) if a["id"] != "self"],
            "background_only": request.get("background_only", False),
            "causal_revision": request.get("causal_revision"),
            "world_updates": world_updates,
            "agenda_changes": agenda_changes,
            "plan_id": plan_id,
            "no_change": no_change,
            "event_impact": impact,
            "state": clean,
            "diary": diary,
            "commitments": commitments,
            "contact_intents": intents,
            "next_check": next_check,
            "daily_plan": plan if "daily_plan" in raw else None,
            "humanlike": humanlike,
            "movement": movement,
            "world_action": world_action,
        }

    def _humanlike_change(self, raw: dict, request: dict, sources: dict) -> dict:
        """Validate sourced interests, plans, affect and member-bound nicknames.

        Args:
            raw: Optional incremental model output, never a full replacement.
            request: Authoritative scope, clock and preceding snapshot.
            sources: Current batch of attributed events.

        Returns:
            Validated incremental updates with program-owned timestamps.

        Raises:
            ValueError: An update lacks evidence, ownership or a bounded horizon.
        """
        limits = {"preferences": 8, "goals": 4, "moods": 8, "nicknames": 8, "corrections": 8, "interests": 4}
        if not isinstance(raw, dict) or set(raw) - set(limits):
            raise NarrativeValidationError("invalid_humanlike_fields", "Invalid humanlike fields")
        now, scope = request["now"], request["scope"]
        result = {}
        for kind, rows in raw.items():
            if not isinstance(rows, list) or len(rows) > limits[kind]:
                raise NarrativeValidationError("humanlike_batch_limit_exceeded", "Humanlike batch limit exceeded")
            if kind in {"corrections", "interests"}:
                result[kind] = self._behavior_change(kind, rows, request, sources)
                continue
            result[kind] = []
            seen = set()
            for row in rows:
                if not isinstance(row, dict):
                    raise NarrativeValidationError("invalid_humanlike_entry", "Invalid humanlike entry")
                source_ids = self._sources(row.get("source_ids"), sources)
                evidence = [sources[sid] for sid in source_ids]
                allowed_types = {
                    "message.received",
                    "chat.message",
                    "delivery.success",
                    "life.tick",
                    "tool.success",
                    "execution.success",
                }
                if any(
                    e["type"] not in allowed_types
                    or e.get("data", {}).get("message_origin") == "system_fallback"
                    for e in evidence
                ):
                    raise NarrativeValidationError("humanlike_changes_require_substantive_evidence", "Humanlike changes require substantive evidence")
                key = "subject_id" if kind in {"moods", "nicknames"} else "id"
                item_id = _text(row.get(key, ""), 100, key)
                if not item_id or item_id in seen or item_id in {"bot", "system"}:
                    raise NarrativeValidationError("invalid_or_duplicate_humanlike_identity", "Invalid or duplicate humanlike identity")
                seen.add(item_id)
                item = {key: item_id, "source_ids": source_ids, "updated_at": now}
                observed_at = min(now, max(e.get("occurred_at", now) for e in evidence))
                if kind in {"moods", "nicknames"}:
                    previous = next(
                        (
                            p
                            for p in request["snapshot"]
                            .get("humanlike", {})
                            .get(kind, [])
                            if p.get(key) == item_id
                        ),
                        {},
                    )
                    if previous.get("updated_at", 0) > observed_at:
                        continue
                    item["updated_at"] = observed_at
                if scope["umo"]:
                    item["participant_ids"] = sorted(
                        {
                            str(e.get("actor_id", ""))
                            for e in evidence
                            if e["type"] in {"message.received", "chat.message"}
                            and e.get("actor_id") not in {None, "", "bot", "system"}
                        }
                        | {
                            str(e["data"]["recipient_user_id"])
                            for e in evidence
                            if e["type"] == "delivery.success"
                            and e.get("data", {}).get("recipient_user_id")
                        }
                    )
                if kind in {"moods", "nicknames"}:
                    if not scope["umo"]:
                        raise NarrativeValidationError("member_state_cannot_enter_global_life", "Member state cannot enter global life")
                    own_messages = [
                        e
                        for e in evidence
                        if e["type"] in {"message.received", "chat.message"}
                        and e.get("actor_id") == item_id
                    ]
                    deliveries = [
                        e
                        for e in evidence
                        if e["type"] == "delivery.success"
                        and e.get("actor_id") == "bot"
                        and e.get("data", {}).get("recipient_user_id") == item_id
                    ]
                    if len(own_messages) + len(deliveries) != len(evidence):
                        raise NarrativeValidationError("member_state_requires_exactly_attributed_sources", "Member state requires exactly attributed sources")
                if kind == "nicknames":
                    status = row.get("status", "active")
                    if status not in {"active", "rejected"}:
                        raise NarrativeValidationError("invalid_nickname_status", "Invalid nickname status")
                    nickname = _text(row.get("nickname", ""), 24, "nickname")
                    quote = _text(row.get("evidence_quote", ""), 300, "nickname quote")
                    if not quote or not any(quote in e["text"] for e in evidence):
                        raise NarrativeValidationError("nickname_requires_an_exact_evidence_quote", "Nickname requires an exact evidence quote")
                    if status == "rejected" and not any(
                        quote in e["text"] for e in own_messages
                    ):
                        raise NarrativeValidationError("only_the_member_can_reject_their_nickname", "Only the member can reject their nickname")
                    if status == "active" and (
                        not nickname
                        or nickname not in quote
                        or any(c in nickname for c in "\n\r\t<>")
                    ):
                        raise NarrativeValidationError("nickname_must_occur_in_delivered_or_member_authored_evidence", "Nickname must occur in delivered or member-authored evidence")
                    if status == "active" and any(
                        re.fullmatch(
                            r"(?:别|不要|别再|不要再)叫我"
                            + re.escape(nickname)
                            + r"[。.!！,，~～]*",
                            e["text"].strip(),
                        )
                        for e in own_messages
                    ):
                        raise NarrativeValidationError("a_nickname_objection_cannot_activate_that_nickname", "A nickname objection cannot activate that nickname")
                    previous = next(
                        (
                            p
                            for p in request["snapshot"]
                            .get("humanlike", {})
                            .get(kind, [])
                            if p.get(key) == item_id
                        ),
                        {},
                    )
                    if (
                        previous.get("status") == "rejected"
                        and status == "active"
                        and not any(
                            quote in e["text"] and nickname in e["text"]
                            for e in own_messages
                        )
                    ):
                        raise NarrativeValidationError("a_rejected_nickname_needs_a_new_member_request", "A rejected nickname needs a new member request")
                    item.update(
                        nickname=nickname,
                        status=status,
                        evidence_quote=quote,
                        fact_kind="observation",
                    )
                else:
                    item["text"] = _text(row.get("text", ""), 120, kind)
                    if not item["text"]:
                        raise NarrativeValidationError("humanlike_text_cannot_be_empty", "Humanlike text cannot be empty")
                    item["fact_kind"] = "plan" if kind == "goals" else "subjective"
                    if kind == "preferences":
                        item["status"] = row.get("status", "active")
                        if item["status"] not in {"active", "removed"}:
                            raise NarrativeValidationError("invalid_preference_status", "Invalid preference status")
                    else:
                        horizon = 3600 if kind == "moods" else 7 * 86400
                        item["expires_at"] = _timestamp(
                            row.get(
                                "expires_at", now + (1800 if kind == "moods" else 86400)
                            )
                        )
                        if not now < item["expires_at"] <= now + horizon:
                            raise NarrativeValidationError("invalid_humanlike_horizon", "Invalid humanlike horizon")
                        if kind == "moods":
                            if row.get("status", "active") not in {"active", "settled"}:
                                raise NarrativeValidationError(
                                    "invalid_mood_status", "Invalid mood status"
                                )
                            item["status"] = row.get("status", "active")
                            item["topic"] = _text(
                                row.get("topic", ""), 80, "mood topic"
                            )
                            quote = _text(row.get("cause_quote", ""), 300, "mood cause")
                            if quote and not any(quote in e["text"] for e in evidence):
                                raise NarrativeValidationError(
                                    "mood_cause_not_in_evidence",
                                    "Mood cause must quote evidence",
                                )
                            item["cause_quote"] = quote
                            if previous.get("source_ids") == source_ids:
                                continue
                            item["expires_at"] = min(
                                item["expires_at"], observed_at + 3600
                            )
                            if item["expires_at"] <= now:
                                continue
                        if kind == "goals":
                            item["status"] = row.get("status", "planned")
                            if item["status"] not in {"planned", "done", "dropped"}:
                                raise NarrativeValidationError("invalid_goal_status", "Invalid goal status")
                            if (
                                scope["umo"]
                                and item["status"] == "done"
                                and not any(
                                    e["type"] in {"tool.success", "execution.success"}
                                    and e.get("data", {}).get("goal_id") == item_id
                                    for e in evidence
                                )
                            ):
                                raise NarrativeValidationError("a_scoped_goal_needs_its_own_execution_receipt", "A scoped goal needs its own execution receipt")
                result[kind].append(item)
        return result

    def _ingest_behavior_feedback(self, db, event: dict, now: float) -> None:
        """Persist unambiguous expression feedback before background inference.

        Args:
            db: Current event-ingestion transaction.
            event: Attributed, normalized incoming event.
            now: Program-owned current time.
        """
        scope = event['scope']
        if (
            not scope["umo"]
            or event["type"] not in {"message.received", "chat.message"}
            or event["actor_id"] in {"", "bot", "system"}
            or event.get("data", {}).get("directed_to_bot") is not True
        ):
            return
        spoken = event["text"].strip().rstrip("。.!！,，~～")
        # Whole-message matches exclude reported speech, quotations and negation.
        patterns = (
            (
                "length",
                r"(?:以后|下次)?(?:你)?(?:回复|回答|说话)(?:请)?(?:简短一点|简短点|短一点|短点)",
                "简短回应，保留必要信息",
            ),
            (
                "advice",
                r"(?:以后|下次)?(?:你)?(?:不要|别)(?:再)?(?:总是|老是)?(?:给我建议|给建议|教我怎么做)",
                "先听和回应感受，只有明确求助时再给建议",
            ),
            (
                "humor",
                r"(?:以后|下次)?(?:你)?(?:不要|别)(?:再)?(?:拿我开玩笑|对我阴阳怪气|嘲讽我)",
                "回应这个成员时收起针对其本人的玩笑和讥讽",
            ),
        )
        matched = next(
            (
                (category, text)
                for category, pattern, text in patterns
                if re.fullmatch(pattern, spoken)
            ),
            None,
        )
        if matched is None:
            return
        category, text = matched
        identity = _identity(scope)
        local = json.loads(
            db.execute(
                "SELECT state FROM scopes WHERE identity=? AND umo=?",
                (identity, scope["umo"]),
            ).fetchone()[0]
        )
        bucket = local.setdefault("humanlike", {}).setdefault("corrections", {})
        item_id = _json([event["actor_id"], category, ""])
        observed = min(now, event["occurred_at"])
        if bucket.get(item_id, {}).get("updated_at", 0) > observed:
            return
        if item_id not in bucket and len(bucket) >= 2048:
            return
        bucket[item_id] = {
            "id": item_id,
            "subject_id": event["actor_id"],
            "category": category,
            "topic": "",
            "text": text,
            "status": "active",
            "evidence_quote": spoken,
            "source_ids": [event["event_id"]],
            "participant_ids": [event["actor_id"]],
            "updated_at": observed,
            "fact_kind": "user_claim",
        }
        db.execute(
            "UPDATE scopes SET state=?,revision=revision+1 WHERE identity=? AND umo=?",
            (_json(local), identity, scope["umo"]),
        )
        db.execute("UPDATE lives SET revision=revision+1 WHERE identity=?", (identity,))

    def _behavior_change(
        self, kind: str, rows: list, request: dict, sources: dict
    ) -> list:
        """Validate durable feedback and incremental interests against current evidence.

        Args:
            kind: Corrections or interests bucket.
            rows: Bounded model-proposed incremental updates.
            request: Authoritative scope, clock and snapshot.
            sources: Current batch of canonical event envelopes.

        Returns:
            Validated updates with evidence timestamps and stable identities.

        Raises:
            NarrativeValidationError: Evidence, identity or progression is invalid.
        """
        result, seen = [], set()
        now, scope = request["now"], request["scope"]
        for row in rows:
            if not isinstance(row, dict):
                raise NarrativeValidationError(
                    "invalid_behavior_entry", "Invalid behavior entry"
                )
            source_ids = self._sources(row.get("source_ids"), sources)
            evidence = [sources[sid] for sid in source_ids]
            if not evidence or any(
                e.get("data", {}).get("message_origin") == "system_fallback"
                for e in evidence
            ):
                raise NarrativeValidationError(
                    "behavior_requires_evidence",
                    "Behavior requires substantive evidence",
                )
            observed = min(now, max(e.get("occurred_at", now) for e in evidence))
            text = _text(row.get("text", ""), 160, "behavior text")
            topic = _text(row.get("topic", ""), 80, "behavior topic")
            quote = _text(row.get("evidence_quote", ""), 300, "behavior quote")
            if not text or not topic and kind == "interests":
                raise NarrativeValidationError(
                    "behavior_text_required", "Behavior text or topic missing"
                )
            if kind == "corrections":
                subject = _text(row.get("subject_id", ""), 100, "subject_id")
                category = row.get("category")
                status = row.get("status", "active")
                if (
                    not scope["umo"]
                    or subject in {"", "bot", "system"}
                    or category
                    not in {"interpretation", "length", "advice", "humor", "addressing"}
                    or status not in {"active", "retracted"}
                    or category == "interpretation"
                    and not topic
                ):
                    raise NarrativeValidationError(
                        "invalid_correction_identity", "Invalid correction identity"
                    )
                own = [
                    e
                    for e in evidence
                    if e["type"] in {"message.received", "chat.message"}
                    and e.get("actor_id") == subject
                    and e.get("data", {}).get("directed_to_bot") is True
                ]
                if (
                    len(own) != len(evidence)
                    or not quote
                    or not any(quote in e["text"] for e in own)
                ):
                    raise NarrativeValidationError(
                        "correction_requires_direct_member_quote",
                        "Correction requires a direct member quote",
                    )
                if any(
                    re.search(
                        r"[“\"‘「『][^”\"’」』]*"
                        + re.escape(quote)
                        + r"[^”\"’」』]*[”\"’」』]",
                        e["text"],
                    )
                    for e in own
                ):
                    raise NarrativeValidationError(
                        "quoted_feedback_is_not_a_request",
                        "Quoted feedback is not a member request",
                    )
                if status == "retracted" and not re.search(
                    r"撤销|收回|取消|不用.{0,8}(?:遵守|记住)|可以.{0,8}(?:建议|玩笑|叫|详细)",
                    quote,
                ):
                    raise NarrativeValidationError(
                        "correction_retraction_requires_request",
                        "Retraction requires an explicit member request",
                    )
                if status == "active" and not re.search(
                    r"不是|是指|说的是|意思是|理解错|误会|别|不要|以后|下次|改成|简短|详细|只想|只要|不用",
                    quote,
                ):
                    raise NarrativeValidationError(
                        "correction_requires_feedback",
                        "Correction requires explicit feedback",
                    )
                item_id = _json([subject, category, topic])
                item = {
                    "id": item_id,
                    "subject_id": subject,
                    "category": category,
                    "topic": topic,
                    "text": text,
                    "status": status,
                    "participant_ids": [subject],
                    "fact_kind": "user_claim",
                }
            else:
                item_id = _text(row.get("id", ""), 100, "interest id")
                status = row.get("status", "active")
                progress_kind = row.get(
                    "progress_kind", "discussion" if scope["umo"] else "fiction"
                )
                if not item_id or status not in {"active", "paused", "done"}:
                    raise NarrativeValidationError(
                        "invalid_interest_identity", "Invalid interest identity"
                    )
                if scope["umo"]:
                    valid = [
                        e
                        for e in evidence
                        if (
                            progress_kind == "discussion"
                            and (
                                e["type"] in {"message.received", "chat.message"}
                                and e.get("actor_id") not in {"", "bot", "system"}
                                and e.get("data", {}).get("directed_to_bot") is True
                                or e["type"] == "delivery.success"
                                and e.get("actor_id") == "bot"
                                and e.get("data", {}).get("recipient_user_id")
                            )
                            or progress_kind == "execution"
                            and e["type"] in {"tool.success", "execution.success"}
                            and e.get("data", {}).get("interest_id") == item_id
                        )
                    ]
                    if (
                        len(valid) != len(evidence)
                        or not quote
                        or not any(quote in e["text"] for e in evidence)
                    ):
                        raise NarrativeValidationError(
                            "interest_progress_requires_evidence",
                            "Interest progress lacks attributed evidence",
                        )
                    participants = sorted(
                        {
                            str(
                                e.get("data", {}).get("recipient_user_id")
                                or e.get("actor_id")
                            )
                            for e in evidence
                        }
                        - {"", "bot", "system", "None"}
                    )
                    if not participants:
                        raise NarrativeValidationError(
                            "interest_requires_participants",
                            "Interest requires participants",
                        )
                else:
                    if progress_kind != "fiction" or any(
                        e["type"] != "life.tick" for e in evidence
                    ):
                        raise NarrativeValidationError(
                            "global_interest_requires_life_tick",
                            "Global interest requires fictional life evidence",
                        )
                    participants = []
                item = {
                    "id": item_id,
                    "topic": topic,
                    "text": text,
                    "status": status,
                    "progress_kind": progress_kind,
                    "next_step": _text(row.get("next_step", ""), 120, "next step"),
                    "participant_ids": participants,
                    "fact_kind": "fiction"
                    if not scope["umo"]
                    else "receipt"
                    if progress_kind == "execution"
                    else "subjective",
                }
            if item_id in seen:
                raise NarrativeValidationError(
                    "duplicate_behavior_identity", "Duplicate behavior identity"
                )
            seen.add(item_id)
            previous = next(
                (
                    p
                    for p in request["snapshot"].get("humanlike", {}).get(kind, [])
                    if p.get("id") == item_id
                    and p.get("origin", "conversation")
                    == ("conversation" if scope["umo"] else "personal")
                ),
                {},
            )
            if kind == "corrections" and item["status"] == "retracted" and not previous:
                raise NarrativeValidationError(
                    "correction_to_retract_missing", "No matching correction to retract"
                )
            if previous.get("updated_at", 0) > observed or set(source_ids) <= set(
                previous.get("source_ids", [])
            ):
                continue
            if kind == "interests":
                if previous and set(previous.get("participant_ids", [])) != set(
                    item["participant_ids"]
                ):
                    raise NarrativeValidationError(
                        "interest_owner_changed", "Interest ownership cannot change"
                    )
                history = list(previous.get("history", []))[-3:]
                history.append(
                    {
                        "text": text,
                        "occurred_at": observed,
                        "source_ids": source_ids,
                        "progress_kind": item["progress_kind"],
                    }
                )
                item["history"] = history
            item.update(
                source_ids=source_ids, evidence_quote=quote, updated_at=observed
            )
            result.append(item)
        return result

    def _commitment(self, raw: dict, scope: dict, sources: dict, now: float) -> dict:
        if not scope["umo"] or not isinstance(raw, dict):
            raise NarrativeValidationError("commitments_require_a_concrete_conversation", "Commitments require a concrete conversation")
        status = raw.get("status", "proposed")
        if status not in COMMITMENT_STATUSES:
            raise NarrativeValidationError("invalid_commitment_status", "Invalid commitment status")
        source_ids = self._sources(raw.get("source_ids"), sources)
        kinds = {sources[source]["type"] for source in source_ids}
        if status == "committed" and "delivery.success" not in kinds:
            raise NarrativeValidationError("an_unsent_reply_cannot_create_a_committed_promise", "An unsent reply cannot create a committed promise")
        if status == "completed":
            item_id = raw.get("commitment_id")
            matching = [sources[source] for source in source_ids if sources[source]["type"] in {"tool.success", "execution.success"}
                        and sources[source]["data"].get("effect_confirmed") is True
                        and (sources[source]["data"].get("commitment_id") == item_id
                             or item_id in sources[source]["data"].get("completed_commitment_ids", []))]
            if not item_id or not matching:
                raise NarrativeValidationError("completed_work_requires_a_matching_confirmed_execution_result", "Completed work requires a matching confirmed execution result")
        if status == "committed":
            quote = raw.get("evidence_quote", "")
            if not isinstance(quote, str) or not quote or not any(
                sources[source]["type"] == "delivery.success" and quote in sources[source]["text"] for source in source_ids):
                raise NarrativeValidationError("committed_promise_must_quote_its_actual_delivered_evidence", "Committed promise must quote its actual delivered evidence")
        item_id = _text(raw.get("commitment_id") or str(uuid.uuid4()), 300, "commitment_id")
        result = {"schema_version": 1, "commitment_id": item_id, "scope": scope,
            "description": _text(raw.get("description", ""), 300, "description"), "status": status,
            "source_ids": source_ids, "created_at": now, "fact_kind": "plan",
            "participant_ids": sorted({sources[s]['actor_id'] for s in source_ids
                if sources[s].get('type') in {'message.received','chat.message'} and sources[s].get('actor_id') not in {'','bot','system',None}}
                | {sources[s]['data']['recipient_user_id'] for s in source_ids
                   if sources[s].get('type') == 'delivery.success' and sources[s].get('data',{}).get('recipient_user_id')})}
        for key in ("reminder_id", "evidence_quote"):
            if raw.get(key):
                result[key] = _text(raw[key], 300, key)
        if result.get("reminder_id"):
            rid = result["reminder_id"]
            with self._db() as db:
                verified = any(json.loads(r[0]).get('data', {}).get('reminder_id') == rid and
                               json.loads(r[0]).get('data', {}).get('effect_kind') == 'reminder.created' and
                               json.loads(r[0]).get('data', {}).get('effect_confirmed') is True
                               for r in db.execute("SELECT payload FROM events WHERE identity=? AND umo=? AND json_extract(payload,'$.type')='execution.success'",
                                                   (_identity(scope), scope['umo'])))
            if not verified:
                raise NarrativeValidationError("reminder_binding_requires_an_owned_creation_receipt", "Reminder binding requires an owned creation receipt")
        if raw.get("due_at") is not None:
            result["due_at"] = _timestamp(raw["due_at"], "due_at")
        return result

    def _intent(self, raw: dict, scope: dict, sources: dict, now: float) -> dict:
        if not isinstance(raw, dict) or not self.is_managed(scope):
            raise NarrativeValidationError("contact_intents_require_an_enabled_explicit_conversation", "Contact intents require an enabled explicit conversation")
        if raw.get("target_umo", scope["umo"]) != scope["umo"]:
            raise NarrativeValidationError("an_intent_cannot_target_another_conversation", "An intent cannot target another conversation")
        source_ids = self._sources(raw.get("source_ids"), sources)
        if all(sources[source]["type"] in {"life.tick", "delivery.failure", "delivery.uncertain"}
               or (sources[source]["type"] == "delivery.success" and sources[source]["data"].get("intent_id"))
               for source in source_ids):
            raise NarrativeValidationError("time_or_failed_delivery_alone_is_not_a_contact_reason", "Time or failed delivery alone is not a contact reason")
        not_before = _timestamp(raw.get("not_before", now), "not_before")
        expires = _timestamp(raw.get("expires_at", now + 86400), "expires_at")
        if not now <= not_before < expires <= now + 7 * 86400:
            raise NarrativeValidationError("invalid_contact_intent_window", "Invalid contact intent window")
        if raw.get("message") or raw.get("text"):
            raise NarrativeValidationError("contact_intents_must_not_contain_prewritten_messages", "Contact intents must not contain prewritten messages")
        result = {"schema_version": 1, "intent_id": _text(raw.get("intent_id") or str(uuid.uuid4()), 300),
            "scope": copy.deepcopy(scope), "target_umo": scope["umo"],
            "reason": _text(raw.get("reason", ""), 300, "reason"), "source_ids": source_ids,
            "not_before": not_before, "expires_at": expires, "status": "pending", "created_at": now}
        if not result["reason"]:
            raise NarrativeValidationError("intent_reason_is_required", "Intent reason is required")
        for key in ("commitment_id", "reminder_id"):
            if raw.get(key):
                result[key] = _text(raw[key], 300, key)
        return result

    def _store_commitment(self, db, scope: dict, item: dict) -> None:
        old = db.execute("SELECT * FROM commitments WHERE commitment_id=?", (item["commitment_id"],)).fetchone()
        if old and (old["identity"] != _identity(scope) or old["umo"] != scope["umo"]):
            raise NarrativeValidationError("a_commitment_cannot_change_ownership", "A commitment cannot change ownership")
        if old:
            existing = json.loads(old["payload"])
            if existing["status"] in {"completed", "cancelled", "expired"} and item["status"] != existing["status"]:
                raise NarrativeValidationError("a_terminal_commitment_cannot_be_reopened", "A terminal commitment cannot be reopened")
            if existing["status"] == "committed" and item["status"] in {"proposed", "conditional"}:
                raise NarrativeValidationError("a_confirmed_promise_cannot_be_downgraded_to_an_unsent_proposal", "A confirmed promise cannot be downgraded to an unsent proposal")
            item["created_at"] = existing["created_at"]
            item["source_ids"] = list(dict.fromkeys(existing["source_ids"] + item["source_ids"]))
        db.execute("INSERT INTO commitments VALUES(?,?,?,?,?) ON CONFLICT(commitment_id) DO UPDATE SET payload=excluded.payload,status=excluded.status",
            (item["commitment_id"], _identity(scope), scope["umo"], _json(item), item["status"]))
        if item["status"] in {"completed", "cancelled", "expired"}:
            for row in db.execute("SELECT intent_id,payload,status FROM intents WHERE identity=? AND umo=?",
                                  (_identity(scope), scope["umo"])):
                intent = json.loads(row["payload"])
                if intent.get("commitment_id") == item["commitment_id"] and row["status"] not in TERMINAL_INTENTS:
                    db.execute("UPDATE intents SET status='cancelled' WHERE intent_id=?", (row["intent_id"],))
