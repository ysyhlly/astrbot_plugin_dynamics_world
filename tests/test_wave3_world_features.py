# ruff: noqa: E402
"""Wave 3 verification tests: external keepsakes, event bus, coop garden & tea party, bookshelf & bookmarks, travel postcard, resident map & neighbor onboarding."""
from __future__ import annotations

import base64
import sys
import types
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT.parent) not in sys.path:
    sys.path.insert(0, str(ROOT.parent))

from astrbot_plugin_dynamics_world.causal_api import _worldbook_neighbor_candidates
from astrbot_plugin_dynamics_world.garden_ecology import EcologyService
from astrbot_plugin_dynamics_world.keepsakes import KeepsakeTimelineService, bookshelf_volumes
from astrbot_plugin_dynamics_world.life.core.narrative import NarrativeEngine
from astrbot_plugin_dynamics_world.mailbox_visitors import MailboxVisitorService
from astrbot_plugin_dynamics_world.main import Main, parse_mailbox_delivery_with_title
from astrbot_plugin_dynamics_world.postcard_renderer import (
    PostcardRenderer,
    is_actor_away,
    parse_shot_override,
)
from astrbot_plugin_dynamics_world.scenes import SceneService
from astrbot_plugin_dynamics_world.spatial import SpatialState

SCOPE = {
    "persona_id": "persona_wave3",
    "character_id": "char_wave3",
    "umo": "default:GroupMessage:wave3_grp",
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
    engine.spatial = SpatialState(engine)
    engine.keepsakes = KeepsakeTimelineService(engine)
    engine.ecology = EcologyService(engine)
    engine.mailbox = MailboxVisitorService(engine)
    engine.scenes = SceneService(engine)
    return engine, t


@pytest.mark.asyncio
async def test_external_keepsake_dedupe_thumbnail_and_event_bus(tmp_path: Path):
    engine, _ = _make_engine(tmp_path)
    try:
        # Create a small PNG cover image
        img_path = tmp_path / "poster.png"
        Image.new("RGB", (400, 300), (88, 142, 112)).save(img_path, format="PNG")

        plugin = object.__new__(Main)
        plugin.data_root = tmp_path
        plugin.config = {"persona_id": SCOPE["persona_id"], "runtime_enabled": True}
        plugin.life = types.SimpleNamespace(narrative=engine)
        plugin.postcards = PostcardRenderer(tmp_path)
        plugin.web = types.SimpleNamespace(bus=types.SimpleNamespace(notify=lambda: None))
        plugin._event_bus_subs = []

        # Fake chat_dynamics event bus companion
        handlers = {}

        class _FakeChat:
            def subscribe_dynamics_event(self, ev_type, cb, *, owner=""):
                tok = f"tok_{ev_type}_{owner}"
                handlers[tok] = (ev_type, cb)
                return tok

            def unsubscribe_dynamics_event(self, tok):
                return handlers.pop(tok, None) is not None

        fake_chat = _FakeChat()
        plugin.onboarding = types.SimpleNamespace(
            companion=lambda pid: (True, fake_chat) if pid == "astrbot_plugin_chat_dynamics" else (False, None)
        )
        plugin._subscribe_series_event_bus()
        assert len(handlers) == 1

        # Fire milestone_achieved event
        _, cb = next(iter(handlers.values()))
        res1 = cb(
            {
                "persona_id": SCOPE["persona_id"],
                "umo": SCOPE["umo"],
                "title": "群友接龙画报",
                "summary": "共同完成十二棒奇幻接龙！",
                "sender_name": "全体群友",
                "source_plugin": "astrbot_plugin_dynamics_games",
                "deep_link": "games",
                "image_path": str(img_path),
                "kind": "game_poster",
            }
        )
        assert res1["ok"] is True
        assert res1["deduplicated"] is False
        assert res1["item"]["source_label"] == "群间游戏"
        assert res1["item"]["image_data_url"].startswith("data:image/jpeg;base64,")
        assert res1["item"]["deep_link"] == "games"

        # Deduplicate identical registration
        res2 = plugin.register_external_keepsake(
            persona_id=SCOPE["persona_id"],
            umo=SCOPE["umo"],
            title="群友接龙画报",
            summary="更新摘要",
            sender_name="全体群友",
            source_plugin="astrbot_plugin_dynamics_games",
            deep_link="javascript:alert(1)",  # must be stripped!
            kind="game_poster",
        )
        assert res2["ok"] is True
        assert res2["deduplicated"] is True
        assert res2["item"]["deep_link"] == "games"

        plugin._unsubscribe_series_event_bus()
        assert len(handlers) == 0
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_coop_garden_watering_and_solar_tea_party(tmp_path: Path):
    engine, clock_box = _make_engine(tmp_path)
    try:
        # User 1 waters once
        r1 = await engine.ecology.coop_water_async(
            SCOPE, user_id="u1", display_name="小爱", note="早安浇水", cooldown_seconds=300, daily_limit=2
        )
        assert r1["ok"] is True
        assert r1["flower_progress"] >= 63

        # Immediate repeat by u1 blocked by cooldown
        with pytest.raises(ValueError, match="刚刚"):
            await engine.ecology.coop_water_async(
                SCOPE, user_id="u1", display_name="小爱", cooldown_seconds=300, daily_limit=2
            )

        # User 2 waters -> triggers blooming / solar-term tea party
        r2 = await engine.ecology.coop_water_async(
            SCOPE, user_id="u2", display_name="阿木", note="一起种花", cooldown_seconds=300, daily_limit=2
        )
        assert r2["tea_party"]["triggered"] is True
        assert "小爱" in r2["tea_party"]["participants"]
        assert "阿木" in r2["tea_party"]["participants"]

        # Verify table_snack keepsake placed
        with engine._db(notify=False) as db:
            ks = engine.keepsakes.snapshot(db, SCOPE, {}, clock_box[0])
            assert "table_snack" in ks["slots"]
            assert "茶点" in ks["slots"]["table_snack"]["title"]

        # Advance clock past cooldown and hit daily cap for u1
        clock_box[0] += 400
        await engine.ecology.coop_water_async(
            SCOPE, user_id="u1", display_name="小爱", cooldown_seconds=300, daily_limit=2
        )
        clock_box[0] += 400
        with pytest.raises(ValueError, match="2 次"):
            await engine.ecology.coop_water_async(
                SCOPE, user_id="u1", display_name="小爱", cooldown_seconds=300, daily_limit=2
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_bookshelf_privacy_filter_and_book_review_bookmarks(tmp_path: Path):
    kind, title, review = parse_mailbox_delivery_with_title("书评 《雨夜手记》 结尾的雨声描写很有画面感")
    assert kind == "book_review"
    assert title == "雨夜手记"
    assert "画面感" in review

    # Public vs private book filter
    fake_scene = {
        "projects": {
            "p_pub": {
                "id": "p_pub",
                "title": "雨夜手记",
                "status": "completed",
                "visibility": "public",
                "sections": [{"title": "第一章", "text": "窗外淅淅沥沥下起了秋雨。"}],
            },
            "p_priv": {
                "id": "p_priv",
                "title": "私密日记",
                "status": "completed",
                "visibility": "private",
                "sections": [{"title": "密", "text": "不公开内容"}],
            },
        }
    }
    pub_vols = bookshelf_volumes(fake_scene, public_only=True)
    assert [v["title"] for v in pub_vols] == ["雨夜手记"]

    engine, clock_box = _make_engine(tmp_path)
    try:
        # Deliver a book review parcel & open it -> becomes a bookmark on the volume
        engine.mailbox.deliver_parcel(
            SCOPE,
            sender_id="u_reader",
            sender_name="林风",
            kind="book_review",
            title="雨夜手记",
            message="结尾的雨声描写很有画面感",
            bypass_cooldown=True,
        )
        opened = await engine.mailbox.open_pending_parcels_async(SCOPE, max_open=2)
        assert len(opened) == 1
        assert opened[0]["kind"] == "book_review"

        with engine._db(notify=False) as db:
            ks = engine.keepsakes.snapshot(db, SCOPE, fake_scene, clock_box[0])
            pub = next(v for v in ks["bookshelf_volumes"] if v["title"] == "雨夜手记")
            assert len(pub["bookmarks"]) == 1
            assert pub["bookmarks"][0]["sender_name"] == "林风"
            assert "画面感" in pub["bookmarks"][0]["review"]
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_travel_scenery_postcard_auto_and_explicit_room_override(tmp_path: Path):
    mode, rest = parse_shot_override("旅途 海风真舒服")
    assert mode == "travel"
    assert rest == "海风真舒服"

    # Prepare a tiny virtual map data URL to test cropping
    buf = BytesIO()
    Image.new("RGB", (600, 400), (168, 198, 152)).save(buf, format="PNG")
    map_url = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

    away_snap = {
        "server_time": 1764200000.0,
        "character": {"name": "夏目安安"},
        "outfit_now": "米色风衣",
        "map": {"map_type": "virtual", "width": 1200, "height": 800, "image": map_url, "places": []},
        "actor": {
            "phase": "travelling",
            "position": [600, 400],
            "progress": 0.62,
            "journey": {"destination_name": "海畔灯塔", "arrives_at": 1764201800.0},
        },
        "scene": {
            "phase": "travelling",
            "destination": "海畔灯塔",
            "place_id": "lighthouse",
            "rooms": [{"id": "r1", "place_id": "home"}],
        },
        "environment": {"available": True, "current": {"label": "多云", "effect": "cloud", "temperature": 19, "is_day": True}},
        "ecology": {"cat": {"spot": "window_perch"}, "vitality": {"mood_label": "期待"}},
    }
    assert is_actor_away(away_snap) is True

    renderer = PostcardRenderer(tmp_path)
    # Default auto mode switches to Travel Scenery Postcard
    res_travel = await renderer.render(away_snap, prefer_3d=False, shot_mode="auto")
    assert res_travel["renderer"] == "travel_postcard"
    assert res_travel["renderer_badge"] == "旅途风景明信片"
    img = Image.open(res_travel["path"])
    assert img.size == (800, 640)

    # Explicit room override (/小屋实况 室内) still renders interior empty cabin & cat
    res_room = await renderer.render(away_snap, prefer_3d=False, shot_mode="room")
    assert res_room["renderer"] == "2d_fallback"
    assert res_room["shot_plan"]["mode"] == "room"


def test_worldbook_neighbor_candidates_and_wave3_frontend_contracts():
    class _FakeEntry:
        def __init__(self, name, content, keys=None, enabled=True):
            self.name = name
            self.content = content
            self.keys = keys or []
            self.enabled = enabled

    class _FakeBook:
        def __init__(self, name, entries):
            self.name = name
            self.entries = entries
            self.enabled = True

    class _FakeStore:
        def list_books(self):
            return [
                _FakeBook(
                    "小镇世界书",
                    [
                        _FakeEntry("花店老板阿青", "性格温和的邻里角色，每天清晨整理洋甘菊。", ["阿青"]),
                        _FakeEntry("夏目安安", "主角色设定", ["安安"]),
                        _FakeEntry("规则说明", "这是一段很长的系统规则描述而非具体人物", []),
                    ],
                )
            ]

    cands = _worldbook_neighbor_candidates(_FakeStore(), exclude_names={"夏目安安"})
    assert len(cands) == 1
    assert cands[0]["name"] == "花店老板阿青"

    map_js = (ROOT / "pages" / "world" / "map.js").read_text("utf-8")
    assert "renderResidentsOnMap" in map_js
    assert "residentVisibleToSelf" in map_js
    assert "dw-resident-avatar" in map_js
    assert "dashArray" in map_js

    causal_js = (ROOT / "pages" / "world" / "causal-panel.js").read_text("utf-8")
    assert "renderNeighborOnboarding" in causal_js
    assert "quick_register_neighbor" in causal_js
    assert "worldbook_characters" in causal_js

    inspect_js = (ROOT / "pages" / "world" / "cabin-inspect.js").read_text("utf-8")
    assert "cabin-keepsake-gallery" in inspect_js
    assert "cabin-keepsake-source" in inspect_js
    assert "群友夹页书签" in inspect_js
