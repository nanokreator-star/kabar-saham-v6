"""
Kabar Saham V6.6 — Event Lifecycle & Corporate Action Timeline.

V5.4 remains the intelligence core.
This runner performs one scan cycle, sends new alerts, persists only
article hashes/timestamps, then exits.
"""

import argparse
import asyncio
import json
import html
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORE_DIR = ROOT / "core"
STATE_PATH = Path(
    os.getenv(
        "V6_STATE_PATH",
        str(ROOT / "state" / "github_state.json"),
    )
)
COMMAND_STATE_PATH = Path(
    os.getenv(
        "V61_COMMAND_STATE_PATH",
        str(ROOT / "state" / "command_state.json"),
    )
)

# main.py expects config path relative to CWD unless explicitly set.
os.environ.setdefault(
    "CONFIG_PATH",
    str(ROOT / "config.json"),
)

# SQLite is only a local compatibility fallback in V6.
# GitHub persistence uses state/github_state.json instead.
os.environ.setdefault(
    "DB_PATH",
    str(ROOT / "runtime_v6.db"),
)

sys.path.insert(0, str(CORE_DIR))
import main as core  # noqa: E402


SCHEMA_VERSION = 3
STATE_RETENTION_DAYS = int(
    os.getenv("V6_STATE_RETENTION_DAYS", "60")
)
STATE_MAX_KEYS = int(
    os.getenv("V6_STATE_MAX_KEYS", "5000")
)
KEEPALIVE_DAYS = int(
    os.getenv("V6_KEEPALIVE_DAYS", "14")
)
FIRST_RUN_MODE = (
    os.getenv("V6_FIRST_RUN_MODE", "BASELINE")
    .strip()
    .upper()
)
SEND_BASELINE_NOTICE = (
    os.getenv("V6_SEND_BASELINE_NOTICE", "1") == "1"
)


# ============================================================
# V6.6 — Smart Watchlist & Milestone Alert
# ============================================================
SMART_WATCHLIST_ENABLED = (
    os.getenv("V64_SMART_WATCHLIST_ENABLED", "1") == "1"
)
SMART_LIFECYCLE_ALERT_ENABLED = (
    os.getenv("V64_SMART_LIFECYCLE_ALERT_ENABLED", "1") == "1"
)
MILESTONE_ALERT_ENABLED = (
    os.getenv("V64_MILESTONE_ALERT_ENABLED", "1") == "1"
)

# V6.6 — first-scan baseline guard + stable material normalization.
SMART_WATCH_BASELINE_GUARD_ENABLED = (
    os.getenv("V641_SMART_WATCH_BASELINE_GUARD_ENABLED", "1") == "1"
)
STAKE_DEDUP_GUARD_ENABLED = (
    os.getenv("V641_STAKE_DEDUP_GUARD_ENABLED", "1") == "1"
)
WATCHLIST_MAX_TICKERS = max(
    1,
    min(50, int(os.getenv("V64_WATCHLIST_MAX_TICKERS", "20"))),
)
WATCH_PRIORITY_LEVELS = {"HIGH", "WATCH", "NORMAL"}
WATCH_PRIORITY_MILESTONES = {
    "HIGH": {7, 3, 1, 0},
    "WATCH": {3, 1, 0},
    "NORMAL": {1, 0},
}
WIB = timezone(timedelta(hours=7))
MONTH_MAP = {
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
MONTH_NAMES_ID = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "Mei", 6: "Jun",
    7: "Jul", 8: "Agu", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Des",
}



def load_command_state():
    if not COMMAND_STATE_PATH.exists():
        return {}
    try:
        data = json.loads(
            COMMAND_STATE_PATH.read_text(encoding="utf-8")
        )
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def normalize_watchlist(command_state):
    raw = command_state.get("watchlist") or {}
    if not isinstance(raw, dict):
        return {}

    output = {}
    for raw_ticker, raw_entry in list(raw.items())[:WATCHLIST_MAX_TICKERS]:
        ticker = str(raw_ticker or "").upper().strip()
        if not re.fullmatch(r"[A-Z]{4}", ticker):
            continue
        entry = raw_entry if isinstance(raw_entry, dict) else {}
        priority = str(entry.get("priority") or "WATCH").upper().strip()
        if priority not in WATCH_PRIORITY_LEVELS:
            priority = "WATCH"
        clean = dict(entry)
        clean["ticker"] = ticker
        clean["priority"] = priority
        output[ticker] = clean
    return output


