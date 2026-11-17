"""Correct-behavior regressions for AUD-01/02/03/05/06/07/08/09."""

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import test_outreach_queue as helpers
from astrbot_plugin_dynamics_world.life.core.narrative import normalize_scope
from astrbot_plugin_dynamics_world.life.service import LifeService
from astrbot_plugin_dynamics_world.world.core.store import WorldBookStore
from astrbot_plugin_dynamics_world.world.core.models import WorldBook


@pytest_asyncio.fixture
async def rig():
    case = helpers.OutreachTests()
    await case.asyncSetUp()
    try:
        yield case
    finally:
        await case.asyncTearDown()


def test_failed_save_rolls_back_memory_and_reports_failure(tmp_path):
    path = tmp_path / "store.json"
    store = WorldBookStore(str(path))
    store.upsert_book(WorldBook(id="saved", name="Original"))
    before = path.read_bytes()
    with patch(
        "astrbot_plugin_dynamics_world.world.core.store.os.replace",
        side_effect=OSError("synthetic disk failure"),
    ):
        with pytest.raises(OSError, match="worldbook_save_failed"):
            store.upsert_book(WorldBook(id="lost", name="Not saved"))
    assert store.get_book("lost") is None
    assert path.read_bytes() == before
    assert WorldBookStore(str(path)).get_book("saved").name == "Original"
    store.upsert_book(WorldBook(id="later", name="Later valid edit"))
    assert WorldBookStore(str(path)).get_book("lost") is None


@pytest.mark.parametrize("body", [b"{broken", b"[]"])
def test_invalid_existing_store_never_falls_back_to_empty(tmp_path, body):
    p = tmp_path / "store.json"
    p.write_bytes(body)
    with pytest.raises(OSError, match="worldbook_load_failed"):
        WorldBookStore(str(p))
    assert p.read_bytes() == body


def test_transient_load_failure_preserves_valid_store(tmp_path):
    p = tmp_path / "store.json"
    store = WorldBookStore(str(p))
    store.upsert_book(WorldBook(id="old", name="Must survive"))
    before = p.read_bytes()
    with patch("builtins.open", side_effect=PermissionError("temporary read error")):
        with pytest.raises(OSError, match="worldbook_load_failed"):
            WorldBookStore(str(p))
    assert p.read_bytes() == before
    assert WorldBookStore(str(p)).get_book("old") is not None


@pytest.mark.asyncio
async def test_pause_is_scoped_and_global_pause_still_wins(rig):
    other = normalize_scope(dict(rig.scope, umo="qq:GroupMessage:two"))
    rig.config["narrative_sessions"].append(other["umo"])
    await rig.engine.get_snapshot(other)
    await rig.engine.set_paused(True, rig.scope, proactive_only=True)
    assert not (await rig.engine.get_snapshot(other))["outreach_paused"]
    await rig.engine.set_paused(False, other, proactive_only=True)
    assert (await rig.engine.get_snapshot(rig.scope))["outreach_paused"]
    await rig.engine.set_outreach_paused(True)
    await rig.engine.set_paused(False, rig.scope, proactive_only=True)
    assert (await rig.engine.get_snapshot(rig.scope))["outreach_paused"]


@pytest.mark.asyncio
async def test_bad_candidate_does_not_discard_valid_care(rig):
    health = rig.event("health", "我头疼，先休息一下，晚点告诉你情况")
    weak = rig.event("weak", uid="u2")
    await rig.engine.ingest_events([health, weak])
    rig.response = {
        "no_change": False,
        "care_waits": [rig.candidate(health, care=True)],
        "chat_openers": [rig.candidate(weak)],
    }
    assert await rig.engine.review_outreach() == [
        {"status": "partial", "candidates": 1}
    ]
    assert rig.rows("select status from intents") == [("pending",)]
    assert rig.rows("select reason_code from validation_failures") == [
        ("outreach.social_reciprocal_topic_required",)
    ]


@pytest.mark.asyncio
async def test_enabling_contact_invalidates_cache_before_old_deadline(rig):
    e = await rig.social_evidence()
    rig.config["social_chat_enabled"] = False
    await rig.engine.review_outreach()
    rig.config["social_chat_enabled"] = True
    rig.now += 1
    rig.response = {"no_change": False, "chat_openers": [rig.candidate(e)]}
    assert (await rig.engine.review_outreach())[0]["candidates"] == 1
    assert len(rig.requests) == 2


@pytest.mark.asyncio
async def test_no_change_cache_has_bounded_lifetime(rig):
    await rig.social_evidence()
    await rig.engine.review_outreach()
    rig.now += 600
    assert await rig.engine.review_outreach() == []
    rig.now += 1201
    assert (await rig.engine.review_outreach())[0]["status"] == "ok"
    assert len(rig.requests) == 2


