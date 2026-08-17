import asyncio
import hashlib
import base64
import html
import json
import os
import re
import sqlite3
import math
import time
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus, urlparse, urljoin, parse_qs, unquote

import httpx
from dotenv import load_dotenv

try:
    import yfinance as yf
    YFINANCE_AVAILABLE = True
except Exception:
    yf = None
    YFINANCE_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except Exception:
    BeautifulSoup = None
    BS4_AVAILABLE = False

logging.getLogger("yfinance").setLevel(logging.CRITICAL)

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
POLL_MINUTES = int(os.getenv("NEWS_POLL_MINUTES", "10"))
DB_PATH = os.getenv("DB_PATH", "ma_alert.db")
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.json")
RECENT_DAYS = int(os.getenv("RECENT_DAYS", "30"))
AUTO_ALERT_HOURS = int(os.getenv("AUTO_ALERT_HOURS", "48"))
INDONESIA_PRIORITY = os.getenv("INDONESIA_PRIORITY", "1") == "1"
AUTO_ALERT_MIN_PRIORITY = os.getenv("AUTO_ALERT_MIN_PRIORITY", "MEDIUM").strip().upper()

# V5 Decision Support
MARKET_DATA_ENABLED = os.getenv("MARKET_DATA_ENABLED", "1") == "1"
MARKET_CACHE_MINUTES = int(os.getenv("MARKET_CACHE_MINUTES", "15"))
DECISION_LOTS = int(os.getenv("DECISION_LOTS", "1"))
MARKET_ENRICH_LIMIT = int(os.getenv("MARKET_ENRICH_LIMIT", "5"))

MARKET_CACHE = {}

# V5.1 Deep Article Extraction
DEEP_EXTRACTION_ENABLED = os.getenv("DEEP_EXTRACTION_ENABLED", "1") == "1"
DEEP_EXTRACT_LIMIT = int(os.getenv("DEEP_EXTRACT_LIMIT", "3"))
ARTICLE_CACHE_MINUTES = int(os.getenv("ARTICLE_CACHE_MINUTES", "60"))
ARTICLE_TIMEOUT_SECONDS = int(os.getenv("ARTICLE_TIMEOUT_SECONDS", "15"))
MAX_ARTICLE_CHARS = int(os.getenv("MAX_ARTICLE_CHARS", "30000"))

ARTICLE_CACHE = {}

# V5.2 Source Resolver
SOURCE_RESOLVER_ENABLED = os.getenv("SOURCE_RESOLVER_ENABLED", "1") == "1"
RESOLVER_MAX_CANDIDATES = int(os.getenv("RESOLVER_MAX_CANDIDATES", "8"))
RESOLVER_SEARCH_FALLBACK = os.getenv("RESOLVER_SEARCH_FALLBACK", "1") == "1"
RESOLVER_CACHE_MINUTES = int(os.getenv("RESOLVER_CACHE_MINUTES", "180"))
RESOLVER_TITLE_MIN_SCORE = int(os.getenv("RESOLVER_TITLE_MIN_SCORE", "35"))

RESOLVER_CACHE = {}

# V5.3 Safe Google News Decoder Core
GOOGLE_DECODER_ENABLED = os.getenv("GOOGLE_DECODER_ENABLED", "1") == "1"
GOOGLE_DECODER_TIMEOUT_SECONDS = int(
    os.getenv("GOOGLE_DECODER_TIMEOUT_SECONDS", "12")
)
GOOGLE_DECODER_MAX_TOKEN_CHARS = int(
    os.getenv("GOOGLE_DECODER_MAX_TOKEN_CHARS", "4096")
)
GOOGLE_DECODER_CACHE_MINUTES = int(
    os.getenv("GOOGLE_DECODER_CACHE_MINUTES", "180")
)
GOOGLE_DECODER_BATCH_ENABLED = (
    os.getenv("GOOGLE_DECODER_BATCH_ENABLED", "1") == "1"
)

GOOGLE_DECODER_CACHE = {}

# V5.3.1 Live Batchexecute Parser Fix
DECODER_DEBUG_ENABLED = os.getenv("DECODER_DEBUG_ENABLED", "1") == "1"
DECODER_MAX_RESPONSE_CHARS = int(
    os.getenv("DECODER_MAX_RESPONSE_CHARS", "250000")
)
DECODER_MAX_URL_CANDIDATES = int(
    os.getenv("DECODER_MAX_URL_CANDIDATES", "20")
)
DECODER_MAX_NESTED_JSON_DEPTH = int(
    os.getenv("DECODER_MAX_NESTED_JSON_DEPTH", "5")
)


# V5.3.2 Dynamic Google Request Protocol
DYNAMIC_PROTOCOL_ENABLED = os.getenv("DYNAMIC_PROTOCOL_ENABLED", "1") == "1"
DYNAMIC_PARAMS_TIMEOUT_SECONDS = int(
    os.getenv("DYNAMIC_PARAMS_TIMEOUT_SECONDS", "12")
)
DYNAMIC_PARAMS_CACHE_MINUTES = int(
    os.getenv("DYNAMIC_PARAMS_CACHE_MINUTES", "180")
)
DYNAMIC_PROTOCOL_FALLBACK_STATIC = (
    os.getenv("DYNAMIC_PROTOCOL_FALLBACK_STATIC", "1") == "1"
)
DYNAMIC_PARAMS_HTML_MAX_CHARS = int(
    os.getenv("DYNAMIC_PARAMS_HTML_MAX_CHARS", "500000")
)

DYNAMIC_PARAMS_CACHE = {}

# V5.4 Publisher Direct Resolver
PUBLISHER_DIRECT_ENABLED = os.getenv("PUBLISHER_DIRECT_ENABLED", "1") == "1"
PUBLISHER_DIRECT_MIN_SCORE = int(
    os.getenv("PUBLISHER_DIRECT_MIN_SCORE", "70")
)
PUBLISHER_DIRECT_CACHE_MINUTES = int(
    os.getenv("PUBLISHER_DIRECT_CACHE_MINUTES", "180")
)
PUBLISHER_DIRECT_TIMEOUT_SECONDS = int(
    os.getenv("PUBLISHER_DIRECT_TIMEOUT_SECONDS", "12")
)
PUBLISHER_DIRECT_MAX_CANDIDATES = int(
    os.getenv("PUBLISHER_DIRECT_MAX_CANDIDATES", "12")
)
PUBLISHER_INTERNAL_SEARCH_ENABLED = (
    os.getenv("PUBLISHER_INTERNAL_SEARCH_ENABLED", "1") == "1"
)
PUBLISHER_PUBLIC_SEARCH_ENABLED = (
    os.getenv("PUBLISHER_PUBLIC_SEARCH_ENABLED", "1") == "1"
)


PUBLISHER_DIRECT_CACHE = {}

# ============================================================
# V6.2 Official Source Priority
# ============================================================

OFFICIAL_SOURCE_PRIORITY_ENABLED = (
    os.getenv("OFFICIAL_SOURCE_PRIORITY_ENABLED", "1") == "1"
)
OFFICIAL_DISCOVERY_ENABLED = (
    os.getenv("OFFICIAL_DISCOVERY_ENABLED", "1") == "1"
)
OFFICIAL_DISCOVERY_QUERY_LIMIT = max(
    0,
    min(10, int(os.getenv("OFFICIAL_DISCOVERY_QUERY_LIMIT", "6"))),
)
OFFICIAL_SOURCE_SCORE_BOOST = max(
    0,
    min(20, int(os.getenv("OFFICIAL_SOURCE_SCORE_BOOST", "10"))),
)
OFFICIAL_ON_DEMAND_ENABLED = (
    os.getenv("OFFICIAL_ON_DEMAND_ENABLED", "1") == "1"
)
OFFICIAL_ON_DEMAND_TIMEOUT_SECONDS = max(
    5,
    min(30, int(os.getenv("OFFICIAL_ON_DEMAND_TIMEOUT_SECONDS", "18"))),
)

# These discovery searches are supplemental. They run through the existing
# Google News RSS parser, so no new third-party package/API key is required.
OFFICIAL_DISCOVERY_QUERIES = [
    'site:idx.co.id "penawaran tender wajib"',
    'site:idx.co.id ("perubahan pengendali" OR akuisisi)',
    'site:idx.co.id (HMETD OR "rights issue")',
    'site:e-ipo.co.id ("penawaran umum perdana" OR bookbuilding OR prospektus)',
    'site:web.ksei.co.id (HMETD OR akuisisi OR merger)',
    'site:ojk.go.id ("penawaran tender wajib" OR HMETD)',
]

# PRIMARY means an event/disclosure venue. REGULATOR remains authoritative,
# but is intentionally ranked below event-level disclosure venues.
OFFICIAL_SOURCE_RULES = [
    {
        "authority": "IDX",
        "kind": "PRIMARY",
        "rank": 5,
        "domains": ("idx.co.id", "www.idx.co.id", "www2.idx.co.id"),
        "aliases": (
            "bursa efek indonesia",
            "indonesia stock exchange",
        ),
        "exact_aliases": ("idx",),
    },
    {
        "authority": "e-IPO",
        "kind": "PRIMARY",
        "rank": 5,
        "domains": ("e-ipo.co.id", "www.e-ipo.co.id"),
        "aliases": (
            "electronic indonesia public offering",
            "e-ipo.co.id",
        ),
        "exact_aliases": ("e-ipo",),
    },
    {
        "authority": "KSEI",
        "kind": "PRIMARY",
        "rank": 4,
        "domains": ("ksei.co.id", "web.ksei.co.id"),
        "aliases": (
            "kustodian sentral efek indonesia",
            "pt kustodian sentral efek indonesia",
        ),
        "exact_aliases": ("ksei",),
    },
    {
        "authority": "OJK",
        "kind": "REGULATOR",
        "rank": 3,
        "domains": ("ojk.go.id", "www.ojk.go.id"),
        "aliases": (
            "otoritas jasa keuangan",
        ),
        "exact_aliases": ("ojk",),
    },
]

OFFICIAL_SEARCH_CACHE = {}
OFFICIAL_SEARCH_CACHE_MINUTES = max(
    5,
    int(os.getenv("OFFICIAL_SEARCH_CACHE_MINUTES", "120")),
)

# ============================================================
# V6.6.1 — Reliability & Verified Cache Guard
# ============================================================

HTTP_RETRY_ATTEMPTS = max(
    1,
    min(5, int(os.getenv("HTTP_RETRY_ATTEMPTS", "3"))),
)
HTTP_RETRY_BASE_SECONDS = max(
    0.25,
    min(5.0, float(os.getenv("HTTP_RETRY_BASE_SECONDS", "1.0"))),
)
TELEGRAM_RETRY_ATTEMPTS = max(
    1,
    min(5, int(os.getenv("TELEGRAM_RETRY_ATTEMPTS", "3"))),
)
VERIFIED_OFFICIAL_CACHE_ENABLED = (
    os.getenv("VERIFIED_OFFICIAL_CACHE_ENABLED", "1") == "1"
)
VERIFIED_OFFICIAL_CACHE_TTL_DAYS = max(
    1,
    min(180, int(os.getenv("VERIFIED_OFFICIAL_CACHE_TTL_DAYS", "30"))),
)
VERIFIED_OFFICIAL_MAX_PER_TICKER = max(
    1,
    min(8, int(os.getenv("VERIFIED_OFFICIAL_MAX_PER_TICKER", "5"))),
)

VERIFIED_OFFICIAL_CACHE = {}

# ============================================================
# V6.6.2 — Entity Role Guard + Indonesia Classification Guard
# ============================================================

ENTITY_ROLE_GUARD_ENABLED = (
    os.getenv("V662_ENTITY_ROLE_GUARD_ENABLED", "1") == "1"
)
INDONESIA_CLASSIFICATION_GUARD_ENABLED = (
    os.getenv("V662_INDONESIA_CLASSIFICATION_GUARD_ENABLED", "1") == "1"
)
LOW_CONFIDENCE_ROLE_SUPPRESSION_ENABLED = (
    os.getenv("V662_LOW_CONFIDENCE_ROLE_SUPPRESSION", "1") == "1"
)

# ============================================================
# V6.6.1 — Event Lifecycle & Corporate Action Timeline
# ============================================================
EVENT_LIFECYCLE_ENABLED = (
    os.getenv("EVENT_LIFECYCLE_ENABLED", "1") == "1"
)
TIMELINE_DEEP_ENABLED = (
    os.getenv("TIMELINE_DEEP_ENABLED", "1") == "1"
)

TIMELINE_NOISE_GUARD_ENABLED = (
    os.getenv("TIMELINE_NOISE_GUARD_ENABLED", "1") == "1"
)
TIMELINE_TIMEZONE_NAME = os.getenv(
    "TIMELINE_TIMEZONE_NAME",
    "Asia/Jakarta",
).strip() or "Asia/Jakarta"

# ============================================================
# V6.6.1 — Smart Watchlist & Milestone Alert
# ============================================================
SMART_WATCHLIST_ENABLED = (
    os.getenv("SMART_WATCHLIST_ENABLED", "1") == "1"
)
SMART_LIFECYCLE_ALERT_ENABLED = (
    os.getenv("SMART_LIFECYCLE_ALERT_ENABLED", "1") == "1"
)
MILESTONE_ALERT_ENABLED = (
    os.getenv("MILESTONE_ALERT_ENABLED", "1") == "1"
)

# ============================================================
# V6.2.1 Ticker Recovery + Issuer Name Resolver
# ============================================================

TICKER_RECOVERY_ENABLED = (
    os.getenv("TICKER_RECOVERY_ENABLED", "1") == "1"
)
TICKER_RECOVERY_QUERY_LIMIT = max(
    1, min(8, int(os.getenv("TICKER_RECOVERY_QUERY_LIMIT", "6")))
)
TICKER_RECOVERY_CACHE_MINUTES = max(
    5, int(os.getenv("TICKER_RECOVERY_CACHE_MINUTES", "90"))
)
ISSUER_ALIAS_PROPAGATION_ENABLED = (
    os.getenv("ISSUER_ALIAS_PROPAGATION_ENABLED", "1") == "1"
)
ISSUER_ALIAS_MIN_CHARS = max(
    6, int(os.getenv("ISSUER_ALIAS_MIN_CHARS", "8"))
)

# V6.2.2 — resolve issuer identity from the full publisher article, then
# correlate official disclosures conservatively.
DEEP_ISSUER_RESOLVER_ENABLED = (
    os.getenv("DEEP_ISSUER_RESOLVER_ENABLED", "1") == "1"
)
MONEY_UNIT_GUARD_ENABLED = (
    os.getenv("MONEY_UNIT_GUARD_ENABLED", "1") == "1"
)
OFFICIAL_CORRELATION_MIN_SCORE = max(
    4,
    min(15, int(os.getenv("OFFICIAL_CORRELATION_MIN_SCORE", "7"))),
)
OFFICIAL_CORRELATION_DAYS = max(
    7,
    int(os.getenv("OFFICIAL_CORRELATION_DAYS", "120")),
)

# ============================================================
# V6.6.1 — Multi-Source Issuer Resolver
# ============================================================

MULTI_SOURCE_ISSUER_RESOLVER_ENABLED = (
    os.getenv("MULTI_SOURCE_ISSUER_RESOLVER_ENABLED", "1") == "1"
)
MARKET_ISSUER_LOOKUP_ENABLED = (
    os.getenv("MARKET_ISSUER_LOOKUP_ENABLED", "1") == "1"
)
RELATED_ISSUER_DISCOVERY_ENABLED = (
    os.getenv("RELATED_ISSUER_DISCOVERY_ENABLED", "1") == "1"
)
OFFICIAL_ISSUER_TRIANGULATION_ENABLED = (
    os.getenv("OFFICIAL_ISSUER_TRIANGULATION_ENABLED", "1") == "1"
)
ISSUER_IDENTITY_QUERY_LIMIT = max(
    2,
    min(8, int(os.getenv("ISSUER_IDENTITY_QUERY_LIMIT", "6"))),
)
ISSUER_TRIANGULATION_MAX_CANDIDATES = max(
    1,
    min(10, int(os.getenv("ISSUER_TRIANGULATION_MAX_CANDIDATES", "6"))),
)
ISSUER_IDENTITY_CACHE_MINUTES = max(
    5,
    int(os.getenv("ISSUER_IDENTITY_CACHE_MINUTES", "180")),
)
ISSUER_PAIR_VALIDATION_DAYS = max(
    7,
    int(os.getenv("ISSUER_PAIR_VALIDATION_DAYS", "180")),
)

TICKER_RECOVERY_CACHE = {}
TICKER_ALIAS_CACHE = {}
ISSUER_IDENTITY_CACHE = {}
MARKET_ISSUER_CACHE = {}

TICKER_RECOVERY_QUERY_TEMPLATES = [
    '"{ticker}" saham',
    '"{ticker}" emiten',
    '"{ticker}" "tender offer"',
    '"{ticker}" akuisisi',
    '"{ticker}" pengendali',
    '"{ticker}" "rights issue"',
    '"{ticker}" HMETD',
    '"{ticker}" IPO',
]

ISSUER_IDENTITY_QUERY_TEMPLATES = [
    '"{ticker}" "Tbk"',
    '"{ticker}" "PT"',
    '"{ticker}" "kode emiten"',
    '"{ticker}" "nama emiten"',
    '"{ticker}" perusahaan',
    '"{ticker}" saham emiten',
]

if not BOT_TOKEN:
    raise SystemExit("TELEGRAM_BOT_TOKEN belum diisi di file .env.")

TG_BASE = f"https://api.telegram.org/bot{BOT_TOKEN}"
GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?"
    "q={query}&hl=id&gl=ID&ceid=ID:id"
)

# ============================================================
# EVENT TAXONOMY
# ============================================================

CORPORATE_ACTION_KEYWORDS = {
    "AKUISISI": [
        "akuisisi", "mengakuisisi", "diakuisisi",
        "acquisition", "acquire", "acquires", "acquired",
        "buyout", "ambil alih", "pengambilalihan",
    ],
    "TAKEOVER": [
        "takeover", "take over", "pengendali baru",
        "perubahan pengendali", "controlling stake",
        "change of control",
    ],
    "TENDER OFFER": [
        "tender offer", "penawaran tender", "tender wajib",
        "mandatory tender offer",
    ],
    "PEMBELIAN SAHAM": [
        "membeli saham", "pembelian saham",
        "stake purchase", "purchase of shares",
        "equity stake",
    ],
    "MERGER": [
        "merger", "penggabungan usaha",
        "business combination",
    ],
    "RIGHTS ISSUE": [
        "rights issue", "right issue", "hmetd",
        "hak memesan efek terlebih dahulu",
        "penambahan modal dengan hmetd",
        "pmhmetd", "rasio rights",
        "harga pelaksanaan rights",
    ],
}

# IPO V4.1 dibuat lebih ketat.
IPO_STRONG_SIGNALS = [
    "initial public offering",
    "penawaran umum perdana",
    "bookbuilding",
    "book building",
    "masa penawaran umum",
    "penawaran awal",
    "listing perdana",
    "pencatatan saham perdana",
    "prospektus awal",
    "prospektus ipo",
    "calon emiten",
    "harga ipo",
    "harga penawaran",
    "saham yang ditawarkan",
    "tanggal listing",
    "jadwal ipo",
]

IPO_WEAK_SIGNALS = [
    "ipo",
]

IPO_NEGATIVE_PHRASES = [
    "bukan ipo",
    "tidak ipo",
    "tidak akan ipo",
    "belum ipo",
    "batal ipo",
    "membatalkan ipo",
    "urung ipo",
    "gagal ipo",
    "bukan penawaran umum perdana",
    "opini ipo",
    "wacana ipo",
    "isu ipo",
]

# V4.2: buang berita yang hanya membahas saham SETELAH IPO atau rekap pasar IPO.
IPO_POST_LISTING_PHRASES = [
    "pasca ipo",
    "setelah ipo",
    "usai ipo",
    "sejak ipo",
    "di bawah harga ipo",
    "di atas harga ipo",
    "jeblok dari harga ipo",
    "jeblok di bawah harga ipo",
    "turun dari harga ipo",
    "naik dari harga ipo",
    "saham ipo jeblok",
    "saham ipo naik",
    "saham ipo turun",
    "kinerja saham ipo",
]

IPO_RECAP_PHRASES = [
    "berapa ipo",
    "jumlah ipo",
    "total ipo",
    "rekap ipo",
    "daftar ipo",
    "baru 7 ipo",
    "baru 8 ipo",
    "baru 9 ipo",
    "ipo hingga juli",
    "ipo hingga agustus",
    "ipo sepanjang tahun",
    "ipo tahun ini",
    "tren ipo",
    "pasar ipo",
    "saham ipo terbaik",
    "saham ipo terburuk",
]

GENERAL_NEGATIVE_PATTERNS = [
    "prediksi harga",
    "analisis teknikal",
    "rekomendasi teknikal",
    "dividen",
    "stock split",
    "buyback",
]

INDONESIA_SOURCE_HINTS = [
    "kontan",
    "bisnis.com",
    "cnbc indonesia",
    "detikfinance",
    "bareksa",
    "emitennews",
    "pasardana",
    "pintarsaham",
    "idx channel",
    "mikir duit",
    "tempo",
    "antaranews",
    "kompas",
    "katadata",
    "investor.id",
    "idnfinancials",
]

INDONESIA_TEXT_HINTS = [
    " indonesia",
    "indonesia ",
    " pt ",
    " tbk",
    " idx",
    " bei ",
    "bursa efek indonesia",
    "rupiah",
    "rp ",
    "bumn",
    "emiten",
    "hmetd",
    "tender wajib",
]

TICKER_STOPWORDS = {
    "IPO", "BEI", "IDX", "HMETD", "RIGHT", "MTO",
    "CEO", "CFO", "USD", "IDR", "RUPS", "RUPSLB",
    "PMHMETD", "ASEAN", "BUMN", "OJK", "ETF",
    "SPA", "MOU", "RI", "NEWS",
}

# ============================================================
# CONFIG / DB
# ============================================================

def load_config():
    path = Path(CONFIG_PATH)
    if not path.exists():
        raise SystemExit(f"Config tidak ditemukan: {CONFIG_PATH}")
    return json.loads(path.read_text(encoding="utf-8"))


