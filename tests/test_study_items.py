import json
import pytest

from test_spatial import GLOBAL, state
from test_scenes import setup, scene, item, start, step, finish
from astrbot_plugin_dynamics_world.scenes import SceneService, SceneActionError
from astrbot_plugin_dynamics_world.life.core.narrative_prompt import (
    build_narrative_prompt,
)


def preset(engine, name, **body):
    return engine.scenes.administer(
        GLOBAL,
        dict(
            action="preset",
            preset=name,
            expected_revision=scene(engine)["revision"],
            **body,
        ),
    )


def test_notebook_has_real_saved_content_only_after_completion_and_survives_restart(
    rig,
):
    engine, now, _ = setup(rig)
    preset(
        engine, "write_note", title="写作线索", text="雨停后的湖边，纸船还留在岸边。"
    )
    assert not item(engine, "notebook")["notes"]
    step(engine, now)
    step(engine, now)
    assert item(engine, "notebook")["carried"] and not item(engine, "notebook")["notes"]
    engine.scenes = SceneService(engine)
    step(engine, now)
    notes = item(engine, "notebook")["notes"]
    assert len(notes) == 1 and notes[0]["title"] == "写作线索"
    assert notes[0]["text"] == "雨停后的湖边，纸船还留在岸边。"
    for _ in range(3):
        scene(engine)
    assert item(engine, "notebook")["note_count"] == 1
    start(engine, [{"kind": "read_notes", "target_id": item(engine, "notebook")["id"]}])
    finish(engine, now)
    assert (
        item(engine, "notebook")["note_count"] == 1
        and item(engine, "notebook")["last_read_at"]
    )


def test_computer_is_stationary_requires_power_and_preserves_saved_draft(rig):
    engine, now, _ = setup(rig)
    computer = item(engine, "computer")
    with pytest.raises(SceneActionError) as error:
        start(engine, [{"kind": "take", "target_id": computer["id"]}])
    assert error.value.code == "scene_computer_stationary"
    preset(
        engine,
        "computer_work",
        mode="writing",
        title="小镇片段",
        text="深夜，窗边还有一盏灯。",
    )
    step(engine, now)
    with engine._db() as db:
        _, _, s = engine.scenes.load(db, GLOBAL)
        actor = engine.spatial.snapshot(db, GLOBAL, now[0])
        with pytest.raises(SceneActionError, match="先打开"):
            engine.scenes.check_step(
                s,
                {
                    "kind": "computer_work",
                    "target_id": computer["id"],
                    "mode": "gaming",
                },
                actor,
                {},
                now[0],
            )
    step(engine, now)
    assert (
        item(engine, "computer")["powered"]
        and item(engine, "computer")["document_count"] == 0
    )
    step(engine, now)
    assert item(engine, "computer")["documents"][0]["text"] == "深夜，窗边还有一盏灯。"
    start(
        engine,
        [{"kind": "computer_work", "target_id": computer["id"], "mode": "organize"}],
    )
    finish(engine, now)
    assert (
        item(engine, "computer")["organize_count"] == 1
        and item(engine, "computer")["document_count"] == 1
    )
    start(
        engine,
        [{"kind": "computer_work", "target_id": computer["id"], "mode": "gaming"}],
    )
    finish(engine, now)
    assert (
        item(engine, "computer")["gaming_minutes"] == 10
        and item(engine, "computer")["document_count"] == 1
    )
    receipt = next(
        r for r in scene(engine)["receipts"] if r["kind"] == "step.completed"
    )
    assert "saved_record" not in receipt["result"]
    start(engine, [{"kind": "power_off", "target_id": computer["id"]}])
    finish(engine, now)
    assert not item(engine, "computer")["powered"]


def test_cancelling_typing_retains_power_but_does_not_save_unwritten_content(rig):
    engine, now, _ = setup(rig)
    preset(engine, "computer_work", mode="writing", title="未写完", text="不应提前保存")
    step(engine, now)
    step(engine, now)
    engine.scenes.administer(
        GLOBAL, {"action": "cancel", "expected_revision": scene(engine)["revision"]}
    )
    assert (
        item(engine, "computer")["powered"]
        and item(engine, "computer")["document_count"] == 0
    )


def test_illegal_content_is_rejected_before_any_step_and_current_rest_target_is_normalized(
    rig,
):
    engine, now, _ = setup(rig)
    with pytest.raises(ValueError):
        preset(engine, "write_note", title="长文本", text="字" * 501)
    assert not scene(engine)["action"] and not item(engine, "notebook")["carried"]
    room = next(r for r in scene(engine)["rooms"] if r["name"] == "房间")
    start(engine, [{"kind": "enter", "target_id": room["id"]}])
    finish(engine, now)
    action = engine.scenes.validate(
        {"operation": "start", "steps": [{"kind": "rest", "target_id": room["id"]}]},
        {"scope": GLOBAL, "snapshot": state(engine)},
    )
    assert "target_id" not in action["steps"][0]
    other = next(r for r in scene(engine)["rooms"] if r["name"] == "玄关")
    with pytest.raises(ValueError):
        engine.scenes.validate(
            {
                "operation": "start",
                "steps": [{"kind": "rest", "target_id": other["id"]}],
            },
            {"scope": GLOBAL, "snapshot": state(engine)},
        )


