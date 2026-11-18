"""Persistent text projects committed with scene actions and their real records."""

import copy
import uuid

from . import study_items

WRITING = {"project_start", "project_write", "project_revise"}
CONTROL = {"project_finish", "project_pause", "project_resume"}
KINDS = WRITING | CONTROL
LABELS = {
    "project_start": "建立创作项目",
    "project_write": "续写项目初稿",
    "project_revise": "修订项目段落",
    "project_finish": "核对并定稿",
    "project_pause": "暂停创作项目",
    "project_resume": "继续创作项目",
}
STAGES = {
    "outline": "构思已保存",
    "draft": "初稿创作中",
    "revision": "逐段修订中",
    "ready": "待定稿",
    "completed": "已定稿",
}


def record(state, ref):
    item = state["items"].get(ref.get("item_id"), {})
    return next(
        (
            r
            for r in item.get("notes", item.get("documents", []))
            if r["id"] == ref.get("record_id")
        ),
        None,
    )


def summary(project):
    return {
        "id": project["id"],
        "title": project["title"],
        "status": project["status"],
        "stage": project["stage"],
        "stage_label": STAGES[project["stage"]],
        "target_parts": project["target_parts"],
        "draft_parts": len(project["parts"]),
        "revised_parts": sum(bool(p.get("revision")) for p in project["parts"]),
        "revision": project["revision"],
        "created_at": project["created_at"],
        "updated_at": project["updated_at"],
        "last_item_id": project["last_item_id"],
        "paused_by": project.get("paused_by"),
    }


def public(state, admin=False):
    values = sorted(
        state.get("projects", {}).values(),
        key=lambda p: (
            p["status"] == "active",
            p["status"] == "paused",
            p["updated_at"],
        ),
        reverse=True,
    )
    rows = []
    for project in values if admin else values[:12]:
        row = summary(project)
        outline = record(state, project["outline"])
        row["outline_excerpt"] = (outline or {}).get("text", "")[:400]
        row["parts"] = [
            {
                "number": p["number"],
                "title": p["title"],
                "revised": bool(p.get("revision")),
            }
            for p in project["parts"]
        ]
        latest = record(state, project["records"][-1])
        row["latest_excerpt"] = (latest or {}).get("text", "")[:500]
        row["latest_record_missing"] = latest is None
        rows.append(row)
    return rows


def detail(state, project_id):
    project = state.get("projects", {}).get(project_id)
    if project is None:
        raise ValueError("项目不存在或不属于当前世界")
    result = summary(project)
    result["records"] = []
    for ref in project["records"]:
        saved = record(state, ref)
        result["records"].append(
            dict(
                ref,
                title=saved.get("title", "") if saved else "",
                text=saved.get("text", "") if saved else "",
                missing=saved is None,
            )
        )
    return result


def validate(step, scene):
    kind = step["kind"]
    known = {p["id"] for p in scene.get("projects", [])}
    # Some native providers use the usual target_id slot for project controls.
    # Normalize only a known project, and never accept conflicting targets.
    if kind in CONTROL and step.get("target_id") in known:
        if step.get("project_id", step["target_id"]) != step["target_id"]:
            raise ValueError("项目目标不一致")
        step["project_id"] = step.pop("target_id")
    allowed = (
        {"kind", "project_id"}
        | ({"target_id", "title", "text"} if kind in WRITING else set())
        | ({"parts"} if kind == "project_start" else set())
        | ({"section"} if kind == "project_revise" else set())
    )
    if set(step) - allowed:
        raise ValueError("未知创作项目字段")
    if kind == "project_start":
        if not isinstance(step.get("title"), str) or not step["title"].strip():
            raise ValueError("请为新项目填写标题")
        if "project_id" in step:
            raise ValueError("新项目 ID 在构思保存完成后生成")
        if type(step.get("parts", 3)) is not int or not 1 <= step.get("parts", 3) <= 8:
            raise ValueError("项目初稿计划为 1–8 段")
    elif not isinstance(step.get("project_id"), str) or step["project_id"] not in known:
        raise ValueError("请选择当前世界已有项目")
    if kind in WRITING:
        item = next(
            (i for i in scene["items"] if i["id"] == step.get("target_id")), None
        )
        if not item or item["kind"] not in {"notebook", "computer"}:
            raise ValueError("请选择纸本或电脑作为创作载体")
        study_items.content(step, 500 if item["kind"] == "notebook" else 1000)
    if kind == "project_revise" and (
        type(step.get("section")) is not int or not 1 <= step["section"] <= 8
    ):
        raise ValueError("请指定要修订的段落编号")


