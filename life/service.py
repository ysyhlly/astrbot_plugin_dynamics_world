# ruff: noqa: E402
# Refresh owned dependencies before importing them during a scoped hot reload.


import asyncio
import datetime
import inspect
import json
import re
import time
from collections.abc import AsyncGenerator

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.core.agent.message import TextPart
from astrbot.core.provider.entities import ProviderRequest

from .. import creative_projects
from .core.generator import Generator
from .core.injector import (
    AUTO_LIFE_GUIDANCE,
    build_fake_tool_call,
    remove_fake_tool_call_from_context,
)
from .core.narrative import NarrativeEngine, normalize_scope
from .core.narrative_io import WorldIOBusy, WorldIOClosed
from .core.narrative_prompt import build_narrative_prompt_parts
from .core.narrative_types import AVAILABILITIES, _identity
from .core.state import (
    CHINA_TIMEZONE,
    NATURAL_SLOT_NAMES,
    OPTIONAL_TIMELINE_FIELDS,
    DataManager,
    LifeState,
    SlotMatch,
    find_slot_by_name,
    format_datetime,
    format_interval,
    minute_of_day,
    parse_clock_time,
    resolve_entry_intervals,
    select_current_slot,
)


def _extract_args_after(message_str: str, command: str) -> str | None:
    """提取命令之后的完整尾随文本。

    Args:
        message_str: 原始事件消息。
        command: 命令前缀（不含前导斜杠）。

    Returns:
        尾随文本，没有额外文本时返回 ``None``。
    """
    text = message_str.lstrip("/").strip()
    text = re.sub(r"\s+", " ", text)  # 规范化空白以便命令匹配。
    prefix = f"{command} "
    idx = text.find(prefix)
    if idx == -1:
        return None
    remainder = text[idx + len(prefix) :].strip()
    return remainder or None


class NarrativeProviderUnavailable(RuntimeError):
    """A deliberately selected background provider is missing or incompatible."""

    status_code = "provider_unavailable"


class NarrativePolicyRefusal(RuntimeError):
    """An explicit Gemini PROHIBITED_CONTENT refusal, with no body text stored."""

    code = "PROHIBITED_CONTENT"


def _is_explicit_prohibited_content(value) -> bool:
    """Match the provider's exact enum/string marker without classifying generic errors."""
    if value is None:
        return False
    name = getattr(value, "name", None)
    candidates = (str(value), str(name) if name is not None else "")
    return any(item.strip().upper() == "PROHIBITED_CONTENT" for item in candidates)