CONFIG = load_config()


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            chat_id INTEGER PRIMARY KEY,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sent_articles (
            article_key TEXT PRIMARY KEY,
            sent_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bot_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def register_chat(chat_id):
    conn = db()
    conn.execute(
        "INSERT OR IGNORE INTO subscribers(chat_id, created_at) VALUES (?, ?)",
        (chat_id, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def subscriber_ids():
    conn = db()
    rows = conn.execute("SELECT chat_id FROM subscribers").fetchall()
    conn.close()
    return [row[0] for row in rows]


def was_sent(key):
    conn = db()
    row = conn.execute(
        "SELECT 1 FROM sent_articles WHERE article_key=?",
        (key,),
    ).fetchone()
    conn.close()
    return bool(row)


def mark_sent(key):
    conn = db()
    conn.execute(
        "INSERT OR IGNORE INTO sent_articles(article_key, sent_at) VALUES (?, ?)",
        (key, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    conn.close()


def get_state(key, default=None):
    conn = db()
    row = conn.execute(
        "SELECT value FROM bot_state WHERE key=?",
        (key,),
    ).fetchone()
    conn.close()
    return row[0] if row else default


def set_state(key, value):
    conn = db()
    conn.execute(
        "INSERT OR REPLACE INTO bot_state(key, value) VALUES (?, ?)",
        (key, str(value)),
    )
    conn.commit()
    conn.close()


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


def strip_html(text):
    text = re.sub(r"<[^>]+>", " ", text or "")
    return normalize(html.unescape(text))


def article_key(title, link):
    raw = f"{normalize(title).lower()}|{normalize(link).lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_date(value):
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def is_recent_days(dt):
    if dt is None:
        return False
    return dt >= datetime.now(timezone.utc) - timedelta(days=RECENT_DAYS)


def is_recent_hours(dt):
    if dt is None:
        return False
    return dt >= datetime.now(timezone.utc) - timedelta(hours=AUTO_ALERT_HOURS)


# ============================================================
# IPO FILTER V4.1
# ============================================================

def has_negative_ipo_context(text):
    low = text.lower()
    return any(phrase in low for phrase in IPO_NEGATIVE_PHRASES)


def is_post_ipo_or_recap(text):
    low = text.lower()
    return (
        any(phrase in low for phrase in IPO_POST_LISTING_PHRASES)
        or any(phrase in low for phrase in IPO_RECAP_PHRASES)
    )


def has_strong_ipo_signal(text):
    low = text.lower()
    return any(signal in low for signal in IPO_STRONG_SIGNALS)


def has_weak_ipo_signal(text):
    low = f" {text.lower()} "
    return any(f" {signal} " in low for signal in IPO_WEAK_SIGNALS)


def is_valid_ipo(text):
    # V4.2: false positive, berita pasca-listing, dan rekap IPO dibuang.
    if has_negative_ipo_context(text) or is_post_ipo_or_recap(text):
        return False

    # Strong transaction-stage signals langsung valid.
    if has_strong_ipo_signal(text):
        return True

    # Kata "IPO" saja tidak cukup. Harus punya >=3 indikator proses IPO.
    if has_weak_ipo_signal(text):
        supporting = [
            "calon emiten",
            "penawaran",
            "listing",
            "bookbuilding",
            "prospektus",
            "underwriter",
            "penjamin emisi",
            "harga penawaran",
            "saham ditawarkan",
            "masa penawaran",
            "tanggal efektif",
            "e-ipo",
        ]
        hit = sum(1 for x in supporting if x in text.lower())
        return hit >= 3

    return False


# ============================================================
# EVENT DETECTION
# ============================================================

def event_type(text):
    low = f" {text.lower()} "

    for preferred in ("RIGHTS ISSUE", "TENDER OFFER", "TAKEOVER"):
        if any(word in low for word in CORPORATE_ACTION_KEYWORDS[preferred]):
            return preferred

    if is_valid_ipo(text):
        return "IPO"

    for event in ("AKUISISI", "PEMBELIAN SAHAM", "MERGER"):
        if any(word in low for word in CORPORATE_ACTION_KEYWORDS[event]):
            return event

    return None


def relevance_score(text, event):
    low = f" {text.lower()} "
    score = 0

    if event:
        score += 10

    for word in [
        "saham", "stake", "pengendali", "perusahaan",
        "emiten", "tbk", "target", "hmetd",
        "tender", "listing", "bookbuilding",
        "pemegang saham", "prospektus",
    ]:
        if word in low:
            score += 2

    if any(bad in low for bad in GENERAL_NEGATIVE_PATTERNS):
        score -= 4

    if event == "IPO" and has_negative_ipo_context(text):
        score -= 25

    return score


# ============================================================
# EXTRACTION: TICKER
# ============================================================

def extract_ticker(title, text, geo):
    candidates = []

    patterns = [
        r"\(([A-Z]{4})\)",
        r"\bsaham\s+([A-Z]{4})\b",
        r"\b(?:ticker|kode saham|kode emiten)\s*[:\-]?\s*([A-Z]{4})\b",
        r"\bemiten\s+([A-Z]{4})\b",
    ]

    for pattern in patterns:
        for match in re.findall(pattern, text):
            t = match.upper()
            if t not in TICKER_STOPWORDS:
                candidates.append(t)

    # V4.1: ticker di awal judul, contoh "CBRE Rencanakan Rights Issue..."
    first_token = normalize(title).split(" ")[0] if title else ""
    first_token = re.sub(r"[^A-Z]", "", first_token.upper())

    if (
        len(first_token) == 4
        and first_token not in TICKER_STOPWORDS
        and (
            geo.startswith("INDONESIA")
            or "tbk" in text.lower()
            or "emiten" in text.lower()
            or "bei" in text.lower()
        )
    ):
        candidates.insert(0, first_token)

    return candidates[0] if candidates else None


# ============================================================
# EXTRACTION: MONEY / PERCENT / RATIO / PRICE
# ============================================================

def extract_percentages(text):
    matches = re.findall(
        r"(?<!\d)(\d{1,3}(?:[.,]\d{1,2})?)\s*%",
        text,
    )
    cleaned = []

    for value in matches:
        try:
            number = float(value.replace(",", "."))
            if 0 < number <= 100:
                cleaned.append(number)
        except ValueError:
            pass

    return cleaned


def format_pct(value):
    if float(value).is_integer():
        return f"{int(value)}%"
    return f"{value:.2f}".replace(".", ",") + "%"


MONEY_MAGNITUDE_MAP = {
    "ribu": "ribu",
    "rb": "ribu",
    "juta": "juta",
    "jt": "juta",
    "million": "million",
    "mn": "million",
    "miliar": "miliar",
    "milyar": "miliar",
    "billion": "billion",
    "bn": "billion",
    "triliun": "triliun",
    "trillion": "trillion",
    "tn": "trillion",
}

MONEY_AMOUNT_CONTEXT = (
    "nilai transaksi",
    "nilai pengambilalihan",
    "nilai akuisisi",
    "nilai pembelian",
    "total transaksi",
    "nilai investasi",
    "dana yang dihimpun",
    "dana hasil",
    "dana segar",
    "meraup dana",
    "menghimpun dana",
    "senilai",
    "sebesar",
    "mencapai",
    "total nilai",
)

MONEY_PRICE_CONTEXT = (
    "harga saham",
    "harga pasar",
    "harga tender",
    "harga penawaran",
    "harga pelaksanaan",
    "harga tebus",
    "harga exercise",
    "target harga",
    "ditutup di",
    "ditutup pada",
    "per saham",
    "/saham",
    "level harga",
)

MONEY_TOKEN_RE = re.compile(
    r"(?P<currency>Rp|IDR|US\$|USD)\s*"
    r"(?P<number>[0-9][0-9.,]*)"
    r"(?:\s*(?P<unit>triliun|trillion|miliar|milyar|billion|juta|million|ribu|tn|bn|mn|jt|rb))?",
    flags=re.I,
)


def _money_context_window(text, start, end, radius=80):
    return normalize(text[max(0, start-radius): min(len(text), end+radius)]).lower()


def _normalize_money_candidate(currency, number, unit):
    currency_raw = str(currency or "").upper().replace(" ", "")
    if currency_raw == "RP":
        prefix = "Rp"
    elif currency_raw == "US$":
        prefix = "US$"
    else:
        prefix = currency_raw

    unit_key = str(unit or "").lower().strip()
    normalized_unit = MONEY_MAGNITUDE_MAP.get(unit_key, unit_key)
    suffix = f" {normalized_unit}" if normalized_unit else ""
    return normalize(f"{prefix}{number}{suffix}")


def _money_candidate_score(text, match, event=None):
    raw_number = match.group("number")
    unit = match.group("unit")
    parsed = parse_localized_number(raw_number)
    context = _money_context_window(text, match.start(), match.end())

    explicit_unit = bool(unit)
    amount_context = any(token in context for token in MONEY_AMOUNT_CONTEXT)
    price_context = any(token in context for token in MONEY_PRICE_CONTEXT)

    # Explicit million/billion/trillion/ribu wording is strong evidence of an
    # amount, while a small unit-less Rupiah figure is normally a share price.
    if MONEY_UNIT_GUARD_ENABLED:
        if not explicit_unit:
            if parsed is None:
                return None
            if price_context:
                return None
            if parsed < 1_000_000:
                return None
            if not amount_context and parsed < 100_000_000:
                return None

    score = 0
    if explicit_unit:
        score += 6
    if amount_context:
        score += 6
    if price_context:
        score -= 7
    if parsed is not None and parsed >= 1_000_000:
        score += 2

    # Corporate-action-specific amount terms get extra priority.
    low = context
    if event in ("TENDER OFFER", "TAKEOVER", "AKUISISI", "PEMBELIAN SAHAM"):
        if any(x in low for x in ("transaksi", "pengambilalihan", "akuisisi", "pembelian")):
            score += 2
    elif event == "RIGHTS ISSUE":
        if any(x in low for x in ("dana", "hm etd", "hmetd", "rights issue")):
            score += 2
    elif event == "IPO":
        if any(x in low for x in ("dana", "ipo", "penawaran umum")):
            score += 2

    return score


def extract_money(text, event=None):
    """Return likely transaction/fund values, not ordinary per-share prices.

    V6.2.2 deliberately rejects small Rupiah values without a magnitude unit
    (for example Rp294 or Rp700) from the generic transaction-value bucket.
    Per-share/tender/exercise prices have dedicated extractors.
    """
    candidates = []
    seen = set()

    for match in MONEY_TOKEN_RE.finditer(text or ""):
        score = _money_candidate_score(text, match, event=event)
        if score is None:
            continue

        value = _normalize_money_candidate(
            match.group("currency"),
            match.group("number"),
            match.group("unit"),
        )
        key = money_key(value) if "money_key" in globals() else re.sub(r"\s+", "", value.lower())
        if key in seen:
            continue
        seen.add(key)
        candidates.append((score, match.start(), value))

    # Prefer contextually strong transaction/fund amounts. Stable source order
    # is retained as a tie breaker.
    candidates.sort(key=lambda x: (-x[0], x[1]))
    return [value for _, _, value in candidates[:5]]


def sanitize_money_values(values):
    kept = []
    removed = []
    for raw in values or []:
        value = normalize(str(raw or ""))
        match = MONEY_TOKEN_RE.fullmatch(value)
        if not match:
            kept.append(value)
            continue
        unit = match.group("unit")
        parsed = parse_localized_number(match.group("number"))
        if MONEY_UNIT_GUARD_ENABLED and not unit and (parsed is None or parsed < 1_000_000):
            removed.append(value)
            continue
        normalized = _normalize_money_candidate(
            match.group("currency"), match.group("number"), unit
        )
        if normalized not in kept:
            kept.append(normalized)
    return kept, removed


def money_guard_lines(article):
    removed = article.get("money_guard_removed") or []
    if not removed:
        return []
    preview = ", ".join(html.escape(str(x)) for x in removed[:3])
    return [f"🛡️ <b>Money Unit Guard:</b> ✅ blocked ambiguous {preview}"]

def money_key(value):
    # Membandingkan Rp50 dan Rp 50 secara konsisten.
    return re.sub(r"\s+", "", (value or "").lower())


def remove_price_duplicates(money_values, execution_price=None, price_range=None):
    """
    Harga pelaksanaan/right price bukan otomatis nilai dana.
    V4.2 menghapus angka harga per saham dari bucket 'Nilai/Dana'.
    """
    blocked = set()

    if execution_price:
        blocked.add(money_key(execution_price))

    if price_range:
        # Contoh Rp150–Rp180 -> block Rp150 dan Rp180 dari 'Dana/Nilai'.
        for number in re.findall(r"Rp\s*([\d.,]+)", price_range, flags=re.I):
            blocked.add(money_key(f"Rp{number}"))

    return [
        value for value in money_values
        if money_key(value) not in blocked
    ]


def extract_ratio(text):
    m = re.search(r"\b(\d+)\s*:\s*(\d+)\b", text)
    if m:
        return f"{m.group(1)}:{m.group(2)}"

    m = re.search(
        r"\bsetiap\s+(\d+)\s+saham[^,.]{0,60}?(\d+)\s+hm(?:etd|ed)\b",
        text,
        flags=re.I,
    )
    if m:
        return f"{m.group(1)}:{m.group(2)}"

    return None


def extract_price_range(text):
    m = re.search(
        r"Rp\s*([\d.,]+)\s*(?:-|–|sampai|hingga)\s*(?:Rp\s*)?([\d.,]+)",
        text,
        flags=re.I,
    )
    if m:
        return f"Rp{m.group(1)}–Rp{m.group(2)}"
    return None


def extract_execution_price(text):
    patterns = [
        r"harga pelaksanaan[^Rp]{0,30}Rp\s*([\d.,]+)",
        r"harga tebus[^Rp]{0,30}Rp\s*([\d.,]+)",
        r"harga exercise[^Rp]{0,30}Rp\s*([\d.,]+)",
    ]

    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return f"Rp{m.group(1)}"

    return None


# ============================================================
# V5 DECISION-SUPPORT EXTRACTORS
# ============================================================

def parse_localized_number(value):
    """
    Parse angka gaya Indonesia/internasional secara best-effort.
    Contoh:
    1.250 -> 1250
    1,250 -> 1250
    1,5 -> 1.5
    1.250,50 -> 1250.50
    """
    if value is None:
        return None

    s = str(value).strip()
    s = re.sub(r"[^0-9,.\-]", "", s)

    if not s:
        return None

    negative = s.startswith("-")
    s = s.lstrip("-")

    if "." in s and "," in s:
        # Separator terakhir diasumsikan desimal.
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) == 3:
            s = "".join(parts)
        elif len(parts) == 2:
            s = parts[0] + "." + parts[1]
        else:
            s = "".join(parts)
    elif "." in s:
        parts = s.split(".")
        if len(parts) == 2 and len(parts[1]) == 3:
            s = "".join(parts)
        elif len(parts) > 2:
            s = "".join(parts)

    try:
        n = float(s)
        return -n if negative else n
    except Exception:
        return None


def rupiah_to_float(value):
    if not value:
        return None
    return parse_localized_number(value)


def human_count_to_float(value):
    if not value:
        return None

    low = value.lower()
    number_match = re.search(r"([\d.,]+)", low)

    if not number_match:
        return None

    number = parse_localized_number(number_match.group(1))

    if number is None:
        return None

    multiplier = 1

    if "triliun" in low or re.search(r"\b(?:tn|trillion)\b", low):
        multiplier = 1_000_000_000_000
    elif "miliar" in low or "milyar" in low or re.search(r"\b(?:bn|billion)\b", low):
        multiplier = 1_000_000_000
    elif "juta" in low or re.search(r"\b(?:jt|mn|million)\b", low):
        multiplier = 1_000_000
    elif "ribu" in low or re.search(r"\brb\b", low):
        multiplier = 1_000

    return number * multiplier


def parse_ratio_values(ratio):
    if not ratio:
        return None, None

    m = re.match(r"\s*(\d+)\s*:\s*(\d+)\s*$", ratio)

    if not m:
        return None, None

    old_shares = int(m.group(1))
    new_shares = int(m.group(2))

    if old_shares <= 0 or new_shares <= 0:
        return None, None

    return old_shares, new_shares


def extract_ipo_single_price(text):
    patterns = [
        r"harga penawaran[^Rp]{0,35}Rp\s*([\d.,]+)",
        r"harga ipo[^Rp]{0,35}Rp\s*([\d.,]+)",
        r"ditawarkan[^Rp]{0,35}Rp\s*([\d.,]+)\s*(?:per saham|\/saham)?",
    ]

    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return f"Rp{m.group(1)}"

    return None


def extract_tender_price(text):
    patterns = [
        r"harga penawaran tender(?: wajib)?[^Rp]{0,50}Rp\s*([\d.,]+)",
        r"harga tender(?: wajib)?[^Rp]{0,50}Rp\s*([\d.,]+)",
        r"tender offer[^Rp]{0,70}Rp\s*([\d.,]+)",
        r"penawaran tender(?: wajib)?[^Rp]{0,70}Rp\s*([\d.,]+)\s*(?:per saham|\/saham)?",
    ]

    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            return f"Rp{m.group(1)}"

    return None


def extract_underwriter(text):
    patterns = [
        r"(?:underwriter|penjamin pelaksana emisi efek|penjamin emisi)\s*[:\-]?\s*([A-Z][A-Za-z0-9&.,()\- ]{3,90})",
    ]

    for p in patterns:
        m = re.search(p, text)
        if m:
            value = normalize(m.group(1))
            value = re.split(r"[.;]|\s+-\s+", value)[0]
            return value[:90]

    return None


def classify_use_of_funds(text):
    low = text.lower()
    uses = []

    mapping = [
        ("EKSPANSI / CAPEX", [
            "ekspansi", "belanja modal", "capital expenditure",
            "capex", "pembangunan pabrik", "penambahan kapasitas",
        ]),
        ("MODAL KERJA", [
            "modal kerja", "working capital",
        ]),
        ("PELUNASAN UTANG", [
            "pelunasan utang", "membayar utang", "bayar utang",
            "refinancing", "refinance",
        ]),
        ("AKUISISI / INVESTASI", [
            "akuisisi", "penyertaan modal", "investasi pada anak usaha",
            "setoran modal",
        ]),
        ("PENGEMBANGAN USAHA", [
            "pengembangan usaha", "pengembangan bisnis",
        ]),
    ]

    for label, words in mapping:
        if any(w in low for w in words):
            uses.append(label)

    return uses[:4]


def format_rupiah_number(value):
    if value is None:
        return "—"

    value = float(value)
    abs_v = abs(value)

    if abs_v >= 1_000_000_000_000:
        return f"Rp{value/1_000_000_000_000:.2f} T"
    if abs_v >= 1_000_000_000:
        return f"Rp{value/1_000_000_000:.2f} M"
    if abs_v >= 1_000_000:
        return f"Rp{value/1_000_000:.2f} Jt"

    return "Rp{:,.0f}".format(value).replace(",", ".")


def format_price(value):
    if value is None:
        return "—"
    return "Rp{:,.0f}".format(float(value)).replace(",", ".")


def extract_share_count(text):
    m = re.search(
        r"([\d.,]+)\s*(juta|miliar|triliun)?\s+saham",
        text,
        flags=re.I,
    )
    if not m:
        return None

    number = m.group(1)
    unit = m.group(2) or ""
    return normalize(f"{number} {unit} saham")


def extract_standby_buyer(text):
    patterns = [
        r"standby buyer[^A-Za-z0-9]{0,8}([A-Z][A-Za-z0-9&.,\- ]{3,60})",
        r"pembeli siaga[^A-Za-z0-9]{0,8}([A-Z][A-Za-z0-9&.,\- ]{3,60})",
    ]

    for p in patterns:
        m = re.search(p, text)
        if m:
            value = normalize(m.group(1))
            value = re.split(r"[.;]", value)[0]
            return value[:80]

    return None




# ============================================================
# V5.1 DEEP ARTICLE EXTRACTION
# ============================================================

GOOGLE_HOST_HINTS = (
    "google.com",
    "google.co.id",
    "news.google.com",
    "googleusercontent.com",
    "gstatic.com",
)

RESTRICTED_PAGE_PHRASES = [
    "subscribe to continue",
    "subscription required",
    "sign in to continue",
    "login to continue",
    "berlangganan untuk membaca",
    "berlangganan untuk melanjutkan",
    "masuk untuk membaca",
    "login untuk membaca",
    "khusus pelanggan",
]

DATE_TOKEN_PATTERN = (
    r"(?:\d{1,2}\s+"
    r"(?:Jan(?:uari)?|Feb(?:ruari)?|Mar(?:et)?|Apr(?:il)?|"
    r"Mei|Jun(?:i)?|Jul(?:i)?|Agu(?:stus)?|Sep(?:tember)?|"
    r"Okt(?:ober)?|Nov(?:ember)?|Des(?:ember)?|"
    r"January|February|March|April|May|June|July|August|"
    r"September|October|November|December)"
    r"\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})"
)


def deep_status_badge(value):
    return {
        "FULL": "✅ FULL",
        "PARTIAL": "🟡 PARTIAL",
        "RESTRICTED": "🔒 RESTRICTED",
        "FAILED": "⚪ FAILED",
        "DISABLED": "⚪ DISABLED",
        "GOOGLE_ONLY": "⚪ GOOGLE ONLY",
    }.get(value, "⚪ UNKNOWN")


def _host(url):
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""


def _is_google_host(host):
    return any(
        host == h or host.endswith("." + h)
        for h in GOOGLE_HOST_HINTS
    )


def _source_tokens(source):
    tokens = re.findall(r"[a-z0-9]+", (source or "").lower())
    stop = {
        "com", "co", "id", "news", "the", "indonesia",
        "online", "media", "www",
    }
    return [x for x in tokens if len(x) >= 3 and x not in stop]



# ============================================================
# V5.2 MULTI-STRATEGY SOURCE RESOLVER
# ============================================================

KNOWN_SOURCE_DOMAINS = {
    "kontan": "kontan.co.id",
    "bisnis.com": "bisnis.com",
    "cnbc indonesia": "cnbcindonesia.com",
    "detikfinance": "finance.detik.com",
    "bareksa": "bareksa.com",
    "emitennews": "emitennews.com",
    "pasardana": "pasardana.id",
    "pintarsaham": "pintarsaham.id",
    "idx channel": "idxchannel.com",
    "investor.id": "investor.id",
    "idnfinancials": "idnfinancials.com",
    "katadata": "katadata.co.id",
    "kompas": "kompas.com",
    "tempo": "tempo.co",
    "antaranews": "antaranews.com",
    "mikir duit": "mikirduit.com",
    "topbusiness": "topbusiness.id",
    "idxchannel": "idxchannel.com",
    "idx channel": "idxchannel.com",
    "bloomberg technoz": "bloombergtechnoz.com",
    "bloombergtechnoz": "bloombergtechnoz.com",
    "liputan6": "liputan6.com",
    "okezone": "okezone.com",
    "sindonews": "sindonews.com",
    "kumparan": "kumparan.com",
    "viva": "viva.co.id",
    "media indonesia": "mediaindonesia.com",
    "republika": "republika.co.id",
    "jawapos": "jawapos.com",
    "theiconomics": "theiconomics.com",
    "stockwatch": "stockwatch.id",
    "snips stockbit": "snips.stockbit.com",
    "stockbit": "stockbit.com",
}


def resolver_status_badge(value):
    return {
        "PUBLISHER_DIRECT": "✅ PUBLISHER DIRECT",
        "PUBLISHER_SEARCH": "✅ PUBLISHER SEARCH",
        "PUBLISHER_INTERNAL": "✅ PUBLISHER INTERNAL",
        "GNEWS_DYNAMIC": "✅ GOOGLE DYNAMIC DECODE",
        "GNEWS_BATCH": "✅ GOOGLE BATCH DECODE",
        "GNEWS_LEGACY": "✅ GOOGLE LEGACY DECODE",
        "GNEWS_DIRECT": "✅ GOOGLE DIRECT DECODE",
        "DIRECT": "✅ DIRECT",
        "CANONICAL": "✅ CANONICAL",
        "EXTERNAL_LINK": "✅ EXTERNAL LINK",
        "TITLE_MATCH": "✅ TITLE MATCH",
        "SEARCH_FALLBACK": "🟡 SEARCH FALLBACK",
        "SOURCE_HOME": "🟡 SOURCE HOME",
        "GOOGLE_ONLY": "⚪ GOOGLE ONLY",
        "FAILED": "⚪ FAILED",
        "DISABLED": "⚪ DISABLED",
    }.get(value, "⚪ UNKNOWN")



# ============================================================
# V5.3 SAFE GOOGLE NEWS DECODER CORE
# ============================================================

GOOGLE_BATCH_ENDPOINT = (
    "https://news.google.com/_/DotsSplashUi/data/"
    "batchexecute?rpcids=Fbv4je"
)

GOOGLE_NEWS_ALLOWED_PATHS = {
    "articles",
    "read",
}


def _is_valid_http_url(url):
    try:
        parsed = urlparse(url)
        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.hostname)
        )
    except Exception:
        return False


def _is_valid_google_news_encoded_url(url):
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        if host != "news.google.com":
            return False

        parts = [x for x in parsed.path.split("/") if x]

        if len(parts) < 2:
            return False

        token = parts[-1]
        parent = parts[-2]

        valid_parent = parent in GOOGLE_NEWS_ALLOWED_PATHS

        if (
            len(parts) >= 3
            and parts[-3] == "rss"
            and parent == "articles"
        ):
            valid_parent = True

        if not valid_parent:
            return False

        if not (
            8 <= len(token)
            <= GOOGLE_DECODER_MAX_TOKEN_CHARS
        ):
            return False

        if not re.fullmatch(r"[A-Za-z0-9_-]+", token):
            return False

        return True
    except Exception:
        return False


def _google_news_token(url):
    if not _is_valid_google_news_encoded_url(url):
        return None

    try:
        return [x for x in urlparse(url).path.split("/") if x][-1]
    except Exception:
        return None


def _decode_varint(data, offset=0):
    value = 0
    shift = 0
    pos = offset

    for _ in range(5):
        if pos >= len(data):
            return None, offset

        b = data[pos]
        pos += 1
        value |= (b & 0x7F) << shift

        if not (b & 0x80):
            return value, pos

        shift += 7

    return None, offset


def _safe_base64_decode_token(token):
    if not token:
        return None

    if len(token) > GOOGLE_DECODER_MAX_TOKEN_CHARS:
        return None

    try:
        padding = "=" * (-len(token) % 4)
        decoded = base64.urlsafe_b64decode(token + padding)

        if len(decoded) > 8192:
            return None

        return decoded
    except Exception:
        return None


def _extract_http_from_bytes(data):
    if not data:
        return None

    m = re.search(
        rb"https?://[^\x00\s\"'<>]+",
        data,
    )

    if not m:
        return None

    try:
        url = m.group(0).decode("utf-8", errors="strict")
    except Exception:
        return None

    return url if _is_valid_http_url(url) else None


def decode_google_news_legacy(url):
    token = _google_news_token(url)

    if not token:
        return {
            "status": False,
            "message": "Invalid Google News encoded URL.",
        }

    decoded = _safe_base64_decode_token(token)

    if not decoded:
        return {
            "status": False,
            "message": "Base64 token could not be decoded safely.",
        }

    direct_embedded = _extract_http_from_bytes(decoded)

    prefix = b"\x08\x13\x22"
    suffix = b"\xd2\x01\x00"
    payload_area = decoded

    if payload_area.startswith(prefix):
        payload_area = payload_area[len(prefix):]

    if payload_area.endswith(suffix):
        payload_area = payload_area[:-len(suffix)]

    length, pos = _decode_varint(payload_area, 0)
    payload = None

    if (
        length is not None
        and length >= 0
        and pos + length <= len(payload_area)
    ):
        payload = payload_area[pos:pos + length]

    if payload:
        try:
            decoded_str = payload.decode("utf-8", errors="strict")
        except Exception:
            decoded_str = payload.decode("latin1", errors="ignore")

        if decoded_str.startswith(("http://", "https://")):
            if _is_valid_http_url(decoded_str):
                return {
                    "status": True,
                    "decoded_url": decoded_str,
                    "needs_batch": False,
                    "token": token,
                    "method": "LEGACY",
                }

        if decoded_str.startswith("AU_yqL"):
            return {
                "status": False,
                "decoded_url": None,
                "needs_batch": True,
                "token": token,
                "method": "BATCH_REQUIRED",
                "message": "Modern token requires batchexecute.",
            }

    if direct_embedded:
        return {
            "status": True,
            "decoded_url": direct_embedded,
            "needs_batch": False,
            "token": token,
            "method": "LEGACY_EMBEDDED",
        }

    return {
        "status": False,
        "decoded_url": None,
        "needs_batch": True,
        "token": token,
        "method": "BATCH_REQUIRED",
        "message": "No direct URL; batchexecute required.",
    }



# ============================================================
# V5.3.2 DYNAMIC SIGNATURE / TIMESTAMP PROTOCOL
# ============================================================

def _valid_google_signature(value):
    if not value:
        return False

    value = str(value).strip()

    return (
        1 <= len(value) <= 2048
        and re.fullmatch(
            r"[A-Za-z0-9_\-.:+/=]+",
            value,
        )
        is not None
    )


def _valid_google_timestamp(value):
    if value is None:
        return False

    value = str(value).strip()

    return (
        value.isdigit()
        and 1 <= len(value) <= 20
    )


def _dynamic_google_page_variants(
    token,
    source_url=None,
):
    variants = [
        (
            "ARTICLES",
            f"https://news.google.com/articles/{token}",
        ),
        (
            "RSS_ARTICLES",
            f"https://news.google.com/rss/articles/{token}",
        ),
    ]

    if (
        source_url
        and _is_valid_google_news_encoded_url(
            source_url
        )
    ):
        variants.append(
            ("ORIGINAL", source_url)
        )

    output = []
    seen = set()

    for mode, url in variants:
        if url in seen:
            continue
        seen.add(url)
        output.append((mode, url))

    return output


def _extract_dynamic_params_from_html(
    html_text,
    token,
):
    if not html_text or not BS4_AVAILABLE:
        return {
            "status": False,
            "message": (
                "Empty HTML or BeautifulSoup unavailable."
            ),
        }

    html_text = html_text[
        :DYNAMIC_PARAMS_HTML_MAX_CHARS
    ]

    soup = BeautifulSoup(
        html_text,
        "html.parser",
    )

    candidates = []

    exact = soup.find(
        attrs={
            "data-n-a-id": token,
            "data-n-a-sg": True,
            "data-n-a-ts": True,
        }
    )

    if exact is not None:
        candidates.append(
            ("EXACT_DATA_ID", exact)
        )

    for node in soup.select(
        "c-wiz > div[jscontroller]"
    ):
        if (
            node.get("data-n-a-sg")
            and node.get("data-n-a-ts")
        ):
            candidates.append(
                ("CWIZ_JSCONTROLLER", node)
            )

    for node in soup.select(
        "[data-n-a-sg][data-n-a-ts]"
    ):
        candidates.append(
            ("GENERIC_ATTRS", node)
        )

    seen = set()

    for selector, node in candidates:
        marker = id(node)
        if marker in seen:
            continue
        seen.add(marker)

        signature = node.get(
            "data-n-a-sg"
        )
        timestamp = node.get(
            "data-n-a-ts"
        )
        data_id = node.get(
            "data-n-a-id"
        )

        if (
            _valid_google_signature(
                signature
            )
            and _valid_google_timestamp(
                timestamp
            )
        ):
            return {
                "status": True,
                "signature": str(signature),
                "timestamp": str(timestamp),
                "data_id": (
                    str(data_id)
                    if data_id
                    else token
                ),
                "selector": selector,
            }

    # Attribute-order tolerant regex fallbacks.
    sg_ts = re.search(
        r'data-n-a-sg=["\']([^"\']+)["\']'
        r'[^>]{0,800}?'
        r'data-n-a-ts=["\'](\d+)["\']',
        html_text,
        flags=re.I | re.S,
    )

    if sg_ts:
        signature = sg_ts.group(1)
        timestamp = sg_ts.group(2)

        if (
            _valid_google_signature(
                signature
            )
            and _valid_google_timestamp(
                timestamp
            )
        ):
            return {
                "status": True,
                "signature": signature,
                "timestamp": timestamp,
                "data_id": token,
                "selector": "REGEX_SG_TS",
            }

    ts_sg = re.search(
        r'data-n-a-ts=["\'](\d+)["\']'
        r'[^>]{0,800}?'
        r'data-n-a-sg=["\']([^"\']+)["\']',
        html_text,
        flags=re.I | re.S,
    )

    if ts_sg:
        timestamp = ts_sg.group(1)
        signature = ts_sg.group(2)

        if (
            _valid_google_signature(
                signature
            )
            and _valid_google_timestamp(
                timestamp
            )
        ):
            return {
                "status": True,
                "signature": signature,
                "timestamp": timestamp,
                "data_id": token,
                "selector": "REGEX_TS_SG",
            }

    return {
        "status": False,
        "message": (
            "data-n-a-sg / data-n-a-ts "
            "not found in Google News HTML."
        ),
    }


async def get_dynamic_decoding_params(
    client,
    source_url,
):
    token = _google_news_token(
        source_url
    )

    if not token:
        return {
            "status": False,
            "method": "NO_TOKEN",
            "message": (
                "Google News token not found."
            ),
            "attempts": [],
        }

    now = time.time()
    cached = DYNAMIC_PARAMS_CACHE.get(
        token
    )

    if cached and (
        now - cached["cached_at"]
        <= DYNAMIC_PARAMS_CACHE_MINUTES * 60
    ):
        return {
            **cached["data"],
            "cache_hit": True,
        }

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/129 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8"
        ),
        "Accept-Language": (
            "en-US,en;q=0.9"
        ),
    }

    attempts = []

    for mode, url in (
        _dynamic_google_page_variants(
            token,
            source_url=source_url,
        )
    ):
        try:
            response = await client.get(
                url,
                headers=headers,
                timeout=DYNAMIC_PARAMS_TIMEOUT_SECONDS,
                follow_redirects=True,
            )
        except Exception as exc:
            attempts.append({
                "mode": mode,
                "http_status": None,
                "html_chars": 0,
                "params_found": False,
                "error": type(exc).__name__,
            })
            continue

        html_text = (
            response.text
            if response.status_code < 400
            else ""
        )

        parsed = (
            _extract_dynamic_params_from_html(
                html_text,
                token,
            )
            if html_text
            else {
                "status": False,
            }
        )

        attempts.append({
            "mode": mode,
            "http_status": (
                response.status_code
            ),
            "html_chars": len(
                html_text
            ),
            "params_found": bool(
                parsed.get("status")
            ),
            "selector": parsed.get(
                "selector"
            ),
            "final_host": _host(
                str(response.url)
            ),
        })

        if parsed.get("status"):
            result = {
                "status": True,
                "method": mode,
                "signature": parsed[
                    "signature"
                ],
                "timestamp": parsed[
                    "timestamp"
                ],
                "data_id": parsed.get(
                    "data_id",
                    token,
                ),
                "selector": parsed.get(
                    "selector"
                ),
                "attempts": attempts,
                "cache_hit": False,
            }

            DYNAMIC_PARAMS_CACHE[
                token
            ] = {
                "cached_at": now,
                "data": result,
            }

            return result

    result = {
        "status": False,
        "method": "PARAMS_NOT_FOUND",
        "message": (
            "Signature/timestamp not found "
            "from Google News page variants."
        ),
        "attempts": attempts,
        "cache_hit": False,
    }

    DYNAMIC_PARAMS_CACHE[token] = {
        "cached_at": now,
        "data": result,
    }

    return result


def _build_dynamic_garturl_f_req(
    token,
    timestamp,
    signature,
):
    if not (
        token
        and _valid_google_timestamp(
            timestamp
        )
        and _valid_google_signature(
            signature
        )
    ):
        raise ValueError(
            "Invalid dynamic decoder parameters."
        )

    dynamic_inner = [
        "garturlreq",
        [
            [
                "X",
                "X",
                ["X", "X"],
                None,
                None,
                1,
                1,
                "US:en",
                None,
                1,
                None,
                None,
                None,
                None,
                None,
                0,
                1,
            ],
            "X",
            "X",
            1,
            [1, 1, 1],
            1,
            1,
            None,
            0,
            0,
            None,
            0,
        ],
        token,
        int(timestamp),
        signature,
    ]

    payload = [
        "Fbv4je",
        json.dumps(
            dynamic_inner,
            separators=(",", ":"),
        ),
    ]

    return json.dumps(
        [[payload]],
        separators=(",", ":"),
    )


def _parse_dynamic_google_response(
    response_text,
    source="",
):
    diagnostics = {
        "structured_parser": False,
        "multi_parser": False,
        "parser_method": "NONE",
        "decoded_url": None,
    }

    if response_text:
        # Batchexecute usually has XSSI/length framing.
        for line in response_text.splitlines():
            chunk = line.strip()

            if (
                not chunk
                or chunk.isdigit()
                or chunk.startswith(")]}'")
            ):
                continue

            if chunk[0] not in "[{":
                continue

            try:
                outer = json.loads(chunk)
            except Exception:
                continue

            try:
                rpc_string = outer[0][2]
                inner = json.loads(
                    rpc_string
                )
                candidate = (
                    _normalize_decoder_candidate(
                        inner[1]
                    )
                )

                if candidate:
                    diagnostics.update({
                        "structured_parser": True,
                        "parser_method": (
                            "STRUCTURED_RPC"
                        ),
                        "decoded_url": candidate,
                    })
                    return diagnostics

            except (
                IndexError,
                TypeError,
                KeyError,
                json.JSONDecodeError,
            ):
                pass

    analysis = (
        _analyze_batchexecute_response(
            response_text,
            source=source,
        )
    )

    if analysis.get("best_candidate"):
        diagnostics.update({
            "multi_parser": True,
            "parser_method": analysis.get(
                "parser_method",
                "MULTI",
            ),
            "decoded_url": analysis[
                "best_candidate"
            ],
            "rpc_found": analysis.get(
                "rpc_found"
            ),
            "garturlres_found": (
                analysis.get(
                    "garturlres_found"
                )
            ),
            "candidate_count": len(
                analysis.get(
                    "url_candidates",
                    [],
                )
            ),
        })

    return diagnostics


async def decode_google_news_dynamic(
    client,
    source_url,
    source="",
):
    if not DYNAMIC_PROTOCOL_ENABLED:
        return {
            "status": False,
            "method": "DYNAMIC_DISABLED",
            "message": (
                "Dynamic protocol disabled."
            ),
        }

    token = _google_news_token(
        source_url
    )

    if not token:
        return {
            "status": False,
            "method": "DYNAMIC_NO_TOKEN",
            "message": "Google token missing.",
        }

    params = (
        await get_dynamic_decoding_params(
            client,
            source_url,
        )
    )

    if not params.get("status"):
        return {
            "status": False,
            "method": "DYNAMIC_PARAMS_FAILED",
            "message": params.get(
                "message",
                "Dynamic params unavailable.",
            ),
            "protocol_debug": {
                "params_found": False,
                "params_method": params.get(
                    "method"
                ),
                "params_attempts": params.get(
                    "attempts",
                    [],
                ),
                "params_cache_hit": params.get(
                    "cache_hit",
                    False,
                ),
            },
        }

    try:
        f_req = (
            _build_dynamic_garturl_f_req(
                token,
                params["timestamp"],
                params["signature"],
            )
        )
    except Exception as exc:
        return {
            "status": False,
            "method": "DYNAMIC_PAYLOAD_FAILED",
            "message": str(exc),
        }

    headers = {
        "Content-Type": (
            "application/x-www-form-urlencoded;"
            "charset=UTF-8"
        ),
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/129 Safari/537.36"
        ),
        "Referer": (
            "https://news.google.com/"
        ),
        "Origin": (
            "https://news.google.com"
        ),
    }

    endpoint = (
        "https://news.google.com/"
        "_/DotsSplashUi/data/"
        "batchexecute?rpcids=Fbv4je"
    )

    try:
        response = await client.post(
            endpoint,
            headers=headers,
            data={"f.req": f_req},
            timeout=GOOGLE_DECODER_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        return {
            "status": False,
            "method": "DYNAMIC_REQUEST_FAILED",
            "message": (
                "Dynamic request failed: "
                f"{type(exc).__name__}"
            ),
            "protocol_debug": {
                "params_found": True,
                "params_method": params.get(
                    "method"
                ),
                "params_selector": params.get(
                    "selector"
                ),
                "params_attempts": params.get(
                    "attempts",
                    [],
                ),
            },
        }

    response_bytes = len(
        response.content or b""
    )

    if response.status_code >= 300:
        return {
            "status": False,
            "method": "DYNAMIC_HTTP_FAILED",
            "message": (
                "Google returned HTTP "
                f"{response.status_code}."
            ),
            "protocol_debug": {
                "params_found": True,
                "params_method": params.get(
                    "method"
                ),
                "params_selector": params.get(
                    "selector"
                ),
                "http_status": (
                    response.status_code
                ),
                "response_bytes": (
                    response_bytes
                ),
            },
        }

    parsed = (
        _parse_dynamic_google_response(
            response.text,
            source=source,
        )
    )

    debug = {
        "params_found": True,
        "params_method": params.get(
            "method"
        ),
        "params_selector": params.get(
            "selector"
        ),
        "params_cache_hit": params.get(
            "cache_hit",
            False,
        ),
        "params_attempts": params.get(
            "attempts",
            [],
        ),
        "signature_length": len(
            params.get("signature", "")
        ),
        "timestamp": params.get(
            "timestamp"
        ),
        "http_status": (
            response.status_code
        ),
        "response_bytes": (
            response_bytes
        ),
        "structured_parser": parsed.get(
            "structured_parser",
            False,
        ),
        "multi_parser": parsed.get(
            "multi_parser",
            False,
        ),
        "response_parser": parsed.get(
            "parser_method",
            "NONE",
        ),
        "rpc_found": parsed.get(
            "rpc_found"
        ),
        "garturlres_found": parsed.get(
            "garturlres_found"
        ),
        "candidate_count": parsed.get(
            "candidate_count",
            0,
        ),
    }

    decoded_url = parsed.get(
        "decoded_url"
    )

    if (
        decoded_url
        and not _is_google_host(
            _host(decoded_url)
        )
    ):
        return {
            "status": True,
            "decoded_url": decoded_url,
            "method": "DYNAMIC_SIGNATURE",
            "protocol_debug": debug,
        }

    return {
        "status": False,
        "method": "DYNAMIC_NO_URL",
        "message": (
            "Dynamic request succeeded but "
            "publisher URL was not parsed."
        ),
        "protocol_debug": debug,
    }


def _build_garturl_f_req(token):
    inner = [
        "garturlreq",
        [
            [
                "en-US",
                "US",
                ["FINANCE_TOP_INDICES", "WEB_TEST_1_0_0"],
                None,
                None,
                1,
                1,
                "US:en",
                None,
                180,
                None,
                None,
                None,
                None,
                None,
                0,
                None,
                None,
                [1608992183, 723341000],
            ],
            "en-US",
            "US",
            1,
            [2, 3, 4, 8],
            1,
            0,
            "655000234",
            0,
            0,
            None,
            0,
        ],
        token,
    ]

    rpc = [
        "Fbv4je",
        json.dumps(inner, separators=(",", ":")),
        None,
        "1",
    ]

    return json.dumps([[rpc]], separators=(",", ":"))


def _decoder_unescape_text(value):
    """Controlled unescape for batchexecute text."""
    if not isinstance(value, str):
        return ""

    result = value
    replacements = [
        ("\\\\u003d", "="),
        ("\\\\u0026", "&"),
        ("\\\\u003f", "?"),
        ("\\\\u002f", "/"),
        ("\\\\u003a", ":"),
        ("\\\\/", "/"),
        ('\\\\\\"', '"'),
        ("\\\\\\\\", "\\\\"),
    ]

    for old, new in replacements:
        result = result.replace(old, new)

    return html.unescape(result)


def _normalize_decoder_candidate(url):
    if not url:
        return None

    value = _decoder_unescape_text(str(url)).strip()
    value = value.lstrip("([{'\\\" ").rstrip(")]},;'\\\" ")

    # Trim obvious batchexecute suffix fragments.
    value = re.split(
        r'(?:\\\\",|",|\\\\\]|"\])',
        value,
        maxsplit=1,
    )[0]

    if not _is_valid_http_url(value):
        return None

    host = _host(value)

    if not host or _is_google_host(host):
        return None

    return value


def _decoder_url_score(url, source=""):
    host = _host(url)

    if not host or _is_google_host(host):
        return -999

    score = 10
    domain_hint = _source_domain_hint(source)

    if domain_hint and (
        host == domain_hint
        or host.endswith("." + domain_hint)
    ):
        score += 80

    low = url.lower()
    path = urlparse(url).path or ""

    if any(
        x in low
        for x in (
            "/news/",
            "/market/",
            "/emiten/",
            "/article/",
            "/read/",
            "/berita/",
            "/bisnis/",
            "/investasi/",
        )
    ):
        score += 15

    if len(path.strip("/")) >= 10:
        score += 8

    if any(
        x in host
        for x in (
            "googleusercontent.com",
            "gstatic.com",
            "doubleclick.net",
            "googlesyndication.com",
            "facebook.com",
            "twitter.com",
            "x.com",
            "youtube.com",
        )
    ):
        score -= 70

    if any(
        x in low
        for x in (
            "/privacy",
            "/terms",
            "/login",
            "/signin",
            "/account",
            "/subscribe",
            "/help",
        )
    ):
        score -= 30

    return score


def _extract_http_urls_loose(text):
    if not text:
        return []

    variants = [
        str(text),
        _decoder_unescape_text(str(text)),
    ]

    results = []
    seen = set()

    for variant in variants:
        for match in re.finditer(
            r'https?://[^\s<>"\']+',
            variant,
            flags=re.I,
        ):
            candidate = _normalize_decoder_candidate(
                match.group(0)
            )

            if candidate and candidate not in seen:
                seen.add(candidate)
                results.append(candidate)

    return results


def _collect_nested_decoder_strings(
    obj,
    output,
    depth=0,
):
    if depth > DECODER_MAX_NESTED_JSON_DEPTH:
        return

    if len(output) >= 500:
        return

    if isinstance(obj, dict):
        for key, value in obj.items():
            output.append(str(key))
            _collect_nested_decoder_strings(
                value,
                output,
                depth + 1,
            )
        return

    if isinstance(obj, list):
        for value in obj:
            _collect_nested_decoder_strings(
                value,
                output,
                depth + 1,
            )
        return

    if isinstance(obj, str):
        output.append(obj)

        stripped = obj.strip()

        if (
            stripped
            and stripped[0] in "[{"
            and len(stripped)
            <= DECODER_MAX_RESPONSE_CHARS
        ):
            try:
                nested = json.loads(stripped)
            except Exception:
                nested = None

            if nested is not None:
                _collect_nested_decoder_strings(
                    nested,
                    output,
                    depth + 1,
                )


def _json_objects_from_batchexecute(text):
    """
    Parse common batchexecute framing:
    )]}'
    <length>
    [JSON]
    """
    if not text:
        return []

    sample = text[:DECODER_MAX_RESPONSE_CHARS]
    objects = []

    for line in sample.splitlines():
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith(")]}'"):
            continue

        if stripped.isdigit():
            continue

        if stripped[0] not in "[{":
            continue

        try:
            objects.append(json.loads(stripped))
        except Exception:
            continue

    if not objects:
        stripped = sample.strip()

        if stripped.startswith(")]}'"):
            stripped = stripped[4:].lstrip()

        stripped = re.sub(
            r'^\d+\s*',
            '',
            stripped,
            count=1,
        )

        if stripped and stripped[0] in "[{":
            try:
                objects.append(json.loads(stripped))
            except Exception:
                pass

    return objects


def _analyze_batchexecute_response(
    text,
    source="",
):
    """
    Multi-format parser.
    Raw response is never returned to Telegram.
    """
    raw = (text or "")[:DECODER_MAX_RESPONSE_CHARS]

    analysis = {
        "response_chars": len(text or ""),
        "analyzed_chars": len(raw),
        "rpc_found": "Fbv4je" in raw,
        "garturlres_found": (
            "garturlres" in raw.lower()
        ),
        "json_objects": 0,
        "nested_strings": 0,
        "url_candidates": [],
        "best_candidate": None,
        "parser_method": "NONE",
    }

    nested_strings = []
    objects = _json_objects_from_batchexecute(raw)

    analysis["json_objects"] = len(objects)

    for obj in objects:
        _collect_nested_decoder_strings(
            obj,
            nested_strings,
        )

    analysis["nested_strings"] = len(nested_strings)

    pool = []
    seen = set()

    def add_values(values, origin):
        for value in values:
            for url in _extract_http_urls_loose(value):
                if url in seen:
                    continue

                seen.add(url)
                pool.append({
                    "url": url,
                    "origin": origin,
                    "score": _decoder_url_score(
                        url,
                        source,
                    ),
                })

    # Strongest signal.
    add_values(
        [
            s for s in nested_strings
            if "garturlres" in s.lower()
        ],
        "GARTURL_NESTED",
    )

    # Generic nested JSON.
    add_values(
        nested_strings,
        "NESTED_JSON",
    )

    # Raw response fallback.
    add_values(
        [raw],
        "RAW_SCAN",
    )

    # Specific proximity scan.
    for variant in (
        raw,
        _decoder_unescape_text(raw),
    ):
        matches = re.findall(
            r'garturlres.{0,250}?'
            r'(https?://[^\s<>"\']+)',
            variant,
            flags=re.I | re.S,
        )
        add_values(
            matches,
            "GARTURL_REGEX",
        )

    origin_bonus = {
        "GARTURL_NESTED": 100,
        "GARTURL_REGEX": 90,
        "NESTED_JSON": 30,
        "RAW_SCAN": 0,
    }

    for item in pool:
        item["rank"] = (
            item["score"]
            + origin_bonus.get(
                item["origin"],
                0,
            )
        )

    pool.sort(
        key=lambda x: x["rank"],
        reverse=True,
    )

    analysis["url_candidates"] = pool[
        :DECODER_MAX_URL_CANDIDATES
    ]

    if pool:
        analysis["best_candidate"] = pool[0]["url"]

        if pool[0]["origin"].startswith("GARTURL"):
            analysis["parser_method"] = "GARTURL_MULTI"
        elif pool[0]["origin"] == "NESTED_JSON":
            analysis["parser_method"] = "NESTED_JSON"
        else:
            analysis["parser_method"] = "URL_SCAN"

    return analysis


def _parse_garturl_response(
    text,
    source="",
):
    return _analyze_batchexecute_response(
        text,
        source=source,
    ).get("best_candidate")


async def decode_google_news_batch(
    client,
    token,
    source="",
):
    if not GOOGLE_DECODER_BATCH_ENABLED:
        return {
            "status": False,
            "message": "Batch decoder disabled.",
            "method": "DISABLED",
        }

    if not token:
        return {
            "status": False,
            "message": "Missing Google News token.",
            "method": "INVALID",
        }

    if len(token) > GOOGLE_DECODER_MAX_TOKEN_CHARS:
        return {
            "status": False,
            "message": "Token exceeds safe bound.",
            "method": "INVALID",
        }

    if not re.fullmatch(r"[A-Za-z0-9_-]+", token):
        return {
            "status": False,
            "message": "Token contains invalid characters.",
            "method": "INVALID",
        }

    f_req = _build_garturl_f_req(token)

    headers = {
        "Content-Type": (
            "application/x-www-form-urlencoded;"
            "charset=utf-8"
        ),
        "Referer": "https://news.google.com/",
        "Origin": "https://news.google.com",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/122 Safari/537.36"
        ),
    }

    try:
        response = await client.post(
            GOOGLE_BATCH_ENDPOINT,
            headers=headers,
            data={"f.req": f_req},
            timeout=GOOGLE_DECODER_TIMEOUT_SECONDS,
        )
    except Exception as exc:
        return {
            "status": False,
            "message": (
                "Batch request failed: "
                f"{type(exc).__name__}"
            ),
            "method": "REQUEST_FAILED",
            "http_status": None,
            "response_bytes": 0,
            "rpc_found": False,
            "garturlres_found": False,
            "candidate_count": 0,
            "url_candidates": [],
        }

    response_bytes = len(response.content or b"")

    if response.status_code != 200:
        return {
            "status": False,
            "message": (
                "Google returned HTTP "
                f"{response.status_code}."
            ),
            "method": "HTTP_FAILED",
            "http_status": response.status_code,
            "response_bytes": response_bytes,
            "rpc_found": False,
            "garturlres_found": False,
            "candidate_count": 0,
            "url_candidates": [],
        }

    analysis = _analyze_batchexecute_response(
        response.text,
        source=source,
    )

    candidates = analysis.get(
        "url_candidates",
        [],
    )

    decoded_url = analysis.get(
        "best_candidate"
    )

    debug = {
        "http_status": response.status_code,
        "response_bytes": response_bytes,
        "response_chars": analysis.get(
            "response_chars",
            0,
        ),
        "rpc_found": analysis.get(
            "rpc_found",
            False,
        ),
        "garturlres_found": analysis.get(
            "garturlres_found",
            False,
        ),
        "json_objects": analysis.get(
            "json_objects",
            0,
        ),
        "nested_strings": analysis.get(
            "nested_strings",
            0,
        ),
        "candidate_count": len(candidates),
        "url_candidates": [
            item.get("url")
            for item in candidates[:10]
        ],
        "candidate_origins": [
            item.get("origin")
            for item in candidates[:10]
        ],
        "parser_method": analysis.get(
            "parser_method",
            "NONE",
        ),
    }

    if not decoded_url:
        return {
            "status": False,
            "message": (
                "No publisher URL candidate "
                "found in batchexecute response."
            ),
            "method": "PARSER_NO_URL",
            **debug,
        }

    if _is_google_host(_host(decoded_url)):
        return {
            "status": False,
            "message": (
                "Best candidate still points "
                "to Google."
            ),
            "method": "PARSER_GOOGLE_ONLY",
            **debug,
        }

    return {
        "status": True,
        "decoded_url": decoded_url,
        "method": "BATCH_MULTI",
        **debug,
    }


