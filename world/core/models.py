from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any


def new_uid() -> str:
    return uuid.uuid4().hex[:12]


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        # allow comma / newline / | separators for convenience
        parts: list[str] = []
        for chunk in text.replace("|", "\n").replace("，", ",").split("\n"):
            for item in chunk.split(","):
                cleaned = item.strip()
                if cleaned:
                    parts.append(cleaned)
        return parts
    if isinstance(value, (list, tuple, set)):
        result: list[str] = []
        for item in value:
            text = str(item or "").strip()
            if text:
                result.append(text)
        return result
    text = str(value).strip()
    return [text] if text else []


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "enable", "enabled", "开启", "启用", "是"}:
        return True
    if text in {"0", "false", "no", "off", "disable", "disabled", "关闭", "停用", "否"}:
        return False
    return default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


@dataclass
class WorldEntry:
    """一条世界书条目。"""

    uid: str = field(default_factory=new_uid)
    name: str = ""
    keys: list[str] = field(default_factory=list)
    secondary_keys: list[str] = field(default_factory=list)
    content: str = ""
    # 绑定场景：空表示任意场景都可匹配；非空则仅在对应场景激活时注入
    scenarios: list[str] = field(default_factory=list)
    # 行为指引：额外强调该场景下角色应如何变化（会拼进注入块）
    behavior: str = ""
    constant: bool = False  # 常驻：不依赖关键词，只要场景匹配就注入
    enabled: bool = True
    priority: int = 100  # 越大越优先
    case_sensitive: bool = False
    match_whole_word: bool = False
    # selective: 有 secondary_keys 时需同时命中至少一个 secondary
    selective: bool = False
    comment: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> WorldEntry:
        raw = data if isinstance(data, dict) else {}
        keys = raw.get("keys", raw.get("key", []))
        secondary = raw.get("secondary_keys", raw.get("keysecondary", raw.get("secondary", [])))
        scenarios = raw.get("scenarios", raw.get("scenario", []))
        name = str(raw.get("name") or raw.get("comment") or raw.get("title") or "").strip()
        return cls(
            uid=str(raw.get("uid") or raw.get("id") or new_uid()),
            name=name,
            keys=_as_str_list(keys),
            secondary_keys=_as_str_list(secondary),
            content=str(raw.get("content") or raw.get("text") or "").strip(),
            scenarios=_as_str_list(scenarios),
            behavior=str(raw.get("behavior") or raw.get("behaviour") or "").strip(),
            constant=_as_bool(raw.get("constant", False), False),
            enabled=(
                not _as_bool(raw.get("disable"), False)
                if "enabled" not in raw and "disable" in raw
                else _as_bool(raw.get("enabled", True), True)
            ),
            priority=_as_int(
                raw.get(
                    "priority",
                    raw.get("order", raw.get("insertion_order", 100)),
                ),
                100,
            ),
            case_sensitive=_as_bool(raw.get("case_sensitive", False), False),
            match_whole_word=_as_bool(raw.get("match_whole_word", False), False),
            # 酒馆语义：selective=false 时忽略 keysecondary，不能强制打开
            selective=_as_bool(raw.get("selective", False), False),
            comment=str(raw.get("comment") or "").strip(),
        )

    def display_name(self) -> str:
        if self.name:
            return self.name
        if self.keys:
            return "/".join(self.keys[:3])
        return self.uid


@dataclass
class WorldBook:
    """一本世界书。"""

    id: str = field(default_factory=new_uid)
    name: str = "未命名世界书"
    description: str = ""
    enabled: bool = True
    entries: list[WorldEntry] = field(default_factory=list)
    # 自动场景：当关键词命中绑定场景的条目时，是否自动切换会话场景
    auto_scenario: bool = True
    created_at: int = field(default_factory=lambda: int(time.time()))
    updated_at: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "enabled": self.enabled,
            "entries": [e.to_dict() for e in self.entries],
            "auto_scenario": self.auto_scenario,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> WorldBook:
        raw = data if isinstance(data, dict) else {}
        entries_raw = raw.get("entries", [])
        entries: list[WorldEntry] = []
        if isinstance(entries_raw, dict):
            # SillyTavern: entries as object map
            for key, value in entries_raw.items():
                if isinstance(value, dict):
                    entry = WorldEntry.from_dict(value)
                    # 只有条目本身没有 uid/id 时才回退到 map 的 key。
                    # 旧写法 `entry.uid == new_uid()` 是跟刚生成的随机值比较，恒为 False。
                    if not str(value.get("uid") or value.get("id") or "").strip():
                        entry.uid = str(key)
                    entries.append(entry)
        elif isinstance(entries_raw, list):
            for item in entries_raw:
                if isinstance(item, dict):
                    entries.append(WorldEntry.from_dict(item))
        return cls(
            id=str(raw.get("id") or new_uid()),
            name=str(raw.get("name") or raw.get("title") or "未命名世界书").strip()
            or "未命名世界书",
            description=str(raw.get("description") or raw.get("desc") or "").strip(),
            enabled=_as_bool(raw.get("enabled", True), True),
            entries=entries,
            auto_scenario=_as_bool(raw.get("auto_scenario", True), True),
            created_at=_as_int(raw.get("created_at"), int(time.time())),
            updated_at=_as_int(raw.get("updated_at"), int(time.time())),
        )

    def touch(self) -> None:
        self.updated_at = int(time.time())

    def get_entry(self, uid: str) -> WorldEntry | None:
        uid = str(uid or "").strip()
        for entry in self.entries:
            if entry.uid == uid:
                return entry
        return None

    def remove_entry(self, uid: str) -> bool:
        uid = str(uid or "").strip()
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.uid != uid]
        if len(self.entries) != before:
            self.touch()
            return True
        return False

    def list_scenarios(self) -> list[str]:
        names: set[str] = set()
        for entry in self.entries:
            for s in entry.scenarios:
                names.add(s)
        return sorted(names)


