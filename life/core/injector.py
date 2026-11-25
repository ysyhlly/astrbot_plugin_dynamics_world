import datetime
import uuid

from .state import (
    OPTIONAL_TIMELINE_FIELDS,
    LifeState,
    SlotMatch,
    format_datetime,
    format_interval,
)

# Fake tool-call constants
FAKE_TOOL_CALL_NAME = "get_current_life_state"
FAKE_TOOL_CALL_ID_PREFIX = "fake_dynamic_life_state_"

AUTO_LIFE_GUIDANCE = (
    "忙闲与时效只用于把握回应长短和时机。直接回应当前话题。"
    "当前生活细节按需读取：对方询问角色此刻在做什么、在哪、眼前场景、天气或项目进展时，"
    "用 get_dynamics_world_state 查询对应内容；寒暄、闲聊、单独的戳一戳无需查询。"
)

LIFE_REPLY_GUIDANCE = (
    "生活状态是语气、回复长短和忙闲的背景。直接接当前话题，不用吃饭、起床、休息、走动等日常动作给无关聊天开场，也不拿它们硬作比喻。"
    "只有对方问起、确实有约好要反馈的进展、当前状态实际限制回应，或该细节能推进当前话题时，才简短提及有依据的状态。"
    "被问到正在做什么时只答当前确认的状态，不从喜好、物品或计划补写同时进行的动作。"
)


# =========================
# Injection text
# =========================


def build_injection_text(
    state: LifeState,
    current_match: SlotMatch | None,
    now: datetime.datetime,
) -> str:
    """构建临时的 ``<life_state>`` 上下文块。

    Args:
        state: 当前自然日期的生活状态。
        current_match: 匹配当前本地时间的时间线条目。
        now: 当前配置时区的本地时间。

    Returns:
        要注入到 LLM 请求中的文本。
    """
    slot_label = "无"
    schedule_label = "无"
    outfit_label = "无"
    interval_label = "无"
    optional_labels: list[str] = []
    if current_match:
        slot_label = current_match.entry.time
        schedule_label = current_match.entry.schedule
        outfit_label = current_match.entry.outfit
        for key, spec in OPTIONAL_TIMELINE_FIELDS.items():
            value = current_match.entry.extra_fields.get(key)
            if value:
                optional_labels.append(f"当前{spec['label']}: {value}\n")
        if current_match.active_interval:
            interval_label = format_interval(current_match.active_interval)

    return (
        f"<life_state>\n"
        f"{LIFE_REPLY_GUIDANCE}\n"
        f"日期: {state.date}\n"
        f"今日节日: {state.holiday or '无'}\n"
        f"当前日期时间: {format_datetime(now)}\n"
        f"今日概况: {state.schedule_summary or '无'}\n"
        f"今日氛围: {state.style_summary or '无'}\n"
        f"当前时段: {slot_label}\n"
        f"当前时段范围: {interval_label}\n"
        f"当前安排: {schedule_label}\n"
        f"当前穿搭: {outfit_label}\n"
        f"{''.join(optional_labels)}"
        f"</life_state>"
    )


# =========================
# Fake tool-call messages
# =========================


def build_fake_tool_call(inject_text: str) -> list[dict]:
    """Wrap the same context used by the text-parts injection mode."""
    call_id = f"{FAKE_TOOL_CALL_ID_PREFIX}{uuid.uuid4().hex[:12]}"

    assistant_msg = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {
                    "name": FAKE_TOOL_CALL_NAME,
                    "arguments": "{}",
                },
            }
        ],
    }

    tool_msg = {
        "role": "tool",
        "tool_call_id": call_id,
        "name": FAKE_TOOL_CALL_NAME,
        "content": inject_text,
    }

    return [assistant_msg, tool_msg]


# =========================
# Context cleanup
# =========================


def remove_fake_tool_call_from_context(contexts: list[dict]) -> None:
    """从请求上下文中移除上一次的伪生活状态工具调用。

    Args:
        contexts: 可变的 provider 上下文消息列表。
    """
    if not contexts:
        return

    indices_to_remove: set[int] = set()
    fake_call_ids: set[str] = set()

    for i, msg in enumerate(contexts):
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        if role == "assistant" and msg.get("tool_calls"):
            for tc in msg["tool_calls"]:
                tc_id = tc.get("id", "") if isinstance(tc, dict) else ""
                if tc_id.startswith(FAKE_TOOL_CALL_ID_PREFIX):
                    fake_call_ids.add(tc_id)
                    indices_to_remove.add(i)
        elif role == "tool":
            tc_id = msg.get("tool_call_id", "")
            if tc_id in fake_call_ids:
                indices_to_remove.add(i)

    for i in sorted(indices_to_remove, reverse=True):
        contexts.pop(i)
