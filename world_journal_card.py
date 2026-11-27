"""Daily World Journal (世界手账) graphic card collector & Pillow renderer for group chat delivery."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .postcard_renderer import _load_font
from .series_panels import resolve_series_timezone
from .spatial import identity as scope_identity

WEEKDAY_ZH = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")
CAT_SPOT_LABELS = {
    "bed_nap": "床铺蜷睡打盹",
    "window_perch": "北窗台晒太阳",
    "rug_stretch": "地毯伸懒腰",
    "desk_watch": "书桌旁安静监工",
    "garden_prowl": "院落花径巡逻",
    "fireplace_warm": "炉火旁烤暖",
    "kitchen_wait": "灶台边等小鱼干",
    "shelf_top": "书架顶端俯瞰",
}
PROJECT_STATUS_LABELS = {
    "active": "创作中",
    "in_progress": "创作中",
    "paused": "暂停中",
    "completed": "已完结",
    "done": "已完结",
}


def _wrap_text(text: str, max_units: int = 34, max_lines: int = 3) -> list[str]:
    """Wrap CJK/ASCII mixed text cleanly by display width units."""
    clean = " ".join(str(text or "").split())
    if not clean:
        return []
    lines: list[str] = []
    buf: list[str] = []
    units = 0.0
    for ch in clean:
        w = 1.0 if ord(ch) > 127 else 0.56
        if units + w > max_units and buf:
            lines.append("".join(buf))
            if len(lines) >= max_lines:
                lines[-1] = lines[-1][:-1] + "…"
                return lines
            buf = [ch]
            units = w
        else:
            buf.append(ch)
            units += w
    if buf:
        lines.append("".join(buf))
    return lines[:max_lines]


def _day_bounds(now_ts: float, context: Any = None) -> tuple[float, datetime]:
    tz = resolve_series_timezone(context)
    local_dt = datetime.fromtimestamp(now_ts, tz=tz)
    start_dt = local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_dt.timestamp(), local_dt


def collect_world_journal_data(
    engine,
    scope: dict,
    *,
    character: dict | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Read-only SQLite snapshot of today's world journal data (run inside asyncio.to_thread)."""
    now_ts = float(engine.clock() if now is None else now)
    day_start, local_dt = _day_bounds(now_ts, getattr(engine, "host_context", None))
    ident = scope_identity(scope)
    char_name = str((character or {}).get("name") or "小屋主人")[:24]

    with engine._db(notify=False) as db:
        db.execute("PRAGMA query_only = ON")
        actor = engine.spatial.snapshot(db, scope, now_ts) if engine.spatial is not None else {}
        env = engine.environment.snapshot(db, scope, now_ts, actor) if engine.environment is not None else {}
        scene = engine.scenes.snapshot(db, scope, now_ts) if engine.scenes is not None else {}
        eco = (
            engine.ecology.snapshot(db, scope, now_ts, scene_state=scene, env=env, actor=actor)
            if engine.ecology is not None
            else {}
        )
        mb = engine.mailbox.snapshot(db, scope, now_ts, character, read_only=True) if engine.mailbox is not None else {}
        ks = engine.keepsakes.snapshot(db, scope, scene, now_ts) if engine.keepsakes is not None else {}

        # Footprints from today's timeline keyframes + diary + current place
        footprints: list[str] = []
        seen_fp: set[str] = set()

        def _add_fp(label: str) -> None:
            clean = " ".join(str(label or "").split()).strip()
            if clean and clean not in seen_fp:
                seen_fp.add(clean)
                footprints.append(clean[:64])

        has_kf = bool(
            db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='world_timeline_keyframes' LIMIT 1"
            ).fetchone()
        )
        if has_kf:
            rows = db.execute(
                "SELECT occurred,kind,payload FROM world_timeline_keyframes "
                "WHERE identity=? AND occurred>=? ORDER BY occurred DESC LIMIT 12",
                (ident, day_start),
            ).fetchall()
            for r in rows:
                t_hm = datetime.fromtimestamp(float(r["occurred"]), tz=local_dt.tzinfo).strftime("%H:%M")
                payload = {}
                try:
                    payload = json.loads(r["payload"]) if r["payload"] else {}
                except Exception:
                    payload = {}
                place = str(payload.get("place_name") or "").strip()
                summ = str(payload.get("summary") or "").strip()
                if place and summ and place not in summ:
                    _add_fp(f"{t_hm} {place} · {summ}")
                elif summ:
                    _add_fp(f"{t_hm} {summ}")
                elif place:
                    _add_fp(f"{t_hm} 到访 {place}")

        has_diary = bool(
            db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='diary' LIMIT 1"
            ).fetchone()
        )
        if has_diary and len(footprints) < 5:
            d_rows = db.execute(
                "SELECT occurred,text FROM diary WHERE identity=? AND occurred>=? "
                "ORDER BY occurred DESC LIMIT 6",
                (ident, day_start),
            ).fetchall()
            for r in d_rows:
                t_hm = datetime.fromtimestamp(float(r["occurred"]), tz=local_dt.tzinfo).strftime("%H:%M")
                _add_fp(f"{t_hm} {str(r['text'] or '').strip()}")

        journey = actor.get("journey") if isinstance(actor, dict) else None
        if isinstance(journey, dict) and journey.get("destination_name"):
            loc_str = f"前往 {journey['destination_name']} 途中"
        else:
            p_name = str(scene.get("place_name") or actor.get("place_name") or "住所小屋")
            r_name = str(scene.get("room_name") or "")
            loc_str = f"{p_name} · {r_name}" if r_name else p_name
        if not footprints:
            act_label = str((scene.get("action") or {}).get("label") or "").strip()
            _add_fp(f"当前位于 {loc_str}" + (f"（{act_label}）" if act_label else "，安静度过日常时光"))

        # Weather
        cur_wx = env.get("current") if isinstance(env.get("current"), dict) else {}
        solar = str((eco.get("season") or {}).get("solar_term") or "")
        wx_label = str(cur_wx.get("label") or "晴")
        temp = cur_wx.get("temperature")
        day_str = "白天" if cur_wx.get("is_day", True) else "夜间"
        if env.get("available") and not env.get("stale"):
            wx_text = f"{wx_label} {round(float(temp))}°C · {day_str}" if temp is not None else f"{wx_label} · {day_str}"
        else:
            wx_text = "天气实况待接入"
        if solar:
            wx_text = f"{solar} · {wx_text}"

        # Creative projects
        raw_projects = scene.get("projects") if isinstance(scene.get("projects"), list) else []
        projects: list[dict[str, Any]] = []
        for proj in raw_projects[:4]:
            if not isinstance(proj, dict):
                continue
            title = str(proj.get("title") or proj.get("name") or "未命名作品")[:28]
            status_raw = str(proj.get("status") or "active").lower()
            status_zh = PROJECT_STATUS_LABELS.get(status_raw, status_raw)
            drafts = proj.get("drafts") if isinstance(proj.get("drafts"), list) else []
            stage = str(proj.get("stage") or "").strip()
            pct = 100 if status_raw in {"completed", "done"} else min(95, max(15, len(drafts) * 25 + 15))
            if isinstance(proj.get("progress"), (int, float)):
                val = float(proj["progress"])
                pct = int(round(val * 100)) if val <= 1.0 else int(round(min(100.0, val)))
            projects.append(
                {
                    "title": title,
                    "status": status_zh,
                    "stage": stage,
                    "draft_count": len(drafts),
                    "percent": max(0, min(100, pct)),
                }
            )

        # Mailbox letters (today's parcels + recent opened)
        parcels = mb.get("parcels") if isinstance(mb.get("parcels"), list) else []
        recent_opened = mb.get("recent_opened") if isinstance(mb.get("recent_opened"), list) else []
        mail_items: list[dict[str, str]] = []
        seen_pid: set[str] = set()
        for item in recent_opened:
            if not isinstance(item, dict):
                continue
            pid = str(item.get("parcel_id") or "")
            if pid and pid not in seen_pid:
                seen_pid.add(pid)
                mail_items.append(
                    {
                        "sender": str(item.get("sender_name") or "群友")[:16],
                        "kind_label": str(item.get("kind_label") or "来信"),
                        "title": str(item.get("title") or "")[:24],
                        "status": "已拆阅",
                        "reaction": str(item.get("reaction") or "")[:56],
                    }
                )
        for p in parcels:
            if not isinstance(p, dict) or len(mail_items) >= 4:
                break
            pid = str(p.get("parcel_id") or "")
            if pid and pid in seen_pid:
                continue
            if float(p.get("created_at") or 0) >= day_start or p.get("status") == "unopened":
                seen_pid.add(pid)
                mail_items.append(
                    {
                        "sender": str(p.get("sender_name") or "群友")[:16],
                        "kind_label": str(p.get("kind_label") or "来信"),
                        "title": str(p.get("title") or "")[:24],
                        "status": "未拆阅" if p.get("status") == "unopened" else "已拆阅",
                        "reaction": str(p.get("reaction") or p.get("message") or "")[:56],
                    }
                )

        # Cat spot & vitality
        cat = eco.get("cat") if isinstance(eco.get("cat"), dict) else {}
        cat_spot_raw = str(cat.get("spot") or "bed_nap")
        cat_spot_label = str(cat.get("label") or CAT_SPOT_LABELS.get(cat_spot_raw, cat_spot_raw))
        cat_name = str(cat.get("name") or "小屋猫咪")
        vit = eco.get("vitality") if isinstance(eco.get("vitality"), dict) else {}
        mood_label = str(vit.get("mood_label") or vit.get("mood") or "平和自在")
        energy_pct = int(round(max(0.0, min(1.0, float(vit.get("energy", 0.8)))) * 100))

        slots = ks.get("slots") if isinstance(ks.get("slots"), dict) else {}
        keepsake_count = sum(1 for v in slots.values() if isinstance(v, dict) and v.get("title"))

    date_iso = local_dt.strftime("%Y-%m-%d")
    weekday = WEEKDAY_ZH[local_dt.weekday()]
    return {
        "character_name": char_name,
        "date": date_iso,
        "date_label": f"{date_iso} {weekday}",
        "generated_hm": local_dt.strftime("%H:%M"),
        "location": loc_str,
        "weather": wx_text,
        "footprints": footprints[:5],
        "projects": projects[:3],
        "mailbox": {
            "unopened_count": int(mb.get("unopened_count") or 0),
            "visitor_count": len(mb.get("visitors") or []),
            "items": mail_items[:3],
        },
        "cat": {
            "name": cat_name,
            "spot": cat_spot_raw,
            "spot_label": cat_spot_label,
        },
        "mood_label": mood_label,
        "energy_pct": energy_pct,
        "keepsake_count": keepsake_count,
    }


