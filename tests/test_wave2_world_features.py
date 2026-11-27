# ruff: noqa: E402
"""Wave 2 verification tests: mailbox live echo, keepsake polaroid, World Journal card, studio/cabin polish & schema."""
from __future__ import annotations

import json
import sys
import types
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from astrbot_plugin_dynamics_world.keepsakes import KeepsakeTimelineService
from astrbot_plugin_dynamics_world.life.core.narrative import NarrativeEngine
from astrbot_plugin_dynamics_world.mailbox_visitors import MailboxVisitorService
from astrbot_plugin_dynamics_world.postcard_renderer import (
    FALLBACK_2D_HINT,
    PostcardRenderer,
    parse_shot_override,
    resolve_shot_plan,
)
from astrbot_plugin_dynamics_world.world_journal_card import (
    collect_world_journal_data,
    format_world_journal_text,
    render_world_journal_card,
    save_world_journal_card,
)


SCOPE = {
    "persona_id": "persona_wave2",
    "character_id": "char_wave2",
    "umo": "default:GroupMessage:wave2_grp",
}


def _make_engine(tmp_path: Path, now_val: float = 1764200000.0):
    t = [now_val]

    async def _noop_model(_request):
        return {}

    engine = NarrativeEngine(
        tmp_path / "narrative.sqlite3",
        {"default_visitor_policy": "pixel_avatar"},
        _noop_model,
        clock=lambda: t[0],
    )
    engine.keepsakes = KeepsakeTimelineService(engine)
    engine.mailbox = MailboxVisitorService(engine)
    return engine, t


