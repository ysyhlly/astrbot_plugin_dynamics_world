import json
import pytest
from test_spatial import SCOPE, GLOBAL, state
from test_scenes import setup, scene, start, finish, item
from astrbot_plugin_dynamics_world import creative_projects
from astrbot_plugin_dynamics_world.visual_context import WorldVisualContext


def prepared(rig):
    engine, now, _ = setup(rig)
    engine.visuals = WorldVisualContext(engine)
    note = item(engine, "notebook")
    start(
        engine,
        [
            {"kind": "enter", "target_id": note["room_id"]},
            {"kind": "take", "target_id": note["id"]},
        ],
    )
    finish(engine, now)
    return engine, now, note["id"]


def begin(engine, now, medium, parts=2):
    start(
        engine,
        [
            {
                "kind": "project_start",
                "target_id": medium,
                "title": "同一个故事",
                "text": "原始构思：一扇门，两个不同的选择。",
                "parts": parts,
            }
        ],
    )
    finish(engine, now)
    return scene(engine)["projects"][0]["id"]


def test_start_and_draft_are_only_saved_after_completion_and_cancel_is_safe(rig):
    engine, now, note = prepared(rig)
    start(
        engine,
        [
            {
                "kind": "project_start",
                "target_id": note,
                "title": "同一个故事",
                "text": "还没写完的构思",
                "parts": 2,
            }
        ],
    )
    assert (
        scene(engine)["projects"] == [] and item(engine, "notebook")["note_count"] == 0
    )
    engine.scenes.administer(
        SCOPE, {"action": "cancel", "expected_revision": scene(engine)["revision"]}
    )
    assert (
        scene(engine)["projects"] == [] and item(engine, "notebook")["note_count"] == 0
    )
    pid = begin(engine, now, note)
    start(
        engine,
        [
            {
                "kind": "project_write",
                "project_id": pid,
                "target_id": note,
                "title": "第一段",
                "text": "这段取消，不应保存。",
            }
        ],
    )
    assert scene(engine)["projects"][0]["draft_parts"] == 0
    engine.scenes.administer(
        SCOPE, {"action": "cancel", "expected_revision": scene(engine)["revision"]}
    )
    assert (
        item(engine, "notebook")["note_count"] == 1
        and scene(engine)["projects"][0]["stage"] == "outline"
    )


def test_full_project_has_real_versions_unique_revision_counts_and_final_receipt(rig):
    engine, now, note = prepared(rig)
    pid = begin(engine, now, note)
    with pytest.raises(ValueError):
        start(engine, [{"kind": "project_finish", "project_id": pid}])
    start(
        engine,
        [
            {
                "kind": "project_write",
                "project_id": pid,
                "target_id": note,
                "title": "开头",
                "text": "她推开第一扇门。",
            },
            {
                "kind": "project_write",
                "project_id": pid,
                "target_id": note,
                "title": "结尾",
                "text": "门后有一盏灯。",
            },
        ],
    )
    finish(engine, now)
    assert scene(engine)["projects"][0]["stage"] == "revision"
    start(
        engine,
        [
            {
                "kind": "project_revise",
                "project_id": pid,
                "target_id": note,
                "section": 1,
                "title": "开头修订",
                "text": "她犹豫片刻，推开那扇旧门。",
            }
        ],
    )
    finish(engine, now)
    assert scene(engine)["projects"][0]["revised_parts"] == 1
    with pytest.raises(ValueError):
        start(engine, [{"kind": "project_finish", "project_id": pid}])
    start(
        engine,
        [
            {
                "kind": "project_revise",
                "project_id": pid,
                "target_id": note,
                "section": 2,
                "title": "结尾修订",
                "text": "一盏灯亮着，仿佛一直在等她。",
            },
            {"kind": "project_finish", "project_id": pid},
        ],
    )
    finish(engine, now)
    project = scene(engine)["projects"][0]
    assert (
        project["id"] == pid
        and project["status"] == "completed"
        and project["revised_parts"] == 2
    )
    with engine._db() as db:
        _, _, s = engine.scenes.load(db, SCOPE)
        detail = creative_projects.detail(s, pid)
    assert (
        len(detail["records"]) == 5
        and detail["records"][1]["text"] == "她推开第一扇门。"
    )
    assert len({r["record_id"] for r in detail["records"]}) == 5
    assert all(r["project_id"] == pid for r in item(engine, "notebook")["notes"])
    assert any(
        r.get("result", {}).get("project_status") == "completed"
        for r in scene(engine)["receipts"]
    )
    with pytest.raises(ValueError):
        start(
            engine,
            [
                {
                    "kind": "project_write",
                    "project_id": pid,
                    "target_id": note,
                    "title": "额外",
                    "text": "不能修改已定稿项目",
                }
            ],
        )