async def decode_google_news_url_core(
    client,
    source_url,
    source="",
):
    if not GOOGLE_DECODER_ENABLED:
        return {
            "status": False,
            "method": "DISABLED",
            "message": "Google decoder disabled.",
        }

    if not source_url:
        return {
            "status": False,
            "method": "FAILED",
            "message": "Empty source URL.",
        }

    parsed = urlparse(source_url)
    host = (parsed.hostname or "").lower()

    if host and not _is_google_host(host):
        return {
            "status": True,
            "decoded_url": source_url,
            "method": "DIRECT",
        }

    if not _is_valid_google_news_encoded_url(
        source_url
    ):
        return {
            "status": False,
            "method": "INVALID",
            "message": "Unsupported Google News URL.",
        }

    cache_key = source_url
    now = time.time()
    cached = GOOGLE_DECODER_CACHE.get(
        cache_key
    )

    if cached and (
        now - cached["cached_at"]
        <= GOOGLE_DECODER_CACHE_MINUTES * 60
    ):
        return cached["data"]

    # 0) Dynamic runtime signature/timestamp protocol.
    dynamic = (
        await decode_google_news_dynamic(
            client,
            source_url,
            source=source,
        )
        if DYNAMIC_PROTOCOL_ENABLED
        else {
            "status": False,
            "method": "DYNAMIC_DISABLED",
        }
    )

    if (
        dynamic.get("status")
        and dynamic.get("decoded_url")
    ):
        result = {
            "status": True,
            "decoded_url": dynamic[
                "decoded_url"
            ],
            "method": "DYNAMIC_SIGNATURE",
            "protocol_debug": dynamic.get(
                "protocol_debug",
                {},
            ),
        }

        GOOGLE_DECODER_CACHE[
            cache_key
        ] = {
            "cached_at": now,
            "data": result,
        }

        return result

    # 1) Legacy direct URL embedded in token.
    legacy = decode_google_news_legacy(
        source_url
    )

    if (
        legacy.get("status")
        and legacy.get("decoded_url")
    ):
        result = {
            "status": True,
            "decoded_url": legacy[
                "decoded_url"
            ],
            "method": "LEGACY",
            "protocol_debug": dynamic.get(
                "protocol_debug",
                {},
            ),
        }

        GOOGLE_DECODER_CACHE[
            cache_key
        ] = {
            "cached_at": now,
            "data": result,
        }

        return result

    token = legacy.get("token")

    # 2) V5.3.1 static batchexecute remains fallback.
    if (
        DYNAMIC_PROTOCOL_FALLBACK_STATIC
        and legacy.get("needs_batch")
        and token
    ):
        batch = await decode_google_news_batch(
            client,
            token,
            source=source,
        )

        if batch.get("status"):
            result = {
                "status": True,
                "decoded_url": batch[
                    "decoded_url"
                ],
                "method": "BATCH_MULTI",
                "protocol_debug": dynamic.get(
                    "protocol_debug",
                    {},
                ),
                "decoder_debug": {
                    key: batch.get(key)
                    for key in (
                        "http_status",
                        "response_bytes",
                        "response_chars",
                        "rpc_found",
                        "garturlres_found",
                        "json_objects",
                        "nested_strings",
                        "candidate_count",
                        "url_candidates",
                        "candidate_origins",
                        "parser_method",
                    )
                },
            }

            GOOGLE_DECODER_CACHE[
                cache_key
            ] = {
                "cached_at": now,
                "data": result,
            }

            return result

        result = {
            "status": False,
            "method": batch.get(
                "method",
                "BATCH_FAILED",
            ),
            "message": batch.get(
                "message",
                "Batch decode failed.",
            ),
            "dynamic_method": dynamic.get(
                "method"
            ),
            "dynamic_message": dynamic.get(
                "message"
            ),
            "protocol_debug": dynamic.get(
                "protocol_debug",
                {},
            ),
            "decoder_debug": {
                key: batch.get(key)
                for key in (
                    "http_status",
                    "response_bytes",
                    "response_chars",
                    "rpc_found",
                    "garturlres_found",
                    "json_objects",
                    "nested_strings",
                    "candidate_count",
                    "url_candidates",
                    "candidate_origins",
                    "parser_method",
                )
            },
        }

        GOOGLE_DECODER_CACHE[
            cache_key
        ] = {
            "cached_at": now,
            "data": result,
        }

        return result

    return {
        "status": False,
        "method": dynamic.get(
            "method",
            "FAILED",
        ),
        "message": dynamic.get(
            "message",
            legacy.get(
                "message",
                "Decoder failed.",
            ),
        ),
        "protocol_debug": dynamic.get(
            "protocol_debug",
            {},
        ),
    }



def _clean_google_wrapped_url(url):
    """
    Decode common Google redirect wrapper parameters such as:
    ?url=https://publisher/article
    ?q=https://publisher/article
    """
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        if not _is_google_host(host):
            return url

        qs = parse_qs(parsed.query)

        for key in ("url", "q"):
            values = qs.get(key) or []
            for value in values:
                decoded = unquote(value)
                if decoded.startswith(("http://", "https://")):
                    return decoded
    except Exception:
        pass

    return url


def _extract_meta_urls(soup, base_url):
    candidates = []

    # canonical
    for rel_value in ("canonical",):
        node = soup.find("link", rel=rel_value)
        if node and node.get("href"):
            candidates.append(
                ("CANONICAL", urljoin(base_url, node["href"]))
            )

    # og:url
    node = soup.find("meta", attrs={"property": "og:url"})
    if node and node.get("content"):
        candidates.append(
            ("CANONICAL", urljoin(base_url, node["content"]))
        )

    # twitter:url
    node = soup.find("meta", attrs={"name": "twitter:url"})
    if node and node.get("content"):
        candidates.append(
            ("CANONICAL", urljoin(base_url, node["content"]))
        )

    # meta refresh
    node = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
    if node and node.get("content"):
        m = re.search(
            r"url\s*=\s*['\"]?([^'\";]+)",
            node["content"],
            flags=re.I,
        )
        if m:
            candidates.append(
                ("DIRECT", urljoin(base_url, m.group(1).strip()))
            )

    # dedup
    output = []
    seen = set()

    for method, url in candidates:
        cleaned = _clean_google_wrapped_url(url)
        if cleaned not in seen:
            seen.add(cleaned)
            output.append((method, cleaned))

    return output


def _title_tokens(text):
    words = re.findall(r"[a-z0-9]+", normalize(text).lower())
    stop = {
        "dan", "yang", "untuk", "dari", "dengan", "ini", "itu",
        "the", "and", "for", "from", "with",
        "saham", "emiten", "perseroan", "pt", "tbk",
        "news", "berita",
    }
    return [
        w for w in words
        if len(w) >= 3 and w not in stop
    ]


def _title_similarity_score(title, candidate_text):
    wanted = set(_title_tokens(title))
    got = set(_title_tokens(candidate_text))

    if not wanted or not got:
        return 0

    overlap = len(wanted & got)
    recall = overlap / max(1, len(wanted))
    precision = overlap / max(1, len(got))

    # weighted score 0-100
    score = (recall * 70) + (precision * 30)
    return int(round(score))


def _source_domain_hint(source):
    low = (source or "").lower().strip()

    for key, domain in KNOWN_SOURCE_DOMAINS.items():
        if key in low:
            return domain

    # If source already looks like a domain.
    m = re.search(
        r"\b([a-z0-9-]+\.(?:com|co\.id|id|net|org))\b",
        low,
    )
    if m:
        return m.group(1)

    return None


def _candidate_score(url, anchor_text, source, title):
    host = _host(url)
    source_tokens = _source_tokens(source)
    domain_hint = _source_domain_hint(source)

    score = 0

    if domain_hint and (
        host == domain_hint
        or host.endswith("." + domain_hint)
    ):
        score += 45

    for token in source_tokens:
        if token in host:
            score += 12
        if token in anchor_text.lower():
            score += 4

    title_score = _title_similarity_score(
        title,
        anchor_text,
    )
    score += int(title_score * 0.6)

    low_url = url.lower()

    if any(x in low_url for x in (
        "/news/", "/market/", "/emiten/",
        "/article/", "/read/", "/berita/",
    )):
        score += 8

    if low_url.rstrip("/").count("/") <= 2:
        # likely home page
        score -= 10

    return score


def _external_link_candidates_v52(
    soup,
    base_url,
    source,
    title,
):
    candidates = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(
            base_url,
            a.get("href", "").strip(),
        )
        href = _clean_google_wrapped_url(href)

        if not href.startswith(("http://", "https://")):
            continue

        host = _host(href)

        if not host or _is_google_host(host):
            continue

        if href in seen:
            continue

        seen.add(href)
        anchor_text = normalize(
            a.get_text(" ", strip=True)
        )

        score = _candidate_score(
            href,
            anchor_text,
            source,
            title,
        )

        candidates.append({
            "score": score,
            "url": href,
            "anchor_text": anchor_text,
            "host": host,
        })

    candidates.sort(
        key=lambda x: x["score"],
        reverse=True,
    )

    return candidates[:RESOLVER_MAX_CANDIDATES]


def _extract_result_url_from_search(href):
    """
    Handles direct links and common DDG redirect:
    //duckduckgo.com/l/?uddg=https%3A%2F%2Fpublisher...
    """
    if not href:
        return None

    if href.startswith("//"):
        href = "https:" + href

    try:
        parsed = urlparse(href)
        host = (parsed.hostname or "").lower()

        if "duckduckgo.com" in host:
            qs = parse_qs(parsed.query)
            uddg = (qs.get("uddg") or [None])[0]
            if uddg:
                return unquote(uddg)

        if href.startswith(("http://", "https://")):
            return href
    except Exception:
        return None

    return None


async def _search_exact_title_candidates(
    client,
    title,
    source,
):
    """
    Optional fallback using public DuckDuckGo HTML search.
    No API key required. Best-effort only.
    """
    if not RESOLVER_SEARCH_FALLBACK:
        return []

    domain_hint = _source_domain_hint(source)

    title_tokens = _title_tokens(title)
    compact_title = " ".join(title_tokens[:10])

    if domain_hint:
        query = f'site:{domain_hint} "{compact_title}"'
    else:
        query = f'"{compact_title}" "{source}"'

    search_url = (
        "https://html.duckduckgo.com/html/?q="
        + quote_plus(query)
    )

    try:
        response = await client.get(
            search_url,
            timeout=ARTICLE_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
    except Exception:
        return []

    if response.status_code >= 400:
        return []

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    results = []

    for a in soup.select(
        "a.result__a, .result__title a, a[href]"
    ):
        href = _extract_result_url_from_search(
            a.get("href", "")
        )

        if not href:
            continue

        host = _host(href)

        if not host or _is_google_host(host):
            continue

        text = normalize(
            a.get_text(" ", strip=True)
        )

        score = _candidate_score(
            href,
            text,
            source,
            title,
        )

        if domain_hint and not (
            host == domain_hint
            or host.endswith("." + domain_hint)
        ):
            score -= 25

        results.append({
            "score": score,
            "url": href,
            "anchor_text": text,
            "host": host,
        })

    # dedup
    unique = {}
    for item in results:
        url = item["url"]
        if (
            url not in unique
            or item["score"] > unique[url]["score"]
        ):
            unique[url] = item

    output = list(unique.values())
    output.sort(
        key=lambda x: x["score"],
        reverse=True,
    )
    return output[:RESOLVER_MAX_CANDIDATES]



# ============================================================
# V5.4 PUBLISHER DIRECT RESOLVER
# ============================================================

EVENT_SEARCH_TERMS = {
    "RIGHTS ISSUE": [
        "rights issue",
        "hmetd",
        "hak memesan efek terlebih dahulu",
    ],
    "IPO": [
        "ipo",
        "initial public offering",
        "penawaran umum perdana",
    ],
    "AKUISISI": [
        "akuisisi",
        "acquisition",
        "ambil alih",
    ],
    "TAKEOVER": [
        "takeover",
        "pengambilalihan",
        "perubahan pengendali",
    ],
    "TENDER OFFER": [
        "tender offer",
        "tender wajib",
        "mandatory tender",
    ],
    "MERGER": [
        "merger",
        "penggabungan usaha",
    ],
}


def _clean_news_title(title, source=""):
    title = normalize(title or "")
    source = normalize(source or "")

    if source:
        patterns = [
            r"\s+-\s+" + re.escape(source) + r"$",
            r"\s+\|\s+" + re.escape(source) + r"$",
        ]

        for pattern in patterns:
            title = re.sub(
                pattern,
                "",
                title,
                flags=re.I,
            ).strip()

    # Remove a final source-like suffix if the title is still long.
    title = re.sub(
        r"\s+-\s+[A-Za-z0-9 ._-]{2,40}$",
        "",
        title,
    ).strip()

    return title


def _money_search_tokens(article):
    values = (
        article.get("details", {})
        .get("money", [])
        or []
    )

    tokens = []

    for value in values[:3]:
        cleaned = normalize(str(value))
        if cleaned:
            tokens.append(cleaned)

    return tokens


def _article_event_search_terms(article):
    event = article.get("event_type", "")
    terms = EVENT_SEARCH_TERMS.get(
        event,
        [event.lower()] if event else [],
    )

    return [
        term
        for term in terms
        if term
    ]


def _publisher_search_queries(article):
    source = article.get("source", "")
    domain = _source_domain_hint(source)
    title = _clean_news_title(
        article.get("title", ""),
        source,
    )

    ticker = (
        article.get("details", {})
        .get("ticker")
    )

    event_terms = _article_event_search_terms(
        article
    )

    money_tokens = _money_search_tokens(
        article
    )

    title_tokens = _title_tokens(title)
    compact_title = " ".join(
        title_tokens[:12]
    )

    queries = []

    if domain and compact_title:
        queries.append(
            (
                "EXACT_TITLE",
                f'site:{domain} "{compact_title}"',
            )
        )

    if domain and ticker and event_terms:
        queries.append(
            (
                "TICKER_EVENT",
                (
                    f"site:{domain} "
                    f"{ticker} "
                    f'"{event_terms[0]}"'
                ),
            )
        )

    if (
        domain
        and ticker
        and event_terms
        and money_tokens
    ):
        queries.append(
            (
                "TICKER_EVENT_VALUE",
                (
                    f"site:{domain} "
                    f"{ticker} "
                    f'"{event_terms[0]}" '
                    f'"{money_tokens[0]}"'
                ),
            )
        )

    if domain and title_tokens:
        core = " ".join(
            title_tokens[:7]
        )
        queries.append(
            (
                "CORE_TITLE",
                f"site:{domain} {core}",
            )
        )

    # Deduplicate query strings.
    output = []
    seen = set()

    for mode, query in queries:
        if query in seen:
            continue

        seen.add(query)
        output.append(
            (mode, query)
        )

    return output


def _publisher_internal_search_urls(
    article,
):
    source = article.get("source", "")
    domain = _source_domain_hint(source)

    if not domain:
        return []

    title = _clean_news_title(
        article.get("title", ""),
        source,
    )

    ticker = (
        article.get("details", {})
        .get("ticker")
        or ""
    )

    event_terms = _article_event_search_terms(
        article
    )

    query_text = " ".join(
        x
        for x in [
            ticker,
            event_terms[0]
            if event_terms
            else "",
            " ".join(
                _title_tokens(title)[:8]
            ),
        ]
        if x
    )

    q = quote_plus(query_text)

    bases = [
        f"https://{domain}/search?q={q}",
        f"https://{domain}/search?query={q}",
        f"https://{domain}/search?keyword={q}",
        f"https://{domain}/?s={q}",
    ]

    # Add www variant when source domain is bare.
    if not domain.startswith("www."):
        bases.extend([
            f"https://www.{domain}/search?q={q}",
            f"https://www.{domain}/?s={q}",
        ])

    output = []
    seen = set()

    for url in bases:
        if url not in seen:
            seen.add(url)
            output.append(url)

    return output


def _same_publisher_domain(
    url,
    domain,
):
    if not url or not domain:
        return False

    host = _host(url)

    return (
        host == domain
        or host.endswith("." + domain)
        or domain.endswith("." + host)
    )


def _publisher_anchor_score(
    url,
    anchor_text,
    article,
    domain,
):
    score = 0

    if _same_publisher_domain(
        url,
        domain,
    ):
        score += 40
    else:
        return -100

    title = _clean_news_title(
        article.get("title", ""),
        article.get("source", ""),
    )

    title_score = _title_similarity_score(
        title,
        anchor_text,
    )

    score += int(
        title_score * 0.6
    )

    ticker = (
        article.get("details", {})
        .get("ticker")
        or ""
    )

    low_text = (
        anchor_text or ""
    ).lower()

    low_url = (
        url or ""
    ).lower()

    if (
        ticker
        and ticker.lower()
        in (
            low_text
            + " "
            + low_url
        )
    ):
        score += 12

    for term in _article_event_search_terms(
        article
    ):
        if term.lower() in (
            low_text
            + " "
            + low_url
        ):
            score += 10
            break

    path = urlparse(url).path or ""

    if len(
        path.strip("/")
    ) >= 12:
        score += 8

    if any(
        bad in low_url
        for bad in (
            "/tag/",
            "/category/",
            "/author/",
            "/login",
            "/search",
            "/privacy",
            "/about",
        )
    ):
        score -= 25

    return score


def _extract_internal_search_candidates(
    html_text,
    base_url,
    article,
    domain,
):
    if not html_text:
        return []

    soup = BeautifulSoup(
        html_text,
        "html.parser",
    )

    candidates = []
    seen = set()

    for a in soup.find_all(
        "a",
        href=True,
    ):
        href = urljoin(
            base_url,
            a.get("href", "").strip(),
        )

        if not href.startswith(
            ("http://", "https://")
        ):
            continue

        if not _same_publisher_domain(
            href,
            domain,
        ):
            continue

        if href in seen:
            continue

        seen.add(href)

        text = normalize(
            a.get_text(
                " ",
                strip=True,
            )
        )

        score = _publisher_anchor_score(
            href,
            text,
            article,
            domain,
        )

        if score <= 0:
            continue

        candidates.append({
            "url": href,
            "score": score,
            "anchor_text": text,
            "origin": "INTERNAL_SEARCH",
        })

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return candidates[
        :PUBLISHER_DIRECT_MAX_CANDIDATES
    ]


async def _publisher_public_search_candidates(
    client,
    article,
):
    if not PUBLISHER_PUBLIC_SEARCH_ENABLED:
        return []

    source = article.get("source", "")
    domain = _source_domain_hint(source)

    if not domain:
        return []

    results = []
    seen = set()

    for mode, query in (
        _publisher_search_queries(
            article
        )
    ):
        search_url = (
            "https://html.duckduckgo.com/html/?q="
            + quote_plus(query)
        )

        try:
            response = await client.get(
                search_url,
                timeout=PUBLISHER_DIRECT_TIMEOUT_SECONDS,
                follow_redirects=True,
            )
        except Exception:
            continue

        if response.status_code >= 400:
            continue

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        for a in soup.select(
            "a.result__a, "
            ".result__title a, "
            "a[href]"
        ):
            href = (
                _extract_result_url_from_search(
                    a.get("href", "")
                )
            )

            if not href:
                continue

            if not _same_publisher_domain(
                href,
                domain,
            ):
                continue

            if href in seen:
                continue

            seen.add(href)

            text = normalize(
                a.get_text(
                    " ",
                    strip=True,
                )
            )

            score = _publisher_anchor_score(
                href,
                text,
                article,
                domain,
            )

            score += {
                "EXACT_TITLE": 25,
                "TICKER_EVENT_VALUE": 20,
                "TICKER_EVENT": 15,
                "CORE_TITLE": 5,
            }.get(mode, 0)

            results.append({
                "url": href,
                "score": score,
                "anchor_text": text,
                "origin": mode,
            })

        # If exact-title search already found multiple strong
        # candidates, avoid unnecessary additional queries.
        strong = [
            item
            for item in results
            if item["score"] >= 70
        ]

        if len(strong) >= 3:
            break

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return results[
        :PUBLISHER_DIRECT_MAX_CANDIDATES
    ]


async def _publisher_internal_candidates(
    client,
    article,
):
    if not PUBLISHER_INTERNAL_SEARCH_ENABLED:
        return []

    domain = _source_domain_hint(
        article.get("source", "")
    )

    if not domain:
        return []

    output = []
    seen = set()

    for search_url in (
        _publisher_internal_search_urls(
            article
        )
    ):
        try:
            response = await client.get(
                search_url,
                timeout=PUBLISHER_DIRECT_TIMEOUT_SECONDS,
                follow_redirects=True,
            )
        except Exception:
            continue

        if response.status_code >= 400:
            continue

        if "html" not in (
            response.headers.get(
                "content-type",
                "",
            ).lower()
        ):
            continue

        candidates = (
            _extract_internal_search_candidates(
                response.text,
                str(response.url),
                article,
                domain,
            )
        )

        for item in candidates:
            if item["url"] in seen:
                continue

            seen.add(
                item["url"]
            )
            output.append(
                item
            )

        if len(output) >= (
            PUBLISHER_DIRECT_MAX_CANDIDATES
        ):
            break

    output.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return output[
        :PUBLISHER_DIRECT_MAX_CANDIDATES
    ]


def _extract_candidate_published_time(
    soup,
):
    values = []

    for attrs in (
        {"property": "article:published_time"},
        {"name": "article:published_time"},
        {"name": "date"},
        {"name": "pubdate"},
        {"itemprop": "datePublished"},
    ):
        node = soup.find(
            "meta",
            attrs=attrs,
        )

        if node and node.get(
            "content"
        ):
            values.append(
                node.get(
                    "content"
                )
            )

    for script in soup.find_all(
        "script",
        attrs={
            "type": "application/ld+json",
        },
    ):
        raw = (
            script.string
            or script.get_text(
                " ",
                strip=True,
            )
        )

        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        stack = [data]

        while stack:
            obj = stack.pop()

            if isinstance(obj, dict):
                date_value = obj.get(
                    "datePublished"
                )

                if isinstance(
                    date_value,
                    str,
                ):
                    values.append(
                        date_value
                    )

                stack.extend(
                    obj.values()
                )

            elif isinstance(obj, list):
                stack.extend(obj)

    return values[0] if values else None


def _date_match_bonus(
    article,
    candidate_date,
):
    if not candidate_date:
        return 0

    published_dt = article.get(
        "published_dt"
    )

    if not published_dt:
        return 0

    try:
        value = candidate_date.strip()
        value = value.replace(
            "Z",
            "+00:00",
        )

        candidate_dt = (
            datetime.fromisoformat(
                value
            )
        )

        if candidate_dt.tzinfo is None:
            candidate_dt = (
                candidate_dt.replace(
                    tzinfo=timezone.utc
                )
            )

        if published_dt.tzinfo is None:
            published_dt = (
                published_dt.replace(
                    tzinfo=timezone.utc
                )
            )

        diff_days = abs(
            (
                candidate_dt
                - published_dt
            ).total_seconds()
        ) / 86400

        if diff_days <= 1:
            return 15
        if diff_days <= 3:
            return 10
        if diff_days <= 7:
            return 5
        if diff_days > 60:
            return -15

    except Exception:
        return 0

    return 0


async def _validate_publisher_candidate(
    client,
    candidate,
    article,
):
    fetched = await _fetch_html(
        client,
        candidate["url"],
    )

    if not fetched:
        return None

    if fetched.get("status") == "RESTRICTED":
        return {
            **candidate,
            "status": "RESTRICTED",
            "article_status": "RESTRICTED",
            "final_score": candidate.get(
                "score",
                0,
            ),
            "text": "",
            "page_title": "",
        }

    final_url = fetched.get("url")

    domain = _source_domain_hint(
        article.get("source", "")
    )

    if not _same_publisher_domain(
        final_url,
        domain,
    ):
        return None

    soup = BeautifulSoup(
        fetched.get("html", ""),
        "html.parser",
    )

    meta_urls = _extract_meta_urls(
        soup,
        final_url,
    )

    resolved_url = final_url

    for _, meta_url in meta_urls:
        if _same_publisher_domain(
            meta_url,
            domain,
        ):
            resolved_url = meta_url
            break

    page_title = ""

    for attrs in (
        {"property": "og:title"},
        {"name": "twitter:title"},
    ):
        node = soup.find(
            "meta",
            attrs=attrs,
        )

        if node and node.get(
            "content"
        ):
            page_title = normalize(
                node.get("content")
            )
            break

    if not page_title:
        h1 = soup.find("h1")

        if h1:
            page_title = normalize(
                h1.get_text(
                    " ",
                    strip=True,
                )
            )

    if not page_title and soup.title:
        page_title = normalize(
            soup.title.get_text(
                " ",
                strip=True,
            )
        )

    readable = (
        extract_readable_text_from_html(
            fetched.get("html", "")
        )
    )

    title = _clean_news_title(
        article.get("title", ""),
        article.get("source", ""),
    )

    comparison_text = " ".join([
        page_title,
        readable.get("text", "")[
            :1800
        ],
    ])

    title_score = (
        _title_similarity_score(
            title,
            comparison_text,
        )
    )

    score = candidate.get(
        "score",
        0,
    )

    score += int(
        title_score * 0.75
    )

    ticker = (
        article.get("details", {})
        .get("ticker")
        or ""
    )

    low_context = (
        comparison_text.lower()
    )

    if (
        ticker
        and ticker.lower()
        in low_context
    ):
        score += 15

    event_match = False

    for term in _article_event_search_terms(
        article
    ):
        if term.lower() in low_context:
            score += 12
            event_match = True
            break

    published_time = (
        _extract_candidate_published_time(
            soup
        )
    )

    score += _date_match_bonus(
        article,
        published_time,
    )

    return {
        **candidate,
        "url": resolved_url,
        "status": "OK",
        "article_status": readable.get(
            "status",
            "FAILED",
        ),
        "text": readable.get(
            "text",
            "",
        ),
        "page_title": page_title,
        "title_score": title_score,
        "ticker_match": (
            bool(ticker)
            and ticker.lower()
            in low_context
        ),
        "event_match": event_match,
        "published_time": published_time,
        "final_score": score,
    }


async def resolve_publisher_direct(
    client,
    article,
):
    """
    V5.4 primary resolver:
      1) known source -> publisher domain
      2) publisher internal search
      3) public exact-title/site search
      4) candidate validation with title/ticker/event/date
    """
    if not PUBLISHER_DIRECT_ENABLED:
        return {
            "status": False,
            "method": "DISABLED",
            "attempts": [],
            "candidates": [],
        }

    source = article.get(
        "source",
        "",
    )

    domain = _source_domain_hint(
        source
    )

    if not domain:
        return {
            "status": False,
            "method": "NO_DOMAIN",
            "domain": None,
            "attempts": [],
            "candidates": [],
        }

    cache_key = (
        domain
        + "|"
        + _clean_news_title(
            article.get("title", ""),
            source,
        )
    )

    now = time.time()
    cached = PUBLISHER_DIRECT_CACHE.get(
        cache_key
    )

    if cached and (
        now - cached["cached_at"]
        <= PUBLISHER_DIRECT_CACHE_MINUTES
        * 60
    ):
        return {
            **cached["data"],
            "cache_hit": True,
        }

    attempts = []
    candidate_map = {}

    internal = (
        await _publisher_internal_candidates(
            client,
            article,
        )
    )

    attempts.append({
        "method": "INTERNAL_SEARCH",
        "count": len(internal),
    })

    for item in internal:
        current = candidate_map.get(
            item["url"]
        )

        if (
            current is None
            or item["score"]
            > current["score"]
        ):
            candidate_map[
                item["url"]
            ] = item

    public = (
        await _publisher_public_search_candidates(
            client,
            article,
        )
    )

    attempts.append({
        "method": "PUBLIC_SEARCH",
        "count": len(public),
    })

    for item in public:
        current = candidate_map.get(
            item["url"]
        )

        if (
            current is None
            or item["score"]
            > current["score"]
        ):
            candidate_map[
                item["url"]
            ] = item

    candidates = list(
        candidate_map.values()
    )

    candidates.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    validated = []

    for item in candidates[
        :PUBLISHER_DIRECT_MAX_CANDIDATES
    ]:
        checked = (
            await _validate_publisher_candidate(
                client,
                item,
                article,
            )
        )

        if not checked:
            continue

        validated.append(
            checked
        )

    validated.sort(
        key=lambda item: item.get(
            "final_score",
            -999,
        ),
        reverse=True,
    )

    best = (
        validated[0]
        if validated
        else None
    )

    if (
        best
        and best.get(
            "final_score",
            0,
        )
        >= PUBLISHER_DIRECT_MIN_SCORE
    ):
        result = {
            "status": True,
            "method": (
                "PUBLISHER_INTERNAL"
                if best.get("origin")
                == "INTERNAL_SEARCH"
                else "PUBLISHER_SEARCH"
            ),
            "domain": domain,
            "url": best["url"],
            "text": best.get(
                "text",
                "",
            ),
            "article_status": best.get(
                "article_status",
                "FAILED",
            ),
            "best_score": best.get(
                "final_score"
            ),
            "title_score": best.get(
                "title_score"
            ),
            "ticker_match": best.get(
                "ticker_match"
            ),
            "event_match": best.get(
                "event_match"
            ),
            "published_time": best.get(
                "published_time"
            ),
            "attempts": attempts,
            "candidates": [
                {
                    "host": _host(
                        item["url"]
                    ),
                    "score": item.get(
                        "final_score",
                        item.get(
                            "score"
                        ),
                    ),
                    "origin": item.get(
                        "origin"
                    ),
                }
                for item in validated[:5]
            ],
            "cache_hit": False,
        }

        PUBLISHER_DIRECT_CACHE[
            cache_key
        ] = {
            "cached_at": now,
            "data": result,
        }

        return result

    result = {
        "status": False,
        "method": "NO_CONFIDENT_MATCH",
        "domain": domain,
        "best_score": (
            best.get("final_score")
            if best
            else None
        ),
        "attempts": attempts,
        "candidates": [
            {
                "host": _host(
                    item["url"]
                ),
                "score": item.get(
                    "final_score",
                    item.get("score"),
                ),
                "origin": item.get(
                    "origin"
                ),
            }
            for item in validated[:5]
        ],
        "cache_hit": False,
    }

    PUBLISHER_DIRECT_CACHE[
        cache_key
    ] = {
        "cached_at": now,
        "data": result,
    }

    return result


async def _validate_candidate_article(
    client,
    candidate_url,
    title,
):
    fetched = await _fetch_html(
        client,
        candidate_url,
    )

    if not fetched:
        return None

    if fetched["status"] == "RESTRICTED":
        return {
            "url": fetched.get("url"),
            "status": "RESTRICTED",
            "article_status": "RESTRICTED",
            "text": "",
            "title_score": 0,
        }

    final_url = fetched["url"]

    if _is_google_host(_host(final_url)):
        return None

    soup = BeautifulSoup(
        fetched["html"],
        "html.parser",
    )

    # Prefer publisher canonical URL.
    meta_urls = _extract_meta_urls(
        soup,
        final_url,
    )

    resolved_url = final_url

    for _, meta_url in meta_urls:
        if not _is_google_host(_host(meta_url)):
            resolved_url = meta_url
            break

    page_title = ""

    og_title = soup.find(
        "meta",
        attrs={"property": "og:title"},
    )

    if og_title and og_title.get("content"):
        page_title = normalize(
            og_title.get("content")
        )

    if not page_title and soup.title:
        page_title = normalize(
            soup.title.get_text(
                " ",
                strip=True,
            )
        )

    readable = extract_readable_text_from_html(
        fetched["html"]
    )

    comparison_text = " ".join([
        page_title,
        readable.get("text", "")[:1000],
    ])

    title_score = _title_similarity_score(
        title,
        comparison_text,
    )

    return {
        "url": resolved_url,
        "status": "OK",
        "article_status": readable["status"],
        "text": readable["text"],
        "title_score": title_score,
        "page_title": page_title,
    }


async def resolve_publisher_url(
    client,
    article,
    first_fetch=None,
):
    """
    V5.4 order:
    0. Publisher Direct Resolver
    1. Google News decoder
    2. redirect/canonical/external Google page heuristics
    3. old public exact-title search fallback
    """
    if not SOURCE_RESOLVER_ENABLED:
        return {
            "status": "DISABLED",
            "url": None,
            "text": "",
            "article_status": "FAILED",
            "attempts": [],
        }

    cache_key = (
        article.get("link")
        or article.get("title")
    )

    now = time.time()
    cached = RESOLVER_CACHE.get(
        cache_key
    )

    if cached and (
        now - cached["cached_at"]
        <= RESOLVER_CACHE_MINUTES * 60
    ):
        return cached["data"]

    attempts = []
    title = article.get(
        "title",
        "",
    )
    source = article.get(
        "source",
        "",
    )

    # ========================================================
    # V5.4 METHOD 0 — Publisher Direct Resolver
    # ========================================================
    publisher = (
        await resolve_publisher_direct(
            client,
            article,
        )
    )

    if publisher.get("status"):
        method = publisher.get(
            "method",
            "PUBLISHER_SEARCH",
        )

        result = {
            "status": method,
            "url": publisher.get(
                "url"
            ),
            "text": publisher.get(
                "text",
                "",
            ),
            "article_status": publisher.get(
                "article_status",
                "FAILED",
            ),
            "attempts": [
                "PUBLISHER_DIRECT:SUCCESS",
                "DOMAIN:"
                + str(
                    publisher.get(
                        "domain",
                        "—",
                    )
                ),
                "SCORE:"
                + str(
                    publisher.get(
                        "best_score",
                        "—",
                    )
                ),
                "TITLE_SCORE:"
                + str(
                    publisher.get(
                        "title_score",
                        "—",
                    )
                ),
            ],
            "publisher_debug": publisher,
            "decoder_method": None,
        }

        RESOLVER_CACHE[
            cache_key
        ] = {
            "cached_at": now,
            "data": result,
        }

        return result

    attempts.append(
        "PUBLISHER_DIRECT:"
        + str(
            publisher.get(
                "method",
                "FAILED",
            )
        )
    )

    attempts.append(
        "PUBLISHER_DOMAIN:"
        + str(
            publisher.get(
                "domain",
                "NONE",
            )
        )
    )

    attempts.append(
        "PUBLISHER_SCORE:"
        + str(
            publisher.get(
                "best_score",
                "—",
            )
        )
    )

    # ========================================================
    # METHOD 1 — Existing Google News decoder
    # ========================================================
    decoded = (
        await decode_google_news_url_core(
            client,
            article.get(
                "link",
                "",
            ),
            source=source,
        )
    )

    if (
        decoded.get("status")
        and decoded.get(
            "decoded_url"
        )
    ):
        decoded_url = decoded[
            "decoded_url"
        ]

        decoder_method = decoded.get(
            "method",
            "DIRECT",
        )

        attempts.append(
            f"GNEWS_{decoder_method}"
        )

        validated = (
            await _validate_candidate_article(
                client,
                decoded_url,
                title,
            )
        )

        resolver_status = (
            "GNEWS_DYNAMIC"
            if decoder_method
            == "DYNAMIC_SIGNATURE"
            else (
                "GNEWS_BATCH"
                if decoder_method in (
                    "BATCH",
                    "BATCH_MULTI",
                )
                else (
                    "GNEWS_LEGACY"
                    if decoder_method
                    == "LEGACY"
                    else "GNEWS_DIRECT"
                )
            )
        )

        if validated:
            result = {
                "status": resolver_status,
                "url": validated.get(
                    "url",
                    decoded_url,
                ),
                "text": validated.get(
                    "text",
                    "",
                ),
                "article_status": (
                    validated.get(
                        "article_status",
                        "FAILED",
                    )
                ),
                "attempts": (
                    attempts
                    + [
                        "TITLE_SCORE:"
                        + str(
                            validated.get(
                                "title_score",
                                0,
                            )
                        )
                    ]
                ),
                "decoder_method": (
                    decoder_method
                ),
                "publisher_debug": (
                    publisher
                ),
            }
        else:
            result = {
                "status": resolver_status,
                "url": decoded_url,
                "text": "",
                "article_status": "FAILED",
                "attempts": attempts,
                "decoder_method": (
                    decoder_method
                ),
                "publisher_debug": (
                    publisher
                ),
            }

        RESOLVER_CACHE[
            cache_key
        ] = {
            "cached_at": now,
            "data": result,
        }

        return result

    if decoded.get("method"):
        attempts.append(
            "GNEWS_DECODER:"
            + decoded.get(
                "method",
                "FAILED",
            )
        )

        protocol = decoded.get(
            "protocol_debug",
            {},
        )

        if protocol:
            attempts.append(
                "PARAMS:"
                + (
                    "YES"
                    if protocol.get(
                        "params_found"
                    )
                    else "NO"
                )
            )

            attempts.append(
                "PARAM_MODE:"
                + str(
                    protocol.get(
                        "params_method",
                        "NONE",
                    )
                )
            )

        debug = decoded.get(
            "decoder_debug",
            {},
        )

        if debug:
            attempts.append(
                "RPC:"
                + (
                    "YES"
                    if debug.get(
                        "rpc_found"
                    )
                    else "NO"
                )
            )

            attempts.append(
                "URLS:"
                + str(
                    debug.get(
                        "candidate_count",
                        0,
                    )
                )
            )

    # ========================================================
    # METHOD 2 — Existing Google page resolver heuristics
    # ========================================================
    first = first_fetch

    if first is None:
        first = await _fetch_html(
            client,
            article.get(
                "link",
                "",
            ),
        )

    if first:
        if (
            first.get("status")
            == "RESTRICTED"
        ):
            result = {
                "status": "FAILED",
                "url": first.get(
                    "url"
                ),
                "text": "",
                "article_status": "RESTRICTED",
                "attempts": (
                    attempts
                    + [
                        "DIRECT_RESTRICTED"
                    ]
                ),
                "publisher_debug": (
                    publisher
                ),
            }

            RESOLVER_CACHE[
                cache_key
            ] = {
                "cached_at": now,
                "data": result,
            }

            return result

        final_url = first.get("url")
        final_host = _host(
            final_url
        )

        if (
            final_url
            and not _is_google_host(
                final_host
            )
        ):
            validated = (
                await _validate_candidate_article(
                    client,
                    final_url,
                    title,
                )
            )

            if validated:
                attempts.append(
                    "DIRECT:"
                    + str(
                        validated.get(
                            "title_score",
                            0,
                        )
                    )
                )

                if (
                    validated.get(
                        "title_score",
                        0,
                    )
                    >= RESOLVER_TITLE_MIN_SCORE
                    or validated.get(
                        "article_status"
                    )
                    == "FULL"
                ):
                    result = {
                        "status": "DIRECT",
                        "url": validated[
                            "url"
                        ],
                        "text": validated[
                            "text"
                        ],
                        "article_status": (
                            validated[
                                "article_status"
                            ]
                        ),
                        "attempts": attempts,
                        "publisher_debug": (
                            publisher
                        ),
                    }

                    RESOLVER_CACHE[
                        cache_key
                    ] = {
                        "cached_at": now,
                        "data": result,
                    }

                    return result

        soup = BeautifulSoup(
            first.get("html", ""),
            "html.parser",
        )

        for method, meta_url in (
            _extract_meta_urls(
                soup,
                final_url
                or article.get(
                    "link",
                    "",
                ),
            )
        ):
            if _is_google_host(
                _host(meta_url)
            ):
                continue

            validated = (
                await _validate_candidate_article(
                    client,
                    meta_url,
                    title,
                )
            )

            if not validated:
                continue

            attempts.append(
                method
                + ":"
                + str(
                    validated.get(
                        "title_score",
                        0,
                    )
                )
            )

            if (
                validated.get(
                    "title_score",
                    0,
                )
                >= RESOLVER_TITLE_MIN_SCORE
                or validated.get(
                    "article_status"
                )
                == "FULL"
            ):
                result = {
                    "status": "CANONICAL",
                    "url": validated[
                        "url"
                    ],
                    "text": validated[
                        "text"
                    ],
                    "article_status": (
                        validated[
                            "article_status"
                        ]
                    ),
                    "attempts": attempts,
                    "publisher_debug": (
                        publisher
                    ),
                }

                RESOLVER_CACHE[
                    cache_key
                ] = {
                    "cached_at": now,
                    "data": result,
                }

                return result

        candidates = (
            _external_link_candidates_v52(
                soup,
                final_url
                or article.get(
                    "link",
                    "",
                ),
                source,
                title,
            )
        )

        for candidate in candidates[
            :RESOLVER_MAX_CANDIDATES
        ]:
            validated = (
                await _validate_candidate_article(
                    client,
                    candidate[
                        "url"
                    ],
                    title,
                )
            )

            if not validated:
                continue

            combined_score = max(
                candidate.get(
                    "score",
                    0,
                ),
                validated.get(
                    "title_score",
                    0,
                ),
            )

            attempts.append(
                "EXTERNAL:"
                + str(
                    combined_score
                )
            )

            if (
                validated.get(
                    "title_score",
                    0,
                )
                >= RESOLVER_TITLE_MIN_SCORE
            ):
                result = {
                    "status": (
                        "TITLE_MATCH"
                        if validated.get(
                            "title_score",
                            0,
                        )
                        >= 60
                        else "EXTERNAL_LINK"
                    ),
                    "url": validated[
                        "url"
                    ],
                    "text": validated[
                        "text"
                    ],
                    "article_status": (
                        validated[
                            "article_status"
                        ]
                    ),
                    "attempts": attempts,
                    "publisher_debug": (
                        publisher
                    ),
                }

                RESOLVER_CACHE[
                    cache_key
                ] = {
                    "cached_at": now,
                    "data": result,
                }

                return result

    # ========================================================
    # METHOD 3 — Old public title-search fallback
    # ========================================================
    search_candidates = (
        await _search_exact_title_candidates(
            client,
            title,
            source,
        )
    )

    for candidate in search_candidates:
        validated = (
            await _validate_candidate_article(
                client,
                candidate["url"],
                title,
            )
        )

        if not validated:
            continue

        combined_score = max(
            candidate.get(
                "score",
                0,
            ),
            validated.get(
                "title_score",
                0,
            ),
        )

        attempts.append(
            "SEARCH:"
            + str(combined_score)
        )

        if (
            validated.get(
                "title_score",
                0,
            )
            >= RESOLVER_TITLE_MIN_SCORE
        ):
            result = {
                "status": "SEARCH_FALLBACK",
                "url": validated[
                    "url"
                ],
                "text": validated[
                    "text"
                ],
                "article_status": (
                    validated[
                        "article_status"
                    ]
                ),
                "attempts": attempts,
                "publisher_debug": (
                    publisher
                ),
            }

            RESOLVER_CACHE[
                cache_key
            ] = {
                "cached_at": now,
                "data": result,
            }

            return result

    result = {
        "status": "GOOGLE_ONLY",
        "url": None,
        "text": "",
        "article_status": "FAILED",
        "attempts": attempts,
        "publisher_debug": (
            publisher
        ),
    }

    RESOLVER_CACHE[
        cache_key
    ] = {
        "cached_at": now,
        "data": result,
    }

    return result



def _external_link_candidates(soup, base_url, source):
    source_tokens = _source_tokens(source)
    candidates = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a.get("href", "").strip())

        if not href.startswith(("http://", "https://")):
            continue

        host = _host(href)

        if not host or _is_google_host(host):
            continue

        if href in seen:
            continue

        seen.add(href)
        anchor_text = normalize(a.get_text(" ", strip=True)).lower()
        score = 0

        for token in source_tokens:
            if token in host:
                score += 8
            if token in anchor_text:
                score += 3

        if "article" in href.lower():
            score += 1

        candidates.append((score, href))

    candidates.sort(key=lambda x: x[0], reverse=True)
    return [url for _, url in candidates[:10]]