@pytest.mark.asyncio
async def test_mailbox_live_echo_llm_reaction_and_fallback(tmp_path: Path):
    engine, clock_box = _make_engine(tmp_path)
    try:
        p1 = engine.mailbox.deliver_parcel(
            SCOPE,
            sender_id="u_alice",
            sender_name="小爱",
            kind="flower",
            title="山谷风铃草",
            message="清晨采的蓝花，祝你今天好心情",
            bypass_cooldown=True,
        )

        async def _fake_llm(scope, parcel, character):
            assert parcel["sender_name"] == "小爱"
            return "把这束带着露水的风铃草插进北窗台的花瓶，窗边一下子亮堂起来了。"

        opened = await engine.mailbox.open_pending_parcels_async(
            SCOPE,
            max_open=3,
            character_context={"name": "夏目安安"},
            reaction_generator=_fake_llm,
        )
        assert len(opened) == 1
        assert opened[0]["parcel_id"] == p1["parcel_id"]
        assert opened[0]["reaction_source"] == "model"
        assert "风铃草" in opened[0]["reaction"]
        assert opened[0]["keepsake_slot"] == "windowsill_vase"

        # Verify diary + world_mailbox_receipts + pending_reply_material
        with engine._db(notify=False) as db:
            diary_row = db.execute(
                "SELECT text, fact_kind FROM diary WHERE entry_id=?",
                (f"mail_diary_{p1['parcel_id']}",),
            ).fetchone()
            assert diary_row is not None
            assert diary_row["fact_kind"] == "fiction"
            assert "风铃草" in diary_row["text"]

            pending = engine.mailbox.pending_reply_material(
                db, SCOPE, umo=SCOPE["umo"], sender_id="u_alice"
            )
            assert len(pending) == 1
            assert pending[0]["parcel_id"] == p1["parcel_id"]
            assert "小爱" in pending[0]["reply_cue"]

            mb_snap = engine.mailbox.snapshot(db, SCOPE, clock_box[0], read_only=True)
            assert len(mb_snap["pending_replies"]) == 1

            brief = NarrativeEngine._build_world_brief(mb_snap, None, None, None, None)
            assert len(brief["pending_mail_replies"]) == 1
            assert "待自然回应小爱" in brief["summary_text"]

        # Mark reply delivered clears pending queue
        marked = await engine.mailbox.mark_reply_delivered_async(
            SCOPE, p1["parcel_id"], "谢谢小爱的风铃草，已经插在窗台啦！"
        )
        assert marked is True
        with engine._db(notify=False) as db:
            assert engine.mailbox.pending_reply_material(db, SCOPE, sender_id="u_alice") == []

        # Graceful fallback when LLM raises
        p2 = engine.mailbox.deliver_parcel(
            SCOPE,
            sender_id="u_bob",
            sender_name="阿木",
            kind="snack",
            title="抹茶曲奇",
            message="刚烤好的曲奇",
            bypass_cooldown=True,
        )

        async def _broken_llm(scope, parcel, character):
            raise RuntimeError("offline")

        opened2 = await engine.mailbox.open_pending_parcels_async(
            SCOPE,
            max_open=3,
            reaction_generator=_broken_llm,
        )
        assert len(opened2) == 1
        assert opened2[0]["parcel_id"] == p2["parcel_id"]
        assert opened2[0]["reaction_source"] == "template"
        assert "阿木" in opened2[0]["reaction"]
        assert "刚烤好的曲奇" in opened2[0]["reaction"]
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_postcard_keepsake_mode_and_45s_cache(tmp_path: Path):
    mode, caption = parse_shot_override("纪念格 窗台上的花束")
    assert mode == "keepsake"
    assert caption == "窗台上的花束"

    snap = {
        "server_time": 1764200000.0,
        "character": {"name": "夏目安安"},
        "scene": {
            "place_id": "home",
            "place_name": "森畔小屋",
            "room_id": "study",
            "room_name": "书房",
            "revision": 3,
            "rooms": [{"id": "study", "place_id": "home"}],
        },
        "environment": {"available": True, "current": {"label": "晴", "effect": "clear", "temperature": 21, "is_day": True}},
        "keepsakes": {
            "slots": {
                "shelf_2": {"title": "星砂玻璃瓶", "sender": "小爱"},
                "desk_2": {"title": "海边明信片", "sender": "阿木"},
            }
        },
        "mailbox": {"unopened_count": 0, "visitors": [], "latest_opened": {"parcel_id": "m1", "keepsake_slot": "desk_2"}},
        "ecology": {"cat": {"spot": "window_perch"}, "vitality": {"mood_label": "惬意"}},
    }
    plan_default = resolve_shot_plan(snap, "keepsake")
    assert plan_default["mode"] == "keepsake"
    assert plan_default["focus"] == "desk"
    assert plan_default["focus_slot"] == "desk_2"

    plan_shelf = resolve_shot_plan(snap, "keepsake", focus_slot="shelf_2")
    assert plan_shelf["focus"] == "shelf"

    renderer = PostcardRenderer(tmp_path, cache_ttl_seconds=45.0)
    res1 = await renderer.render(snap, prefer_3d=False, shot_mode="keepsake", focus_slot="shelf_2")
    assert res1["renderer"] == "2d_fallback"
    assert res1["renderer_badge"] == "2D 像素降级"
    assert res1["fallback_hint"] == FALLBACK_2D_HINT
    assert res1["cached"] is False
    assert Path(res1["path"]).is_file()

    # Second identical call within 45s hits cache
    res2 = await renderer.render(snap, prefer_3d=False, shot_mode="keepsake", focus_slot="shelf_2")
    assert res2["cached"] is True
    assert res2["path"] == res1["path"]

    # Explicit invalidation clears cache
    renderer.invalidate_cache()
    res3 = await renderer.render(snap, prefer_3d=False, shot_mode="keepsake", focus_slot="shelf_2")
    assert res3["cached"] is False


@pytest.mark.asyncio
async def test_world_journal_card_collector_and_pillow_render(tmp_path: Path):
    engine, clock_box = _make_engine(tmp_path)
    try:
        engine.mailbox.deliver_parcel(
            SCOPE,
            sender_id="u1",
            sender_name="旅人甲",
            kind="postcard",
            title="秋日来信",
            message="窗外枫叶红了",
            bypass_cooldown=True,
        )
        await engine.mailbox.open_pending_parcels_async(SCOPE, max_open=1)
        data = collect_world_journal_data(
            engine,
            SCOPE,
            character={"name": "夏目安安"},
            now=clock_box[0],
        )
        assert data["character_name"] == "夏目安安"
        assert data["mailbox"]["items"]
        assert data["cat"]["spot_label"]

        png_bytes = render_world_journal_card(data)
        img = Image.open(BytesIO(png_bytes))
        assert img.format == "PNG"
        assert img.size == (840, 1080)

        saved = save_world_journal_card(tmp_path, data)
        assert saved["ok"] is True
        assert Path(saved["path"]).is_file()
        assert "每日世界手账" in saved["summary_text"]
        assert "夏目安安" in format_world_journal_text(data)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_world_journal_command_and_public_hook(tmp_path: Path, monkeypatch):
    from astrbot_plugin_dynamics_world.main import Main

    engine, clock_box = _make_engine(tmp_path)
    try:
        plugin = object.__new__(Main)
        plugin.data_root = tmp_path
        plugin.config = {
            "runtime_enabled": True,
            "group_cabin_commands_enabled": True,
            "cabin_postcard_cooldown_seconds": 180,
        }
        plugin.postcards = PostcardRenderer(tmp_path)
        plugin.runtime_allowed = lambda: True

        async def _scope_for_event(_ev):
            return dict(SCOPE)

        async def _char_ctx(_scope, _ev):
            return {"name": "夏目安安"}

        plugin.life = types.SimpleNamespace(
            narrative=engine,
            _scope_for_event=_scope_for_event,
        )
        plugin.world = types.SimpleNamespace(get_character_context=_char_ctx)

        # Public hook for Chat Dynamics rhythm
        hook_res = await plugin.build_daily_world_journal(SCOPE, now=clock_box[0])
        assert hook_res["ok"] is True
        assert Path(hook_res["path"]).is_file()

        # Command execution + cooldown check
        class _DummyEvent:
            def plain_result(self, text):
                return ("plain", text)

            def image_result(self, path):
                return ("image", path)

        results1 = [r async for r in plugin.world_journal_command(_DummyEvent(), "")]
        assert len(results1) == 1
        assert results1[0][0] == "image"
        assert Path(results1[0][1]).is_file()

        results2 = [r async for r in plugin.world_journal_command(_DummyEvent(), "")]
        assert len(results2) == 1
        assert results2[0][0] == "plain"
        assert "冷却中" in results2[0][1]
    finally:
        await engine.close()


