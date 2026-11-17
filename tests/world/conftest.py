"""测试用的 AstrBot 桩件。

插件只依赖 astrbot 的几个导入点，这里替换成最小实现，
这样不用安装 AstrBot 就能 import main.py 并实例化插件。
"""
from __future__ import annotations

import asyncio
import os
import sys
import types

PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PLUGIN_NAME = os.path.basename(PLUGIN_DIR)
PARENT_DIR = os.path.dirname(PLUGIN_DIR)

if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)


def _mod(name: str) -> types.ModuleType:
    m = types.ModuleType(name)
    m.__path__ = []  # type: ignore[attr-defined]
    sys.modules[name] = m
    return m


class _Filter:
    class PermissionType:
        ADMIN = "admin"
        MEMBER = "member"

    def _deco(self, *args, **kwargs):
        def deco(fn):
            return fn

        return deco

    command = _deco
    on_llm_request = _deco
    permission_type = _deco
    event_message_type = _deco
    llm_tool = _deco


class AstrMessageEvent:  # pragma: no cover - 仅占位
    pass


class Context:
    pass


class Star:
    def __init__(self, context=None):
        self.context = context


class AstrBotConfig(dict):
    pass


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


class _Sp:
    """astrbot.api.sp 的最小实现（会话级配置读写）。"""

    def __init__(self):
        self.data: dict = {}

    async def get_async(self, scope=None, scope_id=None, key=None, default=None):
        return self.data.get((scope, scope_id, key), default)

    async def put_async(self, scope=None, scope_id=None, key=None, value=None):
        self.data[(scope, scope_id, key)] = value


def install_stubs() -> None:
    import importlib.util
    if "astrbot" in sys.modules or importlib.util.find_spec("astrbot") is not None:
        return

    astrbot = _mod("astrbot")
    api = _mod("astrbot.api")
    web = _mod("astrbot.api.web")
    ev = _mod("astrbot.api.event")
    star = _mod("astrbot.api.star")
    core = _mod("astrbot.core")
    _mod("astrbot.core.provider")
    entities = _mod("astrbot.core.provider.entities")
    _mod("astrbot.core.star")
    _mod("astrbot.core.star.filter")
    fcmd = _mod("astrbot.core.star.filter.command")
    _mod("astrbot.core.agent")
    agent_msg = _mod("astrbot.core.agent.message")

    api.AstrBotConfig = AstrBotConfig
    # Keep web tests independent of an installed Quart application's context.
    web.json_response = lambda data=None, **kwargs: {} if data is None else data
    web.error_response = lambda message, data=None, **kwargs: {
        "status": "error", "message": message, "data": data,
    }
    web.request = None
    api.sp = _Sp()
    ev.AstrMessageEvent = AstrMessageEvent
    ev.filter = _Filter()
    star.Context = Context
    star.Star = Star
    entities.ProviderRequest = ProviderRequest
    fcmd.GreedyStr = str
    agent_msg.TextPart = TextPart
    astrbot.api = api
    astrbot.core = core


# SDK stubs are not installed when the real AstrBot SDK is present.


def pytest_configure(config):  # noqa: ARG001
    install_stubs()


def run(coro):
    """不依赖 pytest-asyncio 的协程执行 helper。"""
    return asyncio.run(coro)


class FakeEvent:
    """最小可用的 AstrMessageEvent 替身。"""

    def __init__(self, umo="test:FriendMessage:10001", message="", admin=True):
        self.unified_msg_origin = umo
        self.message_str = message
        self.role = "admin" if admin else "member"
        self._admin = admin
        self.sent: list[str] = []
        self.stopped = False

    def get_session_id(self):
        return self.unified_msg_origin

    def is_admin(self):
        return self._admin

    def plain_result(self, text):
        self.sent.append(text)
        return text

    def stop_event(self):
        self.stopped = True


class FakeContext:
    """plugin_data_dir 指向 tmp_path，避免测试污染真实数据目录。"""

    def __init__(self, data_dir):
        self.plugin_data_dir = str(data_dir)
        self.persona_manager = None
        self.conversation_manager = None

# ---- 常用 fixture ----

import pytest  # noqa: E402


@pytest.fixture
def wb_main():
    import importlib

    return importlib.import_module(f"{PLUGIN_NAME}.world.service")


@pytest.fixture
def make_plugin(wb_main, tmp_path):
    """构造插件实例；seed=True 时执行 initialize()（会装入内置样本世界书/角色卡）。"""

    def _make(config=None, seed=False):
        inst = wb_main.WorldService(FakeContext(tmp_path), config or {}, tmp_path)
        if seed:
            run(inst.initialize())
        return inst

    return _make


@pytest.fixture
def ProviderRequestCls():
    from astrbot.core.provider.entities import ProviderRequest

    return ProviderRequest
