"""Tests for shared ProviderBudget, telemetry, timezone, provider fallback, exclude_groups, and quiet_hours in Dynamics World."""

from __future__ import annotations

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from astrbot_plugin_dynamics_world.life.core.generator import Generator
from astrbot_plugin_dynamics_world.life.core.narrative import NarrativeEngine
from astrbot_plugin_dynamics_world.life.core.state import DataManager
from astrbot_plugin_dynamics_world.life.service import (
    LifeService,
    NarrativeProviderUnavailable,
)
from astrbot_plugin_dynamics_world.series_hooks import build_series_scope_status
from astrbot_plugin_dynamics_world.series_panels import (
    is_series_group_excluded,
    is_series_in_quiet_hours,
    resolve_series_provider,
    resolve_series_timezone,
    resolve_series_timezone_name,
    series_llm_call,
)


def _chat_ctx(
    *,
    activated: bool = True,
    rhythm_timezone: str = "America/New_York",
    reply_provider: str = "shared-reply-p",
    exclude_groups: list[str] | None = None,
    in_quiet_hours: bool = False,
    budget=None,
    telemetry=None,
    providers: dict | None = None,
    using_provider=None,
):
    class ChatOwner:
        def get_series_shared_config(self):
            return {
                "reply_provider": reply_provider,
                "decision_provider": "shared-decision-p",
                "rhythm_timezone": rhythm_timezone,
                "exclude_groups": list(exclude_groups or []),
                "takeover_groups": ["qq:GroupMessage:1001"],
                "takeover_all_groups": False,
                "persona_id": "p-main",
                "ui_language": "zh-CN",
                "quiet_hours": {
                    "daily_rhythm_enabled": True,
                    "force_sleep": False,
                    "in_quiet_hours": in_quiet_hours,
                },
            }

    provider_map = dict(providers or {})
    ctx = SimpleNamespace(
        get_all_stars=lambda: {
            "chat": SimpleNamespace(
                name="astrbot_plugin_chat_dynamics",
                activated=activated,
                star_cls=ChatOwner(),
            )
        },
        get_provider_by_id=lambda pid: provider_map.get(pid),
        get_using_provider=lambda *_a, **_kw: using_provider,
        persona_manager=SimpleNamespace(
            get_persona=AsyncMock(return_value=SimpleNamespace(system_prompt="persona")),
            get_default_persona_v3=AsyncMock(return_value={"prompt": "default"}),
        ),
    )
    if budget is not None:
        ctx._chat_dynamics_provider_budget = budget
    if telemetry is not None:
        ctx._chat_dynamics_series_telemetry = telemetry
    return ctx


class _FakeTelemetry:
    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, **kwargs) -> None:
        self.records.append(kwargs)


class _FakeBudget:
    supports_series_telemetry = True

    def __init__(self, *, busy: bool = False, telemetry: _FakeTelemetry | None = None):
        self.busy = busy
        self.telemetry = telemetry or _FakeTelemetry()
        self.calls: list[dict] = []

    async def run(
        self,
        provider_id: str,
        purpose: str,
        invoke,
        *,
        plugin_id: str = "unknown",
        acquire_timeout: float | None = None,
    ):
        self.calls.append(
            {
                "provider_id": provider_id,
                "purpose": purpose,
                "plugin_id": plugin_id,
                "acquire_timeout": acquire_timeout,
            }
        )
        if self.busy:
            class _CrossModuleBusy(RuntimeError):
                is_provider_budget_busy = True

                def __init__(self):
                    super().__init__("queue full")
                    self.provider = provider_id
                    self.purpose = purpose
                    self.reason = "queue_full"

            self.telemetry.record(
                plugin_id=plugin_id,
                provider_id=provider_id,
                purpose=purpose,
                ok=False,
                error_type="budget_queue_full",
            )
            raise _CrossModuleBusy()
        res = invoke()
        if hasattr(res, "__await__"):
            res = await res
        self.telemetry.record(
            plugin_id=plugin_id,
            provider_id=provider_id,
            purpose=purpose,
            response=res,
            ok=True,
        )
        return res


