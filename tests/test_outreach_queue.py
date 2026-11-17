"""Fresh outreach must not wait for or rewrite historical life evidence."""

import copy
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "outreach_engine_tests", Path(__file__).parents[1] / "life/core/narrative.py"
)
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class OutreachTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = 1800000000.0
        self.scope = M.normalize_scope(
            {"umo": "qq:GroupMessage:one", "platform": "qq", "persona_id": "p"}
        )
        self.config = {
            "mode": "narrative",
            "persona_id": "p",
            "narrative_sessions": [self.scope["umo"]],
            "contextual_care_sessions": [self.scope["umo"]],
            "social_chat_sessions": [self.scope["umo"]],
        }
        self.requests = []
        self.response = {"no_change": True}

        async def model(request):
            self.requests.append(request)
            return copy.deepcopy(self.response)

        self.engine = M.NarrativeEngine(
            Path(self.temp.name) / "life.sqlite3", self.config, model, lambda: self.now
        )

    async def asyncTearDown(self):
        await self.engine.close()
        self.temp.cleanup()

    def event(
        self,
        eid,
        text="我想继续讨论三体里关于文明的设定",
        uid="u1",
        age=2000,
        kind="message.received",
        data=None,
    ):
        return {
            "event_id": eid,
            "scope": self.scope,
            "actor_id": uid,
            "text": text,
            "type": kind,
            "occurred_at": self.now - age,
            "received_at": self.now - age,
            "source_ids": [eid],
            "fact_kind": "user_claim" if kind == "message.received" else "receipt",
            "data": data if data is not None else {"directed_to_bot": True},
        }

    def candidate(self, e, care=False):
        item = {
            "subject_id": e["actor_id"],
            "reason": "此前聊过这个话题，可以补充一个新角度",
            "evidence_quote": e["text"],
            "source_ids": [e["event_id"]],
            "not_before": self.now + 1800,
            "expires_at": self.now + 7200,
        }
        item.update(
            {"reason_kind": "health_concern", "waiting_for": "是否缓解"}
            if care
            else {"topic": "三体"}
        )
        return item

    def rows(self, sql, args=()):
        with closing(sqlite3.connect(self.engine.path)) as db:
            return db.execute(sql, args).fetchall()

    async def social_evidence(self):
        e = self.event("new")
        await self.engine.ingest_events(
            [
                self.event("earlier", age=6000),
                self.event(
                    "reply",
                    "三体这个设定确实值得讨论",
                    uid="bot",
                    age=5000,
                    kind="delivery.success",
                    data={"recipient_user_id": "u1"},
                ),
                e,
            ]
        )
        return e

    async def test_old_chatter_archived_without_deleting_or_marking_understood(self):
        old = self.event("old", text="今天有点困", age=90000)
        protected = self.event("promise", text="我们约定明天再聊", age=90000)
        await self.engine.ingest_events([old, protected])
        before = self.rows("select payload from events where event_id=?", ("old",))[0][
            0
        ]
        with self.engine._db() as db:
            self.engine._compact_old_queue(db, M._identity(self.scope))
        self.assertEqual(
            self.rows("select status,payload from events where event_id=?", ("old",)),
            [("historical_only", before)],
        )
        self.assertEqual(
            self.rows("select status from events where event_id=?", ("promise",)),
            [("pending",)],
        )

    async def test_compaction_rotates_past_protected_head(self):
        await self.engine.ingest_events(
            [
                self.event("p1", "以后请简短一点", age=90000),
                self.event("p2", "不要这样叫我", age=90000),
                self.event("old", "随便聊聊", age=90000),
            ]
        )
        with self.engine._db() as db:
            self.engine._compact_old_queue(db, M._identity(self.scope), limit=2)
            self.engine._compact_old_queue(db, M._identity(self.scope), limit=2)
        self.assertEqual(
            self.rows("select status from events where event_id='old'"),
            [("historical_only",)],
        )

    async def test_busy_conversation_cannot_exhaust_another_conversation_budget(self):
        with self.engine._db() as db:
            for _ in range(6):
                self.assertTrue(
                    self.engine._reserve(
                        db,
                        M._identity(self.scope),
                        "extra",
                        self.now,
                        umo=self.scope["umo"],
                    )
                )
            self.assertFalse(
                self.engine._reserve(
                    db,
                    M._identity(self.scope),
                    "extra",
                    self.now,
                    umo=self.scope["umo"],
                )
            )
            self.assertTrue(
                self.engine._reserve(
                    db,
                    M._identity(self.scope),
                    "extra",
                    self.now,
                    umo="qq:GroupMessage:two",
                )
            )

    async def test_fresh_care_bypasses_fifo_budget_and_preserves_pending(self):
        e = self.event("health", "我现在有点头疼，先去休息一下")
        await self.engine.ingest_events(
            [self.event("old", "约定还需要核对", age=100000), e]
        )
        with self.engine._db() as db:
            for _ in range(6):
                self.engine._reserve(db, M._identity(self.scope), "extra", self.now)
        self.response = {
            "no_change": False,
            "care_waits": [self.candidate(e, care=True)],
        }
        result = await self.engine.review_outreach()
        self.assertEqual(result, [{"status": "ok", "candidates": 1}])
        self.assertNotIn("old", [x["event_id"] for x in self.requests[0]["events"]])
        self.assertEqual(
            self.rows("select status from events where event_id='old'"), [("pending",)]
        )
        self.now += 400
        await self.engine.review_outreach()
        self.assertEqual(len(self.requests), 1)

    async def test_reciprocal_topic_creates_targeted_candidate_and_new_input_cancels(
        self,
    ):
        e = await self.social_evidence()
        self.response = {"no_change": False, "chat_openers": [self.candidate(e)]}
        self.assertEqual((await self.engine.review_outreach())[0]["candidates"], 1)
        item = json.loads(self.rows("select payload from intents")[0][0])
        self.assertEqual(item["recipient_user_id"], "u1")
        self.assertEqual(item["kind"], "social_chat")
        await self.engine.ingest_events([self.event("other", uid="u2", age=0)])
        self.assertEqual(
            (await self.engine.get_intent(item["intent_id"]))["item"]["status"],
            "pending",
        )
        notifications = []

        def after_commit():
            notifications.extend(self.rows("SELECT status FROM intents"))

        self.engine.on_db_write = after_commit
        self.engine.observe_member_activity(self.scope["umo"], "u1", "return", self.now)
        self.assertEqual(notifications, [("cancelled",)])
        self.assertEqual(
            (await self.engine.get_intent(item["intent_id"]))["item"]["status"],
            "cancelled",
        )

    async def test_presence_only_and_duplicate_do_not_publish(self):
        notifications = []
        self.engine.on_db_write = lambda: notifications.append("write")
        umo = self.scope["umo"]
        self.assertTrue(self.engine.observe_member_activity(umo, "u1", "first", self.now)["accepted"])
        first_revision = self.engine.peek_context_revision(self.scope)
        self.assertTrue(self.engine.observe_member_activity(umo, "u1", "first", self.now)["accepted"])
        self.assertEqual(self.engine.peek_context_revision(self.scope), first_revision)
        self.assertTrue(self.engine.observe_member_activity(umo, "u1", "second", self.now + 1)["accepted"])
        self.assertFalse(notifications)
        watermarks = self.rows("SELECT value FROM metadata WHERE key LIKE 'care_presence:%'")
        self.assertEqual(json.loads(watermarks[0][0])["message_id"], "second")

    async def test_presence_cancel_and_watermark_roll_back_together_without_publishing(self):
        event = await self.social_evidence()
        self.response = {"no_change": False, "chat_openers": [self.candidate(event)]}
        self.assertEqual((await self.engine.review_outreach())[0]["candidates"], 1)
        with self.engine._db() as db:
            db.execute(
                "CREATE TRIGGER reject_cancel BEFORE UPDATE ON intents "
                "WHEN NEW.status='cancelled' BEGIN SELECT RAISE(ABORT,'test rollback'); END"
            )
        notifications = []
        self.engine.on_db_write = lambda: notifications.append("write")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "test rollback"):
            self.engine.observe_member_activity(self.scope["umo"], "u1", "return", self.now)
        self.assertEqual(self.rows("SELECT status FROM intents"), [("pending",)])
        self.assertEqual(self.rows("SELECT value FROM metadata WHERE key LIKE 'care_presence:%'"), [])
        self.assertFalse(notifications)

    async def test_no_reciprocity_or_cross_member_evidence_rejected(self):
        e = self.event("solo")
        await self.engine.ingest_events([e, self.event("others", uid="u2")])
        self.response = {"no_change": False, "chat_openers": [self.candidate(e)]}
        self.assertEqual((await self.engine.review_outreach())[0]["status"], "invalid")
        self.assertEqual(self.rows("select count(*) from intents"), [(0,)])
        spoof = self.candidate(e)
        spoof["subject_id"] = "u2"
        with self.assertRaises(ValueError):
            self.engine._social_chat(
                spoof, self.scope, {"solo": self.engine._event(e, self.now)}, self.now
            )

    async def test_disable_revokes_existing_candidate(self):
        e = await self.social_evidence()
        self.response = {"no_change": False, "chat_openers": [self.candidate(e)]}
        await self.engine.review_outreach()
        item = json.loads(self.rows("select payload from intents")[0][0])
        self.config["social_chat_enabled"] = False
        self.assertEqual(
            (await self.engine.get_intent(item["intent_id"]))["item"]["status"],
            "cancelled",
        )

    async def test_same_member_daily_dedup_and_paused_scope_no_call(self):
        e = await self.social_evidence()
        self.response = {"no_change": False, "chat_openers": [self.candidate(e)]}
        await self.engine.review_outreach()
        iid = self.rows("select intent_id from intents")[0][0]
        self.now += 1801
        await self.engine.update_intent(iid, "claimed")
        await self.engine.update_intent(iid, "sent")
        newer = self.event("newer", age=1800)
        await self.engine.ingest_events([newer])
        self.response = {"no_change": False, "chat_openers": [self.candidate(newer)]}
        self.assertEqual((await self.engine.review_outreach())[0]["candidates"], 0)
        await self.engine.set_outreach_paused(True, self.scope)
        self.now += 1000
        count = len(self.requests)
        self.assertEqual(await self.engine.review_outreach(), [])
        self.assertEqual(len(self.requests), count)

    async def test_old_care_quote_cannot_start_wait(self):
        e = self.event("old", "我头疼先休息一下", age=90000)
        await self.engine.ingest_events([e])
        self.assertEqual(await self.engine.review_outreach(), [])
        self.assertFalse(self.requests)

    async def test_failure_backoff_and_restart_dedup(self):
        e = await self.social_evidence()
        self.response = {"no_change": False, "chat_openers": [self.candidate(e)]}
        await self.engine.review_outreach()
        await self.engine.close()

        async def should_not_call(request):
            raise AssertionError("unchanged evidence must not be replayed")

        self.engine = M.NarrativeEngine(
            self.engine.path, self.config, should_not_call, lambda: self.now
        )
        self.now += 600
        self.assertEqual(await self.engine.review_outreach(), [])
