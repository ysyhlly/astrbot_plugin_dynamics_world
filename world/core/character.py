from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .models import WorldBook, new_uid, _as_bool, _as_int, _as_str_list
from .importer import import_worldbook


def _s(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _group_addendum(raw: dict[str, Any]) -> str:
    """读取群聊适配层文本：优先顶层字段，其次 Tavern extensions。"""
    direct = raw.get("group_addendum")
    if direct:
        return _s(direct)
    ext = raw.get("extensions")
    if isinstance(ext, dict):
        bucket = ext.get("astrbot_worldbook")
        if isinstance(bucket, dict):
            return _s(bucket.get("group_addendum"))
    return ""


# AstrBot UMO 形如 <平台>:GroupMessage:<群号>
GROUP_SESSION_MARKERS = ("groupmessage", "group_message", "guildmessage")


def is_group_session(session_id: str) -> bool:
    """会话是否为群聊。"""
    text = str(session_id or "").strip().lower()
    parts = text.split(":", 2)
    return len(parts) == 3 and bool(parts[0]) and parts[1] in GROUP_SESSION_MARKERS and bool(parts[2])


@dataclass
class CharacterCard:
    """角色卡（兼容 SillyTavern V1/V2 核心字段）。"""

    id: str = field(default_factory=new_uid)
    name: str = "未命名角色"
    description: str = ""
    personality: str = ""
    scenario: str = ""
    first_mes: str = ""
    mes_example: str = ""
    system_prompt: str = ""
    post_history_instructions: str = ""
    creator_notes: str = ""
    tags: list[str] = field(default_factory=list)
    alternate_greetings: list[str] = field(default_factory=list)
    # 群聊适配层：仅群聊会话注入的额外规则，不并入 personality
    group_addendum: str = ""
    # 关联世界书 id（插件内）；导入 character_book 时自动建书
    linked_book_id: str = ""
    # 同步到 AstrBot 人格后的 persona_id
    persona_id: str = ""
    source: str = ""  # tavern_v2 / tavern_v1 / plugin
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))
    # 原始 character_book 快照（可选）
    character_book_raw: dict[str, Any] | None = None

    def touch(self) -> None:
        self.updated_at = int(time.time())

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "CharacterCard":
        raw = data if isinstance(data, dict) else {}
        return cls(
            id=_s(raw.get("id")) or new_uid(),
            name=_s(raw.get("name"), "未命名角色") or "未命名角色",
            description=_s(raw.get("description")),
            personality=_s(raw.get("personality")),
            scenario=_s(raw.get("scenario")),
            first_mes=_s(raw.get("first_mes") or raw.get("first_message")),
            mes_example=_s(raw.get("mes_example") or raw.get("example_dialogue")),
            system_prompt=_s(raw.get("system_prompt")),
            post_history_instructions=_s(
                raw.get("post_history_instructions") or raw.get("post_history")
            ),
            creator_notes=_s(raw.get("creator_notes") or raw.get("creatorcomment")),
            tags=_as_str_list(raw.get("tags")),
            alternate_greetings=_as_str_list(raw.get("alternate_greetings")),
            group_addendum=_group_addendum(raw),
            linked_book_id=_s(raw.get("linked_book_id")),
            persona_id=_s(raw.get("persona_id")),
            source=_s(raw.get("source"), "plugin") or "plugin",
            created_at=_as_int(raw.get("created_at"), int(time.time())),
            updated_at=_as_int(raw.get("updated_at"), int(time.time())),
            character_book_raw=raw.get("character_book_raw")
            if isinstance(raw.get("character_book_raw"), dict)
            else (
                raw.get("character_book")
                if isinstance(raw.get("character_book"), dict)
                else None
            ),
        )

    def build_system_prompt(
        self,
        *,
        include_world_hint: bool = True,
        include_group_addendum: bool = False,
    ) -> str:
        """拼装可注入的系统提示词 / AstrBot 人格 prompt。"""
        parts: list[str] = []
        if self.system_prompt:
            parts.append(self.system_prompt.strip())
        else:
            parts.append(
                f"你正在扮演「{self.name}」。请完全以该角色身份对话，保持口吻、用词与行为一致。"
                "不要跳出角色，不要以 AI 助手自称。"
            )

        if self.description:
            parts.append(f"【角色描述】\n{self.description.strip()}")
        if self.personality:
            parts.append(f"【性格】\n{self.personality.strip()}")
        if self.scenario:
            parts.append(f"【场景】\n{self.scenario.strip()}")
        if include_group_addendum and self.group_addendum:
            parts.append(
                "【群聊适配层 · 仅群聊生效】\n" + self.group_addendum.strip()
            )
        if self.post_history_instructions:
            parts.append(f"【输出要求】\n{self.post_history_instructions.strip()}")
        if include_world_hint:
            parts.append(
                "【世界书】若上下文中出现「世界书 / World Info」条目，请将其视为当前世界的事实设定，"
                "并自然体现在言行中；不要生硬背诵条目原文。"
            )
        return "\n\n".join(p for p in parts if p).strip()

    def build_begin_dialogs(self) -> list[str]:
        """AstrBot begin_dialogs：偶数条 user/assistant 交替。"""
        dialogs: list[str] = []
        if self.mes_example:
            dialogs.extend(_parse_mes_example(self.mes_example, self.name))
        # first_mes 作为助手开场：补一条用户钩子
        if self.first_mes:
            # 若示例已够长，仍把 first_mes 作为可选开场放最后一对
            dialogs.append("……")
            dialogs.append(self.first_mes.strip())
        # 保证偶数
        if len(dialogs) % 2 == 1:
            dialogs = dialogs[:-1]
        return dialogs

    def to_tavern_v2(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "personality": self.personality,
            "scenario": self.scenario,
            "first_mes": self.first_mes,
            "mes_example": self.mes_example,
            "creator_notes": self.creator_notes,
            "system_prompt": self.system_prompt,
            "post_history_instructions": self.post_history_instructions,
            "tags": list(self.tags),
            "creator": "astrbot_plugin_worldbook",
            "character_version": "1.0",
            "alternate_greetings": list(self.alternate_greetings),
            "extensions": (
                {"astrbot_worldbook": {"group_addendum": self.group_addendum}}
                if self.group_addendum
                else {}
            ),
        }
        if self.character_book_raw:
            data["character_book"] = self.character_book_raw
        return {
            "spec": "chara_card_v2",
            "spec_version": "2.0",
            "data": data,
        }


