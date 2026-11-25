"""Tests for Dynamics World v2.0 series capability hooks, journal_feed, and UI contracts."""

from __future__ import annotations

import asyncio
import re
import time
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from test_world_integration import UMO, make_plugin, seed

from astrbot_plugin_dynamics_world import series_panels
from astrbot_plugin_dynamics_world.life.core.narrative import _identity
from astrbot_plugin_dynamics_world.world.core import web_api as wb_api


@pytest.mark.asyncio
async def test_series_summary_and_scope_status_standalone(tmp_path, monkeypatch):
    plugin, entries, _ = await make_plugin(tmp_path, monkeypatch)
    try:
        seed(plugin)
        # Edit mode (runtime_enabled=False)
        s_edit = plugin.get_series_summary()
        assert s_edit["badge"]["tone"] == "muted"
        assert s_edit["badge"]["count"] == 0
        assert "编辑模式" in s_edit["badge"]["label"]
        assert s_edit["pulse"]["updated_at"]

        # Ready mode
        plugin.config["runtime_enabled"] = True
        s_ready = plugin.get_series_summary()
        assert s_ready["badge"]["tone"] in {"accent", "warm"}
        assert isinstance(s_ready["badge"]["count"], int)
        assert s_ready["pulse"]["headline"]

        # Scope status (bound vs unbound)
        st_bound = plugin.get_series_scope_status(UMO)
        assert st_bound["enabled"] is True
        assert st_bound["persona_id"] == "p"
        assert st_bound["supported"] is False
        assert "version" in st_bound

        st_other = plugin.get_series_scope_status("qq:GroupMessage:unbound")
        assert st_other["enabled"] is False

        plugin.world.store.update_session(UMO, card_id="__none__")
        st_unlinked = plugin.get_series_scope_status(UMO)
        assert st_unlinked["enabled"] is False
        assert "解绑" in st_unlinked["summary"]

        # Legacy conflict raises danger badge
        entries.append(
            NS(name="astrbot_plugin_worldbook", activated=True, star_cls=object())
        )
        s_conflict = plugin.get_series_summary()
        assert s_conflict["badge"]["tone"] == "danger"
        assert s_conflict["badge"]["count"] == 1
    finally:
        await plugin.terminate()


@pytest.mark.asyncio
async def test_series_search_items_matches_cards_books_entries_and_diary(
    tmp_path, monkeypatch
):
    plugin, _, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    try:
        seed(plugin)
        assert plugin.series_search_items("", UMO, 8) == []

        hits_card = plugin.series_search_items("角色", UMO, 8)
        assert any(
            item["kind"] == "character_card"
            and item["plugin_id"] == "astrbot_plugin_dynamics_world"
            and item["page"] == "world"
            and item["deep_link"]["view"] == "cards"
            for item in hits_card
        )

        hits_book = plugin.series_search_items("海边", UMO, 8)
        assert any(item["kind"] == "worldbook" for item in hits_book)
        assert any(item["kind"] == "worldbook_entry" for item in hits_book)

        # Limit honored
        assert len(plugin.series_search_items("海边", UMO, 1)) == 1
    finally:
        await plugin.terminate()


