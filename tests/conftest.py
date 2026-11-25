"""Shared pytest fixtures for dynamics_world test suite."""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
import types
from pathlib import Path

_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_DIR = os.path.dirname(_TESTS_DIR)
_PARENT_DIR = os.path.dirname(_PLUGIN_DIR)
for _path in (_PARENT_DIR, _TESTS_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)


def _install_offline_astrbot_stubs() -> None:
    """Install minimal AstrBot SDK stubs only when the real SDK is absent."""
    if "astrbot" in sys.modules or importlib.util.find_spec("astrbot") is not None:
        return

    def _mod(name: str) -> types.ModuleType:
        m = types.ModuleType(name)
        m.__path__ = []  # type: ignore[attr-defined]
        sys.modules[name] = m
        return m

    class _Filter:
        class PermissionType:
            ADMIN = "admin"
            MEMBER = "member"

        class EventMessageType:
            ALL = "all"
            GROUP_MESSAGE = "group"
            PRIVATE_MESSAGE = "private"

        def _deco(self, *args, **kwargs):
            def deco(fn):
                return fn

            return deco

        command = _deco
        command_group = _deco
        on_llm_request = _deco
        on_llm_response = _deco
        after_message_sent = _deco
        permission_type = _deco
        event_message_type = _deco
        llm_tool = _deco

    class AstrMessageEvent:
        pass

    class Context:
        pass

    class Star:
        def __init__(self, context=None):
            self.context = context

    class AstrBotConfig(dict):
        def save_config(self):
            return None

    class ProviderRequest:
        def __init__(self, system_prompt: str = ""):
            self.system_prompt = system_prompt
            self.contexts: list = []
            self.prompt = ""
            self.extra_user_content_parts: list = []

    class TextPart:
        def __init__(self, text: str = ""):
            self.text = text

        def mark_as_temp(self):
            return self

    class StarTools:
        @staticmethod
        def get_data_dir(plugin_name: str = "") -> Path:
            return Path(_PLUGIN_DIR) / ".tmp-test-data"

    class StreamingResponse:
        def __init__(self, content, *, media_type=None, status_code=200, headers=None):
            self.body_iterator = content
            self.media_type = media_type
            self.status_code = status_code
            self.headers = dict(headers or {})

    class _Sp:
        def __init__(self):
            self.data: dict = {}

        async def get_async(self, scope=None, scope_id=None, key=None, default=None):
            return self.data.get((scope, scope_id, key), default)

        async def put_async(self, scope=None, scope_id=None, key=None, value=None):
            self.data[(scope, scope_id, key)] = value

    async def require_dashboard_user(raw):
        state = getattr(raw, "state", None)
        dashboard_g = getattr(state, "dashboard_g", None)
        if dashboard_g is not None:
            username = getattr(dashboard_g, "username", None)
            if username is None and hasattr(dashboard_g, "get"):
                username = dashboard_g.get("username")
            if isinstance(username, str) and username.strip():
                return username
        raise PermissionError("未授权")

    astrbot = _mod("astrbot")
    api = _mod("astrbot.api")
    web = _mod("astrbot.api.web")
    ev = _mod("astrbot.api.event")
    star = _mod("astrbot.api.star")
    core = _mod("astrbot.core")
    _mod("astrbot.core.config")
    core_cfg = _mod("astrbot.core.config.astrbot_config")
    _mod("astrbot.core.provider")
    entities = _mod("astrbot.core.provider.entities")
    _mod("astrbot.core.star")
    core_ctx = _mod("astrbot.core.star.context")
    star_tools = _mod("astrbot.core.star.star_tools")
    _mod("astrbot.core.star.filter")
    fcmd = _mod("astrbot.core.star.filter.command")
    _mod("astrbot.core.agent")
    agent_msg = _mod("astrbot.core.agent.message")
    _mod("astrbot.dashboard")
    _mod("astrbot.dashboard.api")
    dash_auth = _mod("astrbot.dashboard.api.auth")

    api.logger = logging.getLogger("astrbot")
    api.AstrBotConfig = AstrBotConfig
    api.sp = _Sp()
    web.json_response = lambda data=None, **kwargs: {} if data is None else data
    web.error_response = lambda message, data=None, **kwargs: {
        "status": "error",
        "message": message,
        "data": data,
    }
    web.request = None
    web.StreamingResponse = StreamingResponse
    ev.AstrMessageEvent = AstrMessageEvent
    ev.filter = _Filter()
    star.Context = Context
    star.Star = Star
    core_cfg.AstrBotConfig = AstrBotConfig
    core_ctx.Context = Context
    star_tools.StarTools = StarTools
    entities.ProviderRequest = ProviderRequest
    fcmd.GreedyStr = str
    agent_msg.TextPart = TextPart
    dash_auth.require_dashboard_user = require_dashboard_user
    astrbot.api = api
    astrbot.core = core


_install_offline_astrbot_stubs()

from test_spatial import rig  # noqa: E402, F401