@pytest.mark.asyncio
async def test_life_model_autonomously_enters_takes_and_writes_with_provenance(rig):
    engine, now, _ = setup(rig)
    note = item(engine, "notebook")
    requests = []

    async def model(request):
        requests.append(request)
        if len(requests) > 1:
            return {"no_change": True}
        return {
            "no_change": False,
            "world_action": {
                "operation": "start",
                "steps": [
                    {"kind": "enter", "target_id": note["room_id"]},
                    {"kind": "take", "target_id": note["id"]},
                    {
                        "kind": "write_note",
                        "target_id": note["id"],
                        "title": "观察",
                        "text": "花田今天很安静。",
                    },
                ],
            },
        }

    engine.model = model
    await engine.tick()
    assert scene(engine)["action"]["origin"] == "life_model"
    finish(engine, now)
    await engine.tick()
    assert item(engine, "notebook")["note_count"] == 1
    assert any(
        e.get("data", {}).get("trigger") == "world_action_completed"
        for r in requests
        for e in r["events"]
    )
    with engine._db() as db:
        record = json.loads(
            db.execute(
                "SELECT payload FROM world_scene_events WHERE kind='action.started'"
            ).fetchone()[0]
        )
    assert record["origin"] == "life_model" and record["source_event_ids"][
        0
    ].startswith("life.tick:")
    assert "text" not in record["steps"][-1]  # No unsaved prose in started receipts.
    assert "无需等待管理员点击" in build_narrative_prompt(requests[0], {})


@pytest.mark.asyncio
async def test_invalid_autonomous_target_has_actionable_failure_and_no_partial_effects(
    rig,
):
    engine, now, _ = setup(rig)
    note = item(engine, "notebook")

    async def model(request):
        return {
            "world_action": {
                "operation": "start",
                "steps": [{"kind": "take", "target_id": note["id"]}],
            }
        }

    engine.model = model
    result = await engine.tick()
    assert (
        result["results"][0]["status"] == "invalid"
        and not item(engine, "notebook")["carried"]
    )
    with engine._db() as db:
        failure = db.execute(
            "SELECT reason_code FROM validation_failures ORDER BY occurred DESC LIMIT 1"
        ).fetchone()[0]
        rejected = json.loads(
            db.execute(
                "SELECT payload FROM world_scene_events WHERE kind='action.rejected'"
            ).fetchone()[0]
        )
    assert (
        failure == "validation.scene_item_not_here"
        and rejected["origin"] == "life_model"
    )


def test_available_actions_are_legal_and_do_not_require_taking_computer(rig):
    engine, now, _ = setup(rig)
    assert not any(
        a.get("kind") == "computer_work" for a in scene(engine)["available_actions"]
    )
    room = item(engine, "computer")["room_id"]
    start(engine, [{"kind": "enter", "target_id": room}])
    finish(engine, now)
    actions = scene(engine)["available_actions"]
    cid = item(engine, "computer")["id"]
    assert {"kind": "power_on", "target_id": cid} in actions
    assert {"kind": "take", "target_id": cid} not in actions
    start(engine, [{"kind": "power_on", "target_id": cid}])
    finish(engine, now)
    assert {"kind": "computer_work", "target_id": cid, "mode": "gaming"} in scene(
        engine
    )["available_actions"]


def test_redundant_completed_prerequisites_are_skipped_without_fake_receipts(rig):
    engine, now, _ = setup(rig)
    room = item(engine, "notebook")["room_id"]
    start(
        engine,
        [
            {"kind": "enter", "target_id": room},
            {"kind": "take", "target_id": item(engine, "notebook")["id"]},
        ],
    )
    finish(engine, now)
    start(
        engine,
        [
            {"kind": "enter", "target_id": room},
            {"kind": "take", "target_id": item(engine, "notebook")["id"]},
            {
                "kind": "write_note",
                "target_id": item(engine, "notebook")["id"],
                "title": "再次记事",
                "text": "第二次记录。",
            },
        ],
    )
    assert len(scene(engine)["action"]["steps"]) == 1
    finish(engine, now)
    assert item(engine, "notebook")["note_count"] == 1
    with engine._db() as db:
        rows = [
            json.loads(r[0])
            for r in db.execute(
                "SELECT payload FROM world_scene_events WHERE kind='step.completed'"
            )
        ]
    assert [r["operation"] for r in rows].count("enter") == 1 and [
        r["operation"] for r in rows
    ].count("take") == 1
