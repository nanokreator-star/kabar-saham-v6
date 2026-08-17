"""
Kabar Saham V6.6.2.1 — Command Bridge Hotfix
==============================================

Purpose
-------
Add cloud Telegram commands on top of the existing V6.0 auto-alert system.

Architecture:
cron-job.org -> GitHub workflow_dispatch -> lightweight Telegram probe
-> install full dependencies ONLY if commands exist -> V5.4 intelligence core
-> Telegram response.

Security:
- Only chat IDs in TELEGRAM_CHAT_IDS are allowed.
- Bot token / chat IDs are never written to repository state.
- Pending Telegram updates are stored only in GitHub runner temp storage.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
STATE_PATH = Path(
    os.getenv(
        "V61_COMMAND_STATE_PATH",
        str(ROOT / "state" / "command_state.json"),
    )
)
PENDING_PATH = Path(
    os.getenv(
        "V61_PENDING_COMMANDS_PATH",
        str(ROOT / "pending_commands_v61.json"),
    )
)
SCANNER_STATE_PATH = Path(
    os.getenv(
        "V6_STATE_PATH",
        str(ROOT / "state" / "github_state.json"),
    )
)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
RAW_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS", "").strip()

MAX_UPDATES = max(
    1,
    min(
        100,
        int(os.getenv("V61_COMMAND_MAX_UPDATES", "20")),
    ),
)

TG_API_TIMEOUT_SECONDS = int(
    os.getenv("V61_TELEGRAM_TIMEOUT_SECONDS", "20")
)


# V6.6.1 — Native Telegram Command Menu.
NATIVE_TELEGRAM_MENU_ENABLED = (
    os.getenv("V661_NATIVE_TELEGRAM_MENU_ENABLED", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)
NATIVE_MENU_SET_PRIVATE_SCOPE = (
    os.getenv("V661_NATIVE_MENU_PRIVATE_SCOPE", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)

TELEGRAM_NATIVE_COMMANDS = [
    {
        "command": "menu",
        "description": "Buka Kabar Saham Control Center",
    },
    {
        "command": "health",
        "description": "Cek kesehatan scanner dan Command Bridge",
    },
    {
        "command": "today",
        "description": "Milestone corporate action hari ini",
    },
    {
        "command": "recent",
        "description": "Perubahan lifecycle terbaru",
    },
    {
        "command": "watchboard",
        "description": "Dashboard semua Smart Watch",
    },
    {
        "command": "watchlist",
        "description": "Daftar ticker yang sedang dipantau",
    },
    {
        "command": "watch",
        "description": "Tambah atau ubah ticker Smart Watch",
    },
    {
        "command": "unwatch",
        "description": "Hapus ticker dari Smart Watch",
    },
    {
        "command": "analyze",
        "description": "Analisis corporate action satu ticker",
    },
    {
        "command": "timeline",
        "description": "Lifecycle dan riwayat satu ticker",
    },
    {
        "command": "official",
        "description": "Cek sumber resmi corporate action",
    },
    {
        "command": "decision",
        "description": "Tampilkan Decision Board",
    },
    {
        "command": "news24h",
        "description": "Berita corporate action 24 jam terakhir",
    },
    {
        "command": "latest",
        "description": "Corporate action terbaru",
    },
    {
        "command": "high",
        "description": "Filter event dengan urgency HIGH",
    },
    {
        "command": "active",
        "description": "Filter corporate action aktif",
    },
    {
        "command": "ma",
        "description": "Filter M&A dan takeover",
    },
    {
        "command": "ipo",
        "description": "Filter event IPO",
    },
    {
        "command": "rights",
        "description": "Filter Rights Issue atau HMETD",
    },
    {
        "command": "market",
        "description": "Cek harga pasar satu ticker",
    },
    {
        "command": "cloudstatus",
        "description": "Lihat status semua fitur cloud",
    },
    {
        "command": "help",
        "description": "Bantuan dan semua command",
    },
]

BRIDGE_HTTP_RETRY_ATTEMPTS = max(
    1,
    min(5, int(os.getenv("V624_BRIDGE_HTTP_RETRY_ATTEMPTS", "3"))),
)
BRIDGE_HTTP_RETRY_BASE_SECONDS = max(
    0.25,
    min(5.0, float(os.getenv("V624_BRIDGE_HTTP_RETRY_BASE_SECONDS", "1.0"))),
)

SCHEMA_VERSION = 12

# V6.1.1 anti-repeat protection.
COMMAND_DEDUP_SECONDS = max(
    0,
    int(os.getenv("V611_COMMAND_DEDUP_SECONDS", "180")),
)
RECENT_COMMAND_TTL_SECONDS = max(
    3600,
    int(os.getenv("V611_RECENT_COMMAND_TTL_SECONDS", "86400")),
)

# V6.1.1 compact Decision Board.
DECISION_MAX_EVENTS = max(
    1,
    min(8, int(os.getenv("V611_DECISION_MAX_EVENTS", "5"))),
)
DECISION_SCAN_LIMIT = max(
    DECISION_MAX_EVENTS,
    min(50, int(os.getenv("V611_DECISION_SCAN_LIMIT", "30"))),
)

# V6.1.2 Fast & Clean Decision Board.
DECISION_FAST_MODE = (
    os.getenv("V612_DECISION_FAST_MODE", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)
TITLE_TICKER_INFERENCE = (
    os.getenv("V612_TITLE_TICKER_INFERENCE", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)

# V6.6.1 lifecycle memory.
LIFECYCLE_HISTORY_MAX = max(
    3,
    min(30, int(os.getenv("V63_LIFECYCLE_HISTORY_MAX", "12"))),
)
LIFECYCLE_TIMELINE_MAX_DISPLAY = max(
    2,
    min(10, int(os.getenv("V63_TIMELINE_MAX_DISPLAY", "6"))),
)


# V6.6.1 — timeline noise guard + local display time.
TIMELINE_NOISE_GUARD_ENABLED = (
    os.getenv("V631_TIMELINE_NOISE_GUARD_ENABLED", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)
TIMELINE_TIMEZONE_NAME = (
    os.getenv("V631_TIMELINE_TIMEZONE", "Asia/Jakarta").strip()
    or "Asia/Jakarta"
)

try:
    TIMELINE_TZ = ZoneInfo(TIMELINE_TIMEZONE_NAME)
except Exception:
    TIMELINE_TIMEZONE_NAME = "Asia/Jakarta"
    TIMELINE_TZ = timezone(timedelta(hours=7))

INDONESIAN_MONTHS = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "Mei",
    6: "Jun",
    7: "Jul",
    8: "Agu",
    9: "Sep",
    10: "Okt",
    11: "Nov",
    12: "Des",
}


# V6.6.1 Smart Watchlist.
SMART_WATCHLIST_ENABLED = (
    os.getenv("V64_SMART_WATCHLIST_ENABLED", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)
WATCHLIST_MAX_TICKERS = max(
    1,
    min(50, int(os.getenv("V64_WATCHLIST_MAX_TICKERS", "20"))),
)

# V6.6.1 — Smart Watch Dashboard.
SMART_WATCH_DASHBOARD_ENABLED = (
    os.getenv("V65_SMART_WATCH_DASHBOARD_ENABLED", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)
WATCHBOARD_ITEMS_PER_MESSAGE = max(
    2,
    min(8, int(os.getenv("V65_WATCHBOARD_ITEMS_PER_MESSAGE", "5"))),
)
WATCHBOARD_DUE_DAYS = max(
    1,
    min(30, int(os.getenv("V65_WATCHBOARD_DUE_DAYS", "7"))),
)

# V6.6.1 — Control Center + GitHub Actions Health Monitor.
CONTROL_CENTER_ENABLED = (
    os.getenv("V66_CONTROL_CENTER_ENABLED", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)
HEALTH_GITHUB_API_ENABLED = (
    os.getenv("V66_HEALTH_GITHUB_API_ENABLED", "1").strip().lower()
    not in {"0", "false", "off", "no"}
)
HEALTH_SCAN_STALE_MINUTES = max(
    10,
    min(240, int(os.getenv("V66_HEALTH_SCAN_STALE_MINUTES", "30"))),
)
HEALTH_BRIDGE_STALE_MINUTES = max(
    5,
    min(120, int(os.getenv("V66_HEALTH_BRIDGE_STALE_MINUTES", "12"))),
)
HEALTH_RUN_LOOKBACK = max(
    5,
    min(30, int(os.getenv("V66_HEALTH_RUN_LOOKBACK", "15"))),
)
RECENT_MAX_ITEMS = max(
    3,
    min(12, int(os.getenv("V66_RECENT_MAX_ITEMS", "8"))),
)
TODAY_MAX_ITEMS = max(
    3,
    min(12, int(os.getenv("V66_TODAY_MAX_ITEMS", "8"))),
)

GITHUB_REPOSITORY_NAME = os.getenv(
    "GITHUB_REPOSITORY",
    "",
).strip()
AUTO_ALERT_WORKFLOW_FILE = os.getenv(
    "V66_AUTO_ALERT_WORKFLOW_FILE",
    "kabar_saham_v6.yml",
).strip()
COMMAND_BRIDGE_WORKFLOW_FILE = os.getenv(
    "V66_COMMAND_BRIDGE_WORKFLOW_FILE",
    "command_bridge_v6_1.yml",
).strip()

WATCHBOARD_MONTH_MAP = {
    "jan": 1, "januari": 1, "january": 1,
    "feb": 2, "februari": 2, "february": 2,
    "mar": 3, "maret": 3, "march": 3,
    "apr": 4, "april": 4,
    "mei": 5, "may": 5,
    "jun": 6, "juni": 6, "june": 6,
    "jul": 7, "juli": 7, "july": 7,
    "agu": 8, "agustus": 8, "aug": 8, "august": 8,
    "sep": 9, "september": 9,
    "okt": 10, "oktober": 10, "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "des": 12, "desember": 12, "dec": 12, "december": 12,
}
WATCH_PRIORITIES = {"HIGH", "WATCH", "NORMAL"}
WATCH_PRIORITY_RANK = {"HIGH": 3, "WATCH": 2, "NORMAL": 1}


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()



def _parse_iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        dt = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except Exception:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def format_timeline_local_time(value: Any) -> str:
    dt = _parse_iso_datetime(value)

    if not dt:
        return "-"

    local = dt.astimezone(TIMELINE_TZ)
    month = INDONESIAN_MONTHS.get(
        local.month,
        f"{local.month:02d}",
    )
    suffix = (
        "WIB"
        if TIMELINE_TIMEZONE_NAME == "Asia/Jakarta"
        else TIMELINE_TIMEZONE_NAME
    )

    return (
        f"{local.day:02d} {month} {local.year} "
        f"{local.hour:02d}:{local.minute:02d} {suffix}"
    )


def _same_lifecycle_stage(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    return (
        str(left.get("stage") or "").upper()
        == str(right.get("stage") or "").upper()
        and str(left.get("family") or "").upper()
        == str(right.get("family") or "").upper()
    )


def _merge_stage_snapshot(
    previous: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(previous)

    first_seen = (
        previous.get("stage_started_utc")
        or previous.get("observed_utc")
        or current.get("observed_utc")
    )

    for key, value in current.items():
        if key in {
            "observed_utc",
            "stage_started_utc",
            "last_seen_utc",
            "last_detail_update_utc",
            "detail_update_count",
            "signature",
        }:
            continue

        if value not in (None, "", [], {}):
            merged[key] = value

    old_schedule = dict(
        previous.get("schedule") or {}
    )
    new_schedule = dict(
        current.get("schedule") or {}
    )
    old_schedule.update(
        {
            key: value
            for key, value in new_schedule.items()
            if value not in (None, "")
        }
    )
    if old_schedule:
        merged["schedule"] = old_schedule

    if not current.get("official_authority"):
        merged["official_authority"] = previous.get(
            "official_authority",
            "",
        )
        merged["official_kind"] = previous.get(
            "official_kind",
            "",
        )
        merged["official_url"] = previous.get(
            "official_url",
            "",
        )
        merged["official_cached"] = previous.get(
            "official_cached",
            False,
        )

    merged["observed_utc"] = first_seen
    merged["stage_started_utc"] = first_seen
    merged["last_seen_utc"] = (
        current.get("last_seen_utc")
        or current.get("observed_utc")
        or utc_iso()
    )

    return merged


def compact_lifecycle_history(
    history: Any,
) -> tuple[list[dict[str, Any]], int]:
    if not isinstance(history, list):
        return [], 0

    compacted: list[dict[str, Any]] = []
    removed = 0

    for raw in history:
        if not isinstance(raw, dict):
            continue

        item = dict(raw)

        if not item.get("stage_started_utc"):
            item["stage_started_utc"] = (
                item.get("observed_utc")
            )

        if (
            TIMELINE_NOISE_GUARD_ENABLED
            and compacted
            and _same_lifecycle_stage(
                compacted[-1],
                item,
            )
        ):
            previous = compacted[-1]
            merged = _merge_stage_snapshot(
                previous,
                item,
            )

            last_time = (
                item.get("last_seen_utc")
                or item.get("observed_utc")
            )
            if last_time:
                merged["last_seen_utc"] = last_time

            merged["detail_update_count"] = (
                int(
                    previous.get(
                        "detail_update_count",
                        0,
                    )
                    or 0
                )
                + 1
            )
            merged["last_detail_update_utc"] = (
                item.get("last_detail_update_utc")
                or item.get("observed_utc")
                or merged.get("last_seen_utc")
            )

            compacted[-1] = merged
            removed += 1
            continue

        compacted.append(item)

    return (
        compacted[-LIFECYCLE_HISTORY_MAX:],
        removed,
    )


def compact_lifecycle_history_state(
    state: dict[str, Any],
) -> int:
    memory = state.get("lifecycle_history")

    if not isinstance(memory, dict):
        state["lifecycle_history"] = {}
        return 0

    total_removed = 0
    cleaned: dict[str, list[dict[str, Any]]] = {}

    for key, history in memory.items():
        compacted, removed = (
            compact_lifecycle_history(history)
        )
        if compacted:
            cleaned[str(key)] = compacted
        total_removed += removed

    state["lifecycle_history"] = cleaned
    return total_removed


def default_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "initialized": False,
        "next_offset": 0,
        "last_state_change_utc": None,
        "last_command_utc": None,
        "updates_seen": 0,
        "commands_processed": 0,
        "recent_commands": {},
        "duplicates_suppressed": 0,
        "issuer_aliases": {},
        "verified_official": {},
        "lifecycle_history": {},
        "watchlist": {},
    }


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return default_state()

    try:
        data = json.loads(
            STATE_PATH.read_text(encoding="utf-8")
        )
    except Exception as exc:
        raise RuntimeError(
            f"command_state.json rusak/tidak valid: {exc}"
        ) from exc

    state = default_state()
    state.update(data)

    if not isinstance(state.get("next_offset"), int):
        state["next_offset"] = 0

    if not isinstance(state.get("recent_commands"), dict):
        state["recent_commands"] = {}

    if not isinstance(state.get("duplicates_suppressed"), int):
        state["duplicates_suppressed"] = 0

    if not isinstance(state.get("issuer_aliases"), dict):
        state["issuer_aliases"] = {}

    if not isinstance(state.get("verified_official"), dict):
        state["verified_official"] = {}

    if not isinstance(state.get("lifecycle_history"), dict):
        state["lifecycle_history"] = {}

    if not isinstance(state.get("watchlist"), dict):
        state["watchlist"] = {}

    # V6.6.1 transparent migration:
    # collapse repeated same-stage rows from V6.6.1.
    state["_timeline_rows_compacted"] = (
        compact_lifecycle_history_state(state)
    )

    state["_scanner_lifecycle_synced"] = (
        sync_scanner_lifecycle_into_command_state(state)
    )

    # Transparent schema migration: existing command_state.json
    # remains valid and does not need to be replaced manually.
    state["schema_version"] = SCHEMA_VERSION

    return state


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    persistent_state = dict(state)
    persistent_state.pop(
        "_timeline_rows_compacted",
        None,
    )
    persistent_state.pop(
        "_scanner_lifecycle_synced",
        None,
    )

    temp = STATE_PATH.with_suffix(".tmp")
    temp.write_text(
        json.dumps(
            persistent_state,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    temp.replace(STATE_PATH)


def authorized_chat_ids() -> set[int]:
    if not RAW_CHAT_IDS:
        raise RuntimeError(
            "TELEGRAM_CHAT_IDS belum tersedia."
        )

    ids: set[int] = set()

    for item in RAW_CHAT_IDS.split(","):
        item = item.strip()
        if not item:
            continue

        try:
            ids.add(int(item))
        except ValueError as exc:
            raise RuntimeError(
                "TELEGRAM_CHAT_IDS harus berupa angka "
                "dipisahkan koma."
            ) from exc

    if not ids:
        raise RuntimeError(
            "TELEGRAM_CHAT_IDS kosong."
        )

    return ids


def require_token() -> str:
    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN belum tersedia."
        )
    return TOKEN


def telegram_call(
    method: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN belum tersedia."
        )

    payload = payload or {}
    encoded: dict[str, str] = {}

    for key, value in payload.items():
        if isinstance(value, (dict, list, tuple)):
            encoded[key] = json.dumps(
                value,
                ensure_ascii=False,
            )
        elif isinstance(value, bool):
            encoded[key] = "true" if value else "false"
        else:
            encoded[key] = str(value)

    body = urllib.parse.urlencode(encoded).encode("utf-8")
    last_exc: Exception | None = None

    for attempt in range(BRIDGE_HTTP_RETRY_ATTEMPTS):
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{TOKEN}/{method}",
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "Kabar-Saham-V6.6.1-Reliability-Guard/1.0",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=TG_API_TIMEOUT_SECONDS,
            ) as response:
                raw = response.read()

            try:
                data = json.loads(raw.decode("utf-8"))
            except Exception as exc:
                raise RuntimeError(
                    "Telegram response bukan JSON valid."
                ) from exc

            if not data.get("ok"):
                raise RuntimeError(
                    "Telegram API error: "
                    + str(data.get("description", "unknown"))
                )

            return data.get("result")

        except urllib.error.HTTPError as exc:
            last_exc = exc
            body_text = ""

            try:
                body_text = exc.read().decode(
                    "utf-8",
                    errors="replace",
                )
            except Exception:
                pass

            retryable = (
                exc.code == 429
                or 500 <= exc.code <= 599
            )

            if (
                not retryable
                or attempt >= BRIDGE_HTTP_RETRY_ATTEMPTS - 1
            ):
                raise RuntimeError(
                    f"Telegram HTTP {exc.code}: "
                    f"{body_text[:300]}"
                ) from exc

            retry_after = 0.0
            try:
                parsed = json.loads(body_text or "{}")
                retry_after = float(
                    ((parsed.get("parameters") or {}).get("retry_after"))
                    or exc.headers.get("Retry-After", "0")
                    or 0
                )
            except Exception:
                pass

            delay = max(
                BRIDGE_HTTP_RETRY_BASE_SECONDS * (2 ** attempt),
                min(20.0, retry_after),
            )
            time.sleep(min(20.0, delay))

        except urllib.error.URLError as exc:
            last_exc = exc

            if attempt >= BRIDGE_HTTP_RETRY_ATTEMPTS - 1:
                raise RuntimeError(
                    f"Telegram network error: {exc.reason}"
                ) from exc

            delay = BRIDGE_HTTP_RETRY_BASE_SECONDS * (2 ** attempt)
            time.sleep(min(20.0, delay))

    if last_exc:
        raise RuntimeError(
            f"Telegram request gagal setelah retry: {last_exc}"
        ) from last_exc

    raise RuntimeError("Telegram request gagal tanpa detail.")



def validate_native_command_menu() -> None:
    """Fail fast before sending malformed BotCommand definitions."""
    if len(TELEGRAM_NATIVE_COMMANDS) > 100:
        raise RuntimeError(
            "Telegram command menu melebihi batas 100 command."
        )

    seen = set()

    for item in TELEGRAM_NATIVE_COMMANDS:
        if not isinstance(item, dict):
            raise RuntimeError(
                "Telegram command definition harus object."
            )

        command = str(
            item.get("command") or ""
        ).strip()

        description = str(
            item.get("description") or ""
        ).strip()

        if not re.fullmatch(
            r"[a-z0-9_]{1,32}",
            command,
        ):
            raise RuntimeError(
                f"Native command invalid: {command!r}"
            )

        if not (
            1
            <= len(description)
            <= 256
        ):
            raise RuntimeError(
                f"Description invalid untuk /{command}."
            )

        if command in seen:
            raise RuntimeError(
                f"Duplicate native command: /{command}"
            )

        seen.add(command)


def _native_command_scope() -> dict[str, Any]:
    if NATIVE_MENU_SET_PRIVATE_SCOPE:
        return {
            "type": "all_private_chats"
        }

    return {
        "type": "default"
    }


def install_native_telegram_menu(
    *,
    verify: bool = True,
) -> dict[str, Any]:
    """Register Telegram's native command list + Commands menu button.

    This is idempotent and can safely be run again after future upgrades.
    """
    if not NATIVE_TELEGRAM_MENU_ENABLED:
        return {
            "enabled": False,
            "commands": 0,
            "default_button": False,
            "private_chats": 0,
            "private_failures": 0,
            "verified": False,
        }

    validate_native_command_menu()

    scope = _native_command_scope()

    set_commands_result = telegram_call(
        "setMyCommands",
        {
            "commands": TELEGRAM_NATIVE_COMMANDS,
            "scope": scope,
        },
    )

    if set_commands_result is not True:
        raise RuntimeError(
            "Telegram setMyCommands tidak mengembalikan True."
        )

    # Explicitly make Commands the bot's default menu button.
    default_button_result = telegram_call(
        "setChatMenuButton",
        {
            "menu_button": {
                "type": "commands"
            },
        },
    )

    if default_button_result is not True:
        raise RuntimeError(
            "Telegram setChatMenuButton default gagal."
        )

    chat_success = 0
    chat_failures = 0

    # Also pin Commands mode for every authorized private chat.
    # If an ID happens to be a group, Telegram can reject that specific chat;
    # the default Commands button and setMyCommands still remain active.
    for chat_id in sorted(
        authorized_chat_ids()
    ):
        try:
            result = telegram_call(
                "setChatMenuButton",
                {
                    "chat_id": chat_id,
                    "menu_button": {
                        "type": "commands"
                    },
                },
            )

            if result is True:
                chat_success += 1
            else:
                chat_failures += 1

        except Exception:
            chat_failures += 1

    verified = False
    actual_commands = []

    if verify:
        result = telegram_call(
            "getMyCommands",
            {
                "scope": scope,
            },
        )

        if isinstance(
            result,
            list,
        ):
            actual_commands = [
                str(
                    item.get("command")
                    or ""
                )
                for item in result
                if isinstance(
                    item,
                    dict,
                )
            ]

            expected = {
                item["command"]
                for item in TELEGRAM_NATIVE_COMMANDS
            }

            verified = (
                expected
                == set(actual_commands)
            )

        if not verified:
            raise RuntimeError(
                "Native command menu verification mismatch."
            )

    return {
        "enabled": True,
        "commands": len(
            TELEGRAM_NATIVE_COMMANDS
        ),
        "default_button": True,
        "private_chats": chat_success,
        "private_failures": chat_failures,
        "verified": verified,
    }


def native_menu_status_text(
    result: dict[str, Any],
) -> str:
    if not result.get("enabled"):
        return (
            "⚠️ <b>Native Telegram Menu OFF.</b>"
        )

    lines = [
        "✅ <b>Native Telegram Command Menu aktif.</b>",
        "",
        (
            "📋 Commands registered: "
            f"<b>{int(result.get('commands', 0) or 0)}</b>"
        ),
        "🔘 Menu Button: <b>COMMANDS</b>",
        (
            "💬 Authorized private chats configured: "
            f"<b>{int(result.get('private_chats', 0) or 0)}</b>"
        ),
        (
            "🔎 Verification: "
            + (
                "✅ PASS"
                if result.get("verified")
                else "⚪ SKIPPED"
            )
        ),
    ]

    failures = int(
        result.get(
            "private_failures",
            0,
        )
        or 0
    )

    if failures:
        lines.append(
            f"⚠️ Chat-specific menu failures: {failures}"
        )

    lines += [
        "",
        "💡 Tombol Menu native muncul di dekat kolom pesan. Posisi/icon dapat berbeda menurut aplikasi Telegram.",
    ]

    return "\n".join(lines)


def send_message_stdlib(
    chat_id: int,
    text: str,
) -> None:
    telegram_call(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
    )


def write_github_output(
    output_file: str | None,
    **values: Any,
) -> None:
    if not output_file:
        return

    path = Path(output_file)
    with path.open(
        "a",
        encoding="utf-8",
    ) as fh:
        for key, value in values.items():
            if isinstance(value, bool):
                value = "true" if value else "false"
            fh.write(f"{key}={value}\n")


def get_updates(
    offset: int | None = None,
    *,
    limit: int = MAX_UPDATES,
) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {
        "limit": limit,
        "timeout": 0,
        "allowed_updates": ["message"],
    }

    if offset is not None:
        payload["offset"] = offset

    result = telegram_call(
        "getUpdates",
        payload,
    )

    if not isinstance(result, list):
        return []

    return [
        x for x in result
        if isinstance(x, dict)
    ]


def message_info(
    update: dict[str, Any],
) -> tuple[int | None, str]:
    message = update.get("message") or {}
    chat = message.get("chat") or {}

    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    try:
        chat_id = int(chat_id)
    except (TypeError, ValueError):
        chat_id = None

    return chat_id, text


def command_name(text: str) -> str:
    if not text.startswith("/"):
        return ""

    head = text.split(maxsplit=1)[0]
    return head.split("@", 1)[0].lower()



def canonical_command_text(text: str) -> str:
    """Normalize command so /analyze cbre and /analyze CBRE are identical."""
    parts = (text or "").strip().split()
    if not parts:
        return ""

    cmd = parts[0].split("@", 1)[0].lower()
    args = [x.upper() for x in parts[1:]]
    return " ".join([cmd, *args]).strip()


def command_fingerprint(chat_id: int, text: str) -> str:
    """
    Persist only a one-way fingerprint. The repository state does not store
    the raw chat ID or raw command text.
    """
    canonical = canonical_command_text(text)
    raw = f"{chat_id}|{canonical}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def update_timestamp(update: dict[str, Any]) -> int:
    message = update.get("message") or {}
    value = message.get("date")
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(time.time())


def cleanup_recent_commands(
    recent: dict[str, Any],
    *,
    now_ts: int | None = None,
) -> dict[str, int]:
    now_ts = int(now_ts or time.time())
    cleaned: dict[str, int] = {}

    for key, value in recent.items():
        try:
            ts = int(value)
        except (TypeError, ValueError):
            continue

        age = max(0, now_ts - ts)
        if age <= RECENT_COMMAND_TTL_SECONDS:
            cleaned[str(key)] = ts

    return cleaned


def format_duplicate_notice(commands: list[str]) -> str:
    counts: dict[str, int] = {}
    order: list[str] = []

    for value in commands:
        canonical = canonical_command_text(value)
        if not canonical:
            continue
        if canonical not in counts:
            order.append(canonical)
            counts[canonical] = 0
        counts[canonical] += 1

    lines = [
        "♻️ <b>Command duplikat diabaikan.</b>",
        "",
        f"Proteksi anti-repeat aktif selama ±{COMMAND_DEDUP_SECONDS} detik.",
    ]

    for value in order[:5]:
        suffix = f" ×{counts[value]}" if counts[value] > 1 else ""
        lines.append(
            f"• <code>{html.escape(value)}</code>{suffix}"
        )

    lines += [
        "",
        "Command pertama tetap diproses; pengiriman ulang yang terlalu dekat tidak dijalankan lagi.",
    ]
    return "\n".join(lines)


# ============================================================
# V6.1.1 EVENT-LEVEL DEDUP / COMPACT DECISION BOARD
# ============================================================

TICKER_TITLE_STOPWORDS = {
    "AKAN", "BARU", "BISA", "BUKA", "DANA", "DARI", "DATA", "DEAL",
    "HARI", "JADI", "JUAL", "KENA", "KINI", "LAGI", "LAMA", "MANA",
    "NAIK", "OLEH", "PARA", "PASAR", "PUNYA", "RAYA", "RESMI",
    "SANG", "SIAP", "SINI", "TAHUN", "TURUN", "UNTUK", "WAJIB",
    "YANG", "BANK", "CNBC", "FUND", "NEWS",
}

TITLE_TICKER_PATTERNS = [
    re.compile(r"\(([A-Z]{4})\)"),
    re.compile(
        r"\b(?:saham|emiten|ticker|kode\s+saham|kode)\s+([A-Z]{4})\b",
        flags=re.I,
    ),
    re.compile(
        r"\b([A-Z]{4})\s+(?:saham|emiten)\b",
        flags=re.I,
    ),
]


def _valid_equity_ticker(value: Any) -> str | None:
    """
    Conservative validator for IDX equity ticker shown in Decision Board.
    Accepts MAPI and MAPI.JK; rejects numeric fragments such as "34".
    """
    raw = str(value or "").strip().upper()

    # yfinance-style suffix is acceptable input, but not displayed.
    if raw.endswith(".JK"):
        raw = raw[:-3]

    if not re.fullmatch(r"[A-Z]{4}", raw):
        return None

    if raw in TICKER_TITLE_STOPWORDS:
        return None

    return raw


def _infer_ticker_from_title(title: str) -> str | None:
    if not TITLE_TICKER_INFERENCE:
        return None

    original = str(title or "")

    # Explicit ticker contexts first.
    for pattern in TITLE_TICKER_PATTERNS:
        for match in pattern.finditer(original):
            candidate = _valid_equity_ticker(match.group(1))
            if candidate:
                return candidate

    # Bare 4-letter token only when it is already ALL CAPS in the headline.
    # This prevents ordinary words such as "Baru" from becoming BARU.
    for candidate in re.findall(
        r"(?<![A-Za-z])([A-Z]{4})(?![A-Za-z])",
        original,
    ):
        clean = _valid_equity_ticker(candidate)
        if clean:
            return clean

    return None


def _resolved_ticker(article: dict[str, Any]) -> str | None:
    details = article.setdefault("details", {})

    extracted_ticker = _valid_equity_ticker(details.get("ticker"))
    ticker = extracted_ticker

    # Garbage extractor output (example: 34) is discarded.
    if not ticker:
        ticker = _infer_ticker_from_title(article.get("title", ""))

    if ticker:
        details["ticker"] = ticker
        article["decision_ticker_source"] = (
            "EXTRACTOR" if extracted_ticker else "TITLE"
        )
        return ticker

    details["ticker"] = None
    article["decision_ticker_source"] = "NONE"
    return None


def _norm_identity(value: Any) -> str:
    text = re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper())
    return re.sub(r"\s+", " ", text).strip()





def sync_scanner_lifecycle_into_command_state(
    state: dict[str, Any],
) -> int:
    """Import only material Smart Watch changes from scanner github_state."""
    if not SCANNER_STATE_PATH.exists():
        return 0

    try:
        scanner_state = json.loads(
            SCANNER_STATE_PATH.read_text(encoding="utf-8")
        )
    except Exception:
        return 0

    scanner_memory = scanner_state.get("watch_lifecycle") or {}
    if not isinstance(scanner_memory, dict):
        return 0

    watchlist = state.get("watchlist") or {}
    synced = 0

    for key, raw_snapshot in scanner_memory.items():
        if not isinstance(raw_snapshot, dict):
            continue

        ticker = str(
            raw_snapshot.get("ticker") or ""
        ).upper().strip()
        if ticker not in watchlist:
            continue

        current_history = (
            state.get("lifecycle_history") or {}
        ).get(str(key)) or []
        previous = (
            current_history[-1]
            if isinstance(current_history, list) and current_history
            else None
        )

        scanner_stage = str(
            raw_snapshot.get("stage") or ""
        )
        previous_stage = str(
            (previous or {}).get("stage") or ""
        )
        scanner_sig = _lifecycle_signature(
            raw_snapshot
        )
        previous_sig = (
            _lifecycle_signature(previous)
            if isinstance(previous, dict)
            else None
        )

        if (
            previous_stage == scanner_stage
            and previous_sig == scanner_sig
        ):
            continue

        result = record_lifecycle_snapshot(
            state,
            dict(raw_snapshot),
        )
        if (
            result.get("changed")
            or result.get("history_appended")
        ):
            synced += 1

    return synced


# ============================================================
# V6.6.1 SMART WATCHLIST
# ============================================================

def _valid_watch_ticker(value: Any) -> str | None:
    ticker = str(value or "").upper().strip()
    return ticker if re.fullmatch(r"[A-Z]{4}", ticker) else None


def _normalize_watch_priority(value: Any) -> str | None:
    priority = str(value or "WATCH").upper().strip()
    aliases = {
        "TINGGI": "HIGH",
        "H": "HIGH",
        "W": "WATCH",
        "N": "NORMAL",
    }
    priority = aliases.get(priority, priority)
    return priority if priority in WATCH_PRIORITIES else None


def _latest_lifecycle_for_ticker(
    state: dict[str, Any],
    ticker: str,
) -> dict[str, Any] | None:
    memory = state.get("lifecycle_history") or {}
    ticker = str(ticker or "").upper()
    candidates: list[dict[str, Any]] = []

    if not isinstance(memory, dict):
        return None

    for key, history in memory.items():
        if not str(key).upper().startswith(ticker + "|"):
            continue
        if not isinstance(history, list) or not history:
            continue
        item = history[-1]
        if isinstance(item, dict):
            candidates.append(item)

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            _parse_iso_datetime(
                item.get("last_seen_utc")
                or item.get("observed_utc")
            )
            or datetime.min.replace(tzinfo=timezone.utc),
            int(item.get("stage_step", 0) or 0),
        ),
        reverse=True,
    )
    return dict(candidates[0])


def upsert_watchlist_entry(
    state: dict[str, Any],
    ticker: str,
    priority: str = "WATCH",
) -> tuple[dict[str, Any] | None, bool, str | None]:
    ticker = _valid_watch_ticker(ticker)
    priority = _normalize_watch_priority(priority)

    if not ticker:
        return None, False, "Ticker harus 4 huruf."
    if not priority:
        return None, False, "Priority harus HIGH, WATCH, atau NORMAL."

    watchlist = state.setdefault("watchlist", {})
    if ticker not in watchlist and len(watchlist) >= WATCHLIST_MAX_TICKERS:
        return None, False, f"Watchlist penuh (maks {WATCHLIST_MAX_TICKERS} ticker)."

    previous = watchlist.get(ticker)
    existing = previous if isinstance(previous, dict) else {}
    lifecycle = _latest_lifecycle_for_ticker(state, ticker)
    aliases = state.get("issuer_aliases") or {}
    alias_list = aliases.get(ticker) if isinstance(aliases, dict) else None
    issuer = (
        (lifecycle or {}).get("issuer")
        or ((alias_list or [None])[0] if isinstance(alias_list, list) else None)
        or existing.get("issuer")
        or ""
    )

    entry = {
        "ticker": ticker,
        "priority": priority,
        "added_utc": existing.get("added_utc") or utc_iso(),
        "updated_utc": utc_iso(),
        "issuer": issuer,
        "family": (lifecycle or {}).get("family") or existing.get("family") or "",
        "last_known_stage": (lifecycle or {}).get("stage") or existing.get("last_known_stage") or "",
    }
    watchlist[ticker] = entry
    changed = previous != entry
    return entry, changed, None


def remove_watchlist_entry(
    state: dict[str, Any],
    ticker: str,
) -> bool:
    ticker = _valid_watch_ticker(ticker)
    if not ticker:
        return False
    watchlist = state.setdefault("watchlist", {})
    return watchlist.pop(ticker, None) is not None


def format_watchlist(state: dict[str, Any]) -> str:
    watchlist = state.get("watchlist") or {}
    if not isinstance(watchlist, dict) or not watchlist:
        return (
            "👀 <b>SMART WATCHLIST</b>\n\n"
            "Belum ada ticker dipantau.\n"
            "Gunakan <code>/watch DOOH HIGH</code>."
        )

    items = []
    for ticker, raw in watchlist.items():
        if not isinstance(raw, dict):
            raw = {"ticker": ticker, "priority": "WATCH"}
        priority = _normalize_watch_priority(raw.get("priority")) or "WATCH"
        items.append((WATCH_PRIORITY_RANK.get(priority, 0), str(ticker), raw, priority))
    items.sort(key=lambda x: (x[0], x[1]), reverse=True)

    icon = {"HIGH": "🔥", "WATCH": "👀", "NORMAL": "ℹ️"}
    lines = [
        "👀 <b>V6.6.1 SMART WATCHLIST</b>",
        f"Dipantau: <b>{len(items)}</b>/{WATCHLIST_MAX_TICKERS} ticker",
        "",
    ]

    for _, ticker, entry, priority in items:
        latest = _latest_lifecycle_for_ticker(
            state,
            ticker,
        ) or {}
        issuer = str(
            latest.get("issuer")
            or entry.get("issuer")
            or ""
        ).strip()
        stage = str(
            latest.get("stage")
            or entry.get("last_known_stage")
            or ""
        ).strip()
        line = f"{icon.get(priority, '👀')} <b>{html.escape(ticker)}</b> — {priority}"
        if issuer:
            line += " — " + html.escape(issuer)
        lines.append(line)
        if stage:
            lines.append("   🚦 " + html.escape(stage))

    lines += [
        "",
        "Perintah: <code>/watch TICKER HIGH|WATCH|NORMAL</code>",
        "Hapus: <code>/unwatch TICKER</code>",
        "Dashboard: <code>/watchboard</code>",
    ]
    return "\n".join(lines)[:3900]



# ============================================================
# V6.6.1 CONTROL CENTER + HEALTH MONITOR
# ============================================================

def _v66_parse_iso(value: Any):
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except Exception:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def _v66_age_minutes(value: Any):
    parsed = _v66_parse_iso(value)

    if parsed is None:
        return None

    return max(
        0,
        int(
            (
                datetime.now(timezone.utc)
                - parsed
            ).total_seconds()
            // 60
        ),
    )


def _v66_age_text(value: Any) -> str:
    minutes = _v66_age_minutes(value)

    if minutes is None:
        return "belum tersedia"

    if minutes < 1:
        return "<1 menit lalu"

    if minutes < 60:
        return f"{minutes} menit lalu"

    hours, remainder = divmod(
        minutes,
        60,
    )

    if hours < 24:
        return (
            f"{hours}j {remainder}m lalu"
            if remainder
            else f"{hours}j lalu"
        )

    return f"{hours // 24} hari lalu"


def _v66_duration_seconds(run: dict[str, Any]):
    started = _v66_parse_iso(
        run.get("run_started_at")
        or run.get("created_at")
    )
    finished = _v66_parse_iso(
        run.get("updated_at")
    )

    if not started or not finished:
        return None

    return max(
        0,
        int(
            (
                finished
                - started
            ).total_seconds()
        ),
    )


def _v66_github_headers():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "Kabar-Saham-V6.6.1-Health-Monitor/1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    token = (
        os.getenv("GITHUB_TOKEN", "").strip()
        or os.getenv("GH_TOKEN", "").strip()
    )

    if token:
        headers["Authorization"] = (
            f"Bearer {token}"
        )

    return headers


def _v66_github_api_json(path: str):
    if not HEALTH_GITHUB_API_ENABLED:
        raise RuntimeError(
            "GitHub health API disabled."
        )

    if not GITHUB_REPOSITORY_NAME:
        raise RuntimeError(
            "GITHUB_REPOSITORY tidak tersedia."
        )

    url = (
        "https://api.github.com/repos/"
        + GITHUB_REPOSITORY_NAME
        + "/"
        + path.lstrip("/")
    )

    request = urllib.request.Request(
        url,
        headers=_v66_github_headers(),
        method="GET",
    )

    last_exc = None

    for attempt in range(
        BRIDGE_HTTP_RETRY_ATTEMPTS
    ):
        try:
            with urllib.request.urlopen(
                request,
                timeout=15,
            ) as response:
                raw = response.read()

            data = json.loads(
                raw.decode("utf-8")
            )

            if not isinstance(data, dict):
                raise RuntimeError(
                    "GitHub API response tidak valid."
                )

            return data

        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
        ) as exc:
            last_exc = exc

            retryable = True

            if isinstance(
                exc,
                urllib.error.HTTPError,
            ):
                retryable = (
                    exc.code == 429
                    or 500 <= exc.code <= 599
                )

            if (
                not retryable
                or attempt
                >= BRIDGE_HTTP_RETRY_ATTEMPTS - 1
            ):
                break

            time.sleep(
                min(
                    8.0,
                    BRIDGE_HTTP_RETRY_BASE_SECONDS
                    * (2 ** attempt),
                )
            )

    raise RuntimeError(
        "GitHub Actions API gagal: "
        + (
            type(last_exc).__name__
            if last_exc
            else "unknown"
        )
    )


def _v66_workflow_health(
    workflow_file: str,
    *,
    stale_minutes: int,
):
    encoded = urllib.parse.quote(
        workflow_file,
        safe="",
    )

    data = _v66_github_api_json(
        "actions/workflows/"
        + encoded
        + "/runs?per_page="
        + str(HEALTH_RUN_LOOKBACK)
    )

    runs = data.get("workflow_runs") or []

    if not isinstance(runs, list):
        runs = []

    completed = [
        run
        for run in runs
        if (
            isinstance(run, dict)
            and str(
                run.get("status")
                or ""
            ).lower()
            == "completed"
        )
    ]

    completed.sort(
        key=lambda run: (
            _v66_parse_iso(
                run.get("updated_at")
            )
            or datetime.min.replace(
                tzinfo=timezone.utc
            )
        ),
        reverse=True,
    )

    latest = (
        completed[0]
        if completed
        else None
    )

    if not latest:
        return {
            "ok": False,
            "stale": True,
            "conclusion": "NO COMPLETED RUN",
            "updated_at": None,
            "age_minutes": None,
            "duration_seconds": None,
            "failures_24h": 0,
            "run_number": None,
        }

    updated_at = latest.get(
        "updated_at"
    )
    age = _v66_age_minutes(
        updated_at
    )
    conclusion = str(
        latest.get("conclusion")
        or "unknown"
    ).upper()

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(hours=24)
    )

    failures_24h = 0

    for run in completed:
        updated = _v66_parse_iso(
            run.get("updated_at")
        )

        if (
            updated is not None
            and updated >= cutoff
            and str(
                run.get("conclusion")
                or ""
            ).lower()
            not in {
                "success",
                "skipped",
                "neutral",
            }
        ):
            failures_24h += 1

    return {
        "ok": conclusion == "SUCCESS",
        "stale": (
            age is None
            or age > stale_minutes
        ),
        "conclusion": conclusion,
        "updated_at": updated_at,
        "age_minutes": age,
        "duration_seconds": _v66_duration_seconds(
            latest
        ),
        "failures_24h": failures_24h,
        "run_number": latest.get(
            "run_number"
        ),
    }


def _v66_health_icon(info: dict[str, Any]) -> str:
    if not info.get("ok"):
        return "❌"

    if info.get("stale"):
        return "⚠️"

    return "✅"


def _v66_watch_sync_summary(
    state: dict[str, Any],
    scanner_state: dict[str, Any],
):
    watchlist = state.get("watchlist") or {}

    if not isinstance(watchlist, dict):
        watchlist = {}

    tokens = scanner_state.get(
        "watch_baseline_tokens"
    ) or {}

    if not isinstance(tokens, dict):
        tokens = {}

    synced = 0

    for ticker, raw_entry in watchlist.items():
        if not isinstance(raw_entry, dict):
            continue

        if str(
            tokens.get(ticker) or ""
        ) == _watchboard_entry_token(
            raw_entry
        ):
            synced += 1

    return len(watchlist), synced


def _v66_safe_workflow_health(
    workflow_file: str,
    stale_minutes: int,
):
    try:
        return (
            _v66_workflow_health(
                workflow_file,
                stale_minutes=stale_minutes,
            ),
            None,
        )
    except Exception as exc:
        return (
            {
                "ok": False,
                "stale": True,
                "conclusion": "UNKNOWN",
                "updated_at": None,
                "age_minutes": None,
                "duration_seconds": None,
                "failures_24h": 0,
                "run_number": None,
            },
            f"{type(exc).__name__}: {str(exc)}",
        )


def format_system_health(
    core: Any,
    state: dict[str, Any],
) -> str:
    scanner_info, scanner_error = (
        _v66_safe_workflow_health(
            AUTO_ALERT_WORKFLOW_FILE,
            HEALTH_SCAN_STALE_MINUTES,
        )
    )

    bridge_info, bridge_error = (
        _v66_safe_workflow_health(
            COMMAND_BRIDGE_WORKFLOW_FILE,
            HEALTH_BRIDGE_STALE_MINUTES,
        )
    )

    scanner_state = (
        _watchboard_load_scanner_state()
    )

    watch_total, watch_synced = (
        _v66_watch_sync_summary(
            state,
            scanner_state,
        )
    )

    verified = state.get(
        "verified_official"
    ) or {}
    lifecycle = state.get(
        "lifecycle_history"
    ) or {}

    verified_count = (
        len(verified)
        if isinstance(verified, dict)
        else 0
    )
    lifecycle_count = (
        len(lifecycle)
        if isinstance(lifecycle, dict)
        else 0
    )

    api_partial = bool(
        scanner_error
        or bridge_error
    )

    healthy = (
        scanner_info.get("ok")
        and not scanner_info.get("stale")
        and bridge_info.get("ok")
        and not bridge_info.get("stale")
    )

    if healthy:
        overall = "✅ HEALTHY"
    elif api_partial:
        overall = "⚠️ PARTIAL CHECK"
    else:
        overall = "⚠️ CHECK"

    def run_lines(label, info):
        duration = info.get(
            "duration_seconds"
        )

        duration_text = (
            f"{duration}s"
            if duration is not None
            else "-"
        )

        number = info.get(
            "run_number"
        )

        run_text = (
            f"#{number}"
            if number is not None
            else "-"
        )

        return [
            (
                f"{_v66_health_icon(info)} "
                f"<b>{label}:</b> "
                f"{html.escape(str(info.get('conclusion') or 'UNKNOWN'))}"
            ),
            (
                "   🕒 "
                + html.escape(
                    _v66_age_text(
                        info.get("updated_at")
                    )
                )
                + f" | ⏱ {duration_text}"
                + f" | Run {run_text}"
            ),
            (
                "   ❌ Failure 24h: "
                + str(
                    int(
                        info.get(
                            "failures_24h",
                            0,
                        )
                        or 0
                    )
                )
            ),
        ]

    lines = [
        "🩺 <b>V6.6.2 SYSTEM HEALTH</b>",
        "",
        f"Overall: <b>{overall}</b>",
        "",
    ]

    lines.extend(
        run_lines(
            "Auto Scanner",
            scanner_info,
        )
    )
    lines.append("")
    lines.extend(
        run_lines(
            "Command Bridge",
            bridge_info,
        )
    )

    lines += [
        "",
        (
            f"👀 <b>Watchlist:</b> "
            f"{watch_total} ticker"
            f" | 🛡️ Synced: {watch_synced}/{watch_total}"
        ),
        (
            f"🏛️ <b>Verified Official Cache:</b> "
            f"{verified_count} ticker"
        ),
        (
            f"🧭 <b>Lifecycle Memory:</b> "
            f"{lifecycle_count} event"
        ),
        (
            f"♻️ <b>Command duplicates suppressed:</b> "
            f"{int(state.get('duplicates_suppressed', 0) or 0)}"
        ),
        "💾 <b>State:</b> ✅ command_state + github_state",
        "",
        "📡 <b>Health source:</b> GitHub Actions API + state",
    ]

    if scanner_error:
        lines += [
            "",
            "⚠️ Scanner API: "
            + html.escape(
                scanner_error[:300]
            ),
        ]

    if bridge_error:
        lines += [
            "⚠️ Bridge API: "
            + html.escape(
                bridge_error[:300]
            ),
        ]

    lines += [
        "",
        (
            f"Stale threshold: scanner >{HEALTH_SCAN_STALE_MINUTES}m"
            f" | bridge >{HEALTH_BRIDGE_STALE_MINUTES}m"
        ),
        "💡 Jika cron sengaja OFF saat upgrade, status stale/CHECK adalah normal.",
    ]

    return "\n".join(lines)[:3900]


def format_control_center(
    core: Any,
    state: dict[str, Any],
) -> str:
    scanner_state = (
        _watchboard_load_scanner_state()
    )

    watch_total, watch_synced = (
        _v66_watch_sync_summary(
            state,
            scanner_state,
        )
    )

    due_count = 0

    try:
        watchlist = state.get(
            "watchlist"
        ) or {}

        for ticker, raw_entry in (
            watchlist.items()
            if isinstance(watchlist, dict)
            else []
        ):
            ticker_clean = (
                _valid_watch_ticker(
                    ticker
                )
            )

            if not ticker_clean:
                continue

            item = _watchboard_item(
                core,
                state,
                scanner_state,
                ticker_clean,
                raw_entry,
            )

            if (
                item.get("nearest")
                and 0
                <= item["nearest"][0]
                <= WATCHBOARD_DUE_DAYS
            ):
                due_count += 1
    except Exception:
        pass

    return "\n".join(
        [
            "🎛️ <b>V6.6.2 KABAR SAHAM CONTROL CENTER</b>",
            "",
            (
                f"👀 Watchlist: <b>{watch_total}</b>"
                f" | 🛡️ Synced: <b>{watch_synced}/{watch_total}</b>"
                f" | ⏰ Due ≤7d: <b>{due_count}</b>"
            ),
            "",
            "🔘 <b>Native Menu:</b> gunakan tombol <b>Menu</b> di dekat kolom pesan",
            "🔄 <code>/syncmenu</code> — sinkronkan ulang tombol/daftar command",
            "",
            "🩺 <code>/health</code> — kesehatan scanner & Command Bridge",
            "📅 <code>/today</code> — milestone corporate action hari ini",
            "🕘 <code>/recent</code> — perubahan lifecycle terbaru",
            "📊 <code>/watchboard</code> — semua ticker Smart Watch",
            "🧭 <code>/timeline TICKER</code> — riwayat satu ticker",
            "🔎 <code>/analyze TICKER</code> — analisis lengkap",
            "🏛️ <code>/official TICKER</code> — sumber resmi",
            "🧠 <code>/decision</code> — Decision Board",
            "📰 <code>/news24h</code> — berita 24 jam terakhir",
            "",
            "Watchlist:",
            "• <code>/watch DOOH HIGH</code>",
            "• <code>/unwatch DOOH</code>",
            "• <code>/watchlist</code>",
            "",
            "💡 Rutinitas cepat: <code>/health</code> → <code>/today</code> → <code>/watchboard</code>",
        ]
    )[:3900]


def _v66_latest_lifecycle_rows(
    state: dict[str, Any],
):
    memory = state.get(
        "lifecycle_history"
    ) or {}

    if not isinstance(memory, dict):
        return []

    rows = []

    for history in memory.values():
        if (
            not isinstance(history, list)
            or not history
        ):
            continue

        latest = history[-1]

        if isinstance(latest, dict):
            rows.append(
                dict(latest)
            )

    return rows


def format_today_summary(
    core: Any,
    state: dict[str, Any],
) -> str:
    today = datetime.now(
        TIMELINE_TZ
    ).date()

    labels = getattr(
        core,
        "LIFECYCLE_SCHEDULE_LABELS",
        {},
    )

    items = []

    for snapshot in (
        _v66_latest_lifecycle_rows(
            state
        )
    ):
        schedule = (
            snapshot.get("schedule")
            or {}
        )

        if not isinstance(
            schedule,
            dict,
        ):
            continue

        for key, raw_value in schedule.items():
            parsed = (
                _watchboard_parse_date(
                    raw_value
                )
            )

            if parsed != today:
                continue

            items.append(
                {
                    "ticker": str(
                        snapshot.get("ticker")
                        or "-"
                    ),
                    "issuer": str(
                        snapshot.get("issuer")
                        or ""
                    ),
                    "stage": str(
                        snapshot.get("stage")
                        or "-"
                    ),
                    "official": str(
                        snapshot.get(
                            "official_authority"
                        )
                        or ""
                    ),
                    "label": str(
                        labels.get(
                            key,
                            key,
                        )
                    ),
                }
            )

    lines = [
        "📅 <b>V6.6.2 TODAY — CORPORATE ACTION</b>",
        (
            "Tanggal: "
            + html.escape(
                _watchboard_format_date(
                    today
                )
            )
        ),
        "",
    ]

    if not items:
        lines += [
            "Tidak ada milestone bertanggal hari ini di lifecycle memory.",
            "",
            "💡 Untuk berita 24 jam terakhir gunakan <code>/news24h</code>.",
        ]
        return "\n".join(lines)

    for idx, item in enumerate(
        items[:TODAY_MAX_ITEMS],
        start=1,
    ):
        official = (
            " | 🏛️ ✅ "
            + html.escape(
                item["official"]
            )
            if item["official"]
            else ""
        )

        lines += [
            (
                f"<b>{idx}. "
                f"{html.escape(item['ticker'])}</b>"
                f" — {html.escape(item['label'])}"
            ),
            (
                "   🚦 "
                + html.escape(
                    item["stage"]
                )
                + official
            ),
        ]

        if item["issuer"]:
            lines.append(
                "   🏢 "
                + html.escape(
                    item["issuer"]
                )
            )

        lines.append("")

    lines.append(
        "💡 Berita 24 jam: <code>/news24h</code>"
    )

    return "\n".join(lines)[:3900]


def _v66_recent_rows(
    state: dict[str, Any],
):
    memory = state.get(
        "lifecycle_history"
    ) or {}

    if not isinstance(memory, dict):
        return []

    rows = []

    for history in memory.values():
        if not isinstance(
            history,
            list,
        ):
            continue

        for snapshot in history:
            if not isinstance(
                snapshot,
                dict,
            ):
                continue

            timestamp = (
                snapshot.get(
                    "stage_started_utc"
                )
                or snapshot.get(
                    "observed_utc"
                )
                or snapshot.get(
                    "last_seen_utc"
                )
            )

            parsed = _v66_parse_iso(
                timestamp
            )

            if not parsed:
                continue

            rows.append(
                {
                    "time": parsed,
                    "ticker": str(
                        snapshot.get("ticker")
                        or "-"
                    ),
                    "issuer": str(
                        snapshot.get("issuer")
                        or ""
                    ),
                    "stage": str(
                        snapshot.get("stage")
                        or "-"
                    ),
                    "official": str(
                        snapshot.get(
                            "official_authority"
                        )
                        or ""
                    ),
                }
            )

    rows.sort(
        key=lambda row: row["time"],
        reverse=True,
    )

    return rows


def format_recent_summary(
    state: dict[str, Any],
) -> str:
    rows = _v66_recent_rows(
        state
    )

    lines = [
        "🕘 <b>V6.6.2 RECENT LIFECYCLE CHANGES</b>",
        "",
    ]

    if not rows:
        lines += [
            "Belum ada lifecycle history yang dapat ditampilkan.",
        ]
        return "\n".join(lines)

    for idx, row in enumerate(
        rows[:RECENT_MAX_ITEMS],
        start=1,
    ):
        official = (
            " | 🏛️ "
            + html.escape(
                row["official"]
            )
            if row["official"]
            else ""
        )

        lines += [
            (
                f"<b>{idx}. "
                f"{html.escape(row['ticker'])}</b>"
                f" — {html.escape(row['stage'])}"
                + official
            ),
            (
                "   🕒 "
                + html.escape(
                    format_timeline_local_time(
                        row["time"].isoformat()
                    )
                )
            ),
        ]

        if row["issuer"]:
            lines.append(
                "   🏢 "
                + html.escape(
                    row["issuer"]
                )
            )

        lines.append("")

    lines += [
        "💡 Recent = perubahan stage yang sudah tersimpan, bukan seluruh headline berita.",
    ]

    return "\n".join(lines)[:3900]


# ============================================================
# V6.6.1 SMART WATCH DASHBOARD
# ============================================================

def _watchboard_load_scanner_state() -> dict[str, Any]:
    if not SCANNER_STATE_PATH.exists():
        return {}

    try:
        data = json.loads(
            SCANNER_STATE_PATH.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def _watchboard_entry_token(entry: dict[str, Any]) -> str:
    return "|".join(
        [
            str(entry.get("added_utc") or ""),
            str(entry.get("updated_utc") or ""),
            str(entry.get("priority") or "WATCH").upper(),
        ]
    )


def _watchboard_snapshot_time(snapshot: dict[str, Any] | None):
    if not isinstance(snapshot, dict):
        return None

    for key in (
        "scanner_seen_utc",
        "last_seen_utc",
        "observed_utc",
        "stage_started_utc",
    ):
        parsed = _parse_iso_datetime(
            snapshot.get(key)
        )
        if parsed:
            return parsed

    return None


def _watchboard_scanner_snapshot(
    scanner_state: dict[str, Any],
    ticker: str,
) -> dict[str, Any] | None:
    memory = scanner_state.get("watch_lifecycle") or {}

    if not isinstance(memory, dict):
        return None

    candidates = []

    for key, raw in memory.items():
        if not isinstance(raw, dict):
            continue

        raw_ticker = str(
            raw.get("ticker") or ""
        ).upper().strip()

        if (
            raw_ticker != ticker
            and not str(key).upper().startswith(ticker + "|")
        ):
            continue

        candidates.append(dict(raw))

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            _watchboard_snapshot_time(item)
            or datetime.min.replace(tzinfo=timezone.utc),
            int(item.get("stage_step", 0) or 0),
        ),
        reverse=True,
    )

    return candidates[0]


def _watchboard_best_snapshot(
    state: dict[str, Any],
    scanner_state: dict[str, Any],
    ticker: str,
) -> dict[str, Any]:
    command_snapshot = (
        _latest_lifecycle_for_ticker(state, ticker)
        or {}
    )
    scanner_snapshot = (
        _watchboard_scanner_snapshot(
            scanner_state,
            ticker,
        )
        or {}
    )

    command_time = _watchboard_snapshot_time(
        command_snapshot
    )
    scanner_time = _watchboard_snapshot_time(
        scanner_snapshot
    )

    if (
        scanner_snapshot
        and (
            not command_snapshot
            or (
                scanner_time is not None
                and (
                    command_time is None
                    or scanner_time > command_time
                )
            )
        )
    ):
        merged = dict(command_snapshot)

        for key, value in scanner_snapshot.items():
            if value not in (None, "", [], {}):
                merged[key] = value

        merged["_dashboard_source"] = "github_state"
        return merged

    result = dict(command_snapshot)

    if result:
        result["_dashboard_source"] = "command_state"

    return result


def _watchboard_parse_date(value: Any):
    text = str(value or "").strip()

    if not text:
        return None

    match = re.search(
        r"(?<!\d)(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})(?!\d)",
        text,
        flags=re.I,
    )

    if match:
        day = int(match.group(1))
        month = WATCHBOARD_MONTH_MAP.get(
            match.group(2).lower()
        )
        year = int(match.group(3))

        if month:
            try:
                return datetime(
                    year,
                    month,
                    day,
                    tzinfo=TIMELINE_TZ,
                ).date()
            except ValueError:
                return None

    match = re.search(
        r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](20\d{2})(?!\d)",
        text,
    )

    if match:
        try:
            return datetime(
                int(match.group(3)),
                int(match.group(2)),
                int(match.group(1)),
                tzinfo=TIMELINE_TZ,
            ).date()
        except ValueError:
            return None

    return None


def _watchboard_format_date(value) -> str:
    if not value:
        return "-"

    month = INDONESIAN_MONTHS.get(
        value.month,
        f"{value.month:02d}",
    )

    return (
        f"{value.day:02d} "
        f"{month} "
        f"{value.year}"
    )


def _watchboard_nearest_milestone(
    core: Any,
    snapshot: dict[str, Any],
):
    schedule = snapshot.get("schedule") or {}

    if not isinstance(schedule, dict):
        return None

    today = datetime.now(
        TIMELINE_TZ
    ).date()

    labels = getattr(
        core,
        "LIFECYCLE_SCHEDULE_LABELS",
        {},
    )

    candidates = []

    for key, raw in schedule.items():
        parsed = _watchboard_parse_date(raw)

        if parsed is None:
            continue

        days = (parsed - today).days

        if days < 0:
            continue

        candidates.append(
            (
                days,
                str(key),
                parsed,
                str(labels.get(key, key)),
            )
        )

    candidates.sort(
        key=lambda item: item[0]
    )

    return candidates[0] if candidates else None


def _watchboard_baseline_status(
    scanner_state: dict[str, Any],
    ticker: str,
    entry: dict[str, Any],
) -> tuple[str, bool]:
    tokens = scanner_state.get(
        "watch_baseline_tokens"
    ) or {}

    if not isinstance(tokens, dict):
        return "UNKNOWN", False

    expected = _watchboard_entry_token(entry)
    actual = str(tokens.get(ticker) or "")

    if actual and actual == expected:
        return "SYNCED", True

    return "PENDING", False


def _watchboard_item(
    core: Any,
    state: dict[str, Any],
    scanner_state: dict[str, Any],
    ticker: str,
    raw_entry: Any,
) -> dict[str, Any]:
    entry = (
        dict(raw_entry)
        if isinstance(raw_entry, dict)
        else {
            "ticker": ticker,
            "priority": "WATCH",
        }
    )

    priority = (
        _normalize_watch_priority(
            entry.get("priority")
        )
        or "WATCH"
    )

    snapshot = _watchboard_best_snapshot(
        state,
        scanner_state,
        ticker,
    )

    issuer = str(
        snapshot.get("issuer")
        or entry.get("issuer")
        or ""
    ).strip()

    stage = str(
        snapshot.get("stage")
        or entry.get("last_known_stage")
        or ""
    ).strip()

    step = int(
        snapshot.get("stage_step", 0)
        or 0
    )
    total = int(
        snapshot.get("stage_total", 0)
        or 0
    )

    official = str(
        snapshot.get("official_authority")
        or ""
    ).strip()

    official_kind = str(
        snapshot.get("official_kind")
        or "PRIMARY"
    ).strip()

    next_milestone = str(
        snapshot.get("next_milestone")
        or ""
    ).strip()

    nearest = _watchboard_nearest_milestone(
        core,
        snapshot,
    )

    baseline_text, baseline_synced = (
        _watchboard_baseline_status(
            scanner_state,
            ticker,
            entry,
        )
    )

    snapshot_dt = _watchboard_snapshot_time(
        snapshot
    )

    last_seen_text = (
        format_timeline_local_time(
            snapshot_dt.isoformat()
        )
        if snapshot_dt
        else "-"
    )

    priority_rank = WATCH_PRIORITY_RANK.get(
        priority,
        0,
    )

    milestone_days = (
        nearest[0]
        if nearest
        else None
    )

    due_rank = (
        100 - milestone_days
        if (
            milestone_days is not None
            and milestone_days <= WATCHBOARD_DUE_DAYS
        )
        else 0
    )

    progress_rank = (
        int((step / max(total, 1)) * 100)
        if step
        else 0
    )

    return {
        "ticker": ticker,
        "entry": entry,
        "priority": priority,
        "priority_rank": priority_rank,
        "snapshot": snapshot,
        "issuer": issuer,
        "stage": stage,
        "step": step,
        "total": total,
        "official": official,
        "official_kind": official_kind,
        "next_milestone": next_milestone,
        "nearest": nearest,
        "baseline": baseline_text,
        "baseline_synced": baseline_synced,
        "last_seen": last_seen_text,
        "source": snapshot.get("_dashboard_source", "-"),
        "sort_key": (
            priority_rank,
            due_rank,
            progress_rank,
            ticker,
        ),
    }


def _watchboard_filter(
    items: list[dict[str, Any]],
    mode: str,
) -> list[dict[str, Any]]:
    mode = str(
        mode or "ALL"
    ).upper().strip()

    if mode in {"ALL", ""}:
        return items

    if mode in WATCH_PRIORITIES:
        return [
            item
            for item in items
            if item["priority"] == mode
        ]

    if mode == "DUE":
        return [
            item
            for item in items
            if (
                item.get("nearest")
                and 0
                <= item["nearest"][0]
                <= WATCHBOARD_DUE_DAYS
            )
        ]

    if mode == "PENDING":
        return [
            item
            for item in items
            if not item.get("baseline_synced")
        ]

    return []


def _watchboard_item_lines(
    item: dict[str, Any],
) -> list[str]:
    icon = {
        "HIGH": "🔥",
        "WATCH": "👀",
        "NORMAL": "ℹ️",
    }.get(item["priority"], "👀")

    lines = [
        (
            f"{icon} <b>{html.escape(item['ticker'])}</b> "
            f"— {html.escape(item['priority'])}"
        )
    ]

    if item.get("issuer"):
        lines.append(
            "   🏢 "
            + html.escape(item["issuer"])
        )

    stage = item.get("stage") or "-"
    step = item.get("step") or 0
    total = item.get("total") or 0

    stage_text = html.escape(stage)

    if step and total:
        stage_text += f" ({step}/{total})"

    if item.get("official"):
        official_text = (
            "🏛️ ✅ "
            + html.escape(
                item["official"]
            )
        )
    else:
        official_text = "🏛️ ⚪ belum resmi"

    lines.append(
        f"   🚦 {stage_text} | {official_text}"
    )

    if item.get("next_milestone"):
        lines.append(
            "   ⏭ "
            + html.escape(
                item["next_milestone"]
            )
        )

    nearest = item.get("nearest")

    if nearest:
        days, _key, parsed, label = nearest

        countdown = (
            "HARI INI"
            if days == 0
            else f"H-{days}"
        )

        lines.append(
            "   ⏰ "
            + html.escape(countdown)
            + " "
            + html.escape(label)
            + " — "
            + html.escape(
                _watchboard_format_date(parsed)
            )
        )

    baseline_icon = (
        "✅"
        if item.get("baseline_synced")
        else "⏳"
    )

    lines.append(
        "   🛡️ Baseline: "
        + baseline_icon
        + " "
        + html.escape(
            str(item.get("baseline") or "UNKNOWN")
        )
        + " | 🕒 "
        + html.escape(
            str(item.get("last_seen") or "-")
        )
    )

    return lines


def format_watchboard(
    core: Any,
    state: dict[str, Any],
    mode: str = "ALL",
) -> list[str]:
    if not SMART_WATCH_DASHBOARD_ENABLED:
        return [
            "📊 Smart Watch Dashboard sedang OFF."
        ]

    watchlist = state.get("watchlist") or {}

    if (
        not isinstance(watchlist, dict)
        or not watchlist
    ):
        return [
            (
                "📊 <b>V6.6.2 SMART WATCH BOARD</b>\n\n"
                "Belum ada ticker dipantau.\n"
                "Gunakan <code>/watch DOOH HIGH</code>."
            )
        ]

    scanner_state = (
        _watchboard_load_scanner_state()
    )

    items = []

    for raw_ticker, raw_entry in watchlist.items():
        ticker = _valid_watch_ticker(
            raw_ticker
        )

        if not ticker:
            continue

        items.append(
            _watchboard_item(
                core,
                state,
                scanner_state,
                ticker,
                raw_entry,
            )
        )

    items.sort(
        key=lambda item: item["sort_key"],
        reverse=True,
    )

    requested_mode = str(
        mode or "ALL"
    ).upper().strip()

    valid_modes = {
        "ALL",
        "HIGH",
        "WATCH",
        "NORMAL",
        "DUE",
        "PENDING",
    }

    if requested_mode not in valid_modes:
        return [
            (
                "Format: <code>/watchboard "
                "[ALL|HIGH|WATCH|NORMAL|DUE|PENDING]</code>"
            )
        ]

    filtered = _watchboard_filter(
        items,
        requested_mode,
    )

    counts = {
        priority: sum(
            1
            for item in items
            if item["priority"] == priority
        )
        for priority in WATCH_PRIORITIES
    }

    official_count = sum(
        1
        for item in items
        if item.get("official")
    )
    synced_count = sum(
        1
        for item in items
        if item.get("baseline_synced")
    )
    due_count = sum(
        1
        for item in items
        if (
            item.get("nearest")
            and 0
            <= item["nearest"][0]
            <= WATCHBOARD_DUE_DAYS
        )
    )

    header = [
        "📊 <b>V6.6.2 SMART WATCH BOARD</b>",
        (
            f"Dipantau: <b>{len(items)}</b> ticker"
            f" | 🔥 {counts.get('HIGH', 0)}"
            f" | 👀 {counts.get('WATCH', 0)}"
            f" | ℹ️ {counts.get('NORMAL', 0)}"
        ),
        (
            f"🏛️ Official: <b>{official_count}/{len(items)}</b>"
            f" | ⏰ Due ≤{WATCHBOARD_DUE_DAYS}d: <b>{due_count}</b>"
            f" | 🛡️ Synced: <b>{synced_count}/{len(items)}</b>"
        ),
        f"Filter: <b>{html.escape(requested_mode)}</b>",
        "",
    ]

    if not filtered:
        return [
            "\n".join(
                header
                + [
                    "Tidak ada ticker yang cocok dengan filter ini.",
                    "",
                    "Filter: <code>/watchboard ALL|HIGH|WATCH|NORMAL|DUE|PENDING</code>",
                ]
            )
        ]

    chunks = []
    current_lines = list(header)
    item_count = 0

    for index, item in enumerate(filtered, start=1):
        block = [
            f"<b>{index}.</b>"
        ] + _watchboard_item_lines(item)

        block_len = sum(
            len(line) + 1
            for line in block
        )
        current_len = sum(
            len(line) + 1
            for line in current_lines
        )

        if (
            item_count >= WATCHBOARD_ITEMS_PER_MESSAGE
            or current_len + block_len > 3450
        ):
            current_lines += [
                "",
                "💡 Detail: <code>/timeline TICKER</code> | <code>/analyze TICKER</code>",
            ]
            chunks.append(
                "\n".join(current_lines)
            )
            current_lines = [
                "📊 <b>V6.6.2 SMART WATCH BOARD — lanjutan</b>",
                f"Filter: <b>{html.escape(requested_mode)}</b>",
                "",
            ]
            item_count = 0

        current_lines.extend(block)
        current_lines.append("")
        item_count += 1

    current_lines += [
        "💡 Filter: <code>/watchboard HIGH</code> | <code>DUE</code> | <code>PENDING</code>",
        "🔎 Detail: <code>/timeline TICKER</code> | <code>/analyze TICKER</code>",
        "⚠️ Dashboard adalah monitoring corporate action, bukan rekomendasi beli/jual.",
    ]

    chunks.append(
        "\n".join(current_lines)
    )

    return [
        chunk[:3900]
        for chunk in chunks
    ]


# ============================================================
# V6.6.1 LIFECYCLE HISTORY / TIMELINE
# ============================================================

def _lifecycle_key(snapshot: dict[str, Any]) -> str:
    ticker = str(snapshot.get("ticker") or "UNKNOWN").upper()
    family = str(snapshot.get("family") or "CORPORATE ACTION").upper()
    return f"{ticker}|{family}"


def _lifecycle_signature(snapshot: dict[str, Any]) -> str:
    """Material details only; transient cache/signal changes are noise."""
    payload = {
        "stage": snapshot.get("stage"),
        "schedule": snapshot.get("schedule") or {},
        "official_authority": snapshot.get("official_authority"),
        "official_kind": snapshot.get("official_kind"),
        "stake": snapshot.get("stake") or [],
        "money": snapshot.get("money") or [],
        "ratio": snapshot.get("ratio"),
        "execution_price": snapshot.get("execution_price"),
        "tender_price": snapshot.get("tender_price"),
        "price_range": snapshot.get("price_range"),
        "share_count": snapshot.get("share_count"),
    }

    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def record_lifecycle_snapshot(
    state: dict[str, Any],
    snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    if not snapshot or not snapshot.get("ticker"):
        return {
            "changed": False,
            "history": [],
            "previous": None,
            "current": snapshot,
            "change_type": "NONE",
            "history_appended": False,
        }

    memory = state.setdefault(
        "lifecycle_history",
        {},
    )
    key = _lifecycle_key(snapshot)
    history, compacted_rows = (
        compact_lifecycle_history(
            memory.get(key)
        )
    )

    current = dict(snapshot)
    now_utc = utc_iso()
    current["observed_utc"] = now_utc
    current["stage_started_utc"] = now_utc
    current["last_seen_utc"] = now_utc
    current["signature"] = (
        _lifecycle_signature(current)
    )

    previous = (
        dict(history[-1])
        if history
        else None
    )

    if not previous:
        current["detail_update_count"] = 0
        history.append(current)
        memory[key] = history[
            -LIFECYCLE_HISTORY_MAX:
        ]
        return {
            "changed": True,
            "history": memory[key],
            "previous": None,
            "current": current,
            "change_type": "NEW",
            "history_appended": True,
            "compacted_rows": compacted_rows,
        }

    if (
        TIMELINE_NOISE_GUARD_ENABLED
        and _same_lifecycle_stage(
            previous,
            current,
        )
    ):
        previous_signature = (
            previous.get("signature")
            or _lifecycle_signature(previous)
        )

        merged = _merge_stage_snapshot(
            previous,
            current,
        )
        merged["signature"] = (
            _lifecycle_signature(merged)
        )

        material_changed = (
            previous_signature
            != current["signature"]
        )

        if material_changed:
            merged["last_detail_update_utc"] = (
                now_utc
            )
            merged["detail_update_count"] = (
                int(
                    previous.get(
                        "detail_update_count",
                        0,
                    )
                    or 0
                )
                + 1
            )
            change_type = "DETAIL_UPDATED"
        else:
            merged["detail_update_count"] = int(
                previous.get(
                    "detail_update_count",
                    0,
                )
                or 0
            )
            if previous.get(
                "last_detail_update_utc"
            ):
                merged[
                    "last_detail_update_utc"
                ] = previous.get(
                    "last_detail_update_utc"
                )
            change_type = "UNCHANGED"

        history[-1] = merged
        memory[key] = history[
            -LIFECYCLE_HISTORY_MAX:
        ]

        return {
            "changed": material_changed,
            "history": memory[key],
            "previous": previous,
            "current": merged,
            "change_type": change_type,
            "history_appended": False,
            "compacted_rows": compacted_rows,
        }

    old_step = int(
        previous.get("stage_step", 0)
        or 0
    )
    new_step = int(
        current.get("stage_step", 0)
        or 0
    )

    if new_step > old_step:
        change_type = "STAGE_ADVANCED"
    elif new_step < old_step:
        change_type = "STAGE_RECLASSIFIED"
    else:
        change_type = "STAGE_CHANGED"

    current["detail_update_count"] = 0
    history.append(current)
    memory[key] = history[
        -LIFECYCLE_HISTORY_MAX:
    ]

    return {
        "changed": True,
        "history": memory[key],
        "previous": previous,
        "current": current,
        "change_type": change_type,
        "history_appended": True,
        "compacted_rows": compacted_rows,
    }


def _timeline_change_text(
    previous: dict[str, Any] | None,
    current: dict[str, Any],
    change_type: str,
) -> list[str]:
    if not previous:
        return [
            "🆕 <b>Baseline lifecycle dibuat.</b>"
        ]

    lines = []

    if previous.get("stage") != current.get("stage"):
        lines.append(
            "🔄 <b>Perubahan tahap:</b> "
            + html.escape(
                str(previous.get("stage") or "-")
            )
            + " → "
            + html.escape(
                str(current.get("stage") or "-")
            )
        )

    old_schedule = (
        previous.get("schedule") or {}
    )
    new_schedule = (
        current.get("schedule") or {}
    )

    new_dates = [
        (key, value)
        for key, value in new_schedule.items()
        if (
            value
            and old_schedule.get(key) != value
        )
    ]

    if new_dates:
        lines.append(
            f"📅 <b>Update jadwal:</b> "
            f"{len(new_dates)} milestone baru/berubah"
        )

    if (
        previous.get("official_authority")
        != current.get("official_authority")
        and current.get("official_authority")
    ):
        lines.append(
            "🏛️ <b>Official confirmation:</b> "
            + html.escape(
                str(current.get("official_authority"))
            )
        )

    if (
        change_type == "DETAIL_UPDATED"
        and not lines
    ):
        lines.append(
            "🧩 <b>Detail event diperbarui tanpa perubahan tahap.</b>"
        )

    if change_type == "UNCHANGED":
        lines.append(
            "✅ <b>Tidak ada perubahan tahap material.</b>"
        )

    if not lines:
        lines.append(
            "✅ <b>Tidak ada perubahan tahap material.</b>"
        )

    return lines


def format_lifecycle_timeline(
    core: Any,
    snapshot: dict[str, Any],
    result: dict[str, Any],
) -> str:
    current = (
        result.get("current")
        or snapshot
    )

    ticker = html.escape(
        str(current.get("ticker") or "-")
    )
    issuer = html.escape(
        str(current.get("issuer") or "-")
    )
    family = html.escape(
        str(current.get("family") or "-")
    )
    stage = html.escape(
        str(current.get("stage") or "-")
    )
    next_milestone = html.escape(
        str(
            current.get(
                "next_milestone"
            )
            or "-"
        )
    )
    step = int(
        current.get("stage_step", 1)
        or 1
    )
    total = int(
        current.get("stage_total", 1)
        or 1
    )

    lines = [
        f"🧭 <b>V6.6.2 EVENT TIMELINE — {ticker}</b>",
        "",
        f"🏢 <b>Issuer:</b> {issuer}",
        f"🏷 <b>Event:</b> {family}",
        f"🚦 <b>Tahap sekarang:</b> {stage} ({step}/{total})",
        f"⏭ <b>Milestone berikutnya:</b> {next_milestone}",
    ]

    authority = current.get(
        "official_authority"
    )

    if authority:
        cache_mark = (
            " 💾"
            if current.get("official_cached")
            else ""
        )
        lines.append(
            "🏛️ <b>Official:</b> ✅ "
            + html.escape(str(authority))
            + " — "
            + html.escape(
                str(
                    current.get(
                        "official_kind"
                    )
                    or "PRIMARY"
                )
            )
            + cache_mark
        )
    else:
        lines.append(
            "🏛️ <b>Official:</b> ⚪ belum terhubung"
        )

    signal = current.get("signal")
    if signal:
        lines.append(
            "🎛 <b>Monitoring:</b> "
            + html.escape(str(signal))
        )

    if current.get("last_seen_utc"):
        lines.append(
            "🕒 <b>Terakhir dipantau:</b> "
            + html.escape(
                format_timeline_local_time(
                    current.get(
                        "last_seen_utc"
                    )
                )
            )
        )

    schedule = (
        current.get("schedule") or {}
    )
    if schedule:
        lines += [
            "",
            "📅 <b>Jadwal yang terdeteksi:</b>",
        ]
        labels = getattr(
            core,
            "LIFECYCLE_SCHEDULE_LABELS",
            {},
        )

        for key, value in list(
            schedule.items()
        )[:8]:
            label = labels.get(
                key,
                key,
            )
            lines.append(
                "• "
                + html.escape(str(label))
                + ": "
                + html.escape(str(value))
            )

    lines += [
        "",
        "🧠 <b>Update sejak pemeriksaan sebelumnya:</b>",
    ]
    lines.extend(
        _timeline_change_text(
            result.get("previous"),
            current,
            str(
                result.get(
                    "change_type"
                )
                or ""
            ),
        )
    )

    compacted_rows = int(
        result.get("compacted_rows", 0)
        or 0
    )
    if compacted_rows:
        lines.append(
            "🧹 <b>Noise Guard:</b> "
            f"{compacted_rows} snapshot tahap duplikat dirapikan."
        )

    detail_count = int(
        current.get(
            "detail_update_count",
            0,
        )
        or 0
    )
    detail_time = current.get(
        "last_detail_update_utc"
    )

    if detail_count and detail_time:
        lines.append(
            "🧩 <b>Detail update:</b> "
            f"{detail_count}x dalam tahap ini; terakhir "
            + html.escape(
                format_timeline_local_time(
                    detail_time
                )
            )
        )

    history = result.get("history") or []

    if history:
        lines += [
            "",
            "🗂 <b>Riwayat tahap:</b>",
        ]

        for item in history[
            -LIFECYCLE_TIMELINE_MAX_DISPLAY:
        ]:
            stage_time = (
                item.get(
                    "stage_started_utc"
                )
                or item.get(
                    "observed_utc"
                )
            )
            lines.append(
                "• "
                + html.escape(
                    format_timeline_local_time(
                        stage_time
                    )
                )
                + " — "
                + html.escape(
                    str(
                        item.get(
                            "stage"
                        )
                        or "-"
                    )
                )
            )

    lines += [
        "",
        "🛡️ Noise Guard: riwayat hanya bertambah ketika tahap lifecycle berubah.",
        "🕒 Waktu timeline: WIB (Asia/Jakarta).",
        "💡 Timeline tersimpan di <code>state/command_state.json</code>.",
        "⚠️ Lifecycle adalah alat monitoring corporate action, bukan rekomendasi beli/jual.",
    ]

    return "\n".join(lines)[:3900]


async def send_lifecycle_timeline(
    core: Any,
    chat_id: int,
    ticker: str,
    state: dict[str, Any],
) -> dict[str, Any] | None:
    ticker = str(ticker or "").upper().strip()

    if not re.fullmatch(r"[A-Z]{4}", ticker):
        await core.send_message(
            chat_id,
            "Gunakan /timeline TICKER — contoh /timeline DOOH",
        )
        return None

    prepared = await core.prepare_ticker_analysis(
        ticker,
        use_deep=getattr(core, "TIMELINE_DEEP_ENABLED", True),
    )
    article = prepared.get("article")

    if not article:
        await core.send_message(
            chat_id,
            (
                f"Belum ada lifecycle corporate action {ticker} "
                f"yang dapat direcover dalam {core.RECENT_DAYS} hari terakhir."
            ),
        )
        return None

    snapshot = core.lifecycle_snapshot(article)
    result = record_lifecycle_snapshot(state, snapshot)

    await core.send_message(
        chat_id,
        format_lifecycle_timeline(core, snapshot, result),
    )
    return snapshot


def _decision_family(event_type: str) -> str:
    event = (event_type or "").upper()
    if event == "IPO":
        return "IPO"
    if event == "RIGHTS ISSUE":
        return "RIGHTS"
    return "M&A"


def _title_signature(title: str) -> str:
    stop = {
        "SAHAM", "EMITEN", "AKUISISI", "TENDER", "OFFER", "RIGHTS",
        "ISSUE", "HMETD", "IPO", "PENAWARAN", "PERUSAHAAN", "RESMI",
        "BAKAL", "AKAN", "INI", "DAN", "DI", "KE", "DARI", "UNTUK",
        "THE", "OF", "A", "AN", "TO",
    }
    words = [
        x for x in re.findall(r"[A-Z0-9]{2,}", (title or "").upper())
        if x not in stop
    ]
    return " ".join(words[:7])


def decision_event_key(article: dict[str, Any]) -> str:
    d = article.get("details") or {}
    family = _decision_family(article.get("event_type", ""))
    ticker = _resolved_ticker(article)

    # For listed Indonesian issuers, ticker is the most stable event identity.
    # M&A stages (acquisition -> change of control -> tender offer) are therefore
    # intentionally merged into a single corporate-action event.
    if ticker:
        return f"{family}|TICKER|{ticker}"

    target = _norm_identity(d.get("target"))
    acquirer = _norm_identity(d.get("acquirer"))
    if target or acquirer:
        return f"{family}|PARTIES|{acquirer}|{target}"

    return f"{family}|TITLE|{_title_signature(article.get('title', ''))}"


def group_decision_events(
    articles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}

    for article in articles[:DECISION_SCAN_LIMIT]:
        if article.get("context") == "MARKET PIPELINE":
            continue

        key = decision_event_key(article)
        group = groups.get(key)

        if group is None:
            groups[key] = {
                "key": key,
                "representative": article,
                "articles": [article],
            }
            continue

        group["articles"].append(article)

        current = group["representative"]
        current_rank = (
            {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(
                current.get("urgency", current.get("priority", "LOW")), 0
            ),
            current.get("information_score", current.get("ca_score", 0)) or 0,
            current.get("ca_score", 0) or 0,
            current.get("published_dt") or datetime.min.replace(tzinfo=timezone.utc),
        )
        candidate_rank = (
            {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(
                article.get("urgency", article.get("priority", "LOW")), 0
            ),
            article.get("information_score", article.get("ca_score", 0)) or 0,
            article.get("ca_score", 0) or 0,
            article.get("published_dt") or datetime.min.replace(tzinfo=timezone.utc),
        )

        if candidate_rank > current_rank:
            group["representative"] = article

    return list(groups.values())



def _article_official_rank(article: dict[str, Any]) -> int:
    try:
        return int(article.get("official_rank", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _group_official_reference(group: dict[str, Any]) -> dict[str, Any] | None:
    refs = []

    for article in group.get("articles") or []:
        rank = _article_official_rank(article)

        if rank > 0:
            refs.append({
                "authority": article.get("official_source"),
                "kind": article.get("official_kind"),
                "rank": rank,
                "url": article.get("source_url") or article.get("link"),
                "published_dt": article.get("published_dt"),
                "cached": False,
            })

        cached_ref = article.get("verified_official_ref")

        if isinstance(cached_ref, dict):
            refs.append({
                "authority": cached_ref.get("authority"),
                "kind": cached_ref.get("kind") or "PRIMARY",
                "rank": 3,
                "url": cached_ref.get("url"),
                "published_dt": article.get("published_dt"),
                "cached": True,
                "last_verified_utc": cached_ref.get("last_verified_utc"),
            })

    if not refs:
        return None

    refs.sort(
        key=lambda x: (
            x.get("rank", 0),
            0 if x.get("cached") else 1,
            x.get("published_dt")
            or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )

    return refs[0]


def _signal_icon(signal: str) -> str:
    return {
        "HIGH ATTENTION": "🔥",
        "WATCH": "👀",
        "IGNORE": "⚪",
    }.get((signal or "").upper(), "🔎")


def _clean_entity_label(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip(" -–—|,:;")
    if not text:
        return ""

    if re.fullmatch(r"[\d.,%+\- ]+", text):
        return ""

    return text[:36] + ("…" if len(text) > 36 else "")


def _clean_title_label(title: str) -> str:
    text = re.sub(r"\s+", " ", str(title or "")).strip()
    text = re.sub(
        r"\s+-\s+[A-Za-z0-9_.-]+\.(?:com|co\.id|id|net|org)\s*$",
        "",
        text,
        flags=re.I,
    )
    return text[:46] + ("…" if len(text) > 46 else "")


def _article_label(article: dict[str, Any]) -> str:
    d = article.get("details") or {}
    ticker = _resolved_ticker(article)
    if ticker:
        return ticker

    target = _clean_entity_label(d.get("target"))
    if target:
        return target

    acquirer = _clean_entity_label(d.get("acquirer"))
    if acquirer:
        return acquirer

    return _clean_title_label(
        article.get("title") or "Corporate Action"
    )


def format_compact_decision_board(
    groups: list[dict[str, Any]],
    *,
    scanned_articles: int,
) -> str:
    if not groups:
        return "Belum ada event aktif untuk Decision Board."

    signal_rank = {
        "HIGH ATTENTION": 3,
        "WATCH": 2,
        "IGNORE": 1,
    }

    groups = sorted(
        groups,
        key=lambda g: (
            1 if _group_official_reference(g) else 0,
            (_group_official_reference(g) or {}).get("rank", 0),
            signal_rank.get(
                (g["representative"].get("monitoring_signal") or "").upper(), 0
            ),
            g["representative"].get(
                "information_score",
                g["representative"].get("ca_score", 0),
            ) or 0,
            g["representative"].get("ca_score", 0) or 0,
        ),
        reverse=True,
    )

    selected = groups[:DECISION_MAX_EVENTS]
    collapsed = max(0, scanned_articles - len(groups))

    lines = [
        "🧠 <b>V6.6.2 DECISION BOARD — LIFECYCLE + OFFICIAL</b>",
        "<i>Event-level deduplication aktif; urutan untuk triase monitoring, bukan rekomendasi investasi.</i>",
        "",
        f"🧹 <b>Dedup:</b> {scanned_articles} artikel → {len(groups)} event unik"
        + (f" ({collapsed} artikel digabung)" if collapsed else ""),
        f"📌 <b>Ditampilkan:</b> Top {len(selected)} event",
        "",
    ]

    for idx, group in enumerate(selected, start=1):
        article = group["representative"]
        d = article.get("details") or {}
        signal = (article.get("monitoring_signal") or "WATCH").upper()
        score = article.get(
            "information_score",
            article.get("ca_score", 0),
        ) or 0
        event = article.get("event_type") or "CORPORATE ACTION"
        stage = article.get("stage") or "-"
        catalyst = article.get("catalyst") or "NEUTRAL"
        source = article.get("source") or "Unknown"
        related = len(group.get("articles") or [])
        label = _article_label(article)
        ticker = _resolved_ticker(article)
        link = article.get("source_url") or article.get("link") or ""

        lines.append(
            f"{idx}. {_signal_icon(signal)} <b>{html.escape(label)} — "
            f"{html.escape(event)}</b>"
        )
        lines.append(
            f"   Signal: <b>{html.escape(signal)}</b> | Score: <b>{score}/100</b>"
        )
        lines.append(
            f"   Status: {html.escape(str(stage))} | Catalyst: "
            f"{html.escape(str(catalyst))}"
        )
        lines.append(
            f"   Sumber terbaik: {html.escape(str(source))} | "
            f"Related news: {related}"
        )

        official_ref = _group_official_reference(group)
        if official_ref:
            authority = html.escape(
                str(official_ref.get("authority") or "OFFICIAL")
            )
            kind = html.escape(
                str(official_ref.get("kind") or "PRIMARY")
            )
            cache_mark = " 💾" if official_ref.get("cached") else ""
            lines.append(
                f"   🏛️ Official: ✅ {authority} — {kind}{cache_mark}"
            )
        else:
            lines.append(
                "   🏛️ Official: ⚪ belum ditemukan"
            )

        actions: list[str] = []
        if ticker:
            actions.append(f"<code>/analyze {html.escape(ticker)}</code>")
            actions.append(f"<code>/official {html.escape(ticker)}</code>")
        if link:
            actions.append(
                f'<a href="{html.escape(str(link), quote=True)}">Buka sumber</a>'
            )
        if actions:
            lines.append("   🔎 " + " | ".join(actions))

        lines.append("")

    lines += [
        "🛡️ <b>Reliability Guard:</b> retry HTTP aktif; official tervalidasi disimpan ke command_state dan dipakai jika live feed sementara kosong.",
        "💡 Gunakan <code>/analyze TICKER</code> untuk detail dan <code>/timeline TICKER</code> untuk riwayat tahap.",
        "♻️ Berita berbeda yang membahas corporate action sama tidak lagi dikirim sebagai kartu terpisah di /decision.",
    ]

    # Telegram limit is 4096 chars.
    # Keep complete HTML lines so tags are never cut in half.
    safe_lines: list[str] = []
    used = 0

    for line in lines:
        addition = len(line) + 1

        if used + addition > 3850:
            safe_lines.append(
                "… output dipersingkat agar format Telegram tetap valid."
            )
            break

        safe_lines.append(line)
        used += addition

    return "\n".join(safe_lines).strip()


def _pre_decision_group_rank(group: dict[str, Any]) -> tuple:
    article = group["representative"]
    urgency_rank = {
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    official_ref = _group_official_reference(group)

    return (
        1 if official_ref else 0,
        (official_ref or {}).get("rank", 0),
        urgency_rank.get(
            article.get("urgency", article.get("priority", "LOW")),
            0,
        ),
        article.get(
            "information_score",
            article.get("ca_score", 0),
        ) or 0,
        article.get("ca_score", 0) or 0,
        article.get("published_dt")
        or datetime.min.replace(tzinfo=timezone.utc),
    )


async def send_compact_decision_board(
    core: Any,
    chat_id: int,
) -> None:
    articles = await core.fetch_all_articles()
    active_articles = [
        x for x in articles[:DECISION_SCAN_LIMIT]
        if x.get("context") != "MARKET PIPELINE"
    ]

    if not active_articles:
        await core.send_message(
            chat_id,
            "Belum ada event aktif untuk Decision Board.",
        )
        return []

    # Clean tickers before grouping so garbage such as "34"
    # can never become an event identity.
    for article in active_articles:
        _resolved_ticker(article)

    groups = group_decision_events(active_articles)
    groups.sort(
        key=_pre_decision_group_rank,
        reverse=True,
    )

    # Only final Top-N receives cheap snippet-based decision enrichment.
    # Deep extraction and market lookup are intentionally deferred to /analyze.
    candidates = groups[:DECISION_MAX_EVENTS]

    for group in candidates:
        article = group["representative"]

        try:
            if DECISION_FAST_MODE:
                await core.enrich_decision_support(
                    article,
                    use_market=False,
                    use_deep=False,
                )
            else:
                await core.enrich_decision_support(
                    article,
                    use_market=True,
                    use_deep=False,
                )
        except Exception as exc:
            print(
                "Decision enrichment skipped:",
                type(exc).__name__,
            )

    await core.send_message(
        chat_id,
        format_compact_decision_board(
            groups,
            scanned_articles=len(active_articles),
        ),
    )

    return [
        group["representative"]
        for group in candidates
        if group.get("representative")
    ]


def first_baseline(
    state: dict[str, Any],
    chat_ids: set[int],
) -> None:
    """
    Establish a clean Telegram command baseline.

    Telegram supports a negative offset to start from the end of the queue.
    We intentionally discard commands that existed before V6.1 activation
    so old /analyze or /status messages are not replayed.
    """
    latest = get_updates(
        offset=-1,
        limit=1,
    )

    if latest:
        latest_id = int(
            latest[-1].get("update_id", -1)
        )
        state["next_offset"] = max(
            0,
            latest_id + 1,
        )
    else:
        state["next_offset"] = 0

    state["initialized"] = True
    state["last_state_change_utc"] = utc_iso()

    save_state(state)

    notice = (
        "✅ <b>Kabar Saham V6.6.2.1 Command Bridge aktif.</b>\n\n"
        "Command cloud sudah terhubung.\n"
        "Berita/command lama sebelum aktivasi tidak diproses ulang.\n\n"
        "Coba kirim:\n"
        "• /cloudstatus\n"
        "• /market BBCA\n"
        "• /analyze CBRE\n"
        "• /watch DOOH HIGH\n"
        "• /watchlist\n"
        "• /timeline DOOH\n"
        "• /decision\n\n"
        "⏱ Respons mengikuti interval Command Bridge "
        "di cron-job.org."
    )

    for chat_id in sorted(chat_ids):
        try:
            send_message_stdlib(
                chat_id,
                notice,
            )
        except Exception:
            # Baseline itself remains valid even if one ready notice fails.
            pass


def probe(
    github_output: str | None = None,
) -> None:
    chat_ids = authorized_chat_ids()
    state = load_state()

    PENDING_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    PENDING_PATH.write_text(
        "[]\n",
        encoding="utf-8",
    )

    if not state.get("initialized"):
        first_baseline(
            state,
            chat_ids,
        )
        write_github_output(
            github_output,
            has_commands=False,
            command_count=0,
            baseline_initialized=True,
            state_changed=True,
        )
        print(
            "V6.6.1 command baseline initialized."
        )
        return

    offset = int(
        state.get("next_offset", 0)
    )

    updates = get_updates(
        offset=offset,
    )

    if not updates:
        scanner_synced = int(
            state.get("_scanner_lifecycle_synced", 0) or 0
        )
        if scanner_synced:
            state["last_state_change_utc"] = utc_iso()
            save_state(state)

        write_github_output(
            github_output,
            has_commands=False,
            command_count=0,
            baseline_initialized=False,
            state_changed=bool(scanner_synced),
        )
        print(
            "No Telegram updates. "
            f"Scanner lifecycle synced: {scanner_synced}."
        )
        return

    pending: list[dict[str, Any]] = []
    highest_next_offset = offset
    now_ts = int(time.time())

    recent = cleanup_recent_commands(
        state.get("recent_commands", {}),
        now_ts=now_ts,
    )

    duplicates_by_chat: dict[int, list[str]] = {}
    duplicates_count = 0

    for update in updates:
        update_id = update.get("update_id")

        try:
            update_id = int(update_id)
        except (TypeError, ValueError):
            continue

        highest_next_offset = max(
            highest_next_offset,
            update_id + 1,
        )

        chat_id, text = message_info(update)

        if (
            chat_id not in chat_ids
            or not command_name(text)
        ):
            continue

        canonical = canonical_command_text(text)
        fingerprint = command_fingerprint(
            chat_id,
            canonical,
        )
        sent_ts = update_timestamp(update)

        previous_ts = recent.get(fingerprint)
        is_duplicate = False

        if (
            COMMAND_DEDUP_SECONDS > 0
            and previous_ts is not None
        ):
            delta = max(
                0,
                sent_ts - int(previous_ts),
            )
            if delta <= COMMAND_DEDUP_SECONDS:
                is_duplicate = True

        if is_duplicate:
            duplicates_by_chat.setdefault(
                chat_id,
                [],
            ).append(canonical)
            duplicates_count += 1
            continue

        # Register immediately so repeated copies in the SAME polling batch
        # are also suppressed.
        recent[fingerprint] = sent_ts
        pending.append(update)

    state["next_offset"] = highest_next_offset
    state["updates_seen"] = int(
        state.get("updates_seen", 0)
    ) + len(updates)
    state["recent_commands"] = recent
    state["duplicates_suppressed"] = int(
        state.get("duplicates_suppressed", 0)
    ) + duplicates_count
    state["last_state_change_utc"] = utc_iso()
    state["schema_version"] = SCHEMA_VERSION

    # Saved locally now; GitHub commit happens after command execution.
    save_state(state)

    PENDING_PATH.write_text(
        json.dumps(
            pending,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    # Duplicate notice is lightweight and does not require full dependencies.
    for chat_id, duplicate_commands in duplicates_by_chat.items():
        try:
            send_message_stdlib(
                chat_id,
                format_duplicate_notice(
                    duplicate_commands
                ),
            )
        except Exception as exc:
            print(
                "Duplicate notice failed:",
                type(exc).__name__,
            )

    write_github_output(
        github_output,
        has_commands=bool(pending),
        command_count=len(pending),
        baseline_initialized=False,
        state_changed=True,
    )

    print(
        f"Telegram updates: {len(updates)}; "
        f"accepted commands: {len(pending)}; "
        f"duplicates suppressed: {duplicates_count}."
    )


def v662_lightweight_core_presence_check() -> dict[str, bool]:
    """
    Lightweight V6.6.2 probe for mode:test.

    IMPORTANT:
    command_bridge mode:test intentionally runs BEFORE the workflow installs
    the full intelligence dependencies. Therefore it must NOT import
    core/main.py here.

    The full behavioral regression test remains in scan_once.py / core/main.py.
    This probe only confirms that the checked-out core contains the V6.6.2
    guard implementation expected by the bridge.
    """
    core_path = ROOT / "core" / "main.py"

    if not core_path.exists():
        return {
            "core_file": False,
            "entity_role_guard": False,
            "indonesia_guard": False,
            "regression_selftest": False,
        }

    try:
        source = core_path.read_text(
            encoding="utf-8"
        )
    except Exception:
        return {
            "core_file": False,
            "entity_role_guard": False,
            "indonesia_guard": False,
            "regression_selftest": False,
        }

    checks = {
        "core_file": True,
        "entity_role_guard": (
            "def apply_entity_role_guard(" in source
            and "ENTITY_ROLE_GUARD_ENABLED" in source
            and "LOW_CONFIDENCE_ROLE_SUPPRESSION_ENABLED" in source
        ),
        "indonesia_guard": (
            "def apply_indonesia_classification_guard(" in source
            and "INDONESIA_CLASSIFICATION_GUARD_ENABLED" in source
        ),
        "regression_selftest": (
            "def v662_integrity_selftest(" in source
            and "Sinyal Haji Isam Serius Ingin Akuisisi BYAN" in source
        ),
    }

    return checks


def test_bridge() -> None:
    chat_ids = authorized_chat_ids()

    native_result = install_native_telegram_menu(
        verify=True,
    )

    presence = v662_lightweight_core_presence_check()

    if not all(presence.values()):
        missing = [
            key
            for key, ok in presence.items()
            if not ok
        ]
        raise RuntimeError(
            "V6.6.2 core guard presence check gagal: "
            + ", ".join(missing)
        )

    text = (
        "✅ <b>Kabar Saham V6.6.2.1 — COMMAND BRIDGE HOTFIX TEST OK</b>\n\n"
        "GitHub Secrets dan Telegram Bot API berhasil dibaca.\n"
        f"Native Commands: ✅ {int(native_result.get('commands', 0) or 0)} command\n"
        "Menu Button: ✅ COMMANDS\n"
        "Native Menu Verification: ✅ PASS\n"
        "Entity Role Guard Core: ✅ PRESENT\n"
        "Indonesia Classification Guard Core: ✅ PRESENT\n"
        "BYAN Regression Self-test: ✅ PRESENT\n\n"
        "ℹ️ Full guard behavior diuji oleh Auto Scanner/core test, "
        "bukan lightweight Command Bridge probe."
    )

    delivered = 0

    for chat_id in sorted(chat_ids):
        send_message_stdlib(
            chat_id,
            text,
        )
        delivered += 1

    print(
        f"V6.1 test delivered to {delivered} chat(s)."
    )


# ---------------------------------------------------------------------
# Full command execution: imported only when a command actually exists.
# ---------------------------------------------------------------------

HELP_V61 = """
<b>☁️ Kabar Saham V6.6.1 — Event Lifecycle & Timeline</b>

