"""Wave 1 tests: async snapshot perf & cache, kitchen fix, /投递, /小屋, world state focuses & series contracts."""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

from astrbot_plugin_dynamics_world import series_panels, weather_sources
from astrbot_plugin_dynamics_world.main import parse_mailbox_delivery
from test_world_integration import SCOPE, UMO, make_plugin, seed

ROOT = Path(__file__).parents[1]


class _CmdEvent:
    def __init__(self, umo: str = UMO, uid: str = "u100", uname: str = "小旅人"):
        self.unified_msg_origin = umo
        self._uid = uid
        self._uname = uname

    def get_sender_id(self) -> str:
        return self._uid

    def get_sender_name(self) -> str:
        return self._uname

    @staticmethod
    def plain_result(text: str) -> str:
        return text


async def _collect_gen(agen) -> list[str]:
    out = []
    async for item in agen:
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# 1. Async snapshot perf, short-TTL cache & write invalidation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_snapshot_ttl_cache_hits_and_invalidates_on_write_and_clock(tmp_path, monkeypatch):
    import asyncio

    plugin, _, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    try:
        for task in (
            plugin.life._resident_task,
            plugin.life._narrative_task,
            plugin.life._outreach_task,
        ):
            task.cancel()
        await asyncio.gather(
            plugin.life._resident_task,
            plugin.life._narrative_task,
            plugin.life._outreach_task,
            return_exceptions=True,
        )
        seed(plugin)
        engine = plugin.life.narrative
        now = [1_800_000_000.0]
        monkeypatch.setattr(engine, "clock", lambda: now[0])

        read_calls = 0
        orig_snapshot = engine._snapshot

        def counting_snapshot(*args, **kwargs):
            nonlocal read_calls
            read_calls += 1
            return orig_snapshot(*args, **kwargs)

        monkeypatch.setattr(engine, "_snapshot", counting_snapshot)

        snap1 = await engine.get_snapshot(SCOPE)
        snap2 = await engine.get_snapshot(SCOPE)
        assert snap1["managed"] is True
        assert snap2["managed"] is True
        assert read_calls == 1  # Second call within TTL hit snapshot cache.

        # Advancing clock past TTL invalidates cached snapshot.
        now[0] += 5.0
        await engine.get_snapshot(SCOPE)
        assert read_calls == 2

        # Any DB write (e.g. mailbox delivery) immediately invalidates cache even within TTL.
        await engine.mailbox.deliver_parcel_async(
            SCOPE,
            sender_id="u1",
            sender_name="阿星",
            kind="gift",
            message="一个小风铃",
            bypass_cooldown=True,
        )
        snap3 = await engine.get_snapshot(SCOPE)
        assert read_calls == 3
        assert snap3["mailbox"]["unopened_count"] == 1
    finally:
        await plugin.terminate()


@pytest.mark.asyncio
async def test_async_offload_mailbox_visual_weather_and_postcard_snapshot(tmp_path, monkeypatch):
    plugin, _, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    try:
        seed(plugin)
        engine = plugin.life.narrative
        main_tid = threading.get_ident()

        seen_tids: list[int] = []
        orig_deliver = engine.mailbox.deliver_parcel

        def tracked_deliver(*args, **kwargs):
            seen_tids.append(threading.get_ident())
            return orig_deliver(*args, **kwargs)

        monkeypatch.setattr(engine.mailbox, "deliver_parcel", tracked_deliver)
        await engine.mailbox.deliver_parcel_async(
            SCOPE,
            sender_id="u2",
            sender_name="阿月",
            kind="postcard",
            message="测试异步投递",
            bypass_cooldown=True,
        )
        assert seen_tids and main_tid not in seen_tids

        vis_tids: list[int] = []
        orig_assets = engine.visuals.profiles.assets

        def tracked_assets():
            vis_tids.append(threading.get_ident())
            return orig_assets()

        monkeypatch.setattr(engine.visuals.profiles, "assets", tracked_assets)
        await engine.visuals.profiles.assets_async()
        assert vis_tids and main_tid not in vis_tids

        # weather_sources.project caches solar elevation lookups and supports project_async.
        weather_sources._is_day_cached.cache_clear()
        stamp = datetime(2026, 6, 21, 12, 0, tzinfo=timezone.utc).timestamp()
        payload = {
            "source_updated_at": stamp,
            "_series": [
                {"time": stamp + i * 3600, "temperature": 20.0 + i * 0.1}
                for i in range(6)
            ],
        }
        p1 = await weather_sources.project_async(payload, "met", stamp, 31.23, 121.47, "Asia/Shanghai")
        p2 = await weather_sources.project_async(payload, "met", stamp, 31.23, 121.47, "Asia/Shanghai")
        assert p1["current"]["is_day"] == p2["current"]["is_day"]
        assert weather_sources._is_day_cached.cache_info().hits > 0

        # build_cabin_postcard_snapshot runs DB transaction off the event loop thread.
        db_tids: list[int] = []
        orig_db = engine._db

        def observing_db(*args, **kwargs):
            db_tids.append(threading.get_ident())
            return orig_db(*args, **kwargs)

        monkeypatch.setattr(engine, "_db", observing_db)
        snap = await plugin.build_cabin_postcard_snapshot(SCOPE)
        assert snap["character"]["name"] == "角色"
        assert db_tids and main_tid not in db_tids
    finally:
        await plugin.terminate()


