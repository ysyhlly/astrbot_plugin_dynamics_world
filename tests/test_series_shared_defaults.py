"""Tests for read-only series shared defaults inheritance in Dynamics World."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from astrbot_plugin_dynamics_world.life.core.generator import Generator


def _make_generator(config: dict, stars: dict):
    explicit_provider = SimpleNamespace(id="explicit-p")
    inherited_provider = SimpleNamespace(id="series-reply")
    using_provider = SimpleNamespace(id="host-using")

    def get_provider_by_id(pid: str):
        return {
            "explicit-p": explicit_provider,
            "series-reply": inherited_provider,
        }.get(pid)

    persona_manager = SimpleNamespace(
        get_persona=AsyncMock(side_effect=lambda pid: SimpleNamespace(system_prompt=f"prompt:{pid}")),
        get_default_persona_v3=AsyncMock(return_value={"prompt": "prompt:host-default"}),
    )
    ctx = SimpleNamespace(
        get_all_stars=lambda: stars,
        get_provider_by_id=get_provider_by_id,
        get_using_provider=lambda: using_provider,
        persona_manager=persona_manager,
    )
    return Generator(ctx, config, SimpleNamespace())


def _chat_stars(*, activated: bool = True):
    class ChatOwner:
        def get_series_shared_config(self):
            return {
                "reply_provider": "series-reply",
                "persona_id": "series-persona",
            }

    return {
        "chat": SimpleNamespace(
            name="astrbot_plugin_chat_dynamics",
            activated=activated,
            star_cls=ChatOwner(),
        )
    }


@pytest.mark.asyncio
async def test_world_generator_inherits_persona_and_provider_when_empty():
    gen = _make_generator({"persona_id": "", "llm_provider_id": ""}, _chat_stars())
    assert await gen._get_persona() == "prompt:series-persona"
    assert (await gen._get_provider()).id == "series-reply"


@pytest.mark.asyncio
async def test_world_generator_explicit_config_takes_priority():
    gen = _make_generator(
        {"persona_id": "explicit-persona", "llm_provider_id": "explicit-p"},
        _chat_stars(),
    )
    assert await gen._get_persona() == "prompt:explicit-persona"
    assert (await gen._get_provider()).id == "explicit-p"


@pytest.mark.asyncio
async def test_world_generator_safe_fallback_without_chat_dynamics():
    for stars in ({}, _chat_stars(activated=False)):
        gen = _make_generator({"persona_id": "", "llm_provider_id": ""}, stars)
        assert await gen._get_persona() == "prompt:host-default"
        assert (await gen._get_provider()).id == "host-using"