Perintah cloud:
/cloudstatus — status bridge cloud
/status — status intelligence core
/decision — Decision Board Official Priority
/menu — Control Center
/syncmenu — sinkronkan Native Telegram Menu
/health — System Health Monitor
/today — milestone corporate action hari ini
/recent — perubahan lifecycle terbaru
/news24h — berita corporate action 24 jam terakhir
/watch TICKER [HIGH|WATCH|NORMAL] — tambah/ubah Smart Watchlist
/unwatch TICKER — hapus dari Smart Watchlist
/watchlist — lihat ticker yang dipantau
/watchboard [FILTER] — dashboard semua Smart Watch
/timeline TICKER — lifecycle & riwayat corporate action
/official TICKER — cek sumber resmi IDX/e-IPO/KSEI/OJK
/analyze TICKER — analisis corporate action
/deep TICKER — deep article extraction
/market TICKER — harga pasar terakhir
/publisherdebug TICKER — debug Publisher Direct
/resolve TICKER — resolver diagnostics
/decode TICKER — Google News decoder
/protocoldebug TICKER — dynamic protocol debug
/decoderdebug TICKER — decoder parser debug
/latest — corporate action terbaru
/today — berita 24 jam terakhir
/high — Urgency HIGH
/active — event aktif
/actionable — IPO ACTIONABLE
/pipeline — IPO PIPELINE
/ma — M&A / takeover
/ipo — IPO
/rights — Rights Issue / HMETD
/help — bantuan