def _jsonld_article_bodies(soup):
    bodies = []

    def walk(obj):
        if isinstance(obj, dict):
            body = obj.get("articleBody")
            if isinstance(body, str) and len(body.strip()) >= 100:
                bodies.append(normalize(body))

            for value in obj.values():
                walk(value)

        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"},
    ):
        raw = script.string or script.get_text(" ", strip=True)

        if not raw:
            continue

        try:
            data = json.loads(raw)
            walk(data)
        except Exception:
            continue

    return bodies


def extract_readable_text_from_html(html_text):
    if not BS4_AVAILABLE:
        return {
            "text": "",
            "status": "FAILED",
            "restricted": False,
        }

    soup = BeautifulSoup(html_text, "html.parser")
    meta_parts = []

    for attrs in [
        {"name": "description"},
        {"property": "og:description"},
        {"name": "twitter:description"},
    ]:
        node = soup.find("meta", attrs=attrs)
        if node and node.get("content"):
            meta_parts.append(normalize(node.get("content")))

    jsonld_bodies = _jsonld_article_bodies(soup)

    for tag_name in [
        "script", "style", "noscript", "svg",
        "nav", "footer", "header", "aside", "form",
    ]:
        for node in soup.find_all(tag_name):
            node.decompose()

    paragraphs = []
    selectors = [
        "article p",
        "main p",
        "[itemprop='articleBody'] p",
        ".article-body p",
        ".article-content p",
        ".post-content p",
        ".entry-content p",
    ]

    for selector in selectors:
        for p in soup.select(selector):
            text = normalize(p.get_text(" ", strip=True))
            if len(text) >= 40:
                paragraphs.append(text)

        if sum(len(x) for x in paragraphs) >= 1200:
            break

    if sum(len(x) for x in paragraphs) < 500:
        for p in soup.find_all("p"):
            text = normalize(p.get_text(" ", strip=True))
            if len(text) >= 50:
                paragraphs.append(text)

    unique = []
    seen = set()

    for part in meta_parts + jsonld_bodies + paragraphs:
        key = part.lower()
        if key not in seen:
            seen.add(key)
            unique.append(part)

    text = normalize(" ".join(unique))
    text = text[:MAX_ARTICLE_CHARS]
    low = text.lower()

    restricted = any(
        phrase in low
        for phrase in RESTRICTED_PAGE_PHRASES
    )

    if len(text) >= 1200:
        status = "FULL"
    elif len(text) >= 250:
        status = "PARTIAL"
    else:
        status = "FAILED"

    if restricted and status != "FULL":
        status = "RESTRICTED"

    return {
        "text": text,
        "status": status,
        "restricted": restricted,
    }


async def _fetch_html(client, url):
    try:
        response = await client.get(
            url,
            timeout=ARTICLE_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
    except Exception:
        return None

    if response.status_code in (401, 402, 403):
        return {
            "status": "RESTRICTED",
            "url": str(response.url),
            "html": "",
            "content_type": response.headers.get("content-type", ""),
        }

    if response.status_code >= 400:
        return None

    content_type = response.headers.get("content-type", "").lower()
    if "html" not in content_type:
        return None

    return {
        "status": "OK",
        "url": str(response.url),
        "html": response.text,
        "content_type": content_type,
    }


async def fetch_public_article_text(article):
    """
    V5.2:
    resolve Google News URL ke publisher URL terlebih dahulu,
    lalu baca artikel publik. Tidak membypass paywall/login/CAPTCHA.
    """
    if (
        not DEEP_EXTRACTION_ENABLED
        or not BS4_AVAILABLE
    ):
        return {
            "status": "DISABLED",
            "text": "",
            "source_url": None,
            "resolver_status": "DISABLED",
            "resolver_attempts": [],
        }

    key = article.get("link") or article.get("title")
    now = time.time()
    cached = ARTICLE_CACHE.get(key)

    if cached and (
        now - cached["cached_at"]
        <= ARTICLE_CACHE_MINUTES * 60
    ):
        return cached["data"]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/122 Safari/537.36"
        ),
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.7",
    }

    result = {
        "status": "FAILED",
        "text": "",
        "source_url": None,
        "resolver_status": "FAILED",
        "resolver_attempts": [],
    }

    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
    ) as client:
        first = await _fetch_html(
            client,
            article.get("link", ""),
        )

        # If RSS link already resolves directly to publisher,
        # still route through resolver so canonical/title validation occurs.
        resolved = await resolve_publisher_url(
            client,
            article,
            first_fetch=first,
        )

        resolver_status = resolved.get(
            "status",
            "FAILED",
        )
        decoder_method = resolved.get("decoder_method")
        publisher_debug = resolved.get(
            "publisher_debug",
            {},
        )

        resolved_url = resolved.get("url")
        resolved_text = resolved.get("text") or ""
        article_status = resolved.get(
            "article_status",
            "FAILED",
        )

        if resolved_url and resolved_text:
            result = {
                "status": article_status,
                "text": resolved_text,
                "source_url": resolved_url,
                "resolver_status": resolver_status,
                "resolver_attempts": resolved.get(
                    "attempts",
                    [],
                ),
                "decoder_method": decoder_method,
                "publisher_debug": publisher_debug,
            }

        elif resolved_url and article_status == "RESTRICTED":
            result = {
                "status": "RESTRICTED",
                "text": "",
                "source_url": resolved_url,
                "resolver_status": resolver_status,
                "resolver_attempts": resolved.get(
                    "attempts",
                    [],
                ),
                "decoder_method": decoder_method,
                "publisher_debug": publisher_debug,
            }

        else:
            # Preserve GOOGLE_ONLY semantics when no publisher URL was found.
            result = {
                "status": "GOOGLE_ONLY"
                if resolver_status == "GOOGLE_ONLY"
                else "FAILED",
                "text": "",
                "source_url": resolved_url,
                "resolver_status": resolver_status,
                "resolver_attempts": resolved.get(
                    "attempts",
                    [],
                ),
                "decoder_method": decoder_method,
                "publisher_debug": publisher_debug,
            }

    ARTICLE_CACHE[key] = {
        "cached_at": now,
        "data": result,
    }

    return result


def extract_labeled_date(text, labels):
    for label in labels:
        pattern = (
            re.escape(label)
            + r".{0,100}?("
            + DATE_TOKEN_PATTERN
            + r")"
        )
        m = re.search(pattern, text, flags=re.I)
        if m:
            return normalize(m.group(1))
    return None


def extract_schedule_details(text, event):
    schedule = {}

    if event == "RIGHTS ISSUE":
        schedule["cum_right"] = extract_labeled_date(
            text, ["cum-right", "cum right", "cum HMETD"]
        )
        schedule["ex_right"] = extract_labeled_date(
            text, ["ex-right", "ex right", "ex HMETD"]
        )
        schedule["recording_date"] = extract_labeled_date(
            text,
            ["recording date", "tanggal pencatatan", "daftar pemegang saham"],
        )
        schedule["rights_trading"] = extract_labeled_date(
            text,
            [
                "periode perdagangan HMETD",
                "perdagangan HMETD dimulai",
                "HMETD diperdagangkan",
            ],
        )
        schedule["rights_trading_end"] = extract_labeled_date(
            text,
            [
                "akhir perdagangan HMETD",
                "perdagangan HMETD berakhir",
                "akhir periode perdagangan HMETD",
            ],
        )
        schedule["rights_payment"] = extract_labeled_date(
            text,
            [
                "pembayaran pemesanan tambahan",
                "tanggal pembayaran",
                "pembayaran HMETD",
            ],
        )

    elif event == "IPO":
        schedule["bookbuilding"] = extract_labeled_date(
            text, ["bookbuilding", "book building", "penawaran awal"]
        )
        schedule["offering"] = extract_labeled_date(
            text, ["penawaran umum", "masa penawaran umum"]
        )
        schedule["allotment"] = extract_labeled_date(
            text, ["penjatahan", "tanggal penjatahan"]
        )
        schedule["distribution"] = extract_labeled_date(
            text,
            ["distribusi saham", "distribusi saham secara elektronik"],
        )
        schedule["listing"] = extract_labeled_date(
            text,
            ["listing", "pencatatan saham", "mulai diperdagangkan"],
        )

    else:
        schedule["tender_start"] = extract_labeled_date(
            text,
            [
                "periode penawaran tender dimulai",
                "penawaran tender dimulai",
                "awal periode tender",
                "masa penawaran tender",
            ],
        )
        schedule["tender_end"] = extract_labeled_date(
            text,
            [
                "periode penawaran tender berakhir",
                "penawaran tender berakhir",
                "akhir periode tender",
                "batas akhir tender",
            ],
        )
        schedule["tender_payment"] = extract_labeled_date(
            text,
            [
                "tanggal pembayaran tender",
                "pembayaran penawaran tender",
                "pembayaran tender",
            ],
        )
        schedule["transaction_completion"] = extract_labeled_date(
            text,
            [
                "penyelesaian transaksi",
                "tanggal penyelesaian",
                "transaction completion",
                "completion date",
            ],
        )

    return {k: v for k, v in schedule.items() if v}


def _merge_unique(old_items, new_items):
    result = []
    seen = set()

    for value in (old_items or []) + (new_items or []):
        key = normalize(str(value)).lower()
        if key and key not in seen:
            seen.add(key)
            result.append(value)

    return result


def _filled(value):
    return value not in (None, "", [], {})


def merge_deep_details(article, deep_text):
    evt = article["event_type"]
    d = article["details"]
    before = {k: bool(_filled(v)) for k, v in d.items()}

    deep_ticker = extract_ticker(
        article["title"],
        deep_text,
        article["geo"],
    )
    if not d.get("ticker") and deep_ticker:
        d["ticker"] = deep_ticker

    # V6.2.2: learn the legal issuer name from the full publisher article.
    resolve_deep_issuer_alias(article, deep_text)

    d["percentages"] = _merge_unique(
        d.get("percentages"),
        extract_percentages(deep_text),
    )

    if evt == "RIGHTS ISSUE":
        if not d.get("ratio"):
            d["ratio"] = extract_ratio(deep_text)
        if not d.get("execution_price"):
            d["execution_price"] = extract_execution_price(deep_text)
        if not d.get("standby_buyer"):
            d["standby_buyer"] = extract_standby_buyer(deep_text)

    elif evt == "IPO":
        if not d.get("price_range"):
            d["price_range"] = extract_price_range(deep_text)
        if not d.get("ipo_single_price"):
            d["ipo_single_price"] = extract_ipo_single_price(deep_text)
        if not d.get("underwriter"):
            d["underwriter"] = extract_underwriter(deep_text)

    else:
        if not d.get("tender_price"):
            d["tender_price"] = extract_tender_price(deep_text)

    if not d.get("share_count"):
        d["share_count"] = extract_share_count(deep_text)

    d["use_of_funds"] = _merge_unique(
        d.get("use_of_funds"),
        classify_use_of_funds(deep_text),
    )

    new_money = remove_price_duplicates(
        extract_money(deep_text, event=evt),
        execution_price=d.get("execution_price"),
        price_range=d.get("price_range"),
    )

    blocked_prices = {
        money_key(d.get("ipo_single_price")),
        money_key(d.get("tender_price")),
    }

    new_money = [
        x for x in new_money
        if money_key(x) not in blocked_prices
    ]

    existing_money, removed_money = sanitize_money_values(d.get("money"))
    if removed_money:
        article["money_guard_removed"] = _merge_unique(
            article.get("money_guard_removed"),
            removed_money,
        )
    d["money"] = _merge_unique(
        new_money,
        existing_money,
    )[:8]

    schedule = extract_schedule_details(deep_text, evt)
    d["schedule"] = {
        **(d.get("schedule") or {}),
        **schedule,
    }

    if evt == "IPO":
        deep_stage = classify_ipo_stage(deep_text)
    elif evt == "RIGHTS ISSUE":
        deep_stage = classify_rights_stage(deep_text)
    else:
        deep_stage = classify_ma_stage(deep_text, evt)

    current_priority = priority_level(evt, article["stage"])
    deep_priority = priority_level(evt, deep_stage)

    if (
        PRIORITY_RANK.get(deep_priority, 1)
        >= PRIORITY_RANK.get(current_priority, 1)
    ):
        article["stage"] = deep_stage

    article["priority"] = priority_level(evt, article["stage"])
    article["urgency"] = article["priority"]

    if evt == "IPO":
        article["ipo_class"] = classify_ipo_intelligence(
            deep_text,
            article["stage"],
            d,
        )

    catalyst, reasons = catalyst_assessment(
        evt,
        article["stage"],
        deep_text,
        d,
        ipo_class=article.get("ipo_class"),
    )
    article["catalyst"] = catalyst
    article["catalyst_reasons"] = reasons
    article["context"] = article_context(
        evt,
        deep_text,
        ipo_class=article.get("ipo_class"),
    )

    apply_article_integrity_guards(article)

    article["ca_score"] = corporate_action_score(article)
    article["information_score"] = article["ca_score"]

    added = []
    for k, v in d.items():
        if not before.get(k, False) and _filled(v):
            added.append(k)

    article["deep_fields_added"] = added
    return article


async def deep_enrich_article(article):
    if not DEEP_EXTRACTION_ENABLED:
        article["deep_status"] = "DISABLED"
        return article

    result = await fetch_public_article_text(article)
    article["deep_status"] = result.get("status", "FAILED")
    article["source_url"] = result.get("source_url")
    article["resolver_status"] = result.get(
        "resolver_status",
        "FAILED",
    )
    article["resolver_attempts"] = result.get(
        "resolver_attempts",
        [],
    )
    article["decoder_method"] = result.get("decoder_method")
    article["publisher_debug"] = result.get(
        "publisher_debug",
        {},
    )
    text = result.get("text") or ""

    if text:
        article["deep_text_chars"] = len(text)
        merge_deep_details(
            article,
            " ".join([
                article.get("title", ""),
                article.get("snippet", ""),
                text,
            ]),
        )

    return article


# ============================================================
# V5 MARKET DATA
# ============================================================