def hydrate_issuer_memory_from_command_state(command_state=None):
    data = command_state if isinstance(command_state, dict) else load_command_state()

    count = 0
    memory = data.get("issuer_aliases") or {}
    register = getattr(core, "register_ticker_aliases", None)

    if isinstance(memory, dict) and callable(register):
        for ticker, aliases in memory.items():
            if not isinstance(aliases, list):
                continue
            try:
                if register(ticker, aliases):
                    count += 1
            except Exception:
                continue

    hydrate_official = getattr(
        core,
        "hydrate_verified_official_cache",
        None,
    )
    verified = data.get("verified_official") or {}

    if callable(hydrate_official) and isinstance(verified, dict):
        try:
            official_count = int(hydrate_official(verified) or 0)
            if official_count:
                print(
                    "Verified official cache hydrated from command_state: "
                    f"{official_count} ticker(s)."
                )
        except Exception:
            pass

    return count


def utc_now():
    return datetime.now(timezone.utc)


def utc_iso():
    return utc_now().isoformat()


def parse_iso(value):
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )
        return parsed.astimezone(
            timezone.utc
        )
    except Exception:
        return None


def default_state():
    return {
        "schema_version": SCHEMA_VERSION,
        "baseline_initialized": False,
        "last_state_change_utc": None,
        "last_keepalive_utc": None,
        "sent": {},
        "watch_lifecycle": {},
        "watch_baseline_tokens": {},
        "milestone_alerts": {},
    }


