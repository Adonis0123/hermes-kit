"""Policy primitives for the owner-only remote lock-screen tool."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import plistlib
import sqlite3
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

PLUGIN_NAME = "hermes-lock-screen"
COMMAND_TRIGGER = "/lock"
MODEL_TRIGGER = "model_intent"
SHORTCUT_NAME = "Hermes Lock Screen"
SHORTCUT_LIST_ARGV = ["/usr/bin/shortcuts", "list"]
SHORTCUT_ARGV = ["/usr/bin/shortcuts", "run", SHORTCUT_NAME]
IOREG_ARGV = [
    "/usr/sbin/ioreg",
    "-r",
    "-d",
    "1",
    "-c",
    "IOConsoleUsers",
    "-a",
]
Runner = Callable[..., subprocess.CompletedProcess[Any]]


@dataclass(frozen=True)
class PluginSettings:
    owner_user_ids: frozenset[str]
    owner_dm_chat_ids: frozenset[str]


@dataclass(frozen=True)
class SessionOrigin:
    source: str
    chat_type: str
    chat_id: str
    user_id: str
    user_id_alt: str | None


@dataclass(frozen=True)
class LockRequest:
    session_id: str
    message_id: int | str
    origin: SessionOrigin
    trigger: str


@dataclass(frozen=True)
class Authorization:
    allowed: bool
    reason: str


def _string_set(value: Any) -> frozenset[str]:
    if not isinstance(value, list):
        return frozenset()
    return frozenset(item for item in value if isinstance(item, str) and item)


def load_settings(config: Mapping[str, Any]) -> PluginSettings:
    plugins = config.get("plugins", {})
    entries = plugins.get("entries", {}) if isinstance(plugins, Mapping) else {}
    raw = entries.get(PLUGIN_NAME, {}) if isinstance(entries, Mapping) else {}
    if not isinstance(raw, Mapping):
        raw = {}
    return PluginSettings(
        owner_user_ids=_string_set(raw.get("owner_user_ids")),
        owner_dm_chat_ids=_string_set(raw.get("owner_dm_chat_ids")),
    )


def load_session_origin(home: Path, session_id: str) -> SessionOrigin | None:
    database = Path(home) / "state.db"
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        row = connection.execute(
            """
            SELECT source, chat_type, chat_id, user_id, origin_json
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        connection.close()
    if row is None:
        return None

    source, chat_type, chat_id, user_id, raw_origin = row
    user_id_alt: str | None = None
    if isinstance(raw_origin, str):
        try:
            origin = json.loads(raw_origin)
        except (TypeError, ValueError, json.JSONDecodeError):
            origin = {}
        if isinstance(origin, dict) and isinstance(origin.get("user_id_alt"), str):
            user_id_alt = origin["user_id_alt"]

    return SessionOrigin(
        source=str(source or ""),
        chat_type=str(chat_type or ""),
        chat_id=str(chat_id or ""),
        user_id=str(user_id or ""),
        user_id_alt=user_id_alt,
    )


def authorize(
    settings: PluginSettings, origin: SessionOrigin, user_task: str
) -> Authorization:
    if not settings.owner_user_ids or not settings.owner_dm_chat_ids:
        return Authorization(False, "configuration_invalid")
    if origin.source != "feishu":
        return Authorization(False, "source_not_allowed")
    if origin.chat_type != "dm":
        return Authorization(False, "chat_type_not_allowed")
    if origin.chat_id not in settings.owner_dm_chat_ids:
        return Authorization(False, "chat_not_allowed")
    identities = {origin.user_id}
    if origin.user_id_alt:
        identities.add(origin.user_id_alt)
    if not identities.intersection(settings.owner_user_ids):
        return Authorization(False, "user_not_allowed")
    if user_task not in {COMMAND_TRIGGER, MODEL_TRIGGER}:
        return Authorization(False, "trigger_not_allowed")
    return Authorization(True, "authorized")


def _default_home() -> Path:
    configured = os.environ.get("HERMES_HOME")
    return Path(configured).expanduser() if configured else Path.home() / ".hermes"


def _runtime_settings() -> PluginSettings:
    config_module = importlib.import_module("hermes_cli.config")
    return load_settings(config_module.load_config() or {})


def _latest_user_message(home: Path, session_id: str) -> tuple[int, str] | None:
    database = home / "state.db"
    try:
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        row = connection.execute(
            """
            SELECT id, content
            FROM messages
            WHERE session_id = ? AND role = 'user'
            ORDER BY id DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        connection.close()
    if row is None or not isinstance(row[0], int):
        return None
    return row[0], str(row[1] or "")


def _reserve_request(home: Path, session_id: str, message_id: int | str) -> bool:
    state_dir = home / "state"
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state_dir, 0o700)
    database = state_dir / "lock-screen.db"
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(database)
        os.chmod(database, 0o600)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS requests (
                session_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (session_id, message_id)
            )
            """
        )
        connection.execute(
            "INSERT INTO requests (session_id, message_id, created_at) VALUES (?, ?, ?)",
            (session_id, message_id, time.time()),
        )
        connection.commit()
    except sqlite3.IntegrityError:
        return False
    finally:
        if connection is not None:
            connection.close()
    return True