def test_series_panels_presence_v2_badge_pulse_ttl_and_isolation(tmp_path):
    series_panels.invalidate_summary_cache()
    calls = {"learning": 0}

    class LearningOwner:
        def get_dynamics_capabilities(self):
            return {"schema_version": 1, "ready": True, "enabled": True}

        def get_series_summary(self):
            calls["learning"] += 1
            return {
                "badge": {"count": 3, "tone": "warm", "label": "3 项待审"},
                "pulse": {
                    "headline": "今日已审查 12 条",
                    "updated_at": "2026-11-21T02:00:00+08:00",
                },
            }

    class BrokenOwner:
        def get_dynamics_capabilities(self):
            return {"schema_version": 1, "ready": True, "enabled": True}

        def get_series_summary(self):
            raise RuntimeError("boom")

    class LegacyOwner:
        def get_dynamics_capabilities(self):
            return {"schema_version": 1, "ready": True, "enabled": True}

    entries = [
        NS(name="astrbot_plugin_dynamics_learning", activated=True, star_cls=LearningOwner()),
        NS(name="astrbot_plugin_dynamics_horizons", activated=True, star_cls=BrokenOwner()),
        NS(name="astrbot_plugin_dynamics_memory", activated=True, star_cls=LegacyOwner()),
    ]
    ctx = NS(get_all_stars=lambda: entries)

    first = series_panels.presence(ctx, "astrbot_plugin_dynamics_world", root=tmp_path)
    by_id = {p["id"]: p for p in first["plugins"]}

    assert by_id["astrbot_plugin_chat_dynamics"]["label"] == "对话主控"
    assert by_id["astrbot_plugin_group_chronicle"]["label"] == "群文化沿革"

    assert by_id["astrbot_plugin_dynamics_learning"]["badge"] == {
        "count": 3,
        "tone": "warm",
        "label": "3 项待审",
    }
    assert by_id["astrbot_plugin_dynamics_learning"]["pulse"]["headline"] == "今日已审查 12 条"
    assert by_id["astrbot_plugin_dynamics_horizons"]["badge"] is None
    assert by_id["astrbot_plugin_dynamics_horizons"]["pulse"] is None
    assert by_id["astrbot_plugin_dynamics_memory"]["badge"] is None

    # Second call within 10s hits TTL cache
    second = series_panels.presence(ctx, "astrbot_plugin_dynamics_world", root=tmp_path)
    assert calls["learning"] == 1
    assert any(p["id"] == "astrbot_plugin_dynamics_learning" and p["badge"]["count"] == 3 for p in second["plugins"])


@pytest.mark.asyncio
async def test_journal_feed_aggregates_world_and_siblings_with_isolation(
    tmp_path, monkeypatch
):
    plugin, entries, routes = await make_plugin(
        tmp_path, monkeypatch, runtime_enabled=True
    )
    try:
        seed(plugin)
        now = time.time()
        # Seed a committed diary row in World for today
        ident = _identity({"persona_id": "p", "instance_id": "p"})
        with plugin.life.narrative._db() as db:
            db.execute(
                "INSERT INTO diary VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("d-1", ident, UMO, now - 120, "在花圃浇水后沏了一壶洋甘菊茶", "fiction", "[]", 1),
            )

        class HorizonsSibling:
            def get_journal_events(self, persona="", scope="", date="today", limit=20):
                return [
                    {
                        "id": "hz-1",
                        "category": "horizons",
                        "source_label": "群间见闻",
                        "tone": "accent",
                        "occurred_at": now - 30,
                        "title": "精读了一篇独立像素游戏光影设计文章",
                        "subtitle": "新增暂存兴趣「体素光影」",
                        "target_plugin": "astrbot_plugin_dynamics_horizons",
                        "target_route": "reading",
                        "target_id": "hz-1",
                    }
                ]

        class LearningSibling:
            async def get_journal_events(self, persona="", scope="", date="today", limit=20):
                return [
                    {
                        "id": "lrn-1",
                        "category": "learning",
                        "source_label": "群间学习",
                        "tone": "warm",
                        "occurred_at": now - 60,
                        "title": "观察到 3 条新表达习惯提案",
                        "subtitle": "点击进入调整审查",
                        "target_plugin": "astrbot_plugin_dynamics_learning",
                        "target_route": "review",
                        "target_id": "lrn-1",
                    }
                ]

        class BrokenSibling:
            def get_journal_events(self, **kwargs):
                raise RuntimeError("db locked")

        class SlowSibling:
            async def get_journal_events(self, **kwargs):
                await asyncio.sleep(2.0)
                return []

        entries.extend(
            [
                NS(name="astrbot_plugin_dynamics_horizons", activated=True, star_cls=HorizonsSibling()),
                NS(name="astrbot_plugin_dynamics_learning", activated=True, star_cls=LearningSibling()),
                NS(name="astrbot_plugin_dynamics_memory", activated=True, star_cls=BrokenSibling()),
                NS(name="astrbot_plugin_dynamics_games", activated=True, star_cls=SlowSibling()),
            ]
        )

        monkeypatch.setattr(wb_api, "json_response", lambda data=None, **kwargs: data)
        raw_req = NS(
            state=NS(dashboard_g=NS(username="admin")),
            method="GET",
            headers={},
            cookies={},
        )
        monkeypatch.setattr(
            wb_api,
            "request",
            NS(
                query={"scope": UMO, "date": "today", "limit": "20"},
                headers={},
                cookies={},
                method="GET",
                username="admin",
                _request=raw_req,
            ),
        )
        handler = routes[("/astrbot_plugin_dynamics_world/journal_feed", ("GET",))]
        res = await handler()
        assert res["status"] == "ok"
        payload = res["data"]
        events = payload["events"]
        titles = [e["title"] for e in events]
        assert any("洋甘菊茶" in t for t in titles)
        assert any("独立像素游戏" in t for t in titles)
        assert any("3 条新表达习惯提案" in t for t in titles)
        # Sorted descending by timestamp (hz-1 @ -30s, lrn-1 @ -60s, diary @ -120s)
        timestamps = [e["timestamp"] for e in events]
        assert timestamps == sorted(timestamps, reverse=True)
        # Broken & timed-out siblings safely skipped
        assert payload["sources"]["memory"]["available"] is False
        assert payload["sources"]["games"]["available"] is False
        assert payload["sources"]["visual_media"]["available"] is False
    finally:
        await plugin.terminate()


