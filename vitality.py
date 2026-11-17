"""Zero-token deterministic vitality, seasonal solar-term palette and cat routine."""
from __future__ import annotations

import hashlib
import math
from datetime import datetime
from zoneinfo import ZoneInfo

SEASON_PALETTES = {
    "spring": {
        "label": "春分花信",
        "grass": "#6ea85b",
        "grass_alt": "#7db867",
        "foliage": "#eb9ab3",
        "foliage_alt": "#74ae63",
        "accent": "#f6c1d1",
        "fireflies": False,
        "snow_cap": False,
    },
    "summer": {
        "label": "盛夏鸣蝉",
        "grass": "#589649",
        "grass_alt": "#68a756",
        "foliage": "#3f7d3b",
        "foliage_alt": "#52934b",
        "accent": "#9be37a",
        "fireflies": True,
        "snow_cap": False,
    },
    "autumn": {
        "label": "秋日金枫",
        "grass": "#8ca055",
        "grass_alt": "#9eb062",
        "foliage": "#d97b38",
        "foliage_alt": "#e39d45",
        "accent": "#f0b35a",
        "fireflies": False,
        "snow_cap": False,
    },
    "winter": {
        "label": "冬雪初晴",
        "grass": "#7c917d",
        "grass_alt": "#8ea28f",
        "foliage": "#587368",
        "foliage_alt": "#799188",
        "accent": "#e8f1f7",
        "fireflies": False,
        "snow_cap": True,
    },
}

SOLAR_TERMS = (
    (1, "小寒"), (1, "大寒"), (2, "立春"), (2, "雨水"), (3, "惊蛰"), (3, "春分"),
    (4, "清明"), (4, "谷雨"), (5, "立夏"), (5, "小满"), (6, "芒种"), (6, "夏至"),
    (7, "小暑"), (7, "大暑"), (8, "立秋"), (8, "处暑"), (9, "白露"), (9, "秋分"),
    (10, "寒露"), (10, "霜降"), (11, "立冬"), (11, "小雪"), (12, "大雪"), (12, "冬至"),
)


