from __future__ import annotations

import json
import re
from typing import Any

from .models import WorldBook, WorldEntry, new_uid


def _try_parse_json(text: str) -> Any | None:
    text = text.strip()
    if not text:
        return None
    # strip markdown fence
    fence = re.match(r"^```(?:json|JSON)?\s*([\s\S]*?)\s*```$", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except Exception:
        # try extract outermost object/array
        for opener, closer in (("{", "}"), ("[", "]")):
            start = text.find(opener)
            end = text.rfind(closer)
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except Exception:
                    pass
    return None


def _normalize_st_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize SillyTavern / common lorebook entry fields."""
    out = dict(raw)
    if "keys" not in out and "key" in out:
        out["keys"] = out["key"]
    if "secondary_keys" not in out:
        if "keysecondary" in out:
            out["secondary_keys"] = out["keysecondary"]
        elif "secondary_keys" not in out and "keysSecondary" in out:
            out["secondary_keys"] = out["keysSecondary"]
    if "priority" not in out:
        if "order" in out:
            out["priority"] = out["order"]
        elif "insertion_order" in out:
            out["priority"] = out["insertion_order"]
    if "name" not in out and "comment" in out:
        out["name"] = out["comment"]
    if "enabled" not in out and "disable" in out:
        out["enabled"] = not bool(out["disable"])
    # ST match_whole_words / case_sensitive may live under extensions
    ext = out.get("extensions") if isinstance(out.get("extensions"), dict) else {}
    if "match_whole_word" not in out and ext.get("match_whole_words") is not None:
        out["match_whole_word"] = ext.get("match_whole_words")
    if "case_sensitive" not in out and ext.get("case_sensitive") is not None:
        out["case_sensitive"] = ext.get("case_sensitive")
    return out


def import_from_json_obj(obj: Any, *, default_name: str = "导入的世界书") -> WorldBook:
    if isinstance(obj, list):
        # bare entry list
        entries = [WorldEntry.from_dict(_normalize_st_entry(x)) for x in obj if isinstance(x, dict)]
        return WorldBook(id=new_uid(), name=default_name, entries=entries)

    if not isinstance(obj, dict):
        raise ValueError("JSON 根节点必须是对象或数组")

    # SillyTavern character card: character_book
    if "character_book" in obj and isinstance(obj["character_book"], dict):
        cb = obj["character_book"]
        name = str(cb.get("name") or obj.get("name") or default_name)
        return WorldBook.from_dict(
            {
                "name": name,
                "description": str(cb.get("description") or obj.get("description") or ""),
                "entries": cb.get("entries", []),
            }
        )

    # SillyTavern world info export often has entries as dict
    if "entries" in obj:
        book = WorldBook.from_dict(
            {
                "name": str(obj.get("name") or obj.get("title") or default_name),
                "description": str(obj.get("description") or obj.get("desc") or ""),
                "enabled": obj.get("enabled", True),
                "auto_scenario": obj.get("auto_scenario", True),
                "entries": obj.get("entries", []),
                "id": obj.get("id") or new_uid(),
            }
        )
        # re-normalize ST fields that WorldEntry.from_dict may miss on nested raw
        normalized: list[WorldEntry] = []
        raw_entries = obj.get("entries")
        if isinstance(raw_entries, dict):
            for k, v in raw_entries.items():
                if isinstance(v, dict):
                    e = WorldEntry.from_dict(_normalize_st_entry(v))
                    # WorldEntry.from_dict 一定会补一个随机 uid，所以只能看原始字段
                    if not str(v.get("uid") or v.get("id") or "").strip():
                        e.uid = str(k)
                    normalized.append(e)
            book.entries = normalized
        elif isinstance(raw_entries, list):
            book.entries = [
                WorldEntry.from_dict(_normalize_st_entry(x))
                for x in raw_entries
                if isinstance(x, dict)
            ]
        return book

    # single entry object
    if "content" in obj or "keys" in obj or "key" in obj:
        entry = WorldEntry.from_dict(_normalize_st_entry(obj))
        return WorldBook(id=new_uid(), name=default_name, entries=[entry])

    # our full store shape? take first book or wrap
    if "books" in obj and isinstance(obj["books"], dict) and obj["books"]:
        first = next(iter(obj["books"].values()))
        if isinstance(first, dict):
            return WorldBook.from_dict(first)

    raise ValueError("无法识别的世界书 JSON 结构，需要包含 entries 字段")


def import_from_text_block(text: str, *, default_name: str = "导入的世界书") -> WorldBook:
    """支持简易文本格式：

    # 条目名
    keys: a, b, c
    scenario: 咖啡馆
    behavior: 温柔慢节奏
    constant: false
    ---
    正文内容...

    多个条目用 === 分隔
    """
    text = text.strip()
    if not text:
        raise ValueError("导入内容为空")

    blocks = re.split(r"\n\s*===\s*\n", text)
    entries: list[WorldEntry] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        name = ""
        meta: dict[str, str] = {}
        body_lines: list[str] = []
        lines = block.splitlines()
        i = 0
        if lines and lines[0].startswith("#"):
            name = lines[0].lstrip("#").strip()
            i = 1
        content_started = False
        for line in lines[i:]:
            if not content_started and line.strip() == "---":
                content_started = True
                continue
            if not content_started:
                m = re.match(
                    r"^(keys|key|secondary|scenario|scenarios|behavior|behaviour|constant|priority|name)\s*[:=：]\s*(.*)$",
                    line.strip(),
                    re.I,
                )
                if m:
                    meta[m.group(1).lower()] = m.group(2).strip()
                    continue
                # bare content without ---
                content_started = True
                body_lines.append(line)
            else:
                body_lines.append(line)

        keys_raw = meta.get("keys") or meta.get("key") or ""
        secondary_raw = meta.get("secondary") or ""
        scenarios_raw = meta.get("scenarios") or meta.get("scenario") or ""
        constant = str(meta.get("constant", "false")).lower() in {
            "1",
            "true",
            "yes",
            "on",
            "是",
            "开启",
        }
        try:
            priority = int(meta.get("priority", "100"))
        except Exception:
            priority = 100
        entry = WorldEntry(
            uid=new_uid(),
            name=name or meta.get("name") or "",
            keys=[x.strip() for x in re.split(r"[,，|/]+", keys_raw) if x.strip()],
            # 文本格式里写了 secondary 就视为需要同时命中（selective）
            secondary_keys=[
                x.strip() for x in re.split(r"[,，|/]+", secondary_raw) if x.strip()
            ],
            selective=bool(secondary_raw.strip()),
            scenarios=[x.strip() for x in re.split(r"[,，|/]+", scenarios_raw) if x.strip()],
            behavior=meta.get("behavior") or meta.get("behaviour") or "",
            content="\n".join(body_lines).strip(),
            constant=constant,
            priority=priority,
        )
        if entry.content or entry.behavior:
            entries.append(entry)

    if not entries:
        raise ValueError("文本中未解析到有效条目")
    return WorldBook(id=new_uid(), name=default_name, entries=entries)


def import_worldbook(
    raw: str | dict | list,
    *,
    default_name: str = "导入的世界书",
) -> WorldBook:
    """统一导入入口：JSON 字符串 / 对象 / 简易文本。"""
    if isinstance(raw, (dict, list)):
        return import_from_json_obj(raw, default_name=default_name)

    text = str(raw or "").strip()
    if not text:
        raise ValueError("导入内容为空")

    obj = _try_parse_json(text)
    if obj is not None:
        return import_from_json_obj(obj, default_name=default_name)

    return import_from_text_block(text, default_name=default_name)