def test_world_html_v2_hud_and_tab_contracts():
    world_dir = Path(__file__).parents[1] / "pages" / "world"
    html = (world_dir / "index.html").read_text(encoding="utf-8")
    # Zero external CDN references
    assert "https://" not in html and "http://" not in html
    # Cache-bust query versions updated
    assert "workbench.css?v=wb-iso.2" in html
    assert "boot.js?v=wb-iso.1" in html
    # Standalone stories tab & view merged into life
    assert 'id="tab-stories"' not in html
    assert 'id="view-stories"' not in html
    # All 11 workbench tab IDs preserved with role="tab" (4 core + 7 ops)
    for tid in (
        "tab-life",
        "tab-map",
        "tab-cards",
        "tab-books",
        "tab-scenes",
        "tab-weather",
        "tab-sessions",
        "tab-overview",
        "tab-preview",
        "tab-config",
        "tab-migration",
    ):
        assert f'id="{tid}"' in html
    # More & Ops dropdown + Journal pill + Cmd+K trigger present
    assert 'id="wbTabsMore"' in html
    assert 'id="cabinJournalPill"' in html
    assert 'id="dwCmdK"' in html
    assert 'id="dwCabinCenter"' in html
    # Core 4 tabs appear before wbTabsMore; 7 ops tabs appear after
    more_pos = html.index('id="wbTabsMore"')
    for core_id in ("tab-life", "tab-map", "tab-cards", "tab-books"):
        assert html.index(f'id="{core_id}"') < more_pos
    for ops_id in ("tab-scenes", "tab-weather", "tab-sessions", "tab-overview", "tab-preview", "tab-config", "tab-migration"):
        assert html.index(f'id="{ops_id}"') > more_pos
    # Ensure role="tab" present on all 11 static tab buttons
    assert len(re.findall(r'role="tab"', html)) == 11
    # Merged #view-life section contains life controls, fallback plan card, and stories/commitments
    life_match = re.search(r'<section[^>]*id="view-life"[^>]*>.*?</section>', html, re.S)
    assert life_match is not None
    life_html = life_match.group(0)
    for eid in (
        "dwLifeSummary",
        "dwDiary",
        "dwCommitments",
        "dwIntents",
        "dwCorrect",
        "dwPlan",
        "dwPlanCard",
        "dwStoriesSection",
        "dwControlSection",
    ):
        assert f'id="{eid}"' in life_html


