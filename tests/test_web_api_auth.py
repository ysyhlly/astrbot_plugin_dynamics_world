"""Authentication and CSRF regression tests for WorldAPI and WorldBookWebAPI."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS

import pytest

from astrbot_plugin_dynamics_world.web_api import WorldAPI
from astrbot_plugin_dynamics_world.world.core import web_api as wb_api
from astrbot_plugin_dynamics_world.world.service import WorldService


def _run(coro):
    return asyncio.run(coro)


class _DummyContext:
    def __init__(self, data_dir, dashboard_username="admin"):
        self.plugin_data_dir = str(data_dir)
        self.persona_manager = None
        self.conversation_manager = None
        self._dashboard_username = dashboard_username
        self.registered_web_apis = []

    def get_config(self):
        if self._dashboard_username is None:
            return {}
        return {"dashboard": {"username": self._dashboard_username}}

    def get_all_stars(self):
        return []

    def register_web_api(self, route, handler, methods, desc):
        self.registered_web_apis.append((route, handler, list(methods), desc))


def _make_req(
    *,
    username="admin",
    raw_username="admin",
    method="GET",
    headers=None,
    cookies=None,
    query=None,
    body=None,
    include_raw=True,
):
    req_headers = dict(headers or {})
    req_cookies = dict(cookies or {})
    if include_raw:
        state = (
            NS(dashboard_g=NS(username=raw_username))
            if raw_username is not None
            else NS()
        )
        raw = NS(
            state=state,
            method=method,
            headers=req_headers,
            cookies=req_cookies,
        )
    else:
        raw = None
    return NS(
        username=username,
        method=method,
        headers=req_headers,
        cookies=req_cookies,
        query=dict(query or {}),
        json=lambda **kwargs: body,
        _request=raw,
    )


def _admin_write_headers(**extra):
    headers = {
        "Host": "dashboard.local",
        "Origin": "https://dashboard.local",
        "Sec-Fetch-Site": "same-origin",
    }
    headers.update(extra)
    return headers


def _patch_responses(monkeypatch):
    monkeypatch.setattr(
        wb_api,
        "json_response",
        lambda data=None, *, status_code=200, headers=None: (data, status_code),
    )
    monkeypatch.setattr(
        wb_api,
        "error_response",
        lambda message, *, status_code=400, data=None, headers=None: (
            {"status": "error", "message": message, "data": data},
            status_code,
        ),
    )


def _build_world_api(tmp_path, monkeypatch, dashboard_username="admin"):
    _patch_responses(monkeypatch)
    ctx = _DummyContext(tmp_path, dashboard_username=dashboard_username)
    world_svc = WorldService(ctx, {}, tmp_path)

    plugin = NS(
        context=ctx,
        config={"runtime_enabled": False, "mode": "narrative", "persona_id": "p"},
        world=world_svc,
        data_dir=tmp_path,
        data_root=tmp_path,
        _migrating=False,
        _terminating=False,
        _migration_lock=asyncio.Lock(),
        runtime_allowed=lambda: False,
        conflicts=lambda: [],
        get_dynamics_capabilities=lambda: {"ready": False, "enabled": False},
        onboarding=NS(compatibility=lambda: {}),
    )
    world_svc.owner = plugin
    world_api = WorldAPI(plugin)
    world_svc.web.register()
    world_api.register()
    return plugin, world_svc.web, world_api, ctx


# ---------------------------------------------------------------------------
# WorldBookWebAPI (world/core/web_api.py) auth & CSRF tests
# ---------------------------------------------------------------------------


def test_worldbook_unauthenticated_and_missing_request_blocked(tmp_path, monkeypatch):
    _, wb_web, _, _ = _build_world_api(tmp_path, monkeypatch)

    # 1. request is None
    monkeypatch.setattr(wb_api, "request", None)
    payload, code = _run(wb_web.overview())
    assert code == 403 and payload["status"] == "error"

    # 2. request._request is None
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(username="admin", method="GET", include_raw=False),
    )
    payload, code = _run(wb_web.overview())
    assert code == 403 and payload["status"] == "error"

    # 3. Raw request has no dashboard login
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(
            username=None,
            raw_username=None,
            method="POST",
            headers=_admin_write_headers(),
            body={"action": "create", "name": "unauth-book"},
        ),
    )
    payload, code = _run(wb_web.book_post())
    assert code == 403 and payload["status"] == "error"
    assert wb_web.store.find_book_by_name("unauth-book") is None


def test_worldbook_blocks_api_key_and_non_admin_and_empty_config(tmp_path, monkeypatch):
    _, wb_web, _, ctx = _build_world_api(tmp_path, monkeypatch)

    # api_key: principal on both request.username and raw auth
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(
            username="api_key:test-key",
            raw_username="api_key:test-key",
            method="GET",
        ),
    )
    payload, code = _run(wb_web.overview())
    assert code == 403 and payload["status"] == "error"

    # api_key: on request.username even if raw auth says admin
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(
            username="api_key:test-key",
            raw_username="admin",
            method="POST",
            headers=_admin_write_headers(),
            body={"action": "create", "name": "apikey-book"},
        ),
    )
    payload, code = _run(wb_web.book_post())
    assert code == 403 and payload["status"] == "error"
    assert wb_web.store.find_book_by_name("apikey-book") is None

    # Non-admin user
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(username="guest", raw_username="guest", method="GET"),
    )
    payload, code = _run(wb_web.overview())
    assert code == 403 and payload["status"] == "error"

    # Mismatched request.username vs raw username
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(username="other", raw_username="admin", method="GET"),
    )
    payload, code = _run(wb_web.overview())
    assert code == 403 and payload["status"] == "error"

    # Empty dashboard.username in host config must fail closed
    for bad_cfg_username in ("", "   ", None):
        ctx._dashboard_username = bad_cfg_username
        monkeypatch.setattr(
            wb_api,
            "request",
            _make_req(username="admin", raw_username="admin", method="GET"),
        )
        payload, code = _run(wb_web.overview())
        assert code == 403 and payload["status"] == "error"


@pytest.mark.parametrize(
    "headers,cookies",
    [
        ({}, {}),
        ({"Host": "dashboard.local", "Origin": "https://evil.example"}, {}),
        ({"Host": "dashboard.local", "Origin": "null"}, {}),
        (
            {
                "Host": "dashboard.local",
                "Origin": "https://dashboard.local",
                "Sec-Fetch-Site": "cross-site",
            },
            {},
        ),
        (
            {
                "Host": "dashboard.local",
                "Origin": "https://dashboard.local",
                "Sec-Fetch-Site": "same-site",
            },
            {},
        ),
        (
            {"Host": "dashboard.local", "Referer": "https://evil.example/attack"},
            {},
        ),
        (
            {
                "Host": "dashboard.local",
                "Origin": "https://dashboard.local",
                "Sec-Fetch-Site": "same-origin",
            },
            {"csrf_token": "expected-secret"},
        ),
        (
            {
                "Host": "dashboard.local",
                "Origin": "https://dashboard.local",
                "Sec-Fetch-Site": "same-origin",
                "X-CSRF-Token": "wrong-secret",
            },
            {"csrf_token": "expected-secret"},
        ),
    ],
)
def test_worldbook_write_rejects_missing_or_invalid_csrf(
    tmp_path, monkeypatch, headers, cookies
):
    _, wb_web, _, _ = _build_world_api(tmp_path, monkeypatch)
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(
            username="admin",
            raw_username="admin",
            method="POST",
            headers=headers,
            cookies=cookies,
            body={"action": "create", "name": "csrf-blocked"},
        ),
    )
    payload, code = _run(wb_web.book_post())
    assert code == 403 and payload["status"] == "error"
    assert "CSRF" in payload["message"]
    assert wb_web.store.find_book_by_name("csrf-blocked") is None


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_guard_enforces_csrf_on_all_write_http_methods(tmp_path, monkeypatch, method):
    _, wb_web, _, _ = _build_world_api(tmp_path, monkeypatch)
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(username="admin", raw_username="admin", method=method, headers={}),
    )
    payload, code = _run(wb_web._guard("book_post", write=True))
    assert code == 403 and "CSRF" in payload["message"]

    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(
            username="admin",
            raw_username="admin",
            method=method,
            headers=_admin_write_headers(),
        ),
    )
    assert _run(wb_web._guard("book_post", write=True)) is None


def test_worldbook_allows_valid_admin_read_and_write(tmp_path, monkeypatch):
    _, wb_web, _, _ = _build_world_api(tmp_path, monkeypatch)

    # Admin GET works without CSRF headers
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(username="admin", raw_username="admin", method="GET", headers={}),
    )
    payload, code = _run(wb_web.overview())
    assert code == 200 and payload["status"] == "ok"

    # Admin POST with same-origin headers succeeds
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(
            username="admin",
            raw_username="admin",
            method="POST",
            headers=_admin_write_headers(),
            body={"action": "create", "name": "valid-admin-book"},
        ),
    )
    payload, code = _run(wb_web.book_post())
    assert code == 200 and payload["status"] == "ok"
    assert wb_web.store.find_book_by_name("valid-admin-book") is not None

    # Admin POST with Bearer JWT (no Origin) succeeds
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(
            username="admin",
            raw_username="admin",
            method="POST",
            headers={"Authorization": "Bearer jwt-token"},
            body={"action": "create", "name": "bearer-book"},
        ),
    )
    payload, code = _run(wb_web.book_post())
    assert code == 200 and payload["status"] == "ok"

    # Admin POST with matching CSRF cookie + X-CSRF-Token header succeeds
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(
            username="admin",
            raw_username="admin",
            method="POST",
            headers=_admin_write_headers(**{"X-CSRF-Token": "tok-123"}),
            cookies={"csrf_token": "tok-123"},
            body={"action": "create", "name": "csrf-token-book"},
        ),
    )
    payload, code = _run(wb_web.book_post())
    assert code == 200 and payload["status"] == "ok"


def test_preserved_panel_switches_lifecycle_and_rate_limit(tmp_path, monkeypatch):
    plugin, wb_web, world_api, _ = _build_world_api(tmp_path, monkeypatch)

    # Unauthenticated spam must NOT consume admin rate-limit quota
    monkeypatch.setattr(wb_api, "_READ_LIMIT_PER_MINUTE", 2)
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(username=None, raw_username=None, method="GET"),
    )
    for _ in range(5):
        _, code = _run(wb_web.overview())
        assert code == 403

    # Admin still gets full rate-limit quota (2 passes, 3rd is 429)
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(username="admin", raw_username="admin", method="GET"),
    )
    assert _run(wb_web.overview())[1] == 200
    assert _run(wb_web.overview())[1] == 200
    payload, code = _run(wb_web.overview())
    assert code == 429 and "频繁" in payload["message"]

    # web_panel.allow_write=False blocks writes after auth+CSRF
    wb_web._buckets.clear()
    wb_web.settings.raw["web_panel"] = {"enabled": True, "allow_write": False}
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(
            username="admin",
            raw_username="admin",
            method="POST",
            headers=_admin_write_headers(),
            body={"action": "create", "name": "ro-book"},
        ),
    )
    payload, code = _run(wb_web.book_post())
    assert code == 403 and "只读模式" in payload["message"]

    # web_panel.enabled=False blocks reads after auth
    wb_web.settings.raw["web_panel"] = {"enabled": False, "allow_write": True}
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(username="admin", raw_username="admin", method="GET"),
    )
    payload, code = _run(world_api.overview())
    assert code == 403 and "web_panel.enabled" in payload["message"]

    # Lifecycle guards on WorldAPI.guard remain intact
    plugin._migrating = True
    payload, code = _run(world_api.guard("world"))
    assert code == 409
    plugin._migrating = False
    plugin._terminating = True
    payload, code = _run(world_api.guard("world"))
    assert code == 503


# ---------------------------------------------------------------------------
# Exhaustive sweep across ALL registered WorldAPI + WorldBookWebAPI routes
# ---------------------------------------------------------------------------


def test_every_registered_route_enforces_admin_auth_and_write_csrf(
    tmp_path, monkeypatch
):
    _, _, _, ctx = _build_world_api(tmp_path, monkeypatch)
    # 9 WorldBookWebAPI routes + 29 WorldAPI (including CausalAPIMixin) routes = 38
    assert len(ctx.registered_web_apis) == 38

    # 1. Every route blocks unauthenticated requests with 403
    for route, handler, methods, _desc in ctx.registered_web_apis:
        method = methods[0]
        monkeypatch.setattr(
            wb_api,
            "request",
            _make_req(
                username=None,
                raw_username=None,
                method=method,
                headers=_admin_write_headers() if method != "GET" else {},
            ),
        )
        payload, code = _run(handler())
        assert code == 403, f"Unauthenticated {method} {route} was not blocked: {payload}"

    # 2. Every route blocks api_key: principals with 403
    for route, handler, methods, _desc in ctx.registered_web_apis:
        method = methods[0]
        monkeypatch.setattr(
            wb_api,
            "request",
            _make_req(
                username="api_key:stolen",
                raw_username="api_key:stolen",
                method=method,
                headers=_admin_write_headers() if method != "GET" else {},
            ),
        )
        payload, code = _run(handler())
        assert code == 403, f"api_key {method} {route} was not blocked: {payload}"

    # 3. Every write route (POST) blocks authenticated admin missing CSRF with 403
    write_routes = [
        (route, handler, methods)
        for route, handler, methods, _desc in ctx.registered_web_apis
        if "POST" in methods
    ]
    assert len(write_routes) == 19
    for route, handler, _methods in write_routes:
        monkeypatch.setattr(
            wb_api,
            "request",
            _make_req(
                username="admin",
                raw_username="admin",
                method="POST",
                headers={},
            ),
        )
        payload, code = _run(handler())
        assert code == 403 and "CSRF" in payload["message"], (
            f"Missing-CSRF POST {route} was not blocked: {payload}"
        )

    # 4. Normal admin GET to WorldAPI.overview succeeds with 200
    overview_handler = next(
        h for r, h, m, _ in ctx.registered_web_apis if r == "/astrbot_plugin_dynamics_world/world" and "GET" in m
    )
    monkeypatch.setattr(
        wb_api,
        "request",
        _make_req(username="admin", raw_username="admin", method="GET", headers={}),
    )
    payload, code = _run(overview_handler())
    assert code == 200 and payload["status"] == "ok"
