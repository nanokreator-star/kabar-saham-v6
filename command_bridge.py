"""
Kabar Saham V6.1 — Interactive Command Bridge
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
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
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

SCHEMA_VERSION = 1


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "initialized": False,
        "next_offset": 0,
        "last_state_change_utc": None,
        "last_command_utc": None,
        "updates_seen": 0,
        "commands_processed": 0,
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

    return state


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE_PATH.with_suffix(".tmp")
    temp.write_text(
        json.dumps(
            state,
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
    """
    Telegram Bot API using Python standard library only.
    This lets idle command polling avoid installing the full bot stack.
    """
    token = require_token()
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
        elif value is not None:
            encoded[key] = str(value)

    body = urllib.parse.urlencode(encoded).encode("utf-8")

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "Kabar-Saham-V6.1-Command-Bridge/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=TG_API_TIMEOUT_SECONDS,
        ) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        body_text = ""
        try:
            body_text = exc.read().decode(
                "utf-8",
                errors="replace",
            )
        except Exception:
            pass

        raise RuntimeError(
            f"Telegram HTTP {exc.code}: "
            f"{body_text[:300]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Telegram network error: {exc.reason}"
        ) from exc

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
        "✅ <b>Kabar Saham V6.1 Command Bridge aktif.</b>\n\n"
        "Command cloud sudah terhubung.\n"
        "Berita/command lama sebelum aktivasi tidak diproses ulang.\n\n"
        "Coba kirim:\n"
        "• /cloudstatus\n"
        "• /market BBCA\n"
        "• /analyze CBRE\n"
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
            "V6.1 command baseline initialized."
        )
        return

    offset = int(
        state.get("next_offset", 0)
    )

    updates = get_updates(
        offset=offset,
    )

    if not updates:
        write_github_output(
            github_output,
            has_commands=False,
            command_count=0,
            baseline_initialized=False,
            state_changed=False,
        )
        print("No Telegram updates.")
        return

    pending: list[dict[str, Any]] = []
    highest_next_offset = offset

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
            chat_id in chat_ids
            and command_name(text)
        ):
            pending.append(update)

    state["next_offset"] = highest_next_offset
    state["updates_seen"] = int(
        state.get("updates_seen", 0)
    ) + len(updates)
    state["last_state_change_utc"] = utc_iso()

    # State is saved in the working tree now but is only committed
    # AFTER command execution succeeds. If a workflow fails before
    # the commit, the repository keeps the old offset and Telegram
    # commands can be retried on the next run.
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

    write_github_output(
        github_output,
        has_commands=bool(pending),
        command_count=len(pending),
        baseline_initialized=False,
        state_changed=True,
    )

    print(
        f"Telegram updates: {len(updates)}; "
        f"authorized commands: {len(pending)}."
    )


def test_bridge() -> None:
    chat_ids = authorized_chat_ids()

    text = (
        "✅ <b>Kabar Saham V6.1 — Command Bridge TEST OK</b>\n\n"
        "GitHub Secrets dan Telegram Bot API berhasil dibaca.\n"
        "Langkah berikutnya: jalankan mode <b>poll</b> "
        "sekali untuk membuat baseline command."
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
<b>☁️ Kabar Saham V6.1 — Interactive Command Bridge</b>

Perintah cloud:
/cloudstatus — status bridge cloud
/status — status intelligence core
/decision — Decision Board
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
        await core.send_message(
            chat_id,
            "✅ <b>Kabar Saham V6.1 Cloud aktif.</b>\n\n"
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
            "☁️ <b>Kabar Saham V6.1 Cloud Status</b>\n\n"
            "Auto Alert V6.0: ✅ ACTIVE\n"
            "Interactive Command Bridge: ✅ ACTIVE\n"
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
            "🟢 <b>Bot aktif — V6.1 Cloud / V5.4 Intelligence Core</b>\n"
            "Auto Alert: cron-job.org → GitHub Actions\n"
            "Command Bridge: cron-job.org → GitHub Actions\n"
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
            f"⏳ <b>V6.1 memproses {command}</b>…",
        )

    if command == "/latest":
        await core.send_message(
            chat_id,
            "🔎 Mencari corporate action terbaru…",
        )
        await core.send_filtered(chat_id)

    elif command == "/today":
        await core.send_message(
            chat_id,
            "🕒 Mencari berita 24 jam terakhir…",
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

    elif command == "/decision":
        await core.send_decision_board(
            chat_id
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
            await core.analyze_ticker(
                chat_id,
                args[0],
            )

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
