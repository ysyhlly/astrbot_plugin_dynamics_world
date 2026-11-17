import copy
import pytest
from test_spatial import GLOBAL
from test_scenes import setup, scene, item, start, step, finish
from test_study_items import preset
from astrbot_plugin_dynamics_world.scenes import SceneService, SceneActionError
from astrbot_plugin_dynamics_world import study_items


def retire(engine, target, **extra):
    return engine.scenes.retire_item(
        GLOBAL,
        dict(item_id=target, expected_revision=scene(engine)["revision"], **extra),
    )


def test_retirement_keeps_drafts_excludes_actions_and_survives_reload(rig):
    engine, now, _ = setup(rig)
    preset(
        engine,
        "computer_work",
        mode="writing",
        title="旧稿",
        text="必须逐字保留的旧稿。",
    )
    finish(engine, now)
    computer = item(engine, "computer")
    saved = copy.deepcopy(computer["documents"])
    result = retire(engine, computer["id"])
    assert result["records_retained"]
    engine.scenes = SceneService(engine)
    public = scene(engine)
    assert not any(i["kind"] == "computer" for i in public["items"])
    assert "archived_items" not in public
    assert not any(
        a.get("target_id") == computer["id"] for a in public["available_actions"]
    )
    with engine._db() as db:
        admin = engine.scenes.snapshot(db, GLOBAL, now[0], admin=True)
        archived = admin["archived_items"][0]
        assert (
            archived["documents"] == saved
            and archived["retired"]
            and not archived["powered"]
        )
        _, _, s = engine.scenes.load(db, GLOBAL)
        actor = engine.spatial.snapshot(db, GLOBAL, now[0])
        for kind in [
            "power_on",
            "power_off",
            "computer_work",
            "take",
            "place_item",
            "project_start",
        ]:
            with pytest.raises(ValueError, match="停用"):
                engine.scenes.check_step(
                    s,
                    {"kind": kind, "target_id": computer["id"], "text": "新文字"},
                    actor,
                    {},
                    now[0],
                )
        with pytest.raises(ValueError, match="停用"):
            study_items.check(
                s, s["items"][computer["id"]], {"kind": "computer_work"}, actor, now[0]
            )


def test_retire_cancels_related_unfinished_write_without_inventing_draft(rig):
    engine, now, _ = setup(rig)
    computer = item(engine, "computer")
    preset(engine, "computer_work", mode="writing", title="未完成", text="不应保存")
    step(engine, now)
    step(engine, now)
    result = retire(engine, computer["id"])
    assert result["cancelled_related_flow"]
    assert not scene(engine)["action"]
    now[0] += 10000
    scene(engine)
    with engine._db() as db:
        _, _, s = engine.scenes.load(db, GLOBAL)
        assert s["items"][computer["id"]]["documents"] == []


def test_retire_preserves_unrelated_action_and_rejects_stale_revision(rig):
    engine, now, _ = setup(rig)
    computer = item(engine, "computer")
    start(engine, [{"kind": "rest"}])
    before = scene(engine)
    with pytest.raises(SceneActionError, match="变化"):
        engine.scenes.retire_item(
            GLOBAL, {"item_id": computer["id"], "expected_revision": -1}
        )
    result = retire(engine, computer["id"])
    assert not result["cancelled_related_flow"]
    assert scene(engine)["action"]["id"] == before["action"]["id"]
    assert retire(engine, computer["id"])["already_retired"]