def _hash_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _append_audit(
    home: Path,
    *,
    session_id: str,
    origin: SessionOrigin | None,
    message_id: int | str | None,
    authorized: bool,
    outcome: str,
    reason: str,
) -> None:
    logs_dir = home / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    audit_path = logs_dir / "lock-screen-audit.jsonl"
    record = {
        "timestamp": time.time(),
        "session_hash": _hash_identifier(session_id),
        "chat_hash": _hash_identifier(origin.chat_id if origin else ""),
        "user_hash": _hash_identifier(origin.user_id if origin else ""),
        "message_hash": _hash_identifier(str(message_id or "")),
        "authorized": authorized,
        "outcome": outcome,
        "reason": reason,
    }
    payload = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")
    descriptor = os.open(
        audit_path,
        os.O_WRONLY | os.O_CREAT | os.O_APPEND,
        0o600,
    )
    try:
        os.write(descriptor, payload)
    finally:
        os.close(descriptor)
    os.chmod(audit_path, 0o600)


def _response(outcome: str, reason: str, *, verified: bool = False) -> str:
    return json.dumps(
        {
            "success": outcome in {"locked", "invoked_unverified"},
            "outcome": outcome,
            "reason": reason,
            "verified": verified,
        },
        ensure_ascii=False,
    )


def _completed_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value or "")


