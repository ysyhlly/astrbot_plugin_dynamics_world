import asyncio
import json
from datetime import datetime, timezone

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from test_spatial import SCOPE
from test_geo_weather import real, weather, fixture_forecast
from astrbot_plugin_dynamics_world.weather import (
    EnvironmentService,
    DEFAULTS,
    response_error,
)
from astrbot_plugin_dynamics_world.weather_sources import (
    normalize_met,
    normalize_qweather,
    project,
    host_name,
    jwt_headers,
)


def met_fixture(now):
    floor = now // 3600 * 3600

    def iso(ts):
        return (
            datetime.fromtimestamp(ts, timezone.utc).isoformat().replace("+00:00", "Z")
        )

    return {
        "properties": {
            "meta": {"updated_at": iso(now)},
            "timeseries": [
                {
                    "time": iso(floor + i * 3600),
                    "data": {
                        "instant": {
                            "details": {"air_temperature": 20 + i, "wind_speed": 2}
                        },
                        "next_1_hours": {
                            "summary": {"symbol_code": "lightrain"},
                            "details": {"precipitation_amount": 0.2},
                        },
                    },
                }
                for i in range(49)
            ],
        },
        "_http": {"status": 200, "last_modified": "Wed, 11 Nov 2026 01:00:00 GMT"},
    }


def settings(service, provider="met", fallback="open_meteo", revision=0):
    return service.configure(
        SCOPE,
        {
            "expected_revision": revision,
            "settings": dict(
                DEFAULTS, mode="real", provider=provider, fallback=fallback
            ),
        },
    )


async def flush(service):
    await asyncio.gather(*list(service.tasks.values()))
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_met_cache_projects_each_hour_without_network_and_handles_304(rig):
    engine, now, _ = rig
    real(engine)
    calls = []
    original = met_fixture(now[0])

    async def fetch(kind, params):
        calls.append((kind, params))
        return original if len(calls) == 1 else {"_http": {"status": 304}}

    service = engine.environment = EnvironmentService(engine, fetch)
    settings(service)
    service.schedule(SCOPE)
    await flush(service)
    first = weather(engine)
    assert (
        first["provider"] == "met"
        and first["status"] == "ready"
        and not first["fallback_active"]
    )
    assert (
        first["current"]["wind_speed"] == 7.2
        and first["current"]["apparent_temperature"] is None
    )
    assert (
        first["sunrise"] and first["sunset"] and first["sun_source"] == "本地天文计算"
    )
    assert "_series" not in first and len(first["forecast"]) == 24
    now[0] += 3600
    service.schedule(SCOPE)
    assert not service.tasks
    assert (
        weather(engine)["current"]["temperature"] == first["current"]["temperature"] + 1
    )
    assert weather(engine)["current"]["time"] > first["current"]["time"]
    now[0] = first["retry_at"] + 1
    service.schedule(SCOPE)
    await flush(service)
    assert len(calls) == 2 and calls[-1][1]["_last_modified"]
    assert weather(engine)["status"] == "ready"
    restored = EnvironmentService(engine, fetch)
    restored.schedule(SCOPE)
    assert not restored.tasks
    await restored.close()
    await service.close()


@pytest.mark.asyncio
async def test_fallback_is_labelled_and_cooldowns_do_not_cross_providers(rig):
    engine, now, _ = rig
    real(engine)
    calls = []
    fail = [True]

    async def fetch(kind, params):
        calls.append(kind)
        if kind == "met" and fail[0]:
            raise response_error(429, {}, "3600")
        return met_fixture(now[0]) if kind == "met" else fixture_forecast(now[0])

    service = engine.environment = EnvironmentService(engine, fetch)
    settings(service)
    service.schedule(SCOPE)
    await flush(service)
    env = weather(engine)
    assert calls == ["met", "forecast"]
    assert (
        env["provider"] == "open_meteo"
        and env["fallback_active"]
        and "429" in env["primary_error"]
    )
    service.schedule(SCOPE)
    assert not service.tasks
    now[0] += 1801
    service.schedule(SCOPE)
    await flush(service)
    assert calls == ["met", "forecast", "forecast"]  # MET still cooling down.
    fail[0] = False
    now[0] += 1801
    service.schedule(SCOPE)
    await flush(service)
    env = weather(engine)
    assert (
        calls[-1] == "met" and env["provider"] == "met" and not env["fallback_active"]
    )
    await service.close()


@pytest.mark.asyncio
async def test_existing_open_meteo_limit_does_not_block_met(rig):
    engine, now, _ = rig
    real(engine)

    async def fetch(kind, params):
        assert kind == "met"
        return met_fixture(now[0])

    service = engine.environment = EnvironmentService(engine, fetch)
    service.record_failure(
        "52.520,13.405", response_error(429, {"reason": "Hourly limit exceeded"})
    )
    settings(service, "open_meteo", "met")
    service.schedule(SCOPE)
    await flush(service)
    assert weather(engine)["provider"] == "met" and weather(engine)["fallback_active"]
    await service.close()