def _fetch_market_data_sync(ticker):
    if not YFINANCE_AVAILABLE or not MARKET_DATA_ENABLED:
        return None

    symbol = f"{ticker}.JK"

    try:
        t = yf.Ticker(symbol)
        hist = t.history(
            period="5d",
            interval="1d",
            auto_adjust=False,
        )

        if hist is None or hist.empty or "Close" not in hist:
            return None

        closes = hist["Close"].dropna()

        if closes.empty:
            return None

        last = float(closes.iloc[-1])
        prev = float(closes.iloc[-2]) if len(closes) >= 2 else None

        change_pct = None
        if prev and prev != 0:
            change_pct = ((last - prev) / prev) * 100

        volume = None
        try:
            volume_series = hist["Volume"].dropna()
            if not volume_series.empty:
                volume = int(volume_series.iloc[-1])
        except Exception:
            pass

        market_date = None
        try:
            market_date = str(closes.index[-1].date())
        except Exception:
            pass

        return {
            "ticker": ticker,
            "symbol": symbol,
            "last_price": last,
            "previous_close": prev,
            "change_pct": change_pct,
            "volume": volume,
            "market_date": market_date,
            "source": "Yahoo Finance via yfinance",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception:
        return None


async def get_market_data(ticker):
    if not ticker or not MARKET_DATA_ENABLED or not YFINANCE_AVAILABLE:
        return None

    key = ticker.upper()
    now = time.time()

    cached = MARKET_CACHE.get(key)

    if cached:
        age = now - cached["cached_at"]
        if age <= MARKET_CACHE_MINUTES * 60:
            return cached["data"]

    data = await asyncio.to_thread(
        _fetch_market_data_sync,
        key,
    )

    MARKET_CACHE[key] = {
        "cached_at": now,
        "data": data,
    }

    return data


# ============================================================
# V5 DECISION SUPPORT CALCULATIONS
# ============================================================

def calculate_rights_metrics(article):
    d = article["details"]
    market = article.get("market_data") or {}

    current = market.get("last_price")
    exercise = rupiah_to_float(d.get("execution_price"))
    old_ratio, new_ratio = parse_ratio_values(d.get("ratio"))

    metrics = {
        "current_price": current,
        "execution_price": exercise,
        "discount_pct": None,
        "terp": None,
        "dilution_pct": None,
        "right_value": None,
        "rights_for_lots": None,
        "redeem_cost_for_lots": None,
        "market_vs_execution": None,
    }

    if current and exercise:
        metrics["discount_pct"] = (
            (current - exercise) / current * 100
        )

        if current > exercise:
            metrics["market_vs_execution"] = "BELOW MARKET"
        elif current < exercise:
            metrics["market_vs_execution"] = "ABOVE MARKET"
        else:
            metrics["market_vs_execution"] = "AT MARKET"

    if current and exercise and old_ratio and new_ratio:
        metrics["terp"] = (
            (old_ratio * current) + (new_ratio * exercise)
        ) / (old_ratio + new_ratio)

        metrics["dilution_pct"] = (
            new_ratio / (old_ratio + new_ratio)
        ) * 100

        metrics["right_value"] = max(
            metrics["terp"] - exercise,
            0,
        )

        old_shares_owned = max(1, DECISION_LOTS) * 100

        entitled = math.floor(
            old_shares_owned * new_ratio / old_ratio
        )

        metrics["rights_for_lots"] = entitled
        metrics["redeem_cost_for_lots"] = (
            entitled * exercise
        )

    return metrics


def calculate_ipo_metrics(article):
    d = article["details"]

    share_count = human_count_to_float(
        d.get("share_count")
    )

    pct = (
        d.get("percentages", [None])[0]
        if d.get("percentages")
        else None
    )

    price_low = None
    price_high = None
    single_price = rupiah_to_float(
        d.get("ipo_single_price")
    )

    price_range = d.get("price_range")

    if price_range:
        nums = re.findall(r"Rp\s*([\d.,]+)", price_range, flags=re.I)

        if len(nums) >= 2:
            price_low = parse_localized_number(nums[0])
            price_high = parse_localized_number(nums[1])

    midpoint = None

    if price_low and price_high:
        midpoint = (price_low + price_high) / 2
    elif single_price:
        midpoint = single_price

    offer_value = None
    implied_market_cap = None
    implied_post_shares = None

    if midpoint and share_count:
        offer_value = midpoint * share_count

    if midpoint and share_count and pct and 0 < pct <= 100:
        implied_post_shares = share_count / (pct / 100)
        implied_market_cap = implied_post_shares * midpoint

    return {
        "price_low": price_low,
        "price_high": price_high,
        "midpoint_price": midpoint,
        "offered_shares": share_count,
        "offered_pct": pct,
        "estimated_offer_value": offer_value,
        "estimated_post_shares": implied_post_shares,
        "implied_market_cap": implied_market_cap,
        "underwriter": d.get("underwriter"),
        "use_of_funds": d.get("use_of_funds") or [],
    }


def calculate_ma_metrics(article):
    d = article["details"]
    market = article.get("market_data") or {}

    current = market.get("last_price")
    tender_price = rupiah_to_float(
        d.get("tender_price")
    )

    premium_pct = None

    if current and tender_price and current != 0:
        premium_pct = (
            (tender_price - current) / current
        ) * 100

    return {
        "current_price": current,
        "tender_price": tender_price,
        "tender_premium_pct": premium_pct,
    }


def monitoring_signal(article):
    event = article["event_type"]
    stage = article["stage"]
    catalyst = article.get("catalyst", "NEUTRAL")
    urgency = article.get("urgency", "LOW")

    reasons = []

    if event == "IPO":
        ipo_class = article.get("ipo_class")
        metrics = article.get("decision_metrics", {})

        if ipo_class == "PIPELINE":
            return "IGNORE", [
                "Masih berupa pipeline umum, belum emiten actionable."
            ]

        if ipo_class == "ACTIONABLE":
            if (
                metrics.get("midpoint_price")
                and metrics.get("offered_shares")
            ):
                reasons.append(
                    "IPO actionable dengan harga dan ukuran penawaran terdeteksi."
                )
                return "HIGH ATTENTION", reasons

            return "WATCH", [
                "IPO sudah actionable, tetapi detail valuasi belum lengkap."
            ]

        return "WATCH", [
            "Calon emiten spesifik sudah teridentifikasi."
        ]

    if event == "RIGHTS ISSUE":
        metrics = article.get("decision_metrics", {})
        discount = metrics.get("discount_pct")
        dilution = metrics.get("dilution_pct")
        current = metrics.get("current_price")
        exercise = metrics.get("execution_price")

        if current and exercise and exercise >= current:
            reasons.append(
                "Harga pelaksanaan tidak lebih murah dari harga pasar terakhir."
            )
            return "WATCH", reasons

        if (
            stage in ("EFEKTIF", "PERDAGANGAN HMETD")
            and discount is not None
            and discount >= 10
        ):
            reasons.append(
                f"Rights aktif dengan discount sekitar {discount:.1f}% terhadap harga pasar."
            )

            if dilution is not None and dilution >= 20:
                reasons.append(
                    f"Potensi dilusi teoritis cukup besar sekitar {dilution:.1f}%."
                )

            return "HIGH ATTENTION", reasons

        if urgency == "HIGH":
            return "HIGH ATTENTION", [
                "Rights Issue sudah memasuki tahap eksekusi."
            ]

        return "WATCH", [
            "Rights Issue perlu dipantau sampai rasio, harga, dan jadwal lengkap."
        ]

    metrics = article.get("decision_metrics", {})
    premium = metrics.get("tender_premium_pct")

    if event == "TENDER OFFER" and premium is not None:
        if premium >= 5:
            return "HIGH ATTENTION", [
                f"Harga tender sekitar {premium:.1f}% di atas harga pasar terakhir."
            ]

        if premium < 0:
            return "WATCH", [
                f"Harga tender sekitar {abs(premium):.1f}% di bawah harga pasar terakhir."
            ]

        return "WATCH", [
            "Harga tender dekat dengan harga pasar terakhir."
        ]

    if stage in (
        "SPA / SIGNED",
        "COMPLETED",
        "CHANGE OF CONTROL",
        "TENDER OFFER",
    ):
        return "HIGH ATTENTION", [
            f"Transaksi berada pada tahap {stage}."
        ]

    if catalyst == "NEGATIVE":
        return "WATCH", [
            "Terdapat faktor risiko/negatif yang perlu diverifikasi."
        ]

    return "WATCH", [
        "Corporate action masih perlu konfirmasi detail lanjutan."
    ]


def signal_badge(signal):
    return {
        "HIGH ATTENTION": "🔥 HIGH ATTENTION",
        "WATCH": "👀 WATCH",
        "IGNORE": "⚪ IGNORE",
    }.get(signal, "👀 WATCH")


async def enrich_decision_support(
    article,
    use_market=True,
    use_deep=True,
):
    if use_deep and DEEP_EXTRACTION_ENABLED:
        await deep_enrich_article(article)

    apply_article_integrity_guards(article)

    d = article["details"]
    ticker = d.get("ticker")

    market_data = None

    if (
        use_market
        and ticker
        and article["event_type"] != "IPO"
        and MARKET_DATA_ENABLED
    ):
        market_data = await get_market_data(ticker)

    article["market_data"] = market_data
    apply_article_integrity_guards(article)

    if article["event_type"] == "RIGHTS ISSUE":
        metrics = calculate_rights_metrics(article)

    elif article["event_type"] == "IPO":
        metrics = calculate_ipo_metrics(article)

    else:
        metrics = calculate_ma_metrics(article)

    article["decision_metrics"] = metrics

    signal, reasons = monitoring_signal(article)
    article["monitoring_signal"] = signal
    article["monitoring_reasons"] = reasons

    return article


# ============================================================
# V6.6.1 EVENT LIFECYCLE ENGINE
# ============================================================

LIFECYCLE_STAGE_ORDER = {
    "IPO": [
        "IPO INFO",
        "RENCANA / PROSPEKTUS",
        "BOOKBUILDING",
        "OFFERING",
        "LISTING",
    ],
    "RIGHTS ISSUE": [
        "RIGHTS ISSUE INFO",
        "RENCANA",
        "DISETUJUI RUPSLB",
        "EFEKTIF",
        "PERDAGANGAN HMETD",
        "COMPLETED",
    ],
    "M&A / TAKEOVER": [
        "M&A INFO",
        "RENCANA",
        "MOU",
        "SPA / SIGNED",
        "CHANGE OF CONTROL",
        "TENDER OFFER",
        "COMPLETED",
    ],
}

LIFECYCLE_NEXT_MILESTONE = {
    "IPO": {
        "IPO INFO": "Prospektus / rencana resmi",
        "RENCANA / PROSPEKTUS": "Bookbuilding",
        "BOOKBUILDING": "Penawaran umum",
        "OFFERING": "Listing di BEI",
        "LISTING": "Monitoring pasca-listing",
    },
    "RIGHTS ISSUE": {
        "RIGHTS ISSUE INFO": "Rencana / RUPSLB",
        "RENCANA": "Persetujuan RUPSLB",
        "DISETUJUI RUPSLB": "Pernyataan efektif OJK",
        "EFEKTIF": "Cum-right / ex-right",
        "PERDAGANGAN HMETD": "Penyelesaian HMETD",
        "COMPLETED": "Selesai",
    },
    "M&A / TAKEOVER": {
        "M&A INFO": "Konfirmasi rencana transaksi",
        "RENCANA": "MOU / perjanjian transaksi",
        "MOU": "SPA / perjanjian definitif",
        "SPA / SIGNED": "Perubahan pengendali / closing",
        "CHANGE OF CONTROL": "Tender wajib jika berlaku",
        "TENDER OFFER": "Penyelesaian tender / pembayaran",
        "COMPLETED": "Selesai",
    },
}

LIFECYCLE_SCHEDULE_LABELS = {
    "cum_right": "Cum-right",
    "ex_right": "Ex-right",
    "recording_date": "Recording date",
    "rights_trading": "Mulai perdagangan HMETD",
    "rights_trading_end": "Akhir perdagangan HMETD",
    "rights_payment": "Pembayaran HMETD",
    "bookbuilding": "Bookbuilding",
    "offering": "Penawaran umum",
    "allotment": "Penjatahan",
    "distribution": "Distribusi saham",
    "listing": "Listing",
    "tender_start": "Mulai tender",
    "tender_end": "Akhir tender",
    "tender_payment": "Pembayaran tender",
    "transaction_completion": "Penyelesaian transaksi",
}


def lifecycle_family(event_type):
    event = str(event_type or "").upper()
    if event == "IPO":
        return "IPO"
    if event == "RIGHTS ISSUE":
        return "RIGHTS ISSUE"
    return "M&A / TAKEOVER"


def lifecycle_stage_info(event_type, stage):
    family = lifecycle_family(event_type)
    order = LIFECYCLE_STAGE_ORDER.get(family, [])
    stage = str(stage or "").upper()

    try:
        index = order.index(stage)
    except ValueError:
        index = 0

    total = len(order) or 1
    return {
        "family": family,
        "stage": stage or (order[0] if order else "INFO"),
        "step": index + 1,
        "total_steps": total,
        "next_milestone": (
            LIFECYCLE_NEXT_MILESTONE
            .get(family, {})
            .get(stage, "Pantau keterbukaan berikutnya")
        ),
    }



def _snapshot_unique_values(values, *, numeric=False):
    """Stable de-dup for lifecycle material lists.

    Corporate-action extraction can find the same value in title, snippet,
    and deep article. V6.6.1 treats repeated 51 / 51.0 / "51.0" as one stake.
    """
    output = []
    seen = set()

    for raw in values or []:
        if raw in (None, ""):
            continue

        if numeric:
            try:
                value = round(float(str(raw).replace("%", "").strip()), 8)
                key = ("num", value)
                clean = value
            except Exception:
                text = re.sub(r"\\s+", " ", str(raw)).strip()
                key = ("text", text.casefold())
                clean = text
        else:
            if isinstance(raw, (int, float)):
                value = round(float(raw), 8)
                key = ("num", value)
                clean = value
            else:
                text = re.sub(r"\\s+", " ", str(raw)).strip()
                key = ("text", text.casefold())
                clean = text

        if key in seen:
            continue

        seen.add(key)
        output.append(clean)

    return output


def lifecycle_snapshot(article):
    d = article.get("details") or {}
    event = article.get("event_type") or "CORPORATE ACTION"
    info = lifecycle_stage_info(event, article.get("stage") or "INFO")

    ticker = _valid_idx_ticker(d.get("ticker"))
    aliases = _dedup_issuer_aliases(
        list(article.get("issuer_aliases") or [])
        + list(get_ticker_aliases(ticker) if ticker else [])
    )
    issuer = (
        article.get("issuer_name")
        or (aliases[0] if aliases else None)
        or d.get("target")
        or d.get("acquirer")
    )

    official = article.get("official_reference")
    official_cached = False
    if not official and isinstance(article.get("verified_official_ref"), dict):
        cached = article.get("verified_official_ref") or {}
        official = {
            "authority": cached.get("authority"),
            "kind": cached.get("kind"),
            "url": cached.get("url"),
        }
        official_cached = True

    return {
        "ticker": ticker,
        "issuer": str(issuer or ""),
        "event_type": str(event),
        "family": info["family"],
        "stage": info["stage"],
        "stage_step": info["step"],
        "stage_total": info["total_steps"],
        "next_milestone": info["next_milestone"],
        "schedule": {
            str(k): str(v)
            for k, v in (d.get("schedule") or {}).items()
            if v
        },
        "official_authority": str((official or {}).get("authority") or ""),
        "official_kind": str((official or {}).get("kind") or ""),
        "official_url": str((official or {}).get("url") or ""),
        "official_cached": bool(official_cached),
        "signal": str(article.get("monitoring_signal") or ""),
        "catalyst": str(article.get("catalyst") or ""),
        "score": int(
            article.get("information_score", article.get("ca_score", 0)) or 0
        ),
        "stake": _snapshot_unique_values(
            d.get("percentages") or [],
            numeric=True,
        )[:4],
        "money": _snapshot_unique_values(
            d.get("money") or [],
        )[:4],
        "ratio": d.get("ratio"),
        "execution_price": d.get("execution_price"),
        "tender_price": d.get("tender_price"),
        "price_range": d.get("price_range"),
        "share_count": d.get("share_count"),
        "title": str(article.get("title") or "")[:500],
        "source": str(article.get("source") or "")[:120],
        "source_url": str(article.get("source_url") or article.get("link") or "")[:2000],
        "published": str(article.get("published") or "")[:200],
    }


def lifecycle_lines(article):
    if not EVENT_LIFECYCLE_ENABLED:
        return []

    snap = lifecycle_snapshot(article)
    lines = [
        (
            f"🧭 <b>Lifecycle:</b> {html.escape(snap['stage'])} "
            f"({snap['stage_step']}/{snap['stage_total']})"
        ),
        (
            f"⏭ <b>Next milestone:</b> "
            f"{html.escape(snap['next_milestone'])}"
        ),
    ]

    schedule = snap.get("schedule") or {}
    for key, value in list(schedule.items())[:2]:
        label = LIFECYCLE_SCHEDULE_LABELS.get(key, key)
        lines.append(
            f"📅 <b>{html.escape(label)}:</b> {html.escape(str(value))}"
        )

    return lines


# ============================================================
# STAGE / STATUS
# ============================================================

def classify_ipo_stage(text):
    low = text.lower()

    if any(x in low for x in ["listing hari ini", "resmi melantai", "resmi tercatat"]):
        return "LISTING"
    if any(x in low for x in ["masa penawaran umum", "public offering"]):
        return "OFFERING"
    if any(x in low for x in ["bookbuilding", "book building", "penawaran awal"]):
        return "BOOKBUILDING"
    if any(x in low for x in ["prospektus", "calon emiten", "akan ipo", "rencana ipo"]):
        return "RENCANA / PROSPEKTUS"
    return "IPO INFO"


def classify_rights_stage(text):
    low = text.lower()

    if any(
        x in low
        for x in [
            "rights issue rampung",
            "rights issue selesai",
            "hmetd berakhir",
            "perdagangan hmetd berakhir",
            "pelaksanaan hmetd selesai",
        ]
    ):
        return "COMPLETED"
    if any(x in low for x in ["cum right", "cum-right", "ex right", "ex-right"]):
        return "PERDAGANGAN HMETD"
    if any(x in low for x in ["efektif ojk", "pernyataan efektif"]):
        return "EFEKTIF"
    if any(x in low for x in ["disetujui rupslb", "persetujuan rupslb"]):
        return "DISETUJUI RUPSLB"
    if any(x in low for x in ["akan rights issue", "rencana rights issue", "berencana rights issue"]):
        return "RENCANA"
    return "RIGHTS ISSUE INFO"


def classify_ma_stage(text, event):
    low = text.lower()

    if any(
        x in low
        for x in [
            "tuntas akuisisi",
            "selesaikan akuisisi",
            "completed acquisition",
            "akuisisi selesai",
            "transaksi selesai",
            "tender wajib selesai",
            "penawaran tender selesai",
            "periode tender berakhir",
        ]
    ):
        return "COMPLETED"
    if any(x in low for x in ["spa", "share purchase agreement", "perjanjian jual beli"]):
        return "SPA / SIGNED"
    if any(x in low for x in ["mou", "memorandum of understanding"]):
        return "MOU"
    if event == "TENDER OFFER":
        return "TENDER OFFER"
    if any(x in low for x in ["pengendali baru", "perubahan pengendali"]):
        return "CHANGE OF CONTROL"
    if any(x in low for x in ["rencana akuisisi", "berencana mengakuisisi"]):
        return "RENCANA"
    return "M&A INFO"


# ============================================================
# V4.3 IPO INTELLIGENCE CLASS
# ============================================================

IPO_PIPELINE_PHRASES = [
    "bei kantongi",
    "antrean ipo",
    "antrian ipo",
    "pipeline ipo",
    "target ipo",
    "jumlah calon emiten",
    "calon emiten baru",
    "perusahaan antre ipo",
    "perusahaan antri ipo",
    "siap ipo tahun ini",
    "daftar calon emiten",
]


# ============================================================
# V4.4 CONTEXT AWARENESS
# ============================================================

IPO_AGGREGATE_PATTERNS = [
    r"\bbei\b.{0,45}\b\d+\s+calon emiten\b",
    r"\b\d+\s+calon emiten\b.{0,45}\bipo\b",
    r"\b\d+\s+perusahaan\b.{0,45}\bipo\b",
    r"\bantrean\b.{0,25}\bipo\b",
    r"\bantrian\b.{0,25}\bipo\b",
    r"\bpipeline\b.{0,25}\bipo\b",
]

RIGHTS_POST_EVENT_PHRASES = [
    "usai rights issue",
    "pasca rights issue",
    "setelah rights issue",
    "seusai rights issue",
    "rights issue selesai",
    "rights issue rampung",
    "rights issue tuntas",
    "usai hmetd",
    "pasca hmetd",
    "setelah hmetd",
    "seusai hmetd",
]

POST_EVENT_MARKET_COMMENTARY = [
    "saham naik",
    "saham turun",
    "saham melonjak",
    "saham anjlok",
    "saham jeblok",
    "harga saham",
    "kinerja saham",
    "pergerakan saham",
    "laba",
    "rugi",
    "kinerja keuangan",
]

WEAK_PARTICIPATION_PHRASES = [
    "sepi peminat",
    "minim peminat",
    "minim partisipasi",
    "partisipasi minim",
    "partisipasi rendah",
    "kurang diminati",
    "tidak diminati",
    "kurang terserap",
    "tidak terserap",
    "serapan rendah",
    "hanya sedikit investor",
    "hanya sedikit pemegang saham",
]

STRONG_PARTICIPATION_PHRASES = [
    "oversubscribed",
    "oversubscribe",
    "kelebihan permintaan",
    "tersedia penuh",
    "terserap penuh",
    "partisipasi tinggi",
    "diminati investor",
]


def is_aggregate_ipo_news(text):
    low = text.lower()

    if any(phrase in low for phrase in IPO_PIPELINE_PHRASES):
        return True

    return any(
        re.search(pattern, low, flags=re.I)
        for pattern in IPO_AGGREGATE_PATTERNS
    )


def is_post_event_commentary(text, event):
    """
    Filter berita yang hanya membahas kondisi SETELAH corporate action.
    M&A COMPLETED tetap dipertahankan karena completion adalah event penting.
    """
    low = text.lower()

    if event == "RIGHTS ISSUE":
        post_hit = any(p in low for p in RIGHTS_POST_EVENT_PHRASES)
        if not post_hit:
            return False

        # Jika artikel masih membahas tahap aktif HMETD secara eksplisit,
        # jangan langsung dibuang.
        active_terms = [
            "cum-right", "cum right", "ex-right", "ex right",
            "periode perdagangan hmetd", "harga pelaksanaan",
            "standby buyer", "pembeli siaga",
        ]
        if any(term in low for term in active_terms):
            return False

        return True

    # IPO post-event sudah ditangani filter V4.2.
    return False


def participation_context(text):
    low = text.lower()

    if any(p in low for p in WEAK_PARTICIPATION_PHRASES):
        return "WEAK"

    if any(p in low for p in STRONG_PARTICIPATION_PHRASES):
        return "STRONG"

    return "NORMAL"


def article_context(event, text, ipo_class=None):
    if event == "IPO" and ipo_class == "PIPELINE":
        return "MARKET PIPELINE"

    participation = participation_context(text)
    if participation == "WEAK":
        return "WEAK PARTICIPATION"
    if participation == "STRONG":
        return "STRONG PARTICIPATION"

    return "ACTIVE EVENT"


def context_badge(value):
    return {
        "ACTIVE EVENT": "🟢 ACTIVE EVENT",
        "MARKET PIPELINE": "📰 MARKET PIPELINE",
        "WEAK PARTICIPATION": "🟠 WEAK PARTICIPATION",
        "STRONG PARTICIPATION": "🔥 STRONG PARTICIPATION",
    }.get(value, "🟢 ACTIVE EVENT")

def classify_ipo_intelligence(text, stage, details):
    """
    PIPELINE    = informasi umum pasar/BEI mengenai antrean IPO.
    CANDIDATE   = perusahaan/calon emiten spesifik, tetapi belum masuk tahap transaksi aktif.
    ACTIONABLE  = sudah bookbuilding, offering, listing, atau detail transaksi cukup konkret.
    """
    low = text.lower()

    if is_aggregate_ipo_news(text):
        # Jika berita agregat benar-benar memuat transaksi spesifik yang
        # sudah bookbuilding/offering/listing, tetap boleh actionable.
        if stage in ("BOOKBUILDING", "OFFERING", "LISTING"):
            specific_detail_count = sum([
                1 if details.get("price_range") else 0,
                1 if details.get("share_count") else 0,
                1 if details.get("ticker") else 0,
            ])
            if specific_detail_count >= 2:
                return "ACTIONABLE"

        return "PIPELINE"

    if stage in ("BOOKBUILDING", "OFFERING", "LISTING"):
        return "ACTIONABLE"

    concrete_detail_count = sum([
        1 if details.get("price_range") else 0,
        1 if details.get("share_count") else 0,
        1 if details.get("money") else 0,
        1 if details.get("ticker") else 0,
    ])

    if concrete_detail_count >= 2 and stage != "IPO INFO":
        return "ACTIONABLE"

    if any(x in low for x in [
        "calon emiten", "prospektus", "akan ipo",
        "rencana ipo", "berencana ipo", "siap ipo"
    ]):
        return "CANDIDATE"

    return "CANDIDATE"

def ipo_class_badge(value):
    return {
        "PIPELINE": "📰 PIPELINE",
        "CANDIDATE": "🟡 CANDIDATE",
        "ACTIONABLE": "🔥 ACTIONABLE",
    }.get(value, "🟡 CANDIDATE")


# ============================================================
# V6.6.2 — ENTITY ROLE GUARD
# ============================================================

ROLE_GENERIC_TERMS = {
    "saham",
    "emiten",
    "perusahaan",
    "perseroan",
    "pengendali",
    "investor",
    "pembeli",
    "target",
    "akuisisi",
    "takeover",
}

ROLE_BAD_FRAGMENT_PATTERNS = [
    r"\bserius\s+ingin\b",
    r"\bingin\s+(?:mengakuisisi|akuisisi|ambil\s+alih)\b",
    r"\bmau\s+(?:mengakuisisi|akuisisi|ambil\s+alih)\b",
    r"\bakan\s+(?:mengakuisisi|akuisisi|ambil\s+alih)\b",
    r"\bbakal\s+(?:mengakuisisi|akuisisi|ambil\s+alih)\b",
    r"\bsiap\s+(?:mengakuisisi|akuisisi|ambil\s+alih)\b",
    r"\bagendakan\b",
    r"\brupslb\b",
    r"\brups\b",
    r"\bbulan\s+depan\b",
    r"\bharga\s+saham\b",
    r"\bmeroket\b",
    r"\bmelejit\b",
]

ROLE_LOW_CONFIDENCE_CUES = [
    "sinyal ",
    "rumor ",
    "isu ",
    "dikabarkan ",
    "disebut ",
    "kabarnya ",
    "serius ingin ",
    "ingin akuisisi",
    "ingin mengakuisisi",
    "mau akuisisi",
    "akan akuisisi",
    "bakal akuisisi",
    "siap akuisisi",
]


def clean_entity(value):
    """Clean one entity role candidate without swallowing the next headline."""
    value = normalize(value)
    if not value:
        return None

    # Headlines often append another clause after a colon/pipe.
    value = re.split(r"\s*(?::|\||•)\s*", value, maxsplit=1)[0]
    value = re.split(r"\s+-\s+", value, maxsplit=1)[0]
    value = re.split(r"[,;]", value, maxsplit=1)[0]
    value = value.strip(" -:|[](){}\"'“”‘’")

    return value[:90] or None


def _role_entity_is_plausible(value):
    """Reject obvious headline fragments while keeping companies/person names."""
    value = clean_entity(value)
    if not value:
        return False

    low = value.lower().strip()
    words = value.split()

    if len(value) < 2 or len(words) > 12:
        return False

    if low in ROLE_GENERIC_TERMS:
        return False

    if re.search(r"https?://|www\.|@", low):
        return False

    if re.search(r"[!?]", value):
        return False

    if any(
        re.search(pattern, low, flags=re.I)
        for pattern in ROLE_BAD_FRAGMENT_PATTERNS
    ):
        return False

    if re.search(
        r"\b(?:ingin|mau|akan|bakal|siap|agendakan|mengincar)\s*$",
        low,
        flags=re.I,
    ):
        return False

    # A 4-letter ticker is allowed as target identity.
    if re.fullmatch(r"[A-Z]{4}", value.upper()):
        return True

    # Require at least one alphabetic token.
    if not re.search(r"[A-Za-z]", value):
        return False

    return True


def _clean_role_candidate(value):
    value = clean_entity(value)
    if not _role_entity_is_plausible(value):
        return None
    return value


def _role_pattern_result(title):
    """Return (acquirer, target, confidence, source_pattern).

    LOW confidence means the headline only expresses intent/rumour, not
    a completed/confirmed acquisition. The actor candidate is preserved
    internally but can be suppressed from user-visible output.
    """
    clean_title = re.sub(
        r"\s+-\s+[^-]+$",
        "",
        normalize(title),
    )

    patterns = [
        # Example:
        # "Sinyal Haji Isam Serius Ingin Akuisisi BYAN: JARR ..."
        (
            "LOW",
            "SPECULATIVE_SIGNAL",
            r"^(?:sinyal|rumor|isu|kabarnya)\s+(.+?)\s+"
            r"(?:serius\s+)?(?:ingin|mau|akan|bakal|siap)\s+"
            r"(?:mengakuisisi|akuisisi|mengambil\s+alih|ambil\s+alih)\s+(.+)$",
        ),
        # "X ingin/akan/bakal akuisisi Y"
        (
            "LOW",
            "INTENT",
            r"^(.+?)\s+(?:serius\s+)?(?:ingin|mau|akan|bakal|siap)\s+"
            r"(?:mengakuisisi|akuisisi|mengambil\s+alih|ambil\s+alih)\s+(.+)$",
        ),
        # Stronger direct action wording.
        (
            "HIGH",
            "DIRECT",
            r"^(.+?)\s+(?:resmi\s+)?mengakuisisi\s+(.+)$",
        ),
        (
            "HIGH",
            "DIRECT",
            r"^(.+?)\s+(?:resmi\s+)?akuisisi\s+(.+)$",
        ),
        (
            "HIGH",
            "DIRECT",
            r"^(.+?)\s+(?:resmi\s+)?ambil\s+alih\s+(.+)$",
        ),
        (
            "HIGH",
            "DIRECT",
            r"^(.+?)\s+acquires\s+(.+)$",
        ),
        (
            "HIGH",
            "DIRECT",
            r"^(.+?)\s+acquire\s+(.+)$",
        ),
    ]

    for confidence, source_pattern, pattern in patterns:
        match = re.search(
            pattern,
            clean_title,
            flags=re.I,
        )
        if not match:
            continue

        acquirer = _clean_role_candidate(match.group(1))
        target = _clean_role_candidate(match.group(2))

        if acquirer or target:
            return (
                acquirer,
                target,
                confidence,
                source_pattern,
            )

    return None, None, "NONE", "NONE"


def extract_acquirer_target(title):
    """Backward-compatible public wrapper."""
    acquirer, target, _, _ = _role_pattern_result(title)
    return acquirer, target


def extract_acquirer_target_with_meta(title):
    acquirer, target, confidence, source_pattern = _role_pattern_result(title)

    meta = {
        "confidence": confidence,
        "source_pattern": source_pattern,
        "acquirer_candidate": acquirer,
        "target_candidate": target,
        "acquirer_suppressed": False,
        "target_suppressed": False,
        "guard_applied": False,
    }

    if (
        LOW_CONFIDENCE_ROLE_SUPPRESSION_ENABLED
        and confidence == "LOW"
        and acquirer
    ):
        # A rumour/intention headline is not sufficient to label the party
        # as a confirmed Acquirer. Keep the candidate only in metadata.
        meta["acquirer_suppressed"] = True
        acquirer = None

    return acquirer, target, meta


def _ticker_target_role_in_title(title, ticker):
    ticker = _valid_idx_ticker(ticker)
    if not ticker:
        return False

    normalized = normalize(title).upper()
    esc = re.escape(ticker)

    patterns = [
        rf"(?:MENGAKUISISI|AKUISISI|TAKEOVER|MENGAMBIL\s+ALIH|AMBIL\s+ALIH).{{0,35}}\b{esc}\b",
        rf"(?:TARGET|SASARAN).{{0,20}}\b{esc}\b",
    ]

    return any(
        re.search(pattern, normalized, flags=re.I)
        for pattern in patterns
    )


def apply_entity_role_guard(article):
    if not ENTITY_ROLE_GUARD_ENABLED:
        return article

    d = article.setdefault("details", {})
    meta = d.get("role_meta")
    if not isinstance(meta, dict):
        meta = {
            "confidence": "UNKNOWN",
            "source_pattern": "LEGACY",
            "acquirer_candidate": d.get("acquirer"),
            "target_candidate": d.get("target"),
            "acquirer_suppressed": False,
            "target_suppressed": False,
            "guard_applied": False,
        }

    raw_acquirer = d.get("acquirer")
    raw_target = d.get("target")

    clean_acquirer = _clean_role_candidate(raw_acquirer)
    clean_target = _clean_role_candidate(raw_target)

    if raw_acquirer and not clean_acquirer:
        meta["acquirer_candidate"] = clean_entity(raw_acquirer)
        meta["acquirer_suppressed"] = True

    if raw_target and not clean_target:
        meta["target_candidate"] = clean_entity(raw_target)
        meta["target_suppressed"] = True

    confidence = str(meta.get("confidence") or "UNKNOWN").upper()

    if (
        LOW_CONFIDENCE_ROLE_SUPPRESSION_ENABLED
        and confidence == "LOW"
        and clean_acquirer
    ):
        meta["acquirer_candidate"] = clean_acquirer
        meta["acquirer_suppressed"] = True
        clean_acquirer = None

    ticker = _valid_idx_ticker(d.get("ticker"))

    # If the title clearly says "akuisisi TICKER", ticker can safely be used
    # as the target identity even if the old target parser swallowed a
    # following headline clause.
    if (
        not clean_target
        and ticker
        and _ticker_target_role_in_title(
            article.get("title", ""),
            ticker,
        )
    ):
        clean_target = ticker
        meta["target_candidate"] = ticker
        meta["target_suppressed"] = False
        meta["target_recovered_from_ticker"] = True

    d["acquirer"] = clean_acquirer
    d["target"] = clean_target
    meta["guard_applied"] = True
    d["role_meta"] = meta

    article["entity_role_guard_applied"] = True
    return article


def _has_indonesia_evidence(article):
    d = article.get("details") or {}
    ticker = _valid_idx_ticker(d.get("ticker"))
    if not ticker:
        return False, []

    reasons = []

    source = str(article.get("source") or "").lower()
    if any(hint in source for hint in INDONESIA_SOURCE_HINTS):
        reasons.append("INDONESIA_SOURCE")

    text = " ".join([
        str(article.get("title") or ""),
        str(article.get("snippet") or ""),
        str(article.get("description") or ""),
    ]).lower()

    local_terms = [
        "rupslb",
        "rups",
        " tbk",
        "bei",
        "bursa efek indonesia",
        "idx",
        "ojk",
        "ksei",
        "hmetd",
        "tender wajib",
        "rupiah",
        "rp ",
    ]

    if any(term in text for term in local_terms):
        reasons.append("LOCAL_MARKET_TERM")

    if article.get("issuer_name"):
        reasons.append("RESOLVED_ISSUER")

    if article.get("issuer_aliases"):
        reasons.append("ISSUER_ALIAS")

    market = article.get("market_data") or {}
    symbol = str(market.get("symbol") or "").upper()
    if symbol == f"{ticker}.JK":
        reasons.append("JK_MARKET_SYMBOL")

    # Ticker recovery/issuer memory is IDX-oriented in this project.
    recovery = str(article.get("ticker_recovery_source") or "").upper()
    if recovery and recovery not in {"", "NONE"}:
        reasons.append("IDX_TICKER_RECOVERY")

    return bool(reasons), reasons


def apply_indonesia_classification_guard(article):
    if not INDONESIA_CLASSIFICATION_GUARD_ENABLED:
        return article

    d = article.get("details") or {}
    ticker = _valid_idx_ticker(d.get("ticker"))
    if not ticker:
        return article

    has_evidence, reasons = _has_indonesia_evidence(article)
    if not has_evidence:
        return article

    current = str(article.get("geo") or "")

    if not current.startswith("INDONESIA"):
        article["geo_before_guard"] = current or None
        article["geo"] = "INDONESIA 🇮🇩"
        article["geo_guard_applied"] = True
        article["geo_guard_reasons"] = reasons

    return article


def apply_article_integrity_guards(article):
    apply_entity_role_guard(article)
    apply_indonesia_classification_guard(article)
    return article


def v662_integrity_selftest():
    """Offline deterministic self-test used by GitHub Actions mode:test."""
    # Reproduce the BYAN headline that exposed the V6.6.1 role-fragment bug.
    title = (
        "Sinyal Haji Isam Serius Ingin Akuisisi BYAN: "
        "JARR Agendakan RUPSLB Bulan Depan"
    )

    acquirer, target, meta = extract_acquirer_target_with_meta(title)

    byan = {
        "title": title,
        "source": "Media Indonesia",
        "snippet": "",
        "geo": "GLOBAL 🌐",
        "issuer_name": "Bayan Resources",
        "issuer_aliases": ["Bayan Resources"],
        "details": {
            "ticker": "BYAN",
            "acquirer": acquirer,
            "target": target,
            "role_meta": meta,
        },
    }

    apply_article_integrity_guards(byan)

    d = byan["details"]

    byan_ok = (
        d.get("acquirer") is None
        and d.get("target") == "BYAN"
        and byan.get("geo") == "INDONESIA 🇮🇩"
        and bool(
            (d.get("role_meta") or {}).get("acquirer_suppressed")
        )
    )

    strong_title = (
        "PT Alpha Tbk Resmi Mengakuisisi PT Beta Tbk"
    )
    strong_acq, strong_target, strong_meta = (
        extract_acquirer_target_with_meta(strong_title)
    )

    strong_ok = (
        strong_acq == "PT Alpha Tbk"
        and strong_target == "PT Beta Tbk"
        and strong_meta.get("confidence") == "HIGH"
        and not strong_meta.get("acquirer_suppressed")
    )

    return {
        "passed": bool(byan_ok and strong_ok),
        "byan_role_guard": bool(byan_ok),
        "strong_direct_role": bool(strong_ok),
        "indonesia_guard": byan.get("geo") == "INDONESIA 🇮🇩",
        "byan_acquirer": d.get("acquirer"),
        "byan_target": d.get("target"),
        "byan_geo": byan.get("geo"),
    }



# ============================================================
# V6.2.1 TICKER RECOVERY / ISSUER NAME RESOLVER
# ============================================================

ISSUER_NAME_STOPWORDS = {
    "SAHAM", "EMITEN", "PERUSAHAAN", "PERSEROAN", "PENGENDALI",
    "PENGAMBILALIHAN", "AKUISISI", "TENDER", "OFFER", "RIGHTS",
    "ISSUE", "HMETD", "PENAWARAN", "UMUM", "RESMI", "BARU", "WAJIB",
}


def _valid_idx_ticker(value):
    raw = str(value or "").strip().upper()
    if raw.endswith(".JK"):
        raw = raw[:-3]
    if not re.fullmatch(r"[A-Z]{4}", raw):
        return None
    if raw in TICKER_STOPWORDS:
        return None
    return raw


def _ticker_exact_pattern(ticker):
    ticker = re.escape(str(ticker or "").upper())
    return re.compile(rf"(?<![A-Z0-9]){ticker}(?![A-Z0-9])", re.I)


def article_mentions_ticker(article, ticker):
    ticker = _valid_idx_ticker(ticker)
    if not ticker:
        return False
    if _valid_idx_ticker((article.get("details") or {}).get("ticker")) == ticker:
        return True
    combined = " ".join([
        str(article.get("title") or ""),
        str(article.get("snippet") or ""),
        str(article.get("description") or ""),
    ])
    return bool(_ticker_exact_pattern(ticker).search(combined))


def _clean_issuer_alias(value):
    text = normalize(str(value or ""))
    # If a regex captured headline text before "PT", keep only the company suffix.
    pt_match = re.search(r"(?:^|\s)PT\.?\s+(.+)$", text, re.I)
    if pt_match:
        text = pt_match.group(1)
    text = re.sub(r"^(?:saham|emiten|perusahaan|perseroan)\s+", "", text, flags=re.I)
    text = re.sub(r"^(?:PT|PT\.)\s+", "", text, flags=re.I)
    text = re.sub(r"\s+(?:Tbk|Tbk\.)$", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" -–—,.;:()[]")
    if len(text) < ISSUER_ALIAS_MIN_CHARS:
        return None
    if re.fullmatch(r"[\d\s.,%+\-]+", text):
        return None
    tokens = re.findall(r"[A-Za-z0-9]+", text.upper())
    meaningful = [t for t in tokens if t not in ISSUER_NAME_STOPWORDS]
    if not meaningful:
        return None
    # Reject aliases that are mostly headline/corporate-action language.
    if len(tokens) > 9 and len(meaningful) < 2:
        return None
    return text


def _issuer_alias_key(value):
    cleaned = _clean_issuer_alias(value)
    if not cleaned:
        return ""
    text = cleaned.upper()
    text = re.sub(r"\b(?:PT|TBK)\b", " ", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_issuer_aliases_from_text(ticker, text):
    """Extract issuer legal name using the ticker as a hard anchor.

    The patterns intentionally require PT/Tbk or explicit issuer-code labels
    to avoid learning random company names from an article body.
    """
    ticker = _valid_idx_ticker(ticker)
    if not ticker:
        return []

    text = normalize(str(text or ""))
    esc = re.escape(ticker)
    aliases = []

    patterns = [
        # PT Era Media Sejahtera Tbk (DOOH) / ("DOOH") / [IDX: DOOH]
        rf"PT\.?\s+([A-Z][A-Za-z0-9&.,'’\- ]{{2,100}}?)\s+Tbk\.?\s*"
        rf"(?:\(|\[)?(?:IDX\s*:\s*)?[^A-Za-z0-9]{{0,3}}{esc}[^A-Za-z0-9]{{0,3}}(?:\)|\])?",
        # DOOH - PT Era Media Sejahtera Tbk / DOOH adalah PT ...
        rf"\b{esc}\b\s*(?:-|–|—|:|adalah|merupakan|yakni|yaitu)\s*"
        rf"PT\.?\s+([A-Z][A-Za-z0-9&.,'’\- ]{{2,100}}?)\s+Tbk\.?",
        # Nama Emiten: PT ... Tbk ... Kode Emiten: DOOH
        rf"Nama\s+(?:Emiten|Perusahaan)\s*[:\-]?\s*PT\.?\s+"
        rf"([A-Z][A-Za-z0-9&.,'’\- ]{{2,100}}?)\s+Tbk\.?"
        rf".{{0,160}}?(?:Kode\s+(?:Emiten|Saham)|Ticker)\s*[:\-]?\s*{esc}",
        # PT ... Tbk ... kode emiten DOOH
        rf"PT\.?\s+([A-Z][A-Za-z0-9&.,'’\- ]{{2,100}}?)\s+Tbk\.?"
        rf".{{0,120}}?(?:kode\s+(?:emiten|saham)|ticker)\s*[:\-]?\s*{esc}",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            alias = _clean_issuer_alias(match.group(1))
            if alias:
                aliases.append(alias)

    dedup = {}
    for alias in aliases:
        key = _issuer_alias_key(alias)
        if key:
            dedup[key] = alias
    return list(dedup.values())


def resolve_deep_issuer_alias(article, deep_text):
    if not DEEP_ISSUER_RESOLVER_ENABLED:
        return []

    ticker = _valid_idx_ticker((article.get("details") or {}).get("ticker"))
    if not ticker:
        return []

    aliases = extract_issuer_aliases_from_text(ticker, deep_text)
    if not aliases:
        return []

    existing = list(article.get("issuer_aliases") or [])
    merged = {}
    for alias in existing + aliases:
        key = _issuer_alias_key(alias)
        if key:
            merged[key] = alias

    values = list(merged.values())
    article["issuer_aliases"] = values
    article["issuer_name"] = values[0]
    article["issuer_resolution_source"] = "DEEP_ARTICLE"
    register_ticker_aliases(ticker, values)
    return values


def issuer_resolution_lines(article):
    aliases = article.get("issuer_aliases") or []
    if not aliases:
        return []
    source = html.escape(str(article.get("issuer_resolution_source") or "ARTICLE"))
    return [
        "🏢 <b>Issuer Resolver:</b> ✅ " + html.escape(str(aliases[0])),
        f"🧭 <b>Issuer Source:</b> {source}",
    ]


def extract_issuer_aliases_near_ticker(article, ticker):
    ticker = _valid_idx_ticker(ticker)
    if not ticker:
        return []

    combined = normalize(" ".join([
        str(article.get("title") or ""),
        str(article.get("snippet") or ""),
        str(article.get("description") or ""),
    ]))

    aliases = extract_issuer_aliases_from_text(ticker, combined)

    # target is accepted only if this same article explicitly carries ticker.
    if article_mentions_ticker(article, ticker):
        target = _clean_issuer_alias((article.get("details") or {}).get("target"))
        if target:
            aliases.append(target)

    dedup = {}
    for alias in aliases:
        key = _issuer_alias_key(alias)
        if key:
            dedup[key] = alias
    return list(dedup.values())

def register_ticker_aliases(ticker, aliases):
    ticker = _valid_idx_ticker(ticker)
    if not ticker:
        return []
    bucket = TICKER_ALIAS_CACHE.setdefault(ticker, {})
    now = datetime.now(timezone.utc)
    for alias in aliases or []:
        clean = _clean_issuer_alias(alias)
        key = _issuer_alias_key(clean)
        if clean and key:
            bucket[key] = {"alias": clean, "updated_at": now}
    return [x["alias"] for x in bucket.values()]


def get_ticker_aliases(ticker):
    ticker = _valid_idx_ticker(ticker)
    if not ticker:
        return []
    return [
        item.get("alias") for item in TICKER_ALIAS_CACHE.get(ticker, {}).values()
        if item.get("alias")
    ]


def _article_mentions_alias(article, alias):
    alias_key = _issuer_alias_key(alias)
    if not alias_key:
        return False
    combined = _issuer_alias_key(" ".join([
        str(article.get("title") or ""),
        str(article.get("snippet") or ""),
    ]))
    if alias_key in combined:
        return True
    alias_tokens = alias_key.split()
    if len(alias_tokens) >= 3:
        pool = set(combined.split())
        hits = sum(1 for token in alias_tokens if token in pool)
        return hits >= max(3, len(alias_tokens) - 1)
    return False


def recover_ticker_on_article(article, ticker, source="RECOVERY"):
    ticker = _valid_idx_ticker(ticker)
    if not ticker:
        return False
    details = article.setdefault("details", {})
    existing = _valid_idx_ticker(details.get("ticker"))
    if existing and existing != ticker:
        return False
    details["ticker"] = ticker
    article["ticker_recovered"] = True
    article["ticker_recovery_source"] = source
    aliases = extract_issuer_aliases_near_ticker(article, ticker)
    if aliases:
        article["issuer_aliases"] = aliases
        register_ticker_aliases(ticker, aliases)
    try:
        article["ca_score"] = corporate_action_score(article)
        article["information_score"] = article["ca_score"]
    except Exception:
        pass
    return True


def find_ticker_matches(articles, ticker):
    ticker = _valid_idx_ticker(ticker)
    if not ticker:
        return []
    matches, seen = [], set()
    for article in articles:
        details_ticker = _valid_idx_ticker((article.get("details") or {}).get("ticker"))
        if details_ticker == ticker:
            pass
        elif article_mentions_ticker(article, ticker):
            recover_ticker_on_article(article, ticker, source="TITLE_SNIPPET")
        else:
            continue
        aliases = extract_issuer_aliases_near_ticker(article, ticker)
        if aliases:
            article["issuer_aliases"] = aliases
            register_ticker_aliases(ticker, aliases)
        key = article.get("key") or article_key(
            article.get("title", ""), article.get("link", "")
        )
        if key in seen:
            continue
        seen.add(key)
        matches.append(article)
    return matches


def propagate_tickers_by_issuer_alias(articles):
    if not ISSUER_ALIAS_PROPAGATION_ENABLED:
        return articles
    alias_to_tickers = {}
    for article in articles:
        ticker = _valid_idx_ticker((article.get("details") or {}).get("ticker"))
        if not ticker:
            continue
        aliases = extract_issuer_aliases_near_ticker(article, ticker)
        if aliases:
            register_ticker_aliases(ticker, aliases)
        for alias in get_ticker_aliases(ticker):
            key = _issuer_alias_key(alias)
            if key:
                alias_to_tickers.setdefault(key, set()).add(ticker)
    for ticker, bucket in TICKER_ALIAS_CACHE.items():
        for item in bucket.values():
            key = _issuer_alias_key(item.get("alias"))
            if key:
                alias_to_tickers.setdefault(key, set()).add(ticker)
    for article in articles:
        if _valid_idx_ticker((article.get("details") or {}).get("ticker")):
            continue
        hits = set()
        for alias_key, tickers in alias_to_tickers.items():
            if len(tickers) != 1:
                continue
            if _article_mentions_alias(article, alias_key):
                hits.update(tickers)
        if len(hits) == 1:
            recover_ticker_on_article(
                article, next(iter(hits)), source="ISSUER_ALIAS"
            )
    return articles


def _ticker_recovery_queries(ticker):
    ticker = _valid_idx_ticker(ticker)
    if not ticker:
        return []
    return list(dict.fromkeys(
        template.format(ticker=ticker)
        for template in TICKER_RECOVERY_QUERY_TEMPLATES[:TICKER_RECOVERY_QUERY_LIMIT]
    ))


async def search_ticker_recovery_articles(ticker):
    ticker = _valid_idx_ticker(ticker)
    if not ticker or not TICKER_RECOVERY_ENABLED:
        return []
    now = datetime.now(timezone.utc)
    cache = TICKER_RECOVERY_CACHE.get(ticker)
    if cache:
        cached_at = cache.get("cached_at")
        if cached_at and now - cached_at <= timedelta(minutes=TICKER_RECOVERY_CACHE_MINUTES):
            return [dict(x) for x in cache.get("articles", [])]
    queries = _ticker_recovery_queries(ticker)
    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0 Chrome/129 Safari/537.36"},
        follow_redirects=True,
    ) as client:
        results = await asyncio.gather(
            *[fetch_feed(client, q) for q in queries],
            return_exceptions=True,
        )
    found, seen = [], set()
    for query, result in zip(queries, results):
        if isinstance(result, Exception):
            continue
        for article in result:
            if not article_mentions_ticker(article, ticker):
                continue
            recover_ticker_on_article(article, ticker, source="TARGETED_SEARCH")
            article["recovery_query"] = query
            article["discovery_channel"] = "TICKER_RECOVERY"
            key = article.get("key") or article_key(
                article.get("title", ""), article.get("link", "")
            )
            if key in seen:
                continue
            seen.add(key)
            article["key"] = key
            found.append(article)
    found.sort(
        key=lambda x: (
            x.get("information_score", x.get("ca_score", 0)) or 0,
            x.get("published_dt") or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    TICKER_RECOVERY_CACHE[ticker] = {
        "cached_at": now,
        "articles": [dict(x) for x in found],
    }
    return found


async def recover_ticker_context(ticker, seed_articles=None):
    ticker = _valid_idx_ticker(ticker)
    if not ticker:
        return {"ticker": None, "articles": [], "aliases": [], "method": "INVALID"}
    matches = find_ticker_matches(list(seed_articles or []), ticker)
    method = "CURRENT_FEED"
    if not matches and TICKER_RECOVERY_ENABLED:
        matches = await search_ticker_recovery_articles(ticker)
        method = "TARGETED_SEARCH" if matches else "NOT_FOUND"
    aliases = []
    for article in matches:
        aliases.extend(extract_issuer_aliases_near_ticker(article, ticker))
    aliases.extend(get_ticker_aliases(ticker))
    dedup = {}
    for alias in aliases:
        key = _issuer_alias_key(alias)
        if key:
            dedup[key] = alias
    aliases = list(dedup.values())
    if aliases:
        register_ticker_aliases(ticker, aliases)
    return {
        "ticker": ticker,
        "articles": matches,
        "aliases": aliases,
        "method": method,
    }


def ticker_recovery_lines(article):
    if not article.get("ticker_recovered"):
        return []
    lines = [
        "🧩 <b>Ticker Recovery:</b> ✅ "
        + html.escape(str(article.get("ticker_recovery_source", "RECOVERY")))
    ]
    aliases = article.get("issuer_aliases") or []
    if aliases and not article.get("issuer_resolution_source"):
        lines.append("🏢 <b>Issuer:</b> " + html.escape(str(aliases[0])))
    return lines



# ============================================================
# V6.6.1 MULTI-SOURCE ISSUER RESOLVER
# ============================================================

def _dedup_issuer_aliases(values):
    output = {}
    for value in values or []:
        clean = _clean_issuer_alias(value)
        key = _issuer_alias_key(clean)
        if clean and key:
            output[key] = clean
    return list(output.values())


def extract_cooccurring_issuer_aliases(ticker, text):
    """Conservative ticker/name extraction from one headline+snippet unit.

    The ticker must occur as an exact word in the same text unit. We then
    accept only company-like names that include PT/Tbk or explicit issuer
    labels. This is deliberately looser than deep extraction but still avoids
    learning arbitrary organizations from the article.
    """
    ticker = _valid_idx_ticker(ticker)
    text = normalize(str(text or ""))
    if not ticker or not _ticker_exact_pattern(ticker).search(text):
        return []

    aliases = list(extract_issuer_aliases_from_text(ticker, text))

    patterns = [
        # PT Era Media Sejahtera Tbk anywhere in the same title/snippet.
        r"\bPT\.?\s+([A-Z][A-Za-z0-9&.,'’\- ]{2,100}?)\s+Tbk\.?\b",
        # Era Media Sejahtera Tbk (ticker may appear elsewhere in snippet).
        r"\b([A-Z][A-Za-z0-9&.,'’\- ]{4,100}?)\s+Tbk\.?\b",
        # Nama emiten/perusahaan: Era Media Sejahtera
        r"(?:Nama\s+(?:Emiten|Perusahaan)|Emiten)\s*[:\-]\s*"
        r"(?:PT\.?\s+)?([A-Z][A-Za-z0-9&.,'’\- ]{3,100}?)(?:\s+Tbk\.?)?(?=[,.;]|$)",
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            alias = _clean_issuer_alias(match.group(1))
            if alias:
                aliases.append(alias)

    return _dedup_issuer_aliases(aliases)


def _market_issuer_name_candidates(info):
    if not isinstance(info, dict):
        return []

    raw = [
        info.get("longName"),
        info.get("shortName"),
        info.get("displayName"),
        info.get("name"),
    ]

    aliases = []
    for value in raw:
        clean = _clean_issuer_alias(value)
        if not clean:
            continue

        low = clean.lower()
        if any(
            bad in low
            for bad in (
                "ordinary shares",
                "common stock",
                "equity",
                "indonesia stock exchange",
            )
        ):
            continue
        aliases.append(clean)

    return _dedup_issuer_aliases(aliases)


def _fetch_market_issuer_sync(ticker):
    ticker = _valid_idx_ticker(ticker)
    if (
        not ticker
        or not MARKET_ISSUER_LOOKUP_ENABLED
        or not YFINANCE_AVAILABLE
    ):
        return []

    symbol = f"{ticker}.JK"

    try:
        obj = yf.Ticker(symbol)
        info = {}

        getter = getattr(obj, "get_info", None)
        if callable(getter):
            try:
                result = getter()
                if isinstance(result, dict):
                    info.update(result)
            except Exception:
                pass

        if not info:
            try:
                result = getattr(obj, "info", None)
                if isinstance(result, dict):
                    info.update(result)
            except Exception:
                pass

        return _market_issuer_name_candidates(info)

    except Exception:
        return []


async def resolve_market_issuer_alias(ticker):
    ticker = _valid_idx_ticker(ticker)
    if not ticker or not MARKET_ISSUER_LOOKUP_ENABLED:
        return []

    now = time.time()
    cached = MARKET_ISSUER_CACHE.get(ticker)

    if cached and (
        now - cached.get("cached_at", 0)
        <= ISSUER_IDENTITY_CACHE_MINUTES * 60
    ):
        return list(cached.get("aliases", []))

    aliases = await asyncio.to_thread(
        _fetch_market_issuer_sync,
        ticker,
    )
    aliases = _dedup_issuer_aliases(aliases)

    MARKET_ISSUER_CACHE[ticker] = {
        "cached_at": now,
        "aliases": aliases,
    }

    return aliases


def _issuer_identity_queries(ticker):
    ticker = _valid_idx_ticker(ticker)
    if not ticker:
        return []

    return list(dict.fromkeys(
        template.format(ticker=ticker)
        for template in ISSUER_IDENTITY_QUERY_TEMPLATES[
            :ISSUER_IDENTITY_QUERY_LIMIT
        ]
    ))


async def discover_issuer_from_related_news(ticker):
    """Find a ticker/name pair from other public RSS headlines/snippets."""
    ticker = _valid_idx_ticker(ticker)
    if not ticker or not RELATED_ISSUER_DISCOVERY_ENABLED:
        return []

    cache_key = f"RELATED|{ticker}"
    now = time.time()
    cached = ISSUER_IDENTITY_CACHE.get(cache_key)

    if cached and (
        now - cached.get("cached_at", 0)
        <= ISSUER_IDENTITY_CACHE_MINUTES * 60
    ):
        return list(cached.get("aliases", []))

    queries = _issuer_identity_queries(ticker)

    async with httpx.AsyncClient(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/129 Safari/537.36"
            )
        },
        follow_redirects=True,
    ) as client:
        results = await asyncio.gather(
            *[fetch_feed(client, query) for query in queries],
            return_exceptions=True,
        )

    aliases = []

    for result in results:
        if isinstance(result, Exception):
            continue

        for article in result:
            combined = normalize(" ".join([
                str(article.get("title") or ""),
                str(article.get("snippet") or ""),
                str(article.get("description") or ""),
            ]))

            aliases.extend(
                extract_cooccurring_issuer_aliases(
                    ticker,
                    combined,
                )
            )

    aliases = _dedup_issuer_aliases(aliases)

    ISSUER_IDENTITY_CACHE[cache_key] = {
        "cached_at": now,
        "aliases": aliases,
    }

    return aliases


def extract_official_issuer_name_candidates(article):
    """Extract likely target issuer names from official disclosure titles."""
    if official_source_rank(article) <= 0:
        return []

    title = normalize(str(article.get("title") or ""))
    if not title:
        return []

    # Remove publisher suffixes frequently appended by RSS.
    title = re.sub(
        r"\s+-\s+(?:PT\s+)?Bursa Efek Indonesia.*$",
        "",
        title,
        flags=re.I,
    )

    candidates = []

    patterns = [
        # Pengumuman Pengambilalihan Era Media Sejahtera
        r"(?:PENGUMUMAN\s+(?:RINGKAS\s+)?)?"
        r"(?:PENGAMBILALIHAN|PERUBAHAN\s+PENGENDALI)\s+"
        r"(?:ATAS\s+)?(?:SAHAM\s+)?(?:PT\.?\s+)?"
        r"(.+?)(?:\s+TBK\.?)?$",

        # Penawaran Tender Wajib atas saham Era Media Sejahtera
        r"(?:PENGUMUMAN\s+)?PENAWARAN\s+TENDER(?:\s+WAJIB)?"
        r"(?:\s+ATAS)?(?:\s+SAHAM)?\s+(?:PT\.?\s+)?"
        r"(.+?)(?:\s+TBK\.?)?$",

        # Pengambilalihan saham PT Era Media Sejahtera Tbk
        r"(?:PENGAMBILALIHAN|AKUISISI)\s+(?:ATAS\s+)?SAHAM\s+"
        r"(?:PT\.?\s+)?(.+?)(?:\s+TBK\.?)?$",
    ]

    upper = title.upper()

    for pattern in patterns:
        match = re.search(pattern, upper, flags=re.I)
        if not match:
            continue

        alias = _clean_issuer_alias(match.group(1).title())
        if alias:
            candidates.append(alias)

    # Details target is also acceptable on an official disclosure.
    target = _clean_issuer_alias(
        (article.get("details") or {}).get("target")
    )
    if target:
        candidates.append(target)

    return _dedup_issuer_aliases(candidates)


def _alias_tokens(value):
    key = _issuer_alias_key(value)
    return [
        token
        for token in key.split()
        if token and token not in {"PT", "TBK"}
    ]


def issuer_alias_similarity(left, right):
    """0..1 token similarity for legal-name variants."""
    a = set(_alias_tokens(left))
    b = set(_alias_tokens(right))

    if not a or not b:
        return 0.0

    inter = len(a & b)
    union = len(a | b)
    containment = inter / max(1, min(len(a), len(b)))
    jaccard = inter / max(1, union)

    return max(containment, jaccard)


def match_official_candidate_to_known_aliases(candidate, known_aliases):
    for name in extract_official_issuer_name_candidates(candidate):
        for alias in known_aliases or []:
            if issuer_alias_similarity(name, alias) >= 0.80:
                return name
    return None


async def validate_ticker_alias_pair(ticker, alias):
    """Confirm an inferred issuer name with a separate RSS co-occurrence."""
    ticker = _valid_idx_ticker(ticker)
    alias = _clean_issuer_alias(alias)

    if not ticker or not alias:
        return False

    cache_key = f"PAIR|{ticker}|{_issuer_alias_key(alias)}"
    now = time.time()
    cached = ISSUER_IDENTITY_CACHE.get(cache_key)

    if cached and (
        now - cached.get("cached_at", 0)
        <= ISSUER_IDENTITY_CACHE_MINUTES * 60
    ):
        return bool(cached.get("validated"))

    queries = [
        f'"{ticker}" "{alias}"',
        f'"{ticker}" "{alias}" saham',
    ]

    async with httpx.AsyncClient(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/129 Safari/537.36"
            )
        },
        follow_redirects=True,
    ) as client:
        results = await asyncio.gather(
            *[fetch_feed(client, query) for query in queries],
            return_exceptions=True,
        )

    validated = False

    for result in results:
        if isinstance(result, Exception):
            continue

        for article in result:
            combined = normalize(" ".join([
                str(article.get("title") or ""),
                str(article.get("snippet") or ""),
            ]))

            ticker_match = bool(
                _ticker_exact_pattern(ticker).search(combined)
            )

            alias_match = _article_mentions_alias(
                article,
                alias,
            )

            if ticker_match and alias_match:
                validated = True
                break

        if validated:
            break

    ISSUER_IDENTITY_CACHE[cache_key] = {
        "cached_at": now,
        "validated": validated,
    }

    return validated


async def triangulate_issuer_from_official_candidates(
    ticker,
    seed_articles,
    reference_article=None,
):
    """Use official disclosure names only after independent ticker/name proof.

    We never learn an issuer merely because an official article is near in
    date. A candidate name must also be validated by a separate RSS result
    that explicitly co-occurs with the ticker.
    """
    ticker = _valid_idx_ticker(ticker)

    if (
        not ticker
        or not OFFICIAL_ISSUER_TRIANGULATION_ENABLED
    ):
        return []

    candidates = []

    for article in seed_articles or []:
        if official_source_rank(article) <= 0:
            continue

        if reference_article:
            ref_family = _event_family_for_correlation(
                reference_article.get("event_type")
            )
            cand_family = _event_family_for_correlation(
                article.get("event_type")
            )
            if ref_family != cand_family:
                continue

            a_dt = article.get("published_dt")
            r_dt = reference_article.get("published_dt")
            if a_dt and r_dt:
                try:
                    if abs((a_dt - r_dt).days) > ISSUER_PAIR_VALIDATION_DAYS:
                        continue
                except Exception:
                    pass

        for name in extract_official_issuer_name_candidates(article):
            candidates.append((name, article))

    # Dedup candidate names.
    dedup = {}
    for name, article in candidates:
        key = _issuer_alias_key(name)
        if key:
            dedup[key] = (name, article)

    candidates = list(dedup.values())[
        :ISSUER_TRIANGULATION_MAX_CANDIDATES
    ]

    validated = []

    for name, _article in candidates:
        if await validate_ticker_alias_pair(
            ticker,
            name,
        ):
            validated.append(name)

    return _dedup_issuer_aliases(validated)


async def resolve_multisource_issuer_alias(
    ticker,
    reference_article=None,
    seed_articles=None,
):
    """Resolve issuer identity without relying on one publisher page.

    Priority:
      1. existing memory / article aliases
      2. title+snippet co-occurrence
      3. market profile
      4. related-news identity search
      5. official-name triangulation with independent validation
    """
    ticker = _valid_idx_ticker(ticker)

    result = {
        "ticker": ticker,
        "aliases": [],
        "source": "NOT_FOUND",
        "attempts": [],
    }

    if (
        not ticker
        or not MULTI_SOURCE_ISSUER_RESOLVER_ENABLED
    ):
        return result

    aliases = []

    # 1) Existing cache/article identity.
    existing = list(get_ticker_aliases(ticker))

    if reference_article:
        existing.extend(
            reference_article.get("issuer_aliases") or []
        )

        combined = normalize(" ".join([
            str(reference_article.get("title") or ""),
            str(reference_article.get("snippet") or ""),
            str(reference_article.get("description") or ""),
        ]))
        existing.extend(
            extract_cooccurring_issuer_aliases(
                ticker,
                combined,
            )
        )

    existing = _dedup_issuer_aliases(existing)

    if existing:
        aliases = existing
        result["source"] = (
            reference_article.get("issuer_resolution_source")
            if reference_article
            and reference_article.get("issuer_resolution_source")
            else "MEMORY_OR_SNIPPET"
        )
        result["attempts"].append("MEMORY_OR_SNIPPET")

    # 2) Market profile.
    if not aliases and MARKET_ISSUER_LOOKUP_ENABLED:
        result["attempts"].append("MARKET_PROFILE")
        market_aliases = await resolve_market_issuer_alias(
            ticker
        )

        if market_aliases:
            aliases = market_aliases
            result["source"] = "MARKET_PROFILE"

    # 3) Related public RSS identity.
    if not aliases and RELATED_ISSUER_DISCOVERY_ENABLED:
        result["attempts"].append("RELATED_NEWS")
        related_aliases = await discover_issuer_from_related_news(
            ticker
        )

        if related_aliases:
            aliases = related_aliases
            result["source"] = "RELATED_NEWS"

    # 4) Official disclosure candidate -> independently validate ticker/name.
    if (
        not aliases
        and OFFICIAL_ISSUER_TRIANGULATION_ENABLED
    ):
        result["attempts"].append("OFFICIAL_TRIANGULATION")
        official_aliases = await triangulate_issuer_from_official_candidates(
            ticker,
            list(seed_articles or []),
            reference_article=reference_article,
        )

        if official_aliases:
            aliases = official_aliases
            result["source"] = "OFFICIAL_TRIANGULATION"

    aliases = _dedup_issuer_aliases(aliases)

    if aliases:
        register_ticker_aliases(
            ticker,
            aliases,
        )

        if reference_article is not None:
            reference_article["issuer_aliases"] = aliases
            reference_article["issuer_name"] = aliases[0]

            # Do not overwrite DEEP_ARTICLE with a weaker source.
            if not reference_article.get("issuer_resolution_source"):
                reference_article["issuer_resolution_source"] = result["source"]

            reference_article["issuer_resolution_attempts"] = list(
                result["attempts"]
            )

    result["aliases"] = aliases
    return result


def multisource_issuer_lines(article):
    aliases = article.get("issuer_aliases") or []
    source = article.get("issuer_resolution_source")

    if not aliases or not source:
        return []

    if source == "DEEP_ARTICLE":
        return []

    return [
        "🌐 <b>Multi-Source Issuer:</b> ✅ "
        + html.escape(str(aliases[0])),
        "🧭 <b>Identity Source:</b> "
        + html.escape(str(source)),
    ]



# ============================================================
# V6.6.1 VERIFIED OFFICIAL CACHE
# ============================================================

def _utc_iso_now():
    return datetime.now(timezone.utc).isoformat()


def _parse_utc_iso(value):
    try:
        dt = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _verified_official_entry(article):
    return {
        "authority": str(article.get("official_source") or "OFFICIAL"),
        "kind": str(article.get("official_kind") or "PRIMARY"),
        "event_type": str(article.get("event_type") or "CORPORATE ACTION"),
        "title": str(article.get("title") or "")[:500],
        "url": str(article.get("source_url") or article.get("link") or "")[:2000],
        "match_score": int(article.get("official_correlation_score", 0) or 0),
        "published": str(article.get("published") or "")[:200],
    }


def register_verified_official_candidates(ticker, articles, issuer_aliases=None):
    ticker = _valid_idx_ticker(ticker)
    if not ticker or not VERIFIED_OFFICIAL_CACHE_ENABLED:
        return None

    entries = []
    seen = set()

    for article in articles or []:
        if official_source_rank(article) <= 0:
            continue

        score = int(article.get("official_correlation_score", 0) or 0)
        if score < OFFICIAL_CORRELATION_MIN_SCORE:
            continue

        entry = _verified_official_entry(article)
        key = (
            entry["authority"].lower(),
            entry["event_type"].lower(),
            normalize(entry["title"]).lower(),
            entry["url"].lower(),
        )

        if key in seen:
            continue

        seen.add(key)
        entries.append(entry)

        if len(entries) >= VERIFIED_OFFICIAL_MAX_PER_TICKER:
            break

    if not entries:
        return None

    aliases = _dedup_issuer_aliases(
        list(issuer_aliases or []) + list(get_ticker_aliases(ticker))
    )

    record = {
        "ticker": ticker,
        "issuer_aliases": aliases[:8],
        "last_verified_utc": _utc_iso_now(),
        "entries": entries,
    }

    VERIFIED_OFFICIAL_CACHE[ticker] = record
    return record


def hydrate_verified_official_cache(data):
    if not isinstance(data, dict):
        return 0

    count = 0
    now = datetime.now(timezone.utc)

    for raw_ticker, raw_record in data.items():
        ticker = _valid_idx_ticker(raw_ticker)

        if not ticker or not isinstance(raw_record, dict):
            continue

        verified_dt = _parse_utc_iso(raw_record.get("last_verified_utc"))

        if not verified_dt:
            continue

        if now - verified_dt > timedelta(days=VERIFIED_OFFICIAL_CACHE_TTL_DAYS):
            continue

        entries = raw_record.get("entries")

        if not isinstance(entries, list) or not entries:
            continue

        clean_entries = []

        for item in entries[:VERIFIED_OFFICIAL_MAX_PER_TICKER]:
            if not isinstance(item, dict):
                continue

            title = str(item.get("title") or "").strip()
            authority = str(item.get("authority") or "").strip()

            if not title or not authority:
                continue

            clean_entries.append({
                "authority": authority[:100],
                "kind": str(item.get("kind") or "PRIMARY")[:50],
                "event_type": str(item.get("event_type") or "CORPORATE ACTION")[:80],
                "title": title[:500],
                "url": str(item.get("url") or "")[:2000],
                "match_score": int(item.get("match_score", 0) or 0),
                "published": str(item.get("published") or "")[:200],
            })

        if not clean_entries:
            continue

        aliases = _dedup_issuer_aliases(
            raw_record.get("issuer_aliases") or []
        )

        VERIFIED_OFFICIAL_CACHE[ticker] = {
            "ticker": ticker,
            "issuer_aliases": aliases[:8],
            "last_verified_utc": verified_dt.isoformat(),
            "entries": clean_entries,
        }

        if aliases:
            register_ticker_aliases(ticker, aliases)

        count += 1

    return count


def export_verified_official_cache():
    now = datetime.now(timezone.utc)
    output = {}

    for ticker, record in (VERIFIED_OFFICIAL_CACHE or {}).items():
        verified_dt = _parse_utc_iso(record.get("last_verified_utc"))

        if not verified_dt:
            continue

        if now - verified_dt > timedelta(days=VERIFIED_OFFICIAL_CACHE_TTL_DAYS):
            continue

        output[ticker] = {
            "ticker": ticker,
            "issuer_aliases": list(record.get("issuer_aliases") or [])[:8],
            "last_verified_utc": verified_dt.isoformat(),
            "entries": [
                dict(x)
                for x in (record.get("entries") or [])[:VERIFIED_OFFICIAL_MAX_PER_TICKER]
                if isinstance(x, dict)
            ],
        }

    return output


def get_verified_official_record(ticker):
    ticker = _valid_idx_ticker(ticker)

    if not ticker or not VERIFIED_OFFICIAL_CACHE_ENABLED:
        return None

    record = VERIFIED_OFFICIAL_CACHE.get(ticker)

    if not isinstance(record, dict):
        return None

    verified_dt = _parse_utc_iso(record.get("last_verified_utc"))

    if not verified_dt:
        return None

    age = datetime.now(timezone.utc) - verified_dt

    if age > timedelta(days=VERIFIED_OFFICIAL_CACHE_TTL_DAYS):
        VERIFIED_OFFICIAL_CACHE.pop(ticker, None)
        return None

    result = dict(record)
    result["age_seconds"] = max(0, int(age.total_seconds()))
    return result


def _human_cache_age(seconds):
    seconds = max(0, int(seconds or 0))

    if seconds < 60:
        return f"{seconds} detik lalu"
    if seconds < 3600:
        return f"{seconds // 60} menit lalu"
    if seconds < 86400:
        return f"{seconds // 3600} jam lalu"
    return f"{seconds // 86400} hari lalu"


def verified_official_ref_for_article(article):
    ticker = _valid_idx_ticker(
        (article.get("details") or {}).get("ticker")
    )

    if not ticker:
        return None

    record = get_verified_official_record(ticker)

    if not record:
        return None

    family = _event_family_for_correlation(
        article.get("event_type")
    )

    entries = [
        dict(entry)
        for entry in (record.get("entries") or [])
        if _event_family_for_correlation(entry.get("event_type")) == family
    ]

    if not entries:
        return None

    entries.sort(
        key=lambda x: int(x.get("match_score", 0) or 0),
        reverse=True,
    )

    best = entries[0]
    best["cached"] = True
    best["last_verified_utc"] = record.get("last_verified_utc")
    best["age_seconds"] = record.get("age_seconds", 0)
    return best


def attach_verified_official_refs(articles):
    if not VERIFIED_OFFICIAL_CACHE_ENABLED:
        return articles

    for article in articles or []:
        if official_source_rank(article) > 0:
            continue

        ref = verified_official_ref_for_article(article)

        if ref:
            article["verified_official_ref"] = ref

    return articles


# ============================================================
# V6.2 OFFICIAL SOURCE INTELLIGENCE
# ============================================================

def _official_rule_from_source(source="", url=""):
    source_text = normalize(str(source or "")).lower()
    source_exact = source_text.strip()
    host = _host(str(url or "")).lower()

    # Explicit protection: IDX Channel is a media publisher, not IDX/BEI.
    if "idxchannel" in source_text or "idxchannel" in host:
        return None

    for rule in OFFICIAL_SOURCE_RULES:
        for domain in rule["domains"]:
            domain = domain.lower()
            if host == domain or host.endswith("." + domain):
                return rule

        if source_exact in {
            x.lower() for x in rule.get("exact_aliases", ())
        }:
            return rule

        for alias in rule.get("aliases", ()):
            if alias.lower() in source_text:
                return rule

    return None


def annotate_official_source(article):
    if not OFFICIAL_SOURCE_PRIORITY_ENABLED:
        article["official_source"] = None
        article["official_kind"] = None
        article["official_rank"] = 0
        return article

    candidate_urls = [
        article.get("source_url"),
        article.get("official_url"),
        article.get("link"),
    ]

    rule = None

    for url in candidate_urls:
        rule = _official_rule_from_source(
            article.get("source", ""),
            url or "",
        )
        if rule:
            break

    if rule is None:
        rule = _official_rule_from_source(
            article.get("source", ""),
            "",
        )

    if rule:
        article["official_source"] = rule["authority"]
        article["official_kind"] = rule["kind"]
        article["official_rank"] = int(rule["rank"])
        article["official_match"] = True
    else:
        article["official_source"] = None
        article["official_kind"] = None
        article["official_rank"] = 0
        article["official_match"] = False

    return article


def official_source_rank(article):
    try:
        rank = int(article.get("official_rank", 0) or 0)
    except (TypeError, ValueError):
        rank = 0

    if rank:
        return rank

    annotate_official_source(article)

    try:
        return int(article.get("official_rank", 0) or 0)
    except (TypeError, ValueError):
        return 0


def official_source_label(article):
    source = article.get("official_source")
    kind = article.get("official_kind")

    if source and kind:
        return f"{source} ({kind})"

    return None


def _official_reference_from_article(article):
    if official_source_rank(article) <= 0:
        return None

    return {
        "authority": article.get("official_source"),
        "kind": article.get("official_kind"),
        "rank": official_source_rank(article),
        "title": article.get("title"),
        "url": article.get("source_url") or article.get("link"),
        "source": article.get("source"),
        "published": article.get("published"),
        "published_dt": article.get("published_dt"),
    }


def best_official_reference(articles):
    refs = []

    for article in articles:
        ref = _official_reference_from_article(article)
        if ref:
            refs.append(ref)

    if not refs:
        return None

    refs.sort(
        key=lambda ref: (
            int(ref.get("rank", 0) or 0),
            ref.get("published_dt")
            or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )

    return refs[0]


def attach_official_reference(article, related_articles):
    ref = best_official_reference(related_articles)

    if ref:
        article["official_reference"] = ref
        article["official_confirmed"] = True
    else:
        article["official_reference"] = None
        article["official_confirmed"] = False

    return article


def official_reference_lines(article):
    ref = article.get("official_reference")

    if not ref and official_source_rank(article) > 0:
        ref = _official_reference_from_article(article)

    if not ref:
        return [
            "🏛️ <b>Official Source:</b> ⚪ belum ditemukan pada kandidat feed resmi"
        ]

    authority = html.escape(str(ref.get("authority") or "OFFICIAL"))
    kind = html.escape(str(ref.get("kind") or "PRIMARY"))
    url = ref.get("url")

    lines = [
        f"🏛️ <b>Official Source:</b> ✅ {authority} — {kind}"
    ]

    if url:
        lines.append(
            f'📎 <a href="{html.escape(str(url), quote=True)}">'
            f'Buka sumber resmi</a>'
        )

    return lines


def _event_identity_text(value):
    text = normalize(str(value or "")).upper()
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _event_title_signature(title):
    stop = {
        "SAHAM", "EMITEN", "AKUISISI", "TENDER", "OFFER",
        "RIGHTS", "ISSUE", "HMETD", "IPO", "PENAWARAN",
        "PERUSAHAAN", "RESMI", "BAKAL", "AKAN", "INI",
        "DAN", "DI", "KE", "DARI", "UNTUK", "THE", "OF",
    }
    words = [
        x for x in re.findall(r"[A-Z0-9]{2,}", str(title or "").upper())
        if x not in stop
    ]
    return " ".join(words[:7])


def event_identity(article):
    family = alert_family(article.get("event_type", ""))
    d = article.get("details") or {}

    ticker = str(d.get("ticker") or "").upper().strip()
    if re.fullmatch(r"[A-Z]{4}", ticker):
        return f"{family}|TICKER|{ticker}"

    target = _event_identity_text(d.get("target"))
    acquirer = _event_identity_text(d.get("acquirer"))

    if target or acquirer:
        return f"{family}|PARTIES|{acquirer}|{target}"

    return (
        f"{family}|TITLE|"
        f"{_event_title_signature(article.get('title', ''))}"
    )


def _detail_richness(article):
    d = article.get("details") or {}
    keys = (
        "ticker", "money", "percentages", "ratio",
        "execution_price", "price_range", "share_count",
        "standby_buyer", "underwriter", "acquirer", "target",
    )
    score = 0

    for key in keys:
        value = d.get(key)
        if value:
            score += 1

    return score


def _primary_article_rank(article):
    return (
        PRIORITY_RANK.get(
            article.get("urgency", article.get("priority", "LOW")),
            1,
        ),
        _detail_richness(article),
        article.get("information_score", article.get("ca_score", 0)) or 0,
        official_source_rank(article),
        article.get("published_dt")
        or datetime.min.replace(tzinfo=timezone.utc),
    )


def group_event_articles(articles):
    groups = {}

    for article in articles:
        key = event_identity(article)
        group = groups.get(key)

        if group is None:
            groups[key] = {
                "key": key,
                "articles": [article],
                "primary": article,
            }
            continue

        group["articles"].append(article)

        if _primary_article_rank(article) > _primary_article_rank(
            group["primary"]
        ):
            group["primary"] = article

    result = []

    for group in groups.values():
        official_ref = best_official_reference(group["articles"])
        group["official_reference"] = official_ref
        group["official_rank"] = (
            int(official_ref.get("rank", 0))
            if official_ref
            else 0
        )
        attach_official_reference(
            group["primary"],
            group["articles"],
        )
        result.append(group)

    return result


def _event_family_for_correlation(event_type):
    event = str(event_type or "").upper()
    if event == "IPO":
        return "IPO"
    if event == "RIGHTS ISSUE":
        return "RIGHTS"
    return "M&A"


def _control_change_reference(article):
    event = str(article.get("event_type") or "").upper()
    stage = str(article.get("stage") or "").upper()
    return (
        event in {"TENDER OFFER", "TAKEOVER"}
        or "CHANGE OF CONTROL" in stage
        or "TENDER" in stage
        or "PENGENDALI" in stage
    )


def _alias_target_role_in_title(title, aliases):
    normalized = _issuer_alias_key(title)
    if not normalized:
        return False
    for alias in aliases or []:
        a = _issuer_alias_key(alias)
        if not a:
            continue
        # target-role wording: action comes before issuer name.
        patterns = [
            rf"(?:PENGAMBILALIHAN|AKUISISI|TAKEOVER).{{0,8}}{re.escape(a)}",
            rf"(?:PENGENDALI|KONTROL).{{0,15}}{re.escape(a)}",
        ]
        if any(re.search(p, normalized) for p in patterns):
            return True
    return False


def _alias_acquirer_role_in_title(title, aliases):
    normalized = _issuer_alias_key(title)
    if not normalized:
        return False
    for alias in aliases or []:
        a = _issuer_alias_key(alias)
        if not a:
            continue
        if re.search(
            rf"{re.escape(a)}.{{0,12}}(?:MENGAKUISISI|AKUISISI|MENGAMBILALIH|AMBIL ALIH)",
            normalized,
        ):
            return True
    return False


def official_candidate_correlation_score(candidate, ticker, issuer_aliases, reference_article=None):
    """Conservative event correlation for an official disclosure.

    Alias-only matching is not enough for M&A control-change events: the title
    should indicate that the issuer is the target, not merely the acquirer.
    """
    if official_source_rank(candidate) <= 0:
        return -999

    ticker = _valid_idx_ticker(ticker)
    cand_ticker = _valid_idx_ticker((candidate.get("details") or {}).get("ticker"))
    if cand_ticker and ticker and cand_ticker != ticker:
        return -999

    alias_match = any(
        _article_mentions_alias(candidate, alias)
        for alias in (issuer_aliases or [])
    )
    ticker_match = bool(ticker and (cand_ticker == ticker or article_mentions_ticker(candidate, ticker)))

    score = min(2, official_source_rank(candidate))
    if ticker_match:
        score += 6
    if alias_match:
        score += 4

    if reference_article:
        ref_family = _event_family_for_correlation(reference_article.get("event_type"))
        cand_family = _event_family_for_correlation(candidate.get("event_type"))
        if ref_family == cand_family:
            score += 3
        else:
            score -= 6

        if ref_family == "M&A" and _control_change_reference(reference_article) and not ticker_match:
            target_role = _alias_target_role_in_title(candidate.get("title", ""), issuer_aliases)
            acquirer_role = _alias_acquirer_role_in_title(candidate.get("title", ""), issuer_aliases)
            target_field = _clean_issuer_alias((candidate.get("details") or {}).get("target"))
            target_field_match = bool(target_field and any(
                _issuer_alias_key(target_field) == _issuer_alias_key(alias)
                for alias in (issuer_aliases or [])
            ))
            if target_role or target_field_match:
                score += 3
            elif acquirer_role:
                score -= 6
            else:
                # Ambiguous alias-only M&A relationship: do not over-confirm.
                score -= 3

    # Very old documents should not corroborate a fresh corporate-action event.
    if reference_article:
        a_dt = candidate.get("published_dt")
        r_dt = reference_article.get("published_dt")
        if a_dt and r_dt:
            try:
                if abs((a_dt - r_dt).days) > OFFICIAL_CORRELATION_DAYS:
                    score -= 5
            except Exception:
                pass

    return score


def correlate_official_candidates(seed_articles, ticker, issuer_aliases, reference_article=None):
    results = []
    seen = set()
    for candidate in seed_articles or []:
        if official_source_rank(candidate) <= 0:
            continue
        score = official_candidate_correlation_score(
            candidate,
            ticker,
            issuer_aliases,
            reference_article=reference_article,
        )
        if score < OFFICIAL_CORRELATION_MIN_SCORE:
            continue
        if not _valid_idx_ticker((candidate.get("details") or {}).get("ticker")) and ticker:
            recover_ticker_on_article(candidate, ticker, source="OFFICIAL_CORRELATED")
        candidate["official_correlation_score"] = score
        key = candidate.get("key") or article_key(candidate.get("title", ""), candidate.get("link", ""))
        if key in seen:
            continue
        seen.add(key)
        results.append(candidate)
    results.sort(
        key=lambda x: (
            x.get("official_correlation_score", 0),
            official_source_rank(x),
            x.get("published_dt") or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    return results


def _official_ticker_query_specs(ticker, issuer_aliases=None):
    ticker = str(ticker or "").upper().strip()
    aliases = [
        alias for alias in (issuer_aliases or [])
        if _clean_issuer_alias(alias)
    ][:2]

    if aliases:
        terms = " OR ".join(
            [f'"{ticker}"'] + [f'"{alias}"' for alias in aliases]
        )
        needle = f"({terms})"
    else:
        needle = f'"{ticker}"'

    return [
        ("IDX", f"site:idx.co.id {needle}"),
        ("e-IPO", f"site:e-ipo.co.id {needle}"),
        ("KSEI", f"site:web.ksei.co.id {needle}"),
        ("OJK", f"site:ojk.go.id {needle}"),
    ]


async def search_official_ticker_articles(ticker, issuer_aliases=None):
    ticker = str(ticker or "").upper().strip()

    if not re.fullmatch(r"[A-Z]{4}", ticker):
        return []

    if not OFFICIAL_ON_DEMAND_ENABLED:
        return []

    issuer_aliases = list(issuer_aliases or get_ticker_aliases(ticker))
    alias_cache_key = "|".join(sorted(
        _issuer_alias_key(alias)
        for alias in issuer_aliases
        if _issuer_alias_key(alias)
    ))
    cache_key = f"{ticker}|{alias_cache_key}"

    cache = OFFICIAL_SEARCH_CACHE.get(cache_key)
    now = datetime.now(timezone.utc)

    if cache:
        cached_at = cache.get("cached_at")
        if (
            cached_at
            and now - cached_at
            <= timedelta(minutes=OFFICIAL_SEARCH_CACHE_MINUTES)
        ):
            return [
                dict(x)
                for x in cache.get("articles", [])
            ]

    specs = _official_ticker_query_specs(
        ticker,
        issuer_aliases=issuer_aliases,
    )

    async with httpx.AsyncClient(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/129 Safari/537.36"
            )
        },
        follow_redirects=True,
    ) as client:
        tasks = [
            fetch_feed(client, query)
            for _, query in specs
        ]
        results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

    found = []
    seen = set()

    for (authority_hint, query), result in zip(specs, results):
        if isinstance(result, Exception):
            continue

        for article in result:
            article["discovery_channel"] = "OFFICIAL_ON_DEMAND"
            article["official_query_hint"] = authority_hint
            annotate_official_source(article)

            if official_source_rank(article) <= 0:
                continue

            article_ticker = str(
                (article.get("details") or {}).get("ticker") or ""
            ).upper()

            if article_ticker != ticker:
                combined = (
                    f"{article.get('title', '')} "
                    f"{article.get('snippet', '')}"
                )
                ticker_match = bool(_ticker_exact_pattern(ticker).search(combined))
                alias_match = any(
                    _article_mentions_alias(article, alias)
                    for alias in issuer_aliases
                )
                if not ticker_match and not alias_match:
                    continue
                recover_ticker_on_article(
                    article,
                    ticker,
                    source="OFFICIAL_ALIAS" if alias_match else "OFFICIAL_TICKER",
                )

            key = article_key(
                article.get("title", ""),
                article.get("link", ""),
            )

            if key in seen:
                continue

            seen.add(key)
            article["key"] = key
            article["ca_score"] = corporate_action_score(article)
            article["information_score"] = article["ca_score"]
            found.append(article)

    found.sort(
        key=lambda x: (
            official_source_rank(x),
            x.get("published_dt")
            or datetime.min.replace(tzinfo=timezone.utc),
            x.get("ca_score", 0),
        ),
        reverse=True,
    )

    OFFICIAL_SEARCH_CACHE[cache_key] = {
        "cached_at": now,
        "articles": [
            dict(x)
            for x in found
        ],
    }

    return found


async def official_ticker(chat_id, ticker):
    ticker = str(ticker or "").upper().strip()

    if not re.fullmatch(r"[A-Z]{4}", ticker):
        await send_message(chat_id, "Format: /official TICKER — contoh /official DOOH")
        return

    await send_message(chat_id, f"🏛️ Mencari sumber resmi untuk {ticker}…")

    seed_articles = await fetch_all_articles()
    recovery = await recover_ticker_context(ticker, seed_articles=seed_articles)
    reference_articles = recovery.get("articles", []) or []
    reference_article = reference_articles[0] if reference_articles else None

    issuer_aliases = list(recovery.get("aliases", []) or [])

    # Try deep publisher identity first. If it is restricted/failed, V6.6.1
    # continues with market profile, related RSS, and official triangulation.
    if (
        not issuer_aliases
        and reference_article
        and DEEP_ISSUER_RESOLVER_ENABLED
    ):
        await deep_enrich_article(reference_article)
        issuer_aliases.extend(
            reference_article.get("issuer_aliases", []) or []
        )
        issuer_aliases.extend(
            get_ticker_aliases(ticker)
        )

    issuer_aliases = _dedup_issuer_aliases(
        issuer_aliases
    )

    if (
        not issuer_aliases
        and MULTI_SOURCE_ISSUER_RESOLVER_ENABLED
    ):
        multi = await resolve_multisource_issuer_alias(
            ticker,
            reference_article=reference_article,
            seed_articles=seed_articles,
        )
        issuer_aliases.extend(
            multi.get("aliases", [])
        )

    issuer_aliases = _dedup_issuer_aliases(
        issuer_aliases
    )

    if issuer_aliases:
        register_ticker_aliases(
            ticker,
            issuer_aliases,
        )
        propagate_tickers_by_issuer_alias(
            seed_articles
        )

    articles = correlate_official_candidates(
        seed_articles,
        ticker,
        issuer_aliases,
        reference_article=reference_article,
    )

    searched = await search_official_ticker_articles(
        ticker,
        issuer_aliases=issuer_aliases,
    )
    articles.extend(
        correlate_official_candidates(
            searched,
            ticker,
            issuer_aliases,
            reference_article=reference_article,
        )
    )

    # Stable dedup.
    dedup = {}
    for article in articles:
        key = article.get("key") or article_key(article.get("title", ""), article.get("link", ""))
        dedup[key] = article
    articles = list(dedup.values())
    articles.sort(
        key=lambda x: (
            x.get("official_correlation_score", 0),
            official_source_rank(x),
            x.get("published_dt") or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )

    if not articles:
        cached = get_verified_official_record(ticker)

        if cached and cached.get("entries"):
            lines = [
                f"🏛️ <b>OFFICIAL CHECK {ticker}</b>",
                "",
                "Status: ✅ VERIFIED CACHE — live lookup sementara tidak menghasilkan kandidat",
            ]

            cached_aliases = _dedup_issuer_aliases(
                list(issuer_aliases or [])
                + list(cached.get("issuer_aliases") or [])
            )

            if cached_aliases:
                lines.append(
                    "🏢 Issuer Resolver: ✅ "
                    + html.escape(str(cached_aliases[0]))
                )

            lines.append(
                "💾 <b>Last verified:</b> "
                + html.escape(
                    _human_cache_age(cached.get("age_seconds", 0))
                )
            )
            lines.append(
                "🌐 Live official lookup: ⚠️ EMPTY/TEMPORARY"
            )
            lines.append("")

            for idx, entry in enumerate(
                cached.get("entries", [])[:5],
                start=1,
            ):
                authority = html.escape(
                    str(entry.get("authority") or "OFFICIAL")
                )
                kind = html.escape(
                    str(entry.get("kind") or "PRIMARY")
                )
                event = html.escape(
                    str(entry.get("event_type") or "CORPORATE ACTION")
                )
                title = html.escape(
                    str(entry.get("title") or "")
                )
                score = int(
                    entry.get("match_score", 0) or 0
                )
                url = str(entry.get("url") or "")

                lines.append(
                    f"{idx}. 💾 <b>{authority}</b> — "
                    f"{kind} — {event} | Match {score}"
                )
                lines.append(f"   {title[:180]}")

                if url:
                    lines.append(
                        f'   <a href="{html.escape(url, quote=True)}">'
                        "Buka sumber resmi</a>"
                    )

                lines.append("")

            await send_message(
                chat_id,
                "\n".join(lines)[:3900],
            )
            return

        await send_message(
            chat_id,
            (
                f"🏛️ <b>OFFICIAL CHECK {ticker}</b>\n\n"
                "Status: ⚪ BELUM DITEMUKAN pada kandidat resmi yang berkorelasi.\n"
                + (
                    "🏢 Issuer Resolver: ✅ " + html.escape(str(issuer_aliases[0])) + "\n"
                    if issuer_aliases else ""
                )
                + "🧩 Ticker Recovery: " + html.escape(str(recovery.get("method", "NOT_FOUND"))) + "\n"
                + "💾 Verified Cache: belum tersedia\n"
                + "Filter V6.6.1 sengaja konservatif agar dokumen resmi corporate action lain dari emiten yang sama tidak salah dianggap sebagai konfirmasi event ini."
            ),
        )
        return

    register_verified_official_candidates(
        ticker,
        articles,
        issuer_aliases=issuer_aliases,
    )

    lines = [
        f"🏛️ <b>OFFICIAL CHECK {ticker}</b>",
        "",
        f"Status: ✅ DITEMUKAN {len(articles)} kandidat resmi berkorelasi",
        "💾 Verification: ✅ LIVE → VERIFIED CACHE",
    ]
    if issuer_aliases:
        lines.append("🏢 Issuer Resolver: ✅ " + html.escape(str(issuer_aliases[0])))
    lines.append("")

    for idx, article in enumerate(articles[:5], start=1):
        authority = html.escape(str(article.get("official_source") or "OFFICIAL"))
        kind = html.escape(str(article.get("official_kind") or "PRIMARY"))
        event = html.escape(str(article.get("event_type") or "CORPORATE ACTION"))
        title = html.escape(str(article.get("title") or ""))
        score = int(article.get("official_correlation_score", 0) or 0)
        url = article.get("source_url") or article.get("link") or ""
        lines.append(f"{idx}. ✅ <b>{authority}</b> — {kind} — {event} | Match {score}")
        lines.append(f"   {title[:180]}")
        if url:
            lines.append(f'   <a href="{html.escape(str(url), quote=True)}">Buka sumber resmi</a>')
        lines.append("")

    await send_message(chat_id, "\n".join(lines)[:3900])

# ============================================================
# GEO / SCORE
# ============================================================

def geo_category(text, source=""):
    low = f" {text.lower()} "
    src = source.lower()

    source_hit = any(hint in src for hint in INDONESIA_SOURCE_HINTS)
    text_hits = sum(1 for hint in INDONESIA_TEXT_HINTS if hint in low)

    if source_hit or text_hits >= 2:
        return "INDONESIA 🇮🇩"

    if text_hits == 1:
        return "KEMUNGKINAN INDONESIA 🇮🇩"

    return "GLOBAL 🌐"


def source_score(source):
    src = source.lower()

    tier_a = [
        "idx", "bursa efek indonesia", "ojk",
        "ksei", "e-ipo", "idnfinancials",
    ]

    tier_b = [
        "kontan", "bisnis.com", "cnbc indonesia",
        "investor.id", "bareksa", "emitennews",
        "pasardana", "detikfinance", "katadata",
    ]

    if any(x in src for x in tier_a):
        return 20

    if any(x in src for x in tier_b):
        return 14

    return 7


PRIORITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}


def priority_level(event, stage):
    # HIGH = event dekat/di eksekusi dan biasanya paling actionable.
    if event == "IPO":
        if stage in ("BOOKBUILDING", "OFFERING", "LISTING"):
            return "HIGH"
        if stage == "RENCANA / PROSPEKTUS":
            return "MEDIUM"
        return "LOW"

    if event == "RIGHTS ISSUE":
        if stage in ("EFEKTIF", "PERDAGANGAN HMETD"):
            return "HIGH"
        if stage in ("DISETUJUI RUPSLB", "RENCANA"):
            return "MEDIUM"
        return "LOW"

    if event in ("TENDER OFFER", "TAKEOVER"):
        if stage in ("TENDER OFFER", "CHANGE OF CONTROL", "COMPLETED", "SPA / SIGNED"):
            return "HIGH"
        if stage in ("MOU", "RENCANA"):
            return "MEDIUM"
        return "LOW"

    if event in ("AKUISISI", "PEMBELIAN SAHAM", "MERGER"):
        if stage in ("SPA / SIGNED", "COMPLETED", "CHANGE OF CONTROL"):
            return "HIGH"
        if stage in ("MOU", "RENCANA"):
            return "MEDIUM"
        return "LOW"

    return "LOW"


def priority_badge(priority):
    return {
        "HIGH": "🔴 HIGH",
        "MEDIUM": "🟠 MEDIUM",
        "LOW": "⚪ LOW",
    }.get(priority, "⚪ LOW")


def priority_meets_minimum(priority, minimum):
    return PRIORITY_RANK.get(priority, 1) >= PRIORITY_RANK.get(minimum, 2)


def corporate_action_score(article):
    score = 30

    d = article["details"]
    event = article["event_type"]
    priority = article.get("priority", "LOW")

    score += source_score(article["source"])

    if OFFICIAL_SOURCE_PRIORITY_ENABLED:
        official_rank = official_source_rank(article)
        if official_rank >= 4:
            score += OFFICIAL_SOURCE_SCORE_BOOST
        elif official_rank > 0:
            score += max(2, OFFICIAL_SOURCE_SCORE_BOOST // 2)

    if priority == "HIGH":
        score += 10
    elif priority == "MEDIUM":
        score += 5

    if article["geo"].startswith("INDONESIA"):
        score += 10

    if d["ticker"]:
        score += 8

    if d["money"]:
        score += 6

    if d["percentages"]:
        score += 5

    if event == "RIGHTS ISSUE":
        if d["ratio"]:
            score += 6
        if d["execution_price"]:
            score += 6
        if d["share_count"]:
            score += 4
        if d["standby_buyer"]:
            score += 5

    elif event == "IPO":
        if d["price_range"]:
            score += 6
        if d["share_count"]:
            score += 4
        if article["stage"] in ("BOOKBUILDING", "OFFERING", "LISTING"):
            score += 8

    else:
        if d["acquirer"]:
            score += 4
        if d["target"]:
            score += 4
        if article["stage"] in ("SPA / SIGNED", "COMPLETED", "CHANGE OF CONTROL"):
            score += 8

    dt = article.get("published_dt")

    if dt:
        age = datetime.now(timezone.utc) - dt
        if age <= timedelta(hours=24):
            score += 10
        elif age <= timedelta(days=7):
            score += 5

    return max(0, min(100, score))


def score_label(score):
    if score >= 85:
        return "🔥 SANGAT KUAT"
    if score >= 70:
        return "🟢 MENARIK"
    if score >= 55:
        return "🟡 PERLU DIPANTAU"
    return "⚪ INFORMASI"


def alert_family(event):
    if event == "IPO":
        return "IPO"
    if event == "RIGHTS ISSUE":
        return "RIGHTS ISSUE"
    return "M&A / TAKEOVER"


def alert_icon(event):
    return {
        "IPO": "🆕",
        "RIGHTS ISSUE": "📣",
        "AKUISISI": "🤝",
        "TAKEOVER": "🚨",
        "TENDER OFFER": "📢",
        "PEMBELIAN SAHAM": "💼",
        "MERGER": "🔄",
    }.get(event, "📈")


# ============================================================
# V4.3 CATALYST ENGINE
# ============================================================

NEGATIVE_CATALYST_PHRASES = [
    "batal", "dibatalkan", "gagal", "ditunda", "ditolak",
    "suspensi", "default", "pailit", "rugi besar",
]

POSITIVE_EXPANSION_PHRASES = [
    "ekspansi", "penambahan kapasitas", "modal kerja",
    "pengembangan usaha", "akuisisi", "ekspansi bisnis",
]

def catalyst_badge(value):
    return {
        "POSITIVE": "🟢 POSITIVE",
        "NEUTRAL": "⚪ NEUTRAL",
        "NEGATIVE": "🔴 NEGATIVE",
    }.get(value, "⚪ NEUTRAL")

def catalyst_assessment(event, stage, text, details, ipo_class=None):
    """
    Catalyst adalah pembacaan otomatis atas corporate action,
    BUKAN prediksi harga saham.
    """
    low = text.lower()
    reasons = []
    participation = participation_context(text)

    if any(p in low for p in NEGATIVE_CATALYST_PHRASES):
        reasons.append("Terdapat indikasi pembatalan, penundaan, atau risiko eksekusi.")
        return "NEGATIVE", reasons

    # V4.4: stage kuat tidak otomatis positif bila respons investor lemah.
    if participation == "WEAK":
        reasons.append("Partisipasi/serapan investor terindikasi lemah.")
        if event in ("TENDER OFFER", "TAKEOVER", "AKUISISI", "PEMBELIAN SAHAM"):
            reasons.append("Kepastian transaksi dapat tetap tinggi, tetapi respons pemegang saham tidak kuat.")
            return "NEUTRAL", reasons
        if event == "RIGHTS ISSUE":
            reasons.append("Serapan yang lemah dapat meningkatkan risiko tidak terserap/dilusi.")
            return "NEGATIVE", reasons

    if participation == "STRONG":
        reasons.append("Partisipasi/permintaan investor terindikasi kuat.")

    if event == "IPO":
        if ipo_class == "PIPELINE":
            reasons.append("Masih berupa informasi pipeline pasar, belum transaksi emiten spesifik.")
            return "NEUTRAL", reasons

        if ipo_class == "ACTIONABLE":
            reasons.append(f"IPO sudah berada pada tahap {stage}.")
            if details.get("price_range"):
                reasons.append("Range harga penawaran sudah terdeteksi.")
            if details.get("share_count") or details.get("money"):
                reasons.append("Detail ukuran penawaran mulai tersedia.")
            return "POSITIVE", reasons[:3]

        reasons.append("Calon emiten sudah teridentifikasi, tetapi detail eksekusi masih terbatas.")
        return "NEUTRAL", reasons

    if event == "RIGHTS ISSUE":
        if any(p in low for p in POSITIVE_EXPANSION_PHRASES):
            reasons.append("Dana terindikasi digunakan untuk ekspansi/pengembangan usaha.")
            if details.get("standby_buyer"):
                reasons.append("Standby buyer terdeteksi, membantu kepastian penyerapan.")
            return "POSITIVE", reasons[:3]

        if "pelunasan utang" in low or "bayar utang" in low:
            reasons.append("Dana terindikasi untuk memperkuat struktur pendanaan/pelunasan kewajiban.")
            reasons.append("Tetap perhatikan potensi dilusi pemegang saham.")
            return "NEUTRAL", reasons

        reasons.append("Rights Issue dapat menimbulkan dilusi bila HMETD tidak dieksekusi.")
        if stage in ("EFEKTIF", "PERDAGANGAN HMETD"):
            reasons.append(f"Corporate action sudah memasuki tahap {stage}.")
        return "NEUTRAL", reasons[:3]

    if stage in ("COMPLETED", "SPA / SIGNED", "CHANGE OF CONTROL", "TENDER OFFER"):
        reasons.append(f"Transaksi sudah berada pada tahap {stage}, sehingga kepastian eksekusi lebih tinggi.")
        if details.get("percentages"):
            reasons.append("Persentase stake transaksi sudah terdeteksi.")
        if details.get("money"):
            reasons.append("Nilai transaksi sudah terdeteksi.")
        return "POSITIVE", reasons[:3]

    if stage in ("MOU", "RENCANA"):
        reasons.append("Transaksi masih tahap awal sehingga risiko eksekusi masih ada.")
        return "NEUTRAL", reasons

    reasons.append("Belum cukup informasi untuk menilai dampak transaksi secara kuat.")
    return "NEUTRAL", reasons


# ============================================================
# RSS
# ============================================================

def build_rss_url(query):
    return GOOGLE_NEWS_RSS.format(query=quote_plus(query))


def text_of(parent, tag, default=""):
    node = parent.find(tag)

    if node is None or node.text is None:
        return default

    return normalize(node.text)


def parse_google_news_rss(xml_bytes):
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")

    if channel is None:
        return []

    items = []

    for item in channel.findall("item"):
        source_node = item.find("source")

        source = (
            normalize(source_node.text)
            if source_node is not None and source_node.text
            else "Google News"
        )

        published_raw = text_of(
            item,
            "pubDate",
            "Waktu publikasi tidak tersedia",
        )

        items.append({
            "title": text_of(item, "title"),
            "link": text_of(item, "link"),
            "published": published_raw,
            "published_dt": parse_date(published_raw),
            "description": strip_html(text_of(item, "description")),
            "source": source,
        })

    return items


async def fetch_feed(client, query):
    response = None
    last_exc = None

    for attempt in range(HTTP_RETRY_ATTEMPTS):
        try:
            response = await client.get(
                build_rss_url(query),
                timeout=25.0,
                follow_redirects=True,
            )
            response.raise_for_status()
            break

        except (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.RemoteProtocolError,
            httpx.HTTPStatusError,
        ) as exc:
            last_exc = exc
            retryable = True

            if isinstance(exc, httpx.HTTPStatusError):
                status = exc.response.status_code
                retryable = (
                    status == 429
                    or 500 <= status <= 599
                )

            if (
                not retryable
                or attempt >= HTTP_RETRY_ATTEMPTS - 1
            ):
                raise

            delay = HTTP_RETRY_BASE_SECONDS * (2 ** attempt)

            if (
                isinstance(exc, httpx.HTTPStatusError)
                and exc.response.status_code == 429
            ):
                try:
                    retry_after = float(
                        exc.response.headers.get("Retry-After", "0")
                        or 0
                    )
                    delay = max(delay, min(15.0, retry_after))
                except Exception:
                    pass

            await asyncio.sleep(min(15.0, delay))

    if response is None:
        if last_exc:
            raise last_exc
        raise RuntimeError("Feed request gagal tanpa response.")

    entries = parse_google_news_rss(response.content)
    rows = []

    for entry in entries:
        if not is_recent_days(entry["published_dt"]):
            continue

        title = normalize(entry["title"])
        description = normalize(entry["description"])
        combined = f"{title} {description}"

        evt = event_type(combined)

        if not evt:
            continue

        # V4.4: buang berita yang hanya membahas kondisi setelah event.
        if is_post_event_commentary(combined, evt):
            continue

        relevance = relevance_score(combined, evt)

        if relevance < CONFIG.get("minimum_score", 8):
            continue

        geo = geo_category(combined, entry["source"])
        ticker = extract_ticker(title, combined, geo)

        percentages = extract_percentages(combined)
        ratio = extract_ratio(combined) if evt == "RIGHTS ISSUE" else None
        execution_price = (
            extract_execution_price(combined)
            if evt == "RIGHTS ISSUE"
            else None
        )
        price_range = (
            extract_price_range(combined)
            if evt == "IPO"
            else None
        )
        ipo_single_price = (
            extract_ipo_single_price(combined)
            if evt == "IPO"
            else None
        )
        tender_price = (
            extract_tender_price(combined)
            if evt in (
                "TENDER OFFER",
                "TAKEOVER",
                "AKUISISI",
                "PEMBELIAN SAHAM",
            )
            else None
        )
        money = remove_price_duplicates(
            extract_money(combined, event=evt),
            execution_price=execution_price,
            price_range=price_range,
        )

        # V5: harga per saham bukan otomatis nilai transaksi/dana.
        blocked_prices = {
            money_key(ipo_single_price),
            money_key(tender_price),
        }

        money = [
            x for x in money
            if money_key(x) not in blocked_prices
        ]
        share_count = extract_share_count(combined)
        standby_buyer = (
            extract_standby_buyer(combined)
            if evt == "RIGHTS ISSUE"
            else None
        )
        underwriter = (
            extract_underwriter(combined)
            if evt == "IPO"
            else None
        )
        use_of_funds = classify_use_of_funds(combined)

        acquirer, target = (None, None)
        role_meta = {}

        if evt not in ("IPO", "RIGHTS ISSUE"):
            (
                acquirer,
                target,
                role_meta,
            ) = extract_acquirer_target_with_meta(title)

        if evt == "IPO":
            stage = classify_ipo_stage(combined)
        elif evt == "RIGHTS ISSUE":
            stage = classify_rights_stage(combined)
        else:
            stage = classify_ma_stage(combined, evt)

        priority = priority_level(evt, stage)

        details = {
            "ticker": ticker,
            "percentages": percentages,
            "money": money,
            "ratio": ratio,
            "execution_price": execution_price,
            "price_range": price_range,
            "ipo_single_price": ipo_single_price,
            "tender_price": tender_price,
            "share_count": share_count,
            "standby_buyer": standby_buyer,
            "underwriter": underwriter,
            "use_of_funds": use_of_funds,
            "schedule": {},
            "acquirer": acquirer,
            "target": target,
            "role_meta": role_meta,
        }

        ipo_class = None
        if evt == "IPO":
            ipo_class = classify_ipo_intelligence(
                combined,
                stage,
                details,
            )

        catalyst, catalyst_reasons = catalyst_assessment(
            evt,
            stage,
            combined,
            details,
            ipo_class=ipo_class,
        )

        context = article_context(
            evt,
            combined,
            ipo_class=ipo_class,
        )

        article = {
            "title": title,
            "link": normalize(entry["link"]),
            "published": entry["published"],
            "published_dt": entry["published_dt"],
            "source": entry["source"],
            "snippet": description,
            "event_type": evt,
            "stage": stage,
            "priority": priority,
            "urgency": priority,
            "ipo_class": ipo_class,
            "catalyst": catalyst,
            "catalyst_reasons": catalyst_reasons,
            "context": context,
            "geo": geo,
            "relevance_score": relevance,
            "query": query,
            "details": details,
        }

        apply_article_integrity_guards(article)

        article["ca_score"] = corporate_action_score(article)
        article["information_score"] = article["ca_score"]
        rows.append(article)

    return rows


async def fetch_all_articles():
    queries = CONFIG.get("queries", [])

    query_specs = [
        ("NEWS", query)
        for query in queries
    ]

    if OFFICIAL_DISCOVERY_ENABLED:
        query_specs.extend(
            (
                "OFFICIAL_DISCOVERY",
                query,
            )
            for query in OFFICIAL_DISCOVERY_QUERIES[
                :OFFICIAL_DISCOVERY_QUERY_LIMIT
            ]
        )

    async with httpx.AsyncClient(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/120 Safari/537.36"
            )
        }
    ) as client:
        tasks = [
            fetch_feed(client, query)
            for _, query in query_specs
        ]
        results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

    dedup = {}

    for (channel, query), result in zip(
        query_specs,
        results,
    ):
        if isinstance(result, Exception):
            print(
                "Feed error:",
                channel,
                repr(result),
            )
            continue

        for article in result:
            article["discovery_channel"] = channel
            annotate_official_source(article)

            # Recalculate after official-source annotation.
            article["ca_score"] = corporate_action_score(article)
            article["information_score"] = article["ca_score"]

            key = article_key(article["title"], article["link"])

            if key not in dedup:
                article["key"] = key
                dedup[key] = article
                continue

            existing = dedup[key]

            # Preserve the stronger official metadata when the same URL/title
            # was found from both normal and official discovery queries.
            if official_source_rank(article) > official_source_rank(existing):
                article["key"] = key
                dedup[key] = article

    articles = list(dedup.values())

    # Reconnect ticker-less disclosures through learned issuer aliases.
    propagate_tickers_by_issuer_alias(articles)

    # V6.6.2: ticker/issuer recovery can change role/geo confidence.
    for article in articles:
        apply_article_integrity_guards(article)

    # V6.6.1: retain a verified official reference when the live
    # official feed is temporarily empty.
    attach_verified_official_refs(articles)

    if INDONESIA_PRIORITY:
        articles.sort(
            key=lambda x: (
                official_source_rank(x),
                1 if x["geo"].startswith("INDONESIA") else 0,
                PRIORITY_RANK.get(
                    x.get("urgency", x.get("priority", "LOW")),
                    1,
                ),
                x["published_dt"]
                or datetime.min.replace(tzinfo=timezone.utc),
                x["ca_score"],
            ),
            reverse=True,
        )
    else:
        articles.sort(
            key=lambda x: (
                official_source_rank(x),
                PRIORITY_RANK.get(
                    x.get("urgency", x.get("priority", "LOW")),
                    1,
                ),
                x["published_dt"]
                or datetime.min.replace(tzinfo=timezone.utc),
                x["ca_score"],
            ),
            reverse=True,
        )

    return articles


# ============================================================
# ALERT FORMAT
# ============================================================

def detail_lines(article):
    event = article["event_type"]
    d = article["details"]
    lines = []

    if d["ticker"]:
        lines.append(
            f"📈 <b>Ticker:</b> {html.escape(d['ticker'])}"
        )

    lines.append(
        f"🚦 <b>Status:</b> {html.escape(article['stage'])}"
    )
    lines.append(
        f"⚡ <b>Urgency:</b> {html.escape(priority_badge(article.get('urgency', 'LOW')))}"
    )
    lines.append(
        f"🧩 <b>Context:</b> "
        f"{html.escape(context_badge(article.get('context', 'ACTIVE EVENT')))}"
    )

    if event == "IPO":
        if article.get("ipo_class"):
            lines.append(
                f"🧭 <b>IPO Class:</b> "
                f"{html.escape(ipo_class_badge(article['ipo_class']))}"
            )

        if d["price_range"]:
            lines.append(
                f"💵 <b>Range harga:</b> "
                f"{html.escape(d['price_range'])}"
            )

        if d["share_count"]:
            lines.append(
                f"📦 <b>Saham ditawarkan:</b> "
                f"{html.escape(d['share_count'])}"
            )

        if d["percentages"]:
            lines.append(
                f"📊 <b>Porsi saham:</b> "
                f"{format_pct(d['percentages'][0])}"
            )

        if d["money"]:
            lines.append(
                f"💰 <b>Dana/Nilai:</b> "
                f"{html.escape(d['money'][0])}"
            )

    elif event == "RIGHTS ISSUE":
        if d["ratio"]:
            lines.append(
                f"⚖️ <b>Rasio HMETD:</b> "
                f"{html.escape(d['ratio'])}"
            )

        if d["execution_price"]:
            lines.append(
                f"💵 <b>Harga pelaksanaan:</b> "
                f"{html.escape(d['execution_price'])}"
            )

        if d["share_count"]:
            lines.append(
                f"📦 <b>Saham baru:</b> "
                f"{html.escape(d['share_count'])}"
            )

        if d["money"]:
            lines.append(
                f"💰 <b>Nilai/Dana:</b> "
                f"{html.escape(d['money'][0])}"
            )

        if d["standby_buyer"]:
            lines.append(
                f"🧍 <b>Standby buyer:</b> "
                f"{html.escape(d['standby_buyer'])}"
            )

    else:
        role_meta = d.get("role_meta") or {}

        if d["acquirer"]:
            lines.append(
                f"🏢 <b>Acquirer:</b> "
                f"{html.escape(d['acquirer'])}"
            )
        elif role_meta.get("acquirer_suppressed"):
            lines.append(
                "🤝 <b>Acquirer:</b> ⚪ belum terkonfirmasi"
            )

        if d["target"]:
            lines.append(
                f"🎯 <b>Target:</b> "
                f"{html.escape(d['target'])}"
            )
        elif role_meta.get("target_suppressed"):
            lines.append(
                "🎯 <b>Target:</b> ⚪ belum terkonfirmasi"
            )

        if (
            role_meta.get("acquirer_suppressed")
            or role_meta.get("target_suppressed")
        ):
            lines.append(
                "🛡️ <b>Role Guard:</b> kandidat headline ber-confidence rendah ditahan."
            )

        if d["percentages"]:
            lines.append(
                f"📊 <b>Stake:</b> "
                f"{format_pct(d['percentages'][0])}"
            )

        if d["money"]:
            lines.append(
                f"💰 <b>Nilai transaksi:</b> "
                f"{html.escape(d['money'][0])}"
            )

        low = article["title"].lower()

        if (
            "pengendali baru" in low
            or "perubahan pengendali" in low
            or article["event_type"] == "TENDER OFFER"
        ):
            lines.append(
                "🔁 <b>Perubahan pengendali:</b> TERINDIKASI"
            )

    return lines




def deep_extraction_lines(article):
    status = article.get("deep_status")
    if not status:
        return []

    lines = [
        f"🔬 <b>Deep Extraction:</b> "
        f"{html.escape(deep_status_badge(status))}"
    ]

    resolver_status = article.get("resolver_status")
    if resolver_status:
        lines.append(
            f"🧭 <b>Source Resolver:</b> "
            f"{html.escape(resolver_status_badge(resolver_status))}"
        )

    publisher_debug = article.get(
        "publisher_debug",
        {},
    )

    if publisher_debug.get("status"):
        lines.append(
            f"🏢 <b>Publisher Direct:</b> "
            f"✅ {html.escape(str(publisher_debug.get('domain', 'FOUND')))}"
        )

    decoder_method = article.get("decoder_method")
    if decoder_method:
        lines.append(
            f"🔑 <b>Google Decoder:</b> "
            f"{html.escape(decoder_method)}"
        )

    source_url = article.get("source_url")
    if source_url:
        host = _host(source_url)
        if host:
            lines.append(
                f"🌐 <b>Resolved Source:</b> {html.escape(host)}"
            )

    added = article.get("deep_fields_added", [])
    if added:
        friendly = {
            "ratio": "rasio HMETD",
            "execution_price": "harga rights",
            "price_range": "range IPO",
            "ipo_single_price": "harga IPO",
            "tender_price": "harga tender",
            "share_count": "jumlah saham",
            "standby_buyer": "standby buyer",
            "underwriter": "underwriter",
            "use_of_funds": "use of funds",
            "money": "nilai transaksi",
            "percentages": "persentase",
            "ticker": "ticker",
            "schedule": "jadwal",
        }
        labels = [friendly.get(x, x) for x in added[:8]]
        lines.append(
            f"➕ <b>Detail baru:</b> "
            f"{html.escape(', '.join(labels))}"
        )

    return lines


def schedule_lines(article):
    schedule = article.get("details", {}).get("schedule", {})
    if not schedule:
        return []

    labels = dict(LIFECYCLE_SCHEDULE_LABELS)

    return [
        f"🗓 <b>{labels.get(k, k)}:</b> {html.escape(v)}"
        for k, v in schedule.items()
        if v
    ]


def market_data_lines(article):
    market = article.get("market_data")

    if not market:
        return []

    lines = []

    if market.get("last_price") is not None:
        lines.append(
            f"📍 <b>Harga pasar:</b> "
            f"{format_price(market['last_price'])}"
        )

    if market.get("change_pct") is not None:
        lines.append(
            f"📊 <b>Perubahan harian:</b> "
            f"{market['change_pct']:+.2f}%"
        )

    return lines


def decision_support_lines(article):
    event = article["event_type"]
    m = article.get("decision_metrics") or {}
    d = article["details"]

    lines = [
        f"🎛 <b>Monitoring Signal:</b> "
        f"{html.escape(signal_badge(article.get('monitoring_signal', 'WATCH')))}"
    ]

    for reason in article.get("monitoring_reasons", [])[:3]:
        lines.append(
            f"   • {html.escape(reason)}"
        )

    if event == "RIGHTS ISSUE":
        if m.get("discount_pct") is not None:
            lines.append(
                f"🏷 <b>Discount Rights vs Market:</b> "
                f"{m['discount_pct']:.2f}%"
            )

        if m.get("terp") is not None:
            lines.append(
                f"🧮 <b>TERP:</b> "
                f"{format_price(m['terp'])}"
            )

        if m.get("dilution_pct") is not None:
            lines.append(
                f"📉 <b>Dilusi teoritis:</b> "
                f"{m['dilution_pct']:.2f}%"
            )

        if m.get("right_value") is not None:
            lines.append(
                f"💎 <b>Nilai teoritis 1 HMETD:</b> "
                f"{format_price(m['right_value'])}"
            )

        if m.get("redeem_cost_for_lots") is not None:
            lines.append(
                f"💳 <b>Estimasi dana tebus {DECISION_LOTS} lot lama:</b> "
                f"{format_rupiah_number(m['redeem_cost_for_lots'])}"
            )

    elif event == "IPO":
        if m.get("midpoint_price") is not None:
            lines.append(
                f"💵 <b>Midpoint harga:</b> "
                f"{format_price(m['midpoint_price'])}"
            )

        if m.get("estimated_offer_value") is not None:
            lines.append(
                f"💰 <b>Estimasi nilai penawaran:</b> "
                f"{format_rupiah_number(m['estimated_offer_value'])}"
            )

        if m.get("implied_market_cap") is not None:
            lines.append(
                f"🏦 <b>Estimasi implied market cap:</b> "
                f"{format_rupiah_number(m['implied_market_cap'])}"
            )

        if m.get("underwriter"):
            lines.append(
                f"🏢 <b>Underwriter:</b> "
                f"{html.escape(m['underwriter'])}"
            )

        if m.get("use_of_funds"):
            lines.append(
                f"🧾 <b>Use of funds:</b> "
                f"{html.escape(', '.join(m['use_of_funds']))}"
            )

    else:
        if d.get("tender_price"):
            lines.append(
                f"💵 <b>Harga tender:</b> "
                f"{html.escape(d['tender_price'])}"
            )

        if m.get("tender_premium_pct") is not None:
            premium = m["tender_premium_pct"]
            label = "premium" if premium >= 0 else "discount"
            lines.append(
                f"⚖️ <b>Tender {label} vs market:</b> "
                f"{premium:+.2f}%"
            )

    return lines


def format_alert(article):
    apply_article_integrity_guards(article)

    title = html.escape(article["title"])
    source = html.escape(article["source"])
    published = html.escape(article["published"])
    evt = html.escape(article["event_type"])
    geo = html.escape(article["geo"])
    link = html.escape(article.get("source_url") or article["link"], quote=True)

    family = html.escape(alert_family(article["event_type"]))
    icon = alert_icon(article["event_type"])

    score = article["ca_score"]
    label = score_label(score)

    detail_text = "\n".join(detail_lines(article))

    if article["event_type"] == "IPO":
        watch = (
            "🔎 <b>Pantau:</b> harga final, bookbuilding, "
            "underwriter, valuasi, penggunaan dana, "
            "dan oversubscription."
        )

    elif article["event_type"] == "RIGHTS ISSUE":
        watch = (
            "🔎 <b>Pantau:</b> harga pelaksanaan, rasio HMETD, "
            "cum/ex-right, standby buyer, penggunaan dana, "
            "dan potensi dilusi."
        )

    else:
        watch = (
            "🔎 <b>Pantau:</b> pembeli, target, stake, "
            "nilai transaksi, sumber pendanaan, "
            "perubahan pengendali dan tender wajib."
        )

    return (
        f"{icon} <b>{family} ALERT</b>\n\n"
        f"🏷 <b>Jenis:</b> {evt}\n"
        f"🌏 <b>Kategori:</b> {geo}\n"
        + "\n".join(official_reference_lines(article))
        + "\n"
        + (
            "\n".join(ticker_recovery_lines(article))
            + "\n"
            if ticker_recovery_lines(article)
            else ""
        )
        + (
            "\n".join(issuer_resolution_lines(article))
            + "\n"
            if issuer_resolution_lines(article)
            else ""
        )
        + (
            "\n".join(multisource_issuer_lines(article))
            + "\n"
            if multisource_issuer_lines(article)
            else ""
        )
        + (
            "\n".join(money_guard_lines(article))
            + "\n"
            if money_guard_lines(article)
            else ""
        )
        + (
            "\n".join(lifecycle_lines(article)) + "\n"
            if lifecycle_lines(article)
            else ""
        )
        + f"{detail_text}\n"
        + (
            "\n".join(deep_extraction_lines(article)) + "\n"
            if deep_extraction_lines(article)
            else ""
        )
        + (
            "\n".join(schedule_lines(article)) + "\n"
            if schedule_lines(article)
            else ""
        )
        + (
            "\n".join(market_data_lines(article)) + "\n"
            if market_data_lines(article)
            else ""
        )
        + "\n"
        + "\n".join(decision_support_lines(article))
        + "\n\n"
        f"📰 <b>Berita:</b> {title}\n"
        f"🏢 <b>Sumber:</b> {source}\n"
        f"🕒 <b>Publikasi:</b> {published}\n\n"
        f"🎯 <b>Information Score:</b> {score}/100\n"
        f"📌 <b>Information Quality:</b> {label}\n"
        f"🧠 <b>Catalyst:</b> {html.escape(catalyst_badge(article.get('catalyst', 'NEUTRAL')))}\n"
        + "".join(
            f"   • {html.escape(reason)}\n"
            for reason in article.get("catalyst_reasons", [])[:3]
        )
        + f"\n{watch}\n\n"
        f'🔗 <a href="{link}">Buka berita</a>\n\n'
        "⚠️ <i>Decision Support adalah alat triase monitoring, bukan rekomendasi beli/jual. V6.6.2 memakai Entity Role Guard + Indonesia Classification Guard + Event Lifecycle + Timeline + Reliability Guard + Verified Official Cache + Multi-Source Issuer Resolver + Official Source Priority + V5.4 Publisher Direct + Deep Extraction untuk membaca halaman publik sumber jika tersedia; halaman login/paywall tidak dibypass. "
        "Verifikasi prospektus, keterbukaan BEI/OJK, dan dokumen "
        "emiten sebelum mengambil keputusan investasi.</i>"
    )


# ============================================================
# TELEGRAM
# ============================================================

async def tg_call(method, payload):
    last_exc = None

    async with httpx.AsyncClient() as client:
        for attempt in range(TELEGRAM_RETRY_ATTEMPTS):
            try:
                response = await client.post(
                    f"{TG_BASE}/{method}",
                    json=payload,
                    timeout=35.0,
                )
                response.raise_for_status()

                data = response.json()

                if not data.get("ok"):
                    raise RuntimeError(data)

                return data["result"]

            except (
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.RemoteProtocolError,
                httpx.HTTPStatusError,
            ) as exc:
                last_exc = exc
                retryable = True

                if isinstance(exc, httpx.HTTPStatusError):
                    status = exc.response.status_code
                    retryable = (
                        status == 429
                        or 500 <= status <= 599
                    )

                if (
                    not retryable
                    or attempt >= TELEGRAM_RETRY_ATTEMPTS - 1
                ):
                    raise

                delay = HTTP_RETRY_BASE_SECONDS * (2 ** attempt)

                if (
                    isinstance(exc, httpx.HTTPStatusError)
                    and exc.response.status_code == 429
                ):
                    try:
                        body = exc.response.json()
                        retry_after = float(
                            ((body.get("parameters") or {}).get("retry_after"))
                            or exc.response.headers.get("Retry-After", "0")
                            or 0
                        )
                        delay = max(
                            delay,
                            min(20.0, retry_after),
                        )
                    except Exception:
                        pass

                await asyncio.sleep(min(20.0, delay))

    if last_exc:
        raise last_exc

    raise RuntimeError("Telegram request gagal tanpa detail.")


def _telegram_plain_text(value):
    text = re.sub(
        r"<br\s*/?>",
        "\n",
        str(value or ""),
        flags=re.I,
    )
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text)


