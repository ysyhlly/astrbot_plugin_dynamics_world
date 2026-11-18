from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from .models import WorldBook, WorldEntry
from .settings import Settings, render_template


@dataclass
class MatchedEntry:
    book: WorldBook
    entry: WorldEntry
    reasons: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    matched: list[MatchedEntry]
    auto_scenario: str = ""  # 若根据关键词自动识别到场景
    scanned_text: str = ""

    @property
    def entries(self) -> list[WorldEntry]:
        return [m.entry for m in self.matched]


def _normalize(text: str, case_sensitive: bool) -> str:
    return text if case_sensitive else text.lower()


def _key_hit(haystack: str, key: str, *, case_sensitive: bool, whole_word: bool) -> bool:
    key = str(key or "").strip()
    if not key:
        return False
    if not case_sensitive:
        haystack_n = haystack.lower()
        key_n = key.lower()
    else:
        haystack_n = haystack
        key_n = key

    if whole_word:
        # Unicode-aware-ish word boundary for CJK + alnum
        pattern = rf"(?<![\w]){re.escape(key_n)}(?![\w])"
        flags = 0 if case_sensitive else re.IGNORECASE
        return re.search(pattern, haystack if case_sensitive else haystack, flags) is not None

    return key_n in haystack_n


def _entry_matches_text(entry: WorldEntry, text: str) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if entry.constant:
        reasons.append("constant")
        return True, reasons

    if not entry.keys and not entry.secondary_keys:
        return False, reasons

    primary_hit = False
    hit_keys: list[str] = []
    for key in entry.keys:
        if _key_hit(
            text,
            key,
            case_sensitive=entry.case_sensitive,
            whole_word=entry.match_whole_word,
        ):
            primary_hit = True
            hit_keys.append(key)

    if entry.keys and not primary_hit:
        return False, reasons

    # 有主关键词时只有 selective 才要求 secondary 命中（对齐酒馆语义）；
    # 没有主关键词时 secondary 是唯一入场券，否则条目会退化成常驻。
    if entry.secondary_keys and (entry.selective or not entry.keys):
        secondary_hit = False
        for key in entry.secondary_keys:
            if _key_hit(
                text,
                key,
                case_sensitive=entry.case_sensitive,
                whole_word=entry.match_whole_word,
            ):
                secondary_hit = True
                hit_keys.append(f"+{key}")
                break
        if not secondary_hit:
            return False, reasons

    if hit_keys:
        reasons.append("keys:" + ",".join(hit_keys[:6]))
    elif entry.constant:
        reasons.append("constant")
    return True, reasons


def _scenario_allows(entry: WorldEntry, active_scenario: str) -> bool:
    """条目 scenarios 为空=不限制；非空则需 active_scenario 命中其中之一。"""
    if not entry.scenarios:
        return True
    if not active_scenario:
        # 未设定场景时：允许关键词触发带场景的条目（用于自动进场景）
        # 但常驻带场景的条目不注入，避免污染
        if entry.constant:
            return False
        return True
    active = active_scenario.strip().lower()
    return any(s.strip().lower() == active for s in entry.scenarios)


def _default_style() -> Settings:
    """A style bag backed by no config at all: every default applies."""
    return Settings({})


def match_entries(
    books: Iterable[WorldBook],
    text: str,
    *,
    active_scenario: str = "",
    max_entries: int = 12,
    allow_auto_scenario: bool = True,
    dedupe_same_content: bool = True,
) -> MatchResult:
    """根据文本与当前场景匹配世界书条目。

    Args:
        books: 参与匹配的世界书（已按会话过滤）。
        text: 用于关键词匹配的扫描文本。
        active_scenario: 会话手动锁定的场景，非空时只放行该场景与通用条目。
        max_entries: 关键词条目上限；常驻条目始终全部注入。
        allow_auto_scenario: 是否允许按关键词命中投票自动识别场景。
        dedupe_same_content: 是否合并正文完全相同的条目（面板 matching 组可关）。

    Returns:
        含最终注入条目、自动识别场景与扫描文本的匹配结果。
    """
    text = str(text or "")
    active_scenario = str(active_scenario or "").strip()
    # 可能被传入生成器：先物化，自动场景补条目时还要再遍历一次
    book_list = [b for b in books if b is not None]
    candidates: list[MatchedEntry] = []
    auto_scenario_votes: dict[str, int] = {}

    for book in book_list:
        if not book.enabled:
            continue
        for entry in book.entries:
            if not entry.enabled:
                continue
            if not entry.content and not entry.behavior:
                continue
            if not _scenario_allows(entry, active_scenario):
                continue
            ok, reasons = _entry_matches_text(entry, text)
            if not ok:
                continue
            # 关键词命中且条目绑定场景 → 计票自动场景
            if (
                allow_auto_scenario
                and book.auto_scenario
                and entry.scenarios
                and not entry.constant
                and "keys:" in (reasons[0] if reasons else "")
            ):
                for s in entry.scenarios:
                    auto_scenario_votes[s] = auto_scenario_votes.get(s, 0) + max(
                        1, entry.priority // 10
                    )
            candidates.append(MatchedEntry(book=book, entry=entry, reasons=reasons))

    auto_scenario = ""
    if not active_scenario and auto_scenario_votes:
        auto_scenario = max(auto_scenario_votes.items(), key=lambda kv: kv[1])[0]
        # 自动场景确定后，把该场景的常驻条目并入候选。并入发生在截断之前，
        # 避免旧实现「先补入、再按 priority 重排并 [:max_entries]」把常驻截掉。
        candidates = _merge_scenario_constants(book_list, candidates, auto_scenario)

    return MatchResult(
        matched=_select_entries(
            candidates,
            max_entries=max_entries,
            dedupe_same_content=dedupe_same_content,
        ),
        auto_scenario=auto_scenario,
        scanned_text=text[:500],
    )