# ---------------------------------------------------------------------------
# 2. Cabin kitchen buttons & /投递 category parsing
# ---------------------------------------------------------------------------


def test_cabin_inspect_kitchen_buttons_fixed_and_hinted():
    js = (ROOT / "pages" / "world" / "cabin-inspect.js").read_text(encoding="utf-8")
    assert "!canSceneAct&&!hasVeg?!canSceneAct:!canSceneAct" not in js
    assert "!canSceneAct&&!hasHerb?!canSceneAct:!canSceneAct" not in js
    assert "!canSceneAct||!hasVeg" in js
    assert "!canSceneAct||!hasHerb" in js
    assert "缺少鲜蔬" in js
    assert "缺少花草" in js


@pytest.mark.parametrize(
    ("raw", "expected_kind", "expected_msg"),
    [
        ("明信片 今天海风很舒服", "postcard", "今天海风很舒服"),
        ("鲜花 送你一束刚摘的雏菊", "flower", "送你一束刚摘的雏菊"),
        ("点心：抹茶大福和热茶", "snack", "抹茶大福和热茶"),
        ("礼物 星星玻璃风铃", "gift", "星星玻璃风铃"),
        ("gift: 八音盒", "gift", "八音盒"),
        ("鲜花", "flower", "送来一小束鲜花"),
        ("给你带了一个手工书签挂件", "gift", "给你带了一个手工书签挂件"),
        ("路过花店买了束薰衣草", "flower", "路过花店买了束薰衣草"),
        ("烤了一盒曲奇饼干", "snack", "烤了一盒曲奇饼干"),
        ("晚上好，今天过得开心吗", "postcard", "晚上好，今天过得开心吗"),
    ],
)
def test_parse_mailbox_delivery(raw, expected_kind, expected_msg):
    kind, msg = parse_mailbox_delivery(raw)
    assert kind == expected_kind
    assert msg == expected_msg


@pytest.mark.asyncio
async def test_cabin_deliver_command_parses_explicit_gift(tmp_path, monkeypatch):
    plugin, _, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    try:
        seed(plugin)
        out = await _collect_gen(plugin.cabin_deliver_command(_CmdEvent(), "礼物 玻璃星星风铃"))
        assert len(out) == 1
        assert "纪念小物" in out[0]
        mb = await plugin.life.narrative.mailbox.snapshot_async(SCOPE)
        assert mb["unopened_count"] == 1
        assert mb["parcels"][0]["kind"] == "gift"
        assert mb["parcels"][0]["message"] == "玻璃星星风铃"
    finally:
        await plugin.terminate()