Auto-alert V6.0 tetap berjalan terpisah setiap 10 menit.
Command V6.1 diproses saat cron Command Bridge menjalankan GitHub Actions.
""".strip()


async def dispatch_core_command(
    core: Any,
    update: dict[str, Any],
    state: dict[str, Any] | None = None,
) -> None:
    message = update.get("message") or {}
    chat = message.get("chat") or {}

    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return

    try:
        chat_id = int(chat_id)
    except (TypeError, ValueError):
        return

    parts = text.split()
    command = parts[0].split("@")[0].lower()
    args = parts[1:]

    if command == "/start":
        try:
            install_native_telegram_menu(
                verify=False,
            )
        except Exception as exc:
            print(
                "Native menu refresh on /start failed:",
                type(exc).__name__,
            )

        await core.send_message(
            chat_id,
            "✅ <b>Kabar Saham V6.6.2.1 Cloud aktif.</b>\n\n"
            "Auto-alert V6.0 dan Interactive Command Bridge V6.1 "
            "sudah terpisah dari laptop.\n\n"
            + HELP_V61,
        )
        return

    if command == "/help":
        await core.send_message(
            chat_id,
            HELP_V61,
        )
        return

    if command == "/cloudstatus":
        await core.send_message(
            chat_id,
            "☁️ <b>Kabar Saham V6.6.2 Cloud Status</b>\n\n"
            "Auto Alert V6.0: ✅ ACTIVE\n"
            "Interactive Command Bridge: ✅ ACTIVE\n"
            "Anti-Duplicate: ✅ ON (±3 menit)\n"
            "Compact Decision Board: ✅ ON\n"
            "Decision FAST Mode: ✅ ON\n"
            "Ticker Guard: ✅ STRICT 4-LETTER\n"
            "Official Source Priority: "
            f"{'✅ ON' if getattr(core, 'OFFICIAL_SOURCE_PRIORITY_ENABLED', False) else '❌ OFF'}\n"
            "Official Discovery: "
            f"{'✅ ON' if getattr(core, 'OFFICIAL_DISCOVERY_ENABLED', False) else '❌ OFF'}\n"
            "Ticker Recovery: "
            f"{'✅ ON' if getattr(core, 'TICKER_RECOVERY_ENABLED', False) else '❌ OFF'}\n"
            "Issuer Resolver: "
            f"{'✅ ON' if getattr(core, 'ISSUER_ALIAS_PROPAGATION_ENABLED', False) else '❌ OFF'}\n"
            "Deep Issuer Resolver: "
            f"{'✅ ON' if getattr(core, 'DEEP_ISSUER_RESOLVER_ENABLED', False) else '❌ OFF'}\n"
            "Multi-Source Issuer: "
            f"{'✅ ON' if getattr(core, 'MULTI_SOURCE_ISSUER_RESOLVER_ENABLED', False) else '❌ OFF'}\n"
            "Market Issuer Lookup: "
            f"{'✅ ON' if getattr(core, 'MARKET_ISSUER_LOOKUP_ENABLED', False) else '❌ OFF'}\n"
            "Related Issuer Discovery: "
            f"{'✅ ON' if getattr(core, 'RELATED_ISSUER_DISCOVERY_ENABLED', False) else '❌ OFF'}\n"
            "Official Triangulation: "
            f"{'✅ ON' if getattr(core, 'OFFICIAL_ISSUER_TRIANGULATION_ENABLED', False) else '❌ OFF'}\n"
            "Verified Official Cache: "
            f"{'✅ ON' if getattr(core, 'VERIFIED_OFFICIAL_CACHE_ENABLED', False) else '❌ OFF'}\n"
            "HTTP Retry: "
            f"✅ {getattr(core, 'HTTP_RETRY_ATTEMPTS', 1)}x\n"
            "Telegram Retry: "
            f"✅ {getattr(core, 'TELEGRAM_RETRY_ATTEMPTS', 1)}x\n"
            "Verified Cache Memory: ✅ command_state\n"
            "Event Lifecycle: "
            f"{'✅ ON' if getattr(core, 'EVENT_LIFECYCLE_ENABLED', False) else '❌ OFF'}\n"
            "Timeline Command: ✅ /timeline TICKER\n"
            "Timeline Memory: ✅ command_state\n"
            "Timeline Noise Guard: ✅ ON\n"
            "Stage History: ✅ STAGE-ONLY\n"
            "Timeline Timezone: ✅ WIB (Asia/Jakarta)\n"
            "Smart Watchlist: ✅ ON\n"
            f"Watchlist Tickers: ✅ {len((state or {}).get('watchlist', {})) if state is not None else 0}\n"
            "Watchlist Memory: ✅ command_state\n"
            "Lifecycle Auto Alert: ✅ scanner\n"
            "Milestone Alert: ✅ H-7/H-3/H-1/HARI INI\n"
            "Smart Alert State: ✅ github_state\n"
            "First-Scan Baseline Guard: ✅ ON\n"
            "Stake Dedup Guard: ✅ ON\n"
            "Entity Role Guard: "
            f"{'✅ ON' if getattr(core, 'ENTITY_ROLE_GUARD_ENABLED', False) else '❌ OFF'}\n"
            "Low-Confidence Role Suppression: "
            f"{'✅ ON' if getattr(core, 'LOW_CONFIDENCE_ROLE_SUPPRESSION_ENABLED', False) else '❌ OFF'}\n"
            "Indonesia Classification Guard: "
            f"{'✅ ON' if getattr(core, 'INDONESIA_CLASSIFICATION_GUARD_ENABLED', False) else '❌ OFF'}\n"
            "Smart Watch Dashboard: ✅ /watchboard\n"
            "Control Center: ✅ /menu\n"
            f"Native Telegram Menu: {'✅ ON' if NATIVE_TELEGRAM_MENU_ENABLED else '❌ OFF'}\n"
            f"Native Commands: ✅ {len(TELEGRAM_NATIVE_COMMANDS)}\n"
            "Menu Button Type: ✅ COMMANDS\n"
            "Health Monitor: ✅ /health\n"
            "Today / Recent: ✅ /today + /recent\n"
            "News 24h Alias: ✅ /news24h\n"
            "Dashboard Source: ✅ command_state + github_state\n"
            "Dashboard Network: ✅ CACHE-FAST / NO LIVE FETCH\n"
            "Money Unit Guard: "
            f"{'✅ ON' if getattr(core, 'MONEY_UNIT_GUARD_ENABLED', False) else '❌ OFF'}\n"
            "Issuer Memory: ✅ command_state\n"
            "Runtime: GitHub Actions\n"
            "Timer: cron-job.org\n"
            "Laptop required: ❌ NO\n"
            "VPS required: ❌ NO\n"
            "Intelligence core: V5.4 Publisher Direct\n"
            "Market Data: "
            f"{'✅ ON' if core.MARKET_DATA_ENABLED and core.YFINANCE_AVAILABLE else '❌ OFF'}\n"
            "Deep Extraction: "
            f"{'✅ ON' if core.DEEP_EXTRACTION_ENABLED and core.BS4_AVAILABLE else '❌ OFF'}\n"
            "Publisher Direct: "
            f"{'✅ ON' if core.PUBLISHER_DIRECT_ENABLED else '❌ OFF'}\n\n"
            "⏱ Command diproses pada interval cron Command Bridge.",
        )
        return

    if command == "/status":
        await core.send_message(
            chat_id,
            "🟢 <b>Bot aktif — V6.6.2 Cloud / V5.4 Intelligence Core</b>\n"
            "Auto Alert: cron-job.org → GitHub Actions\n"
            "Command Bridge: cron-job.org → GitHub Actions\n"
            "Anti-Duplicate: ON (default ±180 detik)\n"
            "Decision Board: FAST + CLEAN + EVENT DEDUP\n"
            "Ticker Guard: STRICT 4-LETTER + TITLE FALLBACK\n"
            f"Official Source Priority: {'ON' if getattr(core, 'OFFICIAL_SOURCE_PRIORITY_ENABLED', False) else 'OFF'}\n"
            f"Official Discovery: {'ON' if getattr(core, 'OFFICIAL_DISCOVERY_ENABLED', False) else 'OFF'}\n"
            f"Ticker Recovery: {'ON' if getattr(core, 'TICKER_RECOVERY_ENABLED', False) else 'OFF'}\n"
            f"Issuer Resolver: {'ON' if getattr(core, 'ISSUER_ALIAS_PROPAGATION_ENABLED', False) else 'OFF'}\n"
            f"Manual search: {core.RECENT_DAYS} hari terakhir\n"
            f"Auto alert freshness: {core.AUTO_ALERT_HOURS} jam\n"
            f"Minimum priority: {core.AUTO_ALERT_MIN_PRIORITY}\n"
            f"Market data: {'ON' if core.MARKET_DATA_ENABLED and core.YFINANCE_AVAILABLE else 'OFF'}\n"
            f"Deep extraction: {'ON' if core.DEEP_EXTRACTION_ENABLED and core.BS4_AVAILABLE else 'OFF'}\n"
            f"Source resolver: {'ON' if core.SOURCE_RESOLVER_ENABLED else 'OFF'}\n"
            f"Google decoder: {'ON' if core.GOOGLE_DECODER_ENABLED else 'OFF'}\n"
            f"Publisher Direct: {'ON' if core.PUBLISHER_DIRECT_ENABLED else 'OFF'}\n"
            f"Query aktif: {len(core.CONFIG.get('queries', []))}",
        )
        return

    heavy = {
        "/decision",
        "/timeline",
        "/official",
        "/analyze",
        "/deep",
        "/resolve",
        "/decode",
        "/decoderdebug",
        "/protocoldebug",
        "/publisherdebug",
    }

    if command in heavy:
        await core.send_message(
            chat_id,
            f"⏳ <b>V6.6.2 memproses {command}</b>…",
        )

    if command == "/latest":
        await core.send_message(
            chat_id,
            "🔎 Mencari corporate action terbaru…",
        )
        await core.send_filtered(chat_id)

    elif command == "/menu":
        if state is None:
            await core.send_message(
                chat_id,
                "Control Center state belum tersedia pada run ini.",
            )
        else:
            await core.send_message(
                chat_id,
                format_control_center(
                    core,
                    state,
                ),
            )

    elif command == "/syncmenu":
        try:
            native_result = install_native_telegram_menu(
                verify=True,
            )
            await core.send_message(
                chat_id,
                native_menu_status_text(
                    native_result
                ),
            )
        except Exception as exc:
            await core.send_message(
                chat_id,
                "❌ <b>Native Telegram Menu gagal disinkronkan.</b>\n"
                f"Error: {html.escape(type(exc).__name__)}",
            )

    elif command == "/health":
        if state is None:
            await core.send_message(
                chat_id,
                "Health state belum tersedia pada run ini.",
            )
        else:
            await core.send_message(
                chat_id,
                format_system_health(
                    core,
                    state,
                ),
            )

    elif command == "/today":
        if state is None:
            await core.send_message(
                chat_id,
                "Today state belum tersedia pada run ini.",
            )
        else:
            await core.send_message(
                chat_id,
                format_today_summary(
                    core,
                    state,
                ),
            )

    elif command == "/recent":
        if state is None:
            await core.send_message(
                chat_id,
                "Recent state belum tersedia pada run ini.",
            )
        else:
            await core.send_message(
                chat_id,
                format_recent_summary(
                    state
                ),
            )

    elif command == "/news24h":
        await core.send_message(
            chat_id,
            "🕒 Mencari berita corporate action 24 jam terakhir…",
        )
        await core.send_filtered(
            chat_id,
            today_only=True,
        )

    elif command == "/high":
        await core.send_message(
            chat_id,
            "🔴 Mencari corporate action Urgency HIGH…",
        )
        await core.send_filtered(
            chat_id,
            high_only=True,
        )

    elif command == "/active":
        await core.send_message(
            chat_id,
            "🟢 Mencari corporate action ACTIVE terbaru…",
        )
        await core.send_filtered(
            chat_id,
            active_only=True,
        )

    elif command == "/actionable":
        await core.send_message(
            chat_id,
            "🔥 Mencari IPO ACTIONABLE terbaru…",
        )
        await core.send_filtered(
            chat_id,
            ipo_class="ACTIONABLE",
        )

    elif command == "/pipeline":
        await core.send_message(
            chat_id,
            "📰 Mencari IPO PIPELINE terbaru…",
        )
        await core.send_filtered(
            chat_id,
            ipo_class="PIPELINE",
        )

    elif command == "/watch":
        if state is None:
            await core.send_message(
                chat_id,
                "Watchlist state belum tersedia pada run ini.",
            )
        elif not args:
            await core.send_message(
                chat_id,
                "Gunakan /watch TICKER [HIGH|WATCH|NORMAL] — contoh /watch DOOH HIGH",
            )
        else:
            priority = args[1] if len(args) > 1 else "WATCH"
            entry, changed, error = upsert_watchlist_entry(
                state,
                args[0],
                priority,
            )
            if error:
                await core.send_message(chat_id, "⚠️ " + html.escape(error))
            else:
                priority_value = str(entry.get("priority") or "WATCH")
                icon = {"HIGH": "🔥", "WATCH": "👀", "NORMAL": "ℹ️"}.get(priority_value, "👀")
                issuer = str(entry.get("issuer") or "").strip()
                stage = str(entry.get("last_known_stage") or "").strip()
                lines = [
                    f"{icon} <b>SMART WATCH — {html.escape(entry['ticker'])}</b>",
                    f"Priority: <b>{priority_value}</b>",
                    "Status: ✅ " + ("ditambahkan/diperbarui" if changed else "sudah aktif"),
                ]
                if issuer:
                    lines.append("🏢 Issuer: " + html.escape(issuer))
                if stage:
                    lines.append("🚦 Baseline stage: " + html.escape(stage))
                lines += [
                    "",
                    "Scanner akan memantau perubahan stage, official confirmation, jadwal material, dan milestone sesuai priority.",
                    "🛡️ First scanner pass: baseline sync only — alert lama tidak dikirim.",
                    f"💡 Cek: <code>/timeline {html.escape(entry['ticker'])}</code>",
                ]
                await core.send_message(chat_id, "\n".join(lines))

    elif command == "/unwatch":
        if state is None:
            await core.send_message(chat_id, "Watchlist state belum tersedia pada run ini.")
        elif not args:
            await core.send_message(chat_id, "Gunakan /unwatch TICKER — contoh /unwatch DOOH")
        else:
            ticker = _valid_watch_ticker(args[0])
            if not ticker:
                await core.send_message(chat_id, "Ticker harus 4 huruf.")
            elif remove_watchlist_entry(state, ticker):
                await core.send_message(
                    chat_id,
                    f"✅ <b>{ticker}</b> dihapus dari Smart Watchlist.\nLifecycle/issuer memory lama tetap disimpan.",
                )
            else:
                await core.send_message(chat_id, f"ℹ️ <b>{ticker}</b> tidak ada di Smart Watchlist.")

    elif command == "/watchlist":
        if state is None:
            await core.send_message(chat_id, "Watchlist state belum tersedia pada run ini.")
        else:
            await core.send_message(chat_id, format_watchlist(state))

    elif command == "/watchboard":
        if state is None:
            await core.send_message(
                chat_id,
                "Watchboard state belum tersedia pada run ini.",
            )
        else:
            mode = args[0] if args else "ALL"
            for board_message in format_watchboard(
                core,
                state,
                mode,
            ):
                await core.send_message(
                    chat_id,
                    board_message,
                )

    elif command == "/decision":
        decision_articles = await send_compact_decision_board(
            core,
            chat_id,
        )
        if state is not None:
            for decision_article in decision_articles or []:
                try:
                    record_lifecycle_snapshot(
                        state,
                        core.lifecycle_snapshot(decision_article),
                    )
                except Exception:
                    pass

    elif command == "/timeline":
        if not args:
            await core.send_message(
                chat_id,
                "Gunakan /timeline TICKER — contoh /timeline DOOH",
            )
        elif state is None:
            await core.send_message(
                chat_id,
                "Timeline state belum tersedia pada run ini.",
            )
        else:
            await send_lifecycle_timeline(
                core,
                chat_id,
                args[0],
                state,
            )

    elif command == "/official":
        if not args:
            await core.send_message(
                chat_id,
                "Gunakan /official TICKER — contoh /official DOOH",
            )
        else:
            await core.official_ticker(
                chat_id,
                args[0],
            )

    elif command == "/market":
        if not args:
            await core.send_message(
                chat_id,
                "Gunakan /market TICKER — contoh /market BBCA",
            )
        else:
            await core.send_market_quote(
                chat_id,
                args[0],
            )

    elif command in {"/analyze", "/deep"}:
        if not args:
            await core.send_message(
                chat_id,
                f"Gunakan {command} TICKER — contoh {command} CBRE",
            )
        else:
            analyzed_article = await core.analyze_ticker(
                chat_id,
                args[0],
            )
            if state is not None and analyzed_article:
                try:
                    record_lifecycle_snapshot(
                        state,
                        core.lifecycle_snapshot(analyzed_article),
                    )
                except Exception:
                    pass

    elif command == "/resolve":
        if not args:
            await core.send_message(
                chat_id,
                "Gunakan /resolve TICKER — contoh /resolve CBRE",
            )
        else:
            await core.resolve_ticker_source(
                chat_id,
                args[0],
            )

    elif command == "/decode":
        if not args:
            await core.send_message(
                chat_id,
                "Gunakan /decode TICKER — contoh /decode CBRE",
            )
        else:
            await core.decode_ticker_google_url(
                chat_id,
                args[0],
            )

    elif command == "/decoderdebug":
        if not args:
            await core.send_message(
                chat_id,
                "Gunakan /decoderdebug TICKER — contoh /decoderdebug CBRE",
            )
        else:
            await core.decoder_debug_ticker(
                chat_id,
                args[0],
            )

    elif command == "/protocoldebug":
        if not args:
            await core.send_message(
                chat_id,
                "Gunakan /protocoldebug TICKER — contoh /protocoldebug CBRE",
            )
        else:
            await core.protocol_debug_ticker(
                chat_id,
                args[0],
            )

    elif command == "/publisherdebug":
        if not args:
            await core.send_message(
                chat_id,
                "Gunakan /publisherdebug TICKER — contoh /publisherdebug CBRE",
            )
        else:
            await core.publisher_debug_ticker(
                chat_id,
                args[0],
            )

    elif command == "/ma":
        await core.send_message(
            chat_id,
            "🤝 Mencari M&A / takeover terbaru…",
        )
        await core.send_filtered(
            chat_id,
            "MA",
        )

    elif command == "/ipo":
        await core.send_message(
            chat_id,
            "🆕 Mencari IPO valid terbaru…",
        )
        await core.send_filtered(
            chat_id,
            "IPO",
        )

    elif command == "/rights":
        await core.send_message(
            chat_id,
            "📣 Mencari Rights Issue / HMETD terbaru…",
        )
        await core.send_filtered(
            chat_id,
            "RIGHTS",
        )

    else:
        await core.send_message(
            chat_id,
            "❓ Command tidak dikenali.\n\n"
            + HELP_V61,
        )


def hydrate_issuer_memory(core: Any, state: dict[str, Any]) -> int:
    memory = state.get("issuer_aliases") or {}
    count = 0
    register = getattr(core, "register_ticker_aliases", None)
    if not callable(register):
        return 0
    for ticker, aliases in memory.items():
        if not isinstance(aliases, list):
            continue
        try:
            registered = register(ticker, aliases)
            if registered:
                count += 1
        except Exception:
            continue
    return count


def export_issuer_memory(core: Any) -> dict[str, list[str]]:
    cache = getattr(core, "TICKER_ALIAS_CACHE", {}) or {}
    output: dict[str, list[str]] = {}
    for ticker, values in cache.items():
        if not isinstance(values, dict):
            continue
        aliases = []
        seen = set()
        for item in values.values():
            if not isinstance(item, dict):
                continue
            alias = str(item.get("alias") or "").strip()
            key = re.sub(r"\s+", " ", alias).lower()
            if alias and key not in seen:
                seen.add(key)
                aliases.append(alias)
        if aliases:
            output[str(ticker).upper()] = aliases[:8]
    return output


def hydrate_verified_official_memory(
    core: Any,
    state: dict[str, Any],
) -> int:
    hydrate = getattr(
        core,
        "hydrate_verified_official_cache",
        None,
    )

    if not callable(hydrate):
        return 0

    try:
        return int(
            hydrate(
                state.get("verified_official") or {}
            )
            or 0
        )
    except Exception:
        return 0


def export_verified_official_memory(
    core: Any,
) -> dict[str, Any]:
    export = getattr(
        core,
        "export_verified_official_cache",
        None,
    )

    if not callable(export):
        return {}

    try:
        data = export()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


async def execute_pending() -> None:
    if not PENDING_PATH.exists():
        print("No pending command file.")
        return

    try:
        pending = json.loads(
            PENDING_PATH.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        raise RuntimeError(
            f"Pending command JSON invalid: {exc}"
        ) from exc

    if not pending:
        print("No pending commands.")
        return

    chat_ids = authorized_chat_ids()

    # Lazy import: full dependencies are only needed when a real command exists.
    core_dir = ROOT / "core"
    sys.path.insert(
        0,
        str(core_dir),
    )

    import main as core  # type: ignore  # noqa: E402

    state = load_state()
    hydrated_aliases = hydrate_issuer_memory(core, state)
    if hydrated_aliases:
        print(f"Issuer memory hydrated: {hydrated_aliases} ticker(s).")

    hydrated_official = hydrate_verified_official_memory(
        core,
        state,
    )

    if hydrated_official:
        print(
            f"Verified official cache hydrated: "
            f"{hydrated_official} ticker(s)."
        )

    processed = 0

    for update in pending:
        chat_id, text = message_info(update)

        if (
            chat_id not in chat_ids
            or not command_name(text)
        ):
            continue

        try:
            await dispatch_core_command(
                core,
                update,
                state,
            )
        except Exception as exc:
            # A command-level failure is reported to Telegram and then the
            # update is considered handled. The user can explicitly retry.
            try:
                await core.send_message(
                    chat_id,
                    "⚠️ <b>Command V6.1 gagal diproses.</b>\n"
                    f"Jenis error: {type(exc).__name__}\n"
                    "Silakan coba command yang sama pada poll berikutnya.",
                )
            except Exception:
                pass

            print(
                "Command processing error:",
                type(exc).__name__,
            )

        processed += 1

    if processed:
        state["commands_processed"] = int(
            state.get("commands_processed", 0)
        ) + processed
        state["last_command_utc"] = utc_iso()
        state["last_state_change_utc"] = utc_iso()
        state["issuer_aliases"] = export_issuer_memory(core)
        state["verified_official"] = export_verified_official_memory(core)
        save_state(state)

    print(
        f"Commands processed: {processed}."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=[
            "probe",
            "execute",
            "test",
        ],
        required=True,
    )
    parser.add_argument(
        "--github-output",
        default=None,
    )

    args = parser.parse_args()

    if args.mode == "probe":
        probe(
            github_output=args.github_output,
        )
        return

    if args.mode == "test":
        test_bridge()
        write_github_output(
            args.github_output,
            has_commands=False,
            command_count=0,
            state_changed=False,
        )
        return

    asyncio.run(
        execute_pending()
    )


if __name__ == "__main__":
    main()
