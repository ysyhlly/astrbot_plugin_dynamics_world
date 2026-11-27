"""Offscreen 3D Polaroid snapshot renderer with idle-hibernating Chromium hot pool + Pillow fallback."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

try:
    from .series_panels import (
        get_series_memory_watermark,
        get_series_resource_limits,
        heavy_subprocess_slot,
        resolve_series_resource_profile,
        resolve_series_timezone,
        try_malloc_trim,
    )
except Exception:  # pragma: no cover - isolated import fallback
    from datetime import timedelta, timezone

    def resolve_series_timezone(_ctx=None, explicit_tz: str = "", default_tz: str = "Asia/Shanghai"):
        return timezone(timedelta(hours=8))

    def resolve_series_resource_profile(_ctx=None) -> str:
        return "standard"

    def get_series_resource_limits(_ctx=None, *, profile: str | None = None) -> dict[str, Any]:
        return {
            "profile": profile or "standard",
            "world_postcard_idle_timeout_s": 180.0,
            "world_prefer_3d": True,
        }

    def get_series_memory_watermark(_ctx=None, *, force_refresh: bool = False) -> dict[str, Any]:
        return {"state": "ok", "rss_mb": 0.0}

    @asynccontextmanager
    async def heavy_subprocess_slot(_ctx, purpose: str, *, plugin_id: str = "", timeout: float | None = None):
        yield {"purpose": purpose, "plugin_id": plugin_id}

    def try_malloc_trim(*_args, **_kwargs) -> bool:
        return False


class _NullLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass


try:
    from astrbot.api import logger
except Exception:  # pragma: no cover
    logger = _NullLogger()

POSTCARD_CACHE_TTL_SECONDS = 45.0
FALLBACK_2D_HINT = (
    "当前使用 2D 像素降级渲染；在管理面板「安装引导」安装 Playwright Chromium 后可切换为 3D 实景拍立得。"
)

CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
    "--enable-webgl",
    "--ignore-gpu-blocklist",
    "--js-flags=--max-old-space-size=128",
    "--renderer-process-limit=1",
    "--disable-extensions",
    "--disable-background-networking",
    "--mute-audio",
    "--no-first-run",
    "--disable-component-update",
]

_BROWSER_SNAPSHOT_STRIP_KEYS = frozenset({
    "map",
    "avatar_model",
    "guest_avatar_model",
})


def _sanitize_snapshot_for_browser(snapshot: dict) -> dict:
    """Strip multi-MB unused blobs (map PNG/graph, duplicated avatar models) before CDP evaluate."""
    if not isinstance(snapshot, dict):
        return {}
    return {
        k: v for k, v in snapshot.items() if k not in _BROWSER_SNAPSHOT_STRIP_KEYS
    }

OUTFIT_KEYWORDS: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("睡衣", "居家", "睡袍", "night", "pajama", "sleep"), ("sleep", "pajama", "night", "home", "睡", "居")),
    (("雨衣", "外套", "风衣", "rain", "coat"), ("coat", "rain", "outer", "jacket", "外", "雨")),
    (("围裙", "下厨", "备餐", "cook", "apron"), ("apron", "cook", "maid", "kitchen", "厨", "围裙")),
    (("制服", "学院", "正装", "school", "uniform"), ("uniform", "school", "formal", "制", "校")),
    (("夏", "短袖", "连衣裙", "summer", "dress"), ("summer", "dress", "light", "夏", "裙")),
    (("冬", "毛衣", "围巾", "大衣", "winter", "sweater"), ("winter", "warm", "sweater", "scarf", "冬", "毛衣")),
)


def match_outfit_texture(texture_names: list[str] | tuple[str, ...], outfit_text: str, default_index: int = 0) -> int:
    """Match an outfit description to a YSM texture name, falling back to default_index."""
    if not texture_names:
        return 0
    fallback = default_index if 0 <= int(default_index or 0) < len(texture_names) else 0
    outfit = str(outfit_text or "").strip().lower()
    if not outfit:
        return fallback
    lowered = [str(n or "").lower() for n in texture_names]
    for i, name in enumerate(lowered):
        stem = name.rsplit(".", 1)[0]
        if stem and len(stem) >= 2 and stem in outfit:
            return i
    for triggers, targets in OUTFIT_KEYWORDS:
        if any(t in outfit for t in triggers):
            for i, name in enumerate(lowered):
                if any(tok in name for tok in targets):
                    return i
    return fallback


def parse_shot_override(raw_text: str) -> tuple[str, str]:
    """Extract optional leading framing keyword ('全景'/'近景'/'院门'/'纪念格') and remaining caption."""
    text = str(raw_text or "").strip()
    if not text:
        return "auto", ""
    parts = text.split(None, 1)
    head = parts[0].strip().lower()
    rest = parts[1].strip() if len(parts) > 1 else ""
    mapping = {
        "全景": "garden",
        "花园": "garden",
        "庭院": "garden",
        "远景": "garden",
        "garden": "garden",
        "wide": "garden",
        "近景": "room",
        "室内": "room",
        "房间": "room",
        "特写": "room",
        "room": "room",
        "closeup": "room",
        "院门": "gate",
        "信箱": "gate",
        "门口": "gate",
        "gate": "gate",
        "纪念格": "keepsake",
        "纪念品": "keepsake",
        "书架": "keepsake",
        "陈列": "keepsake",
        "keepsake": "keepsake",
        "shelf": "keepsake",
        "旅途": "travel",
        "旅行": "travel",
        "风景": "travel",
        "travel": "travel",
    }
    if head in mapping:
        return mapping[head], rest
    return "auto", text


def is_actor_away(snapshot: dict) -> bool:
    """Return True when the character is travelling or located outside any home place."""
    scene = snapshot.get("scene") or {}
    actor = snapshot.get("actor") or {}
    if scene.get("phase") == "travelling" or actor.get("phase") == "travelling":
        return True
    if actor.get("journey"):
        return True
    rooms = scene.get("rooms") or []
    home_places = {r.get("place_id") for r in rooms if isinstance(r, dict) and r.get("place_id")}
    cur_place = scene.get("place_id") or actor.get("place_id")
    return bool(home_places and cur_place and cur_place not in home_places)


def render_travel_postcard_image(snapshot: dict, *, caption: str = "") -> bytes:
    """Render a dual-map Travel Scenery Postcard (local map/route + live weather + avatar + postmark)."""
    W, H = 800, 640
    card = Image.new("RGB", (W, H), (247, 241, 228))
    draw = ImageDraw.Draw(card, "RGBA")
    # Vintage postcard border & airmail stripes
    draw.rounded_rectangle((14, 14, W - 14, H - 14), radius=18, outline=(198, 184, 160), width=2)
    for sx in range(28, W - 36, 36):
        color = (182, 78, 72) if (sx // 36) % 2 == 0 else (66, 108, 142)
        draw.rectangle((sx, 20, sx + 18, 25), fill=color)

    scene = snapshot.get("scene") or {}
    actor = snapshot.get("actor") or {}
    journey = actor.get("journey") if isinstance(actor.get("journey"), dict) else None
    env = snapshot.get("environment") or {}
    cur = env.get("current") or {}
    map_doc = snapshot.get("map") if isinstance(snapshot.get("map"), dict) else {}
    char_name = str((snapshot.get("character") or {}).get("name") or "旅人")[:18]

    tz = resolve_series_timezone(None, explicit_tz=str(env.get("timezone") or ""))
    now = float(snapshot.get("server_time") or datetime.now().timestamp())
    local = datetime.fromtimestamp(now, tz)

    # Map viewport box
    mx0, my0, mx1, my1 = 36, 44, 520, 446
    mw, mh = mx1 - mx0, my1 - my0
    map_bg = Image.new("RGB", (mw, mh), (232, 224, 204))
    mdraw = ImageDraw.Draw(map_bg, "RGBA")

    # Try embedding cropped virtual map image if available
    embedded_map = False
    raw_img = str(map_doc.get("image") or "")
    if raw_img.startswith("data:image/") and "," in raw_img:
        try:
            raw_bytes = base64.b64decode(raw_img.split(",", 1)[1])
            with Image.open(BytesIO(raw_bytes)) as src_map:
                src_map = src_map.convert("RGB")
                sw, sh = src_map.size
                doc_w = float(map_doc.get("width") or sw or 1200)
                doc_h = float(map_doc.get("height") or sh or 800)
                pos = actor.get("position")
                if isinstance(pos, (list, tuple)) and len(pos) == 2:
                    cx = max(0.0, min(1.0, float(pos[0]) / max(1.0, doc_w))) * sw
                    cy = max(0.0, min(1.0, float(pos[1]) / max(1.0, doc_h))) * sh
                else:
                    cx, cy = sw * 0.5, sh * 0.5
                crop_w = min(sw, max(360, int(sw * 0.55)))
                crop_h = min(sh, int(crop_w * (mh / mw)))
                left = int(max(0, min(sw - crop_w, cx - crop_w / 2)))
                top = int(max(0, min(sh - crop_h, cy - crop_h / 2)))
                cropped = src_map.crop((left, top, left + crop_w, top + crop_h)).resize((mw, mh), Image.Resampling.BILINEAR)
                map_bg.paste(cropped, (0, 0))
                mdraw = ImageDraw.Draw(map_bg, "RGBA")
                embedded_map = True
        except Exception:
            embedded_map = False

    if not embedded_map:
        # Stylized parchment contour map
        for gy in range(24, mh, 34):
            mdraw.line((0, gy, mw, gy), fill=(214, 204, 182, 130), width=1)
        for gx in range(24, mw, 34):
            mdraw.line((gx, 0, gx, mh), fill=(214, 204, 182, 130), width=1)
        mdraw.arc((-60, 120, 320, 440), 200, 355, fill=(142, 174, 184, 170), width=10)
        mdraw.polygon([(60, 290), (140, 210), (220, 290)], fill=(176, 188, 162, 130))
        mdraw.polygon([(260, 240), (350, 145), (440, 240)], fill=(166, 178, 152, 140))

    # Draw dashed journey route & origin/destination pins
    p_start = (92, mh - 96)
    p_end = (mw - 92, 98)
    progress = float(actor.get("progress") or (0.55 if journey else 1.0))
    progress = max(0.08, min(1.0, progress))
    cur_x = int(p_start[0] + (p_end[0] - p_start[0]) * progress)
    cur_y = int(p_start[1] + (p_end[1] - p_start[1]) * progress)
    steps = 16
    for i in range(steps):
        if i % 2 == 0:
            t0, t1 = i / steps, min(1.0, (i + 0.7) / steps)
            x0 = int(p_start[0] + (p_end[0] - p_start[0]) * t0)
            y0 = int(p_start[1] + (p_end[1] - p_start[1]) * t0)
            x1 = int(p_start[0] + (p_end[0] - p_start[0]) * t1)
            y1 = int(p_start[1] + (p_end[1] - p_start[1]) * t1)
            mdraw.line((x0, y0, x1, y1), fill=(42, 108, 82, 235), width=4)

    mdraw.ellipse((p_start[0] - 7, p_start[1] - 7, p_start[0] + 7, p_start[1] + 7), fill=(154, 118, 72), outline=(255, 255, 255), width=2)
    mdraw.ellipse((p_end[0] - 8, p_end[1] - 8, p_end[0] + 8, p_end[1] + 8), fill=(186, 76, 68), outline=(255, 255, 255), width=2)
    mdraw.ellipse((cur_x - 14, cur_y - 14, cur_x + 14, cur_y + 14), fill=(38, 104, 78), outline=(252, 248, 238), width=3)
    mdraw.text((cur_x - 6, cur_y - 9), char_name[:1], fill=(255, 252, 244), font=_load_font(15))

    dest_name = str(
        (journey or {}).get("destination_name")
        or scene.get("destination")
        or actor.get("place_name")
        or scene.get("place_name")
        or "远方地标"
    )[:18]
    origin_name = str(actor.get("origin_name") or "小屋出发")[:14]
    map_mode_tag = "现实地图 · 旅途足迹" if map_doc.get("map_type") == "real" else "世界地图 · 旅途风景"
    mdraw.rounded_rectangle((12, 12, 210, 42), radius=10, fill=(32, 46, 38, 196))
    mdraw.text((22, 18), map_mode_tag, fill=(244, 240, 228), font=_load_font(14))
    mdraw.rounded_rectangle((p_end[0] - 76, p_end[1] + 14, p_end[0] + 76, p_end[1] + 40), radius=8, fill=(252, 247, 236, 224))
    mdraw.text((p_end[0] - 66, p_end[1] + 18), dest_name, fill=(58, 44, 34), font=_load_font(14))
    if journey:
        mdraw.text((p_start[0] - 28, p_start[1] + 14), origin_name, fill=(84, 68, 52), font=_load_font(13))

    card.paste(map_bg, (mx0, my0))
    draw.rectangle((mx0, my0, mx1, my1), outline=(182, 168, 146), width=2)

    # Right sidebar: Weather + Character Medallion + Postmark Stamp
    rx0, rx1 = 540, W - 36
    draw.rounded_rectangle((rx0, 44, rx1, 206), radius=14, fill=(253, 250, 244), outline=(216, 206, 188), width=2)
    wx_effect = str(cur.get("effect") or "clear")
    is_day = cur.get("is_day", True)
    wx_label = str(cur.get("label") or "晴")
    temp_val = cur.get("temperature")
    temp_str = f"{round(float(temp_val))}°C" if temp_val is not None else "--°C"
    # Draw weather icon
    icx, icy = rx0 + 46, 94
    if not is_day and wx_effect == "clear":
        draw.ellipse((icx - 18, icy - 18, icx + 18, icy + 18), fill=(238, 214, 134))
        draw.ellipse((icx - 10, icy - 22, icx + 22, icy + 10), fill=(253, 250, 244))
    elif wx_effect in {"rain", "snow"}:
        draw.rounded_rectangle((icx - 22, icy - 12, icx + 22, icy + 6), radius=10, fill=(134, 152, 166))
        drop_color = (94, 146, 198) if wx_effect == "rain" else (182, 206, 224)
        for dx in (-12, 0, 12):
            draw.ellipse((icx + dx - 3, icy + 10, icx + dx + 3, icy + 18), fill=drop_color)
    elif wx_effect == "cloud":
        draw.rounded_rectangle((icx - 22, icy - 10, icx + 22, icy + 10), radius=10, fill=(172, 182, 188))
    else:
        draw.ellipse((icx - 18, icy - 18, icx + 18, icy + 18), fill=(242, 188, 78))
    draw.text((rx0 + 82, 70), wx_label, fill=(56, 48, 40), font=_load_font(22))
    draw.text((rx0 + 82, 102), f"{temp_str} · {'白昼' if is_day else '夜色'}", fill=(108, 94, 78), font=_load_font(16))
    draw.line((rx0 + 18, 138, rx1 - 18, 138), fill=(232, 224, 210), width=1)
    status_line = f"正在前往 {dest_name}" if journey else f"驻足于 {dest_name}"
    draw.text((rx0 + 18, 150), status_line[:16], fill=(44, 92, 70), font=_load_font(16))
    draw.text((rx0 + 18, 176), f"行程进度 {int(round(progress * 100))}%", fill=(128, 114, 98), font=_load_font(14))

    # Character medallion & circular postmark stamp
    draw.rounded_rectangle((rx0, 222, rx1, 446), radius=14, fill=(253, 250, 244), outline=(216, 206, 188), width=2)
    draw.ellipse((rx0 + 22, 240, rx0 + 86, 304), fill=(52, 104, 80), outline=(228, 216, 194), width=3)
    draw.text((rx0 + 42, 256), char_name[:1], fill=(252, 248, 238), font=_load_font(28))
    draw.text((rx0 + 98, 250), char_name[:10], fill=(48, 40, 34), font=_load_font(20))
    outfit = str(snapshot.get("outfit_now") or "旅途便装")[:12]
    draw.text((rx0 + 98, 280), f"穿搭：{outfit}", fill=(122, 108, 92), font=_load_font(14))

    # Circular postal stamp
    scx, scy = (rx0 + rx1) // 2, 376
    draw.ellipse((scx - 52, scy - 52, scx + 52, scy + 52), outline=(168, 76, 68, 205), width=3)
    draw.ellipse((scx - 42, scy - 42, scx + 42, scy + 42), outline=(168, 76, 68, 155), width=1)
    draw.text((scx - 34, scy - 24), "POSTMARK", fill=(168, 76, 68, 210), font=_load_font(11))
    draw.text((scx - 32, scy - 6), dest_name[:5], fill=(154, 62, 56, 230), font=_load_font(14))
    draw.text((scx - 36, scy + 16), local.strftime("%Y.%m.%d"), fill=(168, 76, 68, 210), font=_load_font(12))

    # Bottom caption strip
    draw.rounded_rectangle((36, 466, W - 36, H - 36), radius=14, fill=(254, 251, 245), outline=(216, 206, 188), width=2)
    note = str(
        caption
        or snapshot.get("activity")
        or snapshot.get("plan_now")
        or (f"在前往{dest_name}的路上寄出一张旅途风景明信片。" if journey else f"在{dest_name}漫步，把此刻的风景寄给你。")
    ).strip()[:52]
    draw.text((56, 486), f"✈ {char_name} 的旅途风景明信片 · {dest_name}", fill=(46, 78, 62), font=_load_font(22))
    draw.text((56, 524), f"「{note}」", fill=(78, 64, 52), font=_load_font(18))
    draw.text(
        (56, 562),
        f"{local.strftime('%Y-%m-%d %H:%M')}  |  {wx_label} {temp_str}  |  发送 /小屋实况 室内 可查看留守小屋与猫咪",
        fill=(136, 120, 102),
        font=_load_font(15),
    )

    out = BytesIO()
    card.save(out, format="PNG", optimize=True)
    return out.getvalue()


def resolve_shot_plan(
    snapshot: dict, shot_mode: str = "auto", *, focus_slot: str = ""
) -> dict:
    """Auto-Director camera framing based on character presence, visitors and current station."""
    mode = str(shot_mode or "auto").strip().lower()
    mode_alias = {
        "全景": "garden",
        "花园": "garden",
        "wide": "garden",
        "近景": "room",
        "室内": "room",
        "closeup": "room",
        "院门": "gate",
        "信箱": "gate",
        "mailbox": "gate",
        "纪念格": "keepsake",
        "纪念品": "keepsake",
        "书架": "keepsake",
        "shelf": "keepsake",
    }
    mode = mode_alias.get(mode, mode)
    scene = snapshot.get("scene") or {}
    actor = snapshot.get("actor") or {}
    mailbox = snapshot.get("mailbox") or {}
    world_space = snapshot.get("world_space") or {}
    rooms = scene.get("rooms") or []
    home_places = {r.get("place_id") for r in rooms if isinstance(r, dict) and r.get("place_id")}
    away = bool(
        scene.get("phase") == "travelling"
        or actor.get("journey")
        or (home_places and (scene.get("place_id") or actor.get("place_id")) not in home_places)
    )

    act_obj = scene.get("action") or {}
    steps = act_obj.get("steps") or []
    idx = int(act_obj.get("index") or 0)
    cur_step = steps[idx] if isinstance(steps, list) and 0 <= idx < len(steps) and isinstance(steps[idx], dict) else {}
    act_kind = str(cur_step.get("kind") or "")
    act_code = str(snapshot.get("activity_code") or "")
    act_text = " ".join(
        str(x or "")
        for x in (act_obj.get("label"), snapshot.get("plan_now"), snapshot.get("activity"))
    )

    def _pick_room_station() -> str | None:
        if act_code in {"sleeping", "resting"} or act_kind == "rest" or any(k in act_text for k in ("睡", "躺", "午休", "小憩", "安眠")):
            return "bed"
        if act_code == "eating" or act_kind in {"prepare_meal", "brew_tea", "drink", "refill"} or any(k in act_text for k in ("茶", "餐", "饭", "厨", "煮", "喝水", "料理")):
            return "kitchen"
        if act_code in {"studying", "working", "reading"} or act_kind in {
            "read",
            "write_note",
            "computer_work",
            "project_create",
            "project_draft",
            "project_revise",
            "project_finish",
        } or any(k in act_text for k in ("书", "写", "记", "电脑", "稿", "读", "创作")):
            return "desk"
        return None

    if mode == "garden":
        return {"mode": "garden", "view": "garden", "focus": None}
    if mode == "gate":
        return {"mode": "gate", "view": "garden", "focus": "gate"}
    if mode == "keepsake":
        slot_key = str(focus_slot or "").strip().lower()
        if not slot_key:
            latest = mailbox.get("latest_opened") if isinstance(mailbox, dict) else None
            if isinstance(latest, dict):
                slot_key = str(latest.get("keepsake_slot") or "").strip().lower()
        focus_target = "desk" if slot_key.startswith(("desk", "table")) else "window" if "window" in slot_key else "shelf"
        return {
            "mode": "keepsake",
            "view": "room",
            "focus": focus_target,
            "focus_slot": slot_key or "shelf_2",
        }
    if mode == "room":
        return {"mode": "room", "view": "room", "focus": _pick_room_station()}

    # Auto-Director:
    if away:
        return {"mode": "gate", "view": "garden", "focus": "gate"}
    sel = snapshot.get("avatar_selection") or {}
    in_garden_room = bool(sel.get("garden_room_id") and scene.get("room_id") == sel.get("garden_room_id"))
    garden_busy = (
        in_garden_room
        or act_kind in {"water_garden", "harvest_garden", "open_mailbox", "rain_walk"}
        or any(k in act_text for k in ("花园", "庭院", "浇水", "采摘", "院门", "信箱", "散步"))
        or bool(mailbox.get("visitors"))
        or bool(world_space.get("active_guest"))
    )
    if garden_busy:
        return {"mode": "garden", "view": "garden", "focus": None}
    return {"mode": "room", "view": "room", "focus": _pick_room_station()}


@lru_cache(maxsize=16)
def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size = max(8, int(size))
    candidates = (
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    )
    for path in candidates:
        if Path(path).is_file():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()


def _postcard_local_time(snapshot: dict, env: dict, now: float) -> datetime:
    tz_name = str(env.get("timezone") or snapshot.get("timezone") or "")
    tz = resolve_series_timezone(None, explicit_tz=tz_name)
    try:
        return datetime.fromtimestamp(now, tz)
    except Exception:
        return datetime.fromtimestamp(now)


def _draw_pixel_cabin_artwork(snapshot: dict, width: int = 720, height: int = 460) -> Image.Image:
    """Crisp cozy pixel-art cabin & garden scene reflecting live hour, weather, curtains, lamp & cat."""
    env = snapshot.get("environment") or {}
    cur = env.get("current") or {}
    now = float(snapshot.get("server_time") or 0) or datetime.now().timestamp()
    local = _postcard_local_time(snapshot, env, now)
    hour = local.hour + local.minute / 60.0
    effect = str(cur.get("effect") or "clear")
    is_night = hour < 6.0 or hour >= 19.2
    is_dusk = (6.0 <= hour < 7.5) or (17.2 <= hour < 19.2)

    if is_night:
        sky_top, sky_bot = (24, 32, 56), (44, 58, 92)
    elif is_dusk:
        sky_top, sky_bot = (112, 86, 128), (228, 152, 108)
    elif effect in {"rain", "snow", "fog"}:
        sky_top, sky_bot = (118, 136, 154), (168, 182, 194)
    else:
        sky_top, sky_bot = (122, 178, 224), (196, 226, 244)

    pw, ph = width // 4, height // 4
    canvas = Image.new("RGB", (pw, ph), sky_top)
    draw = ImageDraw.Draw(canvas)

    for y in range(62):
        t = y / 61.0
        col = tuple(int(sky_top[i] * (1 - t) + sky_bot[i] * t) for i in range(3))
        draw.line([(0, y), (pw, y)], fill=col)

    if is_night:
        for sx, sy in ((22, 14), (48, 9), (86, 18), (132, 11), (158, 21), (112, 7)):
            draw.point((sx, sy), fill=(246, 240, 200))
    elif effect == "clear":
        draw.ellipse((142, 10, 158, 26), fill=(255, 236, 166))

    eco = snapshot.get("ecology") or {}
    palette = (eco.get("season") or {}).get("palette") or {}
    grass_hex = str(palette.get("grass") or "#6ea85b").lstrip("#")
    foliage_hex = str(palette.get("foliage") or "#52934b").lstrip("#")
    grass_rgb = tuple(int(grass_hex[i : i + 2], 16) for i in (0, 2, 4))
    if is_night:
        grass_rgb = tuple(max(18, int(c * 0.48)) for c in grass_rgb)
    foliage_rgb = tuple(int(foliage_hex[i : i + 2], 16) for i in (0, 2, 4))
    if is_night:
        foliage_rgb = tuple(max(20, int(c * 0.52)) for c in foliage_rgb)

    draw.rectangle((0, 62, pw, ph), fill=grass_rgb)
    for step_y in range(82, 112, 5):
        draw.rectangle((82, step_y, 96, step_y + 3), fill=(184, 174, 158))

    for tx in (18, 154):
        draw.rectangle((tx + 5, 48, tx + 9, 68), fill=(104, 72, 48))
        draw.ellipse((tx - 4, 28, tx + 18, 54), fill=foliage_rgb)

    draw.polygon([(46, 44), (90, 22), (134, 44)], fill=(138, 78, 58))
    draw.rectangle((52, 44, 128, 82), fill=(224, 204, 176))
    draw.rectangle((52, 76, 128, 82), fill=(132, 116, 102))

    scene = snapshot.get("scene") or {}
    designs = scene.get("room_designs") or []
    lighting = (designs[0].get("lighting") if designs else None) or ("warm" if is_night or is_dusk else "bright")
    curtains = (designs[0].get("curtains") if designs else None) or "open"
    win_glow = {
        "bright": (255, 242, 192),
        "warm": (255, 204, 122),
        "dim": (182, 138, 88),
        "off": (56, 68, 86),
    }.get(lighting, (255, 210, 136))

    draw.rectangle((62, 52, 84, 68), fill=win_glow, outline=(96, 68, 48))
    if curtains == "closed":
        draw.rectangle((63, 53, 83, 67), fill=(198, 168, 142))
    elif curtains == "half":
        draw.rectangle((63, 53, 69, 67), fill=(198, 168, 142))
        draw.rectangle((77, 53, 83, 67), fill=(198, 168, 142))

    draw.rectangle((96, 54, 110, 81), fill=(122, 82, 54), outline=(82, 52, 34))

    draw.ellipse((14, 84, 48, 102), fill=(78, 148, 178) if not is_night else (42, 84, 112))
    draw.rectangle((124, 84, 162, 102), fill=(112, 82, 56))
    veg_stage = str(((eco.get("veg_patch") or {}).get("stage")) or "growing")
    crop_h = 4 if veg_stage == "ripe" else 2
    for cx in range(128, 158, 7):
        draw.rectangle((cx, 88 - crop_h, cx + 3, 92), fill=(96, 176, 78))
        if veg_stage == "ripe":
            draw.rectangle((cx + 1, 93, cx + 4, 96), fill=(232, 142, 52))

    mailbox = snapshot.get("mailbox") or {}
    draw.rectangle((104, 92, 106, 104), fill=(108, 78, 52))
    draw.rectangle((101, 87, 109, 93), fill=(74, 106, 138))
    if int(mailbox.get("unopened_count") or 0) > 0:
        draw.rectangle((109, 85, 112, 89), fill=(224, 72, 64))

    away = scene.get("phase") == "travelling" or (
        scene.get("rooms")
        and scene.get("place_id") not in {r.get("place_id") for r in scene.get("rooms", []) if isinstance(r, dict)}
    )
    if not away:
        draw.rectangle((72, 56, 76, 65), fill=(74, 62, 88))
        draw.rectangle((72, 53, 76, 56), fill=(242, 212, 192))

    cat_spot = str(((eco.get("cat") or {}).get("spot")) or "bed_nap")
    cat_xy = (100, 100) if cat_spot == "gate_wait" else (46, 88) if cat_spot == "pond_watch" else (78, 64)
    draw.rectangle((cat_xy[0], cat_xy[1], cat_xy[0] + 4, cat_xy[1] + 3), fill=(236, 168, 96))

    if effect == "rain":
        for i in range(36):
            rx = (i * 29 + 11) % (pw - 4)
            ry = (i * 19 + 7) % (ph - 10)
            draw.line([(rx, ry), (rx - 2, ry + 5)], fill=(186, 214, 240))
    elif effect == "snow":
        for i in range(32):
            sx = (i * 31 + 9) % (pw - 4)
            sy = (i * 23 + 5) % (ph - 6)
            draw.rectangle((sx, sy, sx + 1, sy + 1), fill=(248, 252, 255))

    return canvas.resize((width, height), Image.Resampling.NEAREST)


def compose_polaroid(art: Image.Image, snapshot: dict, note_override: str = "") -> bytes:
    """Frame a 720x460 render into an 800x640 warm Polaroid card with caption & stamp."""
    art = art.convert("RGB").resize((720, 460), Image.Resampling.BICUBIC)
    card = Image.new("RGB", (800, 640), (250, 245, 235))
    draw = ImageDraw.Draw(card)

    draw.rectangle((0, 0, 799, 639), outline=(222, 210, 192), width=3)
    draw.rectangle((38, 34, 762, 498), fill=(214, 202, 186))
    card.paste(art, (40, 36))

    env = snapshot.get("environment") or {}
    cur = env.get("current") or {}
    now = float(snapshot.get("server_time") or 0) or datetime.now().timestamp()
    local = _postcard_local_time(snapshot, env, now)

    char_name = str(((snapshot.get("character") or {}).get("name")) or "小屋主人")
    scene = snapshot.get("scene") or {}
    place_label = str(scene.get("place_name") or "小屋")
    if scene.get("room_name") and scene.get("room_id"):
        place_label += f" · {scene['room_name']}"
    elif scene.get("phase") == "travelling" and scene.get("destination"):
        place_label = f"前往 {scene['destination']} 途中"

    weather_str = str(cur.get("label") or "晴")
    if cur.get("temperature") is not None:
        weather_str += f" {round(float(cur['temperature']))}°C"

    eco = snapshot.get("ecology") or {}
    vitality = eco.get("vitality") or {}
    mood_str = str(vitality.get("mood_label") or vitality.get("mood") or "平和自在")
    activity_raw = str(
        note_override
        or ((scene.get("action") or {}).get("label"))
        or snapshot.get("plan_now")
        or snapshot.get("activity")
        or "在小屋度过安静的一刻"
    )
    if len(activity_raw) > 46:
        activity_raw = activity_raw[:45] + "…"

    font_title = _load_font(24)
    font_sub = _load_font(18)
    font_stamp = _load_font(16)

    draw.text((44, 518), f"{char_name} · {place_label}", fill=(58, 44, 34), font=font_title)
    draw.text((44, 556), f"「{activity_raw}」", fill=(96, 76, 60), font=font_sub)
    stamp = f"{local.strftime('%Y-%m-%d %H:%M')}  |  {weather_str}  |  {mood_str}"
    draw.text((44, 594), stamp, fill=(142, 122, 102), font=font_stamp)

    out = BytesIO()
    card.save(out, format="PNG", optimize=True)
    return out.getvalue()


class PostcardRenderer:
    """Rate-limited Polaroid snapshot generator with idle-hibernating warm 3D Chromium pool."""

    def __init__(
        self,
        data_root: Path,
        *,
        idle_timeout: float | None = None,
        cache_ttl_seconds: float = POSTCARD_CACHE_TTL_SECONDS,
        context: Any = None,
    ):
        self.out_dir = Path(data_root) / "postcards"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._context = context
        self._cooldowns: dict[str, float] = {}
        self._sem = asyncio.Semaphore(1)
        self._pool_lock = asyncio.Lock()
        self._explicit_idle_timeout: float | None = (
            max(0.0, float(idle_timeout)) if idle_timeout is not None else None
        )
        self.cache_ttl_seconds = max(0.0, float(cache_ttl_seconds))
        self._render_cache: dict[str, tuple[float, dict]] = {}
        self._pw = None
        self._browser = None
        self._page = None
        self._bundle_mtime: float = 0.0
        self._last_used: float = 0.0
        self._reaper_task: asyncio.Task | None = None
        self._closed = False

    def _resource_limits(self) -> dict[str, Any]:
        return get_series_resource_limits(self._context)

    def _resource_profile(self) -> str:
        return resolve_series_resource_profile(self._context)

    def _effective_idle_timeout(self) -> float:
        if self._explicit_idle_timeout is not None:
            return self._explicit_idle_timeout
        limits = self._resource_limits()
        return max(0.0, float(limits.get("world_postcard_idle_timeout_s", 180.0)))

    @property
    def idle_timeout(self) -> float:
        return self._effective_idle_timeout()

    @idle_timeout.setter
    def idle_timeout(self, value: float) -> None:
        self._explicit_idle_timeout = max(0.0, float(value))

    def _render_cache_max_entries(self) -> int:
        return 8 if self._resource_profile() != "standard" else 32

    def _store_cache_entry(self, cache_key: str, result: dict) -> None:
        if self.cache_ttl_seconds <= 0:
            return
        self._render_cache[cache_key] = (time.monotonic(), dict(result))
        max_entries = self._render_cache_max_entries()
        while len(self._render_cache) > max_entries:
            oldest_key = min(self._render_cache, key=lambda k: self._render_cache[k][0])
            self._render_cache.pop(oldest_key, None)

    def invalidate_cache(self) -> None:
        """Clear cached postcard renders immediately when world state mutates."""
        self._render_cache.clear()

    @staticmethod
    def _build_cache_key(
        snapshot: dict,
        shot_plan: dict,
        caption: str,
        prefer_3d: bool,
    ) -> str:
        scene = snapshot.get("scene") or {}
        env = snapshot.get("environment") or {}
        cur = env.get("current") or {}
        mailbox = snapshot.get("mailbox") or {}
        keepsakes = snapshot.get("keepsakes") or {}
        eco = snapshot.get("ecology") or {}
        sig_payload = {
            "shot": shot_plan,
            "caption": str(caption or ""),
            "prefer_3d": bool(prefer_3d),
            "char": (snapshot.get("character") or {}).get("name", ""),
            "style": snapshot.get("cabin_style", ""),
            "place": scene.get("place_id", ""),
            "room": scene.get("room_id", ""),
            "phase": scene.get("phase", ""),
            "action": (scene.get("action") or {}).get("label", ""),
            "revision": scene.get("revision", 0),
            "wx": (cur.get("effect"), cur.get("label"), cur.get("temperature"), cur.get("is_day")),
            "mail": (
                mailbox.get("unopened_count", 0),
                (mailbox.get("latest_opened") or {}).get("parcel_id", ""),
                len(mailbox.get("visitors") or []),
            ),
            "ks": sorted((keepsakes.get("slots") or {}).keys()) if isinstance(keepsakes.get("slots"), dict) else [],
            "cat": (eco.get("cat") or {}).get("spot", ""),
        }
        raw = json.dumps(sig_payload, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]

    @property
    def is_warm(self) -> bool:
        return self._browser is not None and self._page is not None

    def check_cooldown(self, key: str, now: float, cooldown_seconds: int) -> int:
        if cooldown_seconds <= 0:
            return 0
        last = self._cooldowns.get(key, 0.0)
        if now - last < cooldown_seconds:
            return max(1, int(cooldown_seconds - (now - last)))
        return 0

    def mark_used(self, key: str, now: float) -> None:
        self._cooldowns[key] = now
        if len(self._cooldowns) > 512:
            cutoff = now - 86400
            self._cooldowns = {k: v for k, v in self._cooldowns.items() if v >= cutoff}

    async def _shutdown_pool_locked(self) -> None:
        page, browser, pw = self._page, self._browser, self._pw
        self._page = None
        self._browser = None
        self._pw = None
        self._bundle_mtime = 0.0
        for resource, method in ((page, "close"), (browser, "close"), (pw, "stop")):
            if resource is not None:
                try:
                    await getattr(resource, method)()
                except Exception:
                    pass

    async def hibernate_if_idle(self) -> bool:
        """Close the warm Chromium instance if idle longer than idle_timeout."""
        timeout = self._effective_idle_timeout()
        async with self._pool_lock:
            if self._browser is None:
                return False
            if timeout > 0.0 and time.monotonic() - self._last_used < timeout:
                return False
            await self._shutdown_pool_locked()
            return True

    async def hibernate_now(self) -> None:
        """Force-close the warm Chromium instance immediately without marking renderer closed."""
        task = self._reaper_task
        self._reaper_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        await self._safe_shutdown_pool()

    async def _reaper_loop(self) -> None:
        timeout = self._effective_idle_timeout()
        if timeout <= 0.0:
            return
        interval = max(0.25, min(30.0, timeout / 3.0))
        try:
            while not self._closed:
                await asyncio.sleep(interval)
                if self._closed:
                    break
                if self._browser is None:
                    break
                cur_timeout = self._effective_idle_timeout()
                if (
                    cur_timeout <= 0.0
                    or time.monotonic() - self._last_used >= cur_timeout
                ) and not self._sem.locked():
                    async with self._sem:
                        if await self.hibernate_if_idle():
                            break
        except asyncio.CancelledError:
            pass

    async def close(self) -> None:
        """Terminate warm Chromium pool and idle reaper cleanly on plugin unload."""
        self._closed = True
        task = self._reaper_task
        self._reaper_task = None
        if task is not None and not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        async with self._pool_lock:
            await self._shutdown_pool_locked()

    async def _safe_shutdown_pool(self, *, timeout: float = 3.0) -> None:
        """Acquire pool lock and tear down Playwright/Chromium cleanly even on cancellation."""
        async def _do():
            async with self._pool_lock:
                await self._shutdown_pool_locked()

        try:
            await asyncio.wait_for(asyncio.shield(_do()), timeout=timeout)
        except BaseException:
            pass

    async def _ensure_warm_page(self, bundle_path: Path):
        from playwright.async_api import async_playwright

        mtime = bundle_path.stat().st_mtime
        whale_art_path = bundle_path.with_name("deepseek-whale-maid.jpg")
        async with self._pool_lock:
            if self._closed:
                return None
            need_reload = self._page is None or self._browser is None or (hasattr(self._page, "is_closed") and self._page.is_closed()) or self._bundle_mtime != mtime
            if need_reload:
                try:
                    if self._browser is None:
                        self._pw = await async_playwright().start()
                        self._browser = await self._pw.chromium.launch(headless=True, args=CHROMIUM_ARGS)
                    if self._page is not None:
                        try:
                            await self._page.close()
                        except Exception:
                            pass
                        self._page = None
                    self._page = await self._browser.new_page(viewport={"width": 720, "height": 460})
                    bundle_js = await asyncio.to_thread(bundle_path.read_bytes)
                    module_url = "data:text/javascript;base64," + base64.b64encode(bundle_js).decode("ascii")
                    whale_art_url = ""
                    if whale_art_path.is_file():
                        whale_bytes = await asyncio.to_thread(whale_art_path.read_bytes)
                        whale_art_url = "data:image/jpeg;base64," + base64.b64encode(whale_bytes).decode("ascii")
                    html = (
                        "<!doctype html><html><body style='margin:0;overflow:hidden;background:#1b1714'>"
                        "<div id='stage' style='width:720px;height:460px;position:relative'></div></body></html>"
                    )
                    await self._page.set_content(html)
                    boot_ok = await self._page.evaluate(
                        """async ([modUrl, whaleUrl]) => {
                            if (whaleUrl) window.__CABIN_WHALE_ART_URL__ = whaleUrl;
                            const mod = await import(modUrl);
                            if (!mod || typeof mod.createCabin3D !== 'function') return false;
                            const stage = document.getElementById('stage');
                            const cabin = mod.createCabin3D(stage, { reducedMotion: true });
                            if (!cabin) return false;
                            try {
                                const gl = cabin.canvas?.getContext('webgl2') || cabin.canvas?.getContext('webgl');
                                const dbg = gl?.getExtension('WEBGL_debug_renderer_info');
                                const rdr = dbg ? String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) || '') : '';
                                if (/swiftshader|llvmpipe|software/i.test(rdr)) {
                                    cabin.setQualityMode?.('low');
                                }
                            } catch {}
                            cabin.setEffects?.(false);
                            cabin.setActive?.(false);
                            window.__cabin = cabin;
                            window.__modelKey = '';
                            window.__guestKey = '';
                            return Boolean(stage.querySelector('canvas'));
                        }""",
                        [module_url, whale_art_url],
                    )
                    if not boot_ok:
                        await self._shutdown_pool_locked()
                        return None
                    self._bundle_mtime = mtime
                except BaseException:
                    try:
                        await asyncio.wait_for(asyncio.shield(self._shutdown_pool_locked()), timeout=3.0)
                    except BaseException:
                        pass
                    raise
            self._last_used = time.monotonic()
            if self._effective_idle_timeout() > 0.0 and (
                self._reaper_task is None or self._reaper_task.done()
            ):
                self._reaper_task = asyncio.create_task(self._reaper_loop())
            return self._page

    async def _try_playwright_capture(self, snapshot: dict, plugin_dir: Path, shot_plan: dict) -> Image.Image | None:
        """Render real Three.js cabin3d.min.js + custom YSM model in warm Chromium page."""
        bundle_path = plugin_dir / "pages" / "world" / "cabin3d.min.js"
        if not bundle_path.is_file():
            return None
        async with heavy_subprocess_slot(
            self._context,
            "world_3d_postcard",
            plugin_id="astrbot_plugin_dynamics_world",
        ):
            try:
                page = await self._ensure_warm_page(bundle_path)
                if page is None:
                    return None

                env = snapshot.get("environment") or {}
                cur = env.get("current") or {}
                now = float(snapshot.get("server_time") or 0) or datetime.now().timestamp()
                local = _postcard_local_time(snapshot, env, now)
                hour = local.hour + local.minute / 60.0
                effect = str(cur.get("effect") or "clear")
                eco = snapshot.get("ecology") or {}
                designs = (snapshot.get("scene") or {}).get("room_designs") or []
                room_design = designs[0] if designs else {}
                keepsakes = snapshot.get("keepsakes") or {}
                mailbox = snapshot.get("mailbox") or {}
                avatar_model = snapshot.get("avatar_model")
                avatar_tex = int(snapshot.get("avatar_texture_index") or 0)
                avatar_sel = snapshot.get("avatar_selection") or {}
                guest_model = snapshot.get("guest_avatar_model")
                guest_tex = int(snapshot.get("guest_texture_index") or 0)
                cabin_style = str(
                    snapshot.get("cabin_style")
                    or (snapshot.get("cabin") or {}).get("style")
                    or "cottage"
                ).strip() or "cottage"
                slim_snapshot = _sanitize_snapshot_for_browser(snapshot)

                data_url = await page.evaluate(
                    """async (cfg) => {
                        const cabin = window.__cabin;
                        if (!cabin) return null;
                        let texLoaded = false;
                        const modelId = cfg.avatarModel?.id || 'builtin';
                        const nextKey = `${modelId}:${cfg.avatarTex}`;
                        if (window.__modelKey !== nextKey) {
                            cabin.setAvatarModel?.(cfg.avatarModel || { id: 'builtin', format: 'builtin' }, cfg.avatarTex || 0);
                            window.__modelKey = nextKey;
                            texLoaded = true;
                        }
                        if (cfg.guestModel) {
                            const gKey = `${cfg.guestModel.id || 'builtin'}:${cfg.guestTex || 0}`;
                            if (window.__guestKey !== gKey && typeof cabin.setGuestAvatarModel === 'function') {
                                cabin.setGuestAvatarModel(cfg.guestModel, cfg.guestTex || 0);
                                window.__guestKey = gKey;
                                texLoaded = true;
                            }
                        } else if (window.__guestKey && typeof cabin.setGuestAvatarModel === 'function') {
                            cabin.setGuestAvatarModel(null, 0);
                            window.__guestKey = '';
                        }
                        const applyAll = () => {
                            const tm = cfg.hour < 5.5 || cfg.hour >= 19.5 ? 'night' : cfg.hour < 7.2 ? 'dawn' : cfg.hour >= 17.2 ? 'dusk' : 'day';
                            if (cfg.cabinStyle && typeof cabin.setCabinStyle === 'function') {
                                cabin.setCabinStyle(cfg.cabinStyle);
                            }
                            cabin.setTimeMode?.('auto');
                            if (cfg.snapshot?.environment) {
                                cabin.setEnvironment?.(cfg.snapshot.environment, cfg.snapshot.server_time, cfg.snapshot.scene?.items || []);
                            } else {
                                cabin.setTimeMode?.(tm);
                                cabin.setWeatherOverride?.(cfg.effect);
                            }
                            cabin.setSeason?.(cfg.season);
                            cabin.setEcology?.(cfg.ecology);
                            cabin.setRoomDesign?.(cfg.roomDesign, cfg.snapshot?.scene?.items || [], cfg.snapshot?.server_time);
                            cabin.setKeepsakes?.(cfg.keepsakes);
                            cabin.setMailbox?.(cfg.mailbox);
                            cabin.setCatState?.(cfg.cat, true);
                            if (cfg.snapshot) {
                                cabin.setActorState?.({ ...cfg.snapshot, isReplay: true }, cfg.avatarSelection || {});
                            }
                            if (typeof cabin.setShotPreset === 'function') {
                                cabin.setShotPreset(cfg.shotPlan, true);
                            } else {
                                cabin.setView?.(cfg.shotPlan?.view || 'garden');
                                if (cfg.shotPlan?.focus) cabin.focusTarget?.(cfg.shotPlan.focus);
                                else cabin.clearFocus?.();
                            }
                        };
                        if (typeof cabin.batch === 'function') cabin.batch(applyAll);
                        else applyAll();
                        if (texLoaded || cfg.cabinStyle === 'whale_coast') {
                            await new Promise(r => setTimeout(r, 80));
                        }
                        cabin.setActive?.(false);
                        if (typeof cabin.captureDataURL === 'function') {
                            return cabin.captureDataURL('image/png');
                        }
                        return null;
                    }""",
                    {
                        "hour": hour,
                        "effect": effect,
                        "season": eco.get("season"),
                        "ecology": eco,
                        "roomDesign": room_design,
                        "keepsakes": keepsakes,
                        "mailbox": mailbox,
                        "cat": eco.get("cat"),
                        "snapshot": slim_snapshot,
                        "avatarModel": avatar_model,
                        "avatarTex": avatar_tex,
                        "avatarSelection": avatar_sel,
                        "guestModel": guest_model,
                        "guestTex": guest_tex,
                        "cabinStyle": cabin_style,
                        "shotPlan": shot_plan,
                    },
                )
                self._last_used = time.monotonic()
                if isinstance(data_url, str) and data_url.startswith("data:image/png;base64,"):
                    raw_png = base64.b64decode(data_url.split(",", 1)[1])
                    img = Image.open(BytesIO(raw_png))
                else:
                    raw_png = await page.locator("#stage canvas").first.screenshot(type="png", animations="disabled")
                    self._last_used = time.monotonic()
                    img = Image.open(BytesIO(raw_png))
                if self._effective_idle_timeout() <= 0.0:
                    await self._safe_shutdown_pool()
                    try_malloc_trim()
                return img
            except asyncio.CancelledError:
                await self._safe_shutdown_pool()
                raise
            except Exception:
                await self._safe_shutdown_pool()
                return None
            except BaseException:
                await self._safe_shutdown_pool()
                raise

    async def render(
        self,
        snapshot: dict,
        *,
        plugin_dir: Path | None = None,
        caption: str = "",
        prefer_3d: bool = True,
        force_3d: bool = False,
        shot_mode: str = "auto",
        focus_slot: str = "",
        bypass_cache: bool = False,
    ) -> dict:
        norm_mode = str(shot_mode or "auto").strip().lower()
        want_travel = norm_mode in {"travel", "旅途", "旅行", "风景"} or (
            norm_mode == "auto" and is_actor_away(snapshot)
        )
        if want_travel:
            shot_plan = {"mode": "travel", "view": "map", "focus": "travel"}
            effective_caption = str(caption or "").strip()
            cache_key = self._build_cache_key(snapshot, shot_plan, effective_caption, False)
            if not bypass_cache and self.cache_ttl_seconds > 0:
                cached_entry = self._render_cache.get(cache_key)
                if cached_entry is not None:
                    cached_at, cached_res = cached_entry
                    if (
                        time.monotonic() - cached_at <= self.cache_ttl_seconds
                        and Path(str(cached_res.get("path") or "")).is_file()
                    ):
                        hit = dict(cached_res)
                        hit["cached"] = True
                        return hit
                    self._render_cache.pop(cache_key, None)
            png_bytes = await asyncio.to_thread(
                render_travel_postcard_image, snapshot, caption=effective_caption
            )
            now = float(snapshot.get("server_time") or datetime.now().timestamp())
            digest = hashlib.sha256(png_bytes).hexdigest()[:14]
            out_path = self.out_dir / f"postcard_{int(now)}_{digest}.png"
            await asyncio.to_thread(out_path.write_bytes, png_bytes)
            existing = sorted(self.out_dir.glob("postcard_*.png"), key=lambda p: p.stat().st_mtime)
            for stale in existing[:-40]:
                stale.unlink(missing_ok=True)
            result = {
                "path": str(out_path),
                "bytes": len(png_bytes),
                "renderer": "travel_postcard",
                "renderer_badge": "旅途风景明信片",
                "fallback_hint": "",
                "cached": False,
                "shot_plan": shot_plan,
                "data_url": "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii"),
            }
            self._store_cache_entry(cache_key, result)
            logger.info("[DynamicsWorld] Travel postcard rendered bytes=%d", len(png_bytes))
            return result

        shot_plan = resolve_shot_plan(snapshot, shot_mode, focus_slot=focus_slot)
        effective_caption = str(caption or "").strip()
        if not effective_caption and shot_plan.get("mode") == "keepsake":
            ks_slots = (snapshot.get("keepsakes") or {}).get("slots") or {}
            chosen_slot = shot_plan.get("focus_slot") or ""
            slot_item = ks_slots.get(chosen_slot) if isinstance(ks_slots, dict) else None
            if isinstance(slot_item, dict) and slot_item.get("title"):
                sender = slot_item.get("sender") or ""
                effective_caption = (
                    f"纪念格特写：{sender}送来的「{slot_item['title']}」"
                    if sender
                    else f"纪念格特写：「{slot_item['title']}」"
                )
            else:
                effective_caption = "纪念格陈列拍立得特写"

        limits = self._resource_limits()
        effective_prefer_3d = bool(prefer_3d)
        if effective_prefer_3d and not force_3d and not bool(limits.get("world_prefer_3d", True)):
            effective_prefer_3d = False
        if effective_prefer_3d:
            watermark = get_series_memory_watermark(self._context)
            if str(watermark.get("state") or "ok") == "hard":
                logger.info(
                    "[DynamicsWorld] Memory watermark=hard (rss=%.1f MiB); falling back to 2D pixel cabin",
                    float(watermark.get("rss_mb") or 0.0),
                )
                effective_prefer_3d = False

        cache_key = self._build_cache_key(snapshot, shot_plan, effective_caption, effective_prefer_3d)
        if not bypass_cache and self.cache_ttl_seconds > 0:
            cached_entry = self._render_cache.get(cache_key)
            if cached_entry is not None:
                cached_at, cached_res = cached_entry
                if (
                    time.monotonic() - cached_at <= self.cache_ttl_seconds
                    and Path(str(cached_res.get("path") or "")).is_file()
                ):
                    hit = dict(cached_res)
                    hit["cached"] = True
                    logger.info(
                        "[DynamicsWorld] Postcard cache hit renderer=%s mode=%s",
                        hit.get("renderer"),
                        shot_plan.get("mode"),
                    )
                    return hit
                self._render_cache.pop(cache_key, None)

        async with self._sem:
            art = None
            renderer_kind = "2d_fallback"
            if effective_prefer_3d and plugin_dir is not None and not self._closed:
                try:
                    art = await asyncio.wait_for(self._try_playwright_capture(snapshot, plugin_dir, shot_plan), timeout=12.0)
                    if art is not None:
                        renderer_kind = "3d"
                except Exception:
                    art = None
            if art is None:
                art = await asyncio.to_thread(_draw_pixel_cabin_artwork, snapshot, 720, 460)
                if shot_plan.get("mode") == "keepsake":
                    def _stamp_keepsake_ribbon(img: Image.Image) -> Image.Image:
                        copy_img = img.copy()
                        d = ImageDraw.Draw(copy_img, "RGBA")
                        d.rounded_rectangle((18, 16, 336, 56), radius=12, fill=(36, 28, 22, 188))
                        d.text((32, 26), f"✦ 纪念格特写 · {shot_plan.get('focus_slot') or 'shelf'}", fill=(252, 240, 214), font=_load_font(17))
                        return copy_img

                    prev_art = art
                    art = await asyncio.to_thread(_stamp_keepsake_ribbon, art)
                    try:
                        prev_art.close()
                    except Exception:
                        pass
            try:
                png_bytes = await asyncio.to_thread(compose_polaroid, art, snapshot, effective_caption)
            finally:
                try:
                    art.close()
                except Exception:
                    pass
            now = float(snapshot.get("server_time") or datetime.now().timestamp())
            digest = hashlib.sha256(png_bytes).hexdigest()[:14]
            out_path = self.out_dir / f"postcard_{int(now)}_{digest}.png"
            await asyncio.to_thread(out_path.write_bytes, png_bytes)
            existing = sorted(self.out_dir.glob("postcard_*.png"), key=lambda p: p.stat().st_mtime)
            for stale in existing[:-40]:
                stale.unlink(missing_ok=True)
            is_3d = renderer_kind == "3d"
            result = {
                "path": str(out_path),
                "bytes": len(png_bytes),
                "renderer": renderer_kind,
                "renderer_badge": "3D 实时渲染" if is_3d else "2D 像素降级",
                "fallback_hint": "" if is_3d else FALLBACK_2D_HINT,
                "cached": False,
                "shot_plan": shot_plan,
                "data_url": "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii"),
            }
            self._store_cache_entry(cache_key, result)
            logger.info(
                "[DynamicsWorld] Postcard rendered renderer=%s mode=%s cached=False bytes=%d",
                renderer_kind,
                shot_plan.get("mode"),
                len(png_bytes),
            )
            return result