# ---------------------------------------------------------------------------
# 3. /小屋 help command, extended get_dynamics_world_state & snapshot summary
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cabin_help_command_shows_status_and_member_commands(tmp_path, monkeypatch):
    plugin, _, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    try:
        seed(plugin)
        out = await _collect_gen(plugin.cabin_help_command(_CmdEvent(), ""))
        assert len(out) == 1
        text = out[0]
        assert "小屋实况导航" in text
        assert "当前位置" in text
        assert "当前天气" in text
        assert "访客策略" in text
        assert "/小屋实况" in text
        assert "/投递" in text
        assert "/探访" in text
    finally:
        await plugin.terminate()


@pytest.mark.asyncio
async def test_world_state_tool_new_focuses_and_managed_snapshot_summary(tmp_path, monkeypatch):
    plugin, _, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=True)
    try:
        seed(plugin)
        engine = plugin.life.narrative
        now = engine.clock()

        # Empty idle world has empty world_brief summary_text (backward compatible).
        idle_snap = await engine.get_snapshot(SCOPE)
        assert idle_snap["world_brief"]["summary_text"] == ""

        # Deliver two parcels, open the first, leave the second unopened.
        await engine.mailbox.deliver_parcel_async(
            SCOPE,
            sender_id="u1",
            sender_name="阿星",
            kind="gift",
            title="玻璃风铃",
            message="挂在窗边听风声",
            bypass_cooldown=True,
        )
        with engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            opened = engine.mailbox.open_pending_parcels(db, SCOPE, now, max_open=1)
        assert len(opened) == 1
        assert "summary" in opened[0] and "玻璃风铃" in opened[0]["summary"]

        await engine.mailbox.deliver_parcel_async(
            SCOPE,
            sender_id="u2",
            sender_name="阿月",
            kind="flower",
            message="送你洋甘菊",
            bypass_cooldown=True,
        )
        await engine.mailbox.enter_garden_async(
            SCOPE,
            user_id="u3",
            display_name="小木",
            note="来花园坐坐",
            bypass_cooldown=True,
        )
        # Mark garden ripe and invite a peer guest.
        with engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            key, rev, eco = engine.ecology.load(db, SCOPE)
            eco["veg_patch"]["stage"] = "ripe"
            eco["veg_patch"]["progress"] = 0.95
            engine.ecology.save(db, key, rev, eco, now, bump=True)
        engine.world_spaces.invite_guest(SCOPE, guest_name="艾玛", activity="在花园喝茶")

        ev = _CmdEvent()
        mb_text = await plugin.world_state_tool(ev, focus="mailbox")
        assert "未拆来信：1" in mb_text
        assert "玻璃风铃" in mb_text
        assert "阿星" in mb_text

        garden_text = await plugin.world_state_tool(ev, focus="garden")
        assert "菜畦" in garden_text and "成熟" in garden_text
        assert "小木" in garden_text

        ks_text = await plugin.world_state_tool(ev, focus="keepsakes")
        assert "玻璃风铃" in ks_text

        res_text = await plugin.world_state_tool(ev, focus="residents")
        assert "艾玛" in res_text

        bad_text = await plugin.world_state_tool(ev, focus="invalid_focus")
        assert "mailbox" in bad_text and "residents" in bad_text

        # Managed group snapshot summary projects mailbox, garden, keepsakes & residents!
        snap = await engine.get_snapshot(SCOPE)
        brief = snap["world_brief"]
        assert brief["unopened_mail_count"] == 1
        assert brief["latest_opened_mail"]["title"] == "玻璃风铃"
        assert brief["garden"]["visitor_count"] == 1
        assert brief["garden"]["harvest_ready"] is True
        assert brief["keepsakes"]["displayed_count"] >= 1
        assert brief["residents"]["active_guest"]["name"] == "艾玛"
        assert "未拆来信" in snap["summary"]
        assert "玻璃风铃" in snap["summary"]
        assert "小木" in snap["summary"]
        assert "艾玛" in snap["summary"]
    finally:
        await plugin.terminate()