async def send_message(chat_id, text):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        return await tg_call(
            "sendMessage",
            payload,
        )

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 400:
            return await tg_call(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": _telegram_plain_text(text)[:4000],
                    "disable_web_page_preview": True,
                },
            )
        raise


HELP_TEXT = """
<b>📊 Kabar Saham Intelligence V6.6.2 / V5.4 Core</b>

Perintah:
/start — aktifkan alert otomatis
/decision — Decision Board
/menu — Control Center (Command Bridge)
/syncmenu — sinkronkan Native Telegram Menu (Command Bridge)
/health — cek kesehatan runtime GitHub Actions
/today — milestone corporate action hari ini (Command Bridge)
/recent — perubahan lifecycle terbaru (Command Bridge)
/news24h — berita corporate action 24 jam terakhir
/watch TICKER [HIGH|WATCH|NORMAL] — tambah Smart Watchlist
/unwatch TICKER — hapus dari Smart Watchlist
/watchlist — lihat Smart Watchlist
/watchboard — Smart Watch Dashboard (Command Bridge)
/timeline TICKER — lifecycle & riwayat corporate action
/official TICKER — cek sumber resmi IDX/e-IPO/KSEI/OJK
/analyze TICKER — analisis lengkap
/deep TICKER — deep article extraction
/publisherdebug TICKER — debug direct publisher resolver
/decode TICKER — Google News decoder
/protocoldebug TICKER — debug dynamic Google protocol
/decoderdebug TICKER — debug static Google parser
/resolve TICKER — full source resolver diagnostics
/market TICKER — harga pasar terakhir
/latest — corporate action terbaru
/today — berita 24 jam terakhir
/high — Urgency HIGH
/active — event aktif
/actionable — IPO ACTIONABLE
/pipeline — IPO PIPELINE
/ma — M&A / takeover
/ipo — IPO
/rights — Rights Issue / HMETD
/status — status bot
/help — bantuan

V6.6.2 Entity Role + Indonesia Classification Guard:\n• headline fragments are rejected as Acquirer/Target\n• speculative actor candidates are suppressed until sufficiently confirmed\n• recovered IDX ticker + local issuer evidence cannot remain GLOBAL\n\nV6.2.1 Ticker Recovery + Issuer Resolver:\n• exact ticker → title/snippet → targeted search fallback\n• issuer alias propagation reconnects ticker-less disclosures\n• official lookup uses ticker + issuer name when available\n\nV6.2 Official Source Priority:
• IDX/BEI, e-IPO, KSEI, OJK source classification
• Official discovery feed runs in parallel
• Official events receive ranking/score priority
• /official TICKER for on-demand official-source check

V5.4 Publisher Direct Resolver:
• Source name → publisher domain mapping
• Publisher internal-search fallback
• Exact-title site search
• Ticker + event + transaction-value search
• Title/ticker/event/date validation
• Publisher Direct runs BEFORE Google decoder
• Google V5.3.2 stack remains fallback
""".strip()