def _merge_scenario_constants(
    books: Iterable[WorldBook],
    candidates: list[MatchedEntry],
    scenario: str,
) -> list[MatchedEntry]:
    """把「绑定该场景的常驻条目」并入候选（仅当前未锁定场景时调用）。"""
    merged = list(candidates)
    known_uids = {m.entry.uid for m in merged}
    target = scenario.strip().lower()
    for book in books:
        if not book.enabled:
            continue
        for entry in book.entries:
            if not entry.enabled or not entry.constant or not entry.scenarios:
                continue
            if entry.uid in known_uids:
                continue
            if not entry.content and not entry.behavior:
                continue
            if any(s.strip().lower() == target for s in entry.scenarios):
                merged.append(
                    MatchedEntry(
                        book=book,
                        entry=entry,
                        reasons=["constant+auto_scenario"],
                    )
                )
                known_uids.add(entry.uid)
    return merged


def _select_entries(
    candidates: list[MatchedEntry],
    *,
    max_entries: int,
    dedupe_same_content: bool = True,
) -> list[MatchedEntry]:
    """去重并按「常驻全部保留 + 关键词按 priority 截断」生成最终注入顺序。

    Args:
        candidates: 关键词命中的候选条目。
        max_entries: 关键词条目上限。常驻条目永不被截断
            （_conf_schema.json 承诺「常驻条目始终注入」）。
        dedupe_same_content: 正文与行为都相同的条目只保留优先级最高的一条。

    Returns:
        按注入顺序排列的条目：先常驻，再关键词。
    """
    ordered = sorted(
        candidates,
        key=lambda m: (
            0 if m.entry.constant else 1,
            -m.entry.priority,
            m.entry.display_name(),
            m.entry.uid,
        ),
    )
    limit = max(1, int(max_entries))
    seen_content: set[str] = set()
    constants: list[MatchedEntry] = []
    others: list[MatchedEntry] = []
    for m in ordered:
        content_key = (m.entry.content or "").strip() + "||" + (m.entry.behavior or "").strip()
        if dedupe_same_content:
            if content_key in seen_content:
                continue
            seen_content.add(content_key)
        if m.entry.constant:
            constants.append(m)
        elif len(others) < limit:
            others.append(m)
    return constants + others


def build_injection_text(
    result: MatchResult,
    *,
    active_scenario: str = "",
    header: str | None = None,
    style: Settings | None = None,
) -> str:
    """将匹配结果渲染为可注入提示词。

    Args:
        result: match_entries 的匹配结果。
        active_scenario: 会话手动锁定的场景，优先于自动识别结果。
        header: 覆盖标题行；为 None 时用配置里的 inject_style.header。
        style: 注入文案样式。为 None 时使用全部默认文案。

    Returns:
        可直接追加到提示词的文本；没有命中条目时返回空串。
    """
    if not result.matched:
        return ""

    cfg = style or _default_style()
    scenario = active_scenario or result.auto_scenario
    lines: list[str] = []
    resolved_header = header if header is not None else cfg.inject_header
    if resolved_header:
        lines.append(resolved_header)
    if cfg.inject_preamble:
        lines.append(cfg.inject_preamble)
    if scenario and cfg.scenario_header:
        lines.append(render_template(cfg.scenario_header, scenario=scenario))
    lines.append("")

    for idx, m in enumerate(result.matched, 1):
        entry = m.entry
        title = render_template(
            cfg.entry_title_format,
            index=idx,
            title=entry.display_name(),
            book=m.book.name,
            uid=entry.uid,
        )
        if title:
            lines.append(title)
        if entry.scenarios and cfg.scenario_line_format:
            lines.append(
                render_template(
                    cfg.scenario_line_format,
                    scenarios=", ".join(entry.scenarios),
                    count=len(entry.scenarios),
                )
            )
        if entry.behavior and cfg.behavior_line_format:
            lines.append(render_template(cfg.behavior_line_format, behavior=entry.behavior))
        if entry.content:
            lines.append(entry.content.strip())
        lines.append(cfg.entry_separator)

    footer = cfg.footer_with_scenario if scenario else cfg.footer_without_scenario
    if footer:
        lines.append(render_template(footer, scenario=scenario))

    return "\n".join(lines).strip()