@dataclass
class SessionState:
    """会话级世界书状态。"""

    scenario: str = ""  # 手动锁定的场景：非空时优先，且不再自动切换
    # 最近一次自动识别到的场景：每轮重新投票，只用于渲染/展示，不锁死会话
    scenario_auto: str = ""
    book_ids: list[str] = field(default_factory=list)  # 空=使用全部已启用书
    enabled: bool = True
    last_matched: list[str] = field(default_factory=list)  # entry uids
    last_inject_preview: str = ""
    # 空=使用全局默认角色卡；"__none__"=明确关闭；其它=具体 card id
    card_id: str = ""
    inject_card_prompt: bool = True  # 是否在 on_llm_request 中注入角色卡提示
    last_active: int = 0  # 最近活动时间（剪枝陈旧会话用）

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> SessionState:
        raw = data if isinstance(data, dict) else {}
        return cls(
            scenario=str(raw.get("scenario") or "").strip(),
            scenario_auto=str(raw.get("scenario_auto") or "").strip(),
            book_ids=_as_str_list(raw.get("book_ids")),
            enabled=_as_bool(raw.get("enabled", True), True),
            last_matched=_as_str_list(raw.get("last_matched")),
            last_inject_preview=str(raw.get("last_inject_preview") or ""),
            card_id=str(raw.get("card_id") or "").strip(),
            inject_card_prompt=_as_bool(raw.get("inject_card_prompt", True), True),
            last_active=_as_int(raw.get("last_active"), 0),
        )


# 会话明确关闭角色卡
SESSION_CARD_NONE = "__none__"


@dataclass
class WorldStore:
    books: dict[str, WorldBook] = field(default_factory=dict)
    sessions: dict[str, SessionState] = field(default_factory=dict)
    # 全局默认启用的书 id 列表；空表示全部 enabled 的书
    active_book_ids: list[str] = field(default_factory=list)
    # 角色卡 id -> raw dict（由 CharacterCard.to_dict 序列化）
    cards: dict[str, dict[str, Any]] = field(default_factory=dict)
    # 全局默认角色卡 id（会话未指定时使用）
    default_card_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "books": {bid: book.to_dict() for bid, book in self.books.items()},
            "sessions": {sid: state.to_dict() for sid, state in self.sessions.items()},
            "active_book_ids": list(self.active_book_ids),
            "cards": dict(self.cards),
            "default_card_id": self.default_card_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> WorldStore:
        raw = data if isinstance(data, dict) else {}
        books: dict[str, WorldBook] = {}
        books_raw = raw.get("books", {})
        if isinstance(books_raw, dict):
            for bid, bdata in books_raw.items():
                if isinstance(bdata, dict):
                    book = WorldBook.from_dict(bdata)
                    if not book.id:
                        book.id = str(bid)
                    books[book.id] = book
        sessions: dict[str, SessionState] = {}
        sessions_raw = raw.get("sessions", {})
        if isinstance(sessions_raw, dict):
            for sid, sdata in sessions_raw.items():
                sessions[str(sid)] = SessionState.from_dict(
                    sdata if isinstance(sdata, dict) else {}
                )
        cards: dict[str, dict[str, Any]] = {}
        cards_raw = raw.get("cards", {})
        if isinstance(cards_raw, dict):
            for cid, cdata in cards_raw.items():
                if isinstance(cdata, dict):
                    cards[str(cid)] = cdata
        return cls(
            books=books,
            sessions=sessions,
            active_book_ids=_as_str_list(raw.get("active_book_ids")),
            cards=cards,
            default_card_id=str(raw.get("default_card_id") or "").strip(),
        )
