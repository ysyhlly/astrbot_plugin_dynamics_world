"""Provider adapters and local solar calculations. Never expose credentials."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

import aiohttp
from astral import Observer
from astral.sun import elevation, sunrise, sunset

SOURCES = {
    "open_meteo": {
        "name": "Open-Meteo 预报模型",
        "url": "https://open-meteo.com/",
        "interval": 1800,
    },
    "met": {
        "name": "MET Norway 预报模型",
        "url": "https://api.met.no/",
        "interval": 10800,
    },
    "qweather": {
        "name": "和风天气",
        "url": "https://developer.qweather.com/attribution.html",
        "interval": 1800,
    },
}


def number(value):
    return value if type(value) in (float, int) and math.isfinite(value) else None


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("天气数据时间缺少时区")
    return parsed.timestamp()


def host_name(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*\.qweatherapi\.com",
        value,
    ):
        raise ValueError(
            "请填写控制台分配的 qweatherapi.com API Host，不包含协议、路径或端口"
        )
    return value


class Credentials:
    def __init__(self, engine):
        self.engine = engine
        with engine._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS world_weather_credentials(provider TEXT PRIMARY KEY,revision INTEGER NOT NULL,payload TEXT NOT NULL)"
            )

    def read(self, db):
        row = db.execute(
            "SELECT revision,payload FROM world_weather_credentials WHERE provider='qweather'"
        ).fetchone()
        return (row[0], json.loads(row[1])) if row else (0, {})

    def public(self, db):
        revision, value = self.read(db)
        return {
            "revision": revision,
            "configured": bool(value),
            "host": value.get("host", ""),
            "developer_id": value.get("developer_id", ""),
            "project_id": value.get("project_id", ""),
            "key_id": value.get("key_id", ""),
        }

    def save(self, body):
        incoming = body.get("credentials")
        fields = {
            "host",
            "developer_id",
            "project_id",
            "key_id",
            "private_key",
            "clear",
        }
        if not isinstance(incoming, dict) or set(incoming) - fields:
            raise ValueError("未知凭据字段")
        if "clear" in incoming and type(incoming["clear"]) is not bool:
            raise ValueError("无效清除标记")
        with self.engine._db() as db:
            db.execute("BEGIN IMMEDIATE")
            revision, old = self.read(db)
            if (
                type(body.get("credentials_revision")) is not int
                or body["credentials_revision"] != revision
            ):
                raise ValueError("凭据已变化，请刷新")
            if incoming.get("clear"):
                value = {}
            else:
                value = {k: incoming.get(k, old.get(k, "")) for k in fields - {"clear"}}
                if not value["private_key"]:
                    value["private_key"] = old.get("private_key", "")
                value["host"] = host_name(value["host"])
                for field in ("developer_id", "project_id", "key_id"):
                    if not isinstance(value[field], str) or not re.fullmatch(
                        r"[A-Za-z0-9_-]{1,100}", value[field]
                    ):
                        raise ValueError("请填写有效的开发者 ID、项目 ID 和凭据 ID")
                if (
                    not isinstance(value["private_key"], str)
                    or len(value["private_key"]) > 4096
                ):
                    raise ValueError("无效私钥")
                from cryptography.hazmat.primitives.asymmetric.ed25519 import (
                    Ed25519PrivateKey,
                )
                from cryptography.hazmat.primitives.serialization import (
                    load_pem_private_key,
                )

                try:
                    key = load_pem_private_key(
                        value["private_key"].encode(), password=None
                    )
                except Exception:
                    raise ValueError("私钥必须是未加密的 Ed25519 PEM") from None
                if not isinstance(key, Ed25519PrivateKey):
                    raise ValueError("私钥必须使用 Ed25519")
            db.execute(
                "INSERT INTO world_weather_credentials VALUES('qweather',?,?) ON CONFLICT(provider) DO UPDATE SET revision=excluded.revision,payload=excluded.payload",
                (revision + 1, json.dumps(value)),
            )
            # Old in-flight requests may finish, but their credential revision
            # has its own cache namespace and can never become the new source.
            return self.public(db)


def jwt_headers(credentials, now=None):
    import jwt

    now = int(time.time() if now is None else now)
    token = jwt.encode(
        {
            "iss": credentials["developer_id"],
            "sub": credentials["project_id"],
            "iat": now - 30,
            "exp": now + 900,
        },
        credentials["private_key"],
        algorithm="EdDSA",
        headers={"kid": credentials["key_id"]},
    )
    return {"Authorization": "Bearer " + token}


async def request_json(url, params, headers, provider):
    from .weather import response_error

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=8), headers=headers
    ) as session:
        async with session.get(url, params=params, allow_redirects=False) as response:
            meta = {
                "status": response.status,
                "expires": response.headers.get("Expires"),
                "last_modified": response.headers.get("Last-Modified"),
            }
            if response.status == 304:
                return {"_http": meta}
            result = bytearray()
            async for chunk in response.content.iter_chunked(16384):
                result.extend(chunk)
                if len(result) > 524288:
                    raise ValueError("天气数据超出大小限制")
            try:
                data = json.loads(result)
            except (ValueError, UnicodeDecodeError):
                data = {}
            if response.status != 200:
                error = response_error(
                    response.status, data, response.headers.get("Retry-After")
                )
                if provider != "open_meteo":
                    error.args = (
                        str(error).replace("Open-Meteo", SOURCES[provider]["name"]),
                    )
                raise error
            if not isinstance(data, dict) or not data or data.get("error"):
                raise ValueError("天气服务返回无效数据")
            data["_http"] = meta
            return data


async def fetch_source(service, params):
    headers = {
        "User-Agent": "DynamicsWorld/0.4 (AstrBot plugin; https://github.com/ysyhlly)"
    }
    params = dict(params)
    if service == "met":
        modified = params.pop("_last_modified", None)
        if modified:
            headers["If-Modified-Since"] = modified
        return await request_json(
            "https://api.met.no/weatherapi/locationforecast/2.0/compact",
            params,
            headers,
            "met",
        )
    if service == "qweather":
        credentials = params.pop("_credentials")
        host = host_name(credentials["host"])
        headers.update(jwt_headers(credentials))
        coords = f"{params['latitude']:.2f}/{params['longitude']:.2f}"
        current = await request_json(
            f"https://{host}/weather/v1/current/{coords}",
            {"lang": "zh"},
            headers,
            "qweather",
        )
        hourly = await request_json(
            f"https://{host}/weather/v1/hourly/{coords}",
            {"hours": 48, "lang": "zh"},
            headers,
            "qweather",
        )
        return {"current": current, "hourly": hourly}
    raise ValueError("未知天气服务")


def cache_deadline(provider, data, now, key):
    # A small stable offset avoids simultaneous periodic refreshes.
    deadline = (
        now
        + SOURCES[provider]["interval"]
        + (
            int(hashlib.sha256(key.encode()).hexdigest()[:4], 16) % 60
            if provider == "met"
            else 0
        )
    )
    expires = data.get("_http", {}).get("expires")
    if expires:
        try:
            deadline = max(deadline, parsedate_to_datetime(expires).timestamp())
        except (ValueError, TypeError, OverflowError):
            pass
    return deadline


def met_condition(symbol):
    if "thunder" in symbol:
        return "雷雨", "rain"
    if "snow" in symbol:
        return "雪", "snow"
    if "sleet" in symbol:
        return "雨夹雪", "snow"
    if "rain" in symbol:
        return "雨", "rain"
    if "fog" in symbol:
        return "雾", "fog"
    if "clearsky" in symbol:
        return "晴", "clear"
    if "fair" in symbol or "partlycloudy" in symbol:
        return "多云", "cloud"
    if "cloudy" in symbol:
        return "阴", "cloud"
    return "未知", "unknown"


def normalize_met(data, now):
    properties = data.get("properties", {})
    series = []
    for item in properties.get("timeseries", [])[:100]:
        stamp = timestamp(item["time"])
        row = item["data"]
        instant = row.get("instant", {}).get("details", {})
        temp = number(instant.get("air_temperature"))
        if temp is None:
            continue
        period = row.get("next_1_hours") or row.get("next_6_hours") or {}
        interval = 1 if row.get("next_1_hours") else 6
        details = period.get("details", {})
        symbol = period.get("summary", {}).get("symbol_code", "")
        label, effect = met_condition(symbol)
        wind = number(instant.get("wind_speed"))
        series.append(
            {
                "time": stamp,
                "temperature": temp,
                "apparent_temperature": None,
                "wind_speed": round(wind * 3.6, 1) if wind is not None else None,
                "precipitation": number(details.get("precipitation_amount")),
                "precipitation_probability": number(
                    details.get("probability_of_precipitation")
                ),
                "precipitation_hours": interval,
                "label": label,
                "effect": effect,
                "weather_code": symbol,
            }
        )
    if not series:
        raise ValueError("MET 预报缺少温度与时间")
    return {
        "_series": sorted(series, key=lambda p: p["time"]),
        "source_updated_at": timestamp(properties["meta"]["updated_at"]),
        "updated_at": now,
        "data_kind": "forecast",
        "last_modified": data.get("_http", {}).get("last_modified"),
    }


def q_point(row, stamp):
    def value(field, unit):
        item = row.get(field, {})
        return number(item.get("value")) if item.get("unit") == unit else None

    temp = value("temperature", "°C")
    if temp is None:
        raise ValueError("和风天气缺少摄氏温度")
    precip = row.get("precipitation", {})
    kind = precip.get("type")
    condition = row.get("condition", {})
    # Provider text is displayed using textContent and passed as typed data.
    label = str(condition.get("text", "未知"))[:40]
    code = str(condition.get("code", ""))
    effect = (
        "snow"
        if kind in {"snow", "ice", "mixed"}
        else "rain"
        if kind == "rain"
        else "clear"
        if code in {"100", "150"}
        else "fog"
        if code.startswith("5")
        else "cloud"
    )
    wind = row.get("wind", {}).get("speed", {})
    speed = number(wind.get("value"))
    if speed is not None:
        speed = (
            round(speed * 3.6, 1)
            if wind.get("unit") == "m/s"
            else speed
            if wind.get("unit") == "km/h"
            else None
        )
    amount = precip.get("amount", {})
    probability = number(precip.get("probability"))
    return {
        "time": stamp,
        "temperature": temp,
        "apparent_temperature": value("feelsLike", "°C"),
        "wind_speed": speed,
        "precipitation": number(amount.get("value"))
        if amount.get("unit") == "mm"
        else None,
        "precipitation_probability": round(probability * 100)
        if probability is not None
        else None,
        "label": label,
        "effect": effect,
        "weather_code": code,
    }


def normalize_qweather(data, now):
    current = q_point(data["current"], now)
    points = [
        q_point(row, timestamp(row["forecastTime"]))
        for row in data["hourly"].get("hours", [])[:48]
    ]
    if not points:
        raise ValueError("和风天气缺少逐小时预报")
    return {
        "current": current,
        "_series": sorted(points, key=lambda p: p["time"]),
        "updated_at": now,
        "data_kind": "current",
    }


@lru_cache(maxsize=256)
def solar(day, lat, lon, zone):
    observer = Observer(latitude=lat, longitude=lon)
    result = {}
    for name, fn in (("sunrise", sunrise), ("sunset", sunset)):
        try:
            result[name] = fn(observer, date=day, tzinfo=ZoneInfo(zone)).timestamp()
        except ValueError:
            result[name] = None  # Polar day/night are legitimate.
    return result


def project(payload, provider, now, lat, lon, zone):
    result = copy.deepcopy(payload)
    series = result.pop("_series", [])
    if provider == "met":
        choices = [p for p in series if p["time"] <= now]
        current = choices[-1] if choices else series[0]
        result["current"] = dict(current)
        result["coverage_stale"] = (
            not 0 <= now - current["time"] < 3600
            or now - result["source_updated_at"] > 86400
        )
    result["forecast"] = [dict(p) for p in series if now < p["time"] <= now + 86400]
    observer = Observer(latitude=lat, longitude=lon)
    for p in [result["current"], *result["forecast"]]:
        stamp = now if p is result["current"] else p["time"]
        p["is_day"] = (
            elevation(observer, datetime.fromtimestamp(stamp, timezone.utc)) >= -0.833
        )
    result.update(
        solar(datetime.fromtimestamp(now, ZoneInfo(zone)).date(), lat, lon, zone),
        timezone=zone,
        sun_times_estimated=False,
        sun_source="本地天文计算",
    )
    return result