@pytest.mark.asyncio
async def test_old_optout_survives_restart_and_only_explicit_allow_clears_it(rig):
    await rig.engine.ingest_events(
        [rig.event("refuse", "以后不要主动找我聊天", age=90000)]
    )
    e = await rig.social_evidence()
    model = rig.engine.model
    await rig.engine.close()
    rig.engine = helpers.M.NarrativeEngine(
        rig.engine.path, rig.config, model, lambda: rig.now
    )
    with rig.engine._db() as db:
        assert not rig.engine._contact_allowed(db, rig.scope, "u1")
    with pytest.raises(ValueError, match="declined"):
        rig.engine._social_chat(
            rig.candidate(e),
            rig.scope,
            {e["event_id"]: rig.engine._event(e, rig.now)},
            rig.now,
        )
    await rig.engine.ingest_events(
        [rig.event("quoted", "他说以后不要主动找我聊天", age=0)]
    )
    with rig.engine._db() as db:
        assert not rig.engine._contact_allowed(db, rig.scope, "u1")
    await rig.engine.ingest_events(
        [rig.event("allow", "现在可以主动找我聊天了", age=0)]
    )
    with rig.engine._db() as db:
        assert rig.engine._contact_allowed(db, rig.scope, "u1")


@pytest.mark.asyncio
async def test_existing_legacy_refusal_is_backfilled_without_changing_events(rig):
    await rig.engine.ingest_events(
        [rig.event("old", "以后不要主动找我聊天", age=90000)]
    )
    original = rig.rows("select event_id,payload,status from events")
    with rig.engine._db() as db:
        db.execute("DELETE FROM outreach_preferences")
        db.execute("DELETE FROM metadata WHERE key='outreach_preferences_v1'")
    model = rig.engine.model
    await rig.engine.close()
    rig.engine = helpers.M.NarrativeEngine(
        rig.engine.path, rig.config, model, lambda: rig.now
    )
    assert rig.rows("select event_id,payload,status from events") == original
    with rig.engine._db() as db:
        assert not rig.engine._contact_allowed(db, rig.scope, "u1")


@pytest.mark.asyncio
async def test_optout_revokes_a_claimed_send_and_does_not_affect_another_member(rig):
    e = await rig.social_evidence()
    rig.response = {"no_change": False, "chat_openers": [rig.candidate(e)]}
    await rig.engine.review_outreach()
    iid = rig.rows("select intent_id from intents")[0][0]
    rig.now += 1801
    await rig.engine.update_intent(iid, "claimed")
    await rig.engine.ingest_events([rig.event("stop", "别再主动找我聊天", age=0)])
    assert (await rig.engine.get_intent(iid))["item"]["status"] == "cancelled"
    with rig.engine._db() as db:
        assert rig.engine._contact_allowed(db, rig.scope, "u2")


@pytest.mark.asyncio
async def test_world_tick_independent_of_slow_outreach_and_both_tasks_cancel():
    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow():
        entered.set()
        await release.wait()

    narrative = NS(
        environment=NS(schedule_all=lambda: None, close=AsyncMock()),
        review_outreach=slow,
        tick=AsyncMock(),
        close=AsyncMock(),
    )
    service = NS(
        is_active=lambda: True, narrative=narrative, _stop_scheduler=lambda: None
    )
    service._narrative_task = asyncio.create_task(LifeService._narrative_loop(service))
    service._outreach_task = asyncio.create_task(LifeService._outreach_loop(service))
    await asyncio.wait_for(entered.wait(), 1)
    await asyncio.sleep(0.02)
    narrative.tick.assert_awaited_once()
    await LifeService.terminate(service)
    assert service._narrative_task.done() and service._outreach_task.done()
    narrative.close.assert_awaited_once()


def test_release_rejects_stdlib_logger_even_when_aliased(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "world_build_audit", Path(__file__).parents[1] / "build_release.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path / "plugin"
    root.mkdir()
    (root / "main.py").write_text("import logging as log\n", encoding="utf-8")
    with pytest.raises(ValueError, match="astrbot.api.logger"):
        module.build(root, tmp_path / "bad.zip")


@pytest.mark.asyncio
async def test_policy_refusal_is_not_replayed_when_negative_cache_expires(rig):
    await rig.social_evidence()

    class PolicyRefusal(Exception):
        code = "PROHIBITED_CONTENT"

    rig.engine.model = AsyncMock(side_effect=PolicyRefusal())
    assert (await rig.engine.review_outreach())[0]["status"] == "policy_refusal"
    rig.now += 3600
    assert await rig.engine.review_outreach() == []
    rig.engine.model.assert_awaited_once()