def test_wave2_frontend_and_schema_contracts():
    studio_js = (ROOT / "pages" / "world" / "workbench-studio.js").read_text("utf-8")
    assert "wbEntrySearch" in studio_js
    assert "wbEntryConstFilter" in studio_js
    assert "wbEntryEnabledFilter" in studio_js
    assert "wbEntryScenarioFilter" in studio_js
    assert "wbBatchEnable" in studio_js
    assert "wbBatchDisable" in studio_js
    assert "wbExportBook" in studio_js
    assert "wbExportCard" in studio_js
    assert 'accept=".json,.png"' in studio_js
    assert "parsePngCharaChunk" in studio_js
    assert "wb-book-chips" in studio_js
    assert 'multiple size="2"' not in studio_js

    cabin_js = (ROOT / "pages" / "world" / "pixel-cabin.js").read_text("utf-8")
    assert "activate2DFallback" in cabin_js
    assert "renderSchematic" in cabin_js
    assert "cabinShortcutVisual" in cabin_js
    assert "cabinShortcutAvatar" in cabin_js
    assert "is-inspect-open" in cabin_js
    assert "cabinPostcardBadge" in cabin_js

    cabin_css = (ROOT / "pages" / "world" / "cabin3d.css").read_text("utf-8")
    assert "@media(max-width:650px)" in cabin_css
    assert ".cabin-stage.is-inspect-open .cabin-timeline-bar" in cabin_css

    inspect_js = (ROOT / "pages" / "world" / "cabin-inspect.js").read_text("utf-8")
    assert "chair:" in inspect_js and "lamp:" in inspect_js
    assert "['desk','chair','lamp']" in inspect_js

    schematic_js = (ROOT / "pages" / "world" / "room-schematic.js").read_text("utf-8")
    assert "onMoveFurniture" in schematic_js
    assert "SURFACE_SLOTS" in schematic_js

    vis_js = (ROOT / "pages" / "world" / "visual-editor.js").read_text("utf-8")
    assert "visUploadAutoApply" in vis_js
    assert "上传并立即应用" in vis_js

    avatar_js = (ROOT / "pages" / "world" / "cabin-avatar-ui.js").read_text("utf-8")
    assert "avatarUploadAutoApply" in avatar_js
    assert "上传并立即应用" in avatar_js

    creative_js = (ROOT / "pages" / "world" / "creative-world.js").read_text("utf-8")
    assert "worldStream.subscribe" in creative_js
    assert "10000" not in creative_js

    schema_text = (ROOT / "_conf_schema.json").read_text("utf-8")
    schema = json.loads(schema_text)
    assert "[Legacy 兼容]" in schema["session_list_mode"]["description"]
    assert "[Legacy 兼容]" in schema["prompt_template"]["description"]
    assert "管理面板 → 插件 → 世界书" not in schema_text

    world_service_text = (ROOT / "world" / "service.py").read_text("utf-8")
    assert "管理面板 → 插件 → 世界书" not in world_service_text

    index_html = (ROOT / "pages" / "world" / "index.html").read_text("utf-8")
    assert "管理面板 → 插件 → 世界书" not in index_html