def _parse_mes_example(text: str, char_name: str) -> list[str]:
    """解析 ST 风格 mes_example 为 user/assistant 交替列表。"""
    text = text.strip()
    # SillyTavern 的 <START> 只作轮次分隔标记：解析前去掉，避免混进对白
    text = re.sub(r"(?im)^[ \t]*<START>[ \t]*$", "", text).replace("<START>", "").strip()
    if not text:
        return []
    # 常见：{{user}}: / {{char}}: 或 User: / Char:
    pattern = re.compile(
        r"(?:\{\{user\}\}|User|用户)\s*[:：]\s*(.*?)\s*(?=(?:\{\{char\}\}|Char|助理|角色|"
        + re.escape(char_name)
        + r")\s*[:：]|$)",
        re.I | re.S,
    )
    pattern_char = re.compile(
        r"(?:\{\{char\}\}|Char|助理|角色|"
        + re.escape(char_name)
        + r")\s*[:：]\s*(.*?)\s*(?=(?:\{\{user\}\}|User|用户)\s*[:：]|$)",
        re.I | re.S,
    )
    users = [m.group(1).strip() for m in pattern.finditer(text) if m.group(1).strip()]
    chars = [m.group(1).strip() for m in pattern_char.finditer(text) if m.group(1).strip()]
    dialogs: list[str] = []
    for i in range(min(len(users), len(chars))):
        dialogs.append(users[i])
        dialogs.append(chars[i])
    if dialogs:
        return dialogs
    # fallback: 按空行切两两配对
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    for i in range(0, len(blocks) - 1, 2):
        dialogs.append(blocks[i])
        dialogs.append(blocks[i + 1])
    return dialogs


def import_character_card(raw: str | dict, *, default_name: str = "") -> CharacterCard:
    """导入酒馆 V1/V2 JSON 或本插件卡片。"""
    if isinstance(raw, str):
        text = raw.strip()
        fence = re.match(r"^```(?:json|JSON)?\s*([\s\S]*?)\s*```$", text)
        if fence:
            text = fence.group(1).strip()
        try:
            obj = json.loads(text)
        except Exception:
            # 尝试截取对象
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                obj = json.loads(text[start : end + 1])
            else:
                raise ValueError("角色卡 JSON 解析失败")
    else:
        obj = raw

    if not isinstance(obj, dict):
        raise ValueError("角色卡根节点必须是对象")

    # V2
    if obj.get("spec") == "chara_card_v2" or (
        isinstance(obj.get("data"), dict) and obj.get("spec_version")
    ):
        data = obj.get("data") if isinstance(obj.get("data"), dict) else {}
        card = CharacterCard.from_dict(data)
        card.source = "tavern_v2"
        if default_name and (not card.name or card.name == "未命名角色"):
            card.name = default_name
        if isinstance(data.get("character_book"), dict):
            card.character_book_raw = data["character_book"]
        return card

    # V1 flat
    if any(k in obj for k in ("first_mes", "description", "personality", "mes_example")):
        card = CharacterCard.from_dict(obj)
        card.source = "tavern_v1"
        if default_name and (not card.name or card.name == "未命名角色"):
            card.name = default_name
        if isinstance(obj.get("character_book"), dict):
            card.character_book_raw = obj["character_book"]
        return card

    # 本插件完整卡片
    if "name" in obj and ("system_prompt" in obj or "description" in obj):
        card = CharacterCard.from_dict(obj)
        card.source = _s(obj.get("source"), "plugin") or "plugin"
        return card

    raise ValueError("无法识别的角色卡格式（需要 SillyTavern V1/V2 或本插件格式）")


def character_book_to_worldbook(card: CharacterCard) -> WorldBook | None:
    """将角色卡内嵌 character_book 转为插件世界书。"""
    if not card.character_book_raw:
        return None
    try:
        return import_worldbook(
            {
                "name": f"{card.name}·角色书",
                "description": f"来自角色卡「{card.name}」的 character_book",
                "entries": card.character_book_raw.get("entries", card.character_book_raw),
            },
            default_name=f"{card.name}·角色书",
        )
    except Exception:
        return None


def slug_persona_id(name: str) -> str:
    """生成相对稳定的 persona_id（优先 ASCII，避免部分环境中文 ID 异常）。"""
    aliases = {
        "夏目安安": "natsuume_anan",
        "安安": "natsuume_anan",
        "魔法少女的魔女审判": "mocai",
    }
    name = str(name or "").strip()
    if name in aliases:
        return f"wb_{aliases[name]}"
    # 去掉非 ascii 词，保留字母数字下划线
    ascii_part = re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_").lower()
    if ascii_part:
        base = ascii_part[:40]
    else:
        base = new_uid()[:10]
    return f"wb_{base}"