def render_world_journal_card(data: dict[str, Any]) -> bytes:
    """Synthesize a crisp Pillow graphic daily World Journal card PNG."""
    W, H = 840, 1080
    img = Image.new("RGB", (W, H), (245, 240, 229))
    draw = ImageDraw.Draw(img)

    # Subtle stationery dot grid
    for gx in range(36, W - 24, 28):
        for gy in range(170, H - 56, 28):
            draw.point((gx, gy), fill=(224, 217, 202))

    # Outer stationery border
    draw.rounded_rectangle((18, 18, W - 18, H - 18), radius=24, outline=(206, 198, 180), width=2)

    # Header banner
    draw.rounded_rectangle((32, 32, W - 32, 168), radius=18, fill=(43, 86, 66))
    font_h1 = _load_font(30)
    font_h2 = _load_font(21)
    font_body = _load_font(18)
    font_small = _load_font(15)
    font_tag = _load_font(16)

    char_name = str(data.get("character_name") or "小屋主人")
    draw.text((58, 52), f"{char_name} 的每日世界手账", fill=(250, 247, 238), font=font_h1)
    draw.text(
        (58, 96),
        f"{data.get('date_label', '')}  ·  {data.get('location', '住所小屋')}",
        fill=(212, 232, 219),
        font=font_body,
    )
    wx_line = f"天气：{data.get('weather', '晴')}  |  心情：{data.get('mood_label', '平和')} · 精力 {data.get('energy_pct', 80)}%"
    draw.text((58, 128), wx_line, fill=(238, 224, 192), font=font_small)

    def _draw_section_box(top: int, bottom: int, title: str, badge: str = "") -> int:
        draw.rounded_rectangle(
            (36, top, W - 36, bottom),
            radius=16,
            fill=(252, 249, 243),
            outline=(221, 214, 199),
            width=2,
        )
        draw.rectangle((54, top + 16, 60, top + 40), fill=(52, 108, 82))
        draw.text((72, top + 15), title, fill=(44, 62, 52), font=font_h2)
        if badge:
            draw.rounded_rectangle(
                (W - 220, top + 14, W - 54, top + 42),
                radius=12,
                fill=(232, 242, 234),
            )
            draw.text((W - 208, top + 19), badge[:14], fill=(42, 92, 68), font=font_small)
        draw.line((54, top + 50, W - 54, top + 50), fill=(234, 228, 216), width=1)
        return top + 62

    # Section 1: Footprints (y: 186 -> 430)
    y = _draw_section_box(186, 434, "今日足迹与行踪", f"共 {len(data.get('footprints') or [])} 条记录")
    footprints = data.get("footprints") or ["今日安静待在小屋里。"]
    for fp in footprints[:5]:
        for ln in _wrap_text(f"• {fp}", max_units=40, max_lines=2):
            if y > 410:
                break
            draw.text((58, y), ln, fill=(68, 60, 52), font=font_body)
            y += 28
        y += 4

    # Section 2: Creative projects (y: 450 -> 646)
    projects = data.get("projects") or []
    y = _draw_section_box(450, 646, "创作项目进度", f"{len(projects)} 个项目")
    if not projects:
        draw.text((58, y + 10), "今日暂无进行中的创作项目，正在积蓄新的灵感。", fill=(124, 114, 102), font=font_body)
    else:
        for proj in projects[:3]:
            if y > 616:
                break
            title = proj.get("title", "未命名")
            status = proj.get("status", "创作中")
            pct = int(proj.get("percent", 0))
            draw.text((58, y), f"《{title}》 · {status}", fill=(58, 52, 46), font=font_body)
            # Progress bar
            bar_x0, bar_x1 = W - 260, W - 110
            draw.rounded_rectangle((bar_x0, y + 6, bar_x1, y + 18), radius=6, fill=(230, 226, 216))
            fill_w = max(8, int((bar_x1 - bar_x0) * (pct / 100.0)))
            draw.rounded_rectangle((bar_x0, y + 6, bar_x0 + fill_w, y + 18), radius=6, fill=(66, 128, 94))
            draw.text((W - 98, y + 1), f"{pct}%", fill=(62, 102, 78), font=font_small)
            y += 40

    # Section 3: Mailbox & echoes (y: 662 -> 876)
    mb = data.get("mailbox") or {}
    unopened = int(mb.get("unopened_count") or 0)
    mail_items = mb.get("items") or []
    y = _draw_section_box(662, 876, "院门信箱与来信回音", f"未拆 {unopened} 封")
    if not mail_items:
        draw.text((58, y + 10), "今日院门信箱安静等待中，欢迎群友使用 /投递 寄送心意。", fill=(124, 114, 102), font=font_body)
    else:
        for item in mail_items[:3]:
            if y > 848:
                break
            head = f"• [{item.get('status', '来信')}] {item.get('sender', '群友')} · {item.get('title', '')}"
            draw.text((58, y), head[:42], fill=(56, 48, 42), font=font_body)
            y += 24
            react = str(item.get("reaction") or "").strip()
            if react:
                for ln in _wrap_text(f"  回音：{react}", max_units=41, max_lines=1):
                    draw.text((66, y), ln, fill=(112, 94, 78), font=font_small)
                    y += 22
            y += 6

    # Section 4: Cat spot & keepsakes (y: 892 -> 1018)
    cat = data.get("cat") or {}
    y = _draw_section_box(892, 1018, "今日猫咪点位与小屋近况", f"纪念格 {data.get('keepsake_count', 0)} 件")
    cat_line = f"🐾 {cat.get('name', '小屋猫咪')} 今日常驻：{cat.get('spot_label', '床铺蜷睡')}"
    draw.text((58, y + 2), cat_line, fill=(58, 52, 46), font=font_body)
    vis_cnt = int(mb.get("visitor_count") or 0)
    draw.text(
        (58, y + 32),
        f"🌿 花园当前访客：{vis_cnt} 位  ·  发送 /小屋实况 可拍摄实时拍立得",
        fill=(112, 104, 94),
        font=font_small,
    )

    # Footer
    draw.text(
        (42, H - 48),
        f"群间世界 · Dynamics World 每日手账  |  生成于 {data.get('date', '')} {data.get('generated_hm', '')}",
        fill=(136, 128, 114),
        font=font_tag,
    )

    out = BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()


