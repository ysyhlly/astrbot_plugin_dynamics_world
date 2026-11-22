"""Offscreen 3D Polaroid snapshot renderer with idle-hibernating Chromium hot pool + Pillow fallback."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .series_panels import resolve_series_timezone

CHROMIUM_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
    "--enable-webgl",
    "--ignore-gpu-blocklist",
]

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
    """Extract optional leading framing keyword ('全景'/'近景'/'院门') and remaining caption."""
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
    }
    if head in mapping:
        return mapping[head], rest
    return "auto", text


def resolve_shot_plan(snapshot: dict, shot_mode: str = "auto") -> dict:
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


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
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

    def __init__(self, data_root: Path, *, idle_timeout: float = 300.0):
        self.out_dir = Path(data_root) / "postcards"
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._cooldowns: dict[str, float] = {}
        self._sem = asyncio.Semaphore(1)
        self._pool_lock = asyncio.Lock()
        self.idle_timeout = max(1.0, float(idle_timeout))
        self._pw = None
        self._browser = None
        self._page = None
        self._bundle_mtime: float = 0.0
        self._last_used: float = 0.0
        self._reaper_task: asyncio.Task | None = None
        self._closed = False

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
        async with self._pool_lock:
            if self._browser is None:
                return False
            if time.monotonic() - self._last_used < self.idle_timeout:
                return False
            await self._shutdown_pool_locked()
            return True

    async def _reaper_loop(self) -> None:
        interval = max(0.25, min(30.0, self.idle_timeout / 3.0))
        try:
            while not self._closed:
                await asyncio.sleep(interval)
                if self._closed:
                    break
                if self._browser is None:
                    break
                if time.monotonic() - self._last_used >= self.idle_timeout and not self._sem.locked():
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

    async def _ensure_warm_page(self, bundle_path: Path):
        from playwright.async_api import async_playwright

        mtime = bundle_path.stat().st_mtime
        async with self._pool_lock:
            if self._closed:
                return None
            need_reload = self._page is None or self._browser is None or (hasattr(self._page, "is_closed") and self._page.is_closed()) or self._bundle_mtime != mtime
            if need_reload:
                if self._browser is None:
                    self._pw = await async_playwright().start()
                    self._browser = await self._pw.chromium.launch(headless=True, args=CHROMIUM_ARGS)
                if self._page is not None:
                    try:
                        await self._page.close()
                    except Exception:
                        pass
                self._page = await self._browser.new_page(viewport={"width": 720, "height": 460})
                bundle_js = await asyncio.to_thread(bundle_path.read_bytes)
                module_url = "data:text/javascript;base64," + base64.b64encode(bundle_js).decode("ascii")
                html = (
                    "<!doctype html><html><body style='margin:0;overflow:hidden;background:#1b1714'>"
                    "<div id='stage' style='width:720px;height:460px;position:relative'></div></body></html>"
                )
                await self._page.set_content(html)
                boot_ok = await self._page.evaluate(
                    """async (modUrl) => {
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
                    module_url,
                )
                if not boot_ok:
                    await self._shutdown_pool_locked()
                    return None
                self._bundle_mtime = mtime
            self._last_used = time.monotonic()
            if self._reaper_task is None or self._reaper_task.done():
                self._reaper_task = asyncio.create_task(self._reaper_loop())
            return self._page

    async def _try_playwright_capture(self, snapshot: dict, plugin_dir: Path, shot_plan: dict) -> Image.Image | None:
        """Render real Three.js cabin3d.min.js + custom YSM model in warm Chromium page."""
        bundle_path = plugin_dir / "pages" / "world" / "cabin3d.min.js"
        if not bundle_path.is_file():
            return None
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
                    if (texLoaded) {
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
                    "snapshot": snapshot,
                    "avatarModel": avatar_model,
                    "avatarTex": avatar_tex,
                    "avatarSelection": avatar_sel,
                    "guestModel": guest_model,
                    "guestTex": guest_tex,
                    "shotPlan": shot_plan,
                },
            )
            self._last_used = time.monotonic()
            if isinstance(data_url, str) and data_url.startswith("data:image/png;base64,"):
                raw_png = base64.b64decode(data_url.split(",", 1)[1])
                return Image.open(BytesIO(raw_png))
            raw_png = await page.locator("#stage canvas").first.screenshot(type="png", animations="disabled")
            self._last_used = time.monotonic()
            return Image.open(BytesIO(raw_png))
        except Exception:
            async with self._pool_lock:
                await self._shutdown_pool_locked()
            return None

    async def render(
        self,
        snapshot: dict,
        *,
        plugin_dir: Path | None = None,
        caption: str = "",
        prefer_3d: bool = True,
        shot_mode: str = "auto",
    ) -> dict:
        shot_plan = resolve_shot_plan(snapshot, shot_mode)
        async with self._sem:
            art = None
            renderer_kind = "2d_fallback"
            if prefer_3d and plugin_dir is not None and not self._closed:
                try:
                    art = await asyncio.wait_for(self._try_playwright_capture(snapshot, plugin_dir, shot_plan), timeout=12.0)
                    if art is not None:
                        renderer_kind = "3d"
                except Exception:
                    art = None
            if art is None:
                art = await asyncio.to_thread(_draw_pixel_cabin_artwork, snapshot, 720, 460)
            png_bytes = await asyncio.to_thread(compose_polaroid, art, snapshot, caption)
            now = float(snapshot.get("server_time") or datetime.now().timestamp())
            digest = hashlib.sha256(png_bytes).hexdigest()[:14]
            out_path = self.out_dir / f"postcard_{int(now)}_{digest}.png"
            await asyncio.to_thread(out_path.write_bytes, png_bytes)
            existing = sorted(self.out_dir.glob("postcard_*.png"), key=lambda p: p.stat().st_mtime)
            for stale in existing[:-40]:
                stale.unlink(missing_ok=True)
            return {
                "path": str(out_path),
                "bytes": len(png_bytes),
                "renderer": renderer_kind,
                "shot_plan": shot_plan,
                "data_url": "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii"),
            }