@pytest.mark.asyncio
async def test_no_fallback_means_no_other_requests_and_stale_is_not_simulated(rig):
    engine, now, _ = rig
    real(engine)
    calls = []

    async def fetch(kind, params):
        calls.append(kind)
        raise TimeoutError()

    service = engine.environment = EnvironmentService(engine, fetch)
    settings(service, "met", "none")
    service.schedule(SCOPE)
    await flush(service)
    env = weather(engine)
    assert (
        calls == ["met"]
        and not env["available"]
        and env["fact_kind"] == "external_weather"
    )
    await service.close()


def credential_fixture():
    key = Ed25519PrivateKey.generate()
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return key, {
        "host": "test.xy.qweatherapi.com",
        "developer_id": "Q123456789",
        "project_id": "PROJECT1",
        "key_id": "KEY1",
        "private_key": pem,
    }


def test_qweather_credentials_are_write_only_and_jwt_has_required_claims(rig):
    engine, now, _ = rig
    real(engine)
    service = engine.environment = EnvironmentService(engine)
    key, value = credential_fixture()
    result = service.credentials.save({"credentials_revision": 0, "credentials": value})
    assert result["configured"] and "private_key" not in result
    assert value["private_key"] not in json.dumps(weather(engine))
    token = jwt_headers(value, now[0])["Authorization"].removeprefix("Bearer ")
    claims = jwt.decode(
        token,
        key.public_key(),
        algorithms=["EdDSA"],
        options={"verify_exp": False, "verify_iat": False},
    )
    assert (
        claims["iss"] == value["developer_id"] and claims["sub"] == value["project_id"]
    )
    assert (
        claims["exp"] == int(now[0]) + 900
        and jwt.get_unverified_header(token)["kid"] == "KEY1"
    )
    with pytest.raises(ValueError):
        service.credentials.save({"credentials_revision": 0, "credentials": value})
    service.credentials.save(
        {"credentials_revision": 1, "credentials": dict(value, private_key="")}
    )
    with engine._db() as db:
        assert service.credentials.read(db)[1]["private_key"] == value["private_key"]
    service.credentials.save(
        {"credentials_revision": 2, "credentials": {"clear": True}}
    )
    with engine._db() as db:
        assert not service.credentials.public(db)["configured"]


@pytest.mark.parametrize(
    "host",
    [
        "localhost",
        "127.0.0.1",
        "https://foo.qweatherapi.com",
        "foo.qweatherapi.com:443",
        "foo.qweatherapi.com@evil.test",
        "foo.qweatherapi.com.evil.test",
    ],
)
def test_qweather_host_rejects_arbitrary_destinations(host):
    with pytest.raises(ValueError):
        host_name(host)


def q_fixture(now):
    row = {
        "condition": {"code": "305", "text": "小雨"},
        "temperature": {"value": 23, "unit": "°C"},
        "feelsLike": {"value": 25, "unit": "°C"},
        "wind": {"speed": {"value": 2, "unit": "m/s"}},
        "precipitation": {
            "amount": {"value": 0.5, "unit": "mm"},
            "probability": 0.2,
            "type": "rain",
        },
    }
    return {
        "current": row,
        "hourly": {
            "hours": [
                dict(
                    row,
                    forecastTime=datetime.fromtimestamp(
                        now + 3600, timezone.utc
                    ).isoformat(),
                )
            ]
        },
    }


@pytest.mark.asyncio
async def test_qweather_normalization_and_credential_change_isolates_inflight(rig):
    engine, now, _ = rig
    real(engine)
    gate = asyncio.Event()

    async def fetch(kind, params):
        assert kind == "qweather" and "_credentials" in params
        await gate.wait()
        return q_fixture(now[0])

    service = engine.environment = EnvironmentService(engine, fetch)
    _, credentials = credential_fixture()
    service.credentials.save({"credentials_revision": 0, "credentials": credentials})
    settings(service, "qweather", "none")
    service.schedule(SCOPE)
    await asyncio.sleep(0)
    service.credentials.save(
        {"credentials_revision": 1, "credentials": {"clear": True}}
    )
    gate.set()
    await flush(service)
    assert (
        weather(engine)["status"] == "unconfigured" and not weather(engine)["available"]
    )
    payload = normalize_qweather(q_fixture(now[0]), now[0])
    current = payload["current"]
    assert current["wind_speed"] == 7.2 and current["precipitation_probability"] == 20
    assert current["label"] == "小雨" and current["effect"] == "rain"
    await service.close()


def test_polar_day_has_no_fake_sunrise_or_sunset(rig):
    _, now, _ = rig
    stamp = datetime(2026, 6, 21, 12, tzinfo=timezone.utc).timestamp()
    payload = normalize_met(met_fixture(stamp), stamp)
    env = project(payload, "met", stamp, 78.2, 15.6, "Arctic/Longyearbyen")
    assert env["sunrise"] is None and env["sunset"] is None and env["current"]["is_day"]