def test_restart_resume_and_new_medium_preserve_project_and_previous_records(rig):
    engine, now, note = prepared(rig)
    pid = begin(engine, now, note, 1)
    from astrbot_plugin_dynamics_world.scenes import SceneService

    engine.scenes = SceneService(engine)
    assert scene(engine)["projects"][0]["id"] == pid
    computer = item(engine, "computer")
    start(
        engine,
        [
            {"kind": "power_on", "target_id": computer["id"]},
            {
                "kind": "project_write",
                "project_id": pid,
                "target_id": computer["id"],
                "title": "电脑初稿",
                "text": "新一段保存在电脑，构思仍在纸本。",
            },
        ],
    )
    finish(engine, now)
    assert (
        item(engine, "notebook")["note_count"] == 1
        and item(engine, "computer")["document_count"] == 1
    )
    assert scene(engine)["projects"][0]["last_item_id"] == computer["id"]
    start(engine, [{"kind": "project_pause", "project_id": pid}])
    finish(engine, now)
    assert scene(engine)["projects"][0]["paused_by"] == "admin"
    assert not any(
        a.get("kind") == "project_resume" and a.get("project_id") == pid
        for a in scene(engine)["available_actions"]
    )
    action = engine.scenes.validate(
        {
            "operation": "start",
            "steps": [{"kind": "project_resume", "project_id": pid}],
        },
        {"scope": GLOBAL, "snapshot": state(engine)},
    )
    with pytest.raises(ValueError):
        with engine._db() as db:
            engine.scenes.commit(db, SCOPE, action, now[0], origin="life_model")
    start(engine, [{"kind": "project_resume", "project_id": pid}])
    finish(engine, now)
    assert scene(engine)["projects"][0]["status"] == "active"


def test_duplicates_foreign_ids_fake_sections_capacity_and_private_visual_context(rig):
    engine, now, note = prepared(rig)
    pid = begin(engine, now, note, 1)
    with pytest.raises(ValueError):
        start(
            engine,
            [
                {
                    "kind": "project_start",
                    "target_id": note,
                    "title": "同一个故事",
                    "text": "重复项目",
                }
            ],
        )
    with pytest.raises(ValueError):
        start(
            engine,
            [
                {
                    "kind": "project_write",
                    "project_id": "foreign",
                    "target_id": note,
                    "text": "未知项目",
                }
            ],
        )
    with pytest.raises(ValueError):
        start(engine, [{"kind": "project_pause", "target_id": "foreign"}])
    with pytest.raises(ValueError):
        start(
            engine,
            [
                {
                    "kind": "project_revise",
                    "project_id": pid,
                    "target_id": note,
                    "section": 1,
                    "text": "还没有初稿",
                }
            ],
        )
    with pytest.raises(ValueError):
        engine.scenes.validate(
            {
                "operation": "start",
                "steps": [{"kind": "project_pause", "project_id": pid}],
            },
            {"scope": SCOPE, "snapshot": state(engine)},
        )
    start(
        engine,
        [
            {
                "kind": "project_write",
                "project_id": pid,
                "target_id": note,
                "title": "私有草稿",
                "text": "PRIVATE_PROJECT_DRAFT",
            }
        ],
    )
    finish(engine, now)
    assert "PRIVATE_PROJECT_DRAFT" not in json.dumps(state(engine)["visual_sharing"])
    with pytest.raises(ValueError):
        start(
            engine,
            [
                {
                    "kind": "project_revise",
                    "project_id": pid,
                    "target_id": note,
                    "section": 1,
                    "text": "PRIVATE_PROJECT_DRAFT",
                }
            ],
        )
    with engine._db() as db:
        key, rev, s = engine.scenes.load(db, SCOPE)
        s["items"][note]["notes"] *= 25
        engine.scenes.save(db, key, rev, s)
    with pytest.raises(ValueError):
        start(
            engine,
            [
                {
                    "kind": "project_revise",
                    "project_id": pid,
                    "target_id": note,
                    "section": 1,
                    "text": "内容真实改变，也不能超过载体容量",
                }
            ],
        )
    assert scene(engine)["projects"][0]["revised_parts"] == 0


def test_late_restart_settles_one_step_and_keeps_same_project(rig):
    engine, now, note = prepared(rig)
    pid = begin(engine, now, note, 2)
    start(
        engine,
        [
            {
                "kind": "project_write",
                "project_id": pid,
                "target_id": note,
                "title": "一",
                "text": "第一段",
            },
            {
                "kind": "project_write",
                "project_id": pid,
                "target_id": note,
                "title": "二",
                "text": "第二段",
            },
        ],
    )
    now[0] += 86400
    snap = scene(engine)
    assert snap["projects"][0]["draft_parts"] == 1 and snap["action"]["index"] == 1
    assert snap["action"]["step_ends_at"] > now[0]
    finish(engine, now)
    assert scene(engine)["projects"][0]["draft_parts"] == 2


def test_known_control_target_alias_is_normalized_but_conflicts_are_rejected(rig):
    engine, now, note = prepared(rig)
    pid = begin(engine, now, note, 1)
    start(engine, [{"kind": "project_pause", "target_id": pid}])
    finish(engine, now)
    assert scene(engine)["projects"][0]["status"] == "paused"
    with pytest.raises(ValueError):
        start(
            engine,
            [{"kind": "project_resume", "target_id": pid, "project_id": "other"}],
        )
    start(engine, [{"kind": "project_resume", "target_id": pid}])
    finish(engine, now)
    assert scene(engine)["projects"][0]["status"] == "active"