@pytest.mark.asyncio
async def test_world_generator_delegates_to_shared_budget_and_degrades_on_busy(tmp_path):
    provider = SimpleNamespace(
        id="shared-reply-p",
        provider_config={"id": "shared-reply-p"},
        text_chat=AsyncMock(
            return_value=SimpleNamespace(
                completion_text='{"timeline":[{"time":"08:00-10:00","schedule":"喝茶","mood":"平静"}]}'
            )
        ),
    )
    busy_budget = _FakeBudget(busy=True)
    ctx = _chat_ctx(budget=busy_budget, providers={"shared-reply-p": provider})
    dm = DataManager(tmp_path / "life_state.json")
    gen = Generator(ctx, {"llm_provider_id": "", "persona_id": ""}, dm)

    result = await gen.generate(datetime.date(2026, 11, 22))
    assert result.succeeded is False
    assert busy_budget.calls
    assert busy_budget.calls[0]["plugin_id"] == "astrbot_plugin_dynamics_world"
    assert busy_budget.calls[0]["provider_id"] == "shared-reply-p"
    assert busy_budget.calls[0]["purpose"] == "daily_life_generate"
    # Busy deferral must NOT burn the daily auto-failure counter.
    assert gen._auto_failures.get("2026-11-22", 0) == 0
    provider.text_chat.assert_not_called()


@pytest.mark.asyncio
async def test_world_narrative_model_uses_shared_budget_and_raises_unavailable_on_busy(tmp_path):
    provider = SimpleNamespace(
        provider_config={"id": "shared-reply-p"},
        text_chat=AsyncMock(return_value=SimpleNamespace(completion_text='{"no_change": true}')),
    )
    busy_budget = _FakeBudget(busy=True)
    ctx = _chat_ctx(budget=busy_budget, providers={"shared-reply-p": provider})
    world_stub = SimpleNamespace(
        get_character_context=AsyncMock(
            return_value={"schema_version": 1, "persona_id": "p-main", "fingerprint": "fp1"}
        )
    )
    svc = LifeService(ctx, {"mode": "narrative", "persona_id": "p-main"}, tmp_path, world_stub, lambda: True)
    svc.generator = Generator(ctx, svc.config, DataManager(tmp_path / "life_state.json"))

    req = {
        "scope": {"platform": "qq", "umo": "qq:GroupMessage:1001", "persona_id": "p-main", "instance_id": "p-main"},
        "now": 1794366000.0,
        "snapshot": {},
        "events": [],
        "recent_diary": [],
        "plan": [],
    }
    with pytest.raises(NarrativeProviderUnavailable, match="Shared provider budget busy"):
        await svc._narrative_model(req)
    assert busy_budget.calls[0]["plugin_id"] == "astrbot_plugin_dynamics_world"


@pytest.mark.asyncio
async def test_world_standalone_fallback_without_chat_dynamics(tmp_path):
    standalone_ctx = SimpleNamespace(
        get_all_stars=lambda: {},
        get_provider_by_id=lambda _pid: None,
        get_using_provider=lambda *_a, **_kw: SimpleNamespace(
            id="host-default",
            text_chat=AsyncMock(return_value=SimpleNamespace(completion_text="ok")),
        ),
    )
    assert resolve_series_timezone_name(standalone_ctx) == "Asia/Shanghai"
    assert resolve_series_provider(standalone_ctx, "") == ""
    assert is_series_group_excluded(standalone_ctx, umo="qq:GroupMessage:1001") is False
    assert is_series_in_quiet_hours(standalone_ctx) is False

    called = []

    async def _invoke():
        called.append(True)
        return SimpleNamespace(completion_text="direct-ok")

    res = await series_llm_call(
        standalone_ctx, "host-default", "astrbot_plugin_dynamics_world", "narrative", _invoke
    )
    assert called == [True]
    assert res.completion_text == "direct-ok"