def test_world_workbench_context_isolation_contracts():
    world_dir = Path(__file__).parents[1] / "pages" / "world"
    boot_js = (world_dir / "boot.js").read_text(encoding="utf-8")
    app_js = (world_dir / "app.js").read_text(encoding="utf-8")
    cabin_js = (world_dir / "pixel-cabin.js").read_text(encoding="utf-8")
    world_js = (world_dir / "world.js").read_text(encoding="utf-8")
    causal_js = (world_dir / "causal-panel.js").read_text(encoding="utf-8")

    # Cache-bust chain
    assert "./app.js?v=wb-iso.1" in boot_js
    assert "./pixel-cabin.js?v=wb-iso.1" in app_js
    assert "./world.js?v=wb-iso.1" in app_js
    assert "./creative-world.js?v=wb-iso.1" in app_js
    assert "./cabin-inspect.js?v=wb-iso.1" in cabin_js
    assert "./cabin-messages.js?v=wb-iso.1" in cabin_js

    # Route alias & merged core views in app.js
    assert 'VIEW_ALIASES = { stories: "life" }' in app_js
    assert 'CORE_VIEWS = ["life", "map", "cards", "books"]' in app_js
    assert "cabinDrawerToWorkbench" in app_js
    assert 'document.body.dataset.stageMode !== "cabin-drawer"' in app_js
    assert "Boolean(drawer) && name !== \"cabin\" && STAGE_DRAWER_VIEWS.has(name)" in app_js
    assert "setView(landingView, { focus: true, drawer: false })" in app_js

    # pixel-cabin.js derives visibility from stageMode rather than STAGE_DRAWER_VIEWS
    assert "STAGE_DRAWER_VIEWS" not in cabin_js
    assert "document.body.dataset.stageMode" in cabin_js
    assert "drawer:true" in cabin_js

    # causal-panel.js explicitly opens workbench with drawer:false
    assert "drawer:false" in causal_js

    # world.js hides #dwPlanCard unless legacy or non-ready plan_status
    assert 'planStatus.status !== "ready"' in world_js
    assert 'planCard.hidden = !showPlanFallback' in world_js