def _contains_locked_state(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("CGSSessionScreenIsLocked") is True:
            return True
        return any(_contains_locked_state(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_locked_state(item) for item in value)
    return False


def _probe_locked(runner: Runner) -> bool:
    try:
        completed = runner(
            IOREG_ARGV,
            shell=False,
            timeout=2,
            capture_output=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if completed.returncode != 0:
        return False
    output = completed.stdout
    if isinstance(output, str):
        output = output.encode("utf-8")
    if not isinstance(output, bytes):
        return False
    try:
        payload = plistlib.loads(output)
    except (ValueError, TypeError, plistlib.InvalidFileException):
        return False
    return _contains_locked_state(payload)


def _finish(
    home: Path,
    *,
    session_id: str,
    origin: SessionOrigin | None,
    message_id: int | str | None,
    outcome: str,
    reason: str,
    authorized: bool = False,
    verified: bool = False,
) -> str:
    try:
        _append_audit(
            home,
            session_id=session_id,
            origin=origin,
            message_id=message_id,
            authorized=authorized,
            outcome=outcome,
            reason=reason,
        )
    except OSError:
        return _response("failed", "audit_unavailable")
    return _response(outcome, reason, verified=verified)


def _execute_lock_request(
    request: LockRequest,
    *,
    home: Path,
    settings: PluginSettings,
    runner: Runner,
    sleeper: Callable[[float], None],
) -> str:
    """Authorize and execute one lock request from either public adapter."""

    def finish(
        outcome: str,
        reason: str,
        *,
        authorized: bool = False,
        verified: bool = False,
    ) -> str:
        return _finish(
            home,
            session_id=request.session_id,
            origin=request.origin,
            message_id=request.message_id,
            authorized=authorized,
            outcome=outcome,
            reason=reason,
            verified=verified,
        )

    decision = authorize(settings, request.origin, request.trigger)
    if not decision.allowed:
        return finish("failed", decision.reason)
    try:
        _append_audit(
            home,
            session_id=request.session_id,
            origin=request.origin,
            message_id=request.message_id,
            authorized=True,
            outcome="accepted",
            reason="authorization_passed",
        )
    except OSError:
        return _response("failed", "audit_unavailable")
    if not _reserve_request(home, request.session_id, request.message_id):
        return finish("failed", "duplicate_request", authorized=True)

    try:
        listed = runner(
            SHORTCUT_LIST_ARGV,
            shell=False,
            timeout=5,
            capture_output=True,
        )
    except (OSError, subprocess.SubprocessError):
        return finish("failed", "shortcut_list_failed", authorized=True)
    shortcut_names = {
        line.strip()
        for line in _completed_text(listed.stdout).splitlines()
        if line.strip()
    }
    if listed.returncode != 0 or SHORTCUT_NAME not in shortcut_names:
        return finish("failed", "shortcut_missing", authorized=True)

    try:
        completed = runner(
            SHORTCUT_ARGV,
            shell=False,
            timeout=10,
            capture_output=True,
        )
    except subprocess.TimeoutExpired:
        return finish("failed", "shortcut_timeout", authorized=True)
    except (OSError, subprocess.SubprocessError):
        return finish("failed", "shortcut_execution_failed", authorized=True)
    if completed.returncode != 0:
        return finish("failed", "shortcut_exit_nonzero", authorized=True)

    for attempt in range(5):
        if _probe_locked(runner):
            return finish(
                "locked",
                "screen_lock_verified",
                authorized=True,
                verified=True,
            )
        if attempt < 4:
            sleeper(1.0)
    return finish(
        "invoked_unverified",
        "lock_state_not_verified",
        authorized=True,
    )


def handle_lock_screen(
    args: Mapping[str, Any],
    *,
    session_id: str,
    user_task: str,
    home: Path | None = None,
    settings: PluginSettings | None = None,
    runner: Runner = subprocess.run,
    sleeper: Callable[[float], None] = time.sleep,
) -> str:
    """Adapt one AI-selected tool call into the shared lock request pipeline.

    ``user_task`` is retained for the Hermes tool ABI but is not an
    authorization input: the host currently omits it on normal tool calls and
    documents it as the original task rather than the current message.  The
    model's decision to select this no-argument tool supplies intent; this
    adapter still enforces the trusted session origin and replay boundary.
    """
    runtime_home = Path(home) if home is not None else _default_home()
    origin = load_session_origin(runtime_home, session_id)
    latest = _latest_user_message(runtime_home, session_id)
    message_id = latest[0] if latest else None

    if args:
        return _finish(
            runtime_home,
            session_id=session_id,
            origin=origin,
            message_id=message_id,
            outcome="failed",
            reason="arguments_not_allowed",
        )
    if origin is None:
        return _finish(
            runtime_home,
            session_id=session_id,
            origin=None,
            message_id=message_id,
            outcome="failed",
            reason="session_not_found",
        )

    runtime_settings = settings if settings is not None else _runtime_settings()
    decision = authorize(runtime_settings, origin, MODEL_TRIGGER)
    if not decision.allowed:
        return _finish(
            runtime_home,
            session_id=session_id,
            origin=origin,
            message_id=message_id,
            outcome="failed",
            reason=decision.reason,
        )
    if latest is None:
        return _finish(
            runtime_home,
            session_id=session_id,
            origin=origin,
            message_id=None,
            authorized=True,
            outcome="failed",
            reason="message_not_found",
        )
    return _execute_lock_request(
        LockRequest(
            session_id=session_id,
            message_id=latest[0],
            origin=origin,
            trigger=MODEL_TRIGGER,
        ),
        home=runtime_home,
        settings=runtime_settings,
        runner=runner,
        sleeper=sleeper,
    )


def handle_lock_command(
    raw_args: str,
    command_context: Any,
    *,
    home: Path | None = None,
    settings: PluginSettings | None = None,
    runner: Runner = subprocess.run,
    sleeper: Callable[[float], None] = time.sleep,
) -> str:
    """Adapt a trusted Gateway ``/lock`` invocation into a lock request."""
    runtime_home = Path(home) if home is not None else _default_home()
    if command_context is None or not hasattr(command_context, "session_key"):
        return _finish(
            runtime_home,
            session_id="",
            origin=None,
            message_id=None,
            outcome="failed",
            reason="command_context_missing",
        )

    session_id = str(getattr(command_context, "session_key", "") or "")
    message_id = str(getattr(command_context, "message_id", "") or "")
    origin = SessionOrigin(
        source=str(getattr(command_context, "platform", "") or ""),
        chat_type=str(getattr(command_context, "chat_type", "") or ""),
        chat_id=str(getattr(command_context, "chat_id", "") or ""),
        user_id=str(getattr(command_context, "user_id", "") or ""),
        user_id_alt=str(getattr(command_context, "user_id_alt", "") or "") or None,
    )
    if raw_args.strip():
        return _finish(
            runtime_home,
            session_id=session_id,
            origin=origin,
            message_id=message_id or None,
            outcome="failed",
            reason="arguments_not_allowed",
        )

    runtime_settings = settings if settings is not None else _runtime_settings()
    decision = authorize(runtime_settings, origin, COMMAND_TRIGGER)
    if not decision.allowed:
        return _finish(
            runtime_home,
            session_id=session_id,
            origin=origin,
            message_id=message_id or None,
            outcome="failed",
            reason=decision.reason,
        )
    if not session_id:
        return _finish(
            runtime_home,
            session_id="",
            origin=origin,
            message_id=message_id or None,
            authorized=True,
            outcome="failed",
            reason="command_context_missing",
        )
    if not message_id:
        return _finish(
            runtime_home,
            session_id=session_id,
            origin=origin,
            message_id=None,
            authorized=True,
            outcome="failed",
            reason="message_not_found",
        )

    return _execute_lock_request(
        LockRequest(
            session_id=session_id,
            message_id=message_id,
            origin=origin,
            trigger=COMMAND_TRIGGER,
        ),
        home=runtime_home,
        settings=runtime_settings,
        runner=runner,
        sleeper=sleeper,
    )