class LifeService:
    def __init__(self, context, config, data_dir, world, is_active):
        self.context, self.config, self.data_dir = context, config, data_dir
        self.world, self.is_active = world, is_active
        self.state_file = data_dir / "life_state.json"
        self._loop_events: dict[str, asyncio.Event] = {}

    async def initialize(self) -> None:
        """初始化存储、生成器和午夜定时调度。"""
        self.data_mgr = DataManager(self.state_file)
        self.generator = Generator(self.context, self.config, self.data_mgr)
        self.narrative = NarrativeEngine(
            self.data_dir / "narrative.sqlite3",
            self.config,
            self._narrative_model,
            owner_active=self.is_active,
        )
        from ..world_spaces import WorldSpaceService

        self.narrative.world_spaces = WorldSpaceService(self.narrative)
        from ..spatial import SpatialState

        self.narrative.spatial = SpatialState(self.narrative)
        from ..weather import EnvironmentService

        self.narrative.environment = EnvironmentService(self.narrative)
        from ..keepsakes import KeepsakeTimelineService

        self.narrative.keepsakes = KeepsakeTimelineService(self.narrative)
        from ..garden_ecology import EcologyService

        self.narrative.ecology = EcologyService(self.narrative)
        from ..mailbox_visitors import MailboxVisitorService

        self.narrative.mailbox = MailboxVisitorService(self.narrative)
        from ..scenes import SceneService

        self.narrative.scenes = SceneService(self.narrative)
        from ..visual_context import WorldVisualContext

        self.narrative.visuals = WorldVisualContext(self.narrative)
        from ..horizons_sync import HorizonsSyncService

        if self.narrative.horizons is None:
            self.narrative.horizons = HorizonsSyncService(self.narrative)
        from ..causal_life import CausalLifeService

        self.narrative.causal = CausalLifeService(self.narrative)
        self.narrative.causal.card_resolver = lambda card_id: (
            card.to_dict() if (card := self.world.store.get_card(card_id)) else None
        )
        try:
            self.narrative.migrate_legacy(self.state_file)
        except Exception as exc:
            logger.error(
                f"[DynamicLifeState] Legacy import failed: {type(exc).__name__}"
            )
        from ..resident_runtime import ResidentRunner

        self._loop_events = {
            "narrative": asyncio.Event(),
            "resident": asyncio.Event(),
        }
        self.narrative.on_activity = self._wake_on_activity
        self.residents = ResidentRunner(self)
        self.narrative.resident_runner = self.residents
        self._resident_task = asyncio.create_task(self._resident_loop())
        self._narrative_task = asyncio.create_task(self._narrative_loop())
        self._outreach_task = asyncio.create_task(self._outreach_loop())
        if self.config.get("mode", "narrative") == "legacy":
            self._start_scheduler()

    def _wake_on_activity(self) -> None:
        for ev in getattr(self, "_loop_events", {}).values():
            ev.set()

    def note_activity(self, now: float | None = None) -> None:
        """Reset quiet-period backoff on chat or member interaction."""
        narrative = getattr(self, "narrative", None)
        if narrative is not None and hasattr(narrative, "note_activity"):
            narrative.note_activity(now)
        else:
            self._wake_on_activity()

    async def _sleep_loop(self, kind: str, seconds: float) -> None:
        ev = getattr(self, "_loop_events", {}).get(kind)
        if ev is None:
            await asyncio.sleep(seconds)
            return
        ev.clear()
        try:
            await asyncio.wait_for(ev.wait(), timeout=seconds)
        except TimeoutError:
            pass

    async def terminate(self) -> None:
        """停止午夜定时调度。"""
        self._stop_scheduler()
        tasks = [
            task
            for name in ("_narrative_task", "_outreach_task", "_resident_task")
            if (task := getattr(self, name, None)) is not None
        ]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if hasattr(self, "narrative"):
            await self.narrative.environment.close()
            await self.narrative.close()

    async def _narrative_loop(self) -> None:
        """Own the periodic task and cancel its provider work on unload."""
        while True:
            try:
                if self.is_active():
                    self.narrative.environment.schedule_all()
                    await self.narrative.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    f"[DynamicLifeState] Narrative tick failed: {type(exc).__name__}"
                )
            sleep = getattr(self, "_sleep_loop", None)
            if callable(sleep):
                await sleep("narrative", 30)
            else:
                await asyncio.sleep(30)

    async def _resident_loop(self) -> None:
        while True:
            try:
                await self.residents.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    f"[DynamicsWorld] Resident tick failed: {type(exc).__name__}"
                )
            sleep = getattr(self, "_sleep_loop", None)
            if callable(sleep):
                await sleep("resident", 30)
            else:
                await asyncio.sleep(30)

    async def _outreach_loop(self) -> None:
        """Slow contact inference must not hold up the world's clock."""
        while True:
            try:
                if self.is_active():
                    await self.narrative.review_outreach()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "[DynamicLifeState] Outreach review failed type=%s",
                    type(exc).__name__,
                )
            await asyncio.sleep(30)

    def _worldbook(self):
        return self.world

    async def _character(self, scope: dict, event=None) -> dict:
        """Read the authoritative binding without falling back past explicit removal."""
        worldbook = self._worldbook()
        if worldbook is None:
            return {"disabled": True, "reason": "worldbook_unavailable"}
        result = await worldbook.get_character_context(scope, event)
        if not isinstance(result, dict) or result.get("schema_version", 1) != 1:
            return {"disabled": True, "reason": "invalid_character_context"}
        return result

    async def _scope_for_event(self, event: AstrMessageEvent) -> dict | None:
        """Return a concrete matching character; never inject one persona into another."""
        umo = str(event.unified_msg_origin)
        scope = {
            "platform": umo.split(":", 1)[0],
            "umo": umo,
            "persona_id": str(self.config.get("persona_id", "")),
            "instance_id": str(self.config.get("persona_id", "")),
        }
        character = await self._character(scope, event)
        persona_id = str(character.get("persona_id", ""))
        if character.get("disabled") or not persona_id:
            return None
        configured = str(self.config.get("persona_id", ""))
        if configured and configured != persona_id:
            return None
        scope.update(persona_id=persona_id, instance_id=persona_id)
        return normalize_scope(scope)

    async def _narrative_model(self, request: dict) -> dict:
        """Call the configured provider directly with no chat hooks or tools."""
        if not self.is_active():
            raise NarrativeProviderUnavailable("World is inactive")
        character = await self._character(request["scope"])
        if (
            character.get("disabled")
            or character.get("persona_id") != request["scope"]["persona_id"]
        ):
            raise ValueError("Narrative character binding is unavailable")
        selected_provider_id = str(self.config.get("narrative_provider_id", "")).strip()
        if selected_provider_id:
            lookup = getattr(self.context, "get_provider_by_id", None)
            if not callable(lookup):
                raise NarrativeProviderUnavailable(
                    "Selected narrative provider lookup is unavailable"
                )
            provider = lookup(selected_provider_id)
        else:
            # Preserve older installations until an operator explicitly selects
            # a dedicated background provider. An explicit missing ID fails closed.
            provider = await self.generator._get_provider()
        if provider is None:
            raise NarrativeProviderUnavailable("Narrative provider is unavailable")
        text_chat = getattr(provider, "text_chat", None)
        if not callable(text_chat):
            raise NarrativeProviderUnavailable(
                "Selected narrative provider has no text_chat method"
            )
        if request.get("resident_isolated"):
            from ..resident_runtime import build_prompt_parts

            system_prompt, prompt = build_prompt_parts(request)
        else:
            system_prompt, prompt = build_narrative_prompt_parts(request, character)
        from .core.narrative_schema import narrative_schema

        kwargs = {
            "session_id": "dynamics_world_narrative_" + str(time.time_ns()),
            "contexts": [],
        }
        if getattr(provider, "provider_config", {}).get(
            "type"
        ) == "googlegenai_chat_completion" or any(
            base.__module__.endswith(".gemini_source")
            for base in type(provider).__mro__
        ):
            kwargs["optimizer_operation_id"] = str(
                request.get("inference_call_id", "")
            ).replace("-", "")
        parameters = inspect.signature(text_chat).parameters
        accepts_kwargs = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters.values()
        )
        if "system_prompt" in parameters or accepts_kwargs:
            kwargs["system_prompt"] = system_prompt
        else:
            prompt = f"{system_prompt}\n{prompt}"
        supports_retry_limit = "request_max_retries" in parameters or accepts_kwargs
        if supports_retry_limit:
            kwargs["request_max_retries"] = 1
        elif selected_provider_id:
            raise NarrativeProviderUnavailable(
                "Narrative provider cannot enforce the retry limit"
            )
        if "func_tool" in parameters or accepts_kwargs:
            kwargs["func_tool"] = None
        if "response_format" in parameters or accepts_kwargs:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "narrative_change",
                    "schema": narrative_schema(request),
                },
            }
        response = await text_chat(prompt=prompt, **kwargs)
        current = await self._character(request["scope"])
        if not self.is_active() or current.get("fingerprint") != character.get(
            "fingerprint"
        ):
            raise NarrativeProviderUnavailable(
                "Character changed during life generation"
            )
        raw_completion = getattr(response, "raw_completion", None)
        prompt_feedback = getattr(raw_completion, "prompt_feedback", None)
        if _is_explicit_prohibited_content(
            getattr(prompt_feedback, "block_reason", None)
        ):
            raise NarrativePolicyRefusal("PROHIBITED_CONTENT")
        candidates = getattr(raw_completion, "candidates", None) or []
        if any(
            _is_explicit_prohibited_content(getattr(candidate, "finish_reason", None))
            for candidate in candidates
        ):
            raise NarrativePolicyRefusal("PROHIBITED_CONTENT")
        text = self.generator._extract_completion_text(response)
        return self.generator._extract_json(text)

    async def get_snapshot(self, scope: dict) -> dict:
        """Return schema-v1 scoped state through the public integration API."""
        return await self.narrative.get_snapshot(scope)

    async def read_current_world_state(self, scope: dict, focus: str) -> str:
        """Read confirmed actor facts without advancing the world.

        Args:
            scope: The current event's normalized character and session scope.
            focus: The requested activity, location, scene, weather, or project.

        Returns:
            Bounded recorded facts, or an explicit unavailable/unknown result.
        """
        unavailable = "当前会话尚未启用持续生活。"
        if self.config.get("mode", "legacy") != "narrative":
            if not self._is_session_enabled(scope["umo"]):
                return unavailable
            now = self._now()
            state, _ = self._select_current_state(now)
            match = (
                select_current_slot(state.timeline, minute_of_day(now))
                if state
                else None
            )
            if not match or not any(match.entry is entry for entry in state.timeline):
                return "当前时段没有日程记录。"
            if focus == "activity":
                return (
                    "此时段的日程安排（实际活动未确认）：" + match.entry.schedule[:220]
                )
            if focus == "location" and match.entry.extra_fields.get("location"):
                return (
                    "此时段日程记录的位置（实际位置未确认）："
                    + match.entry.extra_fields["location"][:60]
                )
            return "旧版日程没有这类已确认的状态。"

        engine = self.narrative
        if not engine._snapshot_allowed(scope):
            return unavailable
        try:
            result = await engine._snapshot_io.run(
                self._read_current_world_state, scope, focus
            )
        except (WorldIOBusy, WorldIOClosed):
            return "角色世界状态暂不可用。"
        return result if engine._snapshot_allowed(scope) else unavailable

    def _read_current_world_state(self, scope: dict, focus: str) -> str:
        """Project one category from a consistent, query-only transaction.

        Args:
            scope: The authorized character and session scope.
            focus: The requested category of recorded world facts.

        Returns:
            Text containing only the requested actor facts without private prose.
        """
        engine = self.narrative
        with engine._db(notify=False) as db:
            db.execute("PRAGMA query_only = ON")
            db.execute("BEGIN")
            now = engine.clock()
            actor = engine.spatial.snapshot(db, scope, now)
            if focus == "weather":
                environment = engine.environment.snapshot(db, scope, now, actor)
                if environment.get("status") == "ready":
                    brief = engine.environment.brief(environment)
                    if brief:
                        return brief.removeprefix("；")
                return "当前天气未确认。"

            _, _, scene = engine.scenes.load(db, scope)
            scene = scene or {}
            if focus == "project":
                projects = sorted(
                    scene.get("projects", {}).values(),
                    key=lambda project: (
                        project["status"] == "active",
                        project["updated_at"],
                    ),
                    reverse=True,
                )
                rows = [creative_projects.summary(project) for project in projects[:3]]
                if rows:
                    stages = {"draft": "初稿阶段", "revision": "修订阶段"}
                    statuses = {
                        "active": "未定稿",
                        "paused": "已暂停",
                        "abandoned": "已放弃",
                    }
                    return "已记录的项目进展：\n" + "\n".join(
                        f"{row['title'][:60]} · {stages.get(row['stage'], row['stage_label'])}"
                        f"{' · ' + statuses[row['status']] if row['status'] in statuses else ''}"
                        f"（初稿 {row['draft_parts']}/{row['target_parts']} 段）"
                        for row in rows
                    )
                return "没有已记录的创作项目。"

            if focus in ("location", "scene"):
                journey = actor.get("journey")
                if journey:
                    if actor.get("paused"):
                        return "前往" + journey["destination_name"] + "的行程已暂停。"
                    if journey["arrives_at"] <= now:
                        return "尚无已抵达的记录，当前位置待确认。"
                    return "仍在前往" + journey["destination_name"] + "的途中。"
                if actor.get("phase") != "located":
                    return "当前位置未确认。"
                lines = ["当前位置：" + actor["place_name"][:60]]
                room = scene.get("rooms", {}).get(scene.get("room_id")) or {}
                if room.get("place_id") == actor["place_id"]:
                    lines.append("房间：" + room["name"][:60])
                if focus == "scene":
                    live_scene = engine.scenes.snapshot(db, scope, now)
                    visible = []
                    for item in live_scene.get("items", []):
                        if not (item.get("visible") or item.get("carried")):
                            continue
                        fields = (
                            "carried",
                            "page",
                            "pages",
                            "servings",
                            "capacity",
                            "powered",
                            "wet",
                        )
                        if item["kind"] == "umbrella":
                            fields += ("open",)
                        details = {
                            key: item[key]
                            for key in fields
                            if type(item.get(key)) in (int, float, bool)
                        }
                        visible.append(
                            dict(
                                name=item["name"][:60],
                                kind=item["kind"][:24],
                                **details,
                            )
                        )
                        if len(visible) == 6:
                            break
                    if visible:
                        lines.append(
                            "眼前或随身物品：" + json.dumps(visible, ensure_ascii=False)
                        )
                return "\n".join(lines)

            row = db.execute(
                "SELECT state FROM lives WHERE identity=?", (_identity(scope),)
            ).fetchone()
            state = json.loads(row["state"]) if row else {}
            flow = scene.get("flow")
            if flow and (
                scene.get("paused_at") is not None or flow["step_ends_at"] <= now
            ):
                return "当前活动未确认。"
            journey = actor.get("journey")
            if journey and (actor.get("paused") or journey["arrives_at"] <= now):
                return "当前活动未确认。"
            if flow and flow["step_started_at"] <= now < flow["step_ends_at"]:
                return "正在" + flow["label"][:120] + "（仍在进行）。"
            if journey:
                return "正在前往" + journey["destination_name"][:60] + "（尚未抵达）。"
            if state.get("valid_from", 0) <= now < state.get(
                "valid_until", 0
            ) and state.get("activity") not in (None, "", "未知"):
                return "角色世界内的当前活动：" + state["activity"][:220]
            return "当前活动未确认。"

    def record_horizon_reading(self, scope: dict, payload: dict, *, owner=None) -> dict:
        """Persist a verified reading bookmark through the public integration API."""
        return self.narrative.record_horizon_reading(
            scope, payload, owner=owner or self
        )

    def peek_context_revision(self, scope: dict) -> dict:
        """Publish the RAM-only state epoch for versioned concurrent readers."""
        return self.narrative.peek_context_revision(scope)

    async def ingest_events(self, events: list[dict]) -> dict:
        """Queue typed real events and actual delivery receipts."""
        return await self.narrative.ingest_events(events)

    async def advance(
        self, events: list[dict], expected_revision: int | None = None
    ) -> dict:
        """Apply narrative effects only if the captured revision remains current."""
        return await self.narrative.advance(events, expected_revision)

    async def list_due_intents(self, now: float | None = None) -> list[dict]:
        """Offer motivations to Chat Dynamics; this plugin never sends them itself."""
        return await self.narrative.list_due_intents(now)

    async def observe_member_activity(
        self, umo: str, uid: str, message_id: str, occurred_at: float
    ) -> dict:
        """Cancel obsolete waiting without retaining message contents."""
        return await asyncio.to_thread(
            self.narrative.observe_member_activity, umo, uid, message_id, occurred_at
        )

    async def update_intent(
        self, intent_id: str, status: str, receipt: dict | None = None
    ) -> dict:
        """Store the coordinator's durable delivery lifecycle result."""
        return await self.narrative.update_intent(intent_id, status, receipt)

    async def get_intent(self, intent_id: str) -> dict:
        """Read an intent even when pause or timing removes it from the due list."""
        return await self.narrative.get_intent(intent_id)

    async def cancel_intent(self, intent_id: str) -> dict:
        """Cancel an administrator-selected motivation."""
        return await self.narrative.cancel_intent(intent_id)

    async def get_narrative_admin(self, scope: dict) -> dict:
        """Read diagnostics for the authenticated coordinator admin panel."""
        return await self.narrative.get_narrative_admin(scope)

    async def correct_state(self, scope: dict, patch: dict) -> dict:
        """Record an administrator correction without overwriting history."""
        return await self.narrative.correct_state(scope, patch)

    async def set_paused(
        self, paused: bool, scope: dict | None = None, *, proactive_only: bool = False
    ) -> dict:
        """Persist narrative or proactive pause settings."""
        return await self.narrative.set_paused(
            paused, scope, proactive_only=proactive_only
        )

    async def set_outreach_paused(
        self, paused: bool, scope: dict | None = None
    ) -> dict:
        """Pause proactive contacts while allowing life to continue."""
        return await self.narrative.set_outreach_paused(paused, scope)

    # =========================
    # Scheduler
    # =========================

    def _now(self) -> datetime.datetime:
        """返回中国标准时间的当前日期时间。"""
        return datetime.datetime.now(CHINA_TIMEZONE)

    def _current_date(
        self,
        now: datetime.datetime | None = None,
    ) -> datetime.date:
        """返回中国标准时间的日期。

        Args:
            now: 可选的时间，由调用方或测试提供。

        Returns:
            本地日期。
        """
        value = now or self._now()
        if value.tzinfo is None:
            value = value.replace(tzinfo=CHINA_TIMEZONE)
        else:
            value = value.astimezone(CHINA_TIMEZONE)
        return value.date()

    def _select_current_state(
        self,
        now: datetime.datetime,
    ) -> tuple[LifeState | None, datetime.date]:
        """为当前北京时间选取一个成功生成的状态。

        Args:
            now: 当前日期时间。

        Returns:
            匹配的状态（如果有）和捕获的目标日期。
        """
        target_date = self._current_date(now)
        state = self.data_mgr.get_current(target_date.isoformat())
        if state is None or state.status != "ok":
            return None, target_date
        return state, target_date

    def _start_scheduler(self) -> None:
        """启动固定的本地午夜定时调度器。"""
        try:
            self._scheduler = AsyncIOScheduler(
                timezone=CHINA_TIMEZONE,
                executors={"default": AsyncIOExecutor()},
                job_defaults={
                    "coalesce": True,
                    "max_instances": 1,
                    "misfire_grace_time": 120,
                },
            )
            self._scheduler.add_job(
                self._daily_generate,
                "cron",
                hour=0,
                minute=0,
                id="dynamic_life_state_daily",
            )
            self._scheduler.start()
            logger.info(
                f"[DynamicLifeState] Scheduler started for daily generation "
                f"at 00:00 in {CHINA_TIMEZONE.key}"
            )
        except Exception as e:
            logger.error(f"[DynamicLifeState] Scheduler startup failed: {e}")

    def _stop_scheduler(self) -> None:
        """停止正在运行的定时调度器。"""
        try:
            if hasattr(self, "_scheduler") and self._scheduler.running:
                self._scheduler.shutdown()
        except Exception:
            pass

    async def _daily_generate(self) -> None:
        """生成当前中国标准时间日期的状态。"""
        if self.config.get("mode", "legacy") == "narrative":
            await self.narrative.tick()
            return
        if not self.is_active():
            return
        now = self._now()
        data, target_date = self._select_current_state(now)
        if data:
            logger.info(
                f"[DynamicLifeState] State for {target_date.isoformat()} "
                "already exists; skipping generation"
            )
            return
        await self.generator.generate(target_date)

    # =========================
    # LLM request hook
    # =========================

    async def on_llm_request(
        self,
        event: AstrMessageEvent,
        req: ProviderRequest,
    ) -> None:
        """Attach coarse life context to unmanaged chat requests."""
        self.note_activity()

        marker = (
            event.get_extra("_narrative_managed_v1", None)
            if hasattr(event, "get_extra")
            else None
        )
        internal = (
            event.get_extra("_narrative_internal_v1", False)
            if hasattr(event, "get_extra")
            else False
        )
        if marker or internal:
            return
        get_extra = getattr(event, "get_extra", None)
        blocking_context = (
            get_extra("_autonomous_blocking_context_v1", None)
            if callable(get_extra)
            else None
        )
        if (
            isinstance(blocking_context, dict)
            and blocking_context.get("schema_version") == 1
            and blocking_context.get("projection_restricted") is True
        ):
            return
        narrative_mode = self.config.get("mode", "legacy") == "narrative"
        if narrative_mode and self.narrative._private_peer(
            str(event.unified_msg_origin)
        ):
            return
        scope = await self._scope_for_event(event)
        if scope is None:
            return
        if narrative_mode:
            snapshot = await self.get_snapshot(scope)
            if not snapshot.get("managed"):
                return
            availability = snapshot.get("availability")
            stale = snapshot.get("stale") is not False
            if stale or availability not in AVAILABILITIES:
                availability = "unknown"
            validity = "待确认" if stale else "有效"
            req.system_prompt = (
                f"{getattr(req, 'system_prompt', '') or ''}\n{AUTO_LIFE_GUIDANCE}"
            )
            req.extra_user_content_parts.append(
                TextPart(
                    text=f"<life_state>可交互状态={availability}；时效={validity}</life_state>"
                ).mark_as_temp()
            )
            return

        # 会话过滤
        if not self._is_session_enabled(event.unified_msg_origin):
            return

        now = self._now()
        data, target_date = self._select_current_state(now)
        if data is None:
            if self.generator.is_generating:
                return  # 共享生成任务执行期间跳过注入。
            result = await self.generator.generate(target_date)
            if not result.succeeded or result.state is None:
                return  # 无可用的有效状态时跳过注入。
            data = result.state

        # 选取当前时段。
        current_match = select_current_slot(data.timeline, minute_of_day(now))

        # 解析配置的注入方式。
        injection_method = str(
            self.config.get("injection_mode", "extra_user_content_parts")
        )
        injection_method = self._resolve_injection_method(req, injection_method)

        # 移除上一次的伪注入。
        self._cleanup_previous_injection(req)

        req.system_prompt = (
            f"{getattr(req, 'system_prompt', '') or ''}\n{AUTO_LIFE_GUIDANCE}"
        )
        validity = (
            "当前时段有记录"
            if current_match
            and any(current_match.entry is entry for entry in data.timeline)
            else "当前时段无记录"
        )
        inject_text = f"<life_state>日程时效={validity}</life_state>"
        if injection_method == "extra_user_content_parts":
            req.extra_user_content_parts.append(
                TextPart(text=inject_text).mark_as_temp()
            )
            if self.config.get("debug_mode", False):
                logger.debug(f"[DynamicLifeState] Injected content:\n{inject_text}")

        elif injection_method == "fake_tool_call":
            fake_messages = build_fake_tool_call(inject_text)
            req.contexts.extend(fake_messages)
            if self.config.get("debug_mode", False):
                logger.debug(
                    f"[DynamicLifeState] Injected fake tool call:\n"
                    f"{fake_messages[1]['content']}"
                )

        if self.config.get("debug_mode", False):
            logger.info(
                f"[DynamicLifeState] Injection method={injection_method}, "
                f"date={data.date}, "
                f"slot={current_match.entry.time if current_match else 'N/A'}"
            )

    # =========================
    # Session filter
    # =========================

    def _is_session_enabled(self, unified_msg_origin: str) -> bool:
        """返回当前会话是否启用了生活状态注入。

        Args:
            unified_msg_origin: AstrBot 统一消息来源。

        Returns:
            会话是否通过配置的列表模式检查。
        """
        mode = str(self.config.get("session_list_mode", "whitelist")).strip()
        session_list: list[str] = list(self.config.get("session_list", []) or [])

        if mode == "none":
            return True
        if mode == "whitelist":
            return unified_msg_origin in session_list
        if mode == "blacklist":
            return unified_msg_origin not in session_list
        if getattr(self, "_warned_invalid_session_mode", None) != mode:
            logger.warning(
                f"[DynamicLifeState] Invalid session_list_mode {mode!r}; "
                "falling back to whitelist behavior"
            )
            self._warned_invalid_session_mode = mode
        return unified_msg_origin in session_list

    # =========================
    # Injection fallback
    # =========================

    def _resolve_injection_method(self, req: ProviderRequest, configured: str) -> str:
        """当 provider 不支持伪工具调用时回退到备选方式。

        Args:
            req: 用于解析当前 provider 的请求对象。
            configured: 配置的注入方式。

        Returns:
            兼容的注入方式。
        """
        if configured != "fake_tool_call":
            return configured
        try:
            provider = self.context.get_using_provider(req.session_id)
            provider_config = getattr(provider, "provider_config", {})
            provider_type = (
                str(provider_config.get("type", ""))
                if isinstance(provider_config, dict)
                else ""
            )
            model = provider.get_model() if hasattr(provider, "get_model") else ""
            if "googlegenai" in provider_type or "gemini" in str(model).lower():
                logger.info(
                    "[DynamicLifeState] Gemini does not support fake_tool_call; "
                    "falling back to extra_user_content_parts"
                )
                return "extra_user_content_parts"
        except Exception:
            pass
        return configured

    # =========================
    # Injection cleanup
    # =========================

    def _cleanup_previous_injection(self, req: ProviderRequest) -> None:
        """移除上一次的伪工具调用注入。

        Args:
            req: 可变的 provider 请求。
        """
        remove_fake_tool_call_from_context(req.contexts)

    # =========================
    # LLM tool for full-state queries
    # =========================

    async def get_full_dynamic_life_state(
        self, event: AstrMessageEvent, date: str = ""
    ) -> str:
        """获取 Bot 当前或指定日期的完整生活状态。

        date 参数为可选，格式 YYYY-MM-DD。不传则默认返回今天的状态。
        仅在用户明确询问"今天一整天在做什么""全天状态""完整日程""其他时间段的安排""回顾某天的状态"或类似问题时调用。

        Args:
            date (string): 可选的 YYYY-MM-DD 日期。

        Returns:
            完整状态或查询错误信息。
        """
        scope = await self._scope_for_event(event)
        if scope is None:
            return "当前会话没有匹配的角色生活状态。"
        if self.config.get("mode", "legacy") == "narrative":
            snapshot = await self.get_snapshot(scope)
            if not snapshot.get("managed"):
                return "当前会话未启用持续叙事生活。"
            # Full diary and other days stay in administrator-only surfaces.
            return self._format_narrative_snapshot(snapshot)
        if not self._is_session_enabled(event.unified_msg_origin):
            return "当前会话未启用动态生活状态功能。"

        if self.generator.is_generating:
            return "生活状态正在生成中，请稍后再试。"

        now = self._now()
        if date:
            date = date.strip()
            try:
                datetime.date.fromisoformat(date)
            except ValueError:
                return "日期格式错误，请使用 YYYY-MM-DD 格式，例如 2026-07-01。"
            target_str = date
            data = self.data_mgr.get_by_date(target_str)
        else:
            data, target_date = self._select_current_state(now)
            if data is None:
                return "当前时间没有已生成的生活状态。"
            target_str = target_date.isoformat()

        if not data:
            return f"{target_str} 的生活状态尚未生成。"
        if data.status == "failed":
            return f"{target_str} 的生活状态生成失败。"

        return self._format_full_state(data)

    # =========================
    # State formatting
    # =========================

    @staticmethod
    def _format_match_intervals(match: SlotMatch) -> str:
        """格式化时段匹配中的所有区间。

        Args:
            match: 匹配到的时间线条目。

        Returns:
            人类可读的区间列表。
        """
        return "、".join(format_interval(interval) for interval in match.intervals)

    def _format_current_state(
        self,
        state: LifeState,
        match: SlotMatch,
        *,
        current_datetime: datetime.datetime | None = None,
        show_current: bool = True,
    ) -> str:
        """格式化当前或查询的时段状态。

        Args:
            state: 某一天的生活状态。
            match: 选中的时段。
            current_datetime: 可选的要显示的时钟时间。
            show_current: 标签是否应描述"当前"时刻。

        Returns:
            人类可读的状态文本。
        """
        time_label = "当前时段" if show_current else "时段"
        schedule_label = "当前安排" if show_current else "安排"
        outfit_label = "当前穿搭" if show_current else "穿搭"
        lines = [
            f"📅 日期：{state.date}",
            f"🎉 节日：{state.holiday}",
        ]
        if current_datetime is not None:
            datetime_label = "当前日期时间" if show_current else "日期时间"
            lines.append(f"🗓️ {datetime_label}：{format_datetime(current_datetime)}")
        lines.extend(
            [
                f"🕐 {time_label}：{match.entry.time}",
                f"⌛ 时段范围：{self._format_match_intervals(match) or '无'}",
                f"📋 {schedule_label}：{match.entry.schedule}",
                f"👗 {outfit_label}：{match.entry.outfit}",
            ]
        )
        for key, spec in OPTIONAL_TIMELINE_FIELDS.items():
            value = match.entry.extra_fields.get(key)
            if value:
                lines.append(f"{spec['icon']} {spec['label']}：{value}")
        lines.append(f"⏰ 实际生成时间：{state.generated_at or '未知'}")
        return "\n".join(lines)

    def _format_full_state(
        self,
        state: LifeState,
    ) -> str:
        """格式化某一天的完整状态。

        Args:
            state: 某一天的生活状态。

        Returns:
            人类可读的完整状态。
        """
        lines = [
            f"📅 日期：{state.date}",
            f"🎉 节日：{state.holiday}",
            f"📝 今日概况：{state.schedule_summary or '无'}",
            f"🎨 今日氛围：{state.style_summary or '无'}",
            f"⏰ 实际生成时间：{state.generated_at or '未知'}",
            "",
            "📋 完整时间线：",
        ]
        for entry in state.timeline:
            intervals = resolve_entry_intervals(entry)
            interval_text = "、".join(format_interval(item) for item in intervals)
            lines.append(
                f"  [{entry.time}] {interval_text or '无法解析'} | "
                f"{entry.schedule} | 👗 {entry.outfit}"
            )
            details = []
            for key, spec in OPTIONAL_TIMELINE_FIELDS.items():
                value = entry.extra_fields.get(key)
                if value:
                    details.append(f"{spec['icon']} {value}")
            if details:
                lines.append(f"    {' | '.join(details)}")
        return "\n".join(lines)

    # =========================
    # /dls commands
    # =========================

    def dls(self) -> None:
        """注册动态生活状态命令组。"""
        pass

    async def dls_show(
        self,
        event: AstrMessageEvent,
        time_query: str = "",
    ) -> AsyncGenerator[object, None]:
        """显示当前或指定查询时间的时段状态。

        Args:
            event: 当前 AstrBot 消息事件。
            time_query: 可选的自然时段名称或 HH:MM 格式的时间。

        Yields:
            AstrBot 纯文本命令结果。
        """
        scope = await self._scope_for_event(event)
        if scope is None:
            yield event.plain_result("当前会话没有匹配的角色生活状态。")
            return
        if self.config.get("mode", "legacy") == "narrative":
            snapshot = await self.get_snapshot(scope)
            yield event.plain_result(
                self._format_narrative_snapshot(snapshot)
                if snapshot.get("managed")
                else "当前会话未启用持续叙事生活。"
            )
            return
        time_query = time_query.strip()

        # 加载状态或调用 LLM 之前先做校验。
        if time_query:
            if time_query in NATURAL_SLOT_NAMES:
                pass
            elif ":" in time_query:
                try:
                    parse_clock_time(time_query)
                except ValueError:
                    yield event.plain_result(
                        "时间格式错误，请使用 HH:MM 格式 (00:00–23:59)。"
                    )
                    return
            else:
                allowed = "、".join(NATURAL_SLOT_NAMES)
                yield event.plain_result(
                    f"不支持的时段「{time_query}」，时段仅支持具体时间 (HH:MM) 或自然时段：{allowed}"
                )
                return

        now = self._now()

        if self.generator.is_generating:
            yield event.plain_result("状态正在生成中，请稍后再试。")
            return

        data, target_date = self._select_current_state(now)
        if data is None:
            yield event.plain_result("今天的状态尚未生成，正在生成...")
            result = await self.generator.generate(target_date)
            if not result.succeeded or result.state is None:
                if result.auto_retries_exhausted:
                    yield event.plain_result(
                        "今日自动生成次数已达上限，请使用 /群间日常 重新生成 手动重试。"
                    )
                else:
                    yield event.plain_result(
                        "状态生成失败，请稍后再试或使用 /群间日常 重新生成 重试。"
                    )
                return
            data = result.state

        if not data.timeline:
            yield event.plain_result("没有可用的时段状态。")
            return

        # 无参数：使用当前本地时间。
        if not time_query:
            match = select_current_slot(data.timeline, minute_of_day(now))
            if match is None:
                yield event.plain_result("没有可用的时段状态。")
                return
            yield event.plain_result(
                self._format_current_state(
                    data,
                    match,
                    current_datetime=now,
                )
            )
            return

        # 自然时段：按名称直接选取。
        if time_query in NATURAL_SLOT_NAMES:
            match = find_slot_by_name(data.timeline, time_query)
            if match is None:
                yield event.plain_result("没有可用的时段状态。")
                return
            yield event.plain_result(
                self._format_current_state(
                    data,
                    match,
                    show_current=False,
                )
            )
            return

        # 精确时间：已在访问状态前校验。
        query_minute = parse_clock_time(time_query)
        query_hour, query_minute_part = divmod(query_minute, 60)
        query_datetime = datetime.datetime.combine(
            target_date,
            datetime.time(query_hour, query_minute_part),
            tzinfo=CHINA_TIMEZONE,
        )
        match = select_current_slot(data.timeline, query_minute)
        if match is None:
            yield event.plain_result("没有可用的时段状态。")
            return
        yield event.plain_result(
            self._format_current_state(
                data,
                match,
                current_datetime=query_datetime,
                show_current=False,
            )
        )

    async def dls_full(
        self,
        event: AstrMessageEvent,
        date: str = "",
    ) -> AsyncGenerator[object, None]:
        """显示今天或某个归档日期的完整状态。

        Args:
            event: 当前 AstrBot 消息事件。
            date: 可选的自然日期，格式 YYYY-MM-DD。

        Yields:
            AstrBot 纯文本命令结果。
        """
        scope = await self._scope_for_event(event)
        if scope is None:
            yield event.plain_result("当前会话没有匹配的角色生活状态。")
            return
        if self.config.get("mode", "legacy") == "narrative":
            result = await self.get_narrative_admin(scope)
            if not result.get("managed"):
                yield event.plain_result("当前会话未启用持续叙事生活。")
                return
            entries = result["diary"]
            if date:
                try:
                    wanted = datetime.date.fromisoformat(date)
                except ValueError:
                    yield event.plain_result("日期格式错误，请使用 YYYY-MM-DD 格式。")
                    return
                entries = [
                    row
                    for row in entries
                    if datetime.datetime.fromtimestamp(
                        row["occurred"], CHINA_TIMEZONE
                    ).date()
                    == wanted
                ]
            diary = (
                "\n".join(
                    f"[{row['fact_kind']}] {row['text']}" for row in reversed(entries)
                )
                or "暂无已推进的生活记录。"
            )
            yield event.plain_result(
                self._format_narrative_snapshot(result["snapshot"]) + "\n\n" + diary
            )
            return
        now = self._now()

        if date:
            date = date.strip()
            try:
                datetime.date.fromisoformat(date)
            except ValueError:
                yield event.plain_result("日期格式错误，请使用 YYYY-MM-DD 格式。")
                return
            data = self.data_mgr.get_by_date(date)
            if not data:
                yield event.plain_result(f"{date} 的状态不存在。")
                return
            if data.status == "failed":
                yield event.plain_result(f"{date} 的状态生成失败，无有效状态。")
                return
            yield event.plain_result(self._format_full_state(data))
            return

        data, target_date = self._select_current_state(now)
        if data is None:
            if self.generator.is_generating:
                yield event.plain_result("状态正在生成中，请稍后再试。")
                return
            yield event.plain_result("今天的状态尚未生成，正在生成...")
            result = await self.generator.generate(target_date)
            if not result.succeeded or result.state is None:
                if result.auto_retries_exhausted:
                    yield event.plain_result(
                        "今日自动生成次数已达上限，请使用 /群间日常 重新生成 手动重试。"
                    )
                else:
                    yield event.plain_result("当前暂无有效状态。")
                return
            data = result.state

        yield event.plain_result(self._format_full_state(data))

    async def dls_regen(
        self,
        event: AstrMessageEvent,
    ) -> AsyncGenerator[object, None]:
        """强制重新生成今日状态。

        Args:
            event: 当前 AstrBot 消息事件，包含尾随的附加需求。

        Yields:
            生成进度和结果消息。
        """
        if self.config.get("mode", "legacy") == "narrative":
            yield event.plain_result(
                "持续叙事模式保留已发生的历史。请用管理面板纠正当前状态，或 /群间日常 推进 检查待处理事件。"
            )
            return
        if self.generator.is_generating:
            yield event.plain_result("已有生成任务在进行中，请稍后再试。")
            return

        # 保留命令分词之外的完整附加需求。
        extra = _extract_args_after(event.message_str, "群间日常 重新生成")

        now = self._now()
        _, target_date = self._select_current_state(now)

        if extra:
            yield event.plain_result(f"正在根据附加要求重新生成今日状态：{extra}")
        else:
            yield event.plain_result("正在强制重新生成今日状态...")

        result = await self.generator.generate(
            target_date,
            force=True,
            extra=extra,
        )

        if not result.succeeded or result.state is None:
            if result.used_previous_state and result.state is not None:
                yield event.plain_result(
                    "重新生成失败，已保留原状态。\n\n"
                    f"{self._format_full_state(result.state)}"
                )
            else:
                yield event.plain_result("状态生成失败，请稍后再试。")
            return

        yield event.plain_result(
            f"全局生活状态重新生成完成。\n\n{self._format_full_state(result.state)}"
        )

    async def dls_tick(self, event: AstrMessageEvent) -> AsyncGenerator[object, None]:
        """Run a bounded check; never replay old hours or send a contact intent."""
        result = await self.narrative.tick()
        yield event.plain_result("叙事检查：" + str(result["status"]))

    async def dls_pause(self, event: AstrMessageEvent) -> AsyncGenerator[object, None]:
        """Pause persistent life progression."""
        await self.set_paused(True)
        yield event.plain_result("持续叙事已暂停。")

    async def dls_resume(self, event: AstrMessageEvent) -> AsyncGenerator[object, None]:
        """Resume future bounded life checks."""
        await self.set_paused(False)
        yield event.plain_result("持续叙事已恢复。")

    @staticmethod
    def _format_narrative_snapshot(snapshot: dict) -> str:
        """Format only public life state and commitments belonging to this UMO."""
        lines = [
            "角色当前处境（生活为角色世界内的虚构经历）：",
            "活动：" + str(snapshot.get("activity", "未知")),
            "可交互状态：" + str(snapshot.get("availability", "unknown")),
        ]
        if snapshot.get("subjective_state"):
            lines.append("主观状态：" + snapshot["subjective_state"])
        if snapshot.get("summary"):
            lines.append("近期摘要：" + snapshot["summary"])
        for item in snapshot.get("commitments", []):
            lines.append(
                "当前会话约定（" + item["status"] + "）：" + item["description"]
            )
        lines.append("状态修订：" + str(snapshot.get("revision", 0)))
        return "\n".join(lines)