@pytest.mark.asyncio
async def test_journal_feed_isolates_persona_after_group_switch_and_blocks_unbound(
    tmp_path, monkeypatch
):
    from astrbot_plugin_dynamics_world.world.core.character import CharacterCard

    plugin, entries, routes = await make_plugin(
        tmp_path, monkeypatch, runtime_enabled=True
    )
    try:
        plugin.world.store.upsert_card(
            CharacterCard(
                id="card_a",
                name="角色甲",
                persona_id="persona_a",
                system_prompt="Persona A",
            )
        )
        plugin.world.store.upsert_card(
            CharacterCard(
                id="card_b",
                name="角色乙",
                persona_id="persona_b",
                system_prompt="Persona B",
            )
        )
        # Switch the same group from persona_a to persona_b (no default card fallback).
        plugin.world.store.update_session(UMO, card_id="card_b")

        now = time.time()
        ident_a = _identity({"persona_id": "persona_a", "instance_id": "persona_a"})
        ident_b = _identity({"persona_id": "persona_b", "instance_id": "persona_b"})
        with plugin.life.narrative._db() as db:
            db.execute(
                "INSERT INTO diary VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("da-1", ident_a, UMO, now - 90, "角色甲的旧手账记录", "fiction", "[]", 1),
            )
            db.execute(
                "INSERT INTO diary VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("db-1", ident_b, UMO, now - 60, "角色乙的今日手账记录", "fiction", "[]", 1),
            )

        mem_calls: list[dict] = []
        lrn_calls: list[dict] = []

        class MemorySibling:
            def get_journal_events(
                self,
                persona="",
                scope="",
                date="today",
                limit=20,
                start_ts=None,
                end_ts=None,
            ):
                mem_calls.append(
                    {
                        "persona": persona,
                        "scope": scope,
                        "date": date,
                        "start_ts": start_ts,
                        "end_ts": end_ts,
                    }
                )
                rows = [
                    {
                        "id": "mem-a",
                        "persona": "persona_a",
                        "occurred_at": now - 40,
                        "title": "记忆甲（不应泄露）",
                    },
                    {
                        "id": "mem-b",
                        "persona": "persona_b",
                        "occurred_at": now - 30,
                        "title": "记忆乙（当前角色）",
                    },
                ]
                return [r for r in rows if not persona or r["persona"] == persona]

        class LearningSibling:
            def get_journal_events(
                self,
                persona="",
                scope="",
                date="today",
                limit=20,
                start_ts=None,
                end_ts=None,
            ):
                lrn_calls.append(
                    {
                        "persona": persona,
                        "scope": scope,
                        "date": date,
                        "start_ts": start_ts,
                        "end_ts": end_ts,
                    }
                )
                rows = [
                    {
                        "id": "lrn-a",
                        "persona": "persona_a",
                        "occurred_at": now - 50,
                        "title": "学习甲（不应泄露）",
                    },
                    {
                        "id": "lrn-b",
                        "persona": "persona_b",
                        "occurred_at": now - 20,
                        "title": "学习乙（当前角色）",
                    },
                ]
                return [r for r in rows if not persona or r["persona"] == persona]

        entries.extend(
            [
                NS(
                    name="astrbot_plugin_dynamics_memory",
                    activated=True,
                    star_cls=MemorySibling(),
                ),
                NS(
                    name="astrbot_plugin_dynamics_learning",
                    activated=True,
                    star_cls=LearningSibling(),
                ),
            ]
        )

        monkeypatch.setattr(wb_api, "json_response", lambda data=None, **kwargs: data)
        handler = routes[("/astrbot_plugin_dynamics_world/journal_feed", ("GET",))]

        def _journal_req(scope_val):
            raw_req = NS(
                state=NS(dashboard_g=NS(username="admin")),
                method="GET",
                headers={},
                cookies={},
            )
            return NS(
                query={"scope": scope_val, "date": "today", "limit": "30"},
                headers={},
                cookies={},
                method="GET",
                username="admin",
                _request=raw_req,
            )

        # 1. Cabin only sends scope + date (no persona): backend resolves persona_b and forwards it
        monkeypatch.setattr(wb_api, "request", _journal_req(UMO))
        res = await handler()
        assert res["status"] == "ok"
        payload = res["data"]
        assert payload["persona"] == "persona_b"
        assert payload["scope"] == UMO
        assert len(mem_calls) == 1 and mem_calls[0]["persona"] == "persona_b"
        assert len(lrn_calls) == 1 and lrn_calls[0]["persona"] == "persona_b"
        assert mem_calls[0]["start_ts"] is not None and mem_calls[0]["end_ts"] is not None
        assert lrn_calls[0]["start_ts"] == mem_calls[0]["start_ts"]
        assert lrn_calls[0]["end_ts"] == mem_calls[0]["end_ts"]
        titles = [e["title"] for e in payload["events"]]
        assert any("角色乙的今日手账记录" in t for t in titles)
        assert any("记忆乙" in t for t in titles)
        assert any("学习乙" in t for t in titles)
        assert not any("甲" in t for t in titles)

        # 2. Unbound group (no card bound and no default card): returns empty without calling siblings
        unknown_group = "qq:GroupMessage:unbound_no_card"
        sessions_before = set(plugin.world.store._store.sessions.keys())
        monkeypatch.setattr(wb_api, "request", _journal_req(unknown_group))
        res_unbound = await handler()
        assert res_unbound["status"] == "ok"
        assert res_unbound["data"]["events"] == []
        assert res_unbound["data"]["total"] == 0
        assert res_unbound["data"]["persona"] == ""
        assert len(mem_calls) == 1  # Sibling NOT called with empty persona
        assert len(lrn_calls) == 1
        assert set(plugin.world.store._store.sessions.keys()) == sessions_before

        # 3. Explicitly unbound (__none__) group: returns empty without calling siblings
        plugin.world.store.update_session(UMO, card_id="__none__")
        monkeypatch.setattr(wb_api, "request", _journal_req(UMO))
        res_none = await handler()
        assert res_none["status"] == "ok"
        assert res_none["data"]["events"] == []
        assert res_none["data"]["persona"] == ""
        assert len(mem_calls) == 1
        assert len(lrn_calls) == 1
    finally:
        await plugin.terminate()


