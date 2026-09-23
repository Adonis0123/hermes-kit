"""Register the owner-only verified macOS lock-screen tool."""

from __future__ import annotations

import asyncio
import json
import logging
import platform
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

from .lock_screen import (
    COMMAND_TRIGGER,
    SHORTCUT_LIST_ARGV,
    SHORTCUT_NAME,
    SessionOrigin,
    _runtime_settings,
    authorize,
    handle_lock_command,
    handle_lock_screen,
)

logger = logging.getLogger(__name__)
_PENDING_REPLIES: set[asyncio.Task] = set()

LOCK_SCREEN_SCHEMA = {
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": False,
}


def _check_available() -> bool:
    if platform.system() != "Darwin":
        return False
    if not Path(SHORTCUT_LIST_ARGV[0]).exists():
        return False
    try:
        completed = subprocess.run(
            SHORTCUT_LIST_ARGV,
            shell=False,
            timeout=5,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if completed.returncode != 0:
        return False
    return SHORTCUT_NAME in {
        line.strip() for line in completed.stdout.splitlines() if line.strip()
    }


def _handle(
    args: Mapping[str, Any],
    *,
    session_id: str = "",
    user_task: str = "",
    **_: Any,
) -> str:
    return handle_lock_screen(
        args,
        session_id=session_id,
        user_task=user_task,
    )


def _format_command_result(raw_result: str) -> str:
    try:
        result = json.loads(raw_result)
    except (TypeError, ValueError, json.JSONDecodeError):
        return "❌ 锁屏失败；请确认 Shortcut 与 Hermes 配置。"
    if not isinstance(result, dict):
        return "❌ 锁屏失败；请确认 Shortcut 与 Hermes 配置。"

    outcome = result.get("outcome")
    reason = result.get("reason")
    if outcome == "locked" and result.get("verified") is True:
        return "🔒 已锁屏。"
    if outcome == "invoked_unverified":
        return "🔒 已执行锁屏。"
    if reason == "arguments_not_allowed":
        return "用法：单独发送 /lock，不要附加其他文字。"
    if reason == "duplicate_request":
        return "ℹ️ 这条锁屏请求已处理，不会重复执行。"
    if reason in {
        "command_context_missing",
        "configuration_invalid",
        "source_not_allowed",
        "chat_type_not_allowed",
        "chat_not_allowed",
        "user_not_allowed",
    }:
        return "⛔ /lock 只允许主人在批准的 Feishu 私聊中使用。"
    return "❌ 锁屏失败；请确认 Shortcut 与 Hermes 配置。"


def _handle_command(raw_args: str, command_context: Any = None) -> str:
    return _format_command_result(handle_lock_command(raw_args, command_context))


def _source_value(source: Any, name: str) -> str:
    value = getattr(source, name, "") or ""
    return str(getattr(value, "value", value) or "")


def _dispatch_context(event: Any, gateway: Any) -> SimpleNamespace:
    """The trusted command context, built from the inbound event the gateway already parsed."""
    source = event.source
    session_key = ""
    with_key = getattr(gateway, "_session_key_for_source", None)
    if callable(with_key):
        try:
            session_key = str(with_key(source) or "")
        except Exception:
            logger.debug("lock-screen: session key lookup failed", exc_info=True)
    return SimpleNamespace(
        session_key=session_key,
        message_id=str(getattr(event, "message_id", "") or _source_value(source, "message_id")),
        platform=_source_value(source, "platform"),
        chat_type=_source_value(source, "chat_type"),
        chat_id=_source_value(source, "chat_id"),
        user_id=_source_value(source, "user_id"),
        user_id_alt=_source_value(source, "user_id_alt"),
    )


async def _reply_to_lock(event: Any, gateway: Any, raw_args: str, context: SimpleNamespace) -> None:
    reply = await asyncio.to_thread(_handle_command, raw_args, context)
    adapter = gateway._delivery_adapter_for(event.source)
    if adapter is None:
        logger.warning("lock-screen: no adapter to answer /lock on %s", context.platform)
        return
    await adapter.send(context.chat_id, reply, reply_to=context.message_id or None)


def _pre_gateway_dispatch(event: Any = None, gateway: Any = None, **_: Any) -> dict | None:
    """Answer the owner's ``/lock`` before dispatch.

    Upstream plugin commands receive only the raw args, and the owner check needs the
    sender, so ``/lock`` is taken here where the whole event is visible. Anyone else
    falls through to normal dispatch (gateway auth, then the fail-closed command).
    """
    text = str(getattr(event, "text", "") or "").strip()
    head, _, raw_args = text.partition(" ")
    if head.lower() != COMMAND_TRIGGER or gateway is None or getattr(event, "source", None) is None:
        return None
    context = _dispatch_context(event, gateway)
    origin = SessionOrigin(
        source=context.platform, chat_type=context.chat_type, chat_id=context.chat_id,
        user_id=context.user_id, user_id_alt=context.user_id_alt or None,
    )
    if not authorize(_runtime_settings(), origin, COMMAND_TRIGGER).allowed:
        return None
    task = asyncio.get_running_loop().create_task(_reply_to_lock(event, gateway, raw_args, context))
    _PENDING_REPLIES.add(task)
    task.add_done_callback(_PENDING_REPLIES.discard)
    return {"action": "skip", "reason": "hermes-lock-screen handled /lock"}


def register(ctx: Any) -> None:
    ctx.register_tool(
        name="lock_screen",
        toolset="lock_screen",
        schema=LOCK_SCREEN_SCHEMA,
        handler=_handle,
        check_fn=_check_available,
        description=(
            "Lock this Mac when the current owner is asking you to lock it now, "
            "including free-form requests such as '帮我锁屏', '把电脑锁好', or "
            "'我要出门了，帮我锁一下'. Polite requests phrased as questions, "
            "such as '能帮我锁一下屏吗', still count as immediate requests. The "
            "model decides the user's intent; do not call for pure capability "
            "questions, discussion, negation, or hypothetical future requests. "
            "Takes no arguments. The deterministic /lock command is the preferred "
            "remote entrypoint. For this natural-language compatibility entrypoint, "
            "report the returned execution state exactly: locked + verified=true -> "
            "'🔒 已锁屏。'; invoked_unverified -> '🔒 已执行锁屏。'; failed -> "
            "state the failure. Never report failure after a locked or "
            "invoked_unverified result."
        ),
        emoji="🔒",
    )
    ctx.register_command(
        name="lock",
        handler=_handle_command,
        description="主人专用：立即锁定这台 Mac",
        args_hint="",
    )
    ctx.register_hook("pre_gateway_dispatch", _pre_gateway_dispatch)