def format_world_journal_text(data: dict[str, Any]) -> str:
    """Format a clean text summary of the daily World Journal (fallback & chat caption)."""
    lines = [
        f"📓 {data.get('character_name', '小屋主人')} 的每日世界手账（{data.get('date_label', '')}）",
        f"📍 位置：{data.get('location', '住所小屋')}  |  🌤️ {data.get('weather', '晴')}",
    ]
    fps = data.get("footprints") or []
    if fps:
        lines.append("👣 今日足迹：" + "；".join(fps[:3]))
    projs = data.get("projects") or []
    if projs:
        lines.append(
            "✍️ 创作进度："
            + "、".join(f"《{p['title']}》({p['percent']}%)" for p in projs[:2])
        )
    mb = data.get("mailbox") or {}
    items = mb.get("items") or []
    mail_bit = f"未拆 {mb.get('unopened_count', 0)} 封"
    if items:
        mail_bit += f"，最近：{items[0]['sender']}的「{items[0]['title']}」"
    lines.append(f"📮 院门信箱：{mail_bit}")
    cat = data.get("cat") or {}
    lines.append(
        f"🐾 今日猫咪：{cat.get('spot_label', '床铺蜷睡')}  |  心情：{data.get('mood_label', '平和')}"
    )
    return "\n".join(lines)


def save_world_journal_card(data_root: Path, data: dict[str, Any]) -> dict[str, Any]:
    """Render and persist the daily World Journal card PNG under data_root/postcards."""
    out_dir = Path(data_root) / "postcards"
    out_dir.mkdir(parents=True, exist_ok=True)
    png_bytes = render_world_journal_card(data)
    digest = hashlib.sha256(png_bytes).hexdigest()[:12]
    date_slug = str(data.get("date") or "today").replace("-", "")
    out_path = out_dir / f"journal_{date_slug}_{digest}.png"
    out_path.write_bytes(png_bytes)
    existing = sorted(out_dir.glob("journal_*.png"), key=lambda p: p.stat().st_mtime)
    for stale in existing[:-30]:
        stale.unlink(missing_ok=True)
    return {
        "ok": True,
        "path": str(out_path),
        "bytes": len(png_bytes),
        "date": str(data.get("date") or ""),
        "summary_text": format_world_journal_text(data),
        "data": data,
    }
