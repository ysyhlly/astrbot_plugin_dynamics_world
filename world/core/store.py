from __future__ import annotations

import json
from copy import deepcopy
from astrbot.api import logger
import os
import threading
import time
from typing import Any

from .character import CharacterCard
from .models import (
    SESSION_CARD_NONE,
    SessionState,
    WorldBook,
    WorldEntry,
    WorldStore,
    new_uid,
)


# 调试预览每轮都在变，只保留状态展示需要的一小段（旧实现每个会话存 2000 字，
# 20 个会话就占了 store 文件的 76%）
PREVIEW_MAX = 600
# 会话数超限时剪掉「没有任何用户意图」的陈旧会话（webchat 每次访问都是新会话）
MAX_SESSIONS = 200
# record_match 的最小写盘间隔：连发消息时合并写入，避免每轮一次全量重写
SAVE_DEBOUNCE_SECONDS = 2.0


class WorldBookStore:
    """JSON 持久化世界书仓库。"""

    def __init__(self, data_file: str):
        self.data_file = data_file
        self._lock = threading.RLock()
        self._store = WorldStore()
        self._committed = deepcopy(self._store)
        self._dirty = False
        self._last_save = 0.0
        self.load()

    def load(self) -> None:
        with self._lock:
            try:
                os.stat(self.data_file)
            except FileNotFoundError:
                self._store = WorldStore()
                self._committed = deepcopy(self._store)
                self._dirty = False
                return
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("worldbook store must be an object")
                loaded = WorldStore.from_dict(data)
                self._store = loaded
                self._committed = deepcopy(loaded)
                self._dirty = False
                if self._migrate_loaded_locked():
                    # 旧数据里的超长预览只在这时清理一次，顺便把文件压小
                    self._write_locked()
            except Exception as e:
                # An unreadable existing file is not a new installation. Fail
                # initialization rather than overwrite it with an empty store.
                logger.error("worldbook: load failed type=%s", type(e).__name__)
                raise OSError("worldbook_load_failed; original file retained") from e

    def _migrate_loaded_locked(self) -> bool:
        """旧数据把 last_inject_preview 存到 2000 字，加载时压到 PREVIEW_MAX。"""
        changed = False
        for state in self._store.sessions.values():
            if len(state.last_inject_preview) > PREVIEW_MAX:
                state.last_inject_preview = state.last_inject_preview[:PREVIEW_MAX]
                changed = True
        return changed

    def save(self) -> None:
        """立即全量落盘（用户可见的改动走这里）。"""
        with self._lock:
            self._dirty = True
            self._write_locked()

    def _persist(self, *, force: bool) -> bool:
        """热路径写盘：没有变更直接跳过；force=False 时按防抖间隔合并写入。"""
        with self._lock:
            if not self._dirty:
                return False
            if not force and (time.monotonic() - self._last_save) < SAVE_DEBOUNCE_SECONDS:
                return False
            return self._write_locked()

    def _write_locked(self) -> bool:
        try:
            self._prune_sessions_locked()
            os.makedirs(os.path.dirname(self.data_file) or ".", exist_ok=True)
            tmp = self.data_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._store.to_dict(), f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.data_file)
        except Exception as e:
            self._store = deepcopy(self._committed)
            self._dirty = False
            logger.error("worldbook: save failed type=%s", type(e).__name__)
            raise OSError("worldbook_save_failed; changes were not saved") from e
        self._committed = deepcopy(self._store)
        self._dirty = False
        self._last_save = time.monotonic()
        return True

    def _prune_sessions_locked(self) -> int:
        """会话数超限时剪枝，且只剪「没有任何用户意图」的会话。"""
        sessions = self._store.sessions
        if len(sessions) <= MAX_SESSIONS:
            return 0
        idle = [
            (state.last_active, sid)
            for sid, state in sessions.items()
            if not state.scenario
            and not state.scenario_auto
            and not state.book_ids
            and not state.card_id
            and state.enabled
        ]
        idle.sort()
        removed = 0
        for _, sid in idle[: max(0, len(sessions) - MAX_SESSIONS)]:
            sessions.pop(sid, None)
            removed += 1
        if removed:
            logger.info("worldbook: pruned %d idle session(s)", removed)
        return removed

    # ---- books ----

    def list_books(self) -> list[WorldBook]:
        with self._lock:
            return sorted(self._store.books.values(), key=lambda b: (not b.enabled, b.name))

    def get_book(self, book_id: str) -> WorldBook | None:
        with self._lock:
            return self._store.books.get(str(book_id or "").strip())

    def find_book_by_name(self, name: str) -> WorldBook | None:
        name = str(name or "").strip().lower()
        if not name:
            return None
        with self._lock:
            for book in self._store.books.values():
                if book.name.lower() == name or book.id.lower() == name:
                    return book
            for book in self._store.books.values():
                if name in book.name.lower():
                    return book
        return None

    def upsert_book(self, book: WorldBook) -> WorldBook:
        with self._lock:
            if not book.id:
                book.id = new_uid()
            book.touch()
            self._store.books[book.id] = book
            self.save()
            return book

    def delete_book(self, book_id: str) -> bool:
        book_id = str(book_id or "").strip()
        with self._lock:
            if book_id not in self._store.books:
                return False
            del self._store.books[book_id]
            self._store.active_book_ids = [
                x for x in self._store.active_book_ids if x != book_id
            ]
            self.save()
            return True

    def set_book_enabled(self, book_id: str, enabled: bool) -> WorldBook | None:
        with self._lock:
            book = self._store.books.get(book_id)
            if not book:
                return None
            book.enabled = enabled
            book.touch()
            self.save()
            return book

    def add_entry(self, book_id: str, entry: WorldEntry) -> WorldEntry | None:
        with self._lock:
            book = self._store.books.get(book_id)
            if not book:
                return None
            if not entry.uid:
                entry.uid = new_uid()
            # replace if same uid
            book.entries = [e for e in book.entries if e.uid != entry.uid]
            book.entries.append(entry)
            book.touch()
            self.save()
            return entry

    def remove_entry(self, book_id: str, entry_uid: str) -> bool:
        with self._lock:
            book = self._store.books.get(book_id)
            if not book:
                return False
            ok = book.remove_entry(entry_uid)
            if ok:
                self.save()
            return ok

    # ---- sessions ----

    def get_session(self, session_id: str) -> SessionState:
        session_id = str(session_id or "").strip() or "default"
        with self._lock:
            state = self._store.sessions.get(session_id)
            if state is None:
                state = SessionState()
                self._store.sessions[session_id] = state
            return state

    def snapshot_context_inputs(
        self, session_id: str
    ) -> tuple[SessionState, CharacterCard | None, list[WorldBook]]:
        """Copy the effective character and books without recording a read.

        Args:
            session_id: Full AstrBot unified message origin.

        Returns:
            Detached session, character, and active book snapshots. An explicit
            missing character binding does not fall back to the global card.
        """
        session_id = str(session_id or "").strip()
        with self._lock:
            saved = self._store.sessions.get(session_id)
            state = SessionState.from_dict(saved.to_dict()) if saved else SessionState()
            card_id = state.card_id or self._store.default_card_id
            raw_card = (
                self._store.cards.get(card_id)
                if card_id != SESSION_CARD_NONE
                else None
            )
            card = CharacterCard.from_dict(deepcopy(raw_card)) if raw_card else None
            book_ids = state.book_ids or self._store.active_book_ids
            books = (
                [self._store.books[bid] for bid in book_ids if bid in self._store.books]
                if book_ids
                else list(self._store.books.values())
            )
            return state, card, [
                WorldBook.from_dict(book.to_dict()) for book in books if book.enabled
            ]

    def snapshot_global_character_inputs(
        self, persona_id: str
    ) -> tuple[SessionState, CharacterCard | None, list[WorldBook]]:
        """Read one character and its own linked world, excluding session state."""
        persona_id = str(persona_id or "").strip()
        with self._lock:
            candidates = [
                raw for cid, raw in self._store.cards.items()
                if str(raw.get("persona_id") or f"wb_{cid}") == persona_id
            ] if persona_id else []
            if len(candidates) != 1:
                return SessionState(), None, []
            card = CharacterCard.from_dict(deepcopy(candidates[0]))
            book = self._store.books.get(card.linked_book_id)
            books = [WorldBook.from_dict(book.to_dict())] if book and book.enabled else []
            return SessionState(), card, books

    def update_session(self, session_id: str, **kwargs: Any) -> SessionState:
        session_id = str(session_id or "").strip() or "default"
        with self._lock:
            state = self._store.sessions.get(session_id)
            if state is None:
                state = SessionState()
                self._store.sessions[session_id] = state
            for key, value in kwargs.items():
                if hasattr(state, key):
                    setattr(state, key, value)
            state.last_active = int(time.time())
            self.save()
            return state

    def set_scenario(self, session_id: str, scenario: str) -> SessionState:
        return self.update_session(session_id, scenario=str(scenario or "").strip())

    def clear_scenario(self, session_id: str) -> SessionState:
        return self.update_session(session_id, scenario="")

    def get_active_books_for_session(self, session_id: str) -> list[WorldBook]:
        with self._lock:
            state = self.get_session(session_id)
            if state.book_ids:
                books = [
                    self._store.books[bid]
                    for bid in state.book_ids
                    if bid in self._store.books and self._store.books[bid].enabled
                ]
                return books
            if self._store.active_book_ids:
                books = [
                    self._store.books[bid]
                    for bid in self._store.active_book_ids
                    if bid in self._store.books and self._store.books[bid].enabled
                ]
                return books
            return [b for b in self._store.books.values() if b.enabled]

    def set_global_active_books(self, book_ids: list[str]) -> None:
        with self._lock:
            self._store.active_book_ids = [str(x).strip() for x in book_ids if str(x).strip()]
            self.save()

    def record_match(
        self,
        session_id: str,
        matched_uids: list[str],
        preview: str,
        scenario: str | None = None,
        scenario_auto: str | None = None,
    ) -> bool:
        """记录本轮命中（每轮请求都会调用）。

        - 内容与上次完全一致时不产生任何写盘；
        - 变了也按 SAVE_DEBOUNCE_SECONDS 合并写入，避免连发消息时反复全量重写。
        返回是否产生了新的持久化改动。
        """
        session_id = str(session_id or "").strip() or "default"
        preview = str(preview or "")[:PREVIEW_MAX]
        matched = [str(x) for x in (matched_uids or [])]
        with self._lock:
            state = self._store.sessions.get(session_id)
            if state is None:
                state = SessionState()
                self._store.sessions[session_id] = state
            state.last_active = int(time.time())
            changed = (
                state.last_matched != matched
                or state.last_inject_preview != preview
                or (scenario is not None and state.scenario != scenario)
                or (scenario_auto is not None and state.scenario_auto != scenario_auto)
            )
            if not changed:
                # 内容没变：不产生新改动，但把上一次被防抖推迟的写入补上
                self._persist(force=False)
                return False
            state.last_matched = matched
            state.last_inject_preview = preview
            if scenario is not None:
                state.scenario = str(scenario)
            if scenario_auto is not None:
                state.scenario_auto = str(scenario_auto)
            self._dirty = True
            self._persist(force=False)
            return True

    # ---- character cards ----

    def list_cards(self) -> list[CharacterCard]:
        with self._lock:
            cards = [CharacterCard.from_dict(d) for d in self._store.cards.values()]
            return sorted(cards, key=lambda c: c.name)

    def get_card(self, card_id: str) -> CharacterCard | None:
        card_id = str(card_id or "").strip()
        with self._lock:
            raw = self._store.cards.get(card_id)
            return CharacterCard.from_dict(raw) if raw else None

    def find_card_by_name(self, name: str) -> CharacterCard | None:
        name = str(name or "").strip().lower()
        if not name:
            return None
        with self._lock:
            cards = [CharacterCard.from_dict(d) for d in self._store.cards.values()]
            for c in cards:
                if c.name.lower() == name or c.id.lower() == name:
                    return c
            for c in cards:
                if name in c.name.lower():
                    return c
        return None

    def upsert_card(self, card: CharacterCard) -> CharacterCard:
        with self._lock:
            if not card.id:
                card.id = new_uid()
            card.touch()
            self._store.cards[card.id] = card.to_dict()
            self.save()
            return card

    def delete_card(self, card_id: str) -> bool:
        card_id = str(card_id or "").strip()
        with self._lock:
            if card_id not in self._store.cards:
                return False
            del self._store.cards[card_id]
            if self._store.default_card_id == card_id:
                self._store.default_card_id = ""
            for sid, state in self._store.sessions.items():
                if state.card_id == card_id:
                    state.card_id = ""
            self.save()
            return True

    def set_default_card(self, card_id: str) -> None:
        with self._lock:
            self._store.default_card_id = str(card_id or "").strip()
            self.save()

    def get_default_card_id(self) -> str:
        with self._lock:
            return str(self._store.default_card_id or "").strip()

    def resolve_session_card(self, session_id: str) -> CharacterCard | None:
        """解析会话最终角色卡：显式绑定 > 全局默认；__none__ 表示关闭。"""
        with self._lock:
            state = self.get_session(session_id)
            cid = str(state.card_id or "").strip()
            if cid == SESSION_CARD_NONE:
                return None
            if not cid:
                cid = str(self._store.default_card_id or "").strip()
            if not cid:
                return None
            raw = self._store.cards.get(cid)
            return CharacterCard.from_dict(raw) if raw else None