def load_state():
    if not STATE_PATH.exists():
        return default_state()

    try:
        data = json.loads(
            STATE_PATH.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        # Fail safe: do not silently treat corrupt state as empty
        # because that could resend many alerts.
        raise RuntimeError(
            f"State file rusak/tidak valid: {STATE_PATH}"
        )

    if not isinstance(
        data.get("sent"),
        dict,
    ):
        raise RuntimeError(
            "State field 'sent' tidak valid."
        )

    data.setdefault(
        "schema_version",
        SCHEMA_VERSION,
    )
    data.setdefault(
        "baseline_initialized",
        False,
    )
    data.setdefault(
        "last_state_change_utc",
        None,
    )
    data.setdefault(
        "last_keepalive_utc",
        None,
    )
    if not isinstance(data.get("watch_lifecycle"), dict):
        data["watch_lifecycle"] = {}
    if not isinstance(data.get("watch_baseline_tokens"), dict):
        data["watch_baseline_tokens"] = {}
    if not isinstance(data.get("milestone_alerts"), dict):
        data["milestone_alerts"] = {}

    # Transparent V6.6 state cleanup: normalize old duplicate stake/money.
    normalized_watch = {}
    for lifecycle_key, raw_snapshot in data["watch_lifecycle"].items():
        if isinstance(raw_snapshot, dict):
            normalized_watch[str(lifecycle_key)] = _normalize_watch_snapshot(
                raw_snapshot
            )
    data["watch_lifecycle"] = normalized_watch
    data["schema_version"] = SCHEMA_VERSION

    return data


def save_state(state):
    STATE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp = STATE_PATH.with_suffix(
        ".tmp"
    )

    temp.write_text(
        json.dumps(
            state,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    temp.replace(STATE_PATH)


def prune_state(state):
    sent = state.get("sent", {})
    cutoff = (
        utc_now()
        - timedelta(
            days=STATE_RETENTION_DAYS
        )
    )

    kept = {}

    for key, value in sent.items():
        dt = parse_iso(value)

        if (
            dt is None
            or dt >= cutoff
        ):
            kept[key] = value

    if len(kept) > STATE_MAX_KEYS:
        ordered = sorted(
            kept.items(),
            key=lambda item: (
                parse_iso(item[1])
                or datetime.min.replace(
                    tzinfo=timezone.utc
                )
            ),
            reverse=True,
        )
        kept = dict(
            ordered[:STATE_MAX_KEYS]
        )

    changed = kept != sent
    state["sent"] = kept

    return changed




# ============================================================
# V6.6 SMART WATCH BASELINE + MATERIAL NORMALIZATION
# ============================================================

def _normalize_material_list(values, *, numeric=False):
    output = []
    seen = set()

    for raw in values or []:
        if raw in (None, ""):
            continue

        if numeric:
            try:
                clean = round(
                    float(
                        str(raw)
                        .replace("%", "")
                        .strip()
                    ),
                    8,
                )
                key = ("num", clean)
            except Exception:
                clean = re.sub(
                    r"\\s+",
                    " ",
                    str(raw),
                ).strip()
                key = (
                    "text",
                    clean.casefold(),
                )
        else:
            if isinstance(raw, (int, float)):
                clean = round(float(raw), 8)
                key = ("num", clean)
            else:
                clean = re.sub(
                    r"\\s+",
                    " ",
                    str(raw),
                ).strip()
                key = (
                    "text",
                    clean.casefold(),
                )

        if key in seen:
            continue

        seen.add(key)
        output.append(clean)

    return output


def _normalize_watch_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        return {}

    clean = dict(snapshot)

    if STAKE_DEDUP_GUARD_ENABLED:
        clean["stake"] = _normalize_material_list(
            clean.get("stake") or [],
            numeric=True,
        )

    clean["money"] = _normalize_material_list(
        clean.get("money") or [],
    )

    schedule = clean.get("schedule")
    if isinstance(schedule, dict):
        clean["schedule"] = {
            str(key): str(value)
            for key, value in schedule.items()
            if value not in (None, "")
        }

    return clean


def _watch_entry_token(entry):
    if not isinstance(entry, dict):
        entry = {}

    return "|".join(
        [
            str(entry.get("added_utc") or ""),
            str(entry.get("updated_utc") or ""),
            str(entry.get("priority") or "WATCH").upper(),
        ]
    )


def _watch_needs_baseline_sync(state, ticker, entry):
    if not SMART_WATCH_BASELINE_GUARD_ENABLED:
        return False

    tokens = state.setdefault(
        "watch_baseline_tokens",
        {},
    )
    current = _watch_entry_token(entry)
    return tokens.get(ticker) != current


def _mark_watch_baseline_synced(state, ticker, entry):
    tokens = state.setdefault(
        "watch_baseline_tokens",
        {},
    )
    token = _watch_entry_token(entry)

    if tokens.get(ticker) == token:
        return False

    tokens[ticker] = token
    return True


# ============================================================
# V6.6 SMART WATCHLIST SCANNER
# ============================================================

def _snapshot_key(snapshot):
    ticker = str(snapshot.get("ticker") or "").upper()
    family = str(snapshot.get("family") or "CORPORATE ACTION").upper()
    return f"{ticker}|{family}"


def _snapshot_ticker(key):
    return str(key or "").split("|", 1)[0].upper()


def command_lifecycle_baselines(command_state, watchlist):
    memory = command_state.get("lifecycle_history") or {}
    if not isinstance(memory, dict):
        return {}
    output = {}
    for key, history in memory.items():
        ticker = _snapshot_ticker(key)
        if ticker not in watchlist:
            continue
        if isinstance(history, list) and history and isinstance(history[-1], dict):
            output[str(key)] = _normalize_watch_snapshot(
                history[-1]
            )
    return output


def sync_watch_state(state, command_state, watchlist):
    changed = False
    memory = state.setdefault("watch_lifecycle", {})
    if not isinstance(memory, dict):
        memory = {}
        state["watch_lifecycle"] = memory
        changed = True

    # Remove scanner baselines for tickers no longer watched.
    stale = [key for key in memory if _snapshot_ticker(key) not in watchlist]
    for key in stale:
        memory.pop(key, None)
        changed = True

    baseline_tokens = state.setdefault(
        "watch_baseline_tokens",
        {},
    )
    stale_tokens = [
        ticker
        for ticker in baseline_tokens
        if ticker not in watchlist
    ]
    for ticker in stale_tokens:
        baseline_tokens.pop(ticker, None)
        changed = True

    # Seed scanner state from richer command lifecycle history when available.
    for key, snapshot in command_lifecycle_baselines(command_state, watchlist).items():
        if key not in memory:
            memory[key] = _normalize_watch_snapshot(
                snapshot
            )
            changed = True
    return changed


def _merge_watch_snapshot(previous, current):
    previous = _normalize_watch_snapshot(
        previous
    )
    current = _normalize_watch_snapshot(
        current
    )

    if not previous:
        merged = dict(current)
        merged["scanner_seen_utc"] = utc_iso()
        return merged

    merged = dict(previous)
    # Preserve cumulative detail if a transient feed has less information.
    for key, value in current.items():
        if value not in (None, "", [], {}):
            merged[key] = value

    old_schedule = dict(previous.get("schedule") or {})
    new_schedule = dict(current.get("schedule") or {})
    for key, value in new_schedule.items():
        if value:
            old_schedule[key] = value
    if old_schedule:
        merged["schedule"] = old_schedule

    if not current.get("official_authority") and previous.get("official_authority"):
        merged["official_authority"] = previous.get("official_authority")
        merged["official_kind"] = previous.get("official_kind")
        merged["official_url"] = previous.get("official_url")
        merged["official_cached"] = previous.get("official_cached", False)

    # Conservative stage guard: old articles may reappear. Never automatically
    # move a watched event backwards in its lifecycle.
    old_step = int(previous.get("stage_step", 0) or 0)
    new_step = int(current.get("stage_step", 0) or 0)
    if old_step and new_step and new_step < old_step:
        for key in ("stage", "stage_step", "stage_total", "next_milestone"):
            merged[key] = previous.get(key)
        merged["stage_regression_ignored"] = True

    merged["scanner_seen_utc"] = utc_iso()
    return _normalize_watch_snapshot(
        merged
    )


def _material_changes(previous, current):
    if not previous:
        return [], set()

    previous = _normalize_watch_snapshot(
        previous
    )
    current = _normalize_watch_snapshot(
        current
    )

    lines = []
    kinds = set()

    if previous.get("stage") != current.get("stage"):
        lines.append(
            "🔄 Stage: "
            + str(previous.get("stage") or "-")
            + " → "
            + str(current.get("stage") or "-")
        )
        kinds.add("stage")

    old_official = str(previous.get("official_authority") or "")
    new_official = str(current.get("official_authority") or "")
    if new_official and new_official != old_official:
        lines.append("🏛️ Official confirmation: " + new_official)
        kinds.add("official")

    old_schedule = previous.get("schedule") or {}
    new_schedule = current.get("schedule") or {}
    labels = getattr(core, "LIFECYCLE_SCHEDULE_LABELS", {})
    for key, value in new_schedule.items():
        if value and old_schedule.get(key) != value:
            label = labels.get(key, key)
            lines.append(f"📅 {label}: {value}")
            kinds.add("schedule")

    field_labels = {
        "tender_price": "Harga tender",
        "execution_price": "Harga pelaksanaan",
        "ratio": "Rasio",
        "share_count": "Jumlah saham",
    }
    for key, label in field_labels.items():
        value = current.get(key)
        if value not in (None, "") and value != previous.get(key):
            lines.append(f"🧩 {label}: {value}")
            kinds.add("detail")

    for key, label in (("money", "Nilai transaksi"), ("stake", "Stake")):
        numeric = key == "stake"
        value = _normalize_material_list(
            current.get(key) or [],
            numeric=numeric,
        )
        old = _normalize_material_list(
            previous.get(key) or [],
            numeric=numeric,
        )

        if value and value != old:
            shown = ", ".join(
                str(x)
                for x in value[:3]
            )
            lines.append(
                f"🧩 {label}: {shown}"
            )
            kinds.add("detail")

    return lines, kinds


def _watch_should_alert(priority, kinds):
    if not kinds:
        return False
    if "stage" in kinds:
        return True
    if priority == "NORMAL":
        return False
    if priority == "WATCH":
        return bool(kinds & {"official", "schedule"})
    # HIGH also surfaces material price/value/stake detail updates.
    return True


def _parse_milestone_date(value):
    text = str(value or "").strip()
    if not text:
        return None

    # 30 Agustus 2026 / 30 Aug 2026
    match = re.search(
        r"(?<!\d)(\d{1,2})\s+([A-Za-z]+)\s+(20\d{2})(?!\d)",
        text,
        flags=re.I,
    )
    if match:
        day = int(match.group(1))
        month = MONTH_MAP.get(match.group(2).lower())
        year = int(match.group(3))
        if month:
            try:
                return datetime(year, month, day, tzinfo=WIB).date()
            except ValueError:
                return None

    # 30/08/2026 or 30-08-2026
    match = re.search(r"(?<!\d)(\d{1,2})[/-](\d{1,2})[/-](20\d{2})(?!\d)", text)
    if match:
        try:
            return datetime(
                int(match.group(3)),
                int(match.group(2)),
                int(match.group(1)),
                tzinfo=WIB,
            ).date()
        except ValueError:
            return None

    return None


def _format_wib_date(date_value):
    return f"{date_value.day:02d} {MONTH_NAMES_ID.get(date_value.month, date_value.month)} {date_value.year}"


def _nearest_milestone(snapshot):
    today = datetime.now(WIB).date()
    labels = getattr(core, "LIFECYCLE_SCHEDULE_LABELS", {})
    candidates = []
    for key, raw in (snapshot.get("schedule") or {}).items():
        parsed = _parse_milestone_date(raw)
        if parsed is None:
            continue
        delta = (parsed - today).days
        if delta < 0:
            continue
        candidates.append((delta, key, parsed, raw, labels.get(key, key)))
    candidates.sort(key=lambda x: x[0])
    return candidates[0] if candidates else None


def _format_smart_change_alert(ticker, entry, previous, current, change_lines):
    priority = str(entry.get("priority") or "WATCH").upper()
    icon = {"HIGH": "🔥", "WATCH": "👀", "NORMAL": "ℹ️"}.get(priority, "👀")
    issuer = str(current.get("issuer") or entry.get("issuer") or "-")
    lines = [
        f"🚨 <b>V6.6 SMART WATCH — {ticker}</b>",
        f"{icon} Priority: <b>{priority}</b>",
        f"🏢 Issuer: {html.escape(issuer)}",
        f"🏷 Event: {html.escape(str(current.get('family') or '-'))}",
        "",
        "🧠 <b>APA YANG BERUBAH?</b>",
    ]
    lines.extend(
        "• " + html.escape(str(line))
        for line in change_lines
    )
    lines += [
        "",
        f"🚦 Sekarang: <b>{html.escape(str(current.get('stage') or '-'))}</b> ({current.get('stage_step') or 1}/{current.get('stage_total') or 1})",
        f"⏭ Next: {html.escape(str(current.get('next_milestone') or '-'))}",
    ]
    nearest = _nearest_milestone(current)
    if nearest:
        delta, _, parsed, _, label = nearest
        when = "HARI INI" if delta == 0 else f"H-{delta}"
        lines.append(
            f"⏰ {when}: {html.escape(str(label))} — {_format_wib_date(parsed)}"
        )
    if current.get("official_authority"):
        lines.append(
            f"🏛️ Official: ✅ {html.escape(str(current.get('official_authority')))} — {html.escape(str(current.get('official_kind') or 'PRIMARY'))}"
        )
    title = str(current.get("title") or "").strip()
    if title:
        lines += ["", "📰 " + html.escape(title[:220])]
    url = str(current.get("source_url") or "").strip()
    if url:
        lines.append(
            f'<a href="{html.escape(url, quote=True)}">🔗 Buka sumber</a>'
        )
    lines += [
        "",
        f"💡 /analyze {ticker} | /timeline {ticker}",
        "⚠️ Smart Watch adalah monitoring event, bukan rekomendasi beli/jual.",
    ]
    return "\n".join(lines)[:3900]


def _format_milestone_alert(ticker, entry, snapshot, key, parsed, days_until):
    priority = str(entry.get("priority") or "WATCH").upper()
    icon = {"HIGH": "🔥", "WATCH": "👀", "NORMAL": "ℹ️"}.get(priority, "👀")
    label = getattr(core, "LIFECYCLE_SCHEDULE_LABELS", {}).get(key, key)
    countdown = "HARI INI" if days_until == 0 else f"H-{days_until}"
    issuer = str(snapshot.get("issuer") or entry.get("issuer") or "-")
    lines = [
        f"⏰ <b>V6.6 MILESTONE ALERT — {ticker}</b>",
        f"{icon} Priority: <b>{priority}</b>",
        f"🏢 Issuer: {html.escape(issuer)}",
        f"🏷 Event: {html.escape(str(snapshot.get('family') or '-'))}",
        "",
        f"📣 <b>{countdown} menuju {html.escape(str(label))}</b>",
        f"📅 Tanggal: <b>{_format_wib_date(parsed)}</b>",
        f"🚦 Stage: {html.escape(str(snapshot.get('stage') or '-'))}",
        f"⏭ Next: {html.escape(str(snapshot.get('next_milestone') or '-'))}",
    ]
    if snapshot.get("official_authority"):
        lines.append(
            f"🏛️ Official: ✅ {html.escape(str(snapshot.get('official_authority')))}"
        )
    lines += [
        "",
        f"💡 /timeline {ticker} | /analyze {ticker}",
        "⚠️ Reminder corporate action, bukan rekomendasi beli/jual.",
    ]
    return "\n".join(lines)[:3900]


def prune_milestone_alerts(state, retention_days=120):
    alerts = state.setdefault("milestone_alerts", {})
    if not isinstance(alerts, dict):
        state["milestone_alerts"] = {}
        return True
    cutoff = utc_now() - timedelta(days=retention_days)
    kept = {}
    for key, value in alerts.items():
        dt = parse_iso(value)
        if dt is None or dt >= cutoff:
            kept[key] = value
    changed = kept != alerts
    state["milestone_alerts"] = kept
    return changed


async def process_smart_watchlist(state, command_state, watchlist, articles, chat_ids):
    if not SMART_WATCHLIST_ENABLED:
        return False, 0, set()

    changed = sync_watch_state(state, command_state, watchlist)
    changed = prune_milestone_alerts(state) or changed
    sent_count = 0
    alerted_tickers = set()
    sent_map = state.setdefault("sent", {})
    lifecycle_memory = state.setdefault("watch_lifecycle", {})

    # Current feed lifecycle changes.
    if SMART_LIFECYCLE_ALERT_ENABLED:
        for ticker, entry in watchlist.items():
            # V6.6: a newly added/updated watch gets ONE baseline-sync pass.
            # This prevents historical differences from firing immediately
            # after /watch. The guard is armed per watch-entry token.
            baseline_sync = _watch_needs_baseline_sync(
                state,
                ticker,
                entry,
            )
            baseline_observed = False

            matches = core.find_ticker_matches(
                articles,
                ticker,
            )
            if not matches:
                continue

            groups = core.group_event_articles(
                matches
            )

            for group in groups:
                article = group.get("primary")
                if not article:
                    continue

                try:
                    core.attach_official_reference(
                        article,
                        group.get("articles", []),
                    )
                    snapshot = _normalize_watch_snapshot(
                        core.lifecycle_snapshot(
                            article
                        )
                    )
                except Exception:
                    continue

                if snapshot.get("ticker") != ticker:
                    continue

                baseline_observed = True
                key = _snapshot_key(snapshot)
                previous = _normalize_watch_snapshot(
                    lifecycle_memory.get(key)
                )
                merged = _merge_watch_snapshot(
                    previous,
                    snapshot,
                )
                change_lines, kinds = _material_changes(
                    previous,
                    merged,
                )
                priority = str(
                    entry.get("priority")
                    or "WATCH"
                ).upper()

                # FIRST-SCAN BASELINE GUARD:
                # Always absorb the current canonical snapshot without alerting.
                if baseline_sync:
                    if previous != merged:
                        lifecycle_memory[key] = merged
                        changed = True

                    # Also mark the same event as known by generic alert state,
                    # preventing a historical generic notification immediately
                    # after the user starts watching this ticker.
                    now_sent = utc_iso()
                    for related in group.get("articles", []):
                        article_key = related.get("key")
                        if (
                            article_key
                            and article_key not in sent_map
                        ):
                            sent_map[article_key] = now_sent
                            changed = True
                    continue

                if not previous:
                    lifecycle_memory[key] = merged
                    changed = True
                    continue

                if _watch_should_alert(
                    priority,
                    kinds,
                ):
                    delivered = await send_to_all(
                        chat_ids,
                        _format_smart_change_alert(
                            ticker,
                            entry,
                            previous,
                            merged,
                            change_lines,
                        ),
                    )

                    if delivered > 0:
                        lifecycle_memory[key] = merged
                        changed = True
                        sent_count += 1
                        alerted_tickers.add(ticker)

                        # Suppress the generic auto-alert for the same event.
                        now_sent = utc_iso()
                        for related in group.get("articles", []):
                            article_key = related.get("key")
                            if article_key:
                                sent_map[
                                    article_key
                                ] = now_sent
                    # Delivery failure keeps old baseline so next scan retries.
                else:
                    # Ignore non-material title/source/monitoring churn.
                    # Persist only real material baseline changes.
                    if kinds and previous != merged:
                        lifecycle_memory[key] = merged
                        changed = True

            if (
                baseline_sync
                and baseline_observed
                and _mark_watch_baseline_synced(
                    state,
                    ticker,
                    entry,
                )
            ):
                print(
                    "Smart Watch baseline synced: "
                    f"{ticker} — first scan suppressed."
                )
                changed = True

    # Milestone reminders use persistent scanner baseline, including data seeded
    # from command_state lifecycle_history. No new article is required.
    if MILESTONE_ALERT_ENABLED:
        milestone_state = state.setdefault("milestone_alerts", {})
        today = datetime.now(WIB).date()
        for ticker, entry in watchlist.items():
            priority = str(entry.get("priority") or "WATCH").upper()
            allowed = WATCH_PRIORITY_MILESTONES.get(priority, {1, 0})
            for lifecycle_key, snapshot in list(lifecycle_memory.items()):
                if _snapshot_ticker(lifecycle_key) != ticker:
                    continue
                for schedule_key, raw_date in (snapshot.get("schedule") or {}).items():
                    parsed = _parse_milestone_date(raw_date)
                    if parsed is None:
                        continue
                    days_until = (parsed - today).days
                    if days_until not in allowed:
                        continue
                    alert_key = (
                        f"{lifecycle_key}|{schedule_key}|{parsed.isoformat()}|D{days_until}"
                    )
                    if alert_key in milestone_state:
                        continue

                    # A smart lifecycle alert already contains the nearest date.
                    # Mark the same-cycle reminder covered to prevent noise.
                    if ticker in alerted_tickers:
                        milestone_state[alert_key] = utc_iso()
                        changed = True
                        continue

                    delivered = await send_to_all(
                        chat_ids,
                        _format_milestone_alert(
                            ticker,
                            entry,
                            snapshot,
                            schedule_key,
                            parsed,
                            days_until,
                        ),
                    )
                    if delivered > 0:
                        milestone_state[alert_key] = utc_iso()
                        changed = True
                        sent_count += 1

    return changed, sent_count, alerted_tickers

def secret_chat_ids():
    """
    GitHub uses TELEGRAM_CHAT_IDS secret:
      123456789
    or:
      123456789,-1001234567890

    For local compatibility, if absent, V5.4 SQLite subscribers
    are used when available.
    """
    raw = (
        os.getenv(
            "TELEGRAM_CHAT_IDS",
            "",
        )
        .strip()
    )

    output = []

    if raw:
        for item in raw.split(","):
            item = item.strip()

            if not item:
                continue

            try:
                output.append(
                    int(item)
                )
            except ValueError:
                raise RuntimeError(
                    "TELEGRAM_CHAT_IDS harus berisi "
                    "angka Chat ID dipisahkan koma."
                )

    if output:
        return list(dict.fromkeys(output))

    # Local migration convenience only.
    try:
        output = [
            int(x)
            for x in core.subscriber_ids()
        ]
    except Exception:
        output = []

    return list(dict.fromkeys(output))


async def send_to_all(
    chat_ids,
    text,
):
    delivered = 0

    for chat_id in chat_ids:
        try:
            await core.send_message(
                chat_id,
                text,
            )
            delivered += 1
        except Exception as exc:
            print(
                "Telegram send error:",
                type(exc).__name__,
            )

    return delivered


def qualifies(article):
    if core.was_sent(article["key"]):
        # Only relevant in local V5 compatibility mode.
        return False

    if not core.is_recent_hours(
        article.get("published_dt")
    ):
        return False

    if not core.priority_meets_minimum(
        article.get(
            "urgency",
            article.get(
                "priority",
                "LOW",
            ),
        ),
        core.AUTO_ALERT_MIN_PRIORITY,
    ):
        return False

    if (
        article.get("event_type")
        == "IPO"
        and article.get("ipo_class")
        == "PIPELINE"
    ):
        return False

    return True


async def baseline_run(
    state,
    articles,
    chat_ids,
):
    now = utc_iso()

    if FIRST_RUN_MODE == "SEND_RECENT":
        state["baseline_initialized"] = True
        state["last_state_change_utc"] = now
        state["last_keepalive_utc"] = now
        return True, False

    # Default and safest: know current feed without sending old news.
    for article in articles:
        state["sent"][
            article["key"]
        ] = now

    state["baseline_initialized"] = True
    state["last_state_change_utc"] = now
    state["last_keepalive_utc"] = now

    if (
        SEND_BASELINE_NOTICE
        and chat_ids
    ):
        notice = (
            "✅ <b>Kabar Saham V6.0 GitHub aktif.</b>\n\n"
            f"Baseline dibuat dari "
            f"{len(articles)} artikel yang sudah ada.\n"
            "Berita lama tidak dikirim ulang.\n\n"
            "Mulai run berikutnya, corporate action baru "
            "yang lolos filter akan dikirim otomatis."
        )

        await send_to_all(
            chat_ids,
            notice,
        )

    print(
        "Baseline initialized:",
        len(articles),
        "articles marked known.",
    )

    return True, True


async def scan():
    state = load_state()
    chat_ids = secret_chat_ids()

    if not chat_ids:
        raise RuntimeError(
            "TELEGRAM_CHAT_IDS belum diisi di GitHub Secret. "
            "Tambahkan minimal satu Chat ID."
        )

    command_state = load_command_state()
    hydrated = hydrate_issuer_memory_from_command_state(command_state)
    if hydrated:
        print(f"Issuer memory hydrated from command_state: {hydrated} ticker(s).")

    watchlist = normalize_watchlist(command_state)
    print(f"Smart Watchlist active: {len(watchlist)} ticker(s).")

    articles = await core.fetch_all_articles()
    print(
        f"Fetched {len(articles)} unique corporate-action articles."
    )

    state_changed = prune_state(
        state
    )

    if not state.get(
        "baseline_initialized"
    ):
        _, baseline_completed = (
            await baseline_run(
                state,
                articles,
                chat_ids,
            )
        )

        # SEND_RECENT mode continues to the normal scan.
        if baseline_completed:
            save_state(state)
            return {
                "fetched": len(articles),
                "eligible": 0,
                "sent": 0,
                "baseline": True,
                "state_changed": True,
            }

    sent_map = state["sent"]

    smart_changed, smart_sent, _ = await process_smart_watchlist(
        state,
        command_state,
        watchlist,
        articles,
        chat_ids,
    )
    if smart_changed:
        state_changed = True
    if smart_sent:
        print(f"Smart Watch alerts delivered: {smart_sent}.")

    raw_candidates = [
        article
        for article in articles
        if (
            article["key"]
            not in sent_map
            and qualifies(article)
        )
    ]

    candidate_keys = {
        article["key"]
        for article in raw_candidates
    }

    # Group ALL currently visible articles so a newly-arrived media story can
    # still inherit an official reference discovered in an older/current feed.
    event_groups = core.group_event_articles(articles)

    eligible_groups = [
        group
        for group in event_groups
        if any(
            article.get("key") in candidate_keys
            for article in group.get("articles", [])
        )
    ]

    eligible_groups.sort(
        key=lambda group: (
            group.get("official_rank", 0),
            core.PRIORITY_RANK.get(
                group["primary"].get(
                    "urgency",
                    group["primary"].get("priority", "LOW"),
                ),
                1,
            ),
            group["primary"].get("ca_score", 0),
            group["primary"].get("published_dt")
            or datetime.min.replace(
                tzinfo=timezone.utc
            ),
        ),
        reverse=True,
    )

    eligible_groups = eligible_groups[
        : core.CONFIG.get(
            "push_limit_per_cycle",
            8,
        )
    ]

    print(
        f"Eligible new event alerts: {len(eligible_groups)} "
        f"from {len(raw_candidates)} article(s)"
    )

    sent_count = 0

    for group in eligible_groups:
        article = group["primary"]

        try:
            core.attach_official_reference(
                article,
                group.get("articles", []),
            )

            await core.enrich_decision_support(
                article
            )

            delivered = await send_to_all(
                chat_ids,
                core.format_alert(article),
            )

            if delivered > 0:
                # Mark every article in the same corporate-action event as
                # known, preventing later media/official duplicates.
                now_sent = utc_iso()

                for related in group.get("articles", []):
                    key = related.get("key")
                    if key:
                        sent_map[key] = now_sent

                state_changed = True
                sent_count += 1
                print(
                    "Event alert delivered:",
                    article.get(
                        "event_type",
                        "UNKNOWN",
                    ),
                    article.get(
                        "details",
                        {},
                    ).get(
                        "ticker",
                        "—",
                    ),
                    "official=",
                    (
                        group.get("official_reference") or {}
                    ).get(
                        "authority",
                        "NONE",
                    ),
                )
            else:
                print(
                    "Alert NOT marked sent; "
                    "Telegram delivery failed."
                )

        except Exception as exc:
            # Do not mark as sent; next scheduled run will retry.
            print(
                "Event processing error:",
                type(exc).__name__,
                str(exc)[:300],
            )

    # Public repositories can have schedules disabled after prolonged
    # repository inactivity. We update a harmless state heartbeat only
    # every KEEPALIVE_DAYS, not every 10 minutes.
    keepalive_dt = parse_iso(
        state.get(
            "last_keepalive_utc"
        )
    )

    if (
        keepalive_dt is None
        or (
            utc_now()
            - keepalive_dt
        )
        >= timedelta(
            days=KEEPALIVE_DAYS
        )
    ):
        state["last_keepalive_utc"] = (
            utc_iso()
        )
        state_changed = True

    if state_changed:
        state["last_state_change_utc"] = (
            utc_iso()
        )
        prune_state(state)
        save_state(state)

    return {
        "fetched": len(articles),
        "eligible": len(eligible_groups),
        "sent": sent_count,
        "smart_sent": smart_sent,
        "watchlist": len(watchlist),
        "baseline": False,
        "state_changed": state_changed,
    }


async def test_telegram():
    chat_ids = secret_chat_ids()

    if not chat_ids:
        raise RuntimeError(
            "TELEGRAM_CHAT_IDS belum tersedia."
        )

    text = (
        "✅ <b>Kabar Saham V6.6 — CONTROL CENTER + HEALTH MONITOR TEST OK</b>\n\n"
        "Token Telegram dan Chat ID berhasil dibaca dari GitHub Secrets.\n"
        "Bot siap menjalankan scanner terjadwal."
    )

    delivered = await send_to_all(
        chat_ids,
        text,
    )

    if delivered != len(chat_ids):
        raise RuntimeError(
            f"Telegram test hanya terkirim ke "
            f"{delivered}/{len(chat_ids)} chat."
        )

    print(
        f"Telegram test delivered to "
        f"{delivered} chat(s)."
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=[
            "scan",
            "test_telegram",
        ],
        default="scan",
    )
    args = parser.parse_args()

    if args.mode == "test_telegram":
        asyncio.run(
            test_telegram()
        )
        return

    result = asyncio.run(scan())

    print(
        "SCAN RESULT:",
        json.dumps(
            result,
            ensure_ascii=False,
        ),
    )


if __name__ == "__main__":
    main()
