"""Request-specific output contract; semantic evidence checks remain authoritative."""

from __future__ import annotations


def narrative_schema(request: dict) -> dict:
    """Constrain JSON shape, source IDs, finite labels and program-owned time windows."""
    if request.get('resident_isolated'):
        from ...resident_runtime import decision_schema
        return decision_schema(request)
    now = request["now"]
    scoped = bool(request["scope"]["umo"])

    def text(maximum):
        return {"type": "string", "maxLength": maximum}

    def choice(values):
        return {"type": "string", "enum": values}

    def stamp(end=86400, start=None):
        return {"type": "number", "minimum": now + 0.001 if start is None else start,
                "maximum": now + end}

    def obj(properties, required=()):
        return {"type": "object", "properties": properties, "required": list(required),
                "additionalProperties": False}

    def rows(properties, required, maximum):
        return {"type": "array", "items": obj(properties, required), "maxItems": maximum}

    event_ids = [e["event_id"] for e in request["events"]]
    # Repeating long source-ID enums at every effect produces a provider-side
    # schema-complexity rejection for ordinary multi-event batches. Membership
    # is enforced by NarrativeEngine._sources against the complete request.
    sources = {"type": "array", "items": text(300),
               "minItems": 1 if event_ids else 0, "maxItems": 50 if event_ids else 0}
    basic = {"source_ids": sources}
    member = {**basic, "subject_id": text(100)}
    if request.get('outreach_only'):
        props = {'no_change': {'type':'boolean'}}
        common = {**member, 'reason':text(300), 'evidence_quote':text(600),
                  'not_before':stamp(86400,now+1800), 'expires_at':stamp(86400)}
        required = ('subject_id','reason','evidence_quote','source_ids','not_before','expires_at')
        if request.get('care_policy',{}).get('enabled'):
            props['care_waits'] = rows({**common, 'reason_kind':choice(['health_concern','travel_checkin','agreed_checkin']),
                'waiting_for':text(300)}, (*required,'reason_kind','waiting_for'), 2)
        if request.get('social_policy',{}).get('enabled'):
            social_common = {
                **common,
                # Shared-topic openers still need their historical >=30m
                # quiet break and may expire within 24h; the grounded branch
                # has tighter limits enforced by _social_chat.
                'not_before': stamp(86400, now + 60),
                'expires_at': stamp(86400),
            }
            props['chat_openers'] = rows({
                **social_common,
                'topic': text(120),
                'topic_candidate_id': text(100),
            }, (*required,'topic'), 2)
        return obj(props, ('no_change',))
    humanlike = {
        "preferences": rows({**basic, "id": text(100), "text": text(120),
                             "status": choice(["active", "removed"])},
                            ("id", "text", "source_ids"), 8),
        "goals": rows({**basic, "id": text(100), "text": text(120),
                       "status": choice(["planned", "done", "dropped"]), "expires_at": stamp(7 * 86400)},
                      ("id", "text", "source_ids"), 4),
    }
    humanlike["interests"] = rows(
        {
            **basic,
            "id": text(100),
            "topic": text(80),
            "text": text(160),
            "status": choice(["active", "paused", "done"]),
            "next_step": text(120),
            "progress_kind": choice(
                ["discussion", "execution"] if scoped else ["fiction"]
            ),
            "evidence_quote": text(300),
        },
        ("id", "topic", "text", "source_ids", "progress_kind", "evidence_quote"),
        4,
    )
    if scoped:
        humanlike.update(
            {
                "corrections": rows(
                    {
                        **member,
                        "category": choice(
                            [
                                "interpretation",
                                "length",
                                "advice",
                                "humor",
                                "addressing",
                            ]
                        ),
                        "topic": text(80),
                        "text": text(160),
                        "evidence_quote": text(300),
                        "status": choice(["active", "retracted"]),
                    },
                    (
                        "subject_id",
                        "category",
                        "topic",
                        "text",
                        "evidence_quote",
                        "source_ids",
                    ),
                    8,
                ),
                "moods": rows(
                    {
                        **member,
                        "text": text(120),
                        "expires_at": stamp(3600),
                        "topic": text(80),
                        "cause_quote": text(300),
                        "status": choice(["active", "settled"]),
                    },
                    ("subject_id", "text", "source_ids"),
                    8,
                ),
                "nicknames": rows(
                    {
                        **member,
                        "nickname": text(24),
                        "status": choice(["active", "rejected"]),
                        "evidence_quote": text(300),
                    },
                    (
                        "subject_id",
                        "nickname",
                        "status",
                        "source_ids",
                        "evidence_quote",
                    ),
                    8,
                ),
            }
        )
    properties = {
        "schema_version": {"type": "integer", "enum": [1]},
        "no_change": {"type": "boolean"},
        "event_impact": choice(["none", "activity", "commitment", "relationship"]),
        "state": obj({"activity_code": choice(["writing", "gaming", "resting", "sleeping", "eating",
                                                  "reading", "walking", "chores", "unknown"]),
                      "availability": choice(["available", "busy", "asleep", "unknown"]),
                      "subjective_state": text(300), "summary": text(300), "valid_until": stamp()}),
        "diary": rows({**basic, "text": text(300),
                       "occurred_at": {"type": "number", "minimum": request.get("snapshot", {}).get("narrated_until", 0),
                                       "maximum": now},
                       "fact_kind": choice(["subjective", "user_claim", "observation", "receipt"] if scoped else ["fiction"])},
                      ("text", "source_ids", "fact_kind"), 4),
        "commitments": rows({**basic, "commitment_id": text(300), "description": text(300),
                             "status": choice(["proposed", "committed", "conditional", "completed", "cancelled", "expired"]),
                             "evidence_quote": text(300), "due_at": {"type": "number", "minimum": 0}, "reminder_id": text(300)},
                            ("commitment_id", "description", "status", "source_ids"), 10),
        "contact_intents": rows({**basic, "intent_id": text(300), "reason": text(300),
                                 "not_before": stamp(7 * 86400), "expires_at": stamp(7 * 86400),
                                 "commitment_id": text(300), "reminder_id": text(300)},
                                ("reason", "source_ids", "not_before", "expires_at"), 4),
        "humanlike": obj(humanlike),
        "next_check": stamp(),
    }
    if not scoped:
        properties["state"]["properties"]["activity"] = text(80)
        scene=request.get('snapshot',{}).get('scene') or {}
        if scene.get('available'):
            kinds=['enter','leave','take','put','read','drink','refill','open_umbrella','fold_umbrella','rest','dry','travel','write_note','read_notes','power_on','power_off','computer_work']
            targets=[r['id'] for r in scene.get('rooms',[])]+[i['id'] for i in scene.get('items',[])]+[p['id'] for p in (request.get('snapshot',{}).get('spatial') or {}).get('places',[])]
            from ...room_design import KINDS,POSITIONS,LIGHTS,CURTAINS
            kinds+=sorted(KINDS)
            from ...creative_projects import KINDS as PROJECT_KINDS
            kinds+=sorted(PROJECT_KINDS)
            from ...garden_ecology import ECOLOGY_KINDS
            kinds += sorted(ECOLOGY_KINDS) + ['open_mailbox']
            targets += [f['id'] for d in scene.get('room_designs',[]) for f in d['furniture']]
            targets += [p['id'] for p in scene.get('projects',[])]
            properties['world_action']=obj({'operation':choice(['start','cancel','interrupt','resume']),
                'steps':rows({'kind':choice(kinds),'target_id':choice(targets),'title':text(60),'text':text(1000),
                              'mode':choice(['writing','organize','gaming']+list(LIGHTS)+list(CURTAINS)),
                              'position':choice(list(POSITIONS)), 'record_id':text(160),'project_id':text(100),
                              'parts':{'type':'integer','minimum':1,'maximum':8},'section':{'type':'integer','minimum':1,'maximum':8}},('kind',),6)},('operation',))
        spatial = request.get("snapshot", {}).get("spatial") or {}
        if spatial.get("available"):
            properties["movement"] = obj({"kind": choice(["locate", "plan", "depart"]),
                "target_id": choice([p["id"] for p in spatial.get("places", [])]),
                "not_before": stamp(86400, now)}, ("kind", "target_id"))
    if request.get("care_policy", {}).get("enabled") and scoped:
        properties["care_waits"] = rows({**member, "reason_kind": choice(["health_concern", "travel_checkin", "agreed_checkin"]),
                                         "reason": text(300), "waiting_for": text(300), "evidence_quote": text(300),
                                         "not_before": stamp(7 * 86400, now + 1800), "expires_at": stamp(7 * 86400)},
                                        ("subject_id", "reason_kind", "reason", "waiting_for", "evidence_quote",
                                         "source_ids", "not_before", "expires_at"), 4)
    if not scoped and (request.get("needs_daily_plan") or request.get("weather_reassessment")):
        properties["daily_plan"] = rows({"start": {"type": "number", "minimum": now, "maximum": request["day_end"]},
                                        "end": {"type": "number", "minimum": now, "maximum": request["day_end"]},
                                        "activity": text(120)}, ("start", "end", "activity"), 12)
    if not scoped and request.get("causal_revision") is not None:
        properties["plan_id"] = text(80)
        properties["agenda_changes"] = rows({"id": text(80), "status": choice(["deferred", "cancelled"]),
            "start": stamp(7*86400, now), "end": stamp(7*86400, now), "reason": text(200)}, ("id", "status", "reason"), 12)
    if not scoped and request.get("background_world"):
        actor_ids = [a["id"] for a in request["background_world"]["actors"]]
        properties["world_updates"] = rows({"actor_id": choice(actor_ids),
            "operation": choice(["rest", "observe", "travel", "invite", "respond", "speak"]),
            "target_id": text(160), "invitation_id": text(80), "response": choice(["accepted", "declined", "reschedule"]),
            "when": stamp(7*86400, now), "text": text(240),
            "source_ids": {"type": "array", "items": text(160), "minItems": 1, "maxItems": 8}},
            ("actor_id", "operation", "source_ids"), 8)
    if request.get("background_only"):
        properties = {k: v for k, v in properties.items() if k in {"no_change", "world_updates"}}
    return obj(properties, ("no_change",))
