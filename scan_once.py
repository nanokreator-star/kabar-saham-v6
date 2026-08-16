"""
Kabar Saham V6.2.3 — Multi-Source Issuer Resolver.

V5.4 remains the intelligence core.
This runner performs one scan cycle, sends new alerts, persists only
article hashes/timestamps, then exits.
"""

import argparse
import asyncio
import json
import os
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


SCHEMA_VERSION = 1
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


def hydrate_issuer_memory_from_command_state():
    if not COMMAND_STATE_PATH.exists():
        return 0
    try:
        data = json.loads(COMMAND_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return 0
    memory = data.get("issuer_aliases") or {}
    if not isinstance(memory, dict):
        return 0
    count = 0
    register = getattr(core, "register_ticker_aliases", None)
    if not callable(register):
        return 0
    for ticker, aliases in memory.items():
        if not isinstance(aliases, list):
            continue
        try:
            if register(ticker, aliases):
                count += 1
        except Exception:
            continue
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

    hydrated = hydrate_issuer_memory_from_command_state()
    if hydrated:
        print(f"Issuer memory hydrated from command_state: {hydrated} ticker(s).")

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
        "eligible": len(candidates),
        "sent": sent_count,
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
        "✅ <b>Kabar Saham V6.2.3 — MULTI-SOURCE ISSUER TEST OK</b>\n\n"
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