def writing_step(item, step):
    return {
        "kind": "write_note" if item["kind"] == "notebook" else "computer_work",
        "mode": "writing",
        "title": step.get("title", "未命名记录"),
        "text": step["text"],
    }


def check(state, step, actor, now):
    kind = step["kind"]
    project = state.get("projects", {}).get(step.get("project_id"))
    item = state["items"].get(step.get("target_id"))
    if kind == "project_start":
        title, _ = study_items.content(
            step, 500 if item and item["kind"] == "notebook" else 1000
        )
        active = [
            p for p in state.get("projects", {}).values() if p["status"] == "active"
        ]
        if len(active) >= 4:
            raise ValueError("已有四个进行中项目，请先推进或暂停现有项目")
        if any(
            p["title"].casefold() == title.casefold()
            and p["status"] in {"active", "paused"}
            for p in state.get("projects", {}).values()
        ):
            raise ValueError("已有同名未完成项目，请继续原项目")
    else:
        if project is None:
            raise ValueError("项目不存在")
        if kind == "project_resume":
            if project["status"] != "paused":
                raise ValueError("只能继续已暂停的项目")
            if (
                project.get("paused_by") == "admin"
                and (state.get("flow") or {}).get("origin") != "admin"
            ):
                raise ValueError("管理员暂停的项目需等待管理员恢复")
            if (
                sum(p["status"] == "active" for p in state.get("projects", {}).values())
                >= 4
            ):
                raise ValueError("请先完成或暂停其他进行中项目")
            return 10
        if project["status"] != "active":
            raise ValueError("项目已暂停或定稿")
        if kind == "project_pause":
            return 10
        if kind == "project_write" and len(project["parts"]) >= project["target_parts"]:
            raise ValueError("初稿段落已齐，请逐段修订")
        if kind == "project_revise":
            if len(project["parts"]) < project["target_parts"]:
                raise ValueError("先完成计划中的初稿段落")
            part = next(
                (p for p in project["parts"] if p["number"] == step.get("section")),
                None,
            )
            if not part:
                raise ValueError("段落尚不存在")
            old = record(state, part.get("revision") or part["draft"])
            if old is None:
                raise ValueError("原段落记录不可读取，不能伪造修订")
            if old["text"].strip() == step.get("text", "").strip():
                raise ValueError("修订正文与原文相同")
        if kind == "project_finish":
            if len(project["parts"]) != project["target_parts"] or not all(
                p.get("revision") and record(state, p["revision"])
                for p in project["parts"]
            ):
                raise ValueError("每段都完成修订后才能定稿")
            medium = state["items"].get(project["last_item_id"])
            if not medium:
                raise ValueError("最后使用的创作载体不存在")
            study_items.check(
                state,
                medium,
                {"kind": "read_notes"}
                if medium["kind"] == "notebook"
                else {"kind": "computer_work", "mode": "organize"},
                actor,
                now,
            )
            return 60
    if not item or item["kind"] not in {"notebook", "computer"}:
        raise ValueError("创作载体不存在")
    return study_items.check(state, item, writing_step(item, step), actor, now)


