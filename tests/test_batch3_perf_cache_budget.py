"""Batch 3 regression tests: PostcardRenderer cleanup & cabinStyle, hot-path I/O,
cross-mode prefix_hash, worldbook budget caps, ProviderBudgetBusy closure,
world_stream fixes, 3D perf/disposal, and config schema migration fidelity."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import re
import sys
import types
from pathlib import Path
from types import SimpleNamespace as NS

from astrbot_plugin_dynamics_world import migration
from astrbot_plugin_dynamics_world.causal_life import CausalLifeService
from astrbot_plugin_dynamics_world.life.core.narrative import (
    CHINA,
    NarrativeEngine,
    _identity,
)
from astrbot_plugin_dynamics_world.life.core.narrative_prompt import (
    build_narrative_prompt_segments,
    compute_narrative_prefix_hash,
)
from astrbot_plugin_dynamics_world.life.core.narrative_types import (
    NarrativeProviderBusy,
    _json,
)
from astrbot_plugin_dynamics_world.life.core.state import LifeState, TimelineEntry
from astrbot_plugin_dynamics_world.postcard_renderer import PostcardRenderer
from astrbot_plugin_dynamics_world.resident_runtime import ResidentRunner
from astrbot_plugin_dynamics_world.spatial import SpatialState
from astrbot_plugin_dynamics_world.world.core.character import CharacterCard
from astrbot_plugin_dynamics_world.world.core.matcher import (
    build_injection_text,
    match_entries,
)
from astrbot_plugin_dynamics_world.world.core.models import WorldBook, WorldEntry
from astrbot_plugin_dynamics_world.world.service import WorldService
from astrbot_plugin_dynamics_world.world_stream import (
    _life_cues,
    compute_domain_revisions,
)


SCOPE = {
    "platform": "test",
    "umo": "test:GroupMessage:batch3",
    "persona_id": "p_b3",
    "instance_id": "inst_b3",
}


class _DummyCtx:
    def __init__(self, data_dir: Path):
        self.plugin_data_dir = str(data_dir)
        self.persona_manager = None
        self.conversation_manager = None

    def get_config(self):
        return {"dashboard": {"username": "admin"}}


# ---------------------------------------------------------------------------
# P1-#2 & P1-#8: PostcardRenderer cancellation cleanup & cabinStyle
# ---------------------------------------------------------------------------


def test_postcard_renderer_shuts_down_playwright_on_timeout_cancellation(tmp_path, monkeypatch):
    renderer = PostcardRenderer(tmp_path / "postcards")
    bundle = tmp_path / "pages" / "world" / "cabin3d.min.js"
    bundle.parent.mkdir(parents=True)
    bundle.write_text("export function createCabin3D(){}", encoding="utf-8")

    closed = {"page": 0, "browser": 0, "pw": 0}

    class FakePage:
        def is_closed(self):
            return False

        async def close(self):
            closed["page"] += 1

        async def evaluate(self, _script, _arg):
            await asyncio.sleep(5)  # hangs until cancelled by timeout

    class FakeBrowser:
        async def close(self):
            closed["browser"] += 1

    class FakePW:
        async def stop(self):
            closed["pw"] += 1

    async def fake_ensure(_bundle_path):
        renderer._pw = FakePW()
        renderer._browser = FakeBrowser()
        renderer._page = FakePage()
        return renderer._page

    monkeypatch.setattr(renderer, "_ensure_warm_page", fake_ensure)

    async def run_timeout():
        try:
            await asyncio.wait_for(
                renderer._try_playwright_capture(
                    {"cabin_style": "whale_coast", "server_time": 1_800_000_000.0},
                    tmp_path,
                    {"view": "room", "focus": None},
                ),
                timeout=0.05,
            )
            raise AssertionError("expected TimeoutError")
        except TimeoutError:
            pass

    asyncio.run(run_timeout())
    assert closed == {"page": 1, "browser": 1, "pw": 1}
    assert renderer._page is None and renderer._browser is None and renderer._pw is None


def test_postcard_renderer_ensure_warm_page_cleans_up_on_cancellation(tmp_path, monkeypatch):
    renderer = PostcardRenderer(tmp_path / "postcards")
    bundle = tmp_path / "pages" / "world" / "cabin3d.min.js"
    bundle.parent.mkdir(parents=True)
    bundle.write_text("export function createCabin3D(){}", encoding="utf-8")

    closed = {"page": 0, "browser": 0, "pw": 0}

    class FakePage:
        async def set_content(self, _html):
            await asyncio.sleep(5)  # cancelled mid-boot

        async def close(self):
            closed["page"] += 1

    class FakeBrowser:
        async def new_page(self, **_kw):
            return FakePage()

        async def close(self):
            closed["browser"] += 1

    class FakeChromium:
        async def launch(self, **_kw):
            return FakeBrowser()

    class FakePW:
        chromium = FakeChromium()

        async def stop(self):
            closed["pw"] += 1

    class FakeAsyncPW:
        async def start(self):
            return FakePW()

    fake_mod = types.ModuleType("playwright.async_api")
    fake_mod.async_playwright = lambda: FakeAsyncPW()
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_mod)

    async def run_cancel():
        try:
            await asyncio.wait_for(renderer._ensure_warm_page(bundle), timeout=0.05)
            raise AssertionError("expected TimeoutError")
        except TimeoutError:
            pass

    asyncio.run(run_cancel())
    assert closed == {"page": 1, "browser": 1, "pw": 1}
    assert renderer._page is None and renderer._browser is None and renderer._pw is None


def test_postcard_renderer_passes_cabin_style_and_whale_art_url(tmp_path, monkeypatch):
    renderer = PostcardRenderer(tmp_path / "postcards")
    bundle = tmp_path / "pages" / "world" / "cabin3d.min.js"
    bundle.parent.mkdir(parents=True)
    bundle.write_text("export function createCabin3D(){}", encoding="utf-8")
    (bundle.parent / "deepseek-whale-maid.jpg").write_bytes(b"\xff\xd8\xff\xe0fakejpg")

    captured_evals = []

    class FakePage:
        def is_closed(self):
            return False

        async def set_content(self, _html):
            return None

        async def evaluate(self, script, arg):
            captured_evals.append((script, arg))
            if len(captured_evals) == 1:
                return True
            # Return a minimal 1x1 PNG data URL
            from io import BytesIO
            from PIL import Image
            import base64

            buf = BytesIO()
            Image.new("RGB", (4, 4), "blue").save(buf, format="PNG")
            return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

        async def close(self):
            return None

    class FakeBrowser:
        async def new_page(self, **_kw):
            return FakePage()

        async def close(self):
            return None

    class FakePW:
        chromium = NS(launch=lambda **_kw: asyncio.sleep(0, result=FakeBrowser()))

        async def stop(self):
            return None

    fake_mod = types.ModuleType("playwright.async_api")
    fake_mod.async_playwright = lambda: NS(start=lambda: asyncio.sleep(0, result=FakePW()))
    monkeypatch.setitem(sys.modules, "playwright", types.ModuleType("playwright"))
    monkeypatch.setitem(sys.modules, "playwright.async_api", fake_mod)

    async def run_capture():
        try:
            img = await renderer._try_playwright_capture(
                {"cabin_style": "whale_coast", "server_time": 1_800_000_000.0},
                tmp_path,
                {"view": "room", "focus": None},
            )
            assert img is not None
        finally:
            await renderer.close()

    asyncio.run(run_capture())
    assert len(captured_evals) == 2
    boot_script, boot_args = captured_evals[0]
    assert "__CABIN_WHALE_ART_URL__" in boot_script
    assert boot_args[1].startswith("data:image/jpeg;base64,")
    render_script, render_cfg = captured_evals[1]
    assert "setCabinStyle" in render_script
    assert render_cfg["cabinStyle"] == "whale_coast"


# ---------------------------------------------------------------------------
# P1-#4: Hot-path sync I/O de-blocking (WorldBookStore + WorldService)
# ---------------------------------------------------------------------------


def test_worldbook_on_llm_request_does_not_sync_write_on_event_loop(tmp_path, monkeypatch):
    svc = WorldService(_DummyCtx(tmp_path), {"enabled": True, "inject_mode": "extra"}, tmp_path)
    book = WorldBook(id="b1", name="测试书")
    book.entries.append(WorldEntry(uid="e1", keys=["咖啡"], content="海边咖啡馆"))
    svc.store.upsert_book(book)
    svc.store.set_global_active_books(["b1"])

    writes = []
    orig_write = svc.store._write_locked

    def spy_write():
        writes.append(1)
        return orig_write()

    monkeypatch.setattr(svc.store, "_write_locked", spy_write)

    class Ev:
        unified_msg_origin = "qq:GroupMessage:1"
        message_str = "想去喝咖啡"

        def get_session_id(self):
            return self.unified_msg_origin

        def get_extra(self, _key, default=None):
            return default

    req = NS(system_prompt="SYS", contexts=[], prompt="想去喝咖啡", extra_user_content_parts=[])

    async def run_hot_path():
        await svc.on_llm_request(Ev(), req)
        # Immediately after on_llm_request returns, NO sync write happened on the event loop!
        assert writes == []
        assert svc.store._dirty is True
        await svc.flush_pending_writes()
        assert len(writes) == 1
        assert svc.store._dirty is False

    asyncio.run(run_hot_path())


# ---------------------------------------------------------------------------
# P1-#5: Cross-mode prefix_hash cache sharing
# ---------------------------------------------------------------------------


def test_prefix_hash_shared_across_all_four_narrative_modes():
    character = {
        "name": "安安",
        "persona_id": "p_b3",
        "core_prompt": "安静温和的魔女角色。",
        "world_items": [{"source_id": "w1", "title": "小镇", "text": "牢屋敷海边小镇。"}],
    }
    base_req = {
        "scope": SCOPE,
        "now": 1_800_000_000.0,
        "snapshot": {
            "activity": "看书",
            "spatial": {
                "available": True,
                "places": [{"id": "a", "name": "住所"}, {"id": "b", "name": "书店"}],
            },
        },
        "events": [],
    }
    modes = [
        dict(base_req, scope={**SCOPE, "platform": "", "umo": ""}),  # global tick
        dict(base_req),  # scoped advance
        dict(base_req, outreach_only=True),  # outreach
        dict(base_req, manual_plan_regeneration=True),  # plan regen
    ]
    hashes = []
    anchors = []
    sys_prompts = []
    for req in modes:
        sp, shared_block, _dyn = build_narrative_prompt_segments(req, character)
        sys_prompts.append(sp)
        h = compute_narrative_prefix_hash(sp)
        hashes.append(h)
        anchors.append(shared_block.splitlines()[0])

    # Mode-specific rules differ, yet invariant prefix_hash & cache_anchor are identical!
    assert len(set(sys_prompts)) == 4
    assert len(set(hashes)) == 1
    assert len(set(anchors)) == 1
    assert anchors[0] == f"[cache_anchor task=dynamics_world.narrative prefix={hashes[0]}]"

    # Changing character profile MUST produce a different prefix_hash
    other_sp, _, _ = build_narrative_prompt_segments(
        modes[0], dict(character, core_prompt="完全不同的人设。")
    )
    assert compute_narrative_prefix_hash(other_sp) != hashes[0]


# ---------------------------------------------------------------------------
# P1-#6: Worldbook injection budget caps
# ---------------------------------------------------------------------------


def test_worldbook_matcher_enforces_constant_and_char_budgets():
    book = WorldBook(id="b1", name="巨型世界书")
    for i in range(25):
        book.entries.append(
            WorldEntry(
                uid=f"c{i}",
                name=f"常驻{i}",
                content=f"常驻正文{i}_" + ("字" * 80),
                constant=True,
                priority=100 - i,
            )
        )
    for i in range(5):
        book.entries.append(
            WorldEntry(
                uid=f"k{i}",
                name=f"词条{i}",
                keys=["魔法"],
                content=f"关键词正文{i}_" + ("魔" * 400),
                priority=50 - i,
            )
        )

    # 1. Constant entry cap + char budget
    res = match_entries(
        [book],
        "使用魔法",
        max_entries=10,
        max_constant_entries=5,
        max_total_chars=600,
    )
    consts = [m for m in res.matched if m.entry.constant]
    assert len(consts) <= 5
    # Highest-priority constants come first
    assert res.matched[0].entry.uid == "c0"
    total_chars = sum(
        len(m.entry.name) + len(m.entry.content) + len(m.entry.behavior)
        for m in res.matched
    )
    assert total_chars <= 650

    # 2. Single giant 50,000-char entry is clipped rather than blowing up context
    giant_book = WorldBook(id="bg", name="巨条")
    giant_book.entries.append(
        WorldEntry(uid="g1", name="巨型设定", keys=["触发"], content="长" * 50000, constant=True)
    )
    res_giant = match_entries([giant_book], "触发", max_total_chars=500)
    assert len(res_giant.matched) == 1
    assert len(res_giant.matched[0].entry.content) <= 500
    assert res_giant.matched[0].entry.content.endswith("…")
    assert len(build_injection_text(res_giant)) < 900


# ---------------------------------------------------------------------------
# P1-#7: ProviderBudgetBusyError semantic closure across all 3 consumers
# ---------------------------------------------------------------------------


def test_provider_budget_busy_refunds_budget_and_skips_penalties_in_narrative_and_outreach(
    tmp_path,
):
    now = [1_795_000_000.0]
    ident = _identity(SCOPE)

    async def busy_model(_req):
        raise NarrativeProviderBusy("foreground chat active", retry_after=20.0, reason="foreground_chat")

    cfg = {
        "mode": "narrative",
        "persona_id": SCOPE["persona_id"],
        "narrative_sessions": [SCOPE["umo"]],
        "narrative_timeout_seconds": 10,
        "social_chat_enabled": True,
    }
    engine = NarrativeEngine(tmp_path / "busy.sqlite3", cfg, busy_model, clock=lambda: now[0])
    engine.spatial = SpatialState(engine)
    engine.causal = CausalLifeService(engine)

    # 1. Consumer 1: NarrativeEngine.advance
    ev = {
        "schema_version": 1,
        "event_id": "ev-busy-1",
        "type": "chat.message",
        "scope": SCOPE,
        "occurred_at": now[0] - 5,
        "received_at": now[0] - 5,
        "actor_id": "u1",
        "text": "最近过得怎么样？",
        "fact_kind": "user_claim",
        "data": {"directed_to_bot": True},
    }
    res = asyncio.run(engine.advance([ev]))
    assert res["status"] == "budget_busy"
    with engine._db(notify=False) as db:
        # Hourly budget refunded to 0
        used_sum = db.execute(
            "SELECT COALESCE(SUM(used), 0) FROM budgets WHERE identity=?", (ident,)
        ).fetchone()[0]
        assert used_sum == 0
        # Zero validation_failures recorded
        assert db.execute("SELECT COUNT(*) FROM validation_failures").fetchone()[0] == 0
        # Pending event keeps retry_attempt == 0 and short next_retry
        row = db.execute(
            "SELECT status, retry_attempt, next_retry FROM events WHERE event_id='ev-busy-1'"
        ).fetchone()
        assert row["status"] == "pending"
        assert row["retry_attempt"] == 0
        assert now[0] < row["next_retry"] <= now[0] + 60.0
        assert (
            db.execute("SELECT status FROM calls ORDER BY started DESC LIMIT 1").fetchone()[0]
            == "budget_busy"
        )

    # 2. Consumer 2: NarrativeEngine.review_outreach
    # Seed a daytime directed event so outreach enters model evaluation
    now[0] = dt.datetime(2026, 11, 21, 14, 0, tzinfo=CHINA).timestamp()
    outreach_scope = engine._outreach_scope(SCOPE["umo"])
    outreach_ident = _identity(outreach_scope)
    care_ev = {
        "schema_version": 1,
        "event_id": "ev-care-busy-1",
        "type": "chat.message",
        "scope": outreach_scope,
        "occurred_at": now[0] - 600,
        "received_at": now[0] - 600,
        "actor_id": "u1",
        "text": "我今天发烧了不太舒服，先去躺会儿",
        "fact_kind": "user_claim",
        "data": {"directed_to_bot": True},
    }
    asyncio.run(engine.ingest_events([care_ev]))
    with engine._db() as db:
        db.execute("UPDATE events SET status='processed' WHERE event_id='ev-care-busy-1'")
    outreach_res = asyncio.run(engine.review_outreach())
    assert outreach_res and outreach_res[0]["status"] == "budget_busy"
    with engine._db(notify=False) as db:
        used_sum = db.execute(
            "SELECT COALESCE(SUM(used), 0) FROM budgets WHERE identity=?",
            (outreach_ident,),
        ).fetchone()[0]
        assert used_sum == 0
        assert db.execute("SELECT COUNT(*) FROM validation_failures").fetchone()[0] == 0
        key = "outreach_review:" + _json([outreach_ident, SCOPE["umo"]])
        marker = json.loads(
            db.execute("SELECT value FROM metadata WHERE key=?", (key,)).fetchone()[0]
        )
        assert marker["status"] == "budget_busy"
        assert marker["next_at"] <= now[0] + 120.0


def test_provider_budget_busy_in_resident_runner_refunds_budget_and_preserves_last_served(
    tmp_path,
):
    now = [1_795_000_000.0]

    async def busy_model(_req):
        raise NarrativeProviderBusy("busy", retry_after=15.0, reason="foreground")

    cfg = {
        "mode": "narrative",
        "persona_id": SCOPE["persona_id"],
        "narrative_sessions": [SCOPE["umo"]],
        "resident_hourly_budget": 6,
    }
    engine = NarrativeEngine(tmp_path / "res_busy.sqlite3", cfg, busy_model, clock=lambda: now[0])
    engine.spatial = SpatialState(engine)
    from astrbot_plugin_dynamics_world.scenes import SceneService

    engine.scenes = SceneService(engine)
    engine.causal = CausalLifeService(engine)

    card = CharacterCard(id="c_emma", name="艾玛", personality="温柔")
    engine.causal.card_resolver = lambda cid: card.to_dict() if cid == "c_emma" else None

    global_scope = engine._global_scope()
    # Register resident in causal_life document with last_served = 0
    with engine._db() as db:
        rev, doc = engine.causal.load(db, global_scope)
        doc["residents"]["r1"] = {
            "id": "r1",
            "name": "艾玛",
            "card_id": "c_emma",
            "enabled": True,
            "last_served": 0.0,
            "busy_until": 0.0,
            "place_id": "a",
            "revision": 1,
        }
        engine.causal.save(db, global_scope, rev, doc)

    fake_service = NS(
        narrative=engine,
        context=_DummyCtx(tmp_path),
        is_active=lambda: True,
        _narrative_model=busy_model,
    )
    runner = ResidentRunner(fake_service)

    res = asyncio.run(runner.tick(actor_id="r1", manual=True))
    assert res["status"] == "budget_busy"

    with engine._db(notify=False) as db:
        ident = _identity(global_scope)
        # Budget refunded to 0
        used = db.execute(
            "SELECT used FROM budgets WHERE identity=? AND kind='resident_global'",
            (ident,),
        ).fetchone()[0]
        assert used == 0
        # Resident last_served NOT advanced to now!
        _, doc_after = engine.causal.load(db, global_scope)
        assert doc_after["residents"]["r1"]["last_served"] == 0.0
        # Evaluation status recorded as budget_busy
        ev_status = db.execute(
            "SELECT status FROM world_resident_evaluations WHERE call_id=?",
            (res["call_id"],),
        ).fetchone()[0]
        assert ev_status == "budget_busy"


# ---------------------------------------------------------------------------
# P2-#13, P1-#9, P2-#12, P1-#11: world_stream, 3D cabin sources & schema
# ---------------------------------------------------------------------------


def test_world_stream_legacy_outfit_and_flowerbed_revision(tmp_path):
    now = [dt.datetime(2026, 11, 21, 10, 30, tzinfo=CHINA).timestamp()]

    async def noop_model(_req):
        return {"schema_version": 1, "no_change": True}

    engine = NarrativeEngine(
        tmp_path / "stream.sqlite3",
        {"mode": "legacy", "persona_id": SCOPE["persona_id"]},
        noop_model,
        clock=lambda: now[0],
    )
    legacy_state = LifeState(
        date="2026-11-21",
        timeline=[
            TimelineEntry(time="09:00-12:00", schedule="看书", outfit="浅蓝针织开衫"),
        ],
    )
    fake_life = NS(
        narrative=engine,
        _now=lambda: dt.datetime(2026, 11, 21, 10, 30, tzinfo=CHINA),
        _select_current_state=lambda _dt: (legacy_state, dt.date(2026, 11, 21)),
    )
    with engine._db(notify=False) as db:
        cues = _life_cues(db, SCOPE, now[0], fake_life)
    assert cues["outfit_now"] == "浅蓝针织开衫"

    # flowerbed typo fix: changing ecology["flowerbed"]["stage"] changes eco_rev
    base_kwargs = dict(
        doc=None,
        actor={},
        environment={},
        scene={},
        life={},
        cues={},
        ecology={"flowerbed": {"stage": "seedling"}},
        keepsakes={},
        timeline=[],
        mailbox={},
        world_space={},
        companions={},
    )
    rev1 = compute_domain_revisions(**base_kwargs)["ecology"]
    base_kwargs["ecology"] = {"flowerbed": {"stage": "blooming"}}
    rev2 = compute_domain_revisions(**base_kwargs)["ecology"]
    assert rev1 != rev2


def test_conf_schema_declares_runtime_keys_and_migration_preserves_them(tmp_path):
    root = Path(__file__).parents[1]
    schema = json.loads((root / "_conf_schema.json").read_text(encoding="utf-8"))
    for key in (
        "narrative_global_hourly_budget",
        "narrative_outreach_hourly_budget",
        "narrative_retention_days",
        "max_constant_entries",
        "max_inject_chars",
    ):
        assert key in schema, f"{key} missing from _conf_schema.json"

    # Verify migration retains these keys from legacy life config
    source = tmp_path / "source"
    (source / migration.LIFE).mkdir(parents=True)
    (source / migration.LIFE / "life_state.json").write_text("{}", encoding="utf-8")
    cfg_root = tmp_path / "config"
    cfg_root.mkdir()
    (cfg_root / (migration.LIFE + "_config.json")).write_text(
        json.dumps(
            {
                "persona_id": "p",
                "narrative_global_hourly_budget": 36,
                "narrative_outreach_hourly_budget": 9,
                "narrative_retention_days": 90,
                "unknown_secret_key": "must_drop",
            }
        ),
        encoding="utf-8",
    )
    dest = tmp_path / "dest"
    preview = migration.preview(source, dest, cfg_root)
    target, _ = migration.prepare_import(source, dest, preview["fingerprint"], cfg_root)
    migrated = json.loads((target / "migration-settings.json").read_text(encoding="utf-8"))
    assert migrated["narrative_global_hourly_budget"] == 36
    assert migrated["narrative_outreach_hourly_budget"] == 9
    assert migrated["narrative_retention_days"] == 90
    assert "unknown_secret_key" not in migrated


def test_cabin_3d_perf_and_disposal_contracts():
    root = Path(__file__).parents[1]
    cabin3d = (root / "src" / "cabin3d.js").read_text(encoding="utf-8")
    furniture = (root / "pages" / "world" / "cabin-furniture.js").read_text(encoding="utf-8")
    styles = (root / "pages" / "world" / "cabin-styles.js").read_text(encoding="utf-8")
    bundle = (root / "pages" / "world" / "cabin3d.min.js").read_text(encoding="utf-8")

    # P1-#9: no unconditional 9Hz shadow update or full scene.children raycast
    assert "syncShadowDirty()" in cabin3d
    assert "raycaster.intersectObjects(scene.children" not in cabin3d
    assert "pickTargets" in cabin3d and "floorPlane" in cabin3d
    # P2-#12: dynamic materials disposed
    assert "function disposeMaterials()" in furniture
    assert "world.disposeMaterials?.()" in cabin3d
    # P1-#8: safe data: URL handling in cabin-styles.js & bundled cabin3d.min.js
    assert "__CABIN_WHALE_ART_URL__" in styles
    assert "startsWith('data:')" in styles
    assert "__CABIN_WHALE_ART_URL__" in bundle
    assert "disposeMaterials" in bundle

    # Every THREE.* / T.* symbol referenced by src/cabin3d.js and pages/world/*.js must be bound on THREE
    three_block = re.search(r"const THREE\s*=\s*\{([^}]+)\}", cabin3d)
    assert three_block, "const THREE = {...} block missing from src/cabin3d.js"
    bound_three = set(re.findall(r"\b([A-Za-z0-9_]+)\b", three_block.group(1)))
    assert "Plane" in bound_three
    missing_three: dict[str, list[str]] = {}
    for js_file in [root / "src" / "cabin3d.js", *sorted((root / "pages" / "world").glob("*.js"))]:
        if js_file.name == "cabin3d.min.js":
            continue
        text = js_file.read_text(encoding="utf-8")
        for symbol in re.findall(r"\b(?:THREE|T)\.([A-Z][A-Za-z0-9_]*)\b", text):
            if symbol not in bound_three:
                missing_three.setdefault(symbol, []).append(js_file.name)
    assert not missing_three, f"Unbound THREE symbols: {missing_three}"