async def send_filtered(chat_id, family=None, today_only=False, high_only=False, ipo_class=None, active_only=False):
    articles = await fetch_all_articles()

    if today_only:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        articles = [
            x for x in articles
            if x["published_dt"] and x["published_dt"] >= cutoff
        ]

    if high_only:
        articles = [
            x for x in articles
            if x.get("urgency") == "HIGH"
            and x.get("context") != "MARKET PIPELINE"
        ]

    if ipo_class:
        articles = [
            x for x in articles
            if x.get("event_type") == "IPO"
            and x.get("ipo_class") == ipo_class
        ]

    if active_only:
        articles = [
            x for x in articles
            if x.get("context") != "MARKET PIPELINE"
        ]

    if family == "IPO":
        articles = [
            x for x in articles
            if x["event_type"] == "IPO"
        ]

    elif family == "RIGHTS":
        articles = [
            x for x in articles
            if x["event_type"] == "RIGHTS ISSUE"
        ]

    elif family == "MA":
        articles = [
            x for x in articles
            if x["event_type"] not in ("IPO", "RIGHTS ISSUE")
        ]

    top = articles[: CONFIG.get("latest_limit", 10)]

    if not top:
        await send_message(
            chat_id,
            "Belum ada berita terbaru yang lolos filter V6.0.",
        )
        return

    for idx, article in enumerate(top):
        await enrich_decision_support(
            article,
            use_market=(idx < MARKET_ENRICH_LIMIT),
            use_deep=(idx < DEEP_EXTRACT_LIMIT),
        )

        await send_message(
            chat_id,
            format_alert(article),
        )



