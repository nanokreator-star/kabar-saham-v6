"""
Kabar Saham V6.2.1 — Ticker Recovery + Official Priority
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

SCHEMA_VERSION = 5

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
        "recent_commands": {},
        "duplicates_suppressed": 0,
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

    # Transparent schema migration: existing V6.1 command_state.json
    # remains valid and does not need to be replaced manually.
    state["schema_version"] = SCHEMA_VERSION

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
            "User-Agent": "Kabar-Saham-V6.2.1-Ticker-Recovery/1.0",
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
        if rank <= 0:
            continue

        refs.append({
            "authority": article.get("official_source"),
            "kind": article.get("official_kind"),
            "rank": rank,
            "url": article.get("source_url") or article.get("link"),
            "published_dt": article.get("published_dt"),
        })

    if not refs:
        return None

    refs.sort(
        key=lambda x: (
            x.get("rank", 0),
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
        "🧠 <b>V6.2.1 DECISION BOARD — TICKER RECOVERY + OFFICIAL</b>",
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
            lines.append(
                f"   🏛️ Official: ✅ {authority} — {kind}"
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
        "🧩 <b>Ticker Recovery:</b> /analyze mencoba exact ticker → title/snippet → targeted search; issuer-name resolver menghubungkan disclosure resmi yang tidak menulis ticker. Official Priority tetap aktif.",
        "💡 Gunakan <code>/analyze TICKER</code> untuk detail lengkap satu event.",
        "♻️ Berita berbeda yang membahas corporate action sama tidak lagi dikirim sebagai kartu terpisah di /decision.",
    ]

    text = "\n".join(lines).strip()
    # Telegram sendMessage limit is 4096 chars. Keep a safety margin.
    return text[:3900]


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
        return

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

    await core.send_message(
        chat_id,
        format_compact_decision_board(
            groups,
            scanned_articles=len(active_articles),
        ),
    )


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
        "✅ <b>Kabar Saham V6.2.1 Command Bridge aktif.</b>\n\n"
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
            "V6.2.1 command baseline initialized."
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


def test_bridge() -> None:
    chat_ids = authorized_chat_ids()

    text = (
        "✅ <b>Kabar Saham V6.2.1 — TICKER RECOVERY TEST OK</b>\n\n"
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
<b>☁️ Kabar Saham V6.2.1 — Ticker Recovery + Official Priority</b>

Perintah cloud:
/cloudstatus — status bridge cloud
/status — status intelligence core
/decision — Decision Board Official Priority
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
            "✅ <b>Kabar Saham V6.2.1 Cloud aktif.</b>\n\n"
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
            "☁️ <b>Kabar Saham V6.2.1 Cloud Status</b>\n\n"
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
            "🟢 <b>Bot aktif — V6.2.1 Cloud / V5.4 Intelligence Core</b>\n"
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
            f"⏳ <b>V6.2.1 memproses {command}</b>…",
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
        await send_compact_decision_board(
            core,
            chat_id,
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