@pytest.mark.asyncio
async def test_journal_feed_date_bounds_consistent_across_utc_and_explicit_range(
    tmp_path, monkeypatch
):
    from datetime import datetime, timedelta, timezone

    from astrbot_plugin_dynamics_world.series_hooks import (
        aggregate_journal_feed,
        collect_world_journal_events,
    )

    # Simulate a UTC container at 2026-11-20T23:30:00Z (= 2026-11-21T07:30:00+08:00):
    # UTC date is 2026-11-20 while Shanghai date is 2026-11-21.
    monkeypatch.setenv("TZ", "UTC")
    if hasattr(time, "tzset"):
        time.tzset()

    plugin, entries, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    try:
        seed(plugin)
        tz_sh = timezone(timedelta(hours=8))
        now_utc = datetime(2026, 11, 20, 23, 30, 0, tzinfo=timezone.utc).timestamp()
        plugin.life.narrative.clock = lambda: now_utc

        expected_start = datetime(2026, 11, 21, 0, 0, 0, tzinfo=tz_sh).timestamp()
        expected_end = datetime(2026, 11, 22, 0, 0, 0, tzinfo=tz_sh).timestamp()

        # 2026-11-20T23:30+08:00 (15:30Z): same UTC day as now_utc, but YESTERDAY in UTC+8
        ts_yesterday_sh = datetime(2026, 11, 20, 15, 30, 0, tzinfo=timezone.utc).timestamp()
        # 2026-11-21T00:30+08:00 (16:30Z): TODAY in UTC+8
        ts_today_early_sh = datetime(2026, 11, 20, 16, 30, 0, tzinfo=timezone.utc).timestamp()
        # 2026-11-21T07:10+08:00 (23:10Z): TODAY in UTC+8
        ts_today_morning_sh = datetime(2026, 11, 20, 23, 10, 0, tzinfo=timezone.utc).timestamp()

        ident = _identity({"persona_id": "p", "instance_id": "p"})
        with plugin.life.narrative._db() as db:
            db.execute(
                "INSERT INTO diary VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("d-yest", ident, UMO, ts_yesterday_sh, "上海昨晚的日记", "fiction", "[]", 1),
            )
            db.execute(
                "INSERT INTO diary VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("d-today", ident, UMO, ts_today_early_sh, "上海凌晨的日记", "fiction", "[]", 1),
            )

        captured_bounds: list[tuple[float | None, float | None]] = []

        class TzAwareMemorySibling:
            def get_journal_events(
                self,
                persona="",
                scope="",
                date="today",
                limit=20,
                start_ts=None,
                end_ts=None,
            ):
                captured_bounds.append((start_ts, end_ts))
                items = [
                    {"id": "m-yest", "occurred_at": ts_yesterday_sh, "title": "昨晚记忆"},
                    {"id": "m-morn", "occurred_at": ts_today_morning_sh, "title": "今晨记忆"},
                ]
                if start_ts is not None and end_ts is not None:
                    return [i for i in items if start_ts <= i["occurred_at"] < end_ts]
                return items

        class LegacySignatureSibling:
            def get_journal_events(self, persona="", scope="", date="today", limit=20):
                return [
                    {"id": "leg-1", "occurred_at": ts_today_morning_sh, "title": "旧签名伴生记录"}
                ]

        entries.extend(
            [
                NS(
                    name="astrbot_plugin_dynamics_memory",
                    activated=True,
                    star_cls=TzAwareMemorySibling(),
                ),
                NS(
                    name="astrbot_plugin_dynamics_horizons",
                    activated=True,
                    star_cls=LegacySignatureSibling(),
                ),
            ]
        )

        feed = await aggregate_journal_feed(plugin, scope=UMO, date="today", limit=30)
        assert captured_bounds == [(expected_start, expected_end)]
        titles = [e["title"] for e in feed["events"]]
        assert "上海凌晨的日记" in titles
        assert "今晨记忆" in titles
        assert "旧签名伴生记录" in titles
        assert "上海昨晚的日记" not in titles
        assert "昨晚记忆" not in titles

        # Invalid explicit bounds return empty safely
        assert (
            collect_world_journal_events(
                plugin, scope=UMO, start_ts=expected_end, end_ts=expected_start
            )
            == []
        )
        assert (
            collect_world_journal_events(plugin, scope=UMO, start_ts=expected_start)
            == []
        )
    finally:
        await plugin.terminate()