async def send_decision_board(chat_id):
    articles = await fetch_all_articles()

    active = [
        x for x in articles
        if x.get("context") != "MARKET PIPELINE"
    ][:8]

    if not active:
        await send_message(
            chat_id,
            "Belum ada event aktif untuk Decision Board.",
        )
        return

    for idx, article in enumerate(active):
        await enrich_decision_support(
            article,
            use_market=(idx < MARKET_ENRICH_LIMIT),
            use_deep=(idx < DEEP_EXTRACT_LIMIT),
        )

    rank = {
        "HIGH ATTENTION": 3,
        "WATCH": 2,
        "IGNORE": 1,
    }

    active.sort(
        key=lambda x: (
            rank.get(x.get("monitoring_signal"), 0),
            x.get("information_score", x.get("ca_score", 0)),
        ),
        reverse=True,
    )

    await send_message(
        chat_id,
        "🧠 <b>V5 DECISION BOARD</b>\n"
        "Urutan berdasarkan tingkat perhatian monitoring, bukan rekomendasi investasi.",
    )

    for article in active[:5]:
        await send_message(
            chat_id,
            format_alert(article),
        )


async def send_market_quote(chat_id, ticker):
    ticker = ticker.upper()

    if not re.fullmatch(r"[A-Z]{4}", ticker):
        await send_message(
            chat_id,
            "Format ticker harus 4 huruf, contoh: /market BBCA",
        )
        return

    if not YFINANCE_AVAILABLE:
        await send_message(
            chat_id,
            "⚠️ Modul yfinance belum terpasang. "
            "Jalankan: python -m pip install -r requirements_v5.txt",
        )
        return

    data = await get_market_data(ticker)

    if not data:
        await send_message(
            chat_id,
            f"Market data {ticker} belum berhasil diambil.",
        )
        return

    text = (
        f"📈 <b>MARKET DATA {ticker}</b>\n\n"
        f"💵 Harga terakhir: {format_price(data.get('last_price'))}\n"
    )

    if data.get("change_pct") is not None:
        text += f"📊 Perubahan: {data['change_pct']:+.2f}%\n"

    if data.get("market_date"):
        text += f"🗓 Data pasar: {html.escape(data['market_date'])}\n"

    text += (
        "\n⚠️ <i>Market data bersifat best-effort dan dapat tertunda. "
        "Verifikasi ke aplikasi broker/BEI sebelum mengambil keputusan.</i>"
    )

    await send_message(chat_id, text)




async def publisher_debug_ticker(
    chat_id,
    ticker,
):
    ticker = ticker.upper()

    if not re.fullmatch(
        r"[A-Z]{4}",
        ticker,
    ):
        await send_message(
            chat_id,
            (
                "Format: /publisherdebug TICKER "
                "— contoh /publisherdebug CBRE"
            ),
        )
        return

    articles = await fetch_all_articles()

    matches = [
        article
        for article in articles
        if article["details"].get(
            "ticker"
        ) == ticker
    ]

    if not matches:
        await send_message(
            chat_id,
            f"Belum ada corporate action {ticker}.",
        )
        return

    article = matches[0]

    async with httpx.AsyncClient(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/129 Safari/537.36"
            ),
            "Accept-Language": (
                "id-ID,id;q=0.9,en;q=0.7"
            ),
        },
        follow_redirects=True,
    ) as client:
        result = await resolve_publisher_direct(
            client,
            article,
        )

    text = (
        f"🏢 <b>PUBLISHER DEBUG {ticker}</b>\n\n"
        f"Status: "
        f"{'✅ MATCH FOUND' if result.get('status') else '⚪ NO CONFIDENT MATCH'}\n"
        f"Method: "
        f"{html.escape(str(result.get('method', 'UNKNOWN')))}\n"
        f"Source: "
        f"{html.escape(str(article.get('source', '—')))}\n"
        f"Domain Hint: "
        f"{html.escape(str(result.get('domain', '—')))}\n"
        f"Best Score: "
        f"{html.escape(str(result.get('best_score', '—')))}\n"
        f"Minimum Score: "
        f"{PUBLISHER_DIRECT_MIN_SCORE}\n"
        f"Cache Hit: "
        f"{'YES' if result.get('cache_hit') else 'NO'}\n"
    )

    if result.get("url"):
        text += (
            f"Publisher URL: "
            f"{html.escape(_host(result['url']))}\n"
        )

    attempts = result.get(
        "attempts",
        [],
    )

    if attempts:
        text += "\nSearch Attempts:\n"

        for item in attempts[:6]:
            text += (
                f"• "
                f"{html.escape(str(item.get('method', 'UNKNOWN')))}"
                f" — candidates "
                f"{html.escape(str(item.get('count', 0)))}"
                f"\n"
            )

    candidates = result.get(
        "candidates",
        [],
    )

    if candidates:
        text += "\nTop Candidates:\n"

        for item in candidates[:5]:
            text += (
                f"• "
                f"{html.escape(str(item.get('host', '—')))}"
                f" — score "
                f"{html.escape(str(item.get('score', '—')))}"
                f" — "
                f"{html.escape(str(item.get('origin', '—')))}"
                f"\n"
            )

    queries = _publisher_search_queries(
        article
    )

    if queries:
        text += "\nQuery Modes:\n"

        for mode, _ in queries[:4]:
            text += (
                f"• {html.escape(mode)}\n"
            )

    text += (
        "\n<i>Query lengkap tidak ditampilkan "
        "untuk menjaga output tetap ringkas.</i>"
    )

    await send_message(
        chat_id,
        text,
    )


async def protocol_debug_ticker(
    chat_id,
    ticker,
):
    ticker = ticker.upper()

    if not re.fullmatch(
        r"[A-Z]{4}",
        ticker,
    ):
        await send_message(
            chat_id,
            (
                "Format: /protocoldebug TICKER "
                "— contoh /protocoldebug CBRE"
            ),
        )
        return

    articles = await fetch_all_articles()

    matches = [
        article
        for article in articles
        if article["details"].get(
            "ticker"
        ) == ticker
    ]

    if not matches:
        await send_message(
            chat_id,
            f"Belum ada corporate action {ticker}.",
        )
        return

    article = matches[0]

    async with httpx.AsyncClient(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/129 Safari/537.36"
            ),
        },
        follow_redirects=True,
    ) as client:
        result = (
            await decode_google_news_dynamic(
                client,
                article.get("link", ""),
                source=article.get(
                    "source",
                    "",
                ),
            )
        )

    debug = result.get(
        "protocol_debug",
        {},
    )

    attempts = debug.get(
        "params_attempts",
        [],
    )

    text = (
        f"🧬 <b>PROTOCOL DEBUG {ticker}</b>\n\n"
        f"Status: "
        f"{'✅ DYNAMIC URL FOUND' if result.get('status') else '⚪ DYNAMIC NOT COMPLETE'}\n"
        f"Method: "
        f"{html.escape(result.get('method', 'UNKNOWN'))}\n"
        f"Params Found: "
        f"{'YES' if debug.get('params_found') else 'NO'}\n"
        f"Params Mode: "
        f"{html.escape(str(debug.get('params_method', '—')))}\n"
        f"Selector: "
        f"{html.escape(str(debug.get('params_selector', '—')))}\n"
        f"Signature Length: "
        f"{html.escape(str(debug.get('signature_length', '—')))}\n"
        f"Timestamp: "
        f"{html.escape(str(debug.get('timestamp', '—')))}\n"
        f"Batch HTTP: "
        f"{html.escape(str(debug.get('http_status', '—')))}\n"
        f"Response Size: "
        f"{debug.get('response_bytes', 0):,} bytes\n"
        f"Response Parser: "
        f"{html.escape(str(debug.get('response_parser', 'NONE')))}\n"
        f"Structured Parser: "
        f"{'YES' if debug.get('structured_parser') else 'NO'}\n"
        f"Multi Parser: "
        f"{'YES' if debug.get('multi_parser') else 'NO'}\n"
    )

    if attempts:
        text += (
            "\nParameter Fetch Attempts:\n"
        )

        for item in attempts[:5]:
            text += (
                f"• "
                f"{html.escape(str(item.get('mode', 'UNKNOWN')))}"
                f" — HTTP "
                f"{html.escape(str(item.get('http_status', '—')))}"
                f" — Params "
                f"{'YES' if item.get('params_found') else 'NO'}"
                f"\n"
            )

    if result.get("decoded_url"):
        text += (
            "\nPublisher: "
            + html.escape(
                _host(
                    result[
                        "decoded_url"
                    ]
                )
            )
        )

    if result.get("message"):
        text += (
            "\n\nInfo: "
            + html.escape(
                result["message"]
            )
        )

    text += (
        "\n\n<i>Signature tidak ditampilkan "
        "penuh di Telegram.</i>"
    )

    await send_message(
        chat_id,
        text,
    )


async def decoder_debug_ticker(
    chat_id,
    ticker,
):
    ticker = ticker.upper()

    if not DECODER_DEBUG_ENABLED:
        await send_message(
            chat_id,
            "Decoder debug dinonaktifkan di .env.",
        )
        return

    if not re.fullmatch(r"[A-Z]{4}", ticker):
        await send_message(
            chat_id,
            (
                "Format: /decoderdebug TICKER "
                "— contoh /decoderdebug CBRE"
            ),
        )
        return

    articles = await fetch_all_articles()

    matches = [
        article
        for article in articles
        if article["details"].get("ticker")
        == ticker
    ]

    if not matches:
        await send_message(
            chat_id,
            f"Belum ada corporate action {ticker}.",
        )
        return

    article = matches[0]
    source_url = article.get("link", "")

    legacy = decode_google_news_legacy(
        source_url
    )
    token = legacy.get("token")

    if not token:
        await send_message(
            chat_id,
            (
                f"🧪 <b>DECODER DEBUG {ticker}</b>\n\n"
                "Token Google News tidak ditemukan."
            ),
        )
        return

    async with httpx.AsyncClient(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/122 Safari/537.36"
            ),
        },
        follow_redirects=True,
    ) as client:
        batch = await decode_google_news_batch(
            client,
            token,
            source=article.get(
                "source",
                "",
            ),
        )

    candidates = batch.get(
        "url_candidates",
        [],
    )

    domains = []
    seen = set()

    for url in candidates:
        host = _host(url)

        if host and host not in seen:
            seen.add(host)
            domains.append(host)

    best = (
        batch.get("decoded_url")
        or (
            candidates[0]
            if candidates
            else None
        )
    )

    debug_text = (
        f"🧪 <b>DECODER DEBUG {ticker}</b>\n\n"
        f"Status: "
        f"{'✅ URL FOUND' if batch.get('status') else '⚪ NO FINAL URL'}\n"
        f"Method: "
        f"{html.escape(batch.get('method', 'UNKNOWN'))}\n"
        f"HTTP Status: "
        f"{html.escape(str(batch.get('http_status', '—')))}\n"
        f"Response Size: "
        f"{batch.get('response_bytes', 0):,} bytes\n"
        f"RPC Fbv4je: "
        f"{'YES' if batch.get('rpc_found') else 'NO'}\n"
        f"garturlres: "
        f"{'YES' if batch.get('garturlres_found') else 'NO'}\n"
        f"JSON Objects: "
        f"{batch.get('json_objects', 0)}\n"
        f"Nested Strings: "
        f"{batch.get('nested_strings', 0)}\n"
        f"URL Candidates: "
        f"{batch.get('candidate_count', 0)}\n"
        f"Parser: "
        f"{html.escape(batch.get('parser_method', 'NONE'))}\n"
    )

    if best:
        debug_text += (
            f"Best Candidate: "
            f"{html.escape(_host(best))}\n"
        )

    if domains:
        debug_text += (
            "\nTop Domains:\n"
            + "\n".join(
                f"• {html.escape(host)}"
                for host in domains[:5]
            )
        )

    if batch.get("message"):
        debug_text += (
            "\n\nInfo: "
            + html.escape(
                batch.get("message")
            )
        )

    debug_text += (
        "\n\n<i>Response mentah Google "
        "tidak dikirim ke Telegram.</i>"
    )

    await send_message(
        chat_id,
        debug_text,
    )


async def decode_ticker_google_url(chat_id, ticker):
    ticker = ticker.upper()

    if not re.fullmatch(r"[A-Z]{4}", ticker):
        await send_message(
            chat_id,
            "Format: /decode TICKER — contoh /decode CBRE",
        )
        return

    articles = await fetch_all_articles()
    matches = [
        x for x in articles
        if x["details"].get("ticker") == ticker
    ]

    if not matches:
        await send_message(
            chat_id,
            f"Belum ada corporate action {ticker} dalam "
            f"{RECENT_DAYS} hari terakhir.",
        )
        return

    article = matches[0]

    async with httpx.AsyncClient(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/122 Safari/537.36"
            ),
        },
        follow_redirects=True,
    ) as client:
        result = await decode_google_news_url_core(
            client,
            article.get("link", ""),
            source=article.get(
                "source",
                "",
            ),
        )

    if result.get("status"):
        decoded_url = result.get("decoded_url", "")
        method = result.get("method", "UNKNOWN")

        await send_message(
            chat_id,
            (
                f"🔑 <b>GOOGLE NEWS DECODER {ticker}</b>\n\n"
                f"Status: ✅ BERHASIL\n"
                f"Method: {html.escape(method)}\n"
                f"Publisher: {html.escape(_host(decoded_url))}\n\n"
                f'<a href="{html.escape(decoded_url, quote=True)}">'
                f"Buka URL publisher</a>"
            ),
        )
        return

    await send_message(
        chat_id,
        (
            f"🔑 <b>GOOGLE NEWS DECODER {ticker}</b>\n\n"
            f"Status: ⚪ BELUM BERHASIL\n"
            f"Method: {html.escape(result.get('method', 'FAILED'))}\n"
            f"Info: {html.escape(result.get('message', 'Tidak ada detail.'))}"
        ),
    )


async def resolve_ticker_source(chat_id, ticker):
    ticker = ticker.upper()

    if not re.fullmatch(r"[A-Z]{4}", ticker):
        await send_message(
            chat_id,
            "Format: /resolve TICKER — contoh /resolve CBRE",
        )
        return

    articles = await fetch_all_articles()
    matches = [
        x for x in articles
        if x["details"].get("ticker") == ticker
    ]

    if not matches:
        await send_message(
            chat_id,
            f"Belum ada corporate action {ticker} dalam "
            f"{RECENT_DAYS} hari terakhir.",
        )
        return

    article = matches[0]

    await send_message(
        chat_id,
        f"🧭 Mencoba resolve sumber asli {ticker}…",
    )

    await deep_enrich_article(article)

    resolver_status = article.get(
        "resolver_status",
        "FAILED",
    )

    source_url = article.get("source_url")
    deep_status = article.get(
        "deep_status",
        "FAILED",
    )

    text = (
        f"🧭 <b>SOURCE RESOLVER {ticker}</b>\n\n"
        f"Status: {html.escape(resolver_status_badge(resolver_status))}\n"
        f"Deep Extraction: {html.escape(deep_status_badge(deep_status))}\n"
    )

    if source_url:
        text += (
            f"Publisher: {html.escape(_host(source_url))}\n"
            f'<a href="{html.escape(source_url, quote=True)}">'
            f"Buka publisher</a>\n"
        )

    attempts = article.get(
        "resolver_attempts",
        [],
    )

    if attempts:
        text += (
            "\nResolver attempts:\n"
            + "\n".join(
                f"• {html.escape(x)}"
                for x in attempts[:8]
            )
        )

    await send_message(
        chat_id,
        text,
    )


async def prepare_ticker_analysis(ticker, *, use_deep=True):
    ticker = str(ticker or "").upper().strip()

    if not re.fullmatch(r"[A-Z]{4}", ticker):
        return {
            "ticker": ticker,
            "article": None,
            "recovery": {
                "method": "INVALID_TICKER",
                "articles": [],
                "aliases": [],
            },
        }

    articles = await fetch_all_articles()
    recovery = await recover_ticker_context(
        ticker,
        seed_articles=articles,
    )
    matches = recovery.get("articles", [])

    if not matches:
        return {
            "ticker": ticker,
            "article": None,
            "recovery": recovery,
            "articles": articles,
        }

    combined_articles = list(articles) + list(matches)
    propagate_tickers_by_issuer_alias(combined_articles)
    matches = find_ticker_matches(combined_articles, ticker)

    grouped = group_event_articles(matches)
    grouped.sort(
        key=lambda g: (
            g.get("official_rank", 0),
            _primary_article_rank(g["primary"]),
        ),
        reverse=True,
    )

    if not grouped:
        return {
            "ticker": ticker,
            "article": None,
            "recovery": recovery,
            "articles": articles,
        }

    article = grouped[0]["primary"]

    if recovery.get("method") != "CURRENT_FEED":
        article["ticker_recovered"] = True
        article["ticker_recovery_source"] = recovery.get(
            "method",
            "TARGETED_SEARCH",
        )

    if use_deep and DEEP_EXTRACTION_ENABLED:
        await deep_enrich_article(article)

    issuer_aliases = []
    issuer_aliases.extend(recovery.get("aliases", []) or [])
    issuer_aliases.extend(article.get("issuer_aliases", []) or [])
    issuer_aliases.extend(get_ticker_aliases(ticker))
    issuer_aliases = _dedup_issuer_aliases(issuer_aliases)

    if (
        not issuer_aliases
        and MULTI_SOURCE_ISSUER_RESOLVER_ENABLED
    ):
        issuer_resolution = await resolve_multisource_issuer_alias(
            ticker,
            reference_article=article,
            seed_articles=articles,
        )
        issuer_aliases.extend(
            issuer_resolution.get("aliases", [])
        )

    issuer_aliases = _dedup_issuer_aliases(issuer_aliases)

    if issuer_aliases:
        article["issuer_aliases"] = issuer_aliases
        article["issuer_name"] = issuer_aliases[0]
        register_ticker_aliases(ticker, issuer_aliases)
        propagate_tickers_by_issuer_alias(combined_articles)

    official_candidates = correlate_official_candidates(
        articles,
        ticker,
        issuer_aliases,
        reference_article=article,
    )

    if OFFICIAL_ON_DEMAND_ENABLED:
        searched = await search_official_ticker_articles(
            ticker,
            issuer_aliases=issuer_aliases,
        )
        official_candidates.extend(
            correlate_official_candidates(
                searched,
                ticker,
                issuer_aliases,
                reference_article=article,
            )
        )

    if official_candidates:
        attach_official_reference(
            article,
            [article] + official_candidates,
        )
        register_verified_official_candidates(
            ticker,
            official_candidates,
            issuer_aliases=issuer_aliases,
        )
    else:
        cached_ref = verified_official_ref_for_article(article)
        if cached_ref:
            article["verified_official_ref"] = cached_ref

    await enrich_decision_support(
        article,
        use_deep=False,
    )

    return {
        "ticker": ticker,
        "article": article,
        "recovery": recovery,
        "articles": articles,
        "issuer_aliases": issuer_aliases,
        "official_candidates": official_candidates,
    }


async def analyze_ticker(chat_id, ticker):
    ticker = str(ticker or "").upper().strip()

    if not re.fullmatch(r"[A-Z]{4}", ticker):
        await send_message(
            chat_id,
            "Format: /analyze TICKER — contoh /analyze CBRE",
        )
        return None

    result = await prepare_ticker_analysis(
        ticker,
        use_deep=True,
    )
    article = result.get("article")

    if not article:
        await send_message(
            chat_id,
            (
                f"Belum ada corporate action {ticker} yang dapat direcover "
                f"dalam {RECENT_DAYS} hari terakhir.\n\n"
                "Recovery sudah mencoba exact ticker, title/snippet, "
                "targeted corporate-action search, dan issuer memory."
            ),
        )
        return None

    await send_message(
        chat_id,
        format_alert(article),
    )

    return article


async def handle_update(update):
    message = update.get("message") or {}
    chat = message.get("chat") or {}

    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return

    parts = text.split()
    command = parts[0].split("@")[0].lower()
    args = parts[1:]

    if command == "/start":
        register_chat(chat_id)

        await send_message(
            chat_id,
            "✅ <b>Kabar Saham Intelligence V6.6.2 / V5.4 Core aktif.</b>\n\n"
            "Context awareness, post-event filter, IPO aggregate detection, dan participation-aware catalyst telah diaktifkan.\n\n"
            + HELP_TEXT,
        )

    elif command == "/help":
        await send_message(chat_id, HELP_TEXT)

    elif command == "/status":
        await send_message(
            chat_id,
            "🟢 <b>Bot aktif — V6.6.2 / V5.4 Core</b>\n"
            f"Monitoring: setiap {POLL_MINUTES} menit\n"
            f"Manual search: {RECENT_DAYS} hari terakhir\n"
            f"Auto alert: maksimal umur {AUTO_ALERT_HOURS} jam\n"
            f"Prioritas Indonesia: "
            f"{'YA' if INDONESIA_PRIORITY else 'TIDAK'}\n"
            f"Auto-alert minimum priority: {AUTO_ALERT_MIN_PRIORITY}\n"
            f"Official Source Priority: "
            f"{'ON' if OFFICIAL_SOURCE_PRIORITY_ENABLED else 'OFF'}\n"
            f"Official Discovery: "
            f"{'ON' if OFFICIAL_DISCOVERY_ENABLED else 'OFF'}\n"
            f"Ticker Recovery: "
            f"{'ON' if TICKER_RECOVERY_ENABLED else 'OFF'}\n"
            f"Issuer Alias Propagation: "
            f"{'ON' if ISSUER_ALIAS_PROPAGATION_ENABLED else 'OFF'}\n"
            f"Deep Issuer Resolver: {'ON' if DEEP_ISSUER_RESOLVER_ENABLED else 'OFF'}\n"
            f"Multi-Source Issuer: {'ON' if MULTI_SOURCE_ISSUER_RESOLVER_ENABLED else 'OFF'}\n"
            f"Market Issuer Lookup: {'ON' if MARKET_ISSUER_LOOKUP_ENABLED else 'OFF'}\n"
            f"Related Issuer Discovery: {'ON' if RELATED_ISSUER_DISCOVERY_ENABLED else 'OFF'}\n"
            f"Official Triangulation: {'ON' if OFFICIAL_ISSUER_TRIANGULATION_ENABLED else 'OFF'}\n"
            f"Verified Official Cache: {'ON' if VERIFIED_OFFICIAL_CACHE_ENABLED else 'OFF'}\n"
            f"Event Lifecycle: {'ON' if EVENT_LIFECYCLE_ENABLED else 'OFF'}\n"
            f"Timeline Deep: {'ON' if TIMELINE_DEEP_ENABLED else 'OFF'}\n"
            f"Timeline Noise Guard: {'ON' if TIMELINE_NOISE_GUARD_ENABLED else 'OFF'}\n"
            f"Timeline Timezone: {TIMELINE_TIMEZONE_NAME}\n"
            f"Smart Watchlist: {'ON' if SMART_WATCHLIST_ENABLED else 'OFF'}\n"
            f"Lifecycle Auto Alert: {'ON' if SMART_LIFECYCLE_ALERT_ENABLED else 'OFF'}\n"
            f"Milestone Alert: {'ON' if MILESTONE_ALERT_ENABLED else 'OFF'}\n"
            f"HTTP Retry: {HTTP_RETRY_ATTEMPTS}x\n"
            f"Telegram Retry: {TELEGRAM_RETRY_ATTEMPTS}x\n"
            f"Money Unit Guard: {'ON' if MONEY_UNIT_GUARD_ENABLED else 'OFF'}\n"
            f"Market data: "
            f"{'ON' if MARKET_DATA_ENABLED and YFINANCE_AVAILABLE else 'OFF'}\n"
            f"Market cache: {MARKET_CACHE_MINUTES} menit\n"
            f"Decision lots: {DECISION_LOTS} lot\n"
            f"Deep extraction: "
            f"{'ON' if DEEP_EXTRACTION_ENABLED and BS4_AVAILABLE else 'OFF'}\n"
            f"Deep limit: {DEEP_EXTRACT_LIMIT} artikel/command\n"
            f"Article cache: {ARTICLE_CACHE_MINUTES} menit\n"
            f"Source resolver: "
            f"{'ON' if SOURCE_RESOLVER_ENABLED else 'OFF'}\n"
            f"Search fallback: "
            f"{'ON' if RESOLVER_SEARCH_FALLBACK else 'OFF'}\n"
            f"Resolver cache: {RESOLVER_CACHE_MINUTES} menit\n"
            f"Google decoder: "
            f"{'ON' if GOOGLE_DECODER_ENABLED else 'OFF'}\n"
            f"Batch decoder: "
            f"{'ON' if GOOGLE_DECODER_BATCH_ENABLED else 'OFF'}\n"
            f"Decoder cache: {GOOGLE_DECODER_CACHE_MINUTES} menit\n"
            f"Decoder timeout: {GOOGLE_DECODER_TIMEOUT_SECONDS} detik\n"
            f"Decoder debug: "
            f"{'ON' if DECODER_DEBUG_ENABLED else 'OFF'}\n"
            f"Max response parse: "
            f"{DECODER_MAX_RESPONSE_CHARS:,} chars\n"
            f"Max URL candidates: "
            f"{DECODER_MAX_URL_CANDIDATES}\n"
            f"Dynamic protocol: "
            f"{'ON' if DYNAMIC_PROTOCOL_ENABLED else 'OFF'}\n"
            f"Dynamic params cache: "
            f"{DYNAMIC_PARAMS_CACHE_MINUTES} menit\n"
            f"Static fallback: "
            f"{'ON' if DYNAMIC_PROTOCOL_FALLBACK_STATIC else 'OFF'}\n"
            f"Publisher Direct: "
            f"{'ON' if PUBLISHER_DIRECT_ENABLED else 'OFF'}\n"
            f"Publisher min score: "
            f"{PUBLISHER_DIRECT_MIN_SCORE}\n"
            f"Publisher cache: "
            f"{PUBLISHER_DIRECT_CACHE_MINUTES} menit\n"
            f"Internal publisher search: "
            f"{'ON' if PUBLISHER_INTERNAL_SEARCH_ENABLED else 'OFF'}\n"
            f"Public site search: "
            f"{'ON' if PUBLISHER_PUBLIC_SEARCH_ENABLED else 'OFF'}\n"
            f"Query aktif: {len(CONFIG.get('queries', []))}",
        )

    elif command == "/latest":
        await send_message(
            chat_id,
            "🔎 Mencari corporate action V5.4 terbaru…",
        )
        await send_filtered(chat_id)

    elif command == "/today":
        await send_message(
            chat_id,
            "🕒 Mencari berita 24 jam terakhir…",
        )
        await send_filtered(
            chat_id,
            today_only=True,
        )

    elif command == "/high":
        await send_message(
            chat_id,
            "🔴 Mencari corporate action Urgency HIGH…",
        )
        await send_filtered(
            chat_id,
            high_only=True,
        )

    elif command == "/active":
        await send_message(
            chat_id,
            "🟢 Mencari corporate action ACTIVE terbaru…",
        )
        await send_filtered(
            chat_id,
            active_only=True,
        )

    elif command == "/actionable":
        await send_message(
            chat_id,
            "🔥 Mencari IPO ACTIONABLE terbaru…",
        )
        await send_filtered(
            chat_id,
            ipo_class="ACTIONABLE",
        )

    elif command == "/pipeline":
        await send_message(
            chat_id,
            "📰 Mencari IPO PIPELINE terbaru…",
        )
        await send_filtered(
            chat_id,
            ipo_class="PIPELINE",
        )

    elif command == "/decision":
        await send_decision_board(chat_id)

    elif command == "/official":
        if not args:
            await send_message(
                chat_id,
                "Gunakan /official TICKER — contoh /official DOOH",
            )
        else:
            await official_ticker(
                chat_id,
                args[0],
            )

    elif command == "/market":
        if not args:
            await send_message(
                chat_id,
                "Gunakan /market TICKER — contoh /market BBCA",
            )
        else:
            await send_market_quote(chat_id, args[0])

    elif command == "/analyze":
        if not args:
            await send_message(
                chat_id,
                "Gunakan /analyze TICKER — contoh /analyze CBRE",
            )
        else:
            await analyze_ticker(chat_id, args[0])

    elif command == "/deep":
        if not args:
            await send_message(
                chat_id,
                "Gunakan /deep TICKER — contoh /deep CBRE",
            )
        else:
            await analyze_ticker(chat_id, args[0])

    elif command == "/resolve":
        if not args:
            await send_message(
                chat_id,
                "Gunakan /resolve TICKER — contoh /resolve CBRE",
            )
        else:
            await resolve_ticker_source(chat_id, args[0])

    elif command == "/decode":
        if not args:
            await send_message(
                chat_id,
                "Gunakan /decode TICKER — contoh /decode CBRE",
            )
        else:
            await decode_ticker_google_url(chat_id, args[0])

    elif command == "/decoderdebug":
        if not args:
            await send_message(
                chat_id,
                (
                    "Gunakan /decoderdebug TICKER "
                    "— contoh /decoderdebug CBRE"
                ),
            )
        else:
            await decoder_debug_ticker(
                chat_id,
                args[0],
            )

    elif command == "/protocoldebug":
        if not args:
            await send_message(
                chat_id,
                (
                    "Gunakan /protocoldebug TICKER "
                    "— contoh /protocoldebug CBRE"
                ),
            )
        else:
            await protocol_debug_ticker(
                chat_id,
                args[0],
            )

    elif command == "/publisherdebug":
        if not args:
            await send_message(
                chat_id,
                (
                    "Gunakan /publisherdebug TICKER "
                    "— contoh /publisherdebug CBRE"
                ),
            )
        else:
            await publisher_debug_ticker(
                chat_id,
                args[0],
            )

    elif command == "/ma":
        await send_message(
            chat_id,
            "🤝 Mencari M&A / takeover terbaru…",
        )
        await send_filtered(
            chat_id,
            "MA",
        )

    elif command == "/ipo":
        await send_message(
            chat_id,
            "🆕 Mencari IPO valid terbaru…",
        )
        await send_filtered(
            chat_id,
            "IPO",
        )

    elif command == "/rights":
        await send_message(
            chat_id,
            "📣 Mencari Rights Issue / HMETD terbaru…",
        )
        await send_filtered(
            chat_id,
            "RIGHTS",
        )


# ============================================================
# AUTO ALERT
# ============================================================

async def news_worker():
    while True:
        try:
            articles = await fetch_all_articles()
            subscribers = subscriber_ids()

            initialized = (
                get_state("v5_4_baseline_initialized", "0") == "1"
            )

            if not initialized:
                for article in articles:
                    mark_sent(article["key"])

                set_state(
                    "v5_4_baseline_initialized",
                    "1",
                )

                print(
                    f"V5.4 baseline dibuat: {len(articles)} artikel "
                    "ditandai sebagai sudah diketahui."
                )

            else:
                new_articles = [
                    article
                    for article in articles
                    if not was_sent(article["key"])
                    and is_recent_hours(article["published_dt"])
                    and priority_meets_minimum(
                        article.get("urgency", article.get("priority", "LOW")),
                        AUTO_ALERT_MIN_PRIORITY,
                    )
                    and not (
                        article.get("event_type") == "IPO"
                        and article.get("ipo_class") == "PIPELINE"
                    )
                ]

                new_articles.sort(
                    key=lambda x: (
                        PRIORITY_RANK.get(x.get("urgency", x.get("priority", "LOW")), 1),
                        x["ca_score"],
                        x["published_dt"]
                        or datetime.min.replace(
                            tzinfo=timezone.utc
                        ),
                    ),
                    reverse=True,
                )

                new_articles = new_articles[
                    : CONFIG.get(
                        "push_limit_per_cycle",
                        8,
                    )
                ]

                for article in new_articles:
                    delivered = False

                    await enrich_decision_support(article)

                    for chat_id in subscribers:
                        try:
                            await send_message(
                                chat_id,
                                format_alert(article),
                            )
                            delivered = True

                        except Exception as exc:
                            print(
                                "Send error:",
                                chat_id,
                                repr(exc),
                            )

                    if delivered or not subscribers:
                        mark_sent(article["key"])

        except Exception as exc:
            print("news_worker error:", repr(exc))

        await asyncio.sleep(POLL_MINUTES * 60)


async def telegram_worker():
    offset = 0

    while True:
        try:
            updates = await tg_call(
                "getUpdates",
                {
                    "offset": offset,
                    "timeout": 25,
                    "allowed_updates": ["message"],
                },
            )

            for update in updates:
                offset = update["update_id"] + 1
                await handle_update(update)

        except Exception as exc:
            print(
                "telegram_worker error:",
                repr(exc),
            )
            await asyncio.sleep(3)


async def main():
    print("Kabar Saham Intelligence V6.0 / V5.4 Core running...")
    print("Publisher Direct Resolver: ACTIVE")
    print("Publisher Direct + Deep Parser + Google Fallback: ACTIVE")
    print("RSS parser: Python XML parser")
    print(f"Monitoring interval: {POLL_MINUTES} menit")
    print(f"Manual news range: {RECENT_DAYS} hari")
    print(f"Auto-alert freshness: {AUTO_ALERT_HOURS} jam")
    print(f"Indonesia priority: {INDONESIA_PRIORITY}")
    print(f"Auto-alert min priority: {AUTO_ALERT_MIN_PRIORITY}")
    print(
        f"Market data: "
        f"{'ON' if MARKET_DATA_ENABLED and YFINANCE_AVAILABLE else 'OFF'}"
    )
    print(
        f"Deep extraction: "
        f"{'ON' if DEEP_EXTRACTION_ENABLED and BS4_AVAILABLE else 'OFF'}"
    )
    print(f"Deep extract limit: {DEEP_EXTRACT_LIMIT}")
    print(
        f"Source resolver: "
        f"{'ON' if SOURCE_RESOLVER_ENABLED else 'OFF'}"
    )
    print(
        f"Resolver search fallback: "
        f"{'ON' if RESOLVER_SEARCH_FALLBACK else 'OFF'}"
    )
    print(
        f"Google decoder core: "
        f"{'ON' if GOOGLE_DECODER_ENABLED else 'OFF'}"
    )
    print(
        f"Google batch decoder: "
        f"{'ON' if GOOGLE_DECODER_BATCH_ENABLED else 'OFF'}"
    )
    print("Live multi-format parser: ON")
    print(
        f"Decoder debug: "
        f"{'ON' if DECODER_DEBUG_ENABLED else 'OFF'}"
    )
    print(
        f"Dynamic signature/timestamp protocol: "
        f"{'ON' if DYNAMIC_PROTOCOL_ENABLED else 'OFF'}"
    )
    print(
        f"Static decoder fallback: "
        f"{'ON' if DYNAMIC_PROTOCOL_FALLBACK_STATIC else 'OFF'}"
    )
    print(
        f"Publisher Direct Resolver: "
        f"{'ON' if PUBLISHER_DIRECT_ENABLED else 'OFF'}"
    )
    print(
        f"Publisher confidence threshold: "
        f"{PUBLISHER_DIRECT_MIN_SCORE}"
    )

    await asyncio.gather(
        telegram_worker(),
        news_worker(),
    )


if __name__ == "__main__":
    asyncio.run(main())
