"""
Kabar Saham V6.7.5 — Rumor Intelligence & Confirmation Tracker.

V5.4 remains the intelligence core.
This runner performs one scan cycle, sends official and rumor alerts,
persists event/rumor state, then exits.
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
# V6.6.1 — Smart Watchlist & Milestone Alert
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

# V6.6.1 — first-scan baseline guard + stable material normalization.
SMART_WATCH_BASELINE_GUARD_ENABLED = (
    os.getenv("V641_SMART_WATCH_BASELINE_GUARD_ENABLED", "1") == "1"
)
STAKE_DEDUP_GUARD_ENABLED = (
    os.getenv("V641_STAKE_DEDUP_GUARD_ENABLED", "1") == "1"
)

# V6.6.3 — persistent event-level deduplication.
PERSISTENT_EVENT_DEDUP_ENABLED = (
    os.getenv("V663_PERSISTENT_EVENT_DEDUP_ENABLED", "1") == "1"
)
MARKET_DATA_NOISE_GUARD_ENABLED = (
    os.getenv("V663_MARKET_DATA_NOISE_GUARD_ENABLED", "1") == "1"
)
TRUE_NEW_DETAIL_DIFF_ENABLED = (
    os.getenv("V663_TRUE_NEW_DETAIL_DIFF_ENABLED", "1") == "1"
)
EVENT_MEMORY_RETENTION_DAYS = int(
    os.getenv("V663_EVENT_MEMORY_RETENTION_DAYS", "60")
)
EVENT_MEMORY_MAX_KEYS = int(
    os.getenv("V663_EVENT_MEMORY_MAX_KEYS", "2000")
)

# V6.7.4 — Rumor Intelligence scanner state.
RUMOR_MEMORY_RETENTION_DAYS = max(
    7,
    min(90, int(os.getenv("V67_RUMOR_MEMORY_RETENTION_DAYS", "30"))),
)
RUMOR_MEMORY_MAX_KEYS = max(
    100,
    min(5000, int(os.getenv("V67_RUMOR_MEMORY_MAX_KEYS", "1500"))),
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
        "event_memory": {},
        "event_duplicates_suppressed": 0,
        "market_noise_suppressed": 0,
        "issuer_profile_cache": {},
        "rumor_baseline_initialized": False,
        "rumor_memory": {},
        "rumor_alerts_sent": 0,
        "rumor_duplicates_suppressed": 0,
        "rumor_confirmed_count": 0,
        "rumor_denied_count": 0,
        "rumor_expired_count": 0,
        "rumor_entity_rekeys": 0,
        "rumor_integrity_repairs": 0,
        "rumor_confirmed_dedups": 0,
        "rumor_last_scan_utc": None,
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
    if not isinstance(data.get("event_memory"), dict):
        data["event_memory"] = {}
    try:
        data["event_duplicates_suppressed"] = int(
            data.get("event_duplicates_suppressed", 0) or 0
        )
    except Exception:
        data["event_duplicates_suppressed"] = 0
    try:
        data["market_noise_suppressed"] = int(
            data.get("market_noise_suppressed", 0) or 0
        )
    except Exception:
        data["market_noise_suppressed"] = 0
    if not isinstance(data.get("issuer_profile_cache"), dict):
        data["issuer_profile_cache"] = {}
    data.setdefault("rumor_baseline_initialized", False)
    if not isinstance(data.get("rumor_memory"), dict):
        data["rumor_memory"] = {}
    for counter_key in (
        "rumor_alerts_sent",
        "rumor_duplicates_suppressed",
        "rumor_confirmed_count",
        "rumor_denied_count",
        "rumor_expired_count",
        "rumor_entity_rekeys",
        "rumor_integrity_repairs",
        "rumor_confirmed_dedups",
    ):
        try:
            data[counter_key] = int(
                data.get(counter_key, 0) or 0
            )
        except Exception:
            data[counter_key] = 0
    data.setdefault("rumor_last_scan_utc", None)

    # Transparent V6.6.1 state cleanup: normalize old duplicate stake/money.
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

    event_memory = state.get("event_memory") or {}
    if not isinstance(event_memory, dict):
        event_memory = {}

    event_cutoff = utc_now() - timedelta(
        days=EVENT_MEMORY_RETENTION_DAYS
    )

    kept_events = {}
    for key, entry in event_memory.items():
        if not isinstance(entry, dict):
            continue

        stamp = (
            parse_iso(entry.get("last_seen_utc"))
            or parse_iso(entry.get("last_alert_utc"))
            or parse_iso(entry.get("first_seen_utc"))
        )

        if stamp is None or stamp >= event_cutoff:
            kept_events[str(key)] = entry

    if len(kept_events) > EVENT_MEMORY_MAX_KEYS:
        ordered = sorted(
            kept_events.items(),
            key=lambda item: (
                parse_iso(item[1].get("last_seen_utc"))
                or parse_iso(item[1].get("last_alert_utc"))
                or datetime.min.replace(tzinfo=timezone.utc)
            ),
            reverse=True,
        )
        kept_events = dict(ordered[:EVENT_MEMORY_MAX_KEYS])

    if kept_events != event_memory:
        state["event_memory"] = kept_events
        changed = True

    rumor_memory = state.get("rumor_memory") or {}
    if not isinstance(rumor_memory, dict):
        rumor_memory = {}

    rumor_cutoff = utc_now() - timedelta(
        days=RUMOR_MEMORY_RETENTION_DAYS
    )

    kept_rumors = {}
    for key, entry in rumor_memory.items():
        if not isinstance(entry, dict):
            continue

        stamp = (
            parse_iso(entry.get("last_seen_utc"))
            or parse_iso(entry.get("last_alert_utc"))
            or parse_iso(entry.get("first_seen_utc"))
        )

        if stamp is None or stamp >= rumor_cutoff:
            kept_rumors[str(key)] = entry

    if len(kept_rumors) > RUMOR_MEMORY_MAX_KEYS:
        ordered = sorted(
            kept_rumors.items(),
            key=lambda item: (
                parse_iso(item[1].get("last_seen_utc"))
                or parse_iso(item[1].get("last_alert_utc"))
                or datetime.min.replace(tzinfo=timezone.utc)
            ),
            reverse=True,
        )
        kept_rumors = dict(
            ordered[:RUMOR_MEMORY_MAX_KEYS]
        )

    if kept_rumors != rumor_memory:
        state["rumor_memory"] = kept_rumors
        changed = True

    return changed


# ============================================================
# V6.6.3 — PERSISTENT EVENT DEDUP / TRUE MATERIAL DIFF
# ============================================================

def _stable_scalar(value):
    if value in (None, ""):
        return None
    return re.sub(r"\s+", " ", str(value).strip())


def _stable_text_list(values, numeric=False):
    return _normalize_material_list(
        values or [],
        numeric=numeric,
    )


def _material_snapshot(article):
    """Only facts allowed to trigger a new corporate-action alert.

    EXCLUDED BY DESIGN:
    market price, daily %, score, catalyst, monitoring signal,
    headline/source changes, resolver/extraction/debug status.
    """
    d = article.get("details") or {}
    lifecycle = core.lifecycle_snapshot(article)
    role_meta = d.get("role_meta") or {}

    return {
        "event_type": _stable_scalar(article.get("event_type")),
        "stage": _stable_scalar(lifecycle.get("stage")),
        "stage_step": int(lifecycle.get("stage_step") or 0),
        "stage_total": int(lifecycle.get("stage_total") or 0),
        "official_authority": _stable_scalar(
            lifecycle.get("official_authority")
        ),
        "official_kind": _stable_scalar(
            lifecycle.get("official_kind")
        ),
        "schedule": {
            str(k): _stable_scalar(v)
            for k, v in (lifecycle.get("schedule") or {}).items()
            if _stable_scalar(v)
        },
        "stake": _stable_text_list(
            d.get("percentages") or [],
            numeric=True,
        ),
        "money": _stable_text_list(
            d.get("money") or [],
        ),
        "ratio": _stable_scalar(d.get("ratio")),
        "execution_price": _stable_scalar(d.get("execution_price")),
        "tender_price": _stable_scalar(d.get("tender_price")),
        "price_range": _stable_scalar(d.get("price_range")),
        "ipo_single_price": _stable_scalar(d.get("ipo_single_price")),
        "share_count": _stable_scalar(d.get("share_count")),
        "standby_buyer": _stable_scalar(d.get("standby_buyer")),
        "underwriter": _stable_scalar(d.get("underwriter")),
        "use_of_funds": sorted({
            _stable_scalar(x)
            for x in (d.get("use_of_funds") or [])
            if _stable_scalar(x)
        }),
        "acquirer": _stable_scalar(d.get("acquirer")),
        "target": _stable_scalar(d.get("target")),
        "acquirer_confirmed": bool(
            d.get("acquirer")
            and not role_meta.get("acquirer_suppressed")
        ),
        "target_confirmed": bool(
            d.get("target")
            and not role_meta.get("target_suppressed")
        ),
    }


def _market_context_snapshot(article):
    market = article.get("market_data") or {}

    def rounded(value, digits=4):
        try:
            return round(float(value), digits)
        except Exception:
            return None

    return {
        "last_price": rounded(market.get("last_price"), 4),
        "change_pct": rounded(market.get("change_pct"), 4),
        "market_date": _stable_scalar(market.get("market_date")),
    }


def _merge_material_snapshot(previous, current):
    """Cumulative memory; temporary missing fields never erase known facts."""
    previous = dict(previous or {})
    current = dict(current or {})
    merged = dict(previous)

    old_step = int(previous.get("stage_step", 0) or 0)
    new_step = int(current.get("stage_step", 0) or 0)

    for key, value in current.items():
        if key == "schedule":
            continue

        if key in {"stage", "stage_step", "stage_total"}:
            if old_step and new_step and new_step < old_step:
                continue

        if value not in (None, "", [], {}):
            merged[key] = value

    old_schedule = dict(previous.get("schedule") or {})
    for key, value in (current.get("schedule") or {}).items():
        if value:
            old_schedule[str(key)] = value
    merged["schedule"] = old_schedule

    return merged


def _snapshot_change_lines(previous, current):
    if not previous:
        return [], set()

    previous = dict(previous or {})
    current = _merge_material_snapshot(previous, current)

    lines = []
    fields = set()

    old_step = int(previous.get("stage_step", 0) or 0)
    new_step = int(current.get("stage_step", 0) or 0)

    if (
        current.get("stage")
        and current.get("stage") != previous.get("stage")
        and not (old_step and new_step and new_step < old_step)
    ):
        lines.append(
            "Stage: "
            + str(previous.get("stage") or "-")
            + " → "
            + str(current.get("stage") or "-")
        )
        fields.add("stage")

    old_official = previous.get("official_authority")
    new_official = current.get("official_authority")
    if new_official and new_official != old_official:
        if old_official:
            lines.append(f"Official: {old_official} → {new_official}")
        else:
            lines.append(f"Official confirmation: {new_official}")
        fields.add("official")

    labels = getattr(core, "LIFECYCLE_SCHEDULE_LABELS", {})
    old_schedule = previous.get("schedule") or {}
    new_schedule = current.get("schedule") or {}
    for key, value in new_schedule.items():
        if value and value != old_schedule.get(key):
            lines.append(f"{labels.get(key, key)}: {value}")
            fields.add("schedule")

    scalar_labels = {
        "ratio": "Rasio HMETD",
        "execution_price": "Harga pelaksanaan",
        "tender_price": "Harga tender",
        "price_range": "Range harga",
        "ipo_single_price": "Harga IPO",
        "share_count": "Jumlah saham",
        "standby_buyer": "Standby buyer",
        "underwriter": "Underwriter",
        "acquirer": "Acquirer",
        "target": "Target",
    }

    for key, label in scalar_labels.items():
        value = current.get(key)
        old = previous.get(key)
        if value not in (None, "") and value != old:
            if old not in (None, ""):
                lines.append(f"{label}: {old} → {value}")
            else:
                lines.append(f"{label}: {value}")
            fields.add(key)

    for key, label in (
        ("stake", "Stake"),
        ("money", "Nilai transaksi"),
        ("use_of_funds", "Use of funds"),
    ):
        value = current.get(key) or []
        old = previous.get(key) or []
        if value and value != old:
            shown = ", ".join(str(x) for x in value[:4])
            lines.append(f"{label}: {shown}")
            fields.add(key)

    return lines, fields


def _market_context_changed(old, new):
    old = dict(old or {})
    new = dict(new or {})

    if not any(value not in (None, "") for value in new.values()):
        return False

    return any(
        new.get(key) != old.get(key)
        for key in ("last_price", "change_pct", "market_date")
    )


def _event_memory_entry(article, snapshot, *, alert_utc=None):
    now = utc_iso()
    return {
        "first_seen_utc": now,
        "last_seen_utc": now,
        "last_alert_utc": alert_utc,
        "material_snapshot": dict(snapshot or {}),
        "market_context": _market_context_snapshot(article),
        "ticker": str(
            (article.get("details") or {}).get("ticker") or ""
        ).upper(),
        "family": str(core.alert_family(article.get("event_type", ""))),
    }


def _bootstrap_event_memory_from_sent(state, articles):
    """Migrate prior article-key history without turning old events into new."""
    if not PERSISTENT_EVENT_DEDUP_ENABLED:
        return False

    memory = state.setdefault("event_memory", {})
    sent = state.get("sent") or {}
    changed = False

    for group in core.group_event_articles(articles):
        event_key = str(group.get("key") or "")
        if not event_key or event_key in memory:
            continue

        known = [
            article
            for article in group.get("articles", [])
            if article.get("key") in sent
        ]
        if not known:
            continue

        known.sort(
            key=lambda article: (
                article.get("ca_score", 0),
                article.get("published_dt")
                or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )

        baseline = known[0]
        snap = _material_snapshot(baseline)
        sent_stamp = sent.get(baseline.get("key"))
        entry = _event_memory_entry(
            baseline,
            snap,
            alert_utc=sent_stamp,
        )

        if sent_stamp:
            entry["first_seen_utc"] = sent_stamp
            entry["last_seen_utc"] = sent_stamp

        memory[event_key] = entry
        changed = True

    return changed


def _mark_group_article_keys_sent(sent_map, group, timestamp):
    changed = False
    for related in group.get("articles", []):
        key = related.get("key")
        if key and key not in sent_map:
            sent_map[key] = timestamp
            changed = True
    return changed


def _persistent_event_decision(state, group, article):
    memory = state.setdefault("event_memory", {})
    event_key = str(group.get("key") or core.event_identity(article))

    current_raw = _material_snapshot(article)
    current_market = _market_context_snapshot(article)
    existing = memory.get(event_key)

    if not existing:
        return {
            "event_key": event_key,
            "mode": "NEW_EVENT",
            "should_alert": True,
            "change_lines": [],
            "changed_fields": set(),
            "snapshot": current_raw,
            "market_context": current_market,
            "market_only": False,
        }

    previous = existing.get("material_snapshot") or {}
    merged = _merge_material_snapshot(previous, current_raw)
    change_lines, changed_fields = _snapshot_change_lines(previous, merged)

    should_alert = bool(
        change_lines and TRUE_NEW_DETAIL_DIFF_ENABLED
    )

    market_only = (
        not should_alert
        and MARKET_DATA_NOISE_GUARD_ENABLED
        and _market_context_changed(
            existing.get("market_context") or {},
            current_market,
        )
    )

    return {
        "event_key": event_key,
        "mode": "MATERIAL_UPDATE" if should_alert else "SUPPRESS",
        "should_alert": should_alert,
        "change_lines": change_lines,
        "changed_fields": changed_fields,
        "snapshot": merged,
        "market_context": current_market,
        "market_only": market_only,
    }


def _commit_event_memory(
    state,
    article,
    decision,
    *,
    alert_delivered=False,
):
    memory = state.setdefault("event_memory", {})
    event_key = decision["event_key"]
    now = utc_iso()

    existing = memory.get(event_key)
    if not isinstance(existing, dict):
        existing = _event_memory_entry(
            article,
            decision.get("snapshot") or {},
            alert_utc=(now if alert_delivered else None),
        )
    else:
        existing = dict(existing)

    existing["last_seen_utc"] = now
    existing["material_snapshot"] = dict(decision.get("snapshot") or {})
    existing["market_context"] = dict(decision.get("market_context") or {})
    existing["ticker"] = str(
        (article.get("details") or {}).get("ticker") or ""
    ).upper()
    existing["family"] = str(
        core.alert_family(article.get("event_type", ""))
    )

    if alert_delivered:
        existing["last_alert_utc"] = now

    existing.setdefault("first_seen_utc", now)
    memory[event_key] = existing


def v663_persistent_dedup_selftest():
    base_article = {
        "title": "Pengendali baru DOOH kuasai 51% saham dan wajib tender offer",
        "link": "https://example.com/dooh",
        "source": "Example Media",
        "published": "18 Aug 2026",
        "event_type": "TENDER OFFER",
        "stage": "TENDER OFFER",
        "priority": "HIGH",
        "urgency": "HIGH",
        "context": "ACTIVE EVENT",
        "geo": "INDONESIA 🇮🇩",
        "ca_score": 88,
        "information_score": 88,
        "catalyst": "POSITIVE",
        "issuer_name": "Era Media Sejahtera",
        "issuer_aliases": ["Era Media Sejahtera"],
        "official_reference": {
            "authority": "IDX",
            "kind": "PRIMARY",
            "url": "https://example.com/official",
        },
        "details": {
            "ticker": "DOOH",
            "money": ["Rp197,34 miliar"],
            "percentages": [51.0],
            "ratio": None,
            "execution_price": None,
            "price_range": None,
            "ipo_single_price": None,
            "tender_price": None,
            "share_count": None,
            "standby_buyer": None,
            "underwriter": None,
            "use_of_funds": [],
            "schedule": {},
            "acquirer": None,
            "target": "DOOH",
            "role_meta": {},
        },
        "market_data": {
            "last_price": 326,
            "change_pct": 10.88,
            "market_date": "2026-08-18",
        },
    }

    state = default_state()
    group = {
        "key": core.event_identity(base_article),
        "articles": [base_article],
        "primary": base_article,
    }

    first = _persistent_event_decision(state, group, base_article)
    if not first.get("should_alert"):
        return {"passed": False, "reason": "first event not alert"}

    _commit_event_memory(
        state,
        base_article,
        first,
        alert_delivered=True,
    )

    price_only = json.loads(json.dumps(base_article))
    price_only["market_data"]["last_price"] = 352
    price_only["market_data"]["change_pct"] = 19.73
    second = _persistent_event_decision(state, group, price_only)

    material = json.loads(json.dumps(price_only))
    material["details"]["tender_price"] = "Rp300"
    third = _persistent_event_decision(state, group, material)

    headline_only = json.loads(json.dumps(price_only))
    headline_only["title"] = "Media lain menulis ulang tender offer DOOH"
    headline_only["source"] = "Publisher 2"
    fourth = _persistent_event_decision(state, group, headline_only)

    return {
        "passed": all([
            second.get("should_alert") is False,
            second.get("market_only") is True,
            third.get("should_alert") is True,
            "tender_price" in third.get("changed_fields", set()),
            fourth.get("should_alert") is False,
        ]),
        "market_price_silent": (
            second.get("should_alert") is False
            and second.get("market_only") is True
        ),
        "true_detail_alert": (
            third.get("should_alert") is True
            and "tender_price" in third.get("changed_fields", set())
        ),
        "headline_noise_silent": fourth.get("should_alert") is False,
    }



# ============================================================
# V6.7.4 — RUMOR INTELLIGENCE SCANNER
# ============================================================

def _rumor_record_seen_signature(record):
    if not isinstance(record, dict):
        return ""

    return "|".join([
        str(record.get("status") or ""),
        str(record.get("strength") or ""),
        str(record.get("source_count") or 0),
        str(record.get("last_seen_utc") or ""),
        str(record.get("title") or ""),
    ])


def _initialize_rumor_baseline(state, rumor_groups):
    if state.get("rumor_baseline_initialized"):
        return False

    memory = state.setdefault(
        "rumor_memory",
        {},
    )

    for group in rumor_groups or []:
        record = core.rumor_record_from_group(
            group
        )

        key = str(
            record.get("key")
            or group.get("key")
            or ""
        )

        if not key:
            continue

        record["last_alert_utc"] = None
        memory[key] = record

    state["rumor_baseline_initialized"] = True
    state["rumor_last_scan_utc"] = utc_iso()

    print(
        "V6.7.5 rumor baseline initialized:",
        len(memory),
        "rumor record(s).",
    )

    return True


def _expire_rumor_memory(state, current_keys):
    memory = state.setdefault(
        "rumor_memory",
        {},
    )

    changed = False
    notifications = []

    cutoff = utc_now() - timedelta(
        days=getattr(
            core,
            "RUMOR_EXPIRE_DAYS",
            7,
        )
    )

    for key, record in list(
        memory.items()
    ):
        if key in current_keys:
            continue

        if not isinstance(record, dict):
            continue

        if record.get("status") != "ACTIVE":
            continue

        last_seen = parse_iso(
            record.get("last_seen_utc")
        )

        if (
            last_seen is None
            or last_seen > cutoff
        ):
            continue

        updated = dict(record)
        updated["status"] = "EXPIRED"
        updated["strength"] = record.get(
            "strength",
            "WEAK",
        )
        updated["last_state_change_utc"] = utc_iso()

        decision = core.rumor_change_decision(
            record,
            updated,
        )

        memory[key] = updated
        state["rumor_expired_count"] = (
            int(
                state.get(
                    "rumor_expired_count",
                    0,
                )
                or 0
            )
            + 1
        )

        changed = True

        if decision.get("should_alert"):
            notifications.append(
                (
                    updated,
                    decision,
                )
            )

    return changed, notifications


def _sanitize_rumor_memory_integrity(state):
    memory = state.setdefault("rumor_memory", {})
    if not isinstance(memory, dict):
        return False, 0
    changed = False
    repairs = 0
    for key, record in list(memory.items()):
        if not isinstance(record, dict):
            continue
        clean, count = core.sanitize_rumor_record_integrity(record)
        if count:
            memory[key] = clean
            repairs += int(count)
            changed = True
    if repairs:
        state["rumor_integrity_repairs"] = int(
            state.get("rumor_integrity_repairs", 0) or 0
        ) + repairs
        print(f"V6.7.5 rumor integrity repaired: {repairs} field(s).")
    return changed, repairs


def _reconcile_confirmed_rumor_memory_duplicates(state):
    if not getattr(core, "RUMOR_CONFIRMED_DEDUP_ENABLED", True):
        return False, 0
    memory = state.setdefault("rumor_memory", {})
    if not isinstance(memory, dict):
        return False, 0
    positions = {}
    changed = False
    deduped = 0
    for key in list(memory.keys()):
        record = memory.get(key)
        if not isinstance(record, dict):
            continue
        sig_fn = getattr(core, "_rumor_official_confirmation_signature", None)
        sig = sig_fn(record) if callable(sig_fn) else None
        if not sig:
            continue
        prior_key = positions.get(sig)
        if prior_key is None:
            positions[sig] = key
            continue
        prior = memory.get(prior_key)
        merged = core.merge_rumor_records(prior, record)
        merged["key"] = prior_key
        memory[prior_key] = merged
        del memory[key]
        deduped += 1
        changed = True
    if deduped:
        state["rumor_confirmed_dedups"] = int(
            state.get("rumor_confirmed_dedups", 0) or 0
        ) + deduped
        print(f"V6.7.5 confirmed rumor duplicates merged: {deduped} record(s).")
    return changed, deduped


def _reconcile_rumor_memory_entity_keys(state, rumor_groups):
    """Migrate old UNKNOWN rumor memory into a canonical ticker group.

    This is intentionally silent: entity resolution itself is not a new
    trading rumor and must never create a re-alert. The current canonical
    group is merged immediately so the following diff sees no artificial
    WEAK→STRONG jump caused solely by the re-key.
    """
    if not getattr(core, "RUMOR_UNKNOWN_MERGE_ENABLED", True):
        return False, 0

    memory = state.setdefault("rumor_memory", {})
    if not isinstance(memory, dict) or not memory:
        return False, 0

    candidates = []
    for group in rumor_groups or []:
        primary = group.get("primary") or {}
        ticker = str(primary.get("ticker") or "").upper().strip()
        if not re.fullmatch(r"[A-Z]{4}", ticker):
            continue
        aliases = core.rumor_group_entity_aliases(group)
        if not aliases:
            continue
        candidates.append({
            "ticker": ticker,
            "category": str(primary.get("rumor_category") or ""),
            "aliases": aliases,
            "group": group,
        })

    changed = False
    rekeyed = 0

    for old_key, old_record in list(memory.items()):
        if not isinstance(old_record, dict):
            continue
        if str(old_record.get("ticker") or "").upper().strip():
            continue

        matches = []
        for candidate in candidates:
            if candidate["category"] != str(old_record.get("category") or ""):
                continue
            if core.rumor_record_matches_entity_alias(
                old_record,
                candidate["aliases"],
            ):
                matches.append(candidate)

        tickers = {item["ticker"] for item in matches}
        if len(tickers) != 1:
            continue

        candidate = max(
            (item for item in matches if item["ticker"] in tickers),
            key=lambda item: max(len(str(a)) for a in item["aliases"]),
        )
        current_record = core.rumor_record_from_group(candidate["group"])
        target_key = str(current_record.get("key") or "")
        if not target_key or target_key == old_key:
            continue

        migrated = dict(old_record)
        migrated["key"] = target_key
        migrated["ticker"] = candidate["ticker"]
        if not migrated.get("company_name"):
            migrated["company_name"] = candidate["aliases"][0]
        migrated["entity_aliases"] = list(candidate["aliases"])
        migrated["entity_resolution_source"] = "V6.7.4_MEMORY_REKEY"

        existing = memory.get(target_key)
        merged = core.merge_rumor_records(existing, migrated)
        # Important: absorb the current canonical feed state now. This makes
        # the migration silent and prevents an entity-fix-only re-alert.
        merged = core.merge_rumor_records(merged, current_record)

        # Preserve whichever prior alert timestamp exists.
        alert_times = [
            value for value in [
                (existing or {}).get("last_alert_utc") if isinstance(existing, dict) else None,
                old_record.get("last_alert_utc"),
            ] if value
        ]
        if alert_times:
            merged["last_alert_utc"] = max(alert_times)

        memory[target_key] = merged
        del memory[old_key]
        changed = True
        rekeyed += 1

    if rekeyed:
        state["rumor_entity_rekeys"] = int(
            state.get("rumor_entity_rekeys", 0) or 0
        ) + rekeyed
        print(
            f"V6.7.5 rumor entity memory re-keyed: {rekeyed} record(s)."
        )

    return changed, rekeyed


async def process_rumor_intelligence(
    state,
    rumor_groups,
    official_articles,
    chat_ids,
):
    if not getattr(
        core,
        "RUMOR_INTELLIGENCE_ENABLED",
        False,
    ):
        return False, 0

    core.correlate_rumor_groups_with_official(
        rumor_groups,
        official_articles,
    )

    integrity_changed, _ = _sanitize_rumor_memory_integrity(state)
    confirmed_dedup_changed, _ = _reconcile_confirmed_rumor_memory_duplicates(state)

    rekey_changed, _ = _reconcile_rumor_memory_entity_keys(
        state,
        rumor_groups,
    )

    if not state.get(
        "rumor_baseline_initialized"
    ):
        changed = _initialize_rumor_baseline(
            state,
            rumor_groups,
        )
        return changed, 0

    memory = state.setdefault(
        "rumor_memory",
        {},
    )

    state_changed = bool(
        rekey_changed or integrity_changed or confirmed_dedup_changed
    )
    sent_count = 0
    current_keys = set()
    profile_refresh_budget = 2

    # First allow prior active rumors to be confirmed by the current
    # official corporate-action feed even if the old rumor article is no
    # longer present in this scan's rumor RSS window.
    for key, previous in list(
        memory.items()
    ):
        if not isinstance(previous, dict):
            continue

        if previous.get("status") != "ACTIVE":
            continue

        confirmation = core.find_official_confirmation_for_rumor(
            previous,
            official_articles,
        )

        if not confirmation:
            continue

        current = dict(
            previous
        )
        current["status"] = "CONFIRMED OFFICIAL"
        current["strength"] = "CONFIRMED OFFICIAL"
        current["official_confirmation"] = confirmation
        current["last_seen_utc"] = utc_iso()

        decision = core.rumor_change_decision(
            previous,
            current,
        )

        if decision.get("should_alert"):
            delivered = await send_to_all(
                chat_ids,
                core.format_rumor_alert(
                    current,
                    changes=decision.get("changes"),
                    mode=decision.get("mode"),
                ),
            )

            if delivered > 0:
                current["last_alert_utc"] = utc_iso()
                sent_count += 1
                state["rumor_alerts_sent"] = (
                    int(
                        state.get(
                            "rumor_alerts_sent",
                            0,
                        )
                        or 0
                    )
                    + 1
                )
                state["rumor_confirmed_count"] = (
                    int(
                        state.get(
                            "rumor_confirmed_count",
                            0,
                        )
                        or 0
                    )
                    + 1
                )

        memory[key] = current
        state_changed = True

    groups = list(
        rumor_groups or []
    )

    groups.sort(
        key=lambda group: (
            core.RUMOR_STATUS_RANK.get(
                str(group.get("status") or "ACTIVE"),
                0,
            ),
            core.RUMOR_STRENGTH_RANK.get(
                str(group.get("strength") or "WEAK"),
                0,
            ),
            int(group.get("source_count", 0) or 0),
            group.get("primary", {}).get("published_dt")
            or datetime.min.replace(
                tzinfo=timezone.utc
            ),
        ),
        reverse=True,
    )

    alert_budget = int(
        getattr(
            core,
            "RUMOR_PUSH_LIMIT",
            4,
        )
        or 4
    )

    for group in groups:
        key = str(
            group.get("key")
            or ""
        )

        if not key:
            continue

        current_keys.add(
            key
        )

        previous = memory.get(
            key
        )

        if (
            profile_refresh_budget > 0
            and getattr(core, "RUMOR_PROFILE_ENABLED", False)
            and core.rumor_profile_needs_refresh(previous or {
                "ticker": (group.get("primary") or {}).get("ticker"),
                "issuer_profile": group.get("issuer_profile"),
            })
        ):
            try:
                await core.enrich_rumor_profile_context(group)
                profile_refresh_budget -= 1
            except Exception as exc:
                group["profile_refresh_utc"] = utc_iso()
                print("Rumor profile refresh skipped:", type(exc).__name__)

        basic = core.rumor_record_from_group(
            group
        )

        merged = core.merge_rumor_records(
            previous,
            basic,
        )

        decision = core.rumor_change_decision(
            previous,
            merged,
        )

        # New official/denial record without a previously observed active
        # rumor is not sent as a "rumor" alert.
        if (
            previous is None
            and merged.get("status")
            != "ACTIVE"
        ):
            memory[key] = merged
            state_changed = True
            continue

        # Feed ranking can occasionally surface an older rumor for the first
        # time. Track it, but do not push stale rumor as if it were breaking.
        if (
            previous is None
            and merged.get("status") == "ACTIVE"
            and not core.rumor_is_push_fresh(merged)
        ):
            memory[key] = merged
            state_changed = True
            print(
                "Stale newly-detected rumor stored without alert:",
                merged.get("ticker")
                or merged.get("company_name")
                or "UNKNOWN",
            )
            continue

        if (
            decision.get("should_alert")
            and alert_budget > 0
            and getattr(
                core,
                "RUMOR_AUTO_ALERT_ENABLED",
                True,
            )
        ):
            try:
                await core.enrich_rumor_group(
                    group
                )
                enriched = core.rumor_record_from_group(
                    group
                )
                merged = core.merge_rumor_records(
                    previous,
                    enriched,
                )
                decision = core.rumor_change_decision(
                    previous,
                    merged,
                )
            except Exception as exc:
                print(
                    "Rumor enrichment error:",
                    type(exc).__name__,
                )

            if decision.get("should_alert"):
                delivered = await send_to_all(
                    chat_ids,
                    core.format_rumor_alert(
                        merged,
                        changes=decision.get("changes"),
                        mode=decision.get("mode"),
                    ),
                )

                if delivered > 0:
                    now_alert = utc_iso()
                    merged["last_alert_utc"] = now_alert
                    sent_count += 1
                    alert_budget -= 1

                    state["rumor_alerts_sent"] = (
                        int(
                            state.get(
                                "rumor_alerts_sent",
                                0,
                            )
                            or 0
                        )
                        + 1
                    )

                    if decision.get("mode") == "CONFIRMED":
                        state["rumor_confirmed_count"] = (
                            int(
                                state.get(
                                    "rumor_confirmed_count",
                                    0,
                                )
                                or 0
                            )
                            + 1
                        )

                    elif decision.get("mode") == "DENIED":
                        state["rumor_denied_count"] = (
                            int(
                                state.get(
                                    "rumor_denied_count",
                                    0,
                                )
                                or 0
                            )
                            + 1
                        )

                    print(
                        "Rumor alert delivered:",
                        decision.get("mode"),
                        merged.get("ticker")
                        or merged.get("company_name")
                        or "UNKNOWN",
                        merged.get("category"),
                        merged.get("strength"),
                    )

                    state_changed = True
                else:
                    print(
                        "Rumor alert NOT persisted as delivered; Telegram failed."
                    )
            else:
                # Deep enrichment found no real rumor-state/material change.
                state["rumor_duplicates_suppressed"] = (
                    int(
                        state.get(
                            "rumor_duplicates_suppressed",
                            0,
                        )
                        or 0
                    )
                    + 1
                )
                state_changed = True

        else:
            if previous is not None:
                if (
                    _rumor_record_seen_signature(
                        merged
                    )
                    != _rumor_record_seen_signature(
                        previous
                    )
                ):
                    state["rumor_duplicates_suppressed"] = (
                        int(
                            state.get(
                                "rumor_duplicates_suppressed",
                                0,
                            )
                            or 0
                        )
                        + 1
                    )
                    state_changed = True

        memory[key] = merged

    dedup_changed_after, _ = _reconcile_confirmed_rumor_memory_duplicates(state)
    if dedup_changed_after:
        state_changed = True

    expired_changed, expired_notifications = _expire_rumor_memory(
        state,
        current_keys,
    )

    if expired_changed:
        state_changed = True

    for record, decision in expired_notifications:
        delivered = await send_to_all(
            chat_ids,
            core.format_rumor_alert(
                record,
                changes=decision.get("changes"),
                mode=decision.get("mode"),
            ),
        )

        if delivered > 0:
            sent_count += 1
            state["rumor_alerts_sent"] = (
                int(
                    state.get(
                        "rumor_alerts_sent",
                        0,
                    )
                    or 0
                )
                + 1
            )

    state["rumor_last_scan_utc"] = utc_iso()

    return state_changed, sent_count


def v671_rumor_memory_rekey_selftest():
    now = utc_now()
    state = default_state()
    state["rumor_baseline_initialized"] = True

    old_key = "AKUISISI / TAKEOVER|TITLE|bayan resources tanggapi isu"
    state["rumor_memory"] = {
        old_key: {
            "key": old_key,
            "ticker": None,
            "company_name": None,
            "category": "AKUISISI / TAKEOVER",
            "status": "ACTIVE",
            "strength": "WEAK",
            "source_count": 1,
            "sources": ["Media A"],
            "title": "Bayan Resources Tanggapi Isu Akuisisi",
            "source": "Media A",
            "last_seen_utc": now.isoformat(),
            "first_seen_utc": now.isoformat(),
            "rumor_details": {},
        }
    }

    alias_backup = dict(getattr(core, "TICKER_ALIAS_CACHE", {}))
    try:
        core.TICKER_ALIAS_CACHE.clear()
        core.register_ticker_aliases("BYAN", ["Bayan Resources"])

        articles = [
            {
                "title": "Rumor akuisisi BYAN kembali beredar",
                "snippet": "Bayan Resources menanggapi isu tersebut",
                "ticker": "BYAN",
                "company_name": "Bayan Resources",
                "rumor_category": "AKUISISI / TAKEOVER",
                "rumor_status": "ACTIVE",
                "source": "Media A",
                "published_dt": now,
                "rumor_details": {},
            },
            {
                "title": "Bayan Resources Tanggapi Isu Akuisisi",
                "snippet": "Isu pasar belum dikonfirmasi",
                "ticker": None,
                "company_name": None,
                "rumor_category": "AKUISISI / TAKEOVER",
                "rumor_status": "ACTIVE",
                "source": "Media B",
                "published_dt": now,
                "rumor_details": {},
            },
        ]
        core.resolve_rumor_entities(articles)
        groups = core.group_rumor_articles(articles)
        changed, count = _reconcile_rumor_memory_entity_keys(state, groups)

        canonical = "AKUISISI / TAKEOVER|TICKER|BYAN"
        record = state["rumor_memory"].get(canonical) or {}
        current = core.rumor_record_from_group(groups[0])
        decision = core.rumor_change_decision(record, current)

        return {
            "passed": all([
                changed is True,
                count == 1,
                old_key not in state["rumor_memory"],
                canonical in state["rumor_memory"],
                record.get("ticker") == "BYAN",
                record.get("source_count", 0) >= 2,
                decision.get("should_alert") is False,
            ]),
            "unknown_removed": old_key not in state["rumor_memory"],
            "canonical_created": canonical in state["rumor_memory"],
            "silent_rekey": decision.get("should_alert") is False,
        }
    finally:
        core.TICKER_ALIAS_CACHE.clear()
        core.TICKER_ALIAS_CACHE.update(alias_backup)


def v67_rumor_scanner_selftest():
    state = default_state()

    now = utc_now()

    active_article = {
        "title": "Rumor PT Alpha akan mengakuisisi saham ABCD",
        "link": "https://example.com/a",
        "published": now.isoformat(),
        "published_dt": now,
        "source": "Kontan",
        "snippet": "Investor strategis disebut masuk ABCD",
        "rumor_category": "AKUISISI / TAKEOVER",
        "rumor_status": "ACTIVE",
        "ticker": "ABCD",
        "company_name": "PT ABCD Tbk",
        "rumor_details": {
            "rumored_party": "PT Alpha",
            "percentages": [30.0],
            "money": [],
        },
        "key": "a1",
    }

    group = core.group_rumor_articles(
        [active_article]
    )[0]

    baseline_changed = _initialize_rumor_baseline(
        state,
        [group],
    )

    key = group["key"]
    previous = state["rumor_memory"][
        key
    ]

    price_only = dict(
        previous
    )
    price_only["market_data"] = {
        "last_price": 200,
        "change_pct": 15.0,
    }

    profile_only = dict(
        previous
    )
    profile_only["issuer_profile"] = {
        "business_activity": "Media",
        "sector": "Communication Services",
    }

    stronger = dict(
        previous
    )
    stronger["strength"] = "STRONG"

    return {
        "passed": all([
            baseline_changed is True,
            state.get("rumor_baseline_initialized") is True,
            core.rumor_change_decision(
                previous,
                price_only,
            )["should_alert"] is False,
            core.rumor_change_decision(
                previous,
                profile_only,
            )["should_alert"] is False,
            core.rumor_change_decision(
                previous,
                stronger,
            )["should_alert"] is True,
        ]),
        "baseline_guard": (
            baseline_changed
            and state.get("rumor_baseline_initialized")
        ),
        "market_no_realert": (
            core.rumor_change_decision(
                previous,
                price_only,
            )["should_alert"] is False
        ),
        "profile_no_realert": (
            core.rumor_change_decision(
                previous,
                profile_only,
            )["should_alert"] is False
        ),
    }



# ============================================================
# V6.6.1 SMART WATCH BASELINE + MATERIAL NORMALIZATION
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
# V6.6.1 SMART WATCHLIST SCANNER
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
        f"🚨 <b>V6.7.5 SMART WATCH — {ticker}</b>",
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
        f"⏰ <b>V6.7.5 MILESTONE ALERT — {ticker}</b>",
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
            # V6.6.1: a newly added/updated watch gets ONE baseline-sync pass.
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

    if PERSISTENT_EVENT_DEDUP_ENABLED:
        for group in core.group_event_articles(articles):
            article = group.get("primary")
            event_key = str(group.get("key") or "")
            if not article or not event_key:
                continue
            snap = _material_snapshot(article)
            entry = _event_memory_entry(
                article,
                snap,
                alert_utc=now,
            )
            entry["first_seen_utc"] = now
            entry["last_seen_utc"] = now
            state.setdefault("event_memory", {})[event_key] = entry

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

    hydrate_profiles = getattr(
        core,
        "hydrate_issuer_profile_cache",
        None,
    )
    if callable(hydrate_profiles):
        try:
            command_profile_count = int(
                hydrate_profiles(
                    command_state.get("issuer_profiles") or {}
                )
                or 0
            )
            if command_profile_count:
                print(
                    f"Issuer profile cache hydrated from command_state: {command_profile_count} ticker(s)."
                )
        except Exception:
            pass
        try:
            profile_count = int(
                hydrate_profiles(
                    state.get("issuer_profile_cache") or {}
                )
                or 0
            )
            if profile_count:
                print(
                    f"Issuer profile cache hydrated: {profile_count} ticker(s)."
                )
        except Exception:
            pass

    watchlist = normalize_watchlist(command_state)
    print(f"Smart Watchlist active: {len(watchlist)} ticker(s).")

    articles = await core.fetch_all_articles()
    print(
        f"Fetched {len(articles)} unique corporate-action articles."
    )

    rumor_articles = []
    rumor_groups = []
    rumor_fetch_ok = False

    if getattr(
        core,
        "RUMOR_INTELLIGENCE_ENABLED",
        False,
    ):
        try:
            rumor_articles = await core.fetch_all_rumor_articles(official_articles=articles)
            rumor_groups = core.group_rumor_articles(
                rumor_articles
            )
            rumor_fetch_ok = True
            print(
                f"Fetched {len(rumor_articles)} rumor article(s) "
                f"in {len(rumor_groups)} rumor group(s)."
            )
        except Exception as exc:
            print(
                "Rumor Intelligence fetch error:",
                type(exc).__name__,
            )
            rumor_articles = []
            rumor_groups = []

    state_changed = prune_state(
        state
    )

    rumor_changed = False
    rumor_sent = 0

    if rumor_fetch_ok:
        rumor_changed, rumor_sent = await process_rumor_intelligence(
            state,
            rumor_groups,
            articles,
            chat_ids,
        )

    elif not state.get("rumor_baseline_initialized"):
        print(
            "Rumor baseline NOT initialized because rumor fetch failed."
        )

    if rumor_changed:
        state_changed = True

    if rumor_sent:
        print(
            f"Rumor Intelligence alerts delivered: {rumor_sent}."
        )

    if _bootstrap_event_memory_from_sent(
        state,
        articles,
    ):
        state_changed = True
        print(
            "V6.6.3 event memory bootstrapped from prior sent history."
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
                "rumor_fetched": len(rumor_articles),
                "rumor_groups": len(rumor_groups),
                "rumor_sent": rumor_sent,
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

            decision = _persistent_event_decision(
                state,
                group,
                article,
            )

            article["alert_mode"] = decision.get(
                "mode",
                "NEW_EVENT",
            )
            article["persistent_change_lines"] = list(
                decision.get("change_lines") or []
            )
            article["persistent_changed_fields"] = sorted(
                decision.get("changed_fields") or set()
            )

            if (
                PERSISTENT_EVENT_DEDUP_ENABLED
                and not decision.get("should_alert")
            ):
                now_known = utc_iso()
                _mark_group_article_keys_sent(
                    sent_map,
                    group,
                    now_known,
                )
                _commit_event_memory(
                    state,
                    article,
                    decision,
                    alert_delivered=False,
                )

                state["event_duplicates_suppressed"] = (
                    int(
                        state.get(
                            "event_duplicates_suppressed",
                            0,
                        )
                        or 0
                    )
                    + 1
                )

                if decision.get("market_only"):
                    state["market_noise_suppressed"] = (
                        int(
                            state.get(
                                "market_noise_suppressed",
                                0,
                            )
                            or 0
                        )
                        + 1
                    )
                    print(
                        "Market-only re-alert suppressed:",
                        (article.get("details") or {}).get("ticker", "—"),
                    )
                else:
                    print(
                        "Persistent duplicate event suppressed:",
                        (article.get("details") or {}).get("ticker", "—"),
                    )

                state_changed = True
                continue

            delivered = await send_to_all(
                chat_ids,
                core.format_alert(article),
            )

            if delivered > 0:
                now_sent = utc_iso()

                _mark_group_article_keys_sent(
                    sent_map,
                    group,
                    now_sent,
                )
                _commit_event_memory(
                    state,
                    article,
                    decision,
                    alert_delivered=True,
                )

                state_changed = True
                sent_count += 1
                print(
                    "Event alert delivered:",
                    decision.get("mode"),
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

    export_profiles = getattr(
        core,
        "export_issuer_profile_cache",
        None,
    )
    if callable(export_profiles):
        try:
            exported_profiles = export_profiles()
            if (
                isinstance(exported_profiles, dict)
                and exported_profiles
                and exported_profiles
                != state.get("issuer_profile_cache", {})
            ):
                state["issuer_profile_cache"] = exported_profiles
                state_changed = True
        except Exception:
            pass

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
        "rumor_fetched": len(rumor_articles),
        "rumor_groups": len(rumor_groups),
        "rumor_sent": rumor_sent,
        "smart_sent": smart_sent,
        "watchlist": len(watchlist),
        "baseline": False,
        "state_changed": state_changed,
    }


def v672_rumor_integrity_state_selftest():
    state = default_state()
    state["rumor_baseline_initialized"] = True
    confirmation = {
        "event_type": "BUYBACK",
        "title": "PT Bur mengumumkan buyback saham",
        "official_reference": {
            "authority": "IDX",
            "url": "https://www.idx.co.id/disclosure/123",
        },
    }
    state["rumor_memory"] = {
        "AKUISISI / TAKEOVER|TICKER|BYAN": {
            "key": "AKUISISI / TAKEOVER|TICKER|BYAN",
            "ticker": "BYAN",
            "company_name": "Bayan Resources",
            "category": "AKUISISI / TAKEOVER",
            "status": "ACTIVE",
            "strength": "STRONG",
            "title": "Saham BYAN Terbang 18,75% Tersengat Rumor Akuisisi Haji Isam",
            "rumor_details": {
                "rumored_party": "Tersengat Rumor",
                "percentages": [18.75],
                "share_count": ", saham",
            },
        },
        "BUYBACK|TITLE|a": {
            "key": "BUYBACK|TITLE|a",
            "company_name": "PT Bur",
            "category": "BUYBACK",
            "status": "CONFIRMED OFFICIAL",
            "strength": "CONFIRMED OFFICIAL",
            "source_count": 1,
            "sources": ["Media A"],
            "title": "PT Bur buyback saham",
            "rumor_details": {},
            "official_confirmation": confirmation,
        },
        "BUYBACK|TITLE|b": {
            "key": "BUYBACK|TITLE|b",
            "company_name": "PT Bur",
            "category": "BUYBACK",
            "status": "CONFIRMED OFFICIAL",
            "strength": "CONFIRMED OFFICIAL",
            "source_count": 1,
            "sources": ["Media B"],
            "title": "Buyback PT Bur resmi",
            "rumor_details": {},
            "official_confirmation": confirmation,
        },
    }
    repaired, repairs = _sanitize_rumor_memory_integrity(state)
    deduped, dedup_count = _reconcile_confirmed_rumor_memory_duplicates(state)
    byan = state["rumor_memory"].get("AKUISISI / TAKEOVER|TICKER|BYAN") or {}
    details = byan.get("rumor_details") or {}
    bur_records = [
        r for r in state["rumor_memory"].values()
        if isinstance(r, dict) and r.get("company_name") == "PT Bur"
    ]
    return {
        "passed": all([
            repaired,
            repairs >= 3,
            not details.get("rumored_party"),
            not details.get("percentages"),
            not details.get("share_count"),
            deduped,
            dedup_count == 1,
            len(bur_records) == 1,
            bur_records[0].get("source_count") == 2,
        ]),
        "legacy_bad_fields_removed": repairs >= 3,
        "confirmed_memory_dedup": dedup_count == 1,
    }


async def test_telegram():
    chat_ids = secret_chat_ids()

    if not chat_ids:
        raise RuntimeError(
            "TELEGRAM_CHAT_IDS belum tersedia."
        )

    integrity = core.v662_integrity_selftest()
    if not integrity.get("passed"):
        raise RuntimeError(
            "V6.6.2 integrity guard self-test gagal."
        )

    core_v663 = core.v663_core_selftest()
    persistent = v663_persistent_dedup_selftest()
    profile_test = core.v664_profile_selftest()
    controller_test = core.v6641_controller_deep_selftest()
    profile_sync_test = core.v6642_profile_sync_selftest()
    rumor_core_test = core.v67_rumor_selftest()
    rumor_regression_test = core.v67_rumor_regression_selftest()
    rumor_scanner_test = v67_rumor_scanner_selftest()
    rumor_entity_test = core.v671_rumor_entity_resolution_selftest()
    rumor_entity_prime_test = await core.v671_rumor_entity_prime_selftest()
    rumor_rekey_test = v671_rumor_memory_rekey_selftest()
    rumor_integrity_test = core.v672_rumor_data_integrity_selftest()
    rumor_integrity_state_test = v672_rumor_integrity_state_selftest()
    rumor_v673_test = core.v673_rumor_quality_impact_selftest()
    rumor_v674_test = core.v674_owner_semantic_independence_selftest()
    rumor_v675_test = core.v675_hotfix_selftest()

    if not rumor_v675_test.get("passed"):
        raise RuntimeError(
            "V6.7.5 Issuer/Owner/Profile hotfix self-test gagal."
        )

    if not rumor_v674_test.get("passed"):
        raise RuntimeError(
            "V6.7.4 Owner Intelligence / Semantic Independence self-test gagal."
        )

    if not rumor_v673_test.get("passed"):
        raise RuntimeError(
            "V6.7.3 Source Quality / Anti-Copy / Trading Impact regression gagal."
        )

    if not rumor_integrity_test.get("passed"):
        raise RuntimeError(
            "V6.7.4 Rumor Data Integrity core self-test gagal."
        )

    if not rumor_integrity_state_test.get("passed"):
        raise RuntimeError(
            "V6.7.4 Rumor Data Integrity state self-test gagal."
        )

    if not rumor_entity_prime_test.get("passed"):
        raise RuntimeError(
            "V6.7.4 Rumor Entity Multi-Source Prime self-test gagal."
        )

    if not rumor_entity_test.get("passed"):
        raise RuntimeError(
            "V6.7.4 Rumor Entity Resolution self-test gagal."
        )

    if not rumor_rekey_test.get("passed"):
        raise RuntimeError(
            "V6.7.4 Rumor UNKNOWN Memory Merge self-test gagal."
        )

    if not rumor_regression_test.get("passed"):
        raise RuntimeError(
            "V6.7.4 Rumor Intelligence regression self-test gagal."
        )

    if not rumor_core_test.get("passed"):
        raise RuntimeError(
            "V6.7.4 Rumor Intelligence core self-test gagal."
        )

    if not rumor_scanner_test.get("passed"):
        raise RuntimeError(
            "V6.7.4 Rumor Intelligence scanner self-test gagal."
        )

    if not profile_sync_test.get("passed"):
        raise RuntimeError(
            "V6.7.4 profile sync self-test gagal."
        )

    if not controller_test.get("passed"):
        raise RuntimeError(
            "V6.6.4.1 controller deep resolver self-test gagal."
        )

    if not profile_test.get("passed"):
        raise RuntimeError(
            "V6.6.4 issuer profile self-test gagal."
        )

    if not core_v663.get("passed"):
        raise RuntimeError(
            "V6.6.3 compact alert self-test gagal."
        )

    if not persistent.get("passed"):
        raise RuntimeError(
            "V6.6.3 persistent dedup self-test gagal."
        )

    text = (
        "✅ <b>Kabar Saham V6.7.5 — RUMOR INTELLIGENCE TEST OK</b>\n\n"
        "Entity Role Guard: ✅ PASS\n"
        "Indonesia Classification Guard: ✅ PASS\n"
        "Persistent Event Dedup: ✅ PASS\n"
        "Market Data Noise Guard: ✅ PASS\n"
        "True New-Detail Diff: ✅ PASS\n"
        "Compact 3-Block Alert: ✅ PASS\n"
        "Technical Detail in /analyze: ✅ RETAINED\n"
        "Issuer Profile Intelligence: ✅ PASS\n"
        "Owner-vs-Management Guard: ✅ PASS\n"
        "Profile Context No-Realert: ✅ PASS\n"
        "Controller Deep Resolver: ✅ PASS\n"
        "Official Result-Title Actor: ✅ PASS\n"
        "Target Self-Controller Guard: ✅ PASS\n"
        "Control Status Consistency: ✅ PASS\n"
        "Profile/Analyze Controller Sync: ✅ PASS\n"
        "Verified Controller Cache Merge: ✅ PASS\n"
        "Official Evidence Wording: ✅ PASS\n"
        "Rumor Intelligence Core: ✅ PASS\n"
        "Rumor IPO + M&A + Other CA: ✅ PASS\n"
        "Rumor Confirmation / Denial Tracker: ✅ PASS\n"
        "Rumor Strength Engine: ✅ PASS\n"
        "Rumor Market Noise Guard: ✅ PASS\n"
        "Rumor Profile No-Realert: ✅ PASS\n"
        "Private IPO Founder/Business Context: ✅ PASS\n"
        "Rumor Baseline Guard: ✅ PASS\n"
        "Rumor Ticker Recovery: ✅ PASS\n"
        "Rumor Entity Resolver: ✅ PASS\n"
        "Multi-Source Entity Prime: ✅ PASS\n"
        "UNKNOWN → Ticker Merge: ✅ PASS\n"
        "Existing UNKNOWN Memory Re-key: ✅ PASS\n"
        "Ambiguous Alias Guard: ✅ PASS\n"
        "Entity Fix No-Realert: ✅ PASS\n"
        "Rumor Party Phrase Guard: ✅ PASS\n"
        "Price % ≠ Rumor Stake Guard: ✅ PASS\n"
        "Invalid Share Count Guard: ✅ PASS\n"
        "Confirmed Rumor Canonical Dedup: ✅ PASS\n"
        "Rumor Profile Deep Fallback Guard: ✅ PASS\n"
        "Source Quality Tiering: ✅ PASS\n"
        "Semantic Copy / Rewrite Detection V2: ✅ PASS\n"
        "Issuer Name Sanitizer V3: ✅ PASS\n"
        "Owner Intelligence V3: ✅ PASS\n"
        "Ownership Role Guard V3: ✅ PASS\n"
        "Unified Indonesian Profile: ✅ PASS\n"
        "Silent Profile Cache Repair: ✅ PASS\n"
        "Weighted Effective Independence V2: ✅ PASS\n"
        "Credible Corroboration Gate: ✅ PASS\n"
        "Owner Intelligence V2: ✅ PASS\n"
        "Safe Major-Holder Fallback: ✅ PASS\n"
        "Private / Pre-IPO Profile Resolver V2: ✅ PASS\n"
        "Indonesian Business Profile: ✅ PASS\n"
        "Rumor Trading Impact Score: ✅ PASS\n"
        "Legacy Rumor State Repair: ✅ PASS\n"
        "Rumored Party Guard: ✅ PASS\n"
        "Owner vs Rumored Party Separation: ✅ PASS\n"
        "Private IPO Profile Output: ✅ PASS\n"
        "Official Confirmation Match: ✅ PASS\n"
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
