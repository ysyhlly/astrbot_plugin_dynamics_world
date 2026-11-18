"""Local environment snapshots; network I/O never runs inside life transactions."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import random
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import aiohttp

from .geography import coordinate, timezone
from .spatial import encode, identity
from .weather_sources import (
    SOURCES,
    Credentials,
    cache_deadline,
    fetch_source,
    normalize_met,
    normalize_qweather,
    project,
)

DEFAULTS = {
    "mode": "auto",
    "climate": "temperate",
    "timezone": "Asia/Shanghai",
    "effects": True,
    "reference": None,
    "provider": "open_meteo",
    "fallback": "none",
}
CLIMATES = {
    "temperate": (16, 13, 0.30),
    "warm": (27, 4, 0.45),
    "cold": (1, 16, 0.30),
    "dry": (23, 10, 0.08),
}


class WeatherServiceError(ValueError):
    def __init__(self, message, retry_seconds=300, rate_limited=False):
        super().__init__(message)
        self.retry_seconds = retry_seconds
        self.rate_limited = rate_limited


def response_error(status, body, retry_after=None, now=None):
    delay = 300
    if status == 429:
        reason = str(body.get("reason", "")).lower() if isinstance(body, dict) else ""
        period = next((p for p in ("daily", "hourly", "minutely") if p in reason), None)
        delay = {"daily": 86400, "hourly": 3600, "minutely": 60}.get(period, 900)
        label = {"daily": "当日", "hourly": "本小时", "minutely": "本分钟"}.get(
            period, ""
        )
        message = f"Open-Meteo {label}请求额度已用完（HTTP 429），等待服务恢复"
    else:
        message = f"天气服务返回 HTTP {status}，稍后自动重试"
    if retry_after:
        try:
            seconds = float(retry_after)
        except (ValueError, TypeError):
            try:
                seconds = parsedate_to_datetime(retry_after).timestamp() - (
                    time.time() if now is None else now
                )
            except (ValueError, TypeError, OverflowError):
                seconds = 0
        if math.isfinite(seconds):
            delay = max(delay, seconds)
    return WeatherServiceError(message, delay, status == 429)


def condition(code):
    if code == 0:
        return "晴", "clear"
    if code in (1, 2, 3):
        return "多云" if code < 3 else "阴", "cloud"
    if code in (45, 48):
        return "雾", "fog"
    if code in (71, 73, 75, 77, 85, 86):
        return "雪", "snow"
    if code in (95, 96, 99):
        return "雷雨", "rain"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "雨", "rain"
    return "未知", "unknown"


def simulated(key, now, settings, seed=""):
    zone = ZoneInfo(settings["timezone"])

    def at(stamp):
        dt = datetime.fromtimestamp(stamp, zone)
        rng = random.Random(
            hashlib.sha256(
                f"{key}:{seed}:{settings['climate']}:{int(stamp // 10800)}".encode()
            ).digest()
        )
        base, amplitude, rain = CLIMATES[settings["climate"]]
        temp = (
            base
            + amplitude * math.cos((dt.timetuple().tm_yday - 200) * 2 * math.pi / 365)
            + 3 * math.cos((dt.hour - 14) * math.pi / 12)
            + rng.uniform(-2, 2)
        )
        wet = rng.random() < rain
        code = (73 if temp < 1 else 61) if wet else rng.choice([0, 0, 1, 2, 3])
        label, effect = condition(code)
        return {
            "time": stamp,
            "temperature": round(temp, 1),
            "apparent_temperature": round(temp - 1, 1),
            "precipitation": round(rng.uniform(0.2, 3), 1) if wet else 0,
            "precipitation_probability": round(rain * 100),
            "wind_speed": round(rng.uniform(2, 18), 1),
            "weather_code": code,
            "label": label,
            "effect": effect,
            "is_day": 6 <= dt.hour < 18,
        }

    local = datetime.fromtimestamp(now, zone)
    return {
        "current": at(now),
        "forecast": [at(now + i * 3600) for i in (3, 6, 9, 12, 18, 24)],
        "sunrise": local.replace(hour=6, minute=0, second=0, microsecond=0).timestamp(),
        "sunset": local.replace(hour=18, minute=0, second=0, microsecond=0).timestamp(),
        "timezone": settings["timezone"],
        "sun_times_estimated": True,
        "updated_at": now,
    }


async def fetch_json(service, params):
    if service in {"met", "qweather"}:
        return await fetch_source(service, params)
    urls = {
        "forecast": "https://api.open-meteo.com/v1/forecast",
        "search": "https://geocoding-api.open-meteo.com/v1/search",
    }
    # Fixed HTTPS hosts, no redirects, bounded response and total deadline.
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=8),
        headers={"User-Agent": "DynamicsWorld/0.3 (AstrBot plugin)"},
    ) as session:
        async with session.get(
            urls[service], params=params, allow_redirects=False
        ) as response:
            result = bytearray()
            async for chunk in response.content.iter_chunked(16384):
                result.extend(chunk)
                if len(result) > 524288:
                    raise ValueError("天气数据超出大小限制")
            try:
                data = json.loads(result)
            except (ValueError, UnicodeDecodeError):
                if response.status != 200:
                    raise response_error(
                        response.status, {}, response.headers.get("Retry-After")
                    ) from None
                raise ValueError("天气服务返回无效数据") from None
            if response.status != 200:
                raise response_error(
                    response.status, data, response.headers.get("Retry-After")
                )
            if not isinstance(data, dict) or data.get("error"):
                raise ValueError("天气服务返回无效数据")
            return data


def normalize_forecast(data, now):
    def number(value):
        if type(value) not in (int, float) or not math.isfinite(value):
            return None
        return value

    def point(row, stamp):
        code = number(row.get("weather_code"))
        label, effect = condition(code)
        temp = number(row.get("temperature_2m"))
        if temp is None or number(stamp) is None:
            raise ValueError("天气数据缺少温度或时间")
        return {
            "time": stamp,
            "temperature": temp,
            "apparent_temperature": number(row.get("apparent_temperature")),
            "precipitation": number(row.get("precipitation")),
            "wind_speed": number(row.get("wind_speed_10m")),
            "precipitation_probability": number(row.get("precipitation_probability")),
            "weather_code": code,
            "label": label,
            "effect": effect,
            "is_day": row.get("is_day") == 1,
        }

    current = data.get("current", {})
    hourly = data.get("hourly", {})
    daily = data.get("daily", {})
    points = []
    for i, stamp in enumerate(hourly.get("time", [])[:96]):
        if type(stamp) not in (int, float) or not now < stamp <= now + 86400:
            continue
        if len(points) >= 24:
            break
        points.append(
            point(
                {
                    k: v[i]
                    for k, v in hourly.items()
                    if isinstance(v, list) and len(v) > i
                },
                stamp,
            )
        )
    zone = timezone(data.get("timezone", "UTC"))
    day = datetime.fromtimestamp(now, ZoneInfo(zone)).date()
    index = next(
        (
            i
            for i, t in enumerate(daily.get("time", []))
            if datetime.fromtimestamp(t, ZoneInfo(zone)).date() == day
        ),
        None,
    )

    def sun(field):
        values = daily.get(field, [])
        return (
            number(values[index]) if index is not None and len(values) > index else None
        )

    result = {
        "current": point(current, current.get("time")),
        "forecast": points,
        "sunrise": sun("sunrise"),
        "sunset": sun("sunset"),
        "timezone": zone,
        "sun_times_estimated": False,
        "updated_at": now,
    }
    if abs(now - result["current"]["time"]) > 7200:
        raise ValueError("服务返回的当前天气已过期")
    return result


class EnvironmentService:
    def __init__(self, engine, fetch=fetch_json):
        self.engine, self.fetch = engine, fetch
        self.tasks = {}
        self.closed = False
        self.forecast_lock = asyncio.Lock()
        self.credentials = Credentials(engine)
        from .weather_life import WeatherLifeObserver

        self.life_observer = WeatherLifeObserver(self)
        with engine._db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS world_environment(identity TEXT PRIMARY KEY,revision INTEGER NOT NULL,settings TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS world_weather_cache(cache_key TEXT PRIMARY KEY,payload TEXT,updated REAL NOT NULL,retry_at REAL NOT NULL,error TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS world_weather_limits(service TEXT PRIMARY KEY,retry_at REAL NOT NULL,error TEXT NOT NULL);
            """)

    def settings(self, db, key):
        ws = getattr(self.engine, "world_spaces", None)
        lookup_key = ws.map_owner_key(db, key) if ws is not None else key
        row = db.execute(
            "SELECT revision,settings FROM world_environment WHERE identity=?",
            (lookup_key,),
        ).fetchone()
        if not row and lookup_key != key:
            row = db.execute(
                "SELECT revision,settings FROM world_environment WHERE identity=?",
                (key,),
            ).fetchone()
        return (
            (row["revision"], dict(DEFAULTS, **json.loads(row["settings"])))
            if row
            else (0, dict(DEFAULTS))
        )

    def configure(self, scope, body):
        incoming = body.get("settings")
        if not isinstance(incoming, dict) or set(incoming) - set(DEFAULTS):
            raise ValueError("未知天气设置")
        settings = dict(DEFAULTS, **incoming)
        if settings["mode"] not in {"auto", "real", "simulated", "off"}:
            raise ValueError("未知天气模式")
        if settings["climate"] not in CLIMATES:
            raise ValueError("未知模拟气候")
        if settings["provider"] not in SOURCES or settings["fallback"] not in {
            *SOURCES,
            "none",
        }:
            raise ValueError("未知天气服务")
        if settings["provider"] == settings["fallback"]:
            raise ValueError("主源与备用源不能相同")
        settings["timezone"] = timezone(settings["timezone"])
        if type(settings["effects"]) is not bool:
            raise ValueError("天气特效需为布尔值")
        ref = settings["reference"]
        if ref is not None:
            if not isinstance(ref, dict) or set(ref) != {
                "name",
                "latitude",
                "longitude",
            }:
                raise ValueError("无效天气参考地点")
            if not isinstance(ref["name"], str) or not 1 <= len(ref["name"]) <= 60:
                raise ValueError("参考地点名称需为 1–60 字")
            ref = {
                "name": ref["name"],
                "latitude": coordinate(ref["latitude"], 85, "纬度"),
                "longitude": coordinate(ref["longitude"], 180, "经度"),
            }
            settings["reference"] = ref
        key = identity(scope)
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            revision, _ = self.settings(db, key)
            if (
                type(body.get("expected_revision")) is not int
                or body["expected_revision"] != revision
            ):
                raise ValueError("天气设置已变化，请刷新")
            doc = self.engine.spatial.document(db, key)
            if (
                settings["mode"] == "real"
                and not ref
                and (not doc or doc.get("map_type") != "real")
            ):
                raise ValueError("虚拟地图使用现实天气时，请选择参考城市")
            db.execute(
                "INSERT INTO world_environment VALUES(?,?,?) ON CONFLICT(identity) DO UPDATE SET revision=excluded.revision,settings=excluded.settings",
                (key, revision + 1, encode(settings)),
            )
            db.execute("UPDATE lives SET revision=revision+1 WHERE identity=?", (key,))
        return {"revision": revision + 1}

    def snapshot(self, db, scope, now, actor=None):
        key = identity(scope)
        revision, settings = self.settings(db, key)
        doc = self.engine.spatial.document(db, key)
        base = {
            "schema_version": 1,
            "revision": revision,
            "settings": settings,
            "available": False,
            "status": "off",
        }
        if settings["mode"] == "off":
            return base
        real_map = doc and doc.get("map_type") == "real"
        mode = (
            ("real" if real_map else "simulated")
            if settings["mode"] == "auto"
            else settings["mode"]
        )
        base.update(
            mode=mode,
            source="Open-Meteo 预报模型" if mode == "real" else "世界模拟",
            fact_kind="external_weather" if mode == "real" else "fiction",
        )
        if mode == "simulated":
            if not doc:
                return dict(base, status="no_map")
            local_settings = dict(
                settings, timezone=doc.get("timezone", settings["timezone"])
            )
            ws = getattr(self.engine, "world_spaces", None)
            sim_key = (
                ws.world_id_for(db, key)
                if ws is not None and ws.map_owner_key(db, key) != key
                else key
            )
            return dict(
                base,
                available=True,
                status="ready",
                location="角色世界",
                **simulated(sim_key, now, local_settings, doc.get("seed", "")),
            )
        ref = settings["reference"]
        if ref:
            lon, lat = ref["longitude"], ref["latitude"]
            location = ref["name"] + "（参考城市）"
        elif real_map:
            actor = actor or self.engine.spatial.snapshot(db, scope, now)
            place = next(
                (p for p in doc["places"] if p["id"] == actor.get("place_id")), None
            )
            lon, lat = [place["x"], place["y"]] if place else doc["center"]
            location = (
                (place["name"] + ("（出发地）" if actor.get("journey") else ""))
                if place
                else "地图中心（待定位）"
            )
        else:
            return dict(base, status="needs_location")
        zone = (
            doc.get("timezone", settings["timezone"])
            if real_map and not ref
            else settings["timezone"]
        )
        base.update(
            location=location,
            latitude=lat,
            longitude=lon,
            timezone=zone,
            status="pending",
        )
        providers = self.providers(settings)
        candidates = [self._read_source(db, p, base, now) for p in providers]
        chosen = next((p for p in candidates if p["status"] == "ready"), None)
        if chosen is None:
            chosen = next((p for p in candidates if p["available"]), candidates[0])
        base.update(chosen)
        base["fallback_active"] = chosen["provider"] != settings["provider"]
        base["primary_error"] = (
            candidates[0].get("error", "") if base["fallback_active"] else ""
        )
        base["provider_status"] = [
            {
                k: v
                for k, v in p.items()
                if k in {"provider", "status", "error", "retry_at", "source"}
            }
            for p in candidates
        ]
        # Probe a recovered primary even while a cached backup is usable.
        base["refresh_due"] = any(
            p["can_fetch"]
            for p in candidates[
                : next(
                    (i + 1 for i, p in enumerate(candidates) if p["status"] == "ready"),
                    len(candidates),
                )
            ]
        )
        base["request_key"] = "|".join(p["cache_key"] for p in candidates)
        base.pop("can_fetch", None)
        return base

    @staticmethod
    def providers(settings):
        return [settings["provider"]] + (
            [settings["fallback"]] if settings["fallback"] != "none" else []
        )

    def _read_source(self, db, provider, env, now):
        revision, credentials = self.credentials.read(db)
        coords = f"{env['latitude']:.3f},{env['longitude']:.3f}"
        suffix = f":{revision}" if provider == "qweather" else ""
        cache_key = (
            coords if provider == "open_meteo" else provider + suffix + "|" + coords
        )
        limit_key = "forecast" if provider == "open_meteo" else provider + suffix
        base = {
            "provider": provider,
            "source": SOURCES[provider]["name"],
            "source_url": SOURCES[provider]["url"],
            "cache_key": cache_key,
            "limit_key": limit_key,
            "available": False,
            "status": "pending",
            "retry_at": 0,
            "error": "",
        }
        if provider == "qweather" and not credentials:
            return dict(
                base,
                status="unconfigured",
                error="和风天气尚未配置凭据",
                can_fetch=False,
            )
        row = db.execute(
            "SELECT * FROM world_weather_cache WHERE cache_key=?", (cache_key,)
        ).fetchone()
        if row:
            base.update(error=row["error"], retry_at=row["retry_at"])
            if row["payload"]:
                payload = json.loads(row["payload"])
                deadline = payload.get("expires_at", row["updated"] + 1800)
                if provider in {"met", "qweather"}:
                    payload = project(
                        payload,
                        provider,
                        now,
                        env["latitude"],
                        env["longitude"],
                        env["timezone"],
                    )
                stale = (
                    now >= deadline
                    or now < row["updated"]
                    or payload.get("coverage_stale", False)
                )
                if provider != "met":
                    stale = stale or now - payload["current"]["time"] > 3600
                base.update(
                    payload,
                    available=True,
                    stale=stale,
                    status="stale" if stale else "ready",
                )
            elif row["error"]:
                base["status"] = "unavailable"
        limit = db.execute(
            "SELECT retry_at,error FROM world_weather_limits WHERE service=?",
            (limit_key,),
        ).fetchone()
        if limit and limit["retry_at"] > now and base["status"] != "ready":
            base.update(
                error=limit["error"],
                retry_at=max(base.get("retry_at", 0), limit["retry_at"]),
                status="stale" if base["available"] else "unavailable",
            )
        base["can_fetch"] = base["status"] != "ready" and base["retry_at"] <= now
        return base

    def schedule(self, scope):
        if self.closed:
            return
        with self.engine._db(notify=False) as db:
            env = self.snapshot(db, scope, self.engine.clock())
        self.schedule_projected(env)

    def schedule_projected(self, env):
        if self.closed:
            return
        key = env.get("request_key")
        if not key or not env.get("refresh_due"):
            return
        if key in self.tasks:
            return
        task = asyncio.create_task(self._refresh(key, env))
        self.tasks[key] = task
        task.add_done_callback(lambda done: self.tasks.pop(key, None))

    def schedule_all(self):
        if self.closed:
            return
        now = self.engine.clock()
        with self.engine._db(notify=False) as db:
            keys = [
                json.loads(r[0]) for r in db.execute("SELECT identity FROM world_maps")
            ]
            envs = [
                self.snapshot(
                    db,
                    {
                        "persona_id": persona,
                        "instance_id": instance,
                        "umo": "",
                        "platform": "",
                    },
                    now,
                )
                for persona, instance in keys
            ]
        for env in envs:
            self.schedule_projected(env)

    async def _refresh(self, key, env):
        # Serialize provider access so queued places observe a newly received 429.
        async with self.forecast_lock:
            for provider in self.providers(env["settings"]):
                if self.closed:
                    return
                with self.engine._db() as db:
                    candidate = self._read_source(
                        db, provider, env, self.engine.clock()
                    )
                    revision, credentials = self.credentials.read(db)
                if candidate["status"] == "ready":
                    return
                if not candidate["can_fetch"]:
                    continue
                await self._fetch_weather(
                    candidate["cache_key"],
                    env,
                    provider,
                    candidate["limit_key"],
                    credentials,
                )
                with self.engine._db() as db:
                    result = self._read_source(db, provider, env, self.engine.clock())
                if result["status"] == "ready":
                    return

    async def _fetch_weather(
        self, key, env, provider="open_meteo", limit_key="forecast", credentials=None
    ):
        try:
            if provider == "open_meteo":
                variables = "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,is_day"
                data = await self.fetch(
                    "forecast",
                    {
                        "latitude": round(env["latitude"], 3),
                        "longitude": round(env["longitude"], 3),
                        "current": variables,
                        "hourly": variables + ",precipitation_probability",
                        "daily": "sunrise,sunset",
                        "timezone": "auto",
                        "timeformat": "unixtime",
                        "forecast_days": 2,
                        "wind_speed_unit": "kmh",
                    },
                )
                now = self.engine.clock()
                payload = normalize_forecast(data, now)
            elif provider == "met":
                with self.engine._db() as db:
                    row = db.execute(
                        "SELECT payload FROM world_weather_cache WHERE cache_key=?",
                        (key,),
                    ).fetchone()
                old = json.loads(row[0]) if row and row[0] else {}
                data = await self.fetch(
                    "met",
                    {
                        "lat": f"{env['latitude']:.3f}",
                        "lon": f"{env['longitude']:.3f}",
                        "_last_modified": old.get("last_modified"),
                    },
                )
                now = self.engine.clock()
                if data.get("_http", {}).get("status") == 304:
                    if not old:
                        raise ValueError("MET 返回无缓存的 304")
                    payload = dict(old, updated_at=now)
                else:
                    payload = normalize_met(data, now)
            else:
                data = await self.fetch(
                    "qweather",
                    {
                        "latitude": env["latitude"],
                        "longitude": env["longitude"],
                        "_credentials": credentials,
                    },
                )
                now = self.engine.clock()
                payload = normalize_qweather(data, now)
            deadline = cache_deadline(provider, data, now, key)
            payload["expires_at"] = deadline
            if self.closed:
                return
            with self.engine._db() as db:
                db.execute(
                    "INSERT INTO world_weather_cache VALUES(?,?,?,?,?) ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload,updated=excluded.updated,retry_at=excluded.retry_at,error=''",
                    (key, encode(payload), now, deadline, ""),
                )
                db.execute(
                    "DELETE FROM world_weather_cache WHERE updated<? AND retry_at<?",
                    (now - 7 * 86400, now),
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if self.closed:
                return
            self.record_failure(key, exc, limit_key)

    def record_failure(self, key, exc, limit_key="forecast"):
        now = self.engine.clock()
        delay = exc.retry_seconds if isinstance(exc, WeatherServiceError) else 300
        message = (
            str(exc)
            if isinstance(exc, WeatherServiceError)
            else "天气服务暂不可用，稍后自动重试"
        )
        with self.engine._db() as db:
            db.execute(
                "INSERT INTO world_weather_cache VALUES(?,NULL,0,?,?) ON CONFLICT(cache_key) DO UPDATE SET retry_at=excluded.retry_at,error=excluded.error",
                (key, now + delay, message),
            )
            if isinstance(exc, WeatherServiceError) and exc.rate_limited:
                db.execute(
                    "INSERT INTO world_weather_limits VALUES(?,?,?) ON CONFLICT(service) DO UPDATE SET retry_at=MAX(retry_at,excluded.retry_at),error=excluded.error",
                    (limit_key, now + delay, message),
                )

    async def search(self, name):
        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 80:
            raise ValueError("请输入 2–80 字的城市名")
        data = await self.fetch(
            "search",
            {"name": name.strip(), "count": 5, "language": "zh", "format": "json"},
        )
        results = []
        for item in data.get("results", [])[:5]:
            results.append(
                {
                    "name": " · ".join(
                        str(item[k])
                        for k in ("name", "admin1", "country")
                        if item.get(k)
                    )[:60],
                    "latitude": coordinate(item.get("latitude"), 85, "纬度"),
                    "longitude": coordinate(item.get("longitude"), 180, "经度"),
                    "timezone": timezone(item.get("timezone", "UTC")),
                }
            )
        return {"results": results, "source": "Open-Meteo / GeoNames"}

    async def close(self):
        self.closed = True
        tasks = list(self.tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()

    @staticmethod
    def brief(env):
        if not env or not env.get("available") or env.get("stale"):
            return ""
        current = env["current"]
        return f"；环境参考（{env['source']}）：{env['location']}，{current['label']} {current['temperature']}℃，{'白天' if current['is_day'] else '夜间'}"