def test_world_timezone_inheritance_vs_explicit_override(tmp_path):
    ctx = _chat_ctx(rhythm_timezone="Asia/Tokyo")
    assert resolve_series_timezone_name(ctx) == "Asia/Tokyo"
    assert resolve_series_timezone_name(ctx, explicit_tz="UTC") == "UTC"
    tz = resolve_series_timezone(ctx)
    assert getattr(tz, "key", "") == "Asia/Tokyo"

    svc = LifeService(ctx, {"mode": "legacy"}, tmp_path, SimpleNamespace(), lambda: True)
    assert getattr(svc._tz(), "key", "") == "Asia/Tokyo"

    svc_override = LifeService(
        ctx, {"mode": "legacy", "timezone": "Europe/London"}, tmp_path, SimpleNamespace(), lambda: True
    )
    assert getattr(svc_override._tz(), "key", "") == "Europe/London"

    eng = NarrativeEngine(
        tmp_path / "nar.sqlite3",
        {"mode": "narrative", "persona_id": "p-main", "narrative_all_groups": True},
        AsyncMock(return_value={"no_change": True}),
        host_context=ctx,
    )
    assert eng._timezone_name() == "Asia/Tokyo"


@pytest.mark.asyncio
async def test_world_exclude_groups_and_scope_status(tmp_path):
    excluded_umo = "qq:GroupMessage:9999"
    allowed_umo = "qq:GroupMessage:1001"
    ctx = _chat_ctx(exclude_groups=[excluded_umo])

    eng = NarrativeEngine(
        tmp_path / "nar_excl.sqlite3",
        {"mode": "narrative", "persona_id": "p-main", "narrative_all_groups": True},
        AsyncMock(return_value={"no_change": True}),
        host_context=ctx,
    )
    assert eng.is_managed({"platform": "qq", "umo": excluded_umo, "persona_id": "p-main", "instance_id": "p-main"}) is False
    assert eng.is_managed({"platform": "qq", "umo": allowed_umo, "persona_id": "p-main", "instance_id": "p-main"}) is True

    svc = LifeService(ctx, {"session_list_mode": "none"}, tmp_path, SimpleNamespace(), lambda: True)
    assert svc._is_session_enabled(excluded_umo) is False
    assert svc._is_session_enabled(allowed_umo) is True

    fake_plugin = SimpleNamespace(
        context=ctx,
        config={"narrative_all_groups": True, "persona_id": "p-main"},
        runtime_allowed=lambda: True,
        world=SimpleNamespace(store=None),
        life=SimpleNamespace(narrative=None),
        onboarding=None,
    )
    st_excl = build_series_scope_status(fake_plugin, excluded_umo)
    assert st_excl["enabled"] is False
    assert st_excl["excluded_by_core"] is True
    assert "主控排除" in st_excl["summary"]

    st_ok = build_series_scope_status(fake_plugin, allowed_umo)
    assert st_ok["enabled"] is True
    assert st_ok["excluded_by_core"] is False


@pytest.mark.asyncio
async def test_world_quiet_hours_suppresses_proactive_outreach_only(tmp_path):
    ctx_quiet = _chat_ctx(in_quiet_hours=True)
    ctx_awake = _chat_ctx(in_quiet_hours=False)

    model_mock = AsyncMock(return_value={"no_change": True})
    eng = NarrativeEngine(
        tmp_path / "nar_quiet.sqlite3",
        {
            "mode": "narrative",
            "persona_id": "p-main",
            "narrative_all_groups": True,
            "contextual_care_enabled": True,
            "social_chat_enabled": True,
        },
        model_mock,
        host_context=ctx_quiet,
    )
    assert await eng.review_outreach() == []
    assert await eng.list_due_intents() == []
    model_mock.assert_not_called()

    svc_quiet = LifeService(
        ctx_quiet,
        {"mode": "narrative", "persona_id": "p-main", "narrative_all_groups": True},
        tmp_path,
        SimpleNamespace(),
        lambda: True,
    )
    svc_quiet.narrative = SimpleNamespace(list_due_intents=AsyncMock(return_value=[{"id": "i1"}]))
    assert await svc_quiet.list_due_intents() == []
    svc_quiet.narrative.list_due_intents.assert_not_called()

    svc_awake = LifeService(
        ctx_awake,
        {"mode": "narrative", "persona_id": "p-main", "narrative_all_groups": True},
        tmp_path,
        SimpleNamespace(),
        lambda: True,
    )
    svc_awake.narrative = SimpleNamespace(list_due_intents=AsyncMock(return_value=[{"id": "i1"}]))
    assert await svc_awake.list_due_intents() == [{"id": "i1"}]