def label(state, step):
    project = state.get("projects", {}).get(step.get("project_id"))
    return (
        LABELS[step["kind"]]
        + "："
        + (project["title"] if project else step.get("title", "新项目"))
    )


def apply(state, step, now, origin="life_model"):
    kind = step["kind"]
    projects = state.setdefault("projects", {})
    project = projects.get(step.get("project_id"))
    ref = None
    if kind in WRITING:
        item = state["items"][step["target_id"]]
        study_items.apply(item, writing_step(item, step), now)
        saved = (
            item["notes"][-1] if item["kind"] == "notebook" else item["documents"][-1]
        )
        ref = {
            "item_id": item["id"],
            "record_id": saved["id"],
            "operation": kind,
            "created_at": now,
        }
        if kind == "project_start":
            pid = "project_" + uuid.uuid4().hex[:16]
            project = {
                "id": pid,
                "title": step["title"].strip(),
                "status": "active",
                "stage": "outline",
                "target_parts": step.get("parts", 3),
                "parts": [],
                "created_at": now,
                "updated_at": now,
                "revision": 0,
                "outline": copy.deepcopy(ref),
                "records": [],
                "last_item_id": item["id"],
            }
            projects[pid] = project
        elif kind == "project_write":
            number = len(project["parts"]) + 1
            ref["section"] = number
            project["parts"].append(
                {
                    "number": number,
                    "title": saved["title"],
                    "draft": copy.deepcopy(ref),
                    "revision": None,
                }
            )
            project["stage"] = (
                "revision"
                if len(project["parts"]) == project["target_parts"]
                else "draft"
            )
        else:
            ref["section"] = step["section"]
            part = next(p for p in project["parts"] if p["number"] == step["section"])
            part["revision"] = copy.deepcopy(ref)
            project["stage"] = (
                "ready" if all(p["revision"] for p in project["parts"]) else "revision"
            )
        saved["project_id"] = project["id"]
        saved["project_operation"] = kind
        project["records"].append(ref)
        project["last_item_id"] = item["id"]
    elif kind == "project_pause":
        project.update(status="paused", paused_by=origin)
    elif kind == "project_resume":
        project.update(status="active", paused_by=None)
    elif kind == "project_finish":
        project.update(status="completed", stage="completed", finished_at=now)
    project["revision"] += 1
    project["updated_at"] = now
    value = summary(project)
    return {
        "project_id": project["id"],
        "project_title": project["title"],
        "project_stage": project["stage"],
        "project_status": project["status"],
        "draft_parts": value["draft_parts"],
        "revised_parts": value["revised_parts"],
        "target_parts": value["target_parts"],
        "record_id": ref["record_id"] if ref else None,
        "section": ref.get("section") if ref else None,
    }


def candidates(state):
    result = []
    for project in state.get("projects", {}).values():
        if project["status"] == "paused":
            if project.get("paused_by") != "admin":
                result.append({"kind": "project_resume", "project_id": project["id"]})
            continue
        if project["status"] != "active":
            continue
        result.append({"kind": "project_pause", "project_id": project["id"]})
        if project["stage"] == "ready":
            result.append({"kind": "project_finish", "project_id": project["id"]})
        writing = (
            "project_write"
            if len(project["parts"]) < project["target_parts"]
            else "project_revise"
        )
        section = next((p["number"] for p in project["parts"] if not p["revision"]), 1)
        for item in state["items"].values():
            if item["kind"] not in {"notebook", "computer"}:
                continue
            result.append(
                {
                    "kind": writing,
                    "project_id": project["id"],
                    "target_id": item["id"],
                    **({"section": section} if writing == "project_revise" else {}),
                }
            )
    if sum(p["status"] == "active" for p in state.get("projects", {}).values()) < 4:
        result += [
            {"kind": "project_start", "target_id": i["id"], "parts": 3}
            for i in state["items"].values()
            if i["kind"] in {"notebook", "computer"}
        ]
    return result