def _safe_zone(timezone: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(str(timezone or "Asia/Shanghai"))
    except Exception:
        return ZoneInfo("Asia/Shanghai")


def season_for(now: float, timezone: str = "Asia/Shanghai") -> dict:
    """Resolve current season, solar term and 3D vegetation palette without network/LLM."""
    local = datetime.fromtimestamp(float(now), _safe_zone(timezone))
    month, day = local.month, local.day
    if month in (3, 4, 5):
        season = "spring"
    elif month in (6, 7, 8):
        season = "summer"
    elif month in (9, 10, 11):
        season = "autumn"
    else:
        season = "winter"
    term_idx = (month - 1) * 2 + (1 if day >= 19 else 0)
    _, solar_term = SOLAR_TERMS[max(0, min(len(SOLAR_TERMS) - 1, term_idx))]
    return {
        "season": season,
        "month": month,
        "solar_term": solar_term,
        "palette": dict(SEASON_PALETTES[season]),
    }


def cat_state_for(
    now: float,
    timezone: str = "Asia/Shanghai",
    weather_effect: str = "clear",
    actor_away: bool = False,
    actor_pose: str = "idle",
    seed: str = "",
) -> dict:
    """Deterministic multi-spot cat state machine; guards gate when owner is away."""
    local = datetime.fromtimestamp(float(now), _safe_zone(timezone))
    hour = local.hour + local.minute / 60.0
    raining = weather_effect in {"rain", "snow"}
    bucket = int(float(now) // 900)
    jitter = hashlib.sha256(f"{seed}:{bucket}".encode()).digest()[0] % 3

    if actor_away and not raining:
        return {
            "spot": "gate_wait",
            "label": "蹲守在院门石阶旁望着小路等主人回家",
            "mood": "expectant",
            "indoor": False,
        }
    if actor_away and raining:
        return {
            "spot": "window_sun",
            "label": "趴在北窗内侧听雨，竖着耳朵留意门外的脚步声",
            "mood": "attentive",
            "indoor": True,
        }
    if hour < 6.5 or hour >= 22.0 or actor_pose == "sleep":
        return {
            "spot": "bed_nap",
            "label": "蜷在床尾软垫上安静打呼噜",
            "mood": "sleepy",
            "indoor": True,
        }
    if raining:
        if jitter == 0:
            return {
                "spot": "bed_nap",
                "label": "趁雨天窝在温暖的床尾团成毛球",
                "mood": "cozy",
                "indoor": True,
            }
        return {
            "spot": "window_sun",
            "label": "蹲在北窗边盯着玻璃上滑落的雨珠",
            "mood": "curious",
            "indoor": True,
        }
    if 7.5 <= hour < 11.5:
        return {
            "spot": "window_sun",
            "label": "趴在窗台暖阳里眯眼晒毛",
            "mood": "sunny",
            "indoor": True,
        }
    if 14.0 <= hour < 17.5:
        if jitter == 0:
            return {
                "spot": "garden_patrol",
                "label": "迈着轻快步子在花圃与菜畦间巡视蝴蝶",
                "mood": "playful",
                "indoor": False,
            }
        return {
            "spot": "pond_watch",
            "label": "蹲在池塘木栈边聚精会神盯着水面涟漪",
            "mood": "curious",
            "indoor": False,
        }
    if 17.5 <= hour < 19.5 and jitter == 1:
        return {
            "spot": "garden_patrol",
            "label": "在傍晚微风里的草坪上伸长懒腰",
            "mood": "relaxed",
            "indoor": False,
        }
    return {
        "spot": "bed_nap",
        "label": "窝在床尾轻轻摇晃尾巴尖",
        "mood": "cozy",
        "indoor": True,
    }


def compute_vitality(
    life_state: dict | None,
    scene_state: dict | None,
    env: dict | None,
    ecology_state: dict | None,
    now: float,
    recent_mail_at: float = 0.0,
) -> dict:
    """Cozy non-punitive vitality curves (energy, mood, inspiration). Floor >= 0.28."""
    life_state = life_state or {}
    scene_state = scene_state or {}
    env = env or {}
    ecology_state = ecology_state or {}
    tz = env.get("timezone") or "Asia/Shanghai"
    local = datetime.fromtimestamp(float(now), _safe_zone(tz))
    hour = local.hour + local.minute / 60.0

    # Circadian gentle wave: peaks mid-morning and early evening, restful late night.
    circadian = 0.68 + 0.22 * math.sin((hour - 7.5) * math.pi / 13.0)
    availability = str(life_state.get("availability", "unknown"))
    code = str(life_state.get("activity_code", "unknown"))

    energy = circadian
    if availability == "asleep" or code in {"sleeping", "resting"}:
        energy = max(energy, 0.78)
    meals = ecology_state.get("recent_meals") or []
    if any(float(m.get("at", 0)) >= now - 4 * 3600 for m in meals if isinstance(m, dict)):
        energy += 0.08
    energy = round(max(0.28, min(1.0, energy)), 2)

    weather_effect = str((env.get("current") or {}).get("effect") or "clear")
    inspiration = 0.56 + 0.14 * math.cos((hour - 15.0) * math.pi / 10.0)
    if weather_effect in {"rain", "snow", "fog"}:
        inspiration += 0.12
    if code in {"reading", "writing"}:
        inspiration += 0.10
    flower_stage = str((ecology_state.get("flowerbed") or {}).get("stage", ""))
    if flower_stage == "blooming":
        inspiration += 0.08
    if recent_mail_at and now - recent_mail_at < 6 * 3600:
        inspiration += 0.10
    inspiration = round(max(0.30, min(1.0, inspiration)), 2)

    warmth = 0.66
    if recent_mail_at and now - recent_mail_at < 8 * 3600:
        warmth += 0.16
    if flower_stage == "blooming":
        warmth += 0.07
    if any(float(m.get("at", 0)) >= now - 6 * 3600 for m in meals if isinstance(m, dict)):
        warmth += 0.08
    if float(scene_state.get("wetness", 0) or 0) > 25:
        warmth -= 0.06
    warmth = round(max(0.35, min(1.0, warmth)), 2)

    if availability == "asleep":
        mood_label, tendency = "安睡恬静", "restful_sleep"
    elif recent_mail_at and now - recent_mail_at < 4 * 3600:
        mood_label, tendency = "收到来信的暖意", "reply_or_cherish"
    elif inspiration >= 0.78 and energy >= 0.62:
        mood_label, tendency = "思绪轻盈，很有创作欲", "creative_focus"
    elif weather_effect in {"rain", "snow"}:
        mood_label, tendency = "听雨静心，适合煮茶读书", "tea_and_reading"
    elif weather_effect == "clear" and 7 <= hour <= 17 and energy >= 0.60:
        mood_label, tendency = "晴光舒朗，想照料小院", "garden_stroll"
    else:
        mood_label, tendency = "平和自在", "cozy_routine"

    return {
        "energy": energy,
        "inspiration": inspiration,
        "mood": mood_label,
        "mood_warmth": warmth,
        "tendency": tendency,
        "fact_kind": "fiction",
    }