# ---------------------------------------------------------------------------
# 4. Series scope/runtime contracts & shared config inheritance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_series_scope_enabled_and_activate_series_runtime(tmp_path, monkeypatch):
    plugin, entries, _ = await make_plugin(tmp_path, monkeypatch, runtime_enabled=False)
    try:
        seed(plugin)

        # activate_series_runtime blocked on legacy conflict
        entries.append(NS(name="astrbot_plugin_worldbook", activated=True, star_cls=object()))
        blocked = await plugin.activate_series_runtime()
        assert blocked["ok"] is False
        assert blocked["reason"] == "legacy_conflict"
        entries[0].activated = False

        # activate_series_runtime succeeds & persists runtime_enabled
        activated = await plugin.activate_series_runtime()
        assert activated["ok"] is True
        assert activated["runtime_enabled"] is True
        assert activated["ready"] is True
        assert plugin.host_config.saved["runtime_enabled"] is True

        # idempotent second activation
        again = await plugin.activate_series_runtime()
        assert again["ok"] is True and again["already_enabled"] is True

        # get_series_scope_status conforms to writable contract
        st = plugin.get_series_scope_status(UMO)
        assert st["umo"] == UMO
        assert st["enabled"] is True
        assert st["writable"] is True
        assert st["supported"] is True
        ver = st["version"]

        # optimistic lock mismatch rejected
        conflict = await plugin.set_series_scope_enabled(UMO, False, expected_version="stale-v")
        assert conflict["ok"] is False
        assert conflict["conflict"] is True
        assert conflict["reason"] == "version_conflict"
        assert conflict["version"] == ver

        # disable with valid version
        off = await plugin.set_series_scope_enabled(UMO, False, expected_version=ver)
        assert off["ok"] is True
        assert off["enabled"] is False
        assert UMO not in plugin.config["narrative_sessions"]
        assert off["version"] != ver

        # re-enable with new version
        on = await plugin.set_series_scope_enabled(UMO, True, expected_version=off["version"])
        assert on["ok"] is True
        assert on["enabled"] is True
        assert UMO in plugin.config["narrative_sessions"]
    finally:
        await plugin.terminate()


@pytest.mark.asyncio
async def test_shared_config_inheritance_for_empty_persona_and_light_provider(tmp_path, monkeypatch):
    plugin, _, _ = await make_plugin(
        tmp_path,
        monkeypatch,
        runtime_enabled=True,
        narrative_provider_id="",
        llm_provider_id="",
    )
    plugin.config["persona_id"] = ""
    try:
        seed(plugin)
        used = {}

        async def fake_text_chat(prompt=None, **kwargs):
            used["called"] = True
            return NS(completion_text='{"no_change": true}')

        light_provider = NS(id="series-light", text_chat=fake_text_chat, provider_config={"id": "series-light"})
        plugin.context.get_provider_by_id = lambda pid: light_provider if pid == "series-light" else None
        plugin.context.provider_manager = NS(inst_map={"series-light": light_provider})

        shared = {
            "persona_id": "p",
            "light_analysis_provider": "series-light",
            "reply_provider": "series-reply",
        }
        monkeypatch.setattr(series_panels, "get_series_shared_config", lambda ctx: dict(shared))
        monkeypatch.setattr(
            "astrbot_plugin_dynamics_world.life.service.get_series_shared_config",
            lambda ctx: dict(shared),
        )
        monkeypatch.setattr(
            "astrbot_plugin_dynamics_world.life.core.narrative.get_series_shared_config",
            lambda ctx: dict(shared),
        )
        monkeypatch.setattr(
            "astrbot_plugin_dynamics_world.series_hooks.get_series_shared_config",
            lambda ctx: dict(shared),
        )

        # Effective persona inherited from shared config
        assert plugin._effective_persona_id() == "p"
        assert plugin.get_dynamics_summary(UMO)["persona_id"] == "p"
        assert plugin.life.narrative.is_managed(SCOPE) is True

        # Narrative model inherits light_analysis_provider when plugin provider fields are empty
        res = await plugin.life._narrative_model({"scope": SCOPE, "now": 1_800_000_000.0, "events": []})
        assert res == {"no_change": True}
        assert used.get("called") is True

        # Health report reflects inherited persona and light_analysis_provider
        health = plugin.get_series_health()
        assert health["metrics"]["persona_id"] == "p"
        by_role = {p["role"]: p for p in health["providers"]}
        assert by_role["narrative"]["provider_id"] == "series-light"
        assert by_role["narrative"]["status"] == "ok"
    finally:
        await plugin.terminate()
