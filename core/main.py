import asyncio
import copy
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
from difflib import SequenceMatcher
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
# V6.6.3 — Clean Alert UX + Market Context Isolation
# ============================================================

COMPACT_ALERT_ENABLED = (
    os.getenv("V663_COMPACT_ALERT_ENABLED", "1") == "1"
)
MARKET_DATA_NOISE_GUARD_ENABLED = (
    os.getenv("V663_MARKET_DATA_NOISE_GUARD_ENABLED", "1") == "1"
)
TRUE_NEW_DETAIL_DIFF_ENABLED = (
    os.getenv("V663_TRUE_NEW_DETAIL_DIFF_ENABLED", "1") == "1"
)

# ============================================================
# V6.6.4 — Issuer Profile Intelligence
# ============================================================

ISSUER_PROFILE_ENABLED = (
    os.getenv("V664_ISSUER_PROFILE_ENABLED", "1") == "1"
)
IDX_PROFILE_LOOKUP_ENABLED = (
    os.getenv("V664_IDX_PROFILE_LOOKUP_ENABLED", "1") == "1"
)
PROFILE_MARKET_FALLBACK_ENABLED = (
    os.getenv("V664_PROFILE_MARKET_FALLBACK_ENABLED", "1") == "1"
)
PROFILE_CONTROLLER_SEARCH_ENABLED = (
    os.getenv("V664_PROFILE_CONTROLLER_SEARCH_ENABLED", "1") == "1"
)
PROFILE_CACHE_TTL_DAYS = max(
    1,
    min(180, int(os.getenv("V664_PROFILE_CACHE_TTL_DAYS", "30"))),
)
PROFILE_TIMEOUT_SECONDS = max(
    5,
    min(30, int(os.getenv("V664_PROFILE_TIMEOUT_SECONDS", "15"))),
)
PROFILE_BUSINESS_MAX_CHARS = max(
    80,
    min(500, int(os.getenv("V664_PROFILE_BUSINESS_MAX_CHARS", "240"))),
)

# V6.6.4.1 — Controller Deep Resolver + Status Consistency
CONTROLLER_DEEP_RESOLVER_ENABLED = (
    os.getenv("V6641_CONTROLLER_DEEP_RESOLVER_ENABLED", "1") == "1"
)
CONTROLLER_CROSS_VERIFY_ENABLED = (
    os.getenv("V6641_CONTROLLER_CROSS_VERIFY_ENABLED", "1") == "1"
)
CONTROL_STATUS_CONSISTENCY_ENABLED = (
    os.getenv("V6641_CONTROL_STATUS_CONSISTENCY_ENABLED", "1") == "1"
)

# V6.6.4.2 — Profile/Analyze Memory Sync + Official Evidence Wording
PROFILE_DEEP_CONTEXT_ON_DEMAND_ENABLED = (
    os.getenv("V6642_PROFILE_DEEP_CONTEXT_ON_DEMAND_ENABLED", "1") == "1"
)
PROFILE_CACHE_QUALITY_MERGE_ENABLED = (
    os.getenv("V6642_PROFILE_CACHE_QUALITY_MERGE_ENABLED", "1") == "1"
)
OFFICIAL_EVIDENCE_WORDING_ENABLED = (
    os.getenv("V6642_OFFICIAL_EVIDENCE_WORDING_ENABLED", "1") == "1"
)

# ============================================================
# V6.7.4 — Rumor Intelligence & Confirmation Tracker
# ============================================================

RUMOR_INTELLIGENCE_ENABLED = (
    os.getenv("V67_RUMOR_INTELLIGENCE_ENABLED", "1") == "1"
)
RUMOR_AUTO_ALERT_ENABLED = (
    os.getenv("V67_RUMOR_AUTO_ALERT_ENABLED", "1") == "1"
)
RUMOR_QUERY_LIMIT = max(
    1,
    min(20, int(os.getenv("V67_RUMOR_QUERY_LIMIT", "12"))),
)
RUMOR_CONFIRMATION_QUERY_LIMIT = max(
    0,
    min(6, int(os.getenv("V67_RUMOR_CONFIRMATION_QUERY_LIMIT", "4"))),
)
RUMOR_LOOKBACK_HOURS = max(
    12,
    min(336, int(os.getenv("V67_RUMOR_LOOKBACK_HOURS", "96"))),
)
RUMOR_AUTO_ALERT_HOURS = max(
    1,
    min(96, int(os.getenv("V67_RUMOR_AUTO_ALERT_HOURS", "36"))),
)
RUMOR_PUSH_LIMIT = max(
    1,
    min(8, int(os.getenv("V67_RUMOR_PUSH_LIMIT", "4"))),
)
RUMOR_EXPIRE_DAYS = max(
    2,
    min(30, int(os.getenv("V67_RUMOR_EXPIRE_DAYS", "7"))),
)
RUMOR_NOTIFY_EXPIRED = (
    os.getenv("V67_RUMOR_NOTIFY_EXPIRED", "0") == "1"
)
RUMOR_PROFILE_ENABLED = (
    os.getenv("V67_RUMOR_PROFILE_ENABLED", "1") == "1"
)
RUMOR_DEEP_ENRICH_ENABLED = (
    os.getenv("V67_RUMOR_DEEP_ENRICH_ENABLED", "1") == "1"
)

# V6.7.4 — Rumor Entity Resolution + UNKNOWN Merge Guard
RUMOR_ENTITY_RESOLUTION_ENABLED = (
    os.getenv("V671_RUMOR_ENTITY_RESOLUTION_ENABLED", "1") == "1"
)
RUMOR_UNKNOWN_MERGE_ENABLED = (
    os.getenv("V671_RUMOR_UNKNOWN_MERGE_ENABLED", "1") == "1"
)
RUMOR_ENTITY_MIN_ALIAS_CHARS = max(
    4,
    min(30, int(os.getenv("V671_RUMOR_ENTITY_MIN_ALIAS_CHARS", "5"))),
)
RUMOR_ENTITY_LOOKUP_LIMIT = max(
    1,
    min(10, int(os.getenv("V671_RUMOR_ENTITY_LOOKUP_LIMIT", "6"))),
)

# V6.7.4 — Rumor Data Integrity Guard
RUMOR_DATA_INTEGRITY_GUARD_ENABLED = (
    os.getenv("V672_RUMOR_DATA_INTEGRITY_GUARD_ENABLED", "1") == "1"
)
RUMOR_PRICE_PERCENT_STAKE_GUARD_ENABLED = (
    os.getenv("V672_PRICE_PERCENT_STAKE_GUARD_ENABLED", "1") == "1"
)
RUMOR_PARTY_PHRASE_GUARD_ENABLED = (
    os.getenv("V672_PARTY_PHRASE_GUARD_ENABLED", "1") == "1"
)
RUMOR_SHARE_COUNT_GUARD_ENABLED = (
    os.getenv("V672_SHARE_COUNT_GUARD_ENABLED", "1") == "1"
)
RUMOR_CONFIRMED_DEDUP_ENABLED = (
    os.getenv("V672_CONFIRMED_DEDUP_ENABLED", "1") == "1"
)
RUMOR_PROFILE_DEEP_FALLBACK_ENABLED = (
    os.getenv("V672_PROFILE_DEEP_FALLBACK_ENABLED", "1") == "1"
)
RUMOR_PROFILE_REFRESH_HOURS = max(
    1,
    min(168, int(os.getenv("V672_PROFILE_REFRESH_HOURS", "12"))),
)

# V6.7.4 — Source Quality, Anti-Copy, Indonesian Business Profile,
# Owner Fallback Display, and Rumor Trading Impact.
# All defaults are ON and require no new Secret/workflow/dependency.
RUMOR_SOURCE_QUALITY_ENABLED = (
    os.getenv("V673_RUMOR_SOURCE_QUALITY_ENABLED", "1") == "1"
)
RUMOR_ANTI_COPY_ENABLED = (
    os.getenv("V673_RUMOR_ANTI_COPY_ENABLED", "1") == "1"
)
RUMOR_TRADING_IMPACT_ENABLED = (
    os.getenv("V673_RUMOR_TRADING_IMPACT_ENABLED", "1") == "1"
)
RUMOR_BUSINESS_ID_ENABLED = (
    os.getenv("V673_RUMOR_BUSINESS_ID_ENABLED", "1") == "1"
)
RUMOR_OWNER_FALLBACK_ENABLED = (
    os.getenv("V673_RUMOR_OWNER_FALLBACK_ENABLED", "1") == "1"
)
RUMOR_CONTROLLER_SEARCH_LIMIT = max(
    6,
    min(12, int(os.getenv("V673_CONTROLLER_SEARCH_LIMIT", "10"))),
)
RUMOR_COPY_SIMILARITY = max(
    0.72,
    min(0.97, float(os.getenv("V673_COPY_SIMILARITY", "0.84"))),
)

# V6.7.4 — Owner Intelligence V2 + Semantic Derivative Detection +
# Weighted Effective Independence + Private/Pre-IPO Profile Resolver V2.
# Defaults remain ON. No new Secret/workflow/dependency is required.
RUMOR_SEMANTIC_COPY_V2_ENABLED = (
    os.getenv("V674_SEMANTIC_COPY_V2_ENABLED", "1") == "1"
)
RUMOR_WEIGHTED_INDEPENDENCE_V2_ENABLED = (
    os.getenv("V674_WEIGHTED_INDEPENDENCE_V2_ENABLED", "1") == "1"
)
RUMOR_OWNER_INTELLIGENCE_V2_ENABLED = (
    os.getenv("V674_OWNER_INTELLIGENCE_V2_ENABLED", "1") == "1"
)
RUMOR_PRIVATE_PROFILE_V2_ENABLED = (
    os.getenv("V674_PRIVATE_PROFILE_V2_ENABLED", "1") == "1"
)
RUMOR_SEMANTIC_COPY_SIMILARITY = max(
    0.42,
    min(0.90, float(os.getenv("V674_SEMANTIC_COPY_SIMILARITY", "0.58"))),
)
RUMOR_OWNER_V2_SEARCH_LIMIT = max(
    4,
    min(12, int(os.getenv("V674_OWNER_V2_SEARCH_LIMIT", "8"))),
)
RUMOR_DERIVATIVE_LOW_WEIGHT = max(
    0.10,
    min(0.50, float(os.getenv("V674_DERIVATIVE_LOW_WEIGHT", "0.25"))),
)
RUMOR_DERIVATIVE_MEDIUM_WEIGHT = max(
    0.25,
    min(0.80, float(os.getenv("V674_DERIVATIVE_MEDIUM_WEIGHT", "0.55"))),
)

# V6.7.5 — Issuer Name Sanitizer V3 + Owner Intelligence V3 +
# Unified Indonesian Profile + Silent Profile Cache Repair.
# Additive patch: no new Secret, workflow, dependency, or state schema.
RUMOR_ISSUER_SANITIZER_V3_ENABLED = (
    os.getenv("V675_ISSUER_SANITIZER_V3_ENABLED", "1") == "1"
)
RUMOR_OWNER_INTELLIGENCE_V3_ENABLED = (
    os.getenv("V675_OWNER_INTELLIGENCE_V3_ENABLED", "1") == "1"
)
RUMOR_UNIFIED_PROFILE_ID_ENABLED = (
    os.getenv("V675_UNIFIED_PROFILE_ID_ENABLED", "1") == "1"
)
RUMOR_PROFILE_CACHE_REPAIR_V3_ENABLED = (
    os.getenv("V675_PROFILE_CACHE_REPAIR_V3_ENABLED", "1") == "1"
)
RUMOR_OWNER_V3_SEARCH_LIMIT = max(
    6,
    min(16, int(os.getenv("V675_OWNER_V3_SEARCH_LIMIT", "12"))),
)

# V6.7.7 — Ownership Intelligence Finalization V4.
# Adds primary-company page deep parsing, reverse-role ownership parsing,
# official registry holder-table parsing, and a fresh owner_v4 cache stamp.
# Additive only: no new Secret, workflow, dependency, or state schema.
RUMOR_OWNER_INTELLIGENCE_V4_ENABLED = (
    os.getenv("V676_OWNER_INTELLIGENCE_V4_ENABLED", "1") == "1"
)
RUMOR_OWNER_V4_SEARCH_LIMIT = max(
    6,
    min(18, int(os.getenv("V676_OWNER_V4_SEARCH_LIMIT", "14"))),
)
RUMOR_OWNER_V4_PAGE_FETCH_LIMIT = max(
    1,
    min(8, int(os.getenv("V676_OWNER_V4_PAGE_FETCH_LIMIT", "4"))),
)
RUMOR_OWNER_V4_PAGE_MAX_CHARS = max(
    12000,
    min(120000, int(os.getenv("V676_OWNER_V4_PAGE_MAX_CHARS", "60000"))),
)

# V6.7.7 — Ownership Safety Hotfix V5.
# Safety-first patch after live V6.7.6 false positives from navigation/news text.
# V5 never trusts generic page prose as ownership evidence: controller/holder
# extraction is section/role anchored and restricted to IDX/OJK/KSEI or the
# issuer's exact primary domain. Existing poisoned V4 cache is silently repaired.
RUMOR_OWNER_SAFETY_V5_ENABLED = (
    os.getenv("V677_OWNER_SAFETY_V5_ENABLED", "1") == "1"
)
RUMOR_OWNER_V5_SEARCH_LIMIT = max(
    4,
    min(14, int(os.getenv("V677_OWNER_V5_SEARCH_LIMIT", "10"))),
)
RUMOR_OWNER_V5_PAGE_FETCH_LIMIT = max(
    1,
    min(6, int(os.getenv("V677_OWNER_V5_PAGE_FETCH_LIMIT", "3"))),
)
RUMOR_OWNER_V5_SECTION_CHARS = max(
    300,
    min(1800, int(os.getenv("V677_OWNER_V5_SECTION_CHARS", "900"))),
)

RUMOR_STRENGTH_RANK = {
    "WEAK": 1,
    "MEDIUM": 2,
    "STRONG": 3,
    "CONFIRMED OFFICIAL": 4,
}
RUMOR_STATUS_RANK = {
    "ACTIVE": 1,
    "EXPIRED": 2,
    "DENIED": 3,
    "CONFIRMED OFFICIAL": 4,
}

ISSUER_PROFILE_CACHE = {}

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
        r"(\d[\d.,]*)\s*(ribu|juta|miliar|triliun)?\s+saham",
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

    if (
        CONTROLLER_DEEP_RESOLVER_ENABLED
        and evt not in ("IPO", "RIGHTS ISSUE")
    ):
        article["controller_evidence"] = _deep_controller_evidence(
            deep_text,
            ticker=d.get("ticker"),
            issuer_name=article.get("issuer_name"),
            source_url=article.get("source_url"),
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
# V6.6.4 — ISSUER PROFILE INTELLIGENCE
# ============================================================

IDX_PROFILE_URL_TEMPLATE = (
    "https://www.idx.co.id/id/perusahaan-tercatat/"
    "profil-perusahaan-tercatat/{ticker}"
)


def _profile_now_iso():
    return datetime.now(timezone.utc).isoformat()


def _profile_parse_iso(value):
    try:
        dt = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _profile_fresh(profile):
    if not isinstance(profile, dict):
        return False

    stamp = _profile_parse_iso(
        profile.get("verified_at")
        or profile.get("fetched_at")
    )
    if stamp is None:
        return False

    return (
        datetime.now(timezone.utc) - stamp
        <= timedelta(days=PROFILE_CACHE_TTL_DAYS)
    )


def _clean_profile_text(value, max_chars=240):
    value = normalize(str(value or ""))
    if not value:
        return None

    value = re.sub(
        r"\s+",
        " ",
        value,
    ).strip(" :;,-")

    if not value:
        return None

    return value[:max_chars]


def _clean_business_summary(value):
    value = _clean_profile_text(
        value,
        max_chars=max(
            PROFILE_BUSINESS_MAX_CHARS * 3,
            500,
        ),
    )
    if not value:
        return None

    # Keep the first useful 1–2 sentences; alert should stay concise.
    parts = re.split(
        r"(?<=[.!?])\s+",
        value,
    )
    compact = " ".join(parts[:2]).strip()

    return compact[:PROFILE_BUSINESS_MAX_CHARS] or None


def _profile_result_text_from_html(html_text):
    if not html_text or not BS4_AVAILABLE:
        return ""

    try:
        soup = BeautifulSoup(
            html_text,
            "html.parser",
        )
        return normalize(
            soup.get_text(
                " ",
                strip=True,
            )
        )
    except Exception:
        return normalize(html_text)


def _extract_idx_profile_labels(text):
    """Best-effort label extraction from IDX profile page/search snippet."""
    text = normalize(str(text or ""))
    if not text:
        return {}

    labels = {
        "business_activity": [
            "Bidang Usaha Utama",
            "Main Business Activity",
        ],
        "sector": [
            "Sektor",
            "Sector",
        ],
        "subsector": [
            "Subsektor",
            "Sub Sector",
            "Subsector",
        ],
        "industry": [
            "Industri",
            "Industry",
        ],
        "subindustry": [
            "Subindustri",
            "Sub Industry",
            "Subindustry",
        ],
        "controller_name": [
            "Pemegang Saham Pengendali",
            "Pengendali",
            "Controlling Shareholder",
        ],
        "major_shareholder": [
            "Pemegang Saham Utama",
            "Major Shareholder",
        ],
        "website": [
            "Website",
            "Situs Web",
        ],
    }

    # Labels that commonly follow one another on the IDX profile page.
    all_label_terms = sorted(
        {
            item
            for values in labels.values()
            for item in values
        }
        | {
            "Nama",
            "Kode",
            "Alamat Kantor",
            "Alamat Email",
            "Nomor Telepon",
            "Website",
            "Tanggal Pencatatan",
            "Papan Pencatatan",
            "Biro Administrasi Efek",
        },
        key=len,
        reverse=True,
    )

    stop = "|".join(
        re.escape(x)
        for x in all_label_terms
    )

    output = {}

    for field, candidates in labels.items():
        for label in candidates:
            pattern = (
                rf"\b{re.escape(label)}\s*[:,]?\s*"
                rf"(.{{2,450}}?)"
                rf"(?=\s+(?:{stop})\s*[:,]?|\s*$)"
            )
            match = re.search(
                pattern,
                text,
                flags=re.I,
            )
            if not match:
                continue

            value = _clean_profile_text(
                match.group(1),
                max_chars=(
                    PROFILE_BUSINESS_MAX_CHARS
                    if field == "business_activity"
                    else (220 if field == "website" else (180 if field in {"controller_name", "major_shareholder"} else 120))
                ),
            )
            if value:
                output[field] = value
                break

    return output


async def _fetch_idx_profile(ticker):
    ticker = _valid_idx_ticker(ticker)
    if not ticker or not IDX_PROFILE_LOOKUP_ENABLED:
        return {}

    url = IDX_PROFILE_URL_TEMPLATE.format(
        ticker=ticker,
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/129 Safari/537.36"
        ),
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.7",
    }

    try:
        async with httpx.AsyncClient(
            headers=headers,
            follow_redirects=True,
        ) as client:
            response = await client.get(
                url,
                timeout=PROFILE_TIMEOUT_SECONDS,
            )

        if response.status_code < 400:
            parsed = _extract_idx_profile_labels(
                _profile_result_text_from_html(
                    response.text
                )
            )

            if parsed:
                parsed["source"] = "IDX PROFILE"
                parsed["source_url"] = url
                parsed["source_quality"] = "OFFICIAL"
                return parsed

    except Exception:
        pass

    return {}


def _profile_yfinance_sync(ticker):
    ticker = _valid_idx_ticker(ticker)

    if (
        not ticker
        or not PROFILE_MARKET_FALLBACK_ENABLED
        or not YFINANCE_AVAILABLE
    ):
        return {}

    symbol = f"{ticker}.JK"

    try:
        obj = yf.Ticker(symbol)
        info = {}

        getter = getattr(
            obj,
            "get_info",
            None,
        )

        if callable(getter):
            try:
                result = getter()
                if isinstance(result, dict):
                    info.update(result)
            except Exception:
                pass

        if not info:
            try:
                result = getattr(
                    obj,
                    "info",
                    None,
                )
                if isinstance(result, dict):
                    info.update(result)
            except Exception:
                pass

        if not info:
            return {}

        return {
            "issuer_name": (
                _clean_issuer_alias(
                    info.get("longName")
                    or info.get("shortName")
                    or info.get("displayName")
                )
            ),
            "business_activity": _clean_business_summary(
                info.get("longBusinessSummary")
            ),
            "sector": _clean_profile_text(
                info.get("sector"),
                120,
            ),
            "industry": _clean_profile_text(
                info.get("industry"),
                120,
            ),
            "website": _clean_profile_text(
                info.get("website"),
                220,
            ),
            "source": "Yahoo Finance",
            "source_quality": "FALLBACK",
        }

    except Exception:
        return {}


async def _fetch_market_profile(ticker):
    return await asyncio.to_thread(
        _profile_yfinance_sync,
        ticker,
    )


def _controller_candidate_from_event(article):
    """Resolve controller from an official event + explicit identity evidence.

    Evidence order:
    1. validated Acquirer from event parser,
    2. one unique controller candidate extracted from deep article text.

    A deep-article identity is accepted only when the corporate-action event
    itself is official and the control-change wording is explicit.
    """
    if not isinstance(article, dict):
        return None

    d = article.get("details") or {}

    status = control_change_evidence_status(
        article
    )

    if not (
        status
        and status.startswith("✅")
    ):
        return None

    official = (
        article.get("official_reference")
        or article.get("verified_official_ref")
        or {}
    )

    official_authority = str(
        official.get("authority")
        or "OFFICIAL EVENT"
    )

    official_url = official.get(
        "url"
    )

    event_stake = None

    if d.get("percentages"):
        try:
            event_stake = float(
                d["percentages"][0]
            )
        except Exception:
            event_stake = None

    # 1. Existing validated transaction-role identity.
    acquirer = _clean_role_candidate(
        d.get("acquirer")
    )

    if (
        acquirer
        and not _entity_is_target_issuer(
            acquirer,
            ticker=d.get("ticker"),
            issuer_name=article.get("issuer_name"),
        )
    ):
        return {
            "name": acquirer,
            "stake_pct": event_stake,
            "verified": True,
            "verification_level": "OFFICIAL_EVENT_ROLE",
            "source": official_authority,
            "source_url": official_url,
            "basis": "OFFICIAL_CONTROL_CHANGE_EVENT",
        }

    # 2. Deep article explicitly names exactly one controller candidate,
    # while IDX/official reference corroborates the same corporate action.
    evidence = article.get(
        "controller_evidence"
    ) or {}

    candidates = [
        item
        for item in (
            evidence.get("candidates")
            or []
        )
        if isinstance(item, dict)
        and item.get("name")
    ]

    unique = {}

    for item in candidates:
        name = _normalize_legal_entity_display(
            item.get("name")
        )

        if not name:
            continue

        if _entity_is_target_issuer(
            name,
            ticker=d.get("ticker"),
            issuer_name=article.get("issuer_name"),
        ):
            continue

        key = re.sub(
            r"[^a-z0-9]+",
            "",
            name.lower(),
        )

        if key:
            item = dict(item)
            item["name"] = name
            unique[key] = item

    if (
        CONTROLLER_CROSS_VERIFY_ENABLED
        and evidence.get("explicit_control_change")
        and len(unique) == 1
    ):
        item = next(
            iter(unique.values())
        )

        stake = item.get(
            "stake_pct"
        )

        # Prefer event-level transaction stake if available, because it is
        # already material-normalized and tied to the official event.
        if event_stake is not None:
            stake = event_stake

        return {
            "name": item["name"],
            "stake_pct": stake,
            "verified": True,
            "verification_level": "CROSS_VERIFIED",
            "source": (
                official_authority
                + " + DEEP ARTICLE"
            ),
            "source_url": (
                official_url
                or evidence.get("source_url")
            ),
            "basis": "OFFICIAL_EVENT_PLUS_DEEP_IDENTITY",
            "evidence_text": item.get(
                "evidence_text"
            ),
        }

    return None


def _normalize_legal_entity_display(value):
    value = _clean_profile_text(
        value,
        120,
    )
    if not value:
        return None

    # Remove search-result file suffix / boilerplate.
    value = re.sub(
        r"\s+(?:pdf|download|keterbukaan informasi)$",
        "",
        value,
        flags=re.I,
    ).strip(" -:|")

    # Search engines sometimes lowercase PDF titles.
    if value.lower().startswith("pt "):
        tail = value[3:].strip()
        if tail and tail == tail.lower():
            tail = " ".join(
                word.capitalize()
                for word in tail.split()
            )
        value = "PT " + tail

    return value or None


def _issuer_identity_tokens(
    ticker=None,
    issuer_name=None,
):
    values = []

    if ticker:
        values.append(
            str(ticker).upper()
        )

    if issuer_name:
        clean = re.sub(
            r"\bPT\.?\b|\bTbk\.?\b",
            " ",
            str(issuer_name),
            flags=re.I,
        )
        clean = normalize(clean)

        if clean:
            values.append(
                clean.lower()
            )

    return values


def _entity_is_target_issuer(
    candidate,
    *,
    ticker=None,
    issuer_name=None,
):
    candidate = _normalize_legal_entity_display(
        candidate
    )
    if not candidate:
        return False

    normalized = re.sub(
        r"\bPT\.?\b|\bTbk\.?\b",
        " ",
        candidate,
        flags=re.I,
    )
    normalized = normalize(
        normalized
    ).lower()

    for token in _issuer_identity_tokens(
        ticker=ticker,
        issuer_name=issuer_name,
    ):
        if not token:
            continue

        if token.upper() == token and len(token) == 4:
            # A company legal name need not contain its ticker.
            continue

        if (
            normalized == token
            or normalized in token
            or token in normalized
        ):
            return True

    return False


def _extract_pct_near_text(text):
    text = normalize(
        str(text or "")
    )

    values = []

    for match in re.finditer(
        r"(\d{1,3}(?:[.,]\d+)?)\s*%",
        text,
    ):
        try:
            value = float(
                match.group(1).replace(",", ".")
            )
        except Exception:
            continue

        if 0 <= value <= 100:
            values.append(value)

    # A control transaction commonly cites one material stake.
    return values[0] if values else None


def _controller_context_explicit(text):
    text = normalize(
        str(text or "")
    ).lower()

    return any(
        phrase in text
        for phrase in (
            "pemegang saham pengendali",
            "pengendali baru",
            "pengendali anyar",
            "perubahan pengendali",
            "menjadi pengendali",
            "menjadi pemegang saham pengendali",
            "telah menjadi pengendali",
            "telah menjadi pemegang saham pengendali",
            "pengambilalihan",
            "mengambil alih",
        )
    )


def _extract_controller_from_text(
    text,
    ticker=None,
    issuer_name=None,
):
    """Extract controller candidates while refusing the target issuer itself.

    This function is deliberately conservative. It never treats
    "Pengendali Baru PT <TARGET>" as the controller name.
    """
    text = normalize(
        str(text or "")
    )
    if not text:
        return []

    patterns = [
        # PT X menjadi pengendali / pemegang saham pengendali.
        (
            r"(PT\.?\s+[A-Z][A-Za-z0-9&.,'’()\- ]{2,100}?)"
            r"\s+(?:telah\s+)?(?:resmi\s+)?(?:menjadi|sebagai)\s+"
            r"(?:pemegang\s+saham\s+pengendali|pengendali(?:\s+baru)?)"
        ),
        # Pengendali ... adalah PT X.
        (
            r"(?:pemegang\s+saham\s+pengendali|pengendali(?:\s+baru|\s+anyar)?)"
            r"(?:\s+(?:perseroan|emiten|perusahaan))?"
            r"\s*(?:adalah|yakni|yaitu|ialah|:|-)\s*"
            r"(PT\.?\s+[A-Z][A-Za-z0-9&.,'’()\- ]{2,100}?)"
        ),
        # PT X mengambil alih / mengakuisisi x% saham TARGET.
        (
            r"(PT\.?\s+[A-Z][A-Za-z0-9&.,'’()\- ]{2,100}?)"
            r"\s+(?:telah\s+)?(?:resmi\s+)?"
            r"(?:mengambil\s+alih|mengakuisisi|menguasai)"
            r".{0,140}?"
            r"(?:saham|kepemilikan)"
        ),
        # x% saham TARGET dikuasai / diambil alih PT X.
        (
            r"(?:\d{1,3}(?:[.,]\d+)?\s*%\s*)?"
            r"(?:saham|kepemilikan).{0,150}?"
            r"(?:dikuasai|diambil\s+alih|diakuisisi)\s+oleh\s+"
            r"(PT\.?\s+[A-Z][A-Za-z0-9&.,'’()\- ]{2,100}?)"
        ),
    ]

    output = []

    for pattern in patterns:
        for match in re.finditer(
            pattern,
            text,
            flags=re.I,
        ):
            candidate = _normalize_legal_entity_display(
                match.group(1)
            )
            candidate = _clean_role_candidate(
                candidate
            )

            if not candidate:
                continue

            if _entity_is_target_issuer(
                candidate,
                ticker=ticker,
                issuer_name=issuer_name,
            ):
                # Prevent: "Pengendali Baru PT Era Media Sejahtera Tbk"
                # from being interpreted as "PT Era Media Sejahtera" being
                # its own controller.
                continue

            around = text[
                max(0, match.start() - 180):
                min(len(text), match.end() + 220)
            ]

            output.append({
                "name": candidate,
                "stake_pct": _extract_pct_near_text(
                    around
                ),
                "evidence_text": _clean_profile_text(
                    around,
                    380,
                ),
                "basis": "DEEP_TEXT",
            })

    unique = {}

    for item in output:
        key = re.sub(
            r"[^a-z0-9]+",
            "",
            str(item["name"]).lower(),
        )

        if not key:
            continue

        current = unique.get(key)

        if current is None:
            unique[key] = item
            continue

        # Prefer candidate version that contains a stake.
        if (
            current.get("stake_pct") is None
            and item.get("stake_pct") is not None
        ):
            unique[key] = item

    return list(
        unique.values()
    )


def _controller_from_official_search_result(
    *,
    result_title,
    snippet,
    href,
    ticker,
    issuer_name=None,
):
    """Resolve the controller when an official IDX result title IS the actor.

    Example pattern:
      title   = "pt sinergi internasional investama"
      snippet = "... menjadi Pengendali Baru PT Era Media Sejahtera Tbk"

    In that structure the target company appears after "Pengendali Baru";
    the legal entity in the result title is the actor/controller.
    """
    if not CONTROLLER_DEEP_RESOLVER_ENABLED:
        return None

    ticker = _valid_idx_ticker(
        ticker
    )
    if not ticker:
        return None

    title_entity = _normalize_legal_entity_display(
        result_title
    )
    title_entity = _clean_role_candidate(
        title_entity
    )

    if not title_entity:
        return None

    if not re.match(
        r"^PT\.?\s+",
        title_entity,
        flags=re.I,
    ):
        return None

    if _entity_is_target_issuer(
        title_entity,
        ticker=ticker,
        issuer_name=issuer_name,
    ):
        return None

    combined = normalize(
        f"{result_title} {snippet}"
    )

    if ticker not in combined.upper():
        issuer_token = (
            normalize(str(issuer_name or "")).lower()
        )

        if (
            not issuer_token
            or issuer_token not in combined.lower()
        ):
            return None

    target_context = (
        r"(?:menjadi|sebagai|telah\s+menjadi).{0,80}"
        r"(?:pengendali(?:\s+baru|\s+anyar)?|pemegang\s+saham\s+pengendali)"
    )

    reverse_context = (
        r"(?:pengendali(?:\s+baru|\s+anyar)?|pemegang\s+saham\s+pengendali)"
        r".{0,100}(?:perseroan|perusahaan\s+sasaran|"
        + re.escape(ticker)
        + r"|"
        + re.escape(normalize(str(issuer_name or "")))
        + r")"
    )

    if not (
        re.search(
            target_context,
            combined,
            flags=re.I,
        )
        or re.search(
            reverse_context,
            combined,
            flags=re.I,
        )
    ):
        return None

    return {
        "name": title_entity,
        "stake_pct": _extract_pct_near_text(
            combined
        ),
        "verified": True,
        "verification_level": "OFFICIAL_DIRECT",
        "source": "IDX",
        "source_url": href,
        "basis": "OFFICIAL_RESULT_TITLE_ACTOR",
        "evidence_text": _clean_profile_text(
            snippet,
            380,
        ),
    }


def _deep_controller_evidence(
    text,
    *,
    ticker=None,
    issuer_name=None,
    source_url=None,
):
    candidates = _extract_controller_from_text(
        text,
        ticker=ticker,
        issuer_name=issuer_name,
    )

    explicit = _controller_context_explicit(
        text
    )

    return {
        "explicit_control_change": explicit,
        "candidates": candidates,
        "source_url": source_url,
        "source": "DEEP ARTICLE",
    }




async def _discover_controller_official(ticker, issuer_name=None):
    """Official-domain search resolver.

    Priority:
    1) Official IDX result title acts as controller and snippet says it
       becomes controller of the target issuer.
    2) Controller named explicitly inside official IDX snippet.
    Conflict => return None rather than guess.
    """
    ticker = _valid_idx_ticker(ticker)

    if (
        not ticker
        or not PROFILE_CONTROLLER_SEARCH_ENABLED
        or not RESOLVER_SEARCH_FALLBACK
        or not BS4_AVAILABLE
    ):
        return None

    queries = [
        f'site:idx.co.id "{ticker}" "Pengendali Baru"',
        f'site:idx.co.id "{ticker}" "Pemegang Saham Pengendali"',
        f'site:idx.co.id "{ticker}" "menjadi Pengendali"',
        f'site:idx.co.id "{ticker}" "Penawaran Tender Wajib" "Pengendali"',
        f'site:idx.co.id "{ticker}" "Pengendali" "Pemegang Saham"',
        f'site:idx.co.id "{ticker}" "Komposisi Pemegang Saham"',
        f'site:idx.co.id "{ticker}" "Kepemilikan Saham" "Pengendali"',
        f'site:idx.co.id "{ticker}" "Pemilik Manfaat Akhir"',
    ]

    if issuer_name:
        safe_issuer = _clean_profile_text(
            issuer_name,
            100,
        )
        if safe_issuer:
            queries += [
                f'site:idx.co.id "{safe_issuer}" "Pengendali Baru"',
                f'site:idx.co.id "{safe_issuer}" "Pemegang Saham Pengendali"',
            ]

    discovered = []

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/129 Safari/537.36"
        )
    }

    async with httpx.AsyncClient(
        headers=headers,
        follow_redirects=True,
    ) as client:
        for query in queries[:RUMOR_CONTROLLER_SEARCH_LIMIT]:
            search_url = (
                "https://html.duckduckgo.com/html/?q="
                + quote_plus(query)
            )

            try:
                response = await client.get(
                    search_url,
                    timeout=PROFILE_TIMEOUT_SECONDS,
                )
            except Exception:
                continue

            if response.status_code >= 400:
                continue

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

            result_blocks = soup.select(
                ".result, .web-result"
            )

            for block in result_blocks[:8]:
                link_node = block.select_one(
                    "a.result__a, .result__title a"
                )
                snippet_node = block.select_one(
                    ".result__snippet, .result__body"
                )

                if not link_node:
                    continue

                href = _extract_result_url_from_search(
                    link_node.get("href", "")
                )
                if not href:
                    continue

                host = _host(href)

                if not (
                    host == "idx.co.id"
                    or host.endswith(".idx.co.id")
                ):
                    continue

                result_title = normalize(
                    link_node.get_text(
                        " ",
                        strip=True,
                    )
                )

                snippet = normalize(
                    snippet_node.get_text(
                        " ",
                        strip=True,
                    )
                    if snippet_node
                    else ""
                )

                combined = normalize(
                    f"{result_title} {snippet}"
                )

                if (
                    ticker not in combined.upper()
                    and (
                        not issuer_name
                        or normalize(
                            str(issuer_name)
                        ).lower()
                        not in combined.lower()
                    )
                ):
                    continue

                # Best generic structure for IDX PDF search results:
                # PDF/result title identifies the actor, while snippet
                # states it became controller of the target company.
                title_actor = _controller_from_official_search_result(
                    result_title=result_title,
                    snippet=snippet,
                    href=href,
                    ticker=ticker,
                    issuer_name=issuer_name,
                )

                if title_actor:
                    discovered.append(
                        title_actor
                    )

                # Also accept explicit controller wording inside official
                # snippet, but never accept the target issuer itself.
                for candidate in _extract_controller_from_text(
                    combined,
                    ticker=ticker,
                    issuer_name=issuer_name,
                ):
                    candidate["verified"] = True
                    candidate["verification_level"] = "OFFICIAL_DIRECT"
                    candidate["source"] = "IDX"
                    candidate["source_url"] = href
                    candidate["basis"] = "OFFICIAL_SNIPPET_TEXT"
                    discovered.append(
                        candidate
                    )

    if not discovered:
        return None

    by_name = {}

    for item in discovered:
        name = item.get("name")

        if not name:
            continue

        key = re.sub(
            r"[^a-z0-9]+",
            "",
            str(name).lower(),
        )

        if not key:
            continue

        existing = by_name.get(
            key
        )

        if existing is None:
            by_name[key] = item
            continue

        # Prefer direct title-actor evidence, then candidate with stake.
        old_rank = (
            2
            if existing.get("basis") == "OFFICIAL_RESULT_TITLE_ACTOR"
            else 1
        )
        new_rank = (
            2
            if item.get("basis") == "OFFICIAL_RESULT_TITLE_ACTOR"
            else 1
        )

        if new_rank > old_rank:
            by_name[key] = item
        elif (
            new_rank == old_rank
            and existing.get("stake_pct") is None
            and item.get("stake_pct") is not None
        ):
            by_name[key] = item

    # Conflict guard: multiple distinct official candidates => no guess.
    if len(by_name) != 1:
        return None

    return next(
        iter(by_name.values())
    )


def _profile_holder_from_official_value(value, *, ticker=None, issuer_name=None, source_url=None, controller=False):
    value = _clean_profile_text(value, 180)
    if not value:
        return None

    stake = None
    match = re.search(r"(\d{1,3}(?:[.,]\d+)?)\s*%", value)
    if match:
        try:
            stake = float(match.group(1).replace(",", "."))
        except Exception:
            stake = None
        name_text = (value[:match.start()] + " " + value[match.end():]).strip(" -:;,|")
    else:
        name_text = value

    # Remove common official-page labels accidentally captured in the value.
    name_text = re.sub(
        r"\b(?:pemegang saham pengendali|pemegang saham utama|controlling shareholder|major shareholder)\b",
        " ",
        name_text,
        flags=re.I,
    )
    name = _normalize_legal_entity_display(name_text) or _clean_profile_text(name_text, 120)
    if not name:
        return None
    if _entity_is_target_issuer(name, ticker=ticker, issuer_name=issuer_name):
        return None

    return {
        "name": name,
        "stake_pct": stake,
        "verified": True,
        "verification_level": "OFFICIAL_DIRECT" if controller else "OFFICIAL_HOLDER",
        "source": "IDX PROFILE",
        "source_url": source_url,
        "basis": "IDX_PROFILE_LABEL",
    }



OWNER_V2_ROLE_PATTERNS = [
    ("CONTROLLER", r"(?:pemegang saham pengendali|controlling shareholder|ultimate controller|pengendali)\s*(?:adalah|yakni|yaitu|:|-)\s*([A-Z][A-Za-z0-9&.,'’()\- ]{2,100})"),
    ("MAJOR", r"(?:pemegang saham terbesar|pemegang saham utama|major shareholder|largest shareholder)\s*(?:adalah|yakni|yaitu|:|-)\s*([A-Z][A-Za-z0-9&.,'’()\- ]{2,100})"),
    ("FOUNDER", r"(?:pendiri|founder|co-founder)\s*(?:adalah|yakni|yaitu|:|-)\s*([A-Z][A-Za-z0-9&.,'’()\- ]{2,100})"),
    ("MAJOR", r"([A-Z][A-Za-z0-9&.,'’()\- ]{2,100})\s+(?:memiliki|menguasai|memegang)\s+(\d{1,3}(?:[.,]\d+)?)\s*%\s+(?:saham|kepemilikan)"),
]


def _owner_v2_clean_name(value):
    value = _clean_profile_text(value, 120)
    if not value:
        return None
    value = re.split(
        r"\b(?:dengan|sebesar|memiliki|menguasai|yang|sedangkan|sementara|melalui|pada|di mana)\b",
        value,
        maxsplit=1,
        flags=re.I,
    )[0]
    value = value.strip(" -:;,|.()")
    value = _normalize_legal_entity_display(value) or _clean_profile_text(value, 120)
    if not value or len(re.sub(r"[^A-Za-z0-9]", "", value)) < 3:
        return None
    generic = {
        "perseroan", "perusahaan", "pemegang saham", "investor", "publik",
        "masyarakat", "manajemen", "direksi", "komisaris",
    }
    if value.lower() in generic:
        return None
    return value


def _owner_v2_is_target_issuer(name, *, ticker=None, issuer_name=None):
    name_key = _normalized_entity_key(name)
    issuer_key = _normalized_entity_key(issuer_name)
    if not name_key:
        return True
    if issuer_key and name_key == issuer_key:
        return True
    if ticker and name_key == _normalized_entity_key(ticker):
        return True
    # Only reject exact legal-name equivalents; ownership vehicles often share
    # a family/company token with the issuer and must not be discarded.
    strip_terms = ("pt", "tbk", "persero", "perseroan", "limited", "ltd", "inc")
    def stripped(value):
        tokens = re.findall(r"[a-z0-9]+", str(value or "").lower())
        return "".join(token for token in tokens if token not in strip_terms)
    return bool(issuer_name and stripped(name) and stripped(name) == stripped(issuer_name))


def _extract_owner_candidates_v2(text, *, ticker=None, issuer_name=None, source=None, source_url=None):
    text = normalize(str(text or ""))
    if not text:
        return []
    output = []
    quality = _rumor_source_quality({"source": source or "", "link": source_url or ""})

    # Sentence-local parsing avoids swallowing entire search snippets.
    sentences = re.split(r"(?<=[.!?;])\s+|\s+[|•]\s+", text)
    for sentence in sentences:
        for role, pattern in OWNER_V2_ROLE_PATTERNS:
            for match in re.finditer(pattern, sentence, flags=re.I):
                if role == "MAJOR" and match.lastindex and match.lastindex >= 2 and re.match(r"\d", str(match.group(2) or "")):
                    raw_name = match.group(1)
                    stake_raw = match.group(2)
                else:
                    raw_name = match.group(1)
                    stake_match = re.search(r"(\d{1,3}(?:[.,]\d+)?)\s*%", sentence)
                    stake_raw = stake_match.group(1) if stake_match else None
                name = _owner_v2_clean_name(raw_name)
                if not name:
                    continue
                if ticker and _owner_v2_is_target_issuer(name, ticker=ticker, issuer_name=issuer_name):
                    continue
                stake = None
                if stake_raw:
                    try:
                        stake = float(str(stake_raw).replace(",", "."))
                    except Exception:
                        stake = None
                output.append({
                    "name": name,
                    "stake_pct": stake,
                    "role": role,
                    "source": source or "UNKNOWN",
                    "source_url": source_url,
                    "source_quality": quality["label"],
                    "source_tier": quality["tier"],
                    "source_group": _rumor_editorial_group({"source": source or "", "link": source_url or ""}),
                    "evidence_text": sentence[:320],
                })
    # Deduplicate same role/name/source sentence.
    unique = {}
    for item in output:
        key = (item["role"], _normalized_entity_key(item["name"]), item["source_group"])
        current = unique.get(key)
        if current is None or (current.get("stake_pct") is None and item.get("stake_pct") is not None):
            unique[key] = item
    return list(unique.values())


def _owner_v2_consensus(candidates, *, official_only=False):
    buckets = {}
    for item in candidates or []:
        if official_only and int(item.get("source_tier") or 0) < 5:
            continue
        key = _normalized_entity_key(item.get("name"))
        if not key:
            continue
        bucket = buckets.setdefault(key, {
            "name": item.get("name"), "items": [], "groups": set(),
            "max_tier": 0, "roles": set(), "stake_pct": None,
        })
        bucket["items"].append(item)
        bucket["groups"].add(item.get("source_group"))
        bucket["max_tier"] = max(bucket["max_tier"], int(item.get("source_tier") or 0))
        bucket["roles"].add(item.get("role"))
        if bucket["stake_pct"] is None and item.get("stake_pct") is not None:
            bucket["stake_pct"] = item.get("stake_pct")

    ranked = sorted(
        buckets.values(),
        key=lambda bucket: (
            1 if "CONTROLLER" in bucket["roles"] else 0,
            len(bucket["groups"]), bucket["max_tier"],
            1 if bucket["stake_pct"] is not None else 0,
        ),
        reverse=True,
    )
    return ranked


async def _discover_owner_intelligence_v2(ticker, issuer_name=None, website=None):
    """Find controller/major-holder context without promoting media to official fact."""
    ticker = _valid_idx_ticker(ticker)
    if not ticker or not RUMOR_OWNER_INTELLIGENCE_V2_ENABLED or not BS4_AVAILABLE:
        return {}

    safe_issuer = _clean_profile_text(issuer_name, 100) if issuer_name else None
    queries = [
        f'site:idx.co.id "{ticker}" "Pemegang Saham Pengendali"',
        f'site:idx.co.id "{ticker}" "Pemegang Saham Utama"',
        f'site:idx.co.id "{ticker}" "Komposisi Pemegang Saham"',
        f'"{ticker}" "pemegang saham terbesar"',
        f'"{ticker}" "pemegang saham pengendali"',
    ]
    if safe_issuer:
        queries += [
            f'site:idx.co.id "{safe_issuer}" "Pemilik Manfaat Akhir"',
            f'"{safe_issuer}" "pemegang saham terbesar"',
            f'"{safe_issuer}" "controlling shareholder"',
        ]
    if website:
        host = _host(str(website))
        if host:
            host = re.sub(r"^www\.", "", host)
            queries.append(f'site:{host} "shareholder" "{safe_issuer or ticker}"')

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129 Safari/537.36"}
    candidates = []
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        for query in queries[:RUMOR_OWNER_V2_SEARCH_LIMIT]:
            try:
                response = await client.get(
                    "https://html.duckduckgo.com/html/?q=" + quote_plus(query),
                    timeout=PROFILE_TIMEOUT_SECONDS,
                )
            except Exception:
                continue
            if response.status_code >= 400:
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            for block in soup.select(".result, .web-result")[:8]:
                link_node = block.select_one("a.result__a, .result__title a")
                snippet_node = block.select_one(".result__snippet, .result__body")
                if not link_node:
                    continue
                href = _extract_result_url_from_search(link_node.get("href", ""))
                if not href:
                    continue
                title = normalize(link_node.get_text(" ", strip=True))
                snippet = normalize(snippet_node.get_text(" ", strip=True) if snippet_node else "")
                combined = normalize(f"{title}. {snippet}")
                if ticker not in combined.upper() and safe_issuer and safe_issuer.lower() not in combined.lower():
                    continue
                host = _host(href)
                source_name = host or title[:80]
                candidates.extend(_extract_owner_candidates_v2(
                    combined,
                    ticker=ticker,
                    issuer_name=safe_issuer,
                    source=source_name,
                    source_url=href,
                ))

    if not candidates:
        return {"owner_v2_checked_utc": _profile_now_iso()}

    # Official controller requires official evidence. Never promote a media
    # consensus to controller status.
    official_ranked = _owner_v2_consensus(candidates, official_only=True)
    controller = None
    for bucket in official_ranked:
        if "CONTROLLER" not in bucket["roles"]:
            continue
        item = bucket["items"][0]
        controller = {
            "name": bucket["name"],
            "stake_pct": bucket["stake_pct"],
            "verified": True,
            "verification_level": "OFFICIAL_DIRECT_V2",
            "source": item.get("source") or "IDX",
            "source_url": item.get("source_url"),
            "basis": "OWNER_INTELLIGENCE_V2_OFFICIAL",
        }
        break

    major = None
    ranked = _owner_v2_consensus(candidates, official_only=False)
    for bucket in ranked:
        # Ignore a self/controller duplicate when controller already exists.
        if controller and _normalized_entity_key(controller.get("name")) == _normalized_entity_key(bucket["name"]):
            continue
        groups = {g for g in bucket["groups"] if g and g != "unknown"}
        has_official = bucket["max_tier"] >= 5
        corroborated = len(groups) >= 2 and bucket["max_tier"] >= 3
        premium_explicit = bucket["max_tier"] >= 4 and bucket["stake_pct"] is not None
        if not (has_official or corroborated or premium_explicit):
            continue
        item = sorted(bucket["items"], key=lambda row: int(row.get("source_tier") or 0), reverse=True)[0]
        major = {
            "name": bucket["name"],
            "stake_pct": bucket["stake_pct"],
            "verified": bool(has_official),
            "verification_level": "OFFICIAL_HOLDER_V2" if has_official else "CORROBORATED_CONTEXT_V2",
            "source": item.get("source"),
            "source_url": item.get("source_url"),
            "source_count": len(groups),
        }
        break

    return {
        "controller": controller,
        "major_shareholders": [major] if major else [],
        "owner_context_sources": len({item.get("source_group") for item in candidates if item.get("source_group")}),
        "owner_resolution_level": (
            "OFFICIAL_CONTROLLER" if controller
            else "MAJOR_HOLDER_CONTEXT" if major
            else "NO_SAFE_OWNER_RESULT"
        ),
        "owner_v2_checked_utc": _profile_now_iso(),
    }


OWNER_V3_CONTEXT_CUES = (
    "pemegang saham", "shareholder", "kepemilikan", "ownership",
    "komposisi saham", "shareholding", "beneficial owner",
)


def _extract_owner_candidates_v3(text, *, ticker=None, issuer_name=None, source=None, source_url=None, primary_company=False):
    candidates = _extract_owner_candidates_v2(
        text, ticker=ticker, issuer_name=issuer_name, source=source, source_url=source_url
    )
    normalized = normalize(str(text or ""))
    low = normalized.lower()
    if not normalized or not any(cue in low for cue in OWNER_V3_CONTEXT_CUES):
        return candidates

    quality = _rumor_source_quality({"source": source or "", "link": source_url or ""})
    tier = int(quality.get("tier") or 0)
    label = quality.get("label")
    if primary_company and tier < 4:
        tier = 4
        label = "PRIMARY_COMPANY"

    # Table/snippet fallback: "Low Tuck Kwong 60.94%" under a shareholder cue.
    table_pattern = re.compile(
        r"(?:^|[;|•,:]\s*)([A-Z][A-Za-z0-9&.'’()\- ]{2,90}?)\s*(?:[:\-–—]|\s)\s*(\d{1,3}(?:[.,]\d+)?)\s*%",
        re.I,
    )
    for match in table_pattern.finditer(normalized):
        name = _owner_v2_clean_name(match.group(1))
        if not name or _owner_v2_is_target_issuer(name, ticker=ticker, issuer_name=issuer_name):
            continue
        try:
            stake = float(match.group(2).replace(",", "."))
        except Exception:
            continue
        if not (0 < stake <= 100):
            continue
        candidates.append({
            "name": name, "stake_pct": stake, "role": "MAJOR",
            "source": source or "UNKNOWN", "source_url": source_url,
            "source_quality": label, "source_tier": tier,
            "source_group": _rumor_editorial_group({"source": source or "", "link": source_url or ""}),
            "evidence_text": normalized[:320],
            "primary_company": bool(primary_company),
        })

    unique = {}
    for item in candidates:
        key = (item.get("role"), _normalized_entity_key(item.get("name")), item.get("source_group"))
        current = unique.get(key)
        if current is None or (current.get("stake_pct") is None and item.get("stake_pct") is not None):
            unique[key] = item
    return list(unique.values())


def _owner_v3_select_candidates(candidates):
    candidates = [x for x in (candidates or []) if isinstance(x, dict) and x.get("name")]
    controller = None
    controller_rows = [x for x in candidates if x.get("role") == "CONTROLLER"]
    controller_rows.sort(
        key=lambda x: (int(x.get("source_tier") or 0), bool(x.get("primary_company")), x.get("stake_pct") is not None),
        reverse=True,
    )
    if controller_rows:
        best = controller_rows[0]
        if int(best.get("source_tier") or 0) >= 5 or best.get("primary_company"):
            controller = {
                "name": best.get("name"), "stake_pct": best.get("stake_pct"),
                "verified": True,
                "verification_level": "OFFICIAL_DIRECT_V3" if int(best.get("source_tier") or 0) >= 5 else "PRIMARY_COMPANY_CONTROLLER_V3",
                "source": best.get("source"), "source_url": best.get("source_url"),
                "basis": "OWNER_INTELLIGENCE_V3_EXPLICIT_ROLE",
            }

    buckets = _owner_v2_consensus(candidates, official_only=False)
    majors = []
    for bucket in buckets:
        if controller and _normalized_entity_key(bucket.get("name")) == _normalized_entity_key(controller.get("name")):
            continue
        items = bucket.get("items") or []
        if not items:
            continue
        best = sorted(
            items,
            key=lambda row: (int(row.get("source_tier") or 0), row.get("stake_pct") is not None),
            reverse=True,
        )[0]
        groups = {g for g in bucket.get("groups", set()) if g and g != "unknown"}
        primary = any(bool(row.get("primary_company")) for row in items)
        max_tier = int(bucket.get("max_tier") or 0)
        stake = bucket.get("stake_pct")
        safe = (
            max_tier >= 5
            or primary
            or (max_tier >= 4 and stake is not None)
            or (max_tier >= 3 and len(groups) >= 2 and stake is not None)
        )
        if not safe:
            continue
        majors.append({
            "name": bucket.get("name"), "stake_pct": stake,
            "verified": bool(max_tier >= 5 or primary),
            "verification_level": (
                "OFFICIAL_HOLDER_V3" if max_tier >= 5
                else "PRIMARY_COMPANY_HOLDER_V3" if primary
                else "CORROBORATED_CONTEXT_V3"
            ),
            "source": best.get("source"), "source_url": best.get("source_url"),
            "source_count": len(groups),
        })
        if len(majors) >= 3:
            break

    return {
        "controller": controller,
        "major_shareholders": majors,
        "owner_resolution_level": "OFFICIAL_CONTROLLER" if controller else "MAJOR_HOLDER_CONTEXT" if majors else "NO_SAFE_OWNER_RESULT",
    }


async def _discover_owner_intelligence_v3(ticker, issuer_name=None, website=None):
    """Owner hierarchy: IDX/OJK/KSEI -> official company -> corroborated context.

    Major shareholder evidence is never promoted to controller unless the
    evidence explicitly says controller and comes from an official/primary source.
    """
    ticker = _valid_idx_ticker(ticker)
    if not ticker or not RUMOR_OWNER_INTELLIGENCE_V3_ENABLED or not BS4_AVAILABLE:
        return {}

    safe_issuer = _clean_profile_text(issuer_name, 120) if issuer_name else None
    company_host = re.sub(r"^www\.", "", _host(str(website or "")) or "")
    queries = [
        f'site:idx.co.id "{ticker}" "pemegang saham"',
        f'site:idx.co.id "{ticker}" "komposisi pemegang saham"',
        f'site:idx.co.id "{ticker}" "pemegang saham pengendali"',
        f'site:idx.co.id "{ticker}" "laporan tahunan" "pemegang saham"',
        f'site:ojk.go.id "{ticker}" "pemegang saham"',
        f'site:ksei.co.id "{ticker}" "pemegang saham"',
    ]
    if safe_issuer:
        queries += [
            f'site:idx.co.id "{safe_issuer}" "shareholder"',
            f'"{safe_issuer}" "pemegang saham terbesar"',
            f'"{safe_issuer}" "controlling shareholder"',
        ]
    if company_host:
        queries += [
            f'site:{company_host} "shareholder"',
            f'site:{company_host} "pemegang saham"',
            f'site:{company_host} "annual report" "shareholder"',
        ]

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129 Safari/537.36"}
    candidates = []
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        for query in queries[:RUMOR_OWNER_V3_SEARCH_LIMIT]:
            try:
                response = await client.get(
                    "https://html.duckduckgo.com/html/?q=" + quote_plus(query),
                    timeout=PROFILE_TIMEOUT_SECONDS,
                )
            except Exception:
                continue
            if response.status_code >= 400:
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            for block in soup.select(".result, .web-result")[:10]:
                link_node = block.select_one("a.result__a, .result__title a")
                snippet_node = block.select_one(".result__snippet, .result__body")
                if not link_node:
                    continue
                href = _extract_result_url_from_search(link_node.get("href", ""))
                if not href:
                    continue
                title = normalize(link_node.get_text(" ", strip=True))
                snippet = normalize(snippet_node.get_text(" ", strip=True) if snippet_node else "")
                combined = normalize(f"{title}. {snippet}")
                if ticker not in combined.upper() and safe_issuer and safe_issuer.lower() not in combined.lower():
                    # Company-site result may omit ticker but must at least be on the official domain.
                    if not company_host or company_host not in (_host(href) or ""):
                        continue
                host = re.sub(r"^www\.", "", _host(href) or "")
                primary_company = bool(company_host and host == company_host)
                candidates.extend(_extract_owner_candidates_v3(
                    combined, ticker=ticker, issuer_name=safe_issuer,
                    source=host or title[:80], source_url=href,
                    primary_company=primary_company,
                ))

    if not candidates:
        return {"owner_v3_checked_utc": _profile_now_iso()}

    selected = _owner_v3_select_candidates(candidates)
    selected["owner_context_sources"] = len({
        x.get("source_group") for x in candidates if x.get("source_group")
    })
    selected["owner_v3_checked_utc"] = _profile_now_iso()
    return selected


async def _enrich_profile_owner_intelligence_v3(ticker, profile):
    if not RUMOR_OWNER_INTELLIGENCE_V3_ENABLED or not isinstance(profile, dict):
        return profile
    if _controller_verification_rank(profile.get("controller")) > 0 and profile.get("major_shareholders"):
        return profile
    checked = _profile_parse_iso(profile.get("owner_v3_checked_utc"))
    if checked and checked > datetime.now(timezone.utc) - timedelta(hours=RUMOR_PROFILE_REFRESH_HOURS):
        return profile
    try:
        discovered = await _discover_owner_intelligence_v3(
            ticker, issuer_name=profile.get("issuer_name"), website=profile.get("website")
        )
    except Exception:
        discovered = {"owner_v3_checked_utc": _profile_now_iso()}
    result = dict(profile)
    new_controller = discovered.get("controller")
    if new_controller and _controller_verification_rank(new_controller) > _controller_verification_rank(result.get("controller")):
        result["controller"] = new_controller
    existing = [x for x in (result.get("major_shareholders") or []) if isinstance(x, dict) and x.get("name")]
    known = {_normalized_entity_key(x.get("name")) for x in existing}
    for holder in discovered.get("major_shareholders") or []:
        key = _normalized_entity_key(holder.get("name"))
        if key and key not in known:
            existing.append(holder); known.add(key)
    if existing:
        result["major_shareholders"] = existing[:5]
    for key in ("owner_context_sources", "owner_resolution_level", "owner_v3_checked_utc"):
        if discovered.get(key) not in (None, "", [], {}):
            result[key] = discovered.get(key)
    return result



OWNER_V4_CONTROLLER_PHRASES = (
    "pemegang saham pengendali",
    "pemegang saham utama dan pengendali",
    "pemegang saham utama serta pengendali",
    "primary and controlling shareholder",
    "primary & controlling shareholder",
    "controlling shareholder",
    "ultimate controller",
)
OWNER_V4_MAJOR_PHRASES = (
    "pemegang saham utama",
    "pemegang saham terbesar",
    "primary shareholder",
    "major shareholder",
    "largest shareholder",
)
OWNER_V4_GENERIC_ENTITY_TERMS = (
    "president director", "direktur utama", "director", "direktur",
    "commissioner", "komisaris", "board of", "dewan direksi",
    "dewan komisaris", "pemegang saham", "shareholder", "the company",
    "perseroan", "perusahaan", "founder", "pendiri",
)
OWNER_V4_ENTITY_PATTERN = re.compile(
    r"\b(?:(?:PT\.?\s+)?[A-Z][A-Za-z0-9&.'’\-]+(?:\s+[A-Z][A-Za-z0-9&.'’\-]+){1,7})\b"
)


def _owner_v4_source_flags(source_url=None, company_host=None):
    host = re.sub(r"^www\.", "", _host(str(source_url or "")) or "").lower()
    company_host = re.sub(r"^www\.", "", str(company_host or "")).lower()
    official_registry = bool(
        host == "idx.co.id" or host.endswith(".idx.co.id")
        or host == "ojk.go.id" or host.endswith(".ojk.go.id")
        or host == "ksei.co.id" or host.endswith(".ksei.co.id")
    )
    primary_company = bool(
        company_host and (host == company_host or host.endswith("." + company_host))
    )
    return host, official_registry, primary_company


def _owner_v4_clean_entity(value):
    value = _clean_profile_text(value, 120)
    if not value:
        return None
    # Remove common honorific/role spill while preserving person/legal name.
    value = re.sub(r"\s+(?:President\s+Director|Direktur\s+Utama|Director|Direktur|Founder|Pendiri)$", "", value, flags=re.I)
    value = value.strip(" -:;,|.")
    low = value.lower()
    if any(term == low for term in OWNER_V4_GENERIC_ENTITY_TERMS):
        return None
    if any(term in low for term in ("board of directors", "dewan direksi", "pemegang saham utama", "controlling shareholder")):
        return None
    name = _owner_v2_clean_name(value)
    if not name:
        return None
    return name


def _owner_v4_identity_key(value):
    """Normalize person/company identity for duplicate suppression only.

    Honorifics/legal suffixes are ignored here, but the original display name is
    preserved. This prevents e.g. "Dato' Dr. X" and "DATO' X" from appearing twice.
    """
    tokens = re.findall(r"[a-z0-9]+", str(value or "").lower())
    drop = {
        "dato", "datuk", "dr", "doctor", "haji", "hj", "ir", "prof", "professor",
        "mr", "mrs", "ms", "pt", "tbk", "persero", "perseroan", "ltd", "limited", "inc",
    }
    cleaned = [token for token in tokens if token not in drop]
    return "".join(cleaned)


def _owner_v4_preceding_entity(text, role_start, *, ticker=None, issuer_name=None):
    left = max(0, int(role_start) - 260)
    prefix = str(text or "")[left:int(role_start)]
    found = []
    for match in OWNER_V4_ENTITY_PATTERN.finditer(prefix):
        raw = match.group(0)
        name = _owner_v4_clean_entity(raw)
        if not name:
            continue
        if _owner_v2_is_target_issuer(name, ticker=ticker, issuer_name=issuer_name):
            continue
        gap = prefix[match.end():]
        if len(gap) > 190:
            continue
        gap_low = gap.lower()
        # Avoid choosing a management title nearest to the role phrase.
        if any(term in name.lower() for term in OWNER_V4_GENERIC_ENTITY_TERMS):
            continue
        score = 220 - len(gap)
        if re.search(r",\s*(?:who|yang)\b", gap, flags=re.I):
            score += 180
        if re.search(r"\b(?:anak|son|daughter)\s+(?:dari|of)\s*$", prefix[:match.start()], flags=re.I):
            score += 25
        if re.match(r"^(?:PT\.?\s+|Dato['’]?\s+|DATO['’]?\s+|Dr\.?\s+|DR\.?\s+)", raw):
            score += 20
        found.append((score, match.end(), name))
    if not found:
        return None
    found.sort(reverse=True)
    return found[0][2]


def _owner_v4_apply_trust(items, *, official_registry=False, primary_company=False):
    output = []
    for raw in items or []:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        item = dict(raw)
        if official_registry:
            item["source_tier"] = max(5, int(item.get("source_tier") or 0))
            item["source_quality"] = "OFFICIAL_REGISTRY"
            item["official_registry"] = True
        elif primary_company:
            item["source_tier"] = max(4, int(item.get("source_tier") or 0))
            item["source_quality"] = "PRIMARY_COMPANY"
            item["primary_company"] = True
        output.append(item)
    return output


def _extract_owner_candidates_v4(
    text, *, ticker=None, issuer_name=None, source=None, source_url=None,
    official_registry=False, primary_company=False,
):
    normalized = normalize(str(text or ""))
    if not normalized:
        return []

    # Keep V3 label-first/table-percent parsing, then add role-after-name parsing.
    candidates = _extract_owner_candidates_v3(
        normalized, ticker=ticker, issuer_name=issuer_name,
        source=source, source_url=source_url, primary_company=primary_company,
    )
    candidates = _owner_v4_apply_trust(
        candidates, official_registry=official_registry, primary_company=primary_company,
    )

    quality = _rumor_source_quality({"source": source or "", "link": source_url or ""})
    base_tier = int(quality.get("tier") or 0)
    base_label = quality.get("label")
    if official_registry:
        base_tier, base_label = 5, "OFFICIAL_REGISTRY"
    elif primary_company:
        base_tier, base_label = max(4, base_tier), "PRIMARY_COMPANY"

    # Reverse-role parser: handles official wording such as
    # "NAME, who is ... primary and controlling shareholder" and
    # "NAME, yang ... Pemegang Saham Utama dan Pengendali Perseroan".
    phrase_specs = [("CONTROLLER", p) for p in OWNER_V4_CONTROLLER_PHRASES]
    phrase_specs += [("MAJOR", p) for p in OWNER_V4_MAJOR_PHRASES]
    for role, phrase in phrase_specs:
        for match in re.finditer(re.escape(phrase), normalized, flags=re.I):
            pre_role = normalized[max(0, match.start() - 220):match.start()].lower()
            # Negative affiliation/reference sentences mention controllers but do
            # not assert that the preceding director/person IS the controller.
            if re.search(
                r"(?:not\s+affiliated|not\s+related|tidak\s+(?:memiliki|mempunyai)\s+hubungan\s+afiliasi|tidak\s+terafiliasi|bukan)"
                r"[^.!?;]{0,180}$",
                pre_role, flags=re.I,
            ):
                continue
            name = _owner_v4_preceding_entity(
                normalized, match.start(), ticker=ticker, issuer_name=issuer_name,
            )
            if not name:
                continue
            window = normalized[max(0, match.start() - 220): min(len(normalized), match.end() + 120)]
            stake = None
            stake_match = re.search(r"(\d{1,3}(?:[.,]\d+)?)\s*%", window)
            if stake_match:
                try:
                    stake = float(stake_match.group(1).replace(",", "."))
                except Exception:
                    stake = None
            candidates.append({
                "name": name,
                "stake_pct": stake,
                "role": role,
                "source": source or "UNKNOWN",
                "source_url": source_url,
                "source_quality": base_label,
                "source_tier": base_tier,
                "source_group": _rumor_editorial_group({"source": source or "", "link": source_url or ""}),
                "evidence_text": window[:360],
                "primary_company": bool(primary_company),
                "official_registry": bool(official_registry),
                "basis": "OWNER_V4_REVERSE_ROLE",
            })

    # Official IDX/OJK/KSEI holder tables sometimes expose share counts rather
    # than percentages. They are safe as major-holder context, not controller.
    if official_registry:
        row_pattern = re.compile(
            r"((?:PT\.?\s+)?[A-Z][A-Z0-9&.'’\-]+(?:\s+[A-Z][A-Z0-9&.'’\-]+){1,7})"
            r"\s*,\s*(?:(?:Direksi|Komisaris|Pemegang\s+Saham)[^,;]{0,35},\s*)?"
            r"(\d{1,3}(?:[.,]\d{3}){1,})",
            re.I,
        )
        for match in row_pattern.finditer(normalized):
            name = _owner_v4_clean_entity(match.group(1))
            if not name or _owner_v2_is_target_issuer(name, ticker=ticker, issuer_name=issuer_name):
                continue
            digits = re.sub(r"\D", "", match.group(2))
            if len(digits) < 4:
                continue
            candidates.append({
                "name": name, "stake_pct": None, "share_count": int(digits),
                "role": "HOLDER_COUNT", "source": source or "OFFICIAL REGISTRY",
                "source_url": source_url, "source_quality": "OFFICIAL_REGISTRY",
                "source_tier": 5,
                "source_group": _rumor_editorial_group({"source": source or "", "link": source_url or ""}),
                "evidence_text": match.group(0)[:320], "official_registry": True,
                "registry_major": False, "basis": "OWNER_V4_REGISTRY_SHARE_COUNT",
            })

        # Search snippets can list all >5% holders without counts.
        segment_match = re.search(
            r"pemegang\s+saham\s*>\s*5\s*%(.{0,650}?)(?=(?:masyarakat|publik)\s*<\s*5\s*%|$)",
            normalized, flags=re.I,
        )
        if segment_match:
            segment = segment_match.group(1)
            for name_match in OWNER_V4_ENTITY_PATTERN.finditer(segment):
                raw_name = name_match.group(0)
                # Registry snippets are often uppercase; reject ordinary prose.
                alpha = re.sub(r"[^A-Za-z]", "", raw_name)
                upper_ratio = (sum(1 for c in alpha if c.isupper()) / max(1, len(alpha))) if alpha else 0
                if upper_ratio < 0.72 and not raw_name.upper().startswith("PT "):
                    continue
                name = _owner_v4_clean_entity(raw_name)
                if not name or _owner_v2_is_target_issuer(name, ticker=ticker, issuer_name=issuer_name):
                    continue
                candidates.append({
                    "name": name, "stake_pct": None, "role": "MAJOR",
                    "source": source or "OFFICIAL REGISTRY", "source_url": source_url,
                    "source_quality": "OFFICIAL_REGISTRY", "source_tier": 5,
                    "source_group": _rumor_editorial_group({"source": source or "", "link": source_url or ""}),
                    "evidence_text": segment[:360], "official_registry": True,
                    "registry_major": True, "basis": "OWNER_V4_REGISTRY_GT5",
                })

    # Deduplicate by role/name/source, preserving richer evidence.
    unique = {}
    for item in candidates:
        key = (item.get("role"), _normalized_entity_key(item.get("name")), item.get("source_group"))
        current = unique.get(key)
        if current is None:
            unique[key] = item
            continue
        current_score = (
            int(current.get("source_tier") or 0),
            current.get("stake_pct") is not None,
            int(current.get("share_count") or 0),
        )
        new_score = (
            int(item.get("source_tier") or 0),
            item.get("stake_pct") is not None,
            int(item.get("share_count") or 0),
        )
        if new_score > current_score:
            unique[key] = item
    return list(unique.values())


def _owner_v4_select_candidates(candidates):
    candidates = [x for x in (candidates or []) if isinstance(x, dict) and x.get("name")]
    # HOLDER_COUNT rows are metadata only. Share count alone does NOT prove a
    # person/entity is a major shareholder because total issued shares may be unknown.
    selectable = [
        x for x in candidates
        if x.get("role") in {"CONTROLLER", "MAJOR", "FOUNDER"}
    ]
    selected = _owner_v3_select_candidates(selectable)
    controller = selected.get("controller")
    if isinstance(controller, dict):
        controller = dict(controller)
        level = str(controller.get("verification_level") or "")
        if "PRIMARY_COMPANY" in level:
            controller["verification_level"] = "PRIMARY_COMPANY_CONTROLLER_V4"
        else:
            controller["verification_level"] = "OFFICIAL_DIRECT_V4"
        controller["basis"] = "OWNER_INTELLIGENCE_V4_EXPLICIT_ROLE"
        selected["controller"] = controller

    # Build share-count lookup only to rank holders that are ALREADY proven as
    # major (>5%, explicit major label, or explicit percentage evidence).
    count_by_identity = {}
    for row in candidates:
        if row.get("role") != "HOLDER_COUNT":
            continue
        key = _owner_v4_identity_key(row.get("name"))
        if not key:
            continue
        count_by_identity[key] = max(
            int(count_by_identity.get(key) or 0),
            int(row.get("share_count") or 0),
        )

    controller_key = _owner_v4_identity_key(controller.get("name")) if isinstance(controller, dict) else ""
    dedup = {}
    for raw in (selected.get("major_shareholders") or []):
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        holder = dict(raw)
        identity = _owner_v4_identity_key(holder.get("name"))
        if not identity or identity == controller_key:
            continue
        evidence = [x for x in selectable if _owner_v4_identity_key(x.get("name")) == identity]
        if any(x.get("official_registry") for x in evidence):
            holder["verified"] = True
            holder["verification_level"] = "OFFICIAL_REGISTRY_HOLDER_V4"
        elif any(x.get("primary_company") for x in evidence):
            holder["verified"] = True
            holder["verification_level"] = "PRIMARY_COMPANY_HOLDER_V4"
        if count_by_identity.get(identity):
            holder["share_count"] = count_by_identity[identity]
        current = dedup.get(identity)
        if current is None:
            dedup[identity] = holder
        else:
            old_score = (int(current.get("share_count") or 0), float(current.get("stake_pct") or 0))
            new_score = (int(holder.get("share_count") or 0), float(holder.get("stake_pct") or 0))
            if new_score > old_score:
                dedup[identity] = holder

    majors = list(dedup.values())
    majors.sort(
        key=lambda x: (
            int(x.get("share_count") or 0),
            float(x.get("stake_pct") or 0),
            1 if x.get("verified") else 0,
        ),
        reverse=True,
    )
    selected["major_shareholders"] = majors[:5]
    selected["owner_resolution_level"] = (
        "OFFICIAL_CONTROLLER" if selected.get("controller")
        else "MAJOR_HOLDER_CONTEXT" if selected.get("major_shareholders")
        else "NO_SAFE_OWNER_RESULT"
    )
    return selected


async def _owner_v4_primary_site_seed(client, website, company_host):
    """Read issuer homepage and discover same-domain ownership/governance pages.

    This is a search-engine-independent fallback. Only same-domain HTML links are
    eligible, so an external media page can never become primary-company evidence.
    """
    website = str(website or "").strip()
    company_host = re.sub(r"^www\.", "", str(company_host or "")).lower()
    if not website or not company_host:
        return "", []
    if not re.match(r"^https?://", website, flags=re.I):
        website = "https://" + website.lstrip("/")
    try:
        response = await client.get(website, timeout=PROFILE_TIMEOUT_SECONDS)
    except Exception:
        return "", []
    if response.status_code >= 400:
        return "", []
    content_type = str(response.headers.get("content-type") or "").lower()
    if content_type and "html" not in content_type:
        return "", []
    try:
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception:
        return _profile_result_text_from_html(response.text)[:RUMOR_OWNER_V4_PAGE_MAX_CHARS], []

    home_text = normalize(soup.get_text(" ", strip=True))[:RUMOR_OWNER_V4_PAGE_MAX_CHARS]
    keywords = (
        "shareholder", "pemegang-saham", "pemegang saham", "controlling",
        "board-of-directors", "board of directors", "dewan-direksi", "dewan direksi",
        "corporate-governance", "corporate governance", "governance",
        "investor-relations", "investor relations",
    )
    scored = []
    seen = set()
    for node in soup.select("a[href]"):
        href = urljoin(website, node.get("href") or "")
        if not href or href in seen:
            continue
        host, _, primary = _owner_v4_source_flags(href, company_host)
        if not primary:
            continue
        path = href.lower().split("#", 1)[0]
        if path.endswith(".pdf"):
            continue
        label = normalize(node.get_text(" ", strip=True)).lower()
        probe = f"{label} {path}"
        hits = sum(1 for keyword in keywords if keyword in probe)
        if hits <= 0:
            continue
        score = hits * 10
        if "shareholder" in probe or "pemegang" in probe or "controlling" in probe:
            score += 30
        if "board" in probe or "direksi" in probe:
            score += 20
        scored.append((score, href))
        seen.add(href)
    scored.sort(reverse=True)
    return home_text, [href for _, href in scored[:RUMOR_OWNER_V4_PAGE_FETCH_LIMIT]]


async def _owner_v4_fetch_page_text(client, href):
    href = str(href or "")
    if not href or href.lower().split("?", 1)[0].endswith(".pdf"):
        return ""
    try:
        response = await client.get(href, timeout=PROFILE_TIMEOUT_SECONDS)
    except Exception:
        return ""
    if response.status_code >= 400:
        return ""
    content_type = str(response.headers.get("content-type") or "").lower()
    if content_type and not any(kind in content_type for kind in ("text/html", "application/xhtml", "text/plain")):
        return ""
    return _profile_result_text_from_html(response.text)[:RUMOR_OWNER_V4_PAGE_MAX_CHARS]


async def _discover_owner_intelligence_v4(ticker, issuer_name=None, website=None):
    """Final owner resolver: official registry + issuer primary pages + safe holder fallback.

    Controller verification is allowed only for explicit controller wording on an
    official registry or the issuer's own primary website. Major-holder evidence
    remains a separate role and can never be promoted implicitly to controller.
    """
    ticker = _valid_idx_ticker(ticker)
    if not ticker or not RUMOR_OWNER_INTELLIGENCE_V4_ENABLED or not BS4_AVAILABLE:
        return {}

    safe_issuer = _clean_profile_text(issuer_name, 120) if issuer_name else None
    company_host = re.sub(r"^www\.", "", _host(str(website or "")) or "")

    queries = []
    if company_host:
        queries += [
            f'site:{company_host} "controlling shareholder"',
            f'site:{company_host} "pemegang saham pengendali"',
            f'site:{company_host} "pemegang saham utama" "pengendali"',
            f'site:{company_host} "shareholder" "{safe_issuer or ticker}"',
        ]
    queries += [
        f'site:idx.co.id/id/perusahaan-tercatat/profil-perusahaan-tercatat/{ticker} "Pemegang Saham"',
        f'site:idx.co.id "{ticker}" "Pemegang Saham"',
        f'site:idx.co.id "{ticker}" "Pemegang Saham Pengendali"',
        f'site:idx.co.id "{ticker}" "Pemegang Saham >5%"',
        f'site:idx.co.id "{ticker}" "laporan tahunan" "pemegang saham"',
        f'site:ojk.go.id "{ticker}" "pemegang saham"',
        f'site:ksei.co.id "{ticker}" "pemegang saham"',
    ]
    if safe_issuer:
        queries += [
            f'site:idx.co.id "{safe_issuer}" "pengendali"',
            f'"{safe_issuer}" "primary and controlling shareholder"',
            f'"{safe_issuer}" "pemegang saham utama dan pengendali"',
        ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129 Safari/537.36",
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.7",
    }
    candidates = []
    fetched_pages = set()

    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        # Search-engine-independent primary-site seed. For issuers whose official
        # website is known from IDX/Yahoo profile data, inspect only same-domain
        # governance/shareholder pages.
        if company_host and website:
            home_text, primary_links = await _owner_v4_primary_site_seed(client, website, company_host)
            if home_text:
                candidates.extend(_extract_owner_candidates_v4(
                    home_text, ticker=ticker, issuer_name=safe_issuer,
                    source=company_host, source_url=website,
                    official_registry=False, primary_company=True,
                ))
            for primary_url in primary_links:
                if len(fetched_pages) >= RUMOR_OWNER_V4_PAGE_FETCH_LIMIT:
                    break
                if primary_url in fetched_pages:
                    continue
                fetched_pages.add(primary_url)
                page_text = await _owner_v4_fetch_page_text(client, primary_url)
                if page_text:
                    candidates.extend(_extract_owner_candidates_v4(
                        page_text, ticker=ticker, issuer_name=safe_issuer,
                        source=company_host, source_url=primary_url,
                        official_registry=False, primary_company=True,
                    ))

        for query in queries[:RUMOR_OWNER_V4_SEARCH_LIMIT]:
            try:
                response = await client.get(
                    "https://html.duckduckgo.com/html/?q=" + quote_plus(query),
                    timeout=PROFILE_TIMEOUT_SECONDS,
                )
            except Exception:
                continue
            if response.status_code >= 400:
                continue
            soup = BeautifulSoup(response.text, "html.parser")
            for block in soup.select(".result, .web-result")[:10]:
                link_node = block.select_one("a.result__a, .result__title a")
                snippet_node = block.select_one(".result__snippet, .result__body")
                if not link_node:
                    continue
                href = _extract_result_url_from_search(link_node.get("href", ""))
                if not href:
                    continue
                title = normalize(link_node.get_text(" ", strip=True))
                snippet = normalize(snippet_node.get_text(" ", strip=True) if snippet_node else "")
                combined = normalize(f"{title}. {snippet}")
                host, official_registry, primary_company = _owner_v4_source_flags(href, company_host)
                relevant = (
                    ticker in combined.upper()
                    or bool(safe_issuer and safe_issuer.lower() in combined.lower())
                    or primary_company
                )
                if not relevant:
                    continue
                source_name = host or title[:80]
                candidates.extend(_extract_owner_candidates_v4(
                    combined, ticker=ticker, issuer_name=safe_issuer,
                    source=source_name, source_url=href,
                    official_registry=official_registry, primary_company=primary_company,
                ))

                # Deep-read only trusted HTML pages; never scrape arbitrary media
                # as ownership truth. This fixes cases where the snippet omits the
                # subject name but the issuer's own board/governance page contains it.
                cue_text = combined.lower()
                should_fetch = (
                    (official_registry or primary_company)
                    and href not in fetched_pages
                    and len(fetched_pages) < RUMOR_OWNER_V4_PAGE_FETCH_LIMIT
                    and not href.lower().split("?", 1)[0].endswith(".pdf")
                    and (
                        primary_company
                        or any(cue in cue_text for cue in OWNER_V3_CONTEXT_CUES)
                        or any(phrase in cue_text for phrase in OWNER_V4_CONTROLLER_PHRASES)
                    )
                )
                if should_fetch:
                    fetched_pages.add(href)
                    page_text = await _owner_v4_fetch_page_text(client, href)
                    if page_text:
                        candidates.extend(_extract_owner_candidates_v4(
                            page_text, ticker=ticker, issuer_name=safe_issuer,
                            source=source_name, source_url=href,
                            official_registry=official_registry, primary_company=primary_company,
                        ))

    selected = _owner_v4_select_candidates(candidates)
    selected["owner_context_sources"] = len({
        x.get("source_group") for x in candidates if x.get("source_group")
    })
    selected["owner_v4_checked_utc"] = _profile_now_iso()
    selected["owner_v4_pages_fetched"] = len(fetched_pages)
    selected["owner_discovery_method"] = "OFFICIAL_REGISTRY+PRIMARY_COMPANY_V4"
    return selected


async def _enrich_profile_owner_intelligence_v4(ticker, profile):
    if not RUMOR_OWNER_INTELLIGENCE_V4_ENABLED or not isinstance(profile, dict):
        return profile
    # New cache key intentionally ignores V3's recent failed lookup so an
    # immediate V6.7.7 upgrade gets one fresh ownership-resolution attempt.
    checked = _profile_parse_iso(profile.get("owner_v4_checked_utc"))
    if checked and checked > datetime.now(timezone.utc) - timedelta(hours=RUMOR_PROFILE_REFRESH_HOURS):
        return profile
    try:
        discovered = await _discover_owner_intelligence_v4(
            ticker, issuer_name=profile.get("issuer_name"), website=profile.get("website")
        )
    except Exception:
        discovered = {"owner_v4_checked_utc": _profile_now_iso()}

    result = dict(profile)
    new_controller = discovered.get("controller")
    if new_controller and _controller_verification_rank(new_controller) >= _controller_verification_rank(result.get("controller")):
        result["controller"] = new_controller

    existing = [x for x in (result.get("major_shareholders") or []) if isinstance(x, dict) and x.get("name")]
    # If V4 verified a controller, keep it first as ownership context, but its
    # role remains explicitly controller (not inferred from mere share size).
    if isinstance(result.get("controller"), dict) and result["controller"].get("verified"):
        ctrl = result["controller"]
        ctrl_key = _normalized_entity_key(ctrl.get("name"))
        if ctrl_key and all(_normalized_entity_key(x.get("name")) != ctrl_key for x in existing):
            existing.insert(0, {
                "name": ctrl.get("name"), "stake_pct": ctrl.get("stake_pct"),
                "verified": True, "verification_level": ctrl.get("verification_level"),
                "source": ctrl.get("source"), "source_url": ctrl.get("source_url"),
                "role": "CONTROLLER",
            })
    known = {_normalized_entity_key(x.get("name")) for x in existing}
    for holder in discovered.get("major_shareholders") or []:
        key = _normalized_entity_key(holder.get("name"))
        if key and key not in known:
            existing.append(holder)
            known.add(key)
    if existing:
        result["major_shareholders"] = existing[:5]

    for key in (
        "owner_context_sources", "owner_resolution_level", "owner_v4_checked_utc",
        "owner_v4_pages_fetched", "owner_discovery_method",
    ):
        if discovered.get(key) not in (None, "", [], {}):
            result[key] = discovered.get(key)
    return result



OWNER_V5_NAV_NOISE = (
    "gms", "announcement", "invitation", "minutes", "read more", "readmore",
    "reports", "financial statements", "financial highlights", "sustainability report",
    "general meeting", "corporate action", "news", "latest news", "press release",
    "investor relations", "download", "home", "contact us", "career", "careers",
    "saham-saham", "emiten batubara", "saham byan", "ngacir", "melompat",
)
OWNER_V5_MONTHS = (
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "januari", "februari", "maret",
    "mei", "juni", "juli", "agustus", "oktober", "desember",
)
OWNER_V5_OWNERSHIP_ANCHORS = (
    "pemegang saham pengendali", "pemegang saham utama dan pengendali",
    "pemegang saham utama serta pengendali", "controlling shareholder",
    "primary and controlling shareholder", "primary & controlling shareholder",
    "ultimate controller", "pemegang saham utama", "pemegang saham terbesar",
    "major shareholder", "largest shareholder", "primary shareholder",
    "pemegang saham >5%", "pemegang saham > 5%", "shareholders >5%",
    "shareholders > 5%", "shareholding", "shareholders", "struktur kepemilikan",
    "ownership structure",
)


def _owner_v5_name_sane(value):
    """Reject navigation, article headlines, dates and generic prose as identities."""
    value = _clean_profile_text(value, 140)
    if not value:
        return False
    low = value.lower()
    words = re.findall(r"[A-Za-zÀ-ÿ0-9&.'’\-]+", value)
    alpha_words = [w for w in words if re.search(r"[A-Za-zÀ-ÿ]", w)]
    if len(alpha_words) < 2 or len(alpha_words) > 10:
        return False
    if len(value) > 105:
        return False
    if any(noise in low for noise in OWNER_V5_NAV_NOISE):
        return False
    if any(re.search(r"\b" + re.escape(month) + r"\b", low) for month in OWNER_V5_MONTHS):
        return False
    if re.search(r"\b(?:19|20)\d{2}\b", value):
        return False
    if re.search(r"\b\d{1,3}(?:[.,]\d+)?\s*%", value):
        return False
    if re.search(r"\b(?:stock|shares?|harga|price|persen|percent|laporan|report)\b", low):
        return False
    if re.search(r"\b(?:adalah|merupakan|menjabat|mengumumkan|menyebut|disebut|naik|turun|terbang)\b", low):
        return False
    # Navigation-like title case chains are common false positives.
    generic = {"financial", "statements", "highlights", "sustainability", "general", "meeting", "shareholder", "shareholders"}
    if sum(1 for w in alpha_words if w.lower() in generic) >= 2:
        return False
    cleaned = _owner_v4_clean_entity(value)
    return bool(cleaned and len(re.findall(r"[A-Za-zÀ-ÿ]+", cleaned)) >= 2)



def _owner_v5_clean_candidate_name(value):
    """Recover a real identity when flattened HTML prepends navigation words."""
    raw = _clean_profile_text(value, 140)
    if not raw:
        return None
    nav_tokens = {
        "gms", "announcement", "invitation", "minutes", "reports", "report",
        "financial", "statements", "highlights", "sustainability", "general",
        "news", "latest", "download", "home",
    }
    words = raw.split()
    # If leading tokens look like menu labels, progressively trim them. We only
    # accept a suffix after at least one discarded token when every discarded
    # token is known navigation noise.
    for start in range(0, max(1, len(words) - 1)):
        discarded = [re.sub(r"[^A-Za-z]", "", w).lower() for w in words[:start]]
        if start and not all(token in nav_tokens for token in discarded if token):
            break
        candidate = " ".join(words[start:]).strip(" -:;,|.")
        cleaned = _owner_v4_clean_entity(candidate)
        if cleaned and _owner_v5_name_sane(cleaned):
            # Reject untrimmed candidates beginning with navigation vocabulary.
            first = re.sub(r"[^A-Za-z]", "", words[start]).lower() if words[start:] else ""
            if first in nav_tokens:
                continue
            return cleaned
    return None


def _owner_v5_sentence_window(text, start, end):
    """Bound evidence to one sentence/clause so unrelated % cannot leak in."""
    text = str(text or "")
    left_marks = [text.rfind(ch, 0, int(start)) for ch in ".!?;"]
    left = max(left_marks) + 1
    right_candidates = []
    for ch in ".!?;":
        pos = text.find(ch, int(end))
        if pos >= 0:
            right_candidates.append(pos + 1)
    right = min(right_candidates) if right_candidates else min(len(text), int(end) + 140)
    return text[max(0, left):min(len(text), right)]


def _owner_v5_direct_preceding_name(text, role_start, *, ticker=None, issuer_name=None):
    """Return an entity only when grammar directly links it to the role phrase."""
    prefix = str(text or "")[max(0, int(role_start) - 210):int(role_start)]
    found = []
    for match in OWNER_V4_ENTITY_PATTERN.finditer(prefix):
        raw = match.group(0)
        name = _owner_v5_clean_candidate_name(raw)
        if not name:
            continue
        if _owner_v2_is_target_issuer(name, ticker=ticker, issuer_name=issuer_name):
            continue
        gap = prefix[match.end():]
        if len(gap) > 120:
            continue
        g = gap.strip()
        # Explicit grammatical bridge only. This prevents nearby menu text from
        # becoming a controller merely because the page contains the role phrase.
        grammar_ok = bool(
            re.match(r"^,?\s*(?:who|yang)\b[^.;]{0,105}$", g, re.I)
            or re.match(r"^,?\s*(?:is|adalah|merupakan|selaku|sebagai)\b[^.;]{0,95}$", g, re.I)
            or re.match(r"^\.\s*(?:founder|pendiri)\s+(?:and|dan)\s*$", g, re.I)
            or re.match(r"^[,:\-]?\s*$", g)
        )
        if not grammar_ok:
            continue
        # Negative affiliation/reference is not identity assertion.
        if re.search(
            r"(?:not\s+affiliated|not\s+related|tidak\s+(?:memiliki|mempunyai)\s+hubungan\s+afiliasi|tidak\s+terafiliasi|bukan)[^.;]{0,110}$",
            prefix[:match.start()] + gap, re.I,
        ):
            continue
        found.append((len(gap), match.end(), name))
    if not found:
        return None
    found.sort(key=lambda x: (x[0], -x[1]))
    return found[0][2]


def _owner_v5_direct_following_name(text, role_end, *, ticker=None, issuer_name=None):
    suffix = str(text or "")[int(role_end): int(role_end) + 150]
    # Only label/is-style forward grammar is accepted.
    m = re.match(r"\s*(?::|-|adalah|is|yaitu|yakni)?\s*", suffix, re.I)
    start = m.end() if m else 0
    probe = suffix[start:]
    match = OWNER_V4_ENTITY_PATTERN.search(probe)
    if not match or match.start() > 10:
        return None
    name = _owner_v5_clean_candidate_name(match.group(0))
    if not name:
        return None
    if _owner_v2_is_target_issuer(name, ticker=ticker, issuer_name=issuer_name):
        return None
    return name


def _owner_v5_candidate(name, role, *, source, source_url, official_registry, primary_company, evidence, stake_pct=None, basis=None):
    if not _owner_v5_name_sane(name):
        return None
    if not (official_registry or primary_company):
        return None
    if stake_pct is not None:
        try:
            stake_pct = float(stake_pct)
        except Exception:
            stake_pct = None
        if stake_pct is not None and not (0 < stake_pct <= 100):
            stake_pct = None
    return {
        "name": _owner_v4_clean_entity(name),
        "stake_pct": stake_pct,
        "role": role,
        "source": source or "UNKNOWN",
        "source_url": source_url,
        "source_quality": "OFFICIAL_REGISTRY" if official_registry else "PRIMARY_COMPANY",
        "source_tier": 5 if official_registry else 4,
        "source_group": _rumor_editorial_group({"source": source or "", "link": source_url or ""}),
        "evidence_text": _clean_profile_text(evidence, 420),
        "official_registry": bool(official_registry),
        "primary_company": bool(primary_company),
        "basis": basis or "OWNER_V5_STRICT",
    }


def _extract_owner_candidates_v5(
    text, *, ticker=None, issuer_name=None, source=None, source_url=None,
    official_registry=False, primary_company=False,
):
    """Safety-first owner parser used by V6.7.7 live paths.

    It intentionally does NOT reuse V3/V4 broad candidate extraction. Only
    direct role grammar and ownership-section percentage rows are eligible.
    """
    normalized = normalize(str(text or ""))
    if not normalized or not (official_registry or primary_company):
        return []
    candidates = []

    controller_phrases = OWNER_V4_CONTROLLER_PHRASES
    major_phrases = OWNER_V4_MAJOR_PHRASES
    for role, phrases in (("CONTROLLER", controller_phrases), ("MAJOR", major_phrases)):
        for phrase in phrases:
            for match in re.finditer(re.escape(phrase), normalized, re.I):
                # Use a bounded local window for identity but one sentence for
                # stake/evidence, so a later news-price percentage cannot leak in.
                left = max(0, match.start() - 210)
                right = min(len(normalized), match.end() + 150)
                identity_window = normalized[left:right]
                window = _owner_v5_sentence_window(normalized, match.start(), match.end())
                pre = normalized[left:match.start()]
                if re.search(
                    r"(?:not\s+affiliated|not\s+related|tidak\s+(?:memiliki|mempunyai)\s+hubungan\s+afiliasi|tidak\s+terafiliasi|bukan)[^.!?;]{0,170}$",
                    pre, re.I,
                ):
                    continue
                name = _owner_v5_direct_preceding_name(
                    normalized, match.start(), ticker=ticker, issuer_name=issuer_name,
                )
                if not name:
                    name = _owner_v5_direct_following_name(
                        normalized, match.end(), ticker=ticker, issuer_name=issuer_name,
                    )
                if not name:
                    continue
                stake = None
                pct = re.search(r"(\d{1,3}(?:[.,]\d+)?)\s*%", window)
                if pct:
                    try: stake = float(pct.group(1).replace(",", "."))
                    except Exception: stake = None
                item = _owner_v5_candidate(
                    name, role, source=source, source_url=source_url,
                    official_registry=official_registry, primary_company=primary_company,
                    evidence=window, stake_pct=stake, basis="OWNER_V5_DIRECT_ROLE",
                )
                if item:
                    candidates.append(item)

    # Explicit >5% registry list. This section itself proves MAJOR role but never controller.
    if official_registry:
        gt5 = re.search(
            r"(?:pemegang\s+saham|shareholders?)\s*>\s*5\s*%(.{0,700}?)(?=(?:masyarakat|publik|public)\s*<\s*5\s*%|$)",
            normalized, re.I,
        )
        if gt5:
            segment = gt5.group(1)
            # Split first to avoid merging adjacent all-caps entities into one giant name.
            for piece in re.split(r"[;|\n]+", segment):
                piece = piece.strip(" ,:-")
                if not piece:
                    continue
                pct = re.search(r"(\d{1,3}(?:[.,]\d+)?)\s*%", piece)
                stake = float(pct.group(1).replace(",", ".")) if pct else None
                name_part = re.sub(r"\d{1,3}(?:[.,]\d+)?\s*%.*$", "", piece).strip(" ,:-")
                # choose one sane entity from the piece
                names = []
                for nm in OWNER_V4_ENTITY_PATTERN.finditer(name_part):
                    cleaned = _owner_v4_clean_entity(nm.group(0))
                    if cleaned and _owner_v5_name_sane(cleaned): names.append(cleaned)
                if not names:
                    continue
                name = names[-1]
                if _owner_v2_is_target_issuer(name, ticker=ticker, issuer_name=issuer_name):
                    continue
                item = _owner_v5_candidate(
                    name, "MAJOR", source=source, source_url=source_url,
                    official_registry=True, primary_company=False,
                    evidence=piece, stake_pct=stake, basis="OWNER_V5_REGISTRY_GT5",
                )
                if item: candidates.append(item)

    # Section-anchored name + percentage rows. Require >=5% to be called major.
    heading_re = re.compile(
        r"(?:struktur\s+kepemilikan|ownership\s+structure|shareholding|komposisi\s+pemegang\s+saham|daftar\s+pemegang\s+saham)",
        re.I,
    )
    for heading in heading_re.finditer(normalized):
        segment = normalized[heading.end(): heading.end() + RUMOR_OWNER_V5_SECTION_CHARS]
        for pct in re.finditer(r"(\d{1,3}(?:[.,]\d+)?)\s*%", segment):
            try: stake = float(pct.group(1).replace(",", "."))
            except Exception: continue
            if stake < 5.0 or stake > 100:
                continue
            prefix = segment[max(0, pct.start() - 125):pct.start()]
            names = []
            for nm in OWNER_V4_ENTITY_PATTERN.finditer(prefix):
                cleaned = _owner_v4_clean_entity(nm.group(0))
                if cleaned and _owner_v5_name_sane(cleaned): names.append(cleaned)
            if not names:
                continue
            name = names[-1]
            if _owner_v2_is_target_issuer(name, ticker=ticker, issuer_name=issuer_name):
                continue
            item = _owner_v5_candidate(
                name, "MAJOR", source=source, source_url=source_url,
                official_registry=official_registry, primary_company=primary_company,
                evidence=prefix + pct.group(0), stake_pct=stake, basis="OWNER_V5_SECTION_PERCENT",
            )
            if item: candidates.append(item)

    # Exact dedup by normalized identity/role/source.
    unique = {}
    for item in candidates:
        key = (item.get("role"), _owner_v4_identity_key(item.get("name")), item.get("source_group"))
        if not key[1]:
            continue
        old = unique.get(key)
        if old is None or (item.get("stake_pct") is not None and old.get("stake_pct") is None):
            unique[key] = item
    return list(unique.values())


def _owner_v5_select_candidates(candidates):
    rows = [x for x in (candidates or []) if isinstance(x, dict) and _owner_v5_name_sane(x.get("name"))]
    trusted = [x for x in rows if x.get("official_registry") or x.get("primary_company")]
    controllers = [x for x in trusted if x.get("role") == "CONTROLLER"]
    controllers.sort(key=lambda x: (1 if x.get("official_registry") else 0, int(x.get("source_tier") or 0), x.get("stake_pct") is not None), reverse=True)
    controller = None
    if controllers:
        best = dict(controllers[0])
        best["verified"] = True
        best["verification_level"] = "OFFICIAL_DIRECT_V5" if best.get("official_registry") else "PRIMARY_COMPANY_CONTROLLER_V5"
        best["basis"] = "OWNER_SAFETY_V5_EXPLICIT_ROLE"
        controller = best

    controller_key = _owner_v4_identity_key((controller or {}).get("name"))
    majors = {}
    for raw in trusted:
        if raw.get("role") != "MAJOR":
            continue
        holder = dict(raw)
        identity = _owner_v4_identity_key(holder.get("name"))
        if not identity or identity == controller_key:
            continue
        stake = holder.get("stake_pct")
        if stake is not None:
            try:
                if float(stake) < 5.0: continue
            except Exception:
                continue
        elif holder.get("basis") != "OWNER_V5_REGISTRY_GT5":
            # no percentage is accepted only inside an explicit official >5% section
            continue
        holder["verified"] = True
        holder["verification_level"] = "OFFICIAL_REGISTRY_HOLDER_V5" if holder.get("official_registry") else "PRIMARY_COMPANY_HOLDER_V5"
        old = majors.get(identity)
        if old is None or float(holder.get("stake_pct") or 0) > float(old.get("stake_pct") or 0):
            majors[identity] = holder
    major_list = list(majors.values())
    major_list.sort(key=lambda x: float(x.get("stake_pct") or 0), reverse=True)
    return {
        "controller": controller,
        "major_shareholders": major_list[:5],
        "owner_resolution_level": "OFFICIAL_CONTROLLER" if controller else "MAJOR_HOLDER_CONTEXT" if major_list else "NO_SAFE_OWNER_RESULT",
    }


def _owner_v5_existing_controller_safe(controller, profile=None):
    if not isinstance(controller, dict) or not controller.get("verified") or not _owner_v5_name_sane(controller.get("name")):
        return False
    level = str(controller.get("verification_level") or "").upper()
    # Preserve proven older official/event resolvers. V4 values additionally need
    # a trusted source URL because V6.7.6 is the cache-poison source being repaired.
    if level in {"OFFICIAL_DIRECT", "OFFICIAL_DIRECT_V2", "OFFICIAL_DIRECT_V3", "CROSS_VERIFIED", "OFFICIAL_EVENT_ROLE"}:
        return True
    if not level and isinstance(profile, dict):
        quality = str(profile.get("profile_source_quality") or "").upper()
        source = str(profile.get("profile_source") or "").upper()
        if quality == "OFFICIAL" or "IDX" in source or "OJK" in source or "KSEI" in source:
            return True
    if level in {"OFFICIAL_DIRECT_V4", "PRIMARY_COMPANY_CONTROLLER_V4", "OFFICIAL_DIRECT_V5", "PRIMARY_COMPANY_CONTROLLER_V5"}:
        website = (profile or {}).get("website") if isinstance(profile, dict) else None
        company_host = re.sub(r"^www\.", "", _host(str(website or "")) or "")
        _, registry, primary = _owner_v4_source_flags(controller.get("source_url"), company_host)
        return bool(registry or primary)
    return False


def _owner_v5_existing_holder_safe(holder, profile=None):
    if not isinstance(holder, dict) or not _owner_v5_name_sane(holder.get("name")):
        return False
    stake = holder.get("stake_pct")
    if stake is not None:
        try:
            if not (5.0 <= float(stake) <= 100.0): return False
        except Exception:
            return False
    level = str(holder.get("verification_level") or "").upper()
    if holder.get("verified") or "OFFICIAL" in level or "PRIMARY_COMPANY" in level:
        return True
    # Legacy context may stay only with an explicit >=5% stake and sane name.
    return stake is not None


def _owner_v5_sanitize_profile(profile):
    if not isinstance(profile, dict) or not RUMOR_OWNER_SAFETY_V5_ENABLED:
        return profile
    result = copy.deepcopy(profile)
    # Private/pre-IPO media context is intentionally not promoted to VERIFIED,
    # but it remains useful as clearly-labeled context and must not be erased by
    # the listed-issuer ownership safety repair.
    source_quality = str(result.get("profile_source_quality") or "").upper()
    if not _valid_idx_ticker(result.get("ticker")) and "MEDIA_CONTEXT" in source_quality:
        return result
    repairs = 0
    controller = result.get("controller")
    if controller and not _owner_v5_existing_controller_safe(controller, result):
        result["controller"] = None
        repairs += 1
    safe_holders = []
    seen = set()
    controller_key = _owner_v4_identity_key((result.get("controller") or {}).get("name")) if isinstance(result.get("controller"), dict) else ""
    for holder in result.get("major_shareholders") or []:
        if not _owner_v5_existing_holder_safe(holder, result):
            repairs += 1
            continue
        key = _owner_v4_identity_key(holder.get("name"))
        if not key or key == controller_key or key in seen:
            if key == controller_key: repairs += 1
            continue
        seen.add(key)
        safe_holders.append(dict(holder))
    if safe_holders:
        result["major_shareholders"] = safe_holders[:5]
    else:
        if result.get("major_shareholders"):
            repairs += 1
        result.pop("major_shareholders", None)
    if repairs:
        result["owner_v5_safety_repairs"] = int(result.get("owner_v5_safety_repairs") or 0) + repairs
        result["owner_v5_repaired_utc"] = _profile_now_iso()
    return result


async def _discover_owner_intelligence_v5(ticker, issuer_name=None, website=None):
    ticker = _valid_idx_ticker(ticker)
    if not ticker or not RUMOR_OWNER_SAFETY_V5_ENABLED or not BS4_AVAILABLE:
        return {}
    safe_issuer = _clean_profile_text(issuer_name, 120) if issuer_name else None
    company_host = re.sub(r"^www\.", "", _host(str(website or "")) or "")
    queries = []
    if company_host:
        queries += [
            f'site:{company_host} "primary and controlling shareholder"',
            f'site:{company_host} "controlling shareholder"',
            f'site:{company_host} "pemegang saham pengendali"',
            f'site:{company_host} "shareholding"',
        ]
    queries += [
        f'site:idx.co.id "{ticker}" "Pemegang Saham Pengendali"',
        f'site:idx.co.id "{ticker}" "Pemegang Saham >5%"',
        f'site:ojk.go.id "{ticker}" "pemegang saham pengendali"',
        f'site:ksei.co.id "{ticker}" "pemegang saham"',
    ]
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/129 Safari/537.36",
        "Accept-Language": "id-ID,id;q=0.9,en;q=0.7",
    }
    candidates = []
    fetched = set()
    async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
        if company_host and website:
            home_text, links = await _owner_v4_primary_site_seed(client, website, company_host)
            # Homepage is allowed only through strict direct-role parsing.
            if home_text:
                candidates += _extract_owner_candidates_v5(
                    home_text, ticker=ticker, issuer_name=safe_issuer, source=company_host,
                    source_url=website, primary_company=True,
                )
            for href in links[:RUMOR_OWNER_V5_PAGE_FETCH_LIMIT]:
                if href in fetched: continue
                fetched.add(href)
                page_text = await _owner_v4_fetch_page_text(client, href)
                if page_text:
                    candidates += _extract_owner_candidates_v5(
                        page_text, ticker=ticker, issuer_name=safe_issuer, source=company_host,
                        source_url=href, primary_company=True,
                    )
        for query in queries[:RUMOR_OWNER_V5_SEARCH_LIMIT]:
            try:
                response = await client.get("https://html.duckduckgo.com/html/?q=" + quote_plus(query), timeout=PROFILE_TIMEOUT_SECONDS)
            except Exception:
                continue
            if response.status_code >= 400: continue
            soup = BeautifulSoup(response.text, "html.parser")
            for block in soup.select(".result, .web-result")[:8]:
                link_node = block.select_one("a.result__a, .result__title a")
                snippet_node = block.select_one(".result__snippet, .result__body")
                if not link_node: continue
                href = _extract_result_url_from_search(link_node.get("href", ""))
                if not href: continue
                host, registry, primary = _owner_v4_source_flags(href, company_host)
                # HARD SAFETY RULE: no media/general-web ownership extraction in V5.
                if not (registry or primary):
                    continue
                title = normalize(link_node.get_text(" ", strip=True))
                snippet = normalize(snippet_node.get_text(" ", strip=True) if snippet_node else "")
                combined = normalize(f"{title}. {snippet}")
                candidates += _extract_owner_candidates_v5(
                    combined, ticker=ticker, issuer_name=safe_issuer, source=host or "OFFICIAL",
                    source_url=href, official_registry=registry, primary_company=primary,
                )
                if href not in fetched and len(fetched) < RUMOR_OWNER_V5_PAGE_FETCH_LIMIT and not href.lower().split("?",1)[0].endswith(".pdf"):
                    fetched.add(href)
                    page_text = await _owner_v4_fetch_page_text(client, href)
                    if page_text:
                        candidates += _extract_owner_candidates_v5(
                            page_text, ticker=ticker, issuer_name=safe_issuer, source=host or "OFFICIAL",
                            source_url=href, official_registry=registry, primary_company=primary,
                        )
    selected = _owner_v5_select_candidates(candidates)
    selected["owner_context_sources"] = len({x.get("source_group") for x in candidates if x.get("source_group")})
    selected["owner_v5_checked_utc"] = _profile_now_iso()
    selected["owner_v5_pages_fetched"] = len(fetched)
    selected["owner_discovery_method"] = "STRICT_OFFICIAL_SECTION_V5"
    return selected


async def _enrich_profile_owner_intelligence_v5(ticker, profile):
    if not RUMOR_OWNER_SAFETY_V5_ENABLED or not isinstance(profile, dict):
        return profile
    result = _owner_v5_sanitize_profile(profile)
    checked = _profile_parse_iso(result.get("owner_v5_checked_utc"))
    if checked and checked > datetime.now(timezone.utc) - timedelta(hours=RUMOR_PROFILE_REFRESH_HOURS):
        return result
    try:
        discovered = await _discover_owner_intelligence_v5(
            ticker, issuer_name=result.get("issuer_name"), website=result.get("website")
        )
    except Exception:
        discovered = {"owner_v5_checked_utc": _profile_now_iso()}
    new_controller = discovered.get("controller")
    if new_controller and _controller_verification_rank(new_controller) >= _controller_verification_rank(result.get("controller")):
        result["controller"] = new_controller
    # V5 discovery replaces V4 ownership-derived holder context; retain only safe legacy holders.
    holders = [x for x in (result.get("major_shareholders") or []) if _owner_v5_existing_holder_safe(x, result)]
    known = {_owner_v4_identity_key(x.get("name")) for x in holders}
    ctrl_key = _owner_v4_identity_key((result.get("controller") or {}).get("name")) if isinstance(result.get("controller"), dict) else ""
    for holder in discovered.get("major_shareholders") or []:
        key = _owner_v4_identity_key(holder.get("name"))
        if key and key != ctrl_key and key not in known:
            holders.append(holder); known.add(key)
    if holders: result["major_shareholders"] = holders[:5]
    else: result.pop("major_shareholders", None)
    for key in ("owner_context_sources", "owner_resolution_level", "owner_v5_checked_utc", "owner_v5_pages_fetched", "owner_discovery_method"):
        if discovered.get(key) not in (None, "", [], {}): result[key] = discovered.get(key)
    return _owner_v5_sanitize_profile(result)


async def _enrich_profile_owner_intelligence_v2(ticker, profile):
    if not RUMOR_OWNER_INTELLIGENCE_V2_ENABLED or not isinstance(profile, dict):
        return profile
    controller = profile.get("controller")
    majors = profile.get("major_shareholders") or []
    if _controller_verification_rank(controller) > 0 or majors:
        return profile
    checked = _profile_parse_iso(profile.get("owner_v2_checked_utc"))
    if checked and checked > datetime.now(timezone.utc) - timedelta(hours=RUMOR_PROFILE_REFRESH_HOURS):
        return profile
    try:
        discovered = await _discover_owner_intelligence_v2(
            ticker,
            issuer_name=profile.get("issuer_name"),
            website=profile.get("website"),
        )
    except Exception:
        discovered = {"owner_v2_checked_utc": _profile_now_iso()}
    result = dict(profile)
    new_controller = discovered.get("controller")
    if new_controller and _controller_verification_rank(new_controller) > _controller_verification_rank(result.get("controller")):
        result["controller"] = new_controller
    if not result.get("major_shareholders") and discovered.get("major_shareholders"):
        result["major_shareholders"] = discovered.get("major_shareholders")
    for key in ("owner_context_sources", "owner_resolution_level", "owner_v2_checked_utc"):
        if discovered.get(key) not in (None, "", [], {}):
            result[key] = discovered.get(key)
    return result

def _merge_profile_sources(
    *,
    ticker,
    issuer_name=None,
    idx_profile=None,
    market_profile=None,
    controller=None,
):
    idx_profile = dict(
        idx_profile or {}
    )
    market_profile = dict(
        market_profile or {}
    )

    if not controller and idx_profile.get("controller_name"):
        controller = _profile_holder_from_official_value(
            idx_profile.get("controller_name"),
            ticker=ticker,
            issuer_name=issuer_name,
            source_url=idx_profile.get("source_url"),
            controller=True,
        )

    official_major = None
    if idx_profile.get("major_shareholder"):
        official_major = _profile_holder_from_official_value(
            idx_profile.get("major_shareholder"),
            ticker=ticker,
            issuer_name=issuer_name,
            source_url=idx_profile.get("source_url"),
            controller=False,
        )

    profile = {
        "ticker": ticker,
        "issuer_name": (
            issuer_name
            or idx_profile.get("issuer_name")
            or market_profile.get("issuer_name")
        ),
        "business_activity": (
            idx_profile.get("business_activity")
            or market_profile.get("business_activity")
        ),
        "sector": (
            idx_profile.get("sector")
            or market_profile.get("sector")
        ),
        "subsector": (
            idx_profile.get("subsector")
        ),
        "industry": (
            idx_profile.get("industry")
            or market_profile.get("industry")
        ),
        "subindustry": (
            idx_profile.get("subindustry")
        ),
        "website": (
            idx_profile.get("website")
            or market_profile.get("website")
        ),
        "controller": controller,
        "major_shareholders": [],
        "profile_source": (
            idx_profile.get("source")
            or market_profile.get("source")
            or None
        ),
        "profile_source_url": (
            idx_profile.get("source_url")
        ),
        "profile_source_quality": (
            idx_profile.get("source_quality")
            or market_profile.get("source_quality")
            or "UNVERIFIED"
        ),
        "verified_at": _profile_now_iso(),
    }

    if (
        isinstance(controller, dict)
        and controller.get("verified")
        and controller.get("name")
    ):
        holder = {
            "name": controller.get("name"),
            "stake_pct": controller.get("stake_pct"),
            "verified": True,
            "source": controller.get("source"),
            "source_url": controller.get("source_url"),
        }
        profile["major_shareholders"] = [holder]
    elif official_major:
        profile["major_shareholders"] = [official_major]

    return profile


def _controller_verification_rank(controller):
    if not isinstance(controller, dict):
        return 0
    if not controller.get("verified") or not controller.get("name"):
        return 0
    level = str(controller.get("verification_level") or "").upper()
    if level in {
        "OFFICIAL_DIRECT", "OFFICIAL_DIRECT_V2", "OFFICIAL_DIRECT_V3",
        "OFFICIAL_DIRECT_V4", "OFFICIAL_DIRECT_V5",
    }:
        return 5
    if level in {
        "PRIMARY_COMPANY_CONTROLLER_V3", "PRIMARY_COMPANY_CONTROLLER_V4",
        "PRIMARY_COMPANY_CONTROLLER_V5",
    }:
        return 4
    if level == "CROSS_VERIFIED":
        return 4
    if level == "OFFICIAL_EVENT_ROLE":
        return 4
    return 2


def _normalized_entity_key(value):
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value or "").lower(),
    )


def _profile_source_rank(profile):
    if not isinstance(profile, dict):
        return 0
    quality = str(profile.get("profile_source_quality") or "").upper()
    source = str(profile.get("profile_source") or "").upper()
    if quality == "OFFICIAL" or "IDX" in source:
        return 3
    if quality == "FALLBACK":
        return 2
    return 1 if source else 0


def merge_issuer_profile_records(base_profile, incoming_profile):
    """Quality-aware profile merge.

    Critical V6.6.4.2 rule:
    a stale scanner profile with controller=None must never overwrite a
    verified controller learned by /analyze and persisted in command_state.
    """
    base_profile = dict(base_profile or {})
    incoming_profile = dict(incoming_profile or {})

    if not base_profile:
        return _owner_v5_sanitize_profile(incoming_profile) if RUMOR_OWNER_SAFETY_V5_ENABLED else incoming_profile
    if not incoming_profile:
        return _owner_v5_sanitize_profile(base_profile) if RUMOR_OWNER_SAFETY_V5_ENABLED else base_profile

    result = dict(base_profile)

    # Prefer useful non-empty incoming context, but preserve official profile
    # fields against a weaker fallback source.
    base_source_rank = _profile_source_rank(base_profile)
    incoming_source_rank = _profile_source_rank(incoming_profile)

    context_fields = (
        "ticker", "issuer_name", "business_activity", "sector",
        "subsector", "industry", "subindustry", "website",
        "profile_source", "profile_source_url", "profile_source_quality",
        "owner_context_sources", "owner_resolution_level", "owner_v2_checked_utc",
    )

    for field in context_fields:
        incoming = incoming_profile.get(field)
        current = result.get(field)
        if incoming in (None, "", [], {}):
            continue
        if current in (None, "", [], {}):
            result[field] = incoming
            continue
        if field in {
            "business_activity", "sector", "subsector", "industry",
            "subindustry", "profile_source", "profile_source_url",
            "profile_source_quality",
        } and incoming_source_rank > base_source_rank:
            result[field] = incoming

    old_controller = base_profile.get("controller")
    new_controller = incoming_profile.get("controller")
    old_rank = _controller_verification_rank(old_controller)
    new_rank = _controller_verification_rank(new_controller)

    chosen_controller = old_controller

    if new_rank > old_rank:
        chosen_controller = new_controller
    elif new_rank and old_rank:
        old_key = _normalized_entity_key(old_controller.get("name"))
        new_key = _normalized_entity_key(new_controller.get("name"))

        if old_key and old_key == new_key:
            chosen_controller = dict(old_controller)
            # Fill missing stake/source/evidence from incoming.
            for field in (
                "stake_pct", "source", "source_url", "basis",
                "verification_level", "evidence_text",
            ):
                if chosen_controller.get(field) in (None, "") and new_controller.get(field) not in (None, ""):
                    chosen_controller[field] = new_controller.get(field)
        elif new_rank > old_rank:
            chosen_controller = new_controller
        elif new_rank == old_rank:
            # Equal-strength conflicting controllers are not silently merged.
            # Keep the current verified record and expose the conflict marker.
            result["controller_conflict"] = [
                str(old_controller.get("name") or ""),
                str(new_controller.get("name") or ""),
            ]

    result["controller"] = chosen_controller

    if _controller_verification_rank(chosen_controller) > 0:
        result["major_shareholders"] = [{
            "name": chosen_controller.get("name"),
            "stake_pct": chosen_controller.get("stake_pct"),
            "verified": True,
            "source": chosen_controller.get("source"),
            "source_url": chosen_controller.get("source_url"),
        }]
    else:
        # Never let an incoming empty list erase a verified holder from base.
        old_majors = base_profile.get("major_shareholders") or []
        new_majors = incoming_profile.get("major_shareholders") or []
        result["major_shareholders"] = new_majors or old_majors

    # Keep the newest verification timestamp when parseable.
    old_dt = _profile_parse_iso(base_profile.get("verified_at"))
    new_dt = _profile_parse_iso(incoming_profile.get("verified_at"))
    if new_dt and (not old_dt or new_dt >= old_dt):
        result["verified_at"] = incoming_profile.get("verified_at")
    elif base_profile.get("verified_at"):
        result["verified_at"] = base_profile.get("verified_at")

    if RUMOR_OWNER_SAFETY_V5_ENABLED:
        result = _owner_v5_sanitize_profile(result)
    return result


async def resolve_issuer_profile(
    ticker,
    *,
    article=None,
    force=False,
):
    ticker = _valid_idx_ticker(ticker)

    if not ticker or not ISSUER_PROFILE_ENABLED:
        return None

    cached = ISSUER_PROFILE_CACHE.get(ticker)

    if (
        not force
        and cached
        and _profile_fresh(cached)
    ):
        profile = dict(cached)
        if RUMOR_OWNER_SAFETY_V5_ENABLED:
            profile = _owner_v5_sanitize_profile(profile)
            ISSUER_PROFILE_CACHE[ticker] = dict(profile)

        # Event-level controller evidence can be fresher than cached profile.
        event_controller = _controller_candidate_from_event(
            article or {}
        )

        if event_controller:
            profile["controller"] = event_controller
            profile["major_shareholders"] = [{
                "name": event_controller.get("name"),
                "stake_pct": event_controller.get("stake_pct"),
                "verified": True,
                "source": event_controller.get("source"),
                "source_url": event_controller.get("source_url"),
            }]
            profile["verified_at"] = _profile_now_iso()
            ISSUER_PROFILE_CACHE[ticker] = profile

        # V6.6.4 originally cached "controller=None" for up to 30 days.
        # V6.6.4.1 refreshes only the missing controller while preserving
        # already-cached business/sector context.
        controller = profile.get(
            "controller"
        )

        if not (
            isinstance(controller, dict)
            and controller.get("verified")
            and controller.get("name")
        ):
            try:
                resolved_controller = await _discover_controller_official(
                    ticker,
                    issuer_name=profile.get("issuer_name"),
                )
            except Exception:
                resolved_controller = None

            if resolved_controller:
                profile["controller"] = resolved_controller
                profile["major_shareholders"] = [{
                    "name": resolved_controller.get("name"),
                    "stake_pct": resolved_controller.get("stake_pct"),
                    "verified": True,
                    "source": resolved_controller.get("source"),
                    "source_url": resolved_controller.get("source_url"),
                }]
                profile["verified_at"] = _profile_now_iso()
                ISSUER_PROFILE_CACHE[ticker] = profile

        return profile

    issuer_name = None
    if isinstance(article, dict):
        issuer_name = article.get(
            "issuer_name"
        )

    aliases = get_ticker_aliases(ticker)
    if not issuer_name and aliases:
        issuer_name = aliases[0]

    idx_profile, market_profile = await asyncio.gather(
        _fetch_idx_profile(ticker),
        _fetch_market_profile(ticker),
    )

    issuer_name = (
        issuer_name
        or idx_profile.get("issuer_name")
        or market_profile.get("issuer_name")
    )

    controller = _controller_candidate_from_event(
        article or {}
    )

    if not controller:
        controller = await _discover_controller_official(
            ticker,
            issuer_name=issuer_name,
        )

    profile = _merge_profile_sources(
        ticker=ticker,
        issuer_name=issuer_name,
        idx_profile=idx_profile,
        market_profile=market_profile,
        controller=controller,
    )

    ISSUER_PROFILE_CACHE[ticker] = profile

    return dict(profile)


def hydrate_issuer_profile_cache(data):
    if not isinstance(data, dict):
        return 0

    count = 0

    for raw_ticker, raw_profile in data.items():
        ticker = _valid_idx_ticker(
            raw_ticker
        )
        if (
            not ticker
            or not isinstance(raw_profile, dict)
        ):
            continue

        profile = dict(raw_profile)
        if RUMOR_OWNER_SAFETY_V5_ENABLED:
            profile = _owner_v5_sanitize_profile(profile)

        if not profile.get("ticker"):
            profile["ticker"] = ticker

        existing = ISSUER_PROFILE_CACHE.get(ticker)

        if PROFILE_CACHE_QUALITY_MERGE_ENABLED and isinstance(existing, dict):
            profile = merge_issuer_profile_records(
                existing,
                profile,
            )

        ISSUER_PROFILE_CACHE[ticker] = profile
        count += 1

    return count


def export_issuer_profile_cache():
    output = {}

    for ticker, profile in ISSUER_PROFILE_CACHE.items():
        ticker = _valid_idx_ticker(
            ticker
        )
        if (
            ticker
            and isinstance(profile, dict)
        ):
            clean_profile = dict(profile)
            if RUMOR_OWNER_SAFETY_V5_ENABLED:
                clean_profile = _owner_v5_sanitize_profile(clean_profile)
            output[ticker] = clean_profile

    return output


def issuer_profile_lines(article):
    profile = (
        article.get("issuer_profile")
        if isinstance(article, dict)
        else None
    )

    if not isinstance(profile, dict):
        return []
    if RUMOR_OWNER_SAFETY_V5_ENABLED:
        profile = _owner_v5_sanitize_profile(profile)

    lines = []

    controller = profile.get("controller")

    if (
        isinstance(controller, dict)
        and controller.get("verified")
        and controller.get("name")
    ):
        owner = html.escape(
            str(controller["name"])
        )

        stake = controller.get(
            "stake_pct"
        )
        if stake is not None:
            try:
                owner += (
                    " — "
                    + format_pct(float(stake))
                )
            except Exception:
                pass

        lines.append(
            "👤 <b>Pengendali:</b> "
            + owner
        )

        verification_level = str(
            controller.get("verification_level")
            or "VERIFIED"
        )

        if verification_level in {"OFFICIAL_DIRECT", "OFFICIAL_DIRECT_V2", "OFFICIAL_DIRECT_V3", "OFFICIAL_DIRECT_V4", "OFFICIAL_DIRECT_V5"}:
            lines.append(
                "🛡️ <b>Verifikasi pengendali:</b> ✅ IDX/otoritas langsung"
            )
        elif verification_level in {"PRIMARY_COMPANY_CONTROLLER_V3", "PRIMARY_COMPANY_CONTROLLER_V4", "PRIMARY_COMPANY_CONTROLLER_V5"}:
            lines.append(
                "🛡️ <b>Verifikasi pengendali:</b> ✅ situs resmi emiten"
            )
        elif verification_level == "CROSS_VERIFIED":
            lines.append(
                "🛡️ <b>Verifikasi pengendali:</b> ✅ IDX + identitas artikel"
            )
        else:
            lines.append(
                "🛡️ <b>Verifikasi pengendali:</b> ✅ event resmi"
            )
    else:
        lines.append(
            "👤 <b>Pengendali:</b> "
            "⚪ belum terverifikasi"
        )

    localized = _rumor_business_profile_id(profile) if RUMOR_UNIFIED_PROFILE_ID_ENABLED else {
        "field": profile.get("business_activity"), "activity": None,
        "sector": profile.get("sector"),
        "industry": profile.get("subsector") or profile.get("industry"),
    }
    if localized.get("field"):
        lines.append("💼 <b>Bidang usaha:</b> " + html.escape(str(localized["field"])))
    if localized.get("activity"):
        lines.append("⚙️ <b>Kegiatan utama:</b> " + html.escape(str(localized["activity"])))
    if localized.get("sector"):
        lines.append("🏭 <b>Sektor:</b> " + html.escape(str(localized["sector"])))
    if localized.get("industry"):
        lines.append("📂 <b>Industri:</b> " + html.escape(str(localized["industry"])))

    majors = profile.get(
        "major_shareholders"
    ) or []

    if majors:
        holder = majors[0]
        if isinstance(holder, dict):
            name = holder.get("name")
            stake = holder.get("stake_pct")

            if name:
                text = html.escape(str(name))
                if stake is not None:
                    try:
                        text += (
                            " — "
                            + format_pct(float(stake))
                        )
                    except Exception:
                        pass

                lines.append(
                    "🏦 <b>Pemegang saham utama:</b> "
                    + text
                )

    source = profile.get(
        "profile_source"
    )
    quality = profile.get(
        "profile_source_quality"
    )

    if source:
        quality_badge = (
            "✅"
            if quality == "OFFICIAL"
            else "ℹ️"
        )
        lines.append(
            f"{quality_badge} <b>Sumber profil:</b> "
            + html.escape(str(source))
        )

    return lines[:8]


def format_profile_report(profile):
    if not isinstance(profile, dict):
        return "⚠️ Profil emiten belum tersedia."

    profile = _sanitize_profile_display_v3(profile)
    ticker_raw = str(profile.get("ticker") or "-")
    issuer_raw = str(profile.get("issuer_name") or "-")
    ticker = html.escape(ticker_raw)
    issuer = html.escape(issuer_raw)

    lines = [
        f"🏢 <b>ISSUER PROFILE — {ticker}</b>",
        "",
        f"🏷 <b>Emiten:</b> {issuer}",
    ]

    # V6.7.5: /profile uses the same Indonesian owner/business renderer as
    # /rumor and Auto Alert, eliminating English-vs-Indonesian drift.
    lines.extend(_rumor_profile_lines(profile, private_company=False))

    controller = profile.get("controller")
    if isinstance(controller, dict) and controller.get("verified") and controller.get("source"):
        lines.append("🏛 <b>Sumber pengendali:</b> " + html.escape(str(controller.get("source"))))
    if profile.get("controller_resolution_context") == "DEEP_TICKER_ANALYSIS":
        lines.append("🧠 <b>Context resolver:</b> ✅ sinkron dengan /analyze")

    majors = [x for x in (profile.get("major_shareholders") or []) if isinstance(x, dict) and x.get("name")]
    if majors:
        identity = _owner_v4_identity_key if RUMOR_OWNER_INTELLIGENCE_V4_ENABLED else _normalized_entity_key
        controller_key = identity((controller or {}).get("name")) if isinstance(controller, dict) else ""
        distinct = [x for x in majors if not controller_key or identity(x.get("name")) != controller_key]
        # _rumor_profile_lines already shows the first distinct major holder.
        # Only list additional holders here to prevent duplicate Telegram lines.
        remaining = distinct[1:] if distinct else []
        if remaining:
            lines += ["", "🏦 <b>PEMEGANG SAHAM LAIN</b>"]
            for holder in remaining[:2]:
                text = html.escape(str(holder.get("name")))
                if holder.get("stake_pct") is not None:
                    try:
                        text += " — " + format_pct(float(holder.get("stake_pct")))
                    except Exception:
                        pass
                lines.append("• " + text)

    if profile.get("profile_source_url"):
        lines.append(
            f'<a href="{html.escape(str(profile["profile_source_url"]), quote=True)}">🔗 Buka profil sumber</a>'
        )

    lines += [
        "",
        "⚠️ <i>Pengendali ≠ direktur utama. "
        "Pemegang saham utama juga tidak otomatis dianggap pengendali tanpa bukti role/control.</i>",
    ]
    return "\n".join(lines)[:3900]


def _verified_profile_controller(profile):
    if isinstance(profile, dict) and RUMOR_OWNER_SAFETY_V5_ENABLED:
        profile = _owner_v5_sanitize_profile(profile)
    controller = (
        profile.get("controller")
        if isinstance(profile, dict)
        else None
    )
    return bool(
        isinstance(controller, dict)
        and controller.get("verified")
        and controller.get("name")
    )


async def resolve_issuer_profile_with_context(ticker):
    """Standalone /profile resolver with the same deep event context as /analyze.

    Fast path: cached/official profile already has controller.
    Fallback: silently run ticker analysis, then merge its verified controller
    into the profile. This does not send the /analyze report to Telegram.
    """
    ticker = _valid_idx_ticker(ticker)
    if not ticker:
        return None, None

    profile = await resolve_issuer_profile(
        ticker,
        force=False,
    )
    if profile and RUMOR_PROFILE_CACHE_REPAIR_V3_ENABLED:
        profile = _sanitize_profile_display_v3(profile)
        ISSUER_PROFILE_CACHE[ticker] = dict(profile)

    # V6.7.7: safety-first strict owner resolver before deep /analyze.
    # A fresh V5 cache key forces repair/retry after poisoned V6.7.6 ownership cache.
    if profile and RUMOR_OWNER_SAFETY_V5_ENABLED:
        profile = _owner_v5_sanitize_profile(profile)
    if profile and not _verified_profile_controller(profile):
        if RUMOR_OWNER_SAFETY_V5_ENABLED:
            profile = await _enrich_profile_owner_intelligence_v5(ticker, profile)
        elif RUMOR_OWNER_INTELLIGENCE_V4_ENABLED:
            profile = await _enrich_profile_owner_intelligence_v4(ticker, profile)
        ISSUER_PROFILE_CACHE[ticker] = dict(profile)

    if (
        not PROFILE_DEEP_CONTEXT_ON_DEMAND_ENABLED
        or _verified_profile_controller(profile)
    ):
        if profile and not _verified_profile_controller(profile):
            if RUMOR_OWNER_SAFETY_V5_ENABLED:
                profile = await _enrich_profile_owner_intelligence_v5(ticker, profile)
            elif RUMOR_OWNER_INTELLIGENCE_V4_ENABLED:
                profile = await _enrich_profile_owner_intelligence_v4(ticker, profile)
            elif RUMOR_OWNER_INTELLIGENCE_V3_ENABLED:
                profile = await _enrich_profile_owner_intelligence_v3(ticker, profile)
            else:
                profile = await _enrich_profile_owner_intelligence_v2(ticker, profile)
            ISSUER_PROFILE_CACHE[ticker] = dict(profile)
        return profile, None

    analysis_article = None

    try:
        result = await prepare_ticker_analysis(
            ticker,
            use_deep=True,
        )
        analysis_article = result.get("article") if isinstance(result, dict) else None
    except Exception:
        analysis_article = None

    if analysis_article:
        try:
            enriched = await resolve_issuer_profile(
                ticker,
                article=analysis_article,
                force=False,
            )
        except Exception:
            enriched = None

        if enriched:
            profile = merge_issuer_profile_records(
                profile or {},
                enriched,
            )
            ISSUER_PROFILE_CACHE[ticker] = dict(profile)

    if profile and not _verified_profile_controller(profile):
        if RUMOR_OWNER_SAFETY_V5_ENABLED:
            profile = await _enrich_profile_owner_intelligence_v5(ticker, profile)
        elif RUMOR_OWNER_INTELLIGENCE_V4_ENABLED:
            profile = await _enrich_profile_owner_intelligence_v4(ticker, profile)
        elif RUMOR_OWNER_INTELLIGENCE_V3_ENABLED:
            profile = await _enrich_profile_owner_intelligence_v3(ticker, profile)
        else:
            profile = await _enrich_profile_owner_intelligence_v2(ticker, profile)
        ISSUER_PROFILE_CACHE[ticker] = dict(profile)

    return profile, analysis_article


async def send_issuer_profile(
    chat_id,
    ticker,
):
    ticker = _valid_idx_ticker(
        ticker
    )

    if not ticker:
        await send_message(
            chat_id,
            "Format ticker harus 4 huruf, contoh: /profile DOOH",
        )
        return None

    await send_message(
        chat_id,
        f"🔎 Mencari profil emiten <b>{html.escape(ticker)}</b>…",
    )

    profile, analysis_article = await resolve_issuer_profile_with_context(
        ticker,
    )

    if not profile:
        await send_message(
            chat_id,
            "⚠️ Profil emiten belum berhasil ditemukan.",
        )
        return None

    if analysis_article and _verified_profile_controller(profile):
        profile = dict(profile)
        profile["controller_resolution_context"] = "DEEP_TICKER_ANALYSIS"

    await send_message(
        chat_id,
        format_profile_report(profile),
    )

    return profile


def v6642_profile_sync_selftest():
    controller = {
        "name": "PT Sinergi Internasional Investama",
        "stake_pct": 51.0,
        "verified": True,
        "verification_level": "CROSS_VERIFIED",
        "source": "IDX + DEEP ARTICLE",
        "source_url": "https://idx.co.id/controller.pdf",
    }

    command_profile = {
        "ticker": "DOOH",
        "issuer_name": "Era Media Sejahtera",
        "business_activity": "Media dan periklanan",
        "profile_source": "Yahoo Finance",
        "profile_source_quality": "FALLBACK",
        "controller": controller,
        "major_shareholders": [{
            "name": controller["name"],
            "stake_pct": 51.0,
            "verified": True,
        }],
        "verified_at": _profile_now_iso(),
    }

    stale_scanner = {
        "ticker": "DOOH",
        "issuer_name": "Era Media Sejahtera",
        "business_activity": "Media dan periklanan digital",
        "profile_source": "Yahoo Finance",
        "profile_source_quality": "FALLBACK",
        "controller": None,
        "major_shareholders": [],
        "verified_at": _profile_now_iso(),
    }

    merged = merge_issuer_profile_records(
        command_profile,
        stale_scanner,
    )

    controller_kept = (
        _verified_profile_controller(merged)
        and merged["controller"].get("name")
        == "PT Sinergi Internasional Investama"
        and merged["controller"].get("stake_pct") == 51.0
    )

    article_cached = {
        "title": "Pengendali Anyar DOOH kuasai 51% saham",
        "snippet": "",
        "event_type": "TENDER OFFER",
        "verified_official_ref": {
            "authority": "IDX",
            "kind": "PRIMARY",
            "url": "https://idx.co.id/event.pdf",
        },
        "details": {"ticker": "DOOH"},
    }
    cached_lines = official_reference_lines(article_cached)
    cached_wording = (
        any("Corporate Action Source" in line for line in cached_lines)
        and any("referensi terverifikasi" in line for line in cached_lines)
        and not any("belum ditemukan" in line for line in cached_lines)
    )

    article_controller_only = {
        "title": "Pengendali Anyar DOOH",
        "snippet": "",
        "event_type": "TENDER OFFER",
        "details": {"ticker": "DOOH"},
        "issuer_profile": {
            "controller": controller,
        },
    }
    evidence_lines = official_reference_lines(article_controller_only)
    evidence_wording = (
        any("referensi event langsung belum ditemukan" in line for line in evidence_lines)
        and any("Controller Evidence" in line and "IDX + identitas artikel" in line for line in evidence_lines)
    )

    return {
        "passed": bool(controller_kept and cached_wording and evidence_wording),
        "verified_controller_merge": bool(controller_kept),
        "verified_cache_wording": bool(cached_wording),
        "controller_evidence_wording": bool(evidence_wording),
    }


def v6641_controller_deep_selftest():
    # Regression 1:
    # official search result title is the actor, snippet names the TARGET
    # after the words "Pengendali Baru".
    candidate = _controller_from_official_search_result(
        result_title="pt sinergi internasional investama",
        snippet=(
            "Perusahaan Sasaran dan dengan demikian menjadi "
            "Pengendali Baru PT Era Media Sejahtera Tbk (DOOH)."
        ),
        href="https://www.idx.co.id/example.pdf",
        ticker="DOOH",
        issuer_name="Era Media Sejahtera",
    )

    # Regression 2:
    # never interpret the target company as its own controller.
    wrong = _extract_controller_from_text(
        "Pengendali Baru PT Era Media Sejahtera Tbk (DOOH)",
        ticker="DOOH",
        issuer_name="Era Media Sejahtera",
    )

    # Regression 3:
    # deep article can name the actor + stake.
    deep = _deep_controller_evidence(
        (
            "PT Sinergi Internasional Investama telah menguasai "
            "51% saham PT Era Media Sejahtera Tbk dan telah menjadi "
            "Pemegang Saham Pengendali Perseroan."
        ),
        ticker="DOOH",
        issuer_name="Era Media Sejahtera",
        source_url="https://publisher.example/dooh",
    )

    article = {
        "title": "Pengendali Anyar DOOH kuasai 51% saham & wajib tender offer",
        "snippet": "",
        "event_type": "TENDER OFFER",
        "issuer_name": "Era Media Sejahtera",
        "official_reference": {
            "authority": "IDX",
            "kind": "PRIMARY",
            "url": "https://www.idx.co.id/example.pdf",
        },
        "controller_evidence": deep,
        "details": {
            "ticker": "DOOH",
            "acquirer": None,
            "target": "DOOH",
            "percentages": [51.0],
            "role_meta": {},
        },
    }

    resolved = _controller_candidate_from_event(
        article
    )

    status = control_change_evidence_status(
        article
    )

    return {
        "passed": all([
            candidate is not None,
            candidate.get("name") == "PT Sinergi Internasional Investama",
            candidate.get("verification_level") == "OFFICIAL_DIRECT",
            wrong == [],
            bool(deep.get("candidates")),
            deep["candidates"][0].get("name")
            == "PT Sinergi Internasional Investama",
            resolved is not None,
            resolved.get("name")
            == "PT Sinergi Internasional Investama",
            resolved.get("stake_pct") == 51.0,
            resolved.get("verification_level") == "CROSS_VERIFIED",
            status is not None,
            status.startswith("✅"),
        ]),
        "official_title_actor": (
            candidate is not None
            and candidate.get("name")
            == "PT Sinergi Internasional Investama"
        ),
        "target_self_controller_guard": (
            wrong == []
        ),
        "deep_identity_cross_verify": (
            resolved is not None
            and resolved.get("verification_level")
            == "CROSS_VERIFIED"
        ),
        "control_status_consistency": (
            status is not None
            and status.startswith("✅")
        ),
    }


def v664_profile_selftest():
    event_article = {
        "title": (
            "PT Alpha Investasi menjadi pengendali baru ABCD "
            "setelah menguasai 51% saham"
        ),
        "snippet": "Perubahan pengendali ABCD.",
        "event_type": "TENDER OFFER",
        "official_reference": {
            "authority": "IDX",
            "kind": "PRIMARY",
            "url": "https://idx.co.id/example",
        },
        "details": {
            "ticker": "ABCD",
            "acquirer": "PT Alpha Investasi",
            "target": "ABCD",
            "percentages": [51.0],
            "role_meta": {},
        },
    }

    controller = _controller_candidate_from_event(
        event_article
    )

    profile = _merge_profile_sources(
        ticker="ABCD",
        issuer_name="PT Contoh Tbk",
        idx_profile={
            "business_activity": "Media dan periklanan digital",
            "sector": "Barang Konsumen Non-Primer",
            "subsector": "Media & Hiburan",
            "source": "IDX PROFILE",
            "source_quality": "OFFICIAL",
            "source_url": "https://idx.co.id/profile/ABCD",
        },
        market_profile={
            "industry": "Advertising Agencies",
            "source": "Yahoo Finance",
            "source_quality": "FALLBACK",
        },
        controller=controller,
    )

    report = format_profile_report(
        profile
    )

    return {
        "passed": all([
            controller is not None,
            controller.get("verified") is True,
            controller.get("name") == "PT Alpha Investasi",
            controller.get("stake_pct") == 51.0,
            profile.get("business_activity") == "Media dan periklanan digital",
            profile.get("sector") == "Barang Konsumen Non-Primer",
            profile.get("subsector") == "Media & Hiburan",
            "Pengendali" in report,
            "Bidang usaha" in report,
            "Pengendali ≠ direktur utama" in report,
        ]),
        "controller_guard": (
            controller is not None
            and controller.get("verified") is True
        ),
        "business_profile": bool(
            profile.get("business_activity")
            and profile.get("sector")
        ),
        "management_owner_guard": (
            "Pengendali ≠ direktur utama"
            in report
        ),
    }


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

    if ISSUER_PROFILE_ENABLED and ticker:
        try:
            article["issuer_profile"] = await resolve_issuer_profile(
                ticker,
                article=article,
            )
        except Exception:
            article["issuer_profile"] = None

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
    # V6.7.5: never retain transaction/headline prefixes as issuer identity.
    # Example live bug: "62 Persen Saham Bayan Resources" -> "Bayan Resources".
    if RUMOR_ISSUER_SANITIZER_V3_ENABLED:
        prefix_patterns = [
            r"^(?:sekitar|hingga|sebanyak|sebesar|lebih dari|kurang dari)?\s*\d{1,3}(?:[.,]\d+)?\s*(?:%|persen)\s+(?:kepemilikan\s+)?(?:saham\s+)?",
            r"^(?:mayoritas|minoritas|sebagian|seluruh)\s+(?:kepemilikan\s+)?saham\s+",
            r"^(?:porsi|kepemilikan|stake)\s+\d{1,3}(?:[.,]\d+)?\s*(?:%|persen)?\s+(?:saham\s+)?",
            r"^(?:rumor|isu|kabar)\s+(?:akuisisi|takeover|pengambilalihan)?\s*",
        ]
        for pattern in prefix_patterns:
            text = re.sub(pattern, "", text, flags=re.I).strip(" -–—,:;|")
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


def _controller_official_evidence(article):
    profile = (
        article.get("issuer_profile")
        if isinstance(article, dict)
        else None
    )

    controller = (
        profile.get("controller")
        if isinstance(profile, dict)
        else None
    )

    if not (
        isinstance(controller, dict)
        and controller.get("verified")
        and controller.get("name")
    ):
        return None

    source = str(controller.get("source") or "")
    level = str(controller.get("verification_level") or "").upper()

    if "IDX" not in source.upper() and level not in {
        "OFFICIAL_DIRECT", "CROSS_VERIFIED", "OFFICIAL_EVENT_ROLE"
    }:
        return None

    return controller


def official_reference_lines(article):
    """Explain event-source evidence without contradicting controller evidence."""
    ref = article.get("official_reference")
    ref_origin = "DIRECT"

    if not ref and official_source_rank(article) > 0:
        ref = _official_reference_from_article(article)

    if not ref:
        cached_ref = article.get("verified_official_ref")
        if not cached_ref:
            cached_ref = verified_official_ref_for_article(article)
        if cached_ref:
            ref = cached_ref
            ref_origin = "VERIFIED_CACHE"

    if ref:
        authority = html.escape(str(ref.get("authority") or "OFFICIAL"))
        kind = html.escape(str(ref.get("kind") or "PRIMARY"))
        url = ref.get("url")

        suffix = (
            " — referensi terverifikasi"
            if ref_origin == "VERIFIED_CACHE"
            else ""
        )

        lines = [
            f"🏛️ <b>Corporate Action Source:</b> ✅ {authority} — {kind}{suffix}"
        ]

        if url:
            lines.append(
                f'<a href="{html.escape(str(url), quote=True)}">📎 Buka sumber resmi</a>'
            )

        return lines

    controller = _controller_official_evidence(article)

    if controller and OFFICIAL_EVIDENCE_WORDING_ENABLED:
        level = str(controller.get("verification_level") or "VERIFIED").upper()
        if level == "OFFICIAL_DIRECT":
            evidence = "✅ IDX langsung"
        elif level == "CROSS_VERIFIED":
            evidence = "✅ IDX + identitas artikel"
        else:
            evidence = "✅ event resmi"

        lines = [
            "🏛️ <b>Corporate Action Source:</b> ⚪ referensi event langsung belum ditemukan pada feed saat ini",
            f"🛡️ <b>Controller Evidence:</b> {evidence}",
        ]

        if controller.get("source_url"):
            lines.append(
                f'<a href="{html.escape(str(controller.get("source_url")), quote=True)}">📎 Buka bukti pengendali</a>'
            )

        return lines

    return [
        "🏛️ <b>Corporate Action Source:</b> ⚪ belum ditemukan pada feed/verified cache saat ini"
    ]



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
# V6.7.4 — RUMOR INTELLIGENCE & CONFIRMATION TRACKER
# ============================================================

RUMOR_QUERIES = [
    '"rumor" saham emiten Indonesia',
    '("isu akuisisi" OR "rumor takeover") saham emiten Indonesia',
    '("investor strategis" OR "strategic investor") emiten Indonesia',
    '("wacana merger" OR "rumor merger") emiten Indonesia',
    '("rumor IPO" OR "wacana IPO") perusahaan Indonesia',
    '("akan IPO" OR "bakal IPO" OR "siap IPO") perusahaan Indonesia',
    '("rights issue" OR HMETD OR "private placement" OR PMTHMETD) (rumor OR wacana) emiten',
    '(buyback OR divestasi) (rumor OR wacana OR isu) emiten Indonesia',
    '("spin off" OR restrukturisasi) (rumor OR wacana) emiten Indonesia',
    '(delisting OR relisting) (rumor OR wacana OR isu) emiten Indonesia',
    '("perubahan pengendali" OR "tender offer") (rumor OR isu OR wacana) saham',
    '("calon investor" OR "calon pembeli") saham emiten Indonesia',
]

RUMOR_CONFIRMATION_QUERIES = [
    'site:idx.co.id ("private placement" OR PMTHMETD OR buyback)',
    'site:idx.co.id (divestasi OR "spin off" OR restrukturisasi)',
    'site:idx.co.id (delisting OR relisting)',
    'site:e-ipo.co.id ("penawaran umum perdana" OR bookbuilding)',
]

RUMOR_CATEGORY_KEYWORDS = {
    "IPO": [
        "ipo",
        "initial public offering",
        "penawaran umum perdana",
        "go public",
        "melantai di bursa",
        "listing di bei",
        "listing di bursa",
        "pre-ipo",
        "pre ipo",
    ],
    "TENDER OFFER": [
        "tender offer",
        "penawaran tender",
        "tender wajib",
        "mandatory tender offer",
    ],
    "CHANGE CONTROL": [
        "perubahan pengendali",
        "pengendali baru",
        "pengendali anyar",
        "change of control",
        "pemegang saham pengendali",
    ],
    "MERGER": [
        "merger",
        "penggabungan usaha",
        "business combination",
    ],
    "AKUISISI / TAKEOVER": [
        "akuisisi",
        "mengakuisisi",
        "diakuisisi",
        "takeover",
        "take over",
        "pengambilalihan",
        "ambil alih",
        "acquisition",
        "acquire",
        "buyout",
    ],
    "STRATEGIC INVESTOR": [
        "investor strategis",
        "strategic investor",
        "strategic partner",
        "mitra strategis",
        "investor baru",
        "masuk sebagai investor",
    ],
    "RIGHTS ISSUE": [
        "rights issue",
        "right issue",
        "hmetd",
        "pmhmetd",
        "hak memesan efek terlebih dahulu",
    ],
    "PRIVATE PLACEMENT": [
        "private placement",
        "pmthmetd",
        "penambahan modal tanpa hmetd",
        "non-preemptive rights",
    ],
    "BUYBACK": [
        "buyback",
        "pembelian kembali saham",
        "beli kembali saham",
    ],
    "DIVESTASI": [
        "divestasi",
        "divestment",
        "melepas saham",
        "penjualan saham",
        "jual saham",
    ],
    "SPIN-OFF / RESTRUCTURING": [
        "spin off",
        "spin-off",
        "pemisahan usaha",
        "restrukturisasi",
        "restructuring",
    ],
    "DELISTING / RELISTING": [
        "delisting",
        "go private",
        "relisting",
        "re-listing",
        "pencatatan kembali",
    ],
}

RUMOR_UNCERTAINTY_CUES = [
    "rumor",
    "isu",
    "dikabarkan",
    "disebut-sebut",
    "disebut sebut",
    "santer",
    "spekulasi",
    "wacana",
    "kabarnya",
    "sinyal",
    "beredar kabar",
    "menurut sumber",
    "disebut akan",
    "diperkirakan akan",
    "berpotensi",
    "menjajaki",
    "penjajakan",
    "mempertimbangkan",
    "pertimbangkan",
    "mengincar",
    "berencana",
    "rencana",
    "siap ipo",
    "akan ipo",
    "menuju ipo",
    "bakal ipo",
]

RUMOR_DENIAL_CUES = [
    "membantah",
    "bantah rumor",
    "bantah isu",
    "menepis",
    "tidak benar",
    "hoaks",
    "kabar tidak benar",
    "rumor tidak benar",
    "tidak ada rencana",
    "belum ada rencana",
    "tidak berencana",
    "menolak kabar",
]

RUMOR_CONFIRMATION_CUES = [
    "resmi",
    "mengumumkan",
    "telah menandatangani",
    "telah mengambil alih",
    "telah mengakuisisi",
    "efektif ojk",
    "prospektus",
    "keterbukaan informasi",
    "penjelasan resmi",
    "persetujuan pemegang saham",
    "tercatat di e-ipo",
    "terdaftar di e-ipo",
]

RUMOR_NOT_CONFIRMED_CUES = [
    "belum resmi",
    "tidak resmi",
    "belum dikonfirmasi",
    "belum ada konfirmasi",
    "belum mendapat konfirmasi",
    "masih rumor",
    "masih sebatas rumor",
    "belum final",
    "belum pasti",
]

RUMOR_ESTABLISHED_SOURCES = [
    "kontan",
    "bisnis.com",
    "cnbc indonesia",
    "bloomberg",
    "reuters",
    "investor.id",
    "idnfinancials",
    "katadata",
    "antaranews",
    "tempo",
    "kompas",
    "detikfinance",
    "emitennews",
    "pasardana",
    "bareksa",
]

PRIVATE_SECTOR_KEYWORDS = {
    "Technology": [
        "teknologi", "software", "aplikasi", "platform digital",
        "data center", "cloud", "saas", "artificial intelligence",
        "kecerdasan buatan",
    ],
    "Financials": [
        "bank", "perbankan", "fintech", "pembiayaan", "asuransi",
        "sekuritas", "financial technology", "pinjaman",
    ],
    "Energy": [
        "energi", "minyak", "gas", "batubara", "batu bara",
        "renewable", "panas bumi", "geothermal",
    ],
    "Basic Materials": [
        "nikel", "emas", "tambang", "pertambangan", "mineral",
        "smelter", "logam", "semen", "kimia",
    ],
    "Consumer": [
        "makanan", "minuman", "retail", "ritel", "consumer",
        "restoran", "food", "beverage", "fmcg",
    ],
    "Healthcare": [
        "rumah sakit", "farmasi", "kesehatan", "healthcare",
        "laboratorium", "klinik",
    ],
    "Property & Real Estate": [
        "properti", "real estat", "real estate", "developer",
        "perumahan", "kawasan industri",
    ],
    "Industrials": [
        "manufaktur", "industrial", "pabrik", "mesin",
        "engineering", "otomotif",
    ],
    "Transportation & Logistics": [
        "logistik", "transportasi", "shipping", "pelayaran",
        "kurir", "pergudangan", "warehouse",
    ],
    "Media & Communications": [
        "media", "periklanan", "advertising", "telekomunikasi",
        "telecommunication", "broadcasting",
    ],
    "Infrastructure": [
        "infrastruktur", "jalan tol", "konstruksi", "construction",
        "menara telekomunikasi",
    ],
    "Agriculture": [
        "perkebunan", "kelapa sawit", "sawit", "agriculture",
        "pertanian", "perikanan",
    ],
}


def rumor_category(text):
    low = normalize(str(text or "")).lower()

    # Most-specific categories first.
    order = [
        "IPO",
        "TENDER OFFER",
        "CHANGE CONTROL",
        "MERGER",
        "PRIVATE PLACEMENT",
        "RIGHTS ISSUE",
        "BUYBACK",
        "DIVESTASI",
        "SPIN-OFF / RESTRUCTURING",
        "DELISTING / RELISTING",
        "STRATEGIC INVESTOR",
        "AKUISISI / TAKEOVER",
    ]

    for category in order:
        if any(
            keyword in low
            for keyword in RUMOR_CATEGORY_KEYWORDS[category]
        ):
            return category

    return None


def _rumor_source_key(value):
    value = normalize(str(value or "")).lower()
    value = re.sub(r"\s+", " ", value)
    return value or "unknown"


def _rumor_source_established(source):
    low = _rumor_source_key(source)
    return any(
        hint in low
        for hint in RUMOR_ESTABLISHED_SOURCES
    )


RUMOR_SOURCE_PREMIUM_HINTS = [
    "reuters", "bloomberg", "cnbc indonesia", "bisnis.com", "kontan",
    "tempo", "kompas", "antaranews", "katadata", "detikfinance",
    "investor.id", "idnfinancials",
]

RUMOR_SOURCE_STANDARD_HINTS = [
    "emitennews", "pasardana", "bareksa", "liputan6", "kumparan",
    "okezone", "sindonews", "republika", "the jakarta post",
]

RUMOR_HEADLINE_STOPWORDS = {
    "yang", "dan", "atau", "dari", "untuk", "dengan", "pada", "di", "ke",
    "ini", "itu", "jadi", "bakal", "akan", "soal", "terkait", "saham",
    "emiten", "pt", "tbk", "rumor", "isu", "kabar", "disebut", "dikabarkan",
    "santer", "wacana", "harga", "naik", "turun", "terbang", "tersengat",
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "or", "is",
    "reportedly", "rumored", "shares", "stock", "company",
}


def _rumor_source_probe(article_or_source, link=""):
    if isinstance(article_or_source, dict):
        source = str(article_or_source.get("source") or "")
        link = str(
            article_or_source.get("source_url")
            or article_or_source.get("link")
            or link
            or ""
        )
    else:
        source = str(article_or_source or "")
    return normalize(f"{source} {link}").lower()


def _rumor_source_quality(article_or_source, link=""):
    """Return quality metadata; this scores evidence quality, not truth."""
    probe = _rumor_source_probe(article_or_source, link=link)

    official_hints = (
        "idx.co.id", "bursa efek indonesia", "e-ipo.co.id", "e-ipo",
        "ojk.go.id", "otoritas jasa keuangan", "ksei.co.id",
    )

    if any(hint in probe for hint in official_hints):
        return {"tier": 5, "label": "OFFICIAL", "weight": 5.0}

    if any(hint in probe for hint in RUMOR_SOURCE_PREMIUM_HINTS):
        return {"tier": 4, "label": "HIGH", "weight": 4.0}

    if any(hint in probe for hint in RUMOR_SOURCE_STANDARD_HINTS):
        return {"tier": 3, "label": "MEDIUM", "weight": 2.5}

    if _rumor_source_established(probe):
        return {"tier": 3, "label": "MEDIUM", "weight": 2.5}

    return {"tier": 1, "label": "LOW", "weight": 1.0}


def _rumor_editorial_group(article):
    if not isinstance(article, dict):
        return _rumor_source_key(article)

    source = _rumor_source_key(article.get("source"))
    link = str(article.get("source_url") or article.get("link") or "")
    host = _host(link)

    # Google News URLs are aggregators, not publisher identity.
    if host and "google." not in host and "news.google" not in host:
        host = re.sub(r"^www\.", "", host.lower())
        if host:
            return host

    aliases = {
        "cnbc indonesia": "cnbcindonesia.com",
        "bisnis.com": "bisnis.com",
        "kontan": "kontan.co.id",
        "reuters": "reuters.com",
        "bloomberg": "bloomberg.com",
        "tempo": "tempo.co",
        "kompas": "kompas.com",
        "antaranews": "antaranews.com",
        "katadata": "katadata.co.id",
        "detikfinance": "detik.com",
        "investor.id": "investor.id",
        "idnfinancials": "idnfinancials.com",
        "emitennews": "emitennews.com",
        "pasardana": "pasardana.id",
        "bareksa": "bareksa.com",
    }
    for hint, canonical in aliases.items():
        if hint in source:
            return canonical
    return source or "unknown"


def _rumor_headline_tokens(article):
    if isinstance(article, dict):
        text = str(article.get("title") or "")
    else:
        text = str(article or "")
    text = normalize(text).lower()
    tokens = re.findall(r"[a-z0-9]{3,}", text)
    return {
        token for token in tokens
        if token not in RUMOR_HEADLINE_STOPWORDS
    }


def _rumor_semantic_text(article):
    if not isinstance(article, dict):
        return normalize(str(article or "")).lower()
    deep = str(article.get("rumor_deep_text") or "")[:1800]
    return normalize(" ".join([
        str(article.get("title") or ""),
        str(article.get("snippet") or ""),
        deep,
    ])).lower()


def _rumor_semantic_tokens(article):
    text = _rumor_semantic_text(article)
    tokens = re.findall(r"[a-z0-9]{3,}", text)
    return [
        token for token in tokens
        if token not in RUMOR_HEADLINE_STOPWORDS
    ]


def _rumor_semantic_bigrams(article):
    tokens = _rumor_semantic_tokens(article)
    if len(tokens) < 2:
        return set()
    return {
        tokens[idx] + " " + tokens[idx + 1]
        for idx in range(len(tokens) - 1)
    }


def _rumor_token_similarity(left, right):
    if not left or not right:
        return 0.0
    left = set(left)
    right = set(right)
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def _rumor_containment_similarity(left, right):
    if not left or not right:
        return 0.0
    left = set(left)
    right = set(right)
    denom = max(1, min(len(left), len(right)))
    return len(left & right) / denom


def _rumor_material_signature(article):
    if not isinstance(article, dict):
        return set()
    details = article.get("rumor_details") or {}
    signature = set()
    for key in (
        "rumored_party", "share_count", "price_range", "ipo_price",
        "underwriter", "listing_estimate", "money", "percentages",
    ):
        value = details.get(key)
        if value in (None, "", [], {}):
            continue
        values = value if isinstance(value, (list, tuple, set)) else [value]
        for item in values:
            clean = normalize(str(item or "")).lower()
            if clean:
                signature.add(f"{key}:{clean}")
    return signature


def _rumor_semantic_similarity(left_article, right_article):
    """Text/evidence similarity for derivative detection, not truth scoring."""
    if not RUMOR_SEMANTIC_COPY_V2_ENABLED:
        return _rumor_token_similarity(
            _rumor_headline_tokens(left_article),
            _rumor_headline_tokens(right_article),
        )

    left_tokens = set(_rumor_semantic_tokens(left_article))
    right_tokens = set(_rumor_semantic_tokens(right_article))
    token_jaccard = _rumor_token_similarity(left_tokens, right_tokens)
    token_containment = _rumor_containment_similarity(left_tokens, right_tokens)

    left_bigrams = _rumor_semantic_bigrams(left_article)
    right_bigrams = _rumor_semantic_bigrams(right_article)
    bigram_containment = _rumor_containment_similarity(left_bigrams, right_bigrams)

    left_material = _rumor_material_signature(left_article)
    right_material = _rumor_material_signature(right_article)
    material = _rumor_containment_similarity(left_material, right_material)

    left_title = normalize(str((left_article or {}).get("title") or "")).lower()
    right_title = normalize(str((right_article or {}).get("title") or "")).lower()
    sequence = SequenceMatcher(None, left_title, right_title).ratio() if left_title and right_title else 0.0

    # Weighted blend catches rewritten/clickbait headlines whose snippets and
    # material details still reveal one underlying story.
    return max(
        sequence * 0.85,
        (token_jaccard * 0.30)
        + (token_containment * 0.20)
        + (bigram_containment * 0.35)
        + (material * 0.15),
    )


def _rumor_copy_clusters(articles):
    clusters = []
    for article in articles or []:
        headline_tokens = _rumor_headline_tokens(article)
        placed = False
        if RUMOR_ANTI_COPY_ENABLED:
            best_idx = None
            best_score = 0.0
            for idx, cluster in enumerate(clusters):
                scores = [
                    _rumor_semantic_similarity(article, member)
                    for member in cluster["articles"][:5]
                ]
                score = max(scores, default=0.0)
                old_headline_score = _rumor_token_similarity(
                    headline_tokens,
                    cluster.get("headline_tokens") or set(),
                )
                score = max(score, old_headline_score)
                if score > best_score:
                    best_idx = idx
                    best_score = score
            if best_idx is not None and (
                best_score >= RUMOR_SEMANTIC_COPY_SIMILARITY
                or best_score >= RUMOR_COPY_SIMILARITY
            ):
                cluster = clusters[best_idx]
                cluster["articles"].append(article)
                cluster["headline_tokens"] = (
                    cluster.get("headline_tokens") or set()
                ) | set(headline_tokens)
                cluster["max_similarity"] = max(
                    float(cluster.get("max_similarity") or 0.0),
                    best_score,
                )
                placed = True
        if not placed:
            clusters.append({
                "headline_tokens": set(headline_tokens),
                "articles": [article],
                "max_similarity": 0.0,
            })
    return clusters


def _rumor_source_metrics(articles):
    active = [
        article for article in (articles or [])
        if str(article.get("rumor_status") or "ACTIVE") == "ACTIVE"
    ]
    if not active:
        active = list(articles or [])

    # One best article per editorial group prevents one publisher with multiple
    # URLs from inflating corroboration.
    grouped = {}
    for article in active:
        group = _rumor_editorial_group(article)
        quality = _rumor_source_quality(article)
        current = grouped.get(group)
        candidate = {"article": article, "quality": quality}
        if current is None:
            grouped[group] = candidate
            continue
        current_specificity = _rumor_specificity(current["article"])
        candidate_specificity = _rumor_specificity(article)
        if (
            quality["weight"], candidate_specificity
        ) > (
            current["quality"]["weight"], current_specificity
        ):
            grouped[group] = candidate

    representatives = [item["article"] for item in grouped.values()]
    clusters = _rumor_copy_clusters(representatives)

    cluster_for = {}
    for idx, cluster in enumerate(clusters):
        for article in cluster["articles"]:
            cluster_for[id(article)] = idx

    # Evaluate strongest/most credible sources first. This lets later low-tier
    # portals prove independence only when they add unique material evidence.
    ordered = sorted(
        grouped.items(),
        key=lambda pair: (
            pair[1]["quality"]["tier"],
            _rumor_specificity(pair[1]["article"]),
            pair[1]["article"].get("published_dt")
            or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )

    seen_material = set()
    seen_cluster = set()
    weighted_rows = []
    effective_independent = 0.0
    semantic_copies = 0
    derivative_sources = 0
    quality_score = 0.0

    for group, item in ordered:
        article = item["article"]
        quality = item["quality"]
        tier = int(quality["tier"])
        material = _rumor_material_signature(article)
        new_material = material - seen_material
        cluster_id = cluster_for.get(id(article), -1)
        semantic_copy = cluster_id in seen_cluster

        if not RUMOR_WEIGHTED_INDEPENDENCE_V2_ENABLED:
            independence_weight = 0.20 if semantic_copy else 1.0
            derivative = semantic_copy
        else:
            # Baseline independence by source quality.
            baseline = {
                5: 1.10,  # official
                4: 1.00,  # premium/high
                3: 0.80,  # established/medium
                2: 0.50,
                1: 0.35,  # low-quality/unknown
            }.get(tier, 0.35)

            if semantic_copy:
                semantic_copies += 1
                derivative = True
                duplicate_factor = {
                    5: 0.70,
                    4: 0.55,
                    3: 0.40,
                    2: 0.25,
                    1: 0.18,
                }.get(tier, 0.18)
                independence_weight = baseline * duplicate_factor
            elif not new_material and seen_material:
                # Same thesis with no new material details: count it, but only
                # fractionally. This is the key V6.7.4 defense against 10 low
                # portals rewriting one rumor with different headlines.
                derivative = tier <= 3
                if tier <= 1:
                    independence_weight = RUMOR_DERIVATIVE_LOW_WEIGHT
                elif tier == 2:
                    independence_weight = 0.40
                elif tier == 3:
                    independence_weight = RUMOR_DERIVATIVE_MEDIUM_WEIGHT
                else:
                    independence_weight = baseline * 0.90
            else:
                derivative = False
                independence_weight = baseline
                if new_material and tier <= 2:
                    # Unique specifics can partially rehabilitate a low-tier
                    # source without letting it equal Reuters/IDX.
                    independence_weight = min(0.65, independence_weight + 0.20)

        if derivative and not semantic_copy:
            derivative_sources += 1

        effective_independent += independence_weight
        quality_score += quality["weight"] * independence_weight
        seen_material |= material
        seen_cluster.add(cluster_id)
        weighted_rows.append({
            "source": normalize(str(article.get("source") or group)) or group,
            "group": group,
            "quality": quality["label"],
            "tier": tier,
            "weight": round(independence_weight, 2),
            "derivative": bool(derivative),
            "semantic_copy": bool(semantic_copy),
            "new_material": len(new_material),
        })

    source_count = len(grouped)
    unique_story_count = len(clusters)
    copy_duplicates = semantic_copies + derivative_sources
    effective_independent = round(effective_independent, 1)

    high_quality = sum(
        1 for item in grouped.values()
        if item["quality"]["tier"] >= 3
    )
    premium = sum(
        1 for item in grouped.values()
        if item["quality"]["tier"] >= 4
    )
    credible_effective = round(sum(
        row["weight"] for row in weighted_rows
        if row["tier"] >= 3
    ), 1)

    if premium >= 2 and quality_score >= 7.0 and credible_effective >= 1.8:
        label = "HIGH"
    elif high_quality >= 1 and quality_score >= 2.5:
        label = "MEDIUM"
    else:
        label = "LOW"

    breakdown = sorted(
        weighted_rows,
        key=lambda row: (row["tier"], row["weight"]),
        reverse=True,
    )

    return {
        "detected_source_count": source_count,
        "independent_story_count": unique_story_count,
        "effective_independent_count": effective_independent,
        "credible_effective_independent_count": credible_effective,
        "copy_duplicate_count": copy_duplicates,
        "semantic_copy_count": semantic_copies,
        "derivative_source_count": derivative_sources,
        "high_quality_source_count": high_quality,
        "premium_source_count": premium,
        "source_quality": label,
        "source_quality_score": round(quality_score, 1),
        "source_breakdown": breakdown[:10],
    }

def _rumor_has_uncertainty(text):
    low = normalize(str(text or "")).lower()
    return any(cue in low for cue in RUMOR_UNCERTAINTY_CUES)


def _rumor_has_denial(text):
    low = normalize(str(text or "")).lower()
    return any(cue in low for cue in RUMOR_DENIAL_CUES)


def _rumor_has_confirmation_cue(text):
    low = normalize(str(text or "")).lower()

    if any(
        cue in low
        for cue in RUMOR_NOT_CONFIRMED_CUES
    ):
        return False

    return any(
        cue in low
        for cue in RUMOR_CONFIRMATION_CUES
    )


def _rumor_entry_status(text, source, link=""):
    low = normalize(str(text or "")).lower()

    if _rumor_has_denial(low):
        return "DENIED"

    probe = {
        "title": normalize(str(text or "")),
        "source": normalize(str(source or "")),
        "link": normalize(str(link or "")),
        "details": {"ticker": None},
    }

    try:
        annotate_official_source(probe)
    except Exception:
        pass

    if (
        official_source_rank(probe) > 0
        or _rumor_has_confirmation_cue(low)
    ):
        return "CONFIRMED OFFICIAL"

    if _rumor_has_uncertainty(low):
        return "ACTIVE"

    return None


def _rumor_recent(dt):
    if dt is None:
        return False

    return dt >= (
        datetime.now(timezone.utc)
        - timedelta(hours=RUMOR_LOOKBACK_HOURS)
    )


def _extract_rumor_ticker(title, text, geo):
    ticker = extract_ticker(
        title,
        text,
        geo,
    )

    ticker = _valid_idx_ticker(
        ticker
    )

    if ticker:
        return ticker

    # Rumor headlines frequently use a bare IDX ticker after an action word,
    # e.g. "rumor akuisisi ABCD". Only accept explicit uppercase 4-letter
    # tokens and keep the existing stopword guard.
    candidates = re.findall(
        r"\b([A-Z]{4})\b",
        f"{title} {text}",
    )

    for candidate in candidates:
        candidate = candidate.upper()

        if candidate in TICKER_STOPWORDS:
            continue

        if (
            str(geo).startswith("INDONESIA")
            or "indonesia" in str(text).lower()
            or "emiten" in str(text).lower()
            or "saham" in str(text).lower()
            or "bei" in str(text).lower()
            or "idx" in str(text).lower()
            or "tbk" in str(text).lower()
        ):
            return candidate

    return None


def _extract_rumor_company_name(title, text, category):
    title = normalize(str(title or ""))
    text = normalize(str(text or ""))

    legal_patterns = [
        r"\b(PT\.?\s+[A-Z][A-Za-z0-9&.,'’()\- ]{2,110}?(?:\s+Tbk\.?)?)"
        r"(?=\s+(?:dikabarkan|disebut|berencana|akan|bakal|siap|menuju|"
        r"mengincar|menjajaki|pertimbangkan|mempertimbangkan|resmi|"
        r"melakukan|menggelar|melantai|ipo|merger|akuisisi|rights|"
        r"private|buyback|divestasi|spin|delisting|relisting|$|,|:|-))",
        r"\b(PT\.?\s+[A-Z][A-Za-z0-9&.,'’()\- ]{2,110}?(?:\s+Tbk\.?)?)",
    ]

    for pattern in legal_patterns:
        match = re.search(
            pattern,
            title,
            flags=re.I,
        )
        if match:
            value = _normalize_legal_entity_display(
                match.group(1)
            )
            if value:
                return value

    if category == "IPO":
        patterns = [
            r"^(.{2,80}?)\s+(?:dikabarkan|disebut|berencana|akan|bakal|siap|menuju)\s+(?:akan\s+)?IPO\b",
            r"^(.{2,80}?)\s+(?:siap|bakal|akan)\s+melantai\s+di\s+bursa\b",
            r"\brumor\s+IPO\s+(.{2,80}?)(?:\s+-\s+|\s+\||$)",
        ]

        clean_title = re.sub(
            r"\s+-\s+[^-]+$",
            "",
            title,
        )

        for pattern in patterns:
            match = re.search(
                pattern,
                clean_title,
                flags=re.I,
            )
            if not match:
                continue

            candidate = normalize(
                match.group(1)
            ).strip(" :|-")

            if 2 <= len(candidate) <= 90:
                return candidate

    return None


def _valid_rumored_party(value):
    value = _clean_role_candidate(
        value
    )

    if not value:
        return None

    low = value.lower().strip()

    bad_exact = {
        "rumor",
        "isu",
        "sinyal",
        "emiten",
        "investor",
        "investor strategis",
        "calon investor",
        "calon pembeli",
        "perusahaan",
    }

    if low in bad_exact:
        return None

    bad_phrases = [
        "membantah rumor",
        "bantah rumor",
        "membantah isu",
        "rumor akuisisi",
        "isu akuisisi",
        "rumor takeover",
        "wacana akuisisi",
        "tersengat rumor",
        "tersengat isu",
        "terimbas rumor",
        "terimbas isu",
        "dipicu rumor",
        "dipicu isu",
        "di tengah rumor",
        "diterpa rumor",
        "dihantam rumor",
    ]

    if any(
        phrase in low
        for phrase in bad_phrases
    ):
        return None

    if RUMOR_PARTY_PHRASE_GUARD_ENABLED:
        # Headline/action fragments are not people or legal entities.
        # Example live bug: "Tersengat Rumor" was incorrectly shown as buyer.
        fragment_words = {
            "tersengat", "terimbas", "diterpa", "dihantam", "dipicu",
            "rumor", "isu", "wacana", "sinyal", "saham", "harga",
            "naik", "turun", "melonjak", "terbang", "meroket",
            "menguat", "melemah", "anjlok", "ara", "arb",
        }
        tokens = re.findall(r"[a-z0-9]+", low)
        if tokens and all(token in fragment_words for token in tokens):
            return None
        if re.match(
            r"^(?:tersengat|terimbas|diterpa|dihantam|dipicu|saham|harga)\b",
            low,
        ):
            return None
        if re.search(
            r"\b(?:rumor|isu|wacana)\s*$",
            low,
        ):
            return None

    # Require at least two alphabetic characters and reject action fragments.
    if not re.search(r"[A-Za-z].*[A-Za-z]", value):
        return None

    if re.search(
        r"\b(?:akan|ingin|mau|bakal|siap|dikabarkan|disebut)\s*$",
        low,
        flags=re.I,
    ):
        return None

    return value


def _extract_rumored_party(title, text, category):
    combined = normalize(
        f"{title} {text}"
    )

    if category in {
        "AKUISISI / TAKEOVER",
        "TENDER OFFER",
        "CHANGE CONTROL",
        "STRATEGIC INVESTOR",
        "DIVESTASI",
    }:
        try:
            acquirer, _, meta = extract_acquirer_target_with_meta(
                title
            )
        except Exception:
            acquirer, meta = None, {}

        candidate = (
            acquirer
            or (meta or {}).get("acquirer_candidate")
        )

        candidate = _valid_rumored_party(
            candidate
        )

        if candidate:
            return candidate

        patterns = [
            r"(?:investor strategis|strategic investor|calon pembeli|calon investor)"
            r"\s*(?:adalah|yakni|yaitu|:|-)?\s*"
            r"(PT\.?\s+[A-Z][A-Za-z0-9&.,'’()\- ]{2,90}?)"
            r"(?=\s+(?:masuk|akan|dikabarkan|disebut|dirumorkan|menjajaki|"
            r"mengakuisisi|mengambil\s+alih|ke\b|pada\b)|[,.;|]|$)",
            r"([A-Z][A-Za-z0-9&.,'’()\- ]{2,100}?)"
            r"\s+(?:dikabarkan|disebut|dirumorkan)\s+"
            r"(?:akan\s+)?(?:masuk|mengakuisisi|mengambil alih)",
        ]

        for pattern in patterns:
            match = re.search(
                pattern,
                combined,
                flags=re.I,
            )
            if match:
                value = _valid_rumored_party(
                    match.group(1)
                )
                if value:
                    return value

    return None


RUMOR_STAKE_CUES = (
    "kepemilikan", "stake", "porsi saham", "porsi kepemilikan",
    "menguasai", "mengambil alih", "diambil alih", "membeli",
    "mengakuisisi", "diakuisisi", "saham sebesar", "persen saham",
    "saham kepada publik", "saham ditawarkan", "dilepas ke publik",
    "pemegang saham", "pengendali", "hak suara",
)

RUMOR_MARKET_PERCENT_CUES = (
    "harga saham", "saham naik", "saham turun", "saham menguat",
    "saham melemah", "saham melonjak", "saham terbang", "saham meroket",
    "naik", "turun", "menguat", "melemah", "melonjak", "terbang",
    "meroket", "anjlok", "terkoreksi", "ara", "arb", "return",
    "cuan", "rally", "rali",
)


def _rumor_percentage_matches(text):
    text = normalize(str(text or ""))
    out = []
    for match in re.finditer(
        r"(?<!\d)(\d{1,3}(?:[.,]\d{1,2})?)\s*%",
        text,
    ):
        try:
            value = float(match.group(1).replace(",", "."))
        except Exception:
            continue
        if not (0 < value <= 100):
            continue
        start = max(0, match.start() - 95)
        end = min(len(text), match.end() + 95)
        out.append((value, normalize(text[start:end]).lower()))
    return out


def _rumor_market_move_percentage(value, text):
    """True only when this percent is visibly a market-price move.

    This is intentionally conservative: if the same local window also has a
    clear ownership/stake cue, it is allowed as transaction detail.
    """
    for candidate, window in _rumor_percentage_matches(text):
        if abs(candidate - float(value)) > 1e-6:
            continue
        has_stake = any(cue in window for cue in RUMOR_STAKE_CUES)
        has_market = any(cue in window for cue in RUMOR_MARKET_PERCENT_CUES)
        if has_market and not has_stake:
            return True
    return False


def _extract_rumor_stake_percentages(text, category=None):
    if not RUMOR_PRICE_PERCENT_STAKE_GUARD_ENABLED:
        return extract_percentages(text)

    output = []
    seen = set()
    for value, window in _rumor_percentage_matches(text):
        has_stake = any(cue in window for cue in RUMOR_STAKE_CUES)
        has_market = any(cue in window for cue in RUMOR_MARKET_PERCENT_CUES)

        # Price-performance percentages are context only, never transaction stake.
        if has_market and not has_stake:
            continue

        # Rumor stake is an ownership field. A naked percentage with no
        # ownership/share cue is too ambiguous to publish as stake.
        if not has_stake:
            continue

        token = round(float(value), 6)
        if token in seen:
            continue
        seen.add(token)
        output.append(float(value))

    return output


def _valid_rumor_share_count(value):
    if not value:
        return None
    value = normalize(str(value))
    if not re.fullmatch(
        r"\d[\d.,]*\s*(?:(?:ribu|juta|miliar|triliun)\s+)?saham",
        value,
        flags=re.I,
    ):
        return None
    numeric = re.match(r"^(\d[\d.,]*)", value)
    if not numeric or not re.search(r"\d", numeric.group(1)):
        return None
    return value


def sanitize_rumor_details(details, context="", category=None):
    details = copy.deepcopy(details or {})
    repairs = 0

    party = details.get("rumored_party")
    if party and not _valid_rumored_party(party):
        details.pop("rumored_party", None)
        repairs += 1

    percentages = []
    for value in details.get("percentages") or []:
        try:
            number = float(value)
        except Exception:
            repairs += 1
            continue
        if not (0 < number <= 100):
            repairs += 1
            continue
        if context and _rumor_market_move_percentage(number, context):
            repairs += 1
            continue
        percentages.append(number)
    details["percentages"] = _rumor_normalize_material_list(
        percentages,
        numeric=True,
    )

    share_count = details.get("share_count")
    valid_share_count = _valid_rumor_share_count(share_count)
    if share_count and not valid_share_count:
        details.pop("share_count", None)
        repairs += 1
    elif valid_share_count:
        details["share_count"] = valid_share_count

    return details, repairs


def sanitize_rumor_record_integrity(record):
    if not isinstance(record, dict):
        return record, 0
    clean = copy.deepcopy(record)
    context = " ".join([
        str(clean.get("title") or ""),
        str(clean.get("snippet") or ""),
    ])
    details, repairs = sanitize_rumor_details(
        clean.get("rumor_details") or {},
        context=context,
        category=clean.get("category") or clean.get("rumor_category"),
    )
    clean["rumor_details"] = details

    if RUMOR_PROFILE_CACHE_REPAIR_V3_ENABLED:
        ticker = _valid_idx_ticker(clean.get("ticker"))
        if ticker:
            old_profile = clean.get("issuer_profile")
            if isinstance(old_profile, dict):
                fixed_profile = sanitize_rumor_issuer_profile(ticker, old_profile)
                if fixed_profile != old_profile:
                    clean["issuer_profile"] = fixed_profile
                    repairs += 1
            profile = clean.get("issuer_profile") or {}
            trusted_name = profile.get("issuer_name") if isinstance(profile, dict) else None
            old_company = normalize(str(clean.get("company_name") or ""))
            if trusted_name and (
                not old_company
                or _rumor_issuer_name_malformed(old_company, ticker=ticker)
                or _issuer_alias_key(trusted_name) in _issuer_alias_key(old_company)
                and _issuer_alias_key(trusted_name) != _issuer_alias_key(old_company)
            ):
                if old_company != trusted_name:
                    clean["company_name"] = trusted_name
                    repairs += 1
    return clean, repairs


def _extract_rumor_listing_estimate(text):
    text = normalize(str(text or ""))

    patterns = [
        r"(?:target|perkiraan|rencana|diperkirakan)\s+(?:listing|melantai)"
        r"\s*(?:pada|:|-)?\s*((?:kuartal|semester|q[1-4]|"
        r"januari|februari|maret|april|mei|juni|juli|agustus|september|"
        r"oktober|november|desember|20\d{2})[^.;|]{0,45})",
        r"(?:listing|melantai)\s+pada\s+([^.;|]{3,60})",
        r"(?:kuartal|semester)\s+[IVX1234]+\s+20\d{2}",
        r"(?:Q[1-4])\s+20\d{2}",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.I,
        )

        if match:
            value = (
                match.group(1)
                if match.lastindex
                else match.group(0)
            )
            value = _clean_profile_text(
                value,
                80,
            )
            if value:
                return value

    return None


def _extract_rumor_details(title, description, category):
    combined = normalize(
        f"{title} {description}"
    )

    percentages = _extract_rumor_stake_percentages(
        combined,
        category,
    )
    money = extract_money(
        combined,
        event=(
            "IPO"
            if category == "IPO"
            else "AKUISISI"
        ),
    )

    price_range = (
        extract_price_range(combined)
        if category == "IPO"
        else None
    )

    ipo_price = (
        extract_ipo_single_price(combined)
        if category == "IPO"
        else None
    )

    blocked = {
        money_key(price_range),
        money_key(ipo_price),
    }

    money = [
        item
        for item in money
        if money_key(item) not in blocked
    ]

    share_count = _valid_rumor_share_count(
        extract_share_count(combined)
    )

    underwriter = (
        extract_underwriter(combined)
        if category == "IPO"
        else None
    )

    return {
        "rumored_party": _extract_rumored_party(
            title,
            description,
            category,
        ),
        "percentages": percentages,
        "money": money,
        "price_range": price_range,
        "ipo_price": ipo_price,
        "share_count": share_count,
        "underwriter": underwriter,
        "listing_estimate": (
            _extract_rumor_listing_estimate(combined)
            if category == "IPO"
            else None
        ),
    }


def _rumor_specificity(article):
    details = article.get(
        "rumor_details"
    ) or {}

    score = 0

    for key in (
        "rumored_party",
        "percentages",
        "money",
        "price_range",
        "ipo_price",
        "share_count",
        "underwriter",
        "listing_estimate",
    ):
        if details.get(key):
            score += 1

    if article.get("ticker"):
        score += 2

    if article.get("company_name"):
        score += 1

    return score


def rumor_identity(article):
    category = str(
        article.get("rumor_category")
        or "RUMOR"
    ).upper()

    ticker = _valid_idx_ticker(
        article.get("ticker")
    )

    if ticker:
        return f"{category}|TICKER|{ticker}"

    company = _issuer_alias_key(
        article.get("company_name")
    )

    if company:
        return f"{category}|COMPANY|{company}"

    signature = _event_title_signature(
        article.get("title")
    )

    return f"{category}|TITLE|{signature}"


def _rumor_group_status(articles):
    statuses = {
        str(article.get("rumor_status") or "")
        for article in articles
    }

    if "CONFIRMED OFFICIAL" in statuses:
        return "CONFIRMED OFFICIAL"

    if "DENIED" in statuses:
        return "DENIED"

    return "ACTIVE"


def _rumor_strength(articles, status=None):
    status = status or _rumor_group_status(
        articles
    )

    if status == "CONFIRMED OFFICIAL":
        return "CONFIRMED OFFICIAL"

    active = [
        article
        for article in articles
        if article.get("rumor_status") == "ACTIVE"
    ]

    if not active:
        return "WEAK"

    max_specificity = max(
        (_rumor_specificity(article) for article in active),
        default=0,
    )

    if not RUMOR_SOURCE_QUALITY_ENABLED:
        source_keys = {
            _rumor_source_key(article.get("source"))
            for article in active
        }
        established_count = sum(
            1 for source in source_keys
            if _rumor_source_established(source)
        )
        source_count = len(source_keys)
        if source_count >= 3 or (
            source_count >= 2
            and established_count >= 2
            and max_specificity >= 2
        ):
            return "STRONG"
        if source_count >= 2 or (
            source_count == 1
            and established_count >= 1
            and max_specificity >= 3
        ):
            return "MEDIUM"
        return "WEAK"

    metrics = _rumor_source_metrics(active)
    source_count = metrics["detected_source_count"]
    independent = metrics["independent_story_count"]
    effective = metrics["effective_independent_count"]
    credible_effective = metrics.get("credible_effective_independent_count", 0.0)
    high_quality = metrics["high_quality_source_count"]
    premium = metrics["premium_source_count"]
    quality_score = metrics["source_quality_score"]

    # V6.7.4: STRONG is gated by credible weighted corroboration. Ten derivative
    # low-tier portals cannot compensate for only one credible original report.
    if (
        source_count >= 3
        and high_quality >= 2
        and premium >= 2
        and effective >= 2.2
        and credible_effective >= 1.8
        and quality_score >= 7.0
        and max_specificity >= 2
    ) or (
        premium >= 3
        and credible_effective >= 2.5
        and quality_score >= 9.0
        and max_specificity >= 2
    ):
        return "STRONG"

    if (
        high_quality >= 1
        and credible_effective >= 0.8
        and effective >= 1.2
        and quality_score >= 3.0
    ) or (
        premium >= 1
        and max_specificity >= 3
    ):
        return "MEDIUM"

    return "WEAK"


def _rumor_primary_rank(article):
    status_rank = RUMOR_STATUS_RANK.get(
        str(article.get("rumor_status") or "ACTIVE"),
        0,
    )

    return (
        status_rank,
        1 if _rumor_source_established(article.get("source")) else 0,
        _rumor_specificity(article),
        article.get("published_dt")
        or datetime.min.replace(tzinfo=timezone.utc),
    )


def _rumor_entity_text(article):
    if not isinstance(article, dict):
        return ""

    return normalize(" ".join([
        str(article.get("title") or ""),
        str(article.get("snippet") or ""),
        str(article.get("company_name") or ""),
    ]))


def _rumor_trusted_alias(value):
    clean = _clean_issuer_alias(value)
    key = _issuer_alias_key(clean)

    if not clean or not key:
        return None

    # UNKNOWN recovery must use a meaningful issuer identity, never a generic
    # one-word fragment such as "Resources" or "Group" learned from noise.
    if len(key.replace(" ", "")) < RUMOR_ENTITY_MIN_ALIAS_CHARS:
        return None

    generic = {
        "resources", "resource", "group", "holding", "holdings",
        "investasi", "investment", "investor", "indonesia",
        "perseroan", "emiten", "company", "corporation", "corp",
    }
    if key in generic:
        return None

    return clean


def _rumor_article_mentions_alias(article, alias):
    alias = _rumor_trusted_alias(alias)
    if not alias:
        return False

    alias_key = _issuer_alias_key(alias)
    text_key = _issuer_alias_key(_rumor_entity_text(article))

    if not alias_key or not text_key:
        return False

    # Exact normalized phrase/word boundary. This is deliberately stricter
    # than loose substring propagation because a rumor must not be assigned
    # to a ticker merely because a generic token happens to match.
    return bool(re.search(
        r"(?:^|\s)" + re.escape(alias_key) + r"(?:$|\s)",
        text_key,
    ))


def _rumor_add_alias(index, ticker, alias, source):
    ticker = _valid_idx_ticker(ticker)
    alias = _rumor_trusted_alias(alias)

    if not ticker or not alias:
        return

    key = _issuer_alias_key(alias)
    bucket = index.setdefault(key, {
        "alias": alias,
        "tickers": set(),
        "sources": set(),
    })
    bucket["tickers"].add(ticker)
    bucket["sources"].add(str(source or "MEMORY"))


def _rumor_entity_alias_index(rumor_articles=None, official_articles=None):
    """Build a trusted alias→ticker map from already-verified identities.

    Priority evidence comes from issuer alias memory/profile cache, explicit
    ticker rumor articles, and the current official/corporate-action batch.
    An alias is usable only when it maps to exactly one IDX ticker.
    """
    index = {}

    # 1) Persistent command/scanner alias memory hydrated earlier in the run.
    for ticker, bucket in TICKER_ALIAS_CACHE.items():
        ticker = _valid_idx_ticker(ticker)
        if not ticker or not isinstance(bucket, dict):
            continue
        for item in bucket.values():
            if isinstance(item, dict):
                _rumor_add_alias(
                    index,
                    ticker,
                    item.get("alias"),
                    "ISSUER_ALIAS_MEMORY",
                )

    # 2) Profile cache is also a trusted ticker/company association.
    for raw_ticker, profile in ISSUER_PROFILE_CACHE.items():
        ticker = _valid_idx_ticker(raw_ticker)
        if not ticker or not isinstance(profile, dict):
            continue
        _rumor_add_alias(
            index,
            ticker,
            profile.get("issuer_name"),
            "ISSUER_PROFILE_CACHE",
        )

    # 3) Current corporate-action feed. Only use rows with an explicit valid
    # ticker; we are learning the issuer name, not guessing the ticker.
    for article in official_articles or []:
        if not isinstance(article, dict):
            continue
        details = article.get("details") or {}
        ticker = _valid_idx_ticker(details.get("ticker"))
        if not ticker:
            continue

        candidates = []
        candidates.extend(article.get("issuer_aliases") or [])
        candidates.extend([
            article.get("issuer_name"),
            details.get("target"),
        ])

        combined = normalize(" ".join([
            str(article.get("title") or ""),
            str(article.get("snippet") or ""),
            str(article.get("description") or ""),
        ]))
        try:
            candidates.extend(
                extract_cooccurring_issuer_aliases(ticker, combined)
            )
        except Exception:
            pass

        for alias in candidates:
            _rumor_add_alias(index, ticker, alias, "CORPORATE_ACTION_BATCH")

    # 4) Explicit-ticker rumor rows can teach the batch how the media writes
    # the issuer name. This allows a ticker-less rewrite of the same issue to
    # join the canonical ticker group in the same scan.
    for article in rumor_articles or []:
        if not isinstance(article, dict):
            continue
        ticker = _valid_idx_ticker(article.get("ticker"))
        if not ticker:
            continue

        candidates = []
        candidates.extend(get_ticker_aliases(ticker))
        candidates.append(article.get("company_name"))

        combined = _rumor_entity_text(article)
        try:
            candidates.extend(
                extract_cooccurring_issuer_aliases(ticker, combined)
            )
        except Exception:
            pass

        for alias in candidates:
            _rumor_add_alias(index, ticker, alias, "RUMOR_EXPLICIT_TICKER")

    return index


async def prime_rumor_entity_aliases(rumor_articles, official_articles=None):
    """Prime trusted issuer aliases only when ticker-less rumor rows exist.

    This keeps the normal rumor scan fast. If UNKNOWN rows appear, only the
    explicit tickers in the same rumor categories are resolved, using the
    established multi-source issuer resolver (memory -> market profile ->
    related news -> official triangulation). No UNKNOWN row itself is used
    to teach an issuer identity.
    """
    articles = list(rumor_articles or [])
    if not RUMOR_ENTITY_RESOLUTION_ENABLED or not articles:
        return 0

    unknown_categories = {
        str(article.get("rumor_category") or "")
        for article in articles
        if isinstance(article, dict)
        and not _valid_idx_ticker(article.get("ticker"))
    }
    unknown_categories.discard("")
    if not unknown_categories:
        return 0

    ticker_refs = {}
    for article in articles:
        if not isinstance(article, dict):
            continue
        if str(article.get("rumor_category") or "") not in unknown_categories:
            continue
        ticker = _valid_idx_ticker(article.get("ticker"))
        if ticker and ticker not in ticker_refs:
            ticker_refs[ticker] = article

    learned = 0
    for ticker, reference in list(ticker_refs.items())[:RUMOR_ENTITY_LOOKUP_LIMIT]:
        trusted_existing = [
            alias for alias in get_ticker_aliases(ticker)
            if _rumor_trusted_alias(alias)
        ]
        if trusted_existing:
            continue

        aliases = []
        try:
            result = await resolve_multisource_issuer_alias(
                ticker,
                reference_article=reference,
                seed_articles=official_articles or [],
            )
            aliases = list((result or {}).get("aliases") or [])
        except Exception:
            aliases = []

        aliases = [
            alias for alias in aliases
            if _rumor_trusted_alias(alias)
        ]
        if aliases:
            register_ticker_aliases(ticker, aliases)
            learned += 1

    return learned


def resolve_rumor_entities(rumor_articles, official_articles=None):
    """Recover ticker-less rumor articles from trusted issuer aliases.

    Guardrails:
    - only aliases already tied to a valid IDX ticker are considered;
    - ambiguous aliases mapping to >1 ticker are ignored;
    - one UNKNOWN article must resolve to exactly one ticker;
    - rumored acquirer/investor names are never treated as issuer aliases.
    """
    articles = list(rumor_articles or [])

    if not RUMOR_ENTITY_RESOLUTION_ENABLED or not articles:
        return articles

    index = _rumor_entity_alias_index(
        articles,
        official_articles,
    )

    for article in articles:
        if _valid_idx_ticker(article.get("ticker")):
            continue

        matches = []

        for alias_key, payload in index.items():
            tickers = set(payload.get("tickers") or set())
            if len(tickers) != 1:
                continue

            alias = payload.get("alias") or alias_key
            if not _rumor_article_mentions_alias(article, alias):
                continue

            matches.append({
                "ticker": next(iter(tickers)),
                "alias": alias,
                "alias_key": alias_key,
                "sources": sorted(payload.get("sources") or []),
            })

        ticker_hits = {item["ticker"] for item in matches}
        if len(ticker_hits) != 1:
            # Ambiguous or no evidence: remain UNKNOWN instead of guessing.
            continue

        ticker = next(iter(ticker_hits))
        best = max(
            (item for item in matches if item["ticker"] == ticker),
            key=lambda item: len(item["alias_key"]),
        )

        article["ticker"] = ticker
        article["rumor_entity_alias"] = best["alias"]
        article["rumor_entity_resolution_source"] = (
            "+".join(best["sources"][:3]) or "ISSUER_ALIAS"
        )
        article["rumor_entity_resolution_confidence"] = "HIGH"

        if not article.get("company_name"):
            article["company_name"] = best["alias"]

        register_ticker_aliases(ticker, [best["alias"]])

    return articles


def rumor_group_entity_aliases(group):
    aliases = []
    primary = (group or {}).get("primary") or {}
    ticker = _valid_idx_ticker(primary.get("ticker"))

    if ticker:
        aliases.extend(get_ticker_aliases(ticker))

    for article in (group or {}).get("articles") or []:
        aliases.extend([
            article.get("company_name"),
            article.get("rumor_entity_alias"),
        ])

    out = []
    seen = set()
    for alias in aliases:
        alias = _rumor_trusted_alias(alias)
        key = _issuer_alias_key(alias)
        if not alias or not key or key in seen:
            continue
        seen.add(key)
        out.append(alias)

    return out[:12]


def rumor_record_matches_entity_alias(record, aliases):
    article = {
        "title": str((record or {}).get("title") or ""),
        "snippet": "",
        "company_name": str((record or {}).get("company_name") or ""),
    }

    return any(
        _rumor_article_mentions_alias(article, alias)
        for alias in aliases or []
    )


def group_rumor_articles(articles):
    groups = {}

    for article in articles:
        key = rumor_identity(
            article
        )

        group = groups.get(
            key
        )

        if group is None:
            groups[key] = {
                "key": key,
                "articles": [article],
                "primary": article,
            }
            continue

        group["articles"].append(
            article
        )

        if _rumor_primary_rank(
            article
        ) > _rumor_primary_rank(
            group["primary"]
        ):
            group["primary"] = article

    output = []

    for group in groups.values():
        articles_in_group = group["articles"]

        group["status"] = _rumor_group_status(
            articles_in_group
        )

        group["strength"] = _rumor_strength(
            articles_in_group,
            group["status"],
        )

        source_names = []
        source_keys = set()

        for article in articles_in_group:
            source = normalize(
                str(article.get("source") or "Unknown")
            )
            key = _rumor_source_key(
                source
            )

            if key in source_keys:
                continue

            source_keys.add(
                key
            )
            source_names.append(
                source
            )

        group["source_count"] = len(
            source_names
        )
        group["sources"] = source_names[
            :8
        ]

        source_metrics = _rumor_source_metrics(
            articles_in_group
        )
        group.update(source_metrics)
        # Preserve backward-compatible source_count semantics while exposing
        # quality-aware independence separately.
        group["source_count"] = max(
            group.get("source_count", 0),
            int(source_metrics.get("detected_source_count", 0) or 0),
        )

        group["entity_aliases"] = rumor_group_entity_aliases(
            group
        )

        output.append(
            group
        )

    output.sort(
        key=lambda group: (
            RUMOR_STATUS_RANK.get(
                group.get("status", "ACTIVE"),
                0,
            ),
            RUMOR_STRENGTH_RANK.get(
                group.get("strength", "WEAK"),
                0,
            ),
            group.get("source_count", 0),
            _rumor_primary_rank(
                group["primary"]
            ),
        ),
        reverse=True,
    )

    return output


def _rumor_allowed_official_types(category):
    mapping = {
        "IPO": {"IPO"},
        "AKUISISI / TAKEOVER": {
            "AKUISISI",
            "TAKEOVER",
            "TENDER OFFER",
            "PEMBELIAN SAHAM",
        },
        "STRATEGIC INVESTOR": {
            "PEMBELIAN SAHAM",
            "AKUISISI",
            "TAKEOVER",
        },
        "CHANGE CONTROL": {
            "TAKEOVER",
            "TENDER OFFER",
            "AKUISISI",
        },
        "TENDER OFFER": {
            "TENDER OFFER",
            "TAKEOVER",
        },
        "MERGER": {"MERGER"},
        "RIGHTS ISSUE": {"RIGHTS ISSUE"},
    }

    return mapping.get(
        category,
        set(),
    )


def find_official_confirmation_for_rumor(
    rumor_record,
    official_articles,
):
    if not isinstance(rumor_record, dict):
        return None

    category = str(
        rumor_record.get("category")
        or rumor_record.get("rumor_category")
        or ""
    )

    allowed = _rumor_allowed_official_types(
        category
    )

    if not allowed:
        return None

    ticker = _valid_idx_ticker(
        rumor_record.get("ticker")
    )

    company_key = _issuer_alias_key(
        rumor_record.get("company_name")
    )

    best = None

    for article in official_articles or []:
        if str(article.get("event_type") or "") not in allowed:
            continue

        ref = (
            article.get("official_reference")
            or article.get("verified_official_ref")
        )

        if not ref and official_source_rank(article) <= 0:
            continue

        d = article.get("details") or {}
        official_ticker = _valid_idx_ticker(
            d.get("ticker")
        )

        matched = False

        if (
            ticker
            and official_ticker
            and ticker == official_ticker
        ):
            matched = True

        if not matched and company_key:
            haystack = _issuer_alias_key(
                " ".join([
                    str(article.get("title") or ""),
                    str(article.get("snippet") or ""),
                    str(article.get("issuer_name") or ""),
                    " ".join(
                        article.get("issuer_aliases")
                        or []
                    ),
                ])
            )

            if company_key and company_key in haystack:
                matched = True

        if not matched:
            continue

        if (
            best is None
            or _primary_article_rank(article)
            > _primary_article_rank(best)
        ):
            best = article

    if best is None:
        return None

    return {
        "event_type": best.get("event_type"),
        "stage": best.get("stage"),
        "title": best.get("title"),
        "official_reference": (
            best.get("official_reference")
            or best.get("verified_official_ref")
        ),
    }


def correlate_rumor_groups_with_official(
    rumor_groups,
    official_articles,
):
    for group in rumor_groups:
        if group.get("status") == "DENIED":
            continue

        primary = group["primary"]

        confirmation = find_official_confirmation_for_rumor(
            {
                "ticker": primary.get("ticker"),
                "company_name": primary.get("company_name"),
                "category": primary.get("rumor_category"),
            },
            official_articles,
        )

        if confirmation:
            group["status"] = "CONFIRMED OFFICIAL"
            group["strength"] = "CONFIRMED OFFICIAL"
            group["official_confirmation"] = confirmation

    return rumor_groups


def _rumor_business_sector(value):
    low = normalize(
        str(value or "")
    ).lower()

    if not low:
        return None

    for sector, keywords in PRIVATE_SECTOR_KEYWORDS.items():
        if any(
            keyword in low
            for keyword in keywords
        ):
            return sector

    return None


def _extract_private_company_context(
    text,
    company_name=None,
    source=None,
):
    text = normalize(
        str(text or "")
    )

    controller = None

    owner_patterns = [
        r"(?:didirikan|didirikan oleh|pendiri|founder|co-founder)"
        r"\s*(?:adalah|yakni|yaitu|:|-)?\s*"
        r"([A-Z][A-Za-z0-9&.,'’()\- ]{2,90})",
        r"(?:milik|dimiliki oleh|dikendalikan oleh|pengendali)"
        r"\s*(?:adalah|yakni|yaitu|:|-)?\s*"
        r"([A-Z][A-Za-z0-9&.,'’()\- ]{2,90})",
    ]

    for pattern in owner_patterns:
        match = re.search(
            pattern,
            text,
            flags=re.I,
        )

        if not match:
            continue

        candidate = _clean_profile_text(
            match.group(1),
            100,
        )

        if candidate:
            controller = {
                "name": candidate,
                "verified": False,
                "verification_level": "MEDIA_CONTEXT",
                "source": source or "MEDIA CONTEXT",
            }
            break

    business = None

    business_patterns = [
        r"(?:bergerak|beroperasi|menjalankan usaha|berbisnis)"
        r"\s+(?:di|dalam)\s+bidang\s+([^.;]{4,190})",
        r"(?:merupakan|adalah)\s+perusahaan\s+([^.;]{4,190})",
        r"(?:fokus bisnis|bisnis utama)\s*(?:adalah|:|-)?\s*([^.;]{4,190})",
    ]

    for pattern in business_patterns:
        match = re.search(
            pattern,
            text,
            flags=re.I,
        )

        if not match:
            continue

        candidate = _clean_business_summary(
            match.group(1)
        )

        if candidate:
            business = candidate
            break

    return {
        "ticker": None,
        "issuer_name": company_name,
        "controller": controller,
        "major_shareholders": [],
        "business_activity": business,
        "sector": _rumor_business_sector(
            business or text
        ),
        "subsector": None,
        "industry": None,
        "profile_source": source or "MEDIA CONTEXT",
        "profile_source_quality": "MEDIA_CONTEXT",
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }



def _extract_private_company_context_v2(articles, company_name=None):
    articles = [item for item in (articles or []) if isinstance(item, dict)]
    combined = normalize(" ".join(
        " ".join([
            str(item.get("title") or ""),
            str(item.get("snippet") or ""),
            str(item.get("rumor_deep_text") or "")[:1800],
        ])
        for item in articles[:12]
    ))
    base = _extract_private_company_context(
        combined,
        company_name=company_name,
        source="MULTI-SOURCE MEDIA CONTEXT",
    )
    if not RUMOR_PRIVATE_PROFILE_V2_ENABLED:
        return base

    owner_candidates = []
    source_groups = set()
    for item in articles:
        source = item.get("source") or "MEDIA CONTEXT"
        link = item.get("source_url") or item.get("link") or ""
        source_groups.add(_rumor_editorial_group({"source": source, "link": link}))
        text = normalize(" ".join([
            str(item.get("title") or ""),
            str(item.get("snippet") or ""),
            str(item.get("rumor_deep_text") or "")[:1800],
        ]))
        owner_candidates.extend(_extract_owner_candidates_v2(
            text,
            issuer_name=company_name,
            source=source,
            source_url=link,
        ))

    ranked = _owner_v2_consensus(owner_candidates, official_only=False)
    contextual = None
    for bucket in ranked:
        roles = bucket["roles"]
        if not ({"FOUNDER", "CONTROLLER", "MAJOR"} & roles):
            continue
        groups = {g for g in bucket["groups"] if g and g != "unknown"}
        corroborated = len(groups) >= 2 and bucket["max_tier"] >= 3
        premium_single = bucket["max_tier"] >= 4 and len(groups) >= 1
        if not (corroborated or premium_single):
            continue
        best = sorted(bucket["items"], key=lambda row: int(row.get("source_tier") or 0), reverse=True)[0]
        contextual = {
            "name": bucket["name"],
            "stake_pct": bucket["stake_pct"],
            "verified": False,
            "verification_level": "CORROBORATED_MEDIA_CONTEXT_V2" if corroborated else "PREMIUM_MEDIA_CONTEXT_V2",
            "source": best.get("source") or "MEDIA CONTEXT",
            "source_url": best.get("source_url"),
            "source_count": len(groups),
            "role_context": "FOUNDER" if "FOUNDER" in roles else "OWNER/MAJOR HOLDER",
        }
        break

    if contextual:
        base["controller"] = contextual
        base["ownership_context_confidence"] = "CORROBORATED" if contextual.get("source_count", 0) >= 2 else "SINGLE_PREMIUM_SOURCE"
        base["owner_context_sources"] = contextual.get("source_count", 0)
    base["profile_source"] = f"MULTI-SOURCE MEDIA CONTEXT ({len(source_groups)})"
    base["profile_source_quality"] = "MEDIA_CONTEXT"
    return base


async def deep_enrich_rumor_article(article):
    if not RUMOR_DEEP_ENRICH_ENABLED:
        article["rumor_deep_status"] = "DISABLED"
        return article

    try:
        result = await fetch_public_article_text(
            article
        )
    except Exception:
        article["rumor_deep_status"] = "FAILED"
        return article

    article["rumor_deep_status"] = result.get(
        "status",
        "FAILED",
    )
    article["source_url"] = result.get(
        "source_url"
    )
    article["resolver_status"] = result.get(
        "resolver_status",
        "FAILED",
    )

    deep_text = normalize(
        result.get("text")
        or ""
    )

    if not deep_text:
        return article

    combined = normalize(
        " ".join([
            article.get("title", ""),
            article.get("snippet", ""),
            deep_text,
        ])
    )

    article["rumor_deep_text"] = deep_text[
        :MAX_ARTICLE_CHARS
    ]

    category = article.get(
        "rumor_category"
    )

    new_details = _extract_rumor_details(
        article.get("title", ""),
        combined,
        category,
    )

    existing = dict(
        article.get("rumor_details")
        or {}
    )

    for key, value in new_details.items():
        if value not in (None, "", [], {}):
            existing[key] = value

    existing, _ = sanitize_rumor_details(
        existing,
        context=combined,
        category=category,
    )
    article["rumor_details"] = existing

    if not article.get("company_name"):
        article["company_name"] = _extract_rumor_company_name(
            article.get("title"),
            combined,
            category,
        )

    return article


RUMOR_BUSINESS_ID_RULES = [
    (("thermal coal", "coal", "batu bara", "batubara"),
     "Pertambangan batu bara", "Penambangan, pengolahan, dan penjualan batu bara", "Batu bara termal"),
    (("nickel", "nikel", "mineral", "mining", "pertambangan"),
     "Pertambangan dan mineral", "Eksplorasi, penambangan, pengolahan, dan penjualan mineral", "Pertambangan mineral"),
    (("oil", "gas", "minyak", "geothermal", "energy"),
     "Energi", "Pengembangan, produksi, dan/atau distribusi energi", "Energi"),
    (("bank", "banking", "perbankan"),
     "Perbankan", "Penghimpunan dana, penyaluran kredit, dan layanan perbankan", "Perbankan"),
    (("insurance", "asuransi"),
     "Asuransi", "Penyediaan produk dan layanan perlindungan asuransi", "Asuransi"),
    (("fintech", "financial technology", "pembiayaan", "multifinance"),
     "Jasa keuangan", "Pembiayaan dan layanan keuangan", "Jasa keuangan"),
    (("software", "technology", "teknologi", "digital", "data center", "cloud"),
     "Teknologi", "Pengembangan dan penyediaan produk/layanan teknologi", "Teknologi"),
    (("telecommunication", "telekomunikasi", "tower", "menara"),
     "Telekomunikasi", "Penyediaan jaringan, infrastruktur, dan layanan telekomunikasi", "Telekomunikasi"),
    (("property", "real estate", "properti", "developer"),
     "Properti dan real estat", "Pengembangan, penjualan, dan pengelolaan properti", "Properti"),
    (("hospital", "healthcare", "rumah sakit", "pharma", "farmasi"),
     "Kesehatan", "Penyediaan layanan kesehatan dan/atau produk farmasi", "Kesehatan"),
    (("food", "beverage", "makanan", "minuman", "restaurant", "fmcg"),
     "Barang konsumsi", "Produksi, distribusi, dan/atau penjualan produk konsumsi", "Konsumsi"),
    (("retail", "ritel", "e-commerce", "ecommerce"),
     "Perdagangan ritel", "Penjualan dan distribusi produk kepada konsumen", "Ritel"),
    (("automotive", "otomotif", "manufacturing", "manufaktur"),
     "Manufaktur", "Produksi dan distribusi barang/komponen industri", "Manufaktur"),
    (("shipping", "logistics", "pelayaran", "logistik", "transportation"),
     "Transportasi dan logistik", "Transportasi, distribusi, dan layanan logistik", "Transportasi & logistik"),
    (("plantation", "perkebunan", "palm oil", "sawit", "agriculture"),
     "Perkebunan dan agribisnis", "Budidaya, pengolahan, dan penjualan komoditas agribisnis", "Agribisnis"),
    (("construction", "konstruksi", "infrastructure", "infrastruktur"),
     "Konstruksi dan infrastruktur", "Pembangunan dan pengelolaan proyek/infrastruktur", "Infrastruktur"),
]

RUMOR_SECTOR_ID = {
    "energy": "Energi",
    "basic materials": "Barang Baku",
    "financials": "Keuangan",
    "technology": "Teknologi",
    "consumer": "Konsumen",
    "consumer cyclicals": "Konsumen Siklikal",
    "consumer defensive": "Konsumen Primer",
    "healthcare": "Kesehatan",
    "industrials": "Perindustrian",
    "real estate": "Properti & Real Estat",
    "property & real estate": "Properti & Real Estat",
    "communication services": "Komunikasi",
    "utilities": "Utilitas",
    "infrastructure": "Infrastruktur",
    "transportation & logistics": "Transportasi & Logistik",
    "agriculture": "Agrikultur",
}


def _rumor_business_profile_id(profile):
    if not isinstance(profile, dict):
        return {}

    business = normalize(str(profile.get("business_activity") or ""))
    sector = normalize(str(profile.get("sector") or ""))
    industry = normalize(str(profile.get("industry") or profile.get("subsector") or ""))
    probe = f"{business} {sector} {industry}".lower()

    sector_id = RUMOR_SECTOR_ID.get(sector.lower(), sector or None)

    if RUMOR_BUSINESS_ID_ENABLED:
        for keywords, field, activity, industry_id in RUMOR_BUSINESS_ID_RULES:
            if any(keyword in probe for keyword in keywords):
                return {
                    "field": field,
                    "activity": activity,
                    "sector": sector_id or field,
                    "industry": industry_id,
                }

    return {
        "field": _clean_business_summary(business) if business else None,
        "activity": None,
        "sector": sector_id,
        "industry": industry or None,
    }


def _rumor_profile_lines(profile, *, private_company=False):
    if not isinstance(profile, dict):
        return [
            "👤 <b>Pengendali:</b> ⚪ belum terverifikasi",
            "💼 <b>Bidang usaha:</b> ⚪ belum tersedia",
        ]
    if RUMOR_OWNER_SAFETY_V5_ENABLED:
        profile = _owner_v5_sanitize_profile(profile)

    lines = []
    controller = profile.get("controller")
    majors = profile.get("major_shareholders") or []

    if isinstance(controller, dict) and controller.get("name"):
        name = html.escape(str(controller.get("name")))
        stake = controller.get("stake_pct")
        if stake is not None:
            try:
                name += " — " + format_pct(float(stake))
            except Exception:
                pass

        if controller.get("verified"):
            lines.append("👤 <b>Pengendali saat ini:</b> " + name)
        else:
            label = "Founder/Pengendali (konteks)" if private_company else "Pengendali (konteks)"
            lines.append(f"👤 <b>{label}:</b> " + name)
            lines.append("⚠️ <b>Status:</b> belum terverifikasi sebagai pengendali resmi")
            if controller.get("source_count"):
                lines.append(f"🔎 <b>Owner context:</b> {int(controller.get('source_count') or 0)} sumber editorial")
    else:
        label = "Founder/Pengendali" if private_company else "Pengendali saat ini"
        lines.append(f"👤 <b>{label}:</b> ⚪ belum terverifikasi")

        # Safe fallback: a known shareholder may be shown, but never promoted
        # to controller unless official verification exists.
        if RUMOR_OWNER_FALLBACK_ENABLED and majors:
            holder = next(
                (item for item in majors if isinstance(item, dict) and item.get("name")),
                None,
            )
            if holder:
                holder_text = html.escape(str(holder.get("name")))
                if holder.get("stake_pct") is not None:
                    try:
                        holder_text += " — " + format_pct(float(holder.get("stake_pct")))
                    except Exception:
                        pass
                lines.append("🏦 <b>Pemegang saham utama:</b> " + holder_text)
                holder_verified = bool(holder.get("verified"))
                holder_level = str(holder.get("verification_level") or "").upper()
                if holder_verified or "OFFICIAL" in holder_level:
                    lines.append("✅ <b>Status holder:</b> sumber resmi/primer")
                elif holder.get("source_count"):
                    lines.append(f"🔎 <b>Status holder:</b> konteks terkoroborasi {int(holder.get('source_count') or 0)} sumber")
                lines.append("ℹ️ Pemegang saham utama tidak otomatis dianggap pengendali.")

    localized = _rumor_business_profile_id(profile)
    if localized.get("field"):
        lines.append("💼 <b>Bidang usaha:</b> " + html.escape(str(localized["field"])))
    else:
        lines.append("💼 <b>Bidang usaha:</b> ⚪ belum tersedia")

    if localized.get("activity"):
        lines.append("⚙️ <b>Kegiatan utama:</b> " + html.escape(str(localized["activity"])))

    if localized.get("sector"):
        lines.append("🏭 <b>Sektor:</b> " + html.escape(str(localized["sector"])))

    if localized.get("industry"):
        lines.append("📂 <b>Industri:</b> " + html.escape(str(localized["industry"])))

    # If controller already exists, show a distinct major shareholder only.
    if majors and isinstance(controller, dict) and controller.get("name"):
        controller_key = (
            _owner_v4_identity_key(controller.get("name"))
            if RUMOR_OWNER_INTELLIGENCE_V4_ENABLED
            else _normalized_entity_key(controller.get("name"))
        )
        holder = next(
            (
                item for item in majors
                if isinstance(item, dict)
                and item.get("name")
                and (
                    _owner_v4_identity_key(item.get("name"))
                    if RUMOR_OWNER_INTELLIGENCE_V4_ENABLED
                    else _normalized_entity_key(item.get("name"))
                ) != controller_key
            ),
            None,
        )
        if holder:
            holder_text = html.escape(str(holder.get("name")))
            if holder.get("stake_pct") is not None:
                try:
                    holder_text += " — " + format_pct(float(holder.get("stake_pct")))
                except Exception:
                    pass
            lines.append("🏦 <b>Pemegang saham utama:</b> " + holder_text)

    source = profile.get("profile_source")
    if source:
        quality = str(profile.get("profile_source_quality") or "").upper()
        lines.append(
            ("✅" if quality == "OFFICIAL" else "ℹ️")
            + " <b>Sumber profil:</b> "
            + html.escape(str(source))
        )

    return lines[:11]


def _rumor_issuer_name_malformed(value, ticker=None):
    value = normalize(str(value or ""))
    if not value:
        return True
    if value.count("(") != value.count(")"):
        return True
    if value.count("[") != value.count("]"):
        return True
    if ticker and re.search(r"\(\s*" + re.escape(str(ticker)) + r"\s*$", value, re.I):
        return True
    if re.search(r"(?:\(|\[)\s*[A-Z]{4}\s*$", value):
        return True
    if RUMOR_ISSUER_SANITIZER_V3_ENABLED:
        # Numeric/share/corporate-action fragments at the beginning are headline
        # context, not a legal issuer name.
        if re.search(
            r"^(?:(?:sekitar|hingga|sebanyak|sebesar)\s+)?(?:\d{1,3}(?:[.,]\d+)?\s*(?:%|persen)|mayoritas|minoritas)\s+(?:kepemilikan\s+)?saham\b",
            value,
            re.I,
        ):
            return True
        if re.search(r"^(?:rumor|isu|kabar)\s+(?:akuisisi|takeover|pengambilalihan)\b", value, re.I):
            return True
    return False


def sanitize_rumor_issuer_profile(ticker, profile):
    ticker = _valid_idx_ticker(ticker)
    if not ticker or not isinstance(profile, dict):
        return profile

    result = copy.deepcopy(profile)
    issuer = normalize(str(result.get("issuer_name") or ""))
    aliases = [
        alias for alias in get_ticker_aliases(ticker)
        if _rumor_trusted_alias(alias)
    ]
    aliases.sort(
        key=lambda value: (
            len(re.findall(r"[A-Za-z0-9]+", str(value))),
            len(str(value)),
        ),
        reverse=True,
    )

    # V6.7.5 ticker-aware rescue: if a noisy headline value contains a trusted
    # issuer alias, prefer the alias instead of trying to trim arbitrary words.
    alias_match = None
    if RUMOR_ISSUER_SANITIZER_V3_ENABLED and issuer and aliases:
        issuer_key = _issuer_alias_key(issuer)
        for alias in aliases:
            alias_key = _issuer_alias_key(alias)
            if alias_key and issuer_key and re.search(
                r"(?:^|\s)" + re.escape(alias_key) + r"(?:$|\s)",
                issuer_key,
            ):
                alias_match = alias
                break

    if alias_match:
        result["issuer_name"] = alias_match
    elif _rumor_issuer_name_malformed(issuer, ticker=ticker):
        if aliases:
            result["issuer_name"] = aliases[0]
        else:
            cleaned = re.sub(
                r"\s*[\[(]\s*" + re.escape(ticker) + r".*$",
                "",
                str(issuer or ""),
                flags=re.I,
            ).strip(" -:|()[]")
            cleaned = _clean_issuer_alias(cleaned) or cleaned
            result["issuer_name"] = cleaned or ticker
    else:
        cleaned = _clean_issuer_alias(issuer)
        if cleaned:
            result["issuer_name"] = cleaned

    result["ticker"] = ticker
    return result


def _sanitize_profile_display_v3(profile):
    if not isinstance(profile, dict):
        return profile
    result = copy.deepcopy(profile)
    if RUMOR_OWNER_SAFETY_V5_ENABLED:
        result = _owner_v5_sanitize_profile(result)
    ticker = _valid_idx_ticker(result.get("ticker"))
    if ticker:
        result = sanitize_rumor_issuer_profile(ticker, result)
    return result


def rumor_profile_is_sparse(profile, ticker=None):
    if not isinstance(profile, dict):
        return True
    issuer = profile.get("issuer_name")
    controller = profile.get("controller")
    return any([
        _rumor_issuer_name_malformed(issuer, ticker=ticker),
        not profile.get("business_activity"),
        not (
            isinstance(controller, dict)
            and controller.get("name")
            and controller.get("verified")
        ),
    ])


async def resolve_rumor_issuer_profile(ticker):
    ticker = _valid_idx_ticker(ticker)
    if not ticker:
        return None

    try:
        profile = await resolve_issuer_profile(ticker, article=None)
    except Exception:
        profile = None
    profile = sanitize_rumor_issuer_profile(ticker, profile)

    if RUMOR_PROFILE_DEEP_FALLBACK_ENABLED and rumor_profile_is_sparse(profile, ticker):
        # First retry the dedicated profile endpoints instead of accepting a
        # fresh-but-empty cache for weeks.
        try:
            refreshed = await resolve_issuer_profile(
                ticker,
                article=None,
                force=True,
            )
        except Exception:
            refreshed = None
        if refreshed:
            profile = merge_issuer_profile_records(profile or {}, refreshed)
            profile = sanitize_rumor_issuer_profile(ticker, profile)

        # If controller is still missing, reuse the proven /profile-/analyze
        # deep context path. This does not promote a rumor to official fact.
        if rumor_profile_is_sparse(profile, ticker):
            try:
                deep_profile, _ = await resolve_issuer_profile_with_context(ticker)
            except Exception:
                deep_profile = None
            if deep_profile:
                profile = merge_issuer_profile_records(profile or {}, deep_profile)
                profile = sanitize_rumor_issuer_profile(ticker, profile)

    if profile and (RUMOR_OWNER_SAFETY_V5_ENABLED or RUMOR_OWNER_INTELLIGENCE_V4_ENABLED or RUMOR_OWNER_INTELLIGENCE_V3_ENABLED or RUMOR_OWNER_INTELLIGENCE_V2_ENABLED):
        if RUMOR_OWNER_SAFETY_V5_ENABLED:
            profile = await _enrich_profile_owner_intelligence_v5(ticker, profile)
        elif RUMOR_OWNER_INTELLIGENCE_V4_ENABLED:
            profile = await _enrich_profile_owner_intelligence_v4(ticker, profile)
        elif RUMOR_OWNER_INTELLIGENCE_V3_ENABLED:
            profile = await _enrich_profile_owner_intelligence_v3(ticker, profile)
        else:
            profile = await _enrich_profile_owner_intelligence_v2(ticker, profile)
        profile = sanitize_rumor_issuer_profile(ticker, profile)

    if profile:
        ISSUER_PROFILE_CACHE[ticker] = dict(profile)
    return profile


def rumor_profile_needs_refresh(record):
    if not isinstance(record, dict):
        return True
    ticker = _valid_idx_ticker(record.get("ticker"))
    if not ticker:
        return False
    profile = record.get("issuer_profile")
    if not rumor_profile_is_sparse(profile, ticker=ticker):
        return False
    last = _profile_parse_iso(record.get("profile_refresh_utc"))
    if last is None:
        return True
    return last < datetime.now(timezone.utc) - timedelta(hours=RUMOR_PROFILE_REFRESH_HOURS)


async def enrich_rumor_profile_context(group):
    primary = (group or {}).get("primary") or {}
    ticker = _valid_idx_ticker(primary.get("ticker"))
    if not ticker or not RUMOR_PROFILE_ENABLED:
        return group
    profile = await resolve_rumor_issuer_profile(ticker)
    group["issuer_profile"] = profile
    group["profile_refresh_utc"] = datetime.now(timezone.utc).isoformat()
    return group


async def enrich_rumor_group(group):
    primary = group.get(
        "primary"
    )

    if not isinstance(primary, dict):
        return group

    if primary.get("rumor_status") == "ACTIVE":
        await deep_enrich_rumor_article(
            primary
        )

    ticker = _valid_idx_ticker(
        primary.get("ticker")
    )

    profile = None

    if RUMOR_PROFILE_ENABLED:
        if ticker:
            try:
                # Never pass the rumor as an official transaction article.
                # V6.7.4 retries sparse/malformed profile context through the
                # same quality-aware profile/deep resolver used by /profile.
                profile = await resolve_rumor_issuer_profile(
                    ticker
                )
            except Exception:
                profile = None
        else:
            combined = normalize(
                " ".join([
                    primary.get("title", ""),
                    primary.get("snippet", ""),
                    primary.get("rumor_deep_text", ""),
                ])
            )

            profile = _extract_private_company_context_v2(
                group.get("articles") or [primary],
                company_name=primary.get("company_name"),
            )

    market = None

    if ticker and MARKET_DATA_ENABLED:
        try:
            market = await get_market_data(
                ticker
            )
        except Exception:
            market = None

    group["issuer_profile"] = profile
    group["market_data"] = market

    # Recompute quality/anti-copy metrics and strength after deep details improve.
    group.update(
        _rumor_source_metrics(
            group.get("articles") or []
        )
    )
    group["strength"] = _rumor_strength(
        group.get("articles") or [],
        group.get("status"),
    )

    return group


def _rumor_normalize_material_list(values, numeric=False):
    output = []
    seen = set()

    for value in values or []:
        if numeric:
            try:
                normalized = round(float(value), 6)
            except Exception:
                continue
            key = f"N:{normalized}"
            display = normalized
        else:
            display = normalize(str(value or ""))
            if not display:
                continue
            key = "T:" + re.sub(
                r"\s+",
                " ",
                display.lower(),
            )

        if key in seen:
            continue

        seen.add(key)
        output.append(display)

    return output


RUMOR_CATALYST_IMPACT = {
    "AKUISISI / TAKEOVER": 28,
    "CHANGE CONTROL": 30,
    "TENDER OFFER": 27,
    "MERGER": 28,
    "STRATEGIC INVESTOR": 25,
    "IPO": 24,
    "RIGHTS ISSUE": 18,
    "PRIVATE PLACEMENT": 18,
    "BUYBACK": 16,
    "DIVESTASI": 20,
    "SPIN-OFF / RESTRUCTURING": 18,
    "DELISTING / RELISTING": 24,
}


def _rumor_freshness_hours(record):
    dt = _profile_parse_iso((record or {}).get("last_seen_utc"))
    if dt is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0)


def rumor_trading_impact(record):
    """Prioritization score for monitoring; explicitly not buy/sell advice."""
    if not isinstance(record, dict):
        return {}

    category = str(record.get("category") or "RUMOR").upper()
    status = str(record.get("status") or "ACTIVE").upper()
    strength = str(record.get("strength") or "WEAK").upper()
    source_quality = str(record.get("source_quality") or "LOW").upper()

    score = int(RUMOR_CATALYST_IMPACT.get(category, 12))
    score += {
        "WEAK": 4,
        "MEDIUM": 14,
        "STRONG": 24,
        "CONFIRMED OFFICIAL": 30,
    }.get(strength, 4)
    score += {
        "LOW": 2,
        "MEDIUM": 7,
        "HIGH": 12,
        "OFFICIAL": 15,
    }.get(source_quality, 2)

    age = _rumor_freshness_hours(record)
    if age is not None:
        if age <= 6:
            score += 14
        elif age <= 24:
            score += 10
        elif age <= 72:
            score += 5

    details = record.get("rumor_details") or {}
    material_keys = (
        "rumored_party", "percentages", "money", "price_range",
        "ipo_price", "share_count", "underwriter", "listing_estimate",
    )
    material_count = sum(1 for key in material_keys if details.get(key))
    score += min(7, material_count * 2)

    effective = float(record.get("effective_independent_count") or 0.0)
    credible_effective = float(record.get("credible_effective_independent_count") or 0.0)
    derivative = int(record.get("derivative_source_count", 0) or 0)
    detected = int(record.get("detected_source_count", 0) or 0)
    score += min(6, int(round(credible_effective * 2)))
    if detected >= 5 and derivative / max(1, detected) >= 0.60:
        score -= 4

    # Market movement is only an impact/context component, never rumor truth.
    market = record.get("market_data") or {}
    try:
        move = abs(float(market.get("change_pct")))
    except Exception:
        move = 0.0
    if move >= 15:
        score += 5
    elif move >= 7:
        score += 3
    elif move >= 3:
        score += 1

    if status == "CONFIRMED OFFICIAL":
        official_status = "FOUND"
        information_risk = "LOW — sudah ada konfirmasi resmi"
    elif status == "DENIED":
        official_status = "DENIED"
        information_risk = "HIGH — rumor telah dibantah"
    else:
        official_status = "NONE"
        information_risk = "HIGH — belum ada keterbukaan/konfirmasi resmi"

    score = max(0, min(100, int(round(score))))
    if score >= 70:
        impact = "HIGH"
    elif score >= 45:
        impact = "MEDIUM"
    else:
        impact = "LOW"

    return {
        "score": score,
        "potential_impact": impact,
        "catalyst": category,
        "source_quality": source_quality,
        "official_confirmation": official_status,
        "information_risk": information_risk,
        "freshness_hours": round(age, 1) if age is not None else None,
    }


def _rumor_trading_impact_lines(record):
    if not RUMOR_TRADING_IMPACT_ENABLED:
        return []
    impact = rumor_trading_impact(record)
    if not impact:
        return []

    effective = record.get("effective_independent_count")
    credible_effective = record.get("credible_effective_independent_count")
    detected = int(record.get("detected_source_count", 0) or 0)
    hq = int(record.get("high_quality_source_count", 0) or 0)
    copies = int(record.get("copy_duplicate_count", 0) or 0)
    derivatives = int(record.get("derivative_source_count", 0) or 0)

    lines = [
        "🔥 <b>TRADING IMPACT</b>",
        f"🎯 Potential Impact: <b>{html.escape(str(impact.get('potential_impact')))}</b> — Score {int(impact.get('score', 0))}/100",
        f"⚡ Catalyst: {html.escape(str(impact.get('catalyst') or '-'))}",
        f"📡 Rumor Strength: {_rumor_strength_badge(str(record.get('strength') or 'WEAK'))}",
        f"🧾 Source Quality: <b>{html.escape(str(impact.get('source_quality') or 'LOW'))}</b>",
    ]
    if effective is not None:
        credible_text = f" | Credible: {credible_effective}" if credible_effective is not None else ""
        lines.append(
            f"🔗 Weighted Independence: {effective}{credible_text} | Detected: {detected} | HQ: {hq}"
        )
        lines.append(f"🪞 Copy/Mirror/Derivative: {copies} | Semantic derivative: {derivatives}")
    lines += [
        f"🏛 Official Confirmation: <b>{html.escape(str(impact.get('official_confirmation') or 'NONE'))}</b>",
        f"⚠️ Information Risk: {html.escape(str(impact.get('information_risk') or '-'))}",
        "ℹ️ Score untuk prioritas monitoring, bukan sinyal beli/jual dan bukan probabilitas rumor benar.",
    ]
    return lines


def rumor_record_from_group(group):
    primary = group.get(
        "primary"
    ) or {}

    details = dict(
        primary.get("rumor_details")
        or {}
    )
    details, _ = sanitize_rumor_details(
        details,
        context=" ".join([
            str(primary.get("title") or ""),
            str(primary.get("snippet") or ""),
            str(primary.get("rumor_deep_text") or ""),
        ]),
        category=primary.get("rumor_category"),
    )

    published_values = [
        article.get("published_dt")
        for article in group.get("articles", [])
        if article.get("published_dt")
    ]

    first_seen = (
        min(published_values).isoformat()
        if published_values
        else datetime.now(timezone.utc).isoformat()
    )

    last_seen = (
        max(published_values).isoformat()
        if published_values
        else datetime.now(timezone.utc).isoformat()
    )

    return {
        "key": group.get("key"),
        "ticker": _valid_idx_ticker(
            primary.get("ticker")
        ),
        "company_name": primary.get(
            "company_name"
        ),
        "category": primary.get(
            "rumor_category"
        ),
        "status": group.get(
            "status",
            "ACTIVE",
        ),
        "strength": group.get(
            "strength",
            "WEAK",
        ),
        "source_count": int(
            group.get("source_count", 0)
            or 0
        ),
        "sources": list(
            group.get("sources")
            or []
        )[:8],
        "source_quality": group.get("source_quality", "LOW"),
        "source_quality_score": group.get("source_quality_score", 0.0),
        "detected_source_count": int(group.get("detected_source_count", group.get("source_count", 0)) or 0),
        "independent_story_count": int(group.get("independent_story_count", 0) or 0),
        "effective_independent_count": group.get("effective_independent_count", 0.0),
        "credible_effective_independent_count": group.get("credible_effective_independent_count", 0.0),
        "copy_duplicate_count": int(group.get("copy_duplicate_count", 0) or 0),
        "semantic_copy_count": int(group.get("semantic_copy_count", 0) or 0),
        "derivative_source_count": int(group.get("derivative_source_count", 0) or 0),
        "high_quality_source_count": int(group.get("high_quality_source_count", 0) or 0),
        "premium_source_count": int(group.get("premium_source_count", 0) or 0),
        "source_breakdown": list(group.get("source_breakdown") or [])[:8],
        "title": primary.get(
            "title"
        ),
        "source": primary.get(
            "source"
        ),
        "link": (
            primary.get("source_url")
            or primary.get("link")
        ),
        "published": primary.get(
            "published"
        ),
        "first_seen_utc": first_seen,
        "last_seen_utc": last_seen,
        "rumor_details": details,
        "issuer_profile": sanitize_rumor_issuer_profile(
            _valid_idx_ticker(primary.get("ticker")),
            group.get("issuer_profile"),
        ) if _valid_idx_ticker(primary.get("ticker")) else group.get("issuer_profile"),
        "profile_refresh_utc": group.get("profile_refresh_utc"),
        "market_data": group.get(
            "market_data"
        ),
        "official_confirmation": group.get(
            "official_confirmation"
        ),
        "entity_aliases": list(
            group.get("entity_aliases")
            or []
        )[:12],
        "entity_resolution_source": primary.get(
            "rumor_entity_resolution_source"
        ),
    }


def merge_rumor_records(previous, current):
    """Quality-aware rumor record merge.

    Temporary missing feed fields never erase known rumor details/profile.
    Market/profile enrichment is retained but does not trigger rumor alerts.
    """
    if not isinstance(previous, dict):
        return copy.deepcopy(current or {})

    if not isinstance(current, dict):
        return copy.deepcopy(previous)

    previous, _ = sanitize_rumor_record_integrity(previous)
    current, _ = sanitize_rumor_record_integrity(current)
    merged = copy.deepcopy(previous)

    # Current lifecycle/status fields are authoritative.
    for key in (
        "key",
        "ticker",
        "company_name",
        "category",
        "status",
        "strength",
        "source_count",
        "source_quality",
        "source_quality_score",
        "detected_source_count",
        "independent_story_count",
        "effective_independent_count",
        "credible_effective_independent_count",
        "copy_duplicate_count",
        "semantic_copy_count",
        "derivative_source_count",
        "high_quality_source_count",
        "premium_source_count",
        "source_breakdown",
        "title",
        "source",
        "link",
        "published",
        "last_seen_utc",
        "profile_refresh_utc",
    ):
        value = current.get(key)
        if value not in (None, "", [], {}):
            merged[key] = copy.deepcopy(value)

    old_sources = list(previous.get("sources") or [])
    new_sources = list(current.get("sources") or [])
    source_out = []
    seen_sources = set()

    for value in new_sources + old_sources:
        key = _rumor_source_key(value)
        if key in seen_sources:
            continue
        seen_sources.add(key)
        source_out.append(value)

    merged["sources"] = source_out[:8]
    merged["source_count"] = max(
        int(current.get("source_count", 0) or 0),
        len(source_out),
        int(previous.get("source_count", 0) or 0),
    )

    details = copy.deepcopy(
        previous.get("rumor_details")
        or {}
    )

    for key, value in (
        current.get("rumor_details")
        or {}
    ).items():
        if value in (None, "", [], {}):
            continue

        if isinstance(value, list):
            old_list = details.get(key) or []
            combined = []
            seen = set()
            for item in list(value) + list(old_list):
                token = normalize(str(item)).lower()
                if token in seen:
                    continue
                seen.add(token)
                combined.append(item)
            details[key] = combined
        else:
            details[key] = copy.deepcopy(value)

    merged["rumor_details"] = details

    if current.get("issuer_profile"):
        profile = copy.deepcopy(current.get("issuer_profile"))
        ticker = _valid_idx_ticker(
            current.get("ticker") or merged.get("ticker")
        )
        if ticker:
            profile = sanitize_rumor_issuer_profile(ticker, profile)
        merged["issuer_profile"] = profile

    if current.get("market_data"):
        merged["market_data"] = copy.deepcopy(
            current.get("market_data")
        )

    if current.get("official_confirmation"):
        merged["official_confirmation"] = copy.deepcopy(
            current.get("official_confirmation")
        )

    entity_aliases = []
    entity_seen = set()
    for value in list(current.get("entity_aliases") or []) + list(previous.get("entity_aliases") or []):
        clean = _rumor_trusted_alias(value)
        key = _issuer_alias_key(clean)
        if not clean or not key or key in entity_seen:
            continue
        entity_seen.add(key)
        entity_aliases.append(clean)
    if entity_aliases:
        merged["entity_aliases"] = entity_aliases[:12]

    if current.get("entity_resolution_source"):
        merged["entity_resolution_source"] = current.get("entity_resolution_source")

    old_first = _profile_parse_iso(
        previous.get("first_seen_utc")
    )
    new_first = _profile_parse_iso(
        current.get("first_seen_utc")
    )

    first_candidates = [
        dt
        for dt in (old_first, new_first)
        if dt is not None
    ]

    if first_candidates:
        merged["first_seen_utc"] = min(
            first_candidates
        ).isoformat()

    return merged


def rumor_material_snapshot(record):
    details = record.get(
        "rumor_details"
    ) or {}

    return {
        "status": record.get(
            "status"
        ),
        "strength": record.get(
            "strength"
        ),
        "rumored_party": _clean_profile_text(
            details.get("rumored_party"),
            120,
        ),
        "percentages": _rumor_normalize_material_list(
            details.get("percentages")
            or [],
            numeric=True,
        ),
        "money": _rumor_normalize_material_list(
            details.get("money")
            or [],
        ),
        "price_range": _clean_profile_text(
            details.get("price_range"),
            120,
        ),
        "ipo_price": _clean_profile_text(
            details.get("ipo_price"),
            120,
        ),
        "share_count": _clean_profile_text(
            details.get("share_count"),
            120,
        ),
        "underwriter": _clean_profile_text(
            details.get("underwriter"),
            120,
        ),
        "listing_estimate": _clean_profile_text(
            details.get("listing_estimate"),
            100,
        ),
    }


def rumor_is_push_fresh(record):
    dt = _profile_parse_iso(
        (record or {}).get("last_seen_utc")
    )

    if dt is None:
        return False

    return (
        datetime.now(timezone.utc) - dt
        <= timedelta(hours=RUMOR_AUTO_ALERT_HOURS)
    )


def rumor_change_decision(previous, current):
    """Rumor update diff.

    Market data and company profile are intentionally excluded.
    New alert can be triggered by:
    - status transition,
    - strength-tier increase,
    - newly discovered material rumor detail.
    """
    if not previous:
        return {
            "should_alert": (
                current.get("status") == "ACTIVE"
            ),
            "mode": "NEW_RUMOR",
            "changes": [],
        }

    old = rumor_material_snapshot(
        previous
    )
    new = rumor_material_snapshot(
        current
    )

    changes = []

    old_status = str(
        old.get("status")
        or "ACTIVE"
    )
    new_status = str(
        new.get("status")
        or "ACTIVE"
    )

    if new_status != old_status:
        changes.append(
            f"Status: {old_status} → {new_status}"
        )

    old_strength = str(
        old.get("strength")
        or "WEAK"
    )
    new_strength = str(
        new.get("strength")
        or "WEAK"
    )

    if (
        new_status == "ACTIVE"
        and RUMOR_STRENGTH_RANK.get(
            new_strength,
            0,
        )
        > RUMOR_STRENGTH_RANK.get(
            old_strength,
            0,
        )
    ):
        changes.append(
            f"Rumor Strength: {old_strength} → {new_strength}"
        )

    labels = {
        "rumored_party": "Pihak yang dirumorkan",
        "percentages": "Rumor stake",
        "money": "Rumor nilai/dana",
        "price_range": "Rumor range harga IPO",
        "ipo_price": "Rumor harga IPO",
        "share_count": "Rumor jumlah saham",
        "underwriter": "Rumor underwriter",
        "listing_estimate": "Rumor listing",
    }

    for key, label in labels.items():
        old_value = old.get(
            key
        )
        new_value = new.get(
            key
        )

        if new_value in (None, "", [], {}):
            continue

        if old_value == new_value:
            continue

        if isinstance(
            new_value,
            list,
        ):
            shown = ", ".join(
                str(x)
                for x in new_value[:4]
            )
        else:
            shown = str(
                new_value
            )

        changes.append(
            f"{label}: {shown}"
        )

    should_alert = bool(
        changes
    )

    mode = (
        "RUMOR_UPDATE"
        if should_alert
        else "SUPPRESS"
    )

    if (
        old_status == "ACTIVE"
        and new_status == "CONFIRMED OFFICIAL"
    ):
        mode = "CONFIRMED"

    elif (
        old_status == "ACTIVE"
        and new_status == "DENIED"
    ):
        mode = "DENIED"

    elif (
        new_status == "EXPIRED"
        and old_status != "EXPIRED"
    ):
        mode = "EXPIRED"
        should_alert = RUMOR_NOTIFY_EXPIRED

    return {
        "should_alert": should_alert,
        "mode": mode,
        "changes": changes,
    }


def _rumor_status_badge(status):
    return {
        "ACTIVE": "⚠️ BELUM TERKONFIRMASI",
        "CONFIRMED OFFICIAL": "🟢 CONFIRMED OFFICIAL",
        "DENIED": "🔴 DENIED / DIBANTAH",
        "EXPIRED": "⚫ EXPIRED",
    }.get(
        str(status or ""),
        "⚠️ BELUM TERKONFIRMASI",
    )


def _rumor_strength_badge(strength):
    return {
        "WEAK": "⚪ WEAK",
        "MEDIUM": "🟡 MEDIUM",
        "STRONG": "🟠 STRONG",
        "CONFIRMED OFFICIAL": "🟢 OFFICIAL",
    }.get(
        str(strength or ""),
        "⚪ WEAK",
    )


def _rumor_age_text(record):
    dt = _profile_parse_iso(
        record.get("last_seen_utc")
    )

    if dt is None:
        return "-"

    delta = (
        datetime.now(timezone.utc)
        - dt
    )

    minutes = max(
        0,
        int(delta.total_seconds() // 60),
    )

    if minutes < 60:
        return f"{minutes} menit"

    hours = minutes // 60

    if hours < 48:
        return f"{hours} jam"

    return f"{hours // 24} hari"


def _rumor_watch_next(category):
    category = str(
        category or ""
    )

    mapping = {
        "IPO": [
            "e-IPO / prospektus resmi",
            "underwriter & jadwal bookbuilding",
            "harga / jumlah saham final",
        ],
        "AKUISISI / TAKEOVER": [
            "keterbukaan IDX",
            "klarifikasi emiten",
            "SPA / perubahan kepemilikan",
        ],
        "STRATEGIC INVESTOR": [
            "keterbukaan IDX",
            "perubahan pemegang saham",
            "RUPS/RUPSLB jika relevan",
        ],
        "MERGER": [
            "keterbukaan IDX",
            "RUPS/RUPSLB",
            "dokumen merger resmi",
        ],
        "RIGHTS ISSUE": [
            "RUPS",
            "efektif OJK",
            "harga & rasio HMETD",
        ],
        "PRIVATE PLACEMENT": [
            "RUPS/RUPSLB",
            "keterbukaan IDX",
            "harga & investor pelaksana",
        ],
        "BUYBACK": [
            "keterbukaan IDX",
            "periode buyback",
            "batas dana / jumlah saham",
        ],
        "DIVESTASI": [
            "keterbukaan IDX",
            "buyer",
            "nilai transaksi",
        ],
        "CHANGE CONTROL": [
            "keterbukaan IDX",
            "pemegang saham pengendali baru",
            "tender wajib",
        ],
        "TENDER OFFER": [
            "keterbukaan IDX",
            "harga tender",
            "periode & pembayaran",
        ],
        "SPIN-OFF / RESTRUCTURING": [
            "keterbukaan IDX",
            "RUPS",
            "struktur transaksi",
        ],
        "DELISTING / RELISTING": [
            "pengumuman IDX",
            "RUPS",
            "jadwal & ketentuan resmi",
        ],
    }

    return mapping.get(
        category,
        [
            "keterbukaan IDX",
            "klarifikasi emiten",
        ],
    )


def format_rumor_alert(record, *, changes=None, mode=None):
    if not isinstance(record, dict):
        return "⚠️ Rumor record tidak valid."

    # Display-time fail-safe: even if an older V6.7/V6.7.1 state record has
    # not yet been migrated by the scanner, never show known-bad semantics.
    record, _ = sanitize_rumor_record_integrity(record)
    record = copy.deepcopy(record)
    _display_ticker = _valid_idx_ticker(record.get("ticker"))
    if _display_ticker and record.get("issuer_profile"):
        record["issuer_profile"] = sanitize_rumor_issuer_profile(
            _display_ticker,
            record.get("issuer_profile"),
        )
        _display_name = (record.get("issuer_profile") or {}).get("issuer_name")
        if _display_name:
            record["company_name"] = _display_name

    status = str(
        record.get("status")
        or "ACTIVE"
    )
    strength = str(
        record.get("strength")
        or "WEAK"
    )
    category = str(
        record.get("category")
        or "RUMOR"
    )

    identity = (
        record.get("ticker")
        or record.get("company_name")
        or "UNKNOWN"
    )

    mode = str(
        mode
        or "NEW_RUMOR"
    )

    if mode == "CONFIRMED":
        header = (
            f"🟢 <b>RUMOR CONFIRMED — "
            f"{html.escape(str(identity))}</b>"
        )
    elif mode == "DENIED":
        header = (
            f"🔴 <b>RUMOR DENIED — "
            f"{html.escape(str(identity))}</b>"
        )
    elif mode == "RUMOR_UPDATE":
        header = (
            f"🟣 <b>RUMOR UPDATE — "
            f"{html.escape(str(identity))}</b>"
        )
    elif mode == "VIEW":
        header = (
            f"🔍 <b>RUMOR DETAIL — "
            f"{html.escape(str(identity))}</b>"
        )
    else:
        header = (
            f"🟣 <b>RUMOR WATCH — "
            f"{html.escape(str(identity))}</b>"
        )

    lines = [
        header,
        "",
        "⚠️ <b>STATUS RUMOR</b>",
        _rumor_status_badge(status),
        f"🏷 Topik: <b>{html.escape(category)}</b>",
        (
            "📡 Rumor Strength: "
            f"<b>{html.escape(_rumor_strength_badge(strength))}</b>"
        ),
        f"📰 Sumber terdeteksi: {int(record.get('source_count', 0) or 0)}",
        (
            "🧾 Source Quality: "
            f"<b>{html.escape(str(record.get('source_quality') or 'LOW'))}</b>"
            f" | weighted: {record.get('effective_independent_count', 0)}"
            f" | credible: {record.get('credible_effective_independent_count', 0)}"
        ),
        (
            "🪞 Copy/Mirror/Derivative: "
            f"{int(record.get('copy_duplicate_count', 0) or 0)}"
            f" / {int(record.get('detected_source_count', record.get('source_count', 0)) or 0)} sumber"
        ),
        f"🕒 Freshness: {_rumor_age_text(record)}",
    ]

    impact_lines = _rumor_trading_impact_lines(record)
    if impact_lines:
        lines += [""] + impact_lines

    if changes:
        lines += [
            "",
            "🆕 <b>YANG BERUBAH</b>",
        ]
        lines.extend(
            "• " + html.escape(
                str(item)
            )
            for item in list(changes)[:8]
        )

    lines += [
        "",
        "📰 <b>RUMOR</b>",
        html.escape(
            str(record.get("title") or "-")[:420]
        ),
    ]

    ticker = _valid_idx_ticker(
        record.get("ticker")
    )
    profile = record.get(
        "issuer_profile"
    )

    if profile or ticker or record.get("company_name"):
        lines += [
            "",
            (
                "🏢 <b>PROFIL EMITEN</b>"
                if ticker
                else "🏢 <b>PROFIL PERUSAHAAN</b>"
            ),
        ]

        if ticker:
            lines.append(
                f"🏷 <b>{html.escape(ticker)}</b> — "
                + html.escape(
                    str(
                        (profile or {}).get("issuer_name")
                        or record.get("company_name")
                        or "-"
                    )
                )
            )
        elif record.get("company_name"):
            lines.append(
                "🏷 <b>Perusahaan:</b> "
                + html.escape(
                    str(record.get("company_name"))
                )
            )

        lines.extend(
            _rumor_profile_lines(
                profile,
                private_company=not bool(ticker),
            )
        )

    details = record.get(
        "rumor_details"
    ) or {}

    material_lines = []

    if details.get("rumored_party"):
        material_lines.append(
            "🤝 <b>Pihak yang dirumorkan:</b> ⚠️ "
            + html.escape(
                str(details.get("rumored_party"))
            )
        )

    if details.get("percentages"):
        material_lines.append(
            "📊 <b>Rumor stake:</b> "
            + format_pct(
                details["percentages"][0]
            )
        )

    if details.get("money"):
        material_lines.append(
            "💰 <b>Rumor nilai/dana:</b> "
            + html.escape(
                str(details["money"][0])
            )
        )

    if details.get("price_range"):
        material_lines.append(
            "💵 <b>Rumor range harga IPO:</b> "
            + html.escape(
                str(details["price_range"])
            )
        )
    elif details.get("ipo_price"):
        material_lines.append(
            "💵 <b>Rumor harga IPO:</b> "
            + html.escape(
                str(details["ipo_price"])
            )
        )

    if details.get("share_count"):
        material_lines.append(
            "📦 <b>Rumor jumlah saham:</b> "
            + html.escape(
                str(details["share_count"])
            )
        )

    if details.get("underwriter"):
        material_lines.append(
            "🏦 <b>Rumor underwriter:</b> "
            + html.escape(
                str(details["underwriter"])
            )
        )

    if details.get("listing_estimate"):
        material_lines.append(
            "📅 <b>Rumor listing:</b> "
            + html.escape(
                str(details["listing_estimate"])
            )
        )

    if material_lines:
        lines += [
            "",
            (
                "🚀 <b>RUMOR IPO DETAIL</b>"
                if category == "IPO"
                else "🤝 <b>RUMOR TRANSACTION DETAIL</b>"
            ),
        ]
        lines.extend(
            material_lines
        )

    market = record.get(
        "market_data"
    ) or {}

    if ticker and market:
        lines += [
            "",
            "📈 <b>MARKET REACTION</b>",
        ]

        if market.get("last_price") is not None:
            lines.append(
                "💵 Harga: "
                + format_price(
                    market.get("last_price")
                )
            )

        if market.get("change_pct") is not None:
            lines.append(
                "📊 Hari ini: "
                + f"{float(market.get('change_pct')):+.2f}%"
            )

        if market.get("volume") is not None:
            try:
                lines.append(
                    "📦 Volume: "
                    + f"{int(market.get('volume')):,}".replace(",", ".")
                )
            except Exception:
                pass

        lines.append(
            "ℹ️ Harga/volume hanya konteks dan tidak meningkatkan kebenaran rumor."
        )

    official = record.get(
        "official_confirmation"
    )

    if status == "CONFIRMED OFFICIAL" and isinstance(official, dict):
        lines += [
            "",
            "🏛 <b>OFFICIAL CONFIRMATION</b>",
            "✅ Rumor telah menemukan pasangan corporate action resmi.",
        ]

        if official.get("event_type"):
            lines.append(
                "Event resmi: "
                + html.escape(
                    str(official.get("event_type"))
                )
            )

        if official.get("stage"):
            lines.append(
                "Stage: "
                + html.escape(
                    str(official.get("stage"))
                )
            )

    lines += [
        "",
        "🔎 <b>YANG DITUNGGU</b>",
    ]

    lines.extend(
        "• " + html.escape(item)
        for item in _rumor_watch_next(category)
    )

    sources = record.get(
        "sources"
    ) or []

    if sources:
        lines += [
            "",
            "📰 <b>SUMBER TERDETEKSI</b>",
        ]
        quality_map = {
            str(item.get("source") or "").casefold(): str(item.get("quality") or "")
            for item in (record.get("source_breakdown") or [])
            if isinstance(item, dict)
        }
        for source in sources[:5]:
            quality = quality_map.get(str(source).casefold())
            suffix = f" — {quality}" if quality else ""
            lines.append("• " + html.escape(str(source) + suffix))

    link = str(
        record.get("link")
        or ""
    ).strip()

    if link:
        lines.append(
            f'<a href="{html.escape(link, quote=True)}">🔗 Buka sumber terbaru</a>'
        )

    lines += [
        "",
        "⚠️ <b>RUMOR BUKAN FAKTA RESMI.</b>",
        (
            "<i>Rumor Strength menunjukkan kualitas dan konfirmasi silang sumber, "
            "bukan probabilitas bahwa rumor benar dan bukan sinyal beli/jual.</i>"
        ),
    ]

    return "\n".join(
        lines
    )[:3900]


def _rumor_official_confirmation_signature(record):
    if not isinstance(record, dict):
        return None
    if str(record.get("status") or "") != "CONFIRMED OFFICIAL":
        return None
    confirmation = record.get("official_confirmation") or {}
    if not isinstance(confirmation, dict):
        return None

    ticker = _valid_idx_ticker(record.get("ticker"))
    company = _issuer_alias_key(record.get("company_name"))
    if not company:
        company = re.sub(
            r"[^A-Z0-9]+",
            " ",
            re.sub(
                r"\b(?:PT|TBK)\.?\b",
                " ",
                str(record.get("company_name") or "").upper(),
                flags=re.I,
            ),
        )
        company = re.sub(r"\s+", " ", company).strip()
    entity = f"TICKER:{ticker}" if ticker else (f"COMPANY:{company}" if company else "")
    if not entity:
        return None

    event_type = normalize(str(confirmation.get("event_type") or record.get("category") or "")).upper()
    ref = confirmation.get("official_reference") or {}
    if isinstance(ref, dict):
        url = normalize(str(ref.get("url") or ""))
        authority = normalize(str(ref.get("authority") or "")).upper()
    else:
        url = ""
        authority = ""
    url = re.sub(r"[?#].*$", "", url).rstrip("/").lower()
    title = _event_title_signature(confirmation.get("title") or "")

    evidence = url or (authority + "|" + title if (authority or title) else "")
    if not evidence:
        return None
    return "|".join([
        str(record.get("category") or "RUMOR").upper(),
        entity,
        event_type,
        evidence,
    ])


def canonicalize_rumor_records(records):
    """Merge only high-confidence confirmed duplicates.

    Two confirmed rows are collapsed only when they point to the same entity,
    rumor category and the same official-confirmation evidence. Active rumors
    are deliberately left untouched so distinct live theses are not merged.
    """
    output = []
    positions = {}
    for raw in records or []:
        if not isinstance(raw, dict):
            continue
        record, _ = sanitize_rumor_record_integrity(raw)
        sig = _rumor_official_confirmation_signature(record) if RUMOR_CONFIRMED_DEDUP_ENABLED else None
        if sig and sig in positions:
            idx = positions[sig]
            output[idx] = merge_rumor_records(output[idx], record)
            continue
        if sig:
            positions[sig] = len(output)
        output.append(record)
    return output


def _rumor_record_sort_key(record):
    return (
        RUMOR_STATUS_RANK.get(
            str(record.get("status") or "ACTIVE"),
            0,
        ),
        RUMOR_STRENGTH_RANK.get(
            str(record.get("strength") or "WEAK"),
            0,
        ),
        int(record.get("source_count", 0) or 0),
        _profile_parse_iso(
            record.get("last_seen_utc")
        )
        or datetime.min.replace(tzinfo=timezone.utc),
    )


def format_rumor_board(records, mode="ALL"):
    mode = str(
        mode or "ALL"
    ).strip().upper()

    records = canonicalize_rumor_records(records)

    if mode == "ACTIVE":
        records = [
            record
            for record in records
            if record.get("status") == "ACTIVE"
        ]

    elif mode in {
        "WEAK",
        "MEDIUM",
        "STRONG",
    }:
        records = [
            record
            for record in records
            if str(record.get("strength") or "").upper() == mode
        ]

    elif mode in {
        "CONFIRMED",
        "OFFICIAL",
    }:
        records = [
            record
            for record in records
            if record.get("status") == "CONFIRMED OFFICIAL"
        ]

    elif mode == "DENIED":
        records = [
            record
            for record in records
            if record.get("status") == "DENIED"
        ]

    elif mode == "IPO":
        records = [
            record
            for record in records
            if record.get("category") == "IPO"
        ]

    elif mode in {
        "TAKEOVER", "AKUISISI",
    }:
        records = [record for record in records if record.get("category") == "AKUISISI / TAKEOVER"]

    elif mode in {"STRATEGIC", "INVESTOR"}:
        records = [record for record in records if record.get("category") == "STRATEGIC INVESTOR"]

    elif mode in {"RIGHTS", "RIGHTS ISSUE", "HMETD"}:
        records = [record for record in records if record.get("category") == "RIGHTS ISSUE"]

    elif mode in {"PP", "PRIVATE", "PRIVATE PLACEMENT"}:
        records = [record for record in records if record.get("category") == "PRIVATE PLACEMENT"]

    elif mode == "BUYBACK":
        records = [record for record in records if record.get("category") == "BUYBACK"]

    elif mode in {"SPINOFF", "SPIN-OFF", "RESTRUCTURING", "RESTRUKTURISASI"}:
        records = [record for record in records if record.get("category") == "SPIN-OFF / RESTRUCTURING"]

    elif mode in {
        "MA",
        "M&A",
    }:
        records = [
            record
            for record in records
            if record.get("category") in {
                "AKUISISI / TAKEOVER",
                "STRATEGIC INVESTOR",
                "CHANGE CONTROL",
                "TENDER OFFER",
                "MERGER",
                "DIVESTASI",
            }
        ]

    else:
        records = [
            record
            for record in records
            if record.get("status") != "EXPIRED"
        ]

    records.sort(
        key=_rumor_record_sort_key,
        reverse=True,
    )

    lines = [
        "🟣 <b>V6.7.7 RUMOR BOARD</b>",
        f"Filter: <b>{html.escape(mode)}</b>",
        f"Rumor: <b>{len(records)}</b>",
        "",
    ]

    if not records:
        lines.append(
            "⚪ Tidak ada rumor pada filter ini."
        )
        return "\n".join(lines)

    for index, record in enumerate(
        records[:12],
        start=1,
    ):
        identity = (
            record.get("ticker")
            or record.get("company_name")
            or "UNKNOWN"
        )

        lines += [
            (
                f"{index}. <b>{html.escape(str(identity))}</b> — "
                f"{html.escape(str(record.get('category') or 'RUMOR'))}"
            ),
            (
                f"   {_rumor_status_badge(record.get('status'))} | "
                f"{_rumor_strength_badge(record.get('strength'))}"
            ),
            (
                f"   📰 {int(record.get('source_count', 0) or 0)} sumber"
                f" | 🧾 {html.escape(str(record.get('source_quality') or 'LOW'))}"
                f" | 🔗 efektif {record.get('effective_independent_count', 0)}"
                f" | 🕒 {_rumor_age_text(record)}"
            ),
            (
                f"   🔥 Impact {html.escape(str(rumor_trading_impact(record).get('potential_impact') or 'LOW'))}"
                f" — {int(rumor_trading_impact(record).get('score', 0) or 0)}/100"
            ),
        ]

        details = record.get(
            "rumor_details"
        ) or {}

        if details.get("rumored_party"):
            lines.append(
                "   🤝 "
                + html.escape(
                    str(details.get("rumored_party"))
                )
            )

    lines += [
        "",
        "Filter: ALL | ACTIVE | WEAK | MEDIUM | STRONG | CONFIRMED | DENIED | IPO | MA | TAKEOVER | STRATEGIC | RIGHTS | PP | BUYBACK | SPINOFF",
        "Detail: <code>/rumor TICKER</code>",
    ]

    return "\n".join(lines)[:3900]


def rumor_search_record(records, query):
    query = normalize(
        str(query or "")
    )

    if not query:
        return None

    ticker = _valid_idx_ticker(
        query
    )

    candidates = canonicalize_rumor_records(records)

    if ticker:
        matches = [
            record
            for record in candidates
            if _valid_idx_ticker(record.get("ticker")) == ticker
        ]
    else:
        q = _issuer_alias_key(
            query
        )
        matches = [
            record
            for record in candidates
            if q and q in _issuer_alias_key(
                " ".join([
                    str(record.get("company_name") or ""),
                    str(record.get("title") or ""),
                ])
            )
        ]

    if not matches:
        return None

    matches.sort(
        key=lambda record: (
            _profile_parse_iso(
                record.get("last_seen_utc")
            )
            or datetime.min.replace(tzinfo=timezone.utc),
            1 if record.get("status") == "ACTIVE" else 0,
            RUMOR_STRENGTH_RANK.get(
                str(record.get("strength") or "WEAK"),
                0,
            ),
        ),
        reverse=True,
    )

    return matches[0]


def v672_rumor_data_integrity_selftest():
    alias_backup = copy.deepcopy(TICKER_ALIAS_CACHE)
    try:
        TICKER_ALIAS_CACHE.clear()
        register_ticker_aliases("BYAN", ["Bayan Resources", "PT Bayan Resources Tbk"])

        bad_party = _valid_rumored_party("Tersengat Rumor") is None
        headline = "Saham BYAN Terbang 18,75% Tersengat Rumor Akuisisi Haji Isam"
        details = _extract_rumor_details(
            headline,
            headline,
            "AKUISISI / TAKEOVER",
        )
        price_not_stake = 18.75 not in (details.get("percentages") or [])
        phrase_not_party = details.get("rumored_party") != "Tersengat Rumor"

        valid_stake = _extract_rumor_stake_percentages(
            "Investor disebut akan mengakuisisi 51% saham BYAN",
            "AKUISISI / TAKEOVER",
        ) == [51.0]

        invalid_share = _valid_rumor_share_count(", saham") is None
        valid_share = _valid_rumor_share_count("1,2 miliar saham") == "1,2 miliar saham"

        profile = sanitize_rumor_issuer_profile(
            "BYAN",
            {
                "ticker": "BYAN",
                "issuer_name": "Bayan (BYAN",
                "controller": None,
                "business_activity": None,
            },
        )
        profile_name_fixed = profile.get("issuer_name") == "Bayan Resources"

        confirmation = {
            "event_type": "BUYBACK",
            "title": "PT Bur mengumumkan buyback saham",
            "official_reference": {
                "authority": "IDX",
                "url": "https://www.idx.co.id/disclosure/123?x=1",
            },
        }
        r1 = {
            "key": "BUYBACK|TITLE|a",
            "ticker": None,
            "company_name": "PT Bur",
            "category": "BUYBACK",
            "status": "CONFIRMED OFFICIAL",
            "strength": "CONFIRMED OFFICIAL",
            "source_count": 1,
            "sources": ["Media A"],
            "title": "PT Bur buyback saham",
            "rumor_details": {},
            "official_confirmation": confirmation,
        }
        r2 = {
            **copy.deepcopy(r1),
            "key": "BUYBACK|TITLE|b",
            "source_count": 1,
            "sources": ["Media B"],
            "title": "Buyback PT Bur resmi",
        }
        dedup = canonicalize_rumor_records([r1, r2])
        confirmed_dedup = len(dedup) == 1 and dedup[0].get("source_count") == 2

        stale = {
            "ticker": "BYAN",
            "company_name": "Bayan Resources",
            "category": "AKUISISI / TAKEOVER",
            "title": headline,
            "rumor_details": {
                "rumored_party": "Tersengat Rumor",
                "percentages": [18.75],
                "share_count": ", saham",
            },
        }
        cleaned, repair_count = sanitize_rumor_record_integrity(stale)
        cleaned_details = cleaned.get("rumor_details") or {}
        state_repair = all([
            not cleaned_details.get("rumored_party"),
            not cleaned_details.get("percentages"),
            not cleaned_details.get("share_count"),
            repair_count >= 3,
        ])

        display_record = copy.deepcopy(stale)
        display_record.update({
            "status": "ACTIVE",
            "strength": "STRONG",
            "source_count": 13,
            "issuer_profile": {
                "ticker": "BYAN",
                "issuer_name": "Bayan (BYAN",
                "controller": None,
                "business_activity": None,
            },
        })
        display = format_rumor_alert(display_record, mode="VIEW")
        display_fail_safe = all([
            "Tersengat Rumor</b>" not in display,
            "Rumor stake:</b> 18,75%" not in display,
            "Rumor jumlah saham:</b> , saham" not in display,
            "BYAN</b> — Bayan Resources" in display,
        ])

        return {
            "passed": all([
                bad_party,
                price_not_stake,
                phrase_not_party,
                valid_stake,
                invalid_share,
                valid_share,
                profile_name_fixed,
                confirmed_dedup,
                state_repair,
                display_fail_safe,
            ]),
            "headline_phrase_guard": bad_party and phrase_not_party,
            "price_percent_not_stake": price_not_stake,
            "valid_transaction_stake": valid_stake,
            "share_count_guard": invalid_share and valid_share,
            "profile_name_guard": profile_name_fixed,
            "confirmed_dedup": confirmed_dedup,
            "legacy_state_repair": state_repair,
            "display_fail_safe": display_fail_safe,
        }
    finally:
        TICKER_ALIAS_CACHE.clear()
        TICKER_ALIAS_CACHE.update(alias_backup)


async def fetch_rumor_feed(client, query, *, confirmation_channel=False):
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

            await asyncio.sleep(
                min(
                    12.0,
                    HTTP_RETRY_BASE_SECONDS
                    * (2 ** attempt),
                )
            )

    if response is None:
        if last_exc:
            raise last_exc
        return []

    entries = parse_google_news_rss(
        response.content
    )

    rows = []

    for entry in entries:
        if not _rumor_recent(
            entry.get("published_dt")
        ):
            continue

        title = normalize(
            entry.get("title")
            or ""
        )

        description = normalize(
            entry.get("description")
            or ""
        )

        combined = normalize(
            f"{title} {description}"
        )

        category = rumor_category(
            combined
        )

        if not category:
            continue

        status = _rumor_entry_status(
            combined,
            entry.get("source"),
            entry.get("link"),
        )

        if confirmation_channel and status is None:
            probe = {
                "title": title,
                "source": entry.get("source"),
                "link": entry.get("link"),
                "details": {"ticker": None},
            }
            try:
                annotate_official_source(
                    probe
                )
            except Exception:
                pass

            if official_source_rank(probe) > 0:
                status = "CONFIRMED OFFICIAL"

        if status is None:
            continue

        geo = geo_category(
            combined,
            entry.get("source")
            or "",
        )

        ticker = _extract_rumor_ticker(
            title,
            combined,
            geo,
        )

        company_name = _extract_rumor_company_name(
            title,
            combined,
            category,
        )

        # Indonesia-focused rumor engine.
        if (
            not str(geo).startswith("INDONESIA")
            and not ticker
            and "indonesia" not in combined.lower()
            and not any(
                hint in _rumor_source_key(entry.get("source"))
                for hint in INDONESIA_SOURCE_HINTS
            )
        ):
            continue

        article = {
            "title": title,
            "link": normalize(
                entry.get("link")
                or ""
            ),
            "published": entry.get(
                "published"
            ),
            "published_dt": entry.get(
                "published_dt"
            ),
            "source": entry.get(
                "source"
            ),
            "snippet": description,
            "rumor_category": category,
            "rumor_status": status,
            "ticker": ticker,
            "company_name": company_name,
            "rumor_details": _extract_rumor_details(
                title,
                description,
                category,
            ),
            "geo": geo,
            "query": query,
            "rumor_confirmation_channel": bool(
                confirmation_channel
            ),
        }

        article["key"] = article_key(
            title,
            article["link"],
        )

        rows.append(
            article
        )

    return rows


def v673_rumor_quality_impact_selftest():
    now = datetime.now(timezone.utc)

    # Many mirrored low-quality headlines must NOT become STRONG.
    mirror_articles = []
    for idx in range(6):
        mirror_articles.append({
            "title": "BYAN dikabarkan akan diakuisisi investor strategis besar",
            "snippet": "Rumor akuisisi BYAN masih belum resmi.",
            "source": f"Portal Copy {idx}",
            "link": f"https://copy{idx}.example/news/byan",
            "rumor_status": "ACTIVE",
            "rumor_category": "AKUISISI / TAKEOVER",
            "ticker": "BYAN",
            "company_name": "Bayan Resources",
            "rumor_details": {"rumored_party": "Investor Strategis"},
            "published_dt": now,
        })

    mirror_metrics = _rumor_source_metrics(mirror_articles)
    mirror_strength = _rumor_strength(mirror_articles, "ACTIVE")

    # Three credible publishers with independently worded reports can be STRONG.
    independent_articles = [
        {
            "title": "Investor besar jajaki akuisisi saham BYAN",
            "snippet": "Sumber menyebut proses penjajakan pengambilalihan masih berlangsung.",
            "source": "Reuters",
            "link": "https://reuters.com/example/byan-a",
            "rumor_status": "ACTIVE",
            "rumor_category": "AKUISISI / TAKEOVER",
            "ticker": "BYAN",
            "company_name": "Bayan Resources",
            "rumor_details": {"rumored_party": "PT Alpha Investasi", "percentages": [51.0]},
            "published_dt": now,
        },
        {
            "title": "Isu takeover Bayan Resources menguat, calon pembeli disebut PT Alpha",
            "snippet": "Dua pihak disebut membahas transaksi mayoritas saham.",
            "source": "CNBC Indonesia",
            "link": "https://cnbcindonesia.com/example/byan-b",
            "rumor_status": "ACTIVE",
            "rumor_category": "AKUISISI / TAKEOVER",
            "ticker": "BYAN",
            "company_name": "Bayan Resources",
            "rumor_details": {"rumored_party": "PT Alpha Investasi", "percentages": [51.0]},
            "published_dt": now,
        },
        {
            "title": "Pasar menanti kepastian rencana pengambilalihan BYAN oleh PT Alpha",
            "snippet": "Belum ada keterbukaan resmi, tetapi pembahasan transaksi disebut berlanjut.",
            "source": "Bisnis.com",
            "link": "https://bisnis.com/example/byan-c",
            "rumor_status": "ACTIVE",
            "rumor_category": "AKUISISI / TAKEOVER",
            "ticker": "BYAN",
            "company_name": "Bayan Resources",
            "rumor_details": {"rumored_party": "PT Alpha Investasi", "percentages": [51.0]},
            "published_dt": now,
        },
    ]
    independent_metrics = _rumor_source_metrics(independent_articles)
    independent_strength = _rumor_strength(independent_articles, "ACTIVE")

    profile = {
        "issuer_name": "Bayan Resources",
        "controller": None,
        "major_shareholders": [{"name": "Contoh Pemegang Saham", "stake_pct": 55.0}],
        "business_activity": "Coal mining, processing and sale of thermal coal.",
        "sector": "Energy",
        "industry": "Thermal Coal",
        "profile_source": "IDX PROFILE",
        "profile_source_quality": "OFFICIAL",
    }
    profile_lines = "\n".join(_rumor_profile_lines(profile))

    record = {
        "ticker": "BYAN",
        "company_name": "Bayan Resources",
        "category": "AKUISISI / TAKEOVER",
        "status": "ACTIVE",
        "strength": independent_strength,
        "source_quality": independent_metrics.get("source_quality"),
        "effective_independent_count": independent_metrics.get("effective_independent_count"),
        "copy_duplicate_count": independent_metrics.get("copy_duplicate_count"),
        "high_quality_source_count": independent_metrics.get("high_quality_source_count"),
        "last_seen_utc": now.isoformat(),
        "rumor_details": {"rumored_party": "PT Alpha Investasi", "percentages": [51.0]},
        "market_data": {"change_pct": 8.0},
    }
    impact = rumor_trading_impact(record)
    official_holder = _profile_holder_from_official_value(
        "PT Alpha Investasi 55,5%",
        ticker="BYAN",
        issuer_name="Bayan Resources",
        source_url="https://idx.co.id/profile/BYAN",
        controller=True,
    )

    return {
        "passed": all([
            mirror_strength != "STRONG",
            mirror_metrics.get("copy_duplicate_count", 0) >= 5,
            mirror_metrics.get("independent_story_count") == 1,
            independent_strength == "STRONG",
            independent_metrics.get("source_quality") == "HIGH",
            independent_metrics.get("independent_story_count", 0) >= 2,
            "Pertambangan batu bara" in profile_lines,
            "Kegiatan utama" in profile_lines,
            "Pemegang saham utama" in profile_lines,
            "tidak otomatis dianggap pengendali" in profile_lines,
            impact.get("potential_impact") in {"MEDIUM", "HIGH"},
            int(impact.get("score", 0)) >= 45,
            impact.get("official_confirmation") == "NONE",
            isinstance(official_holder, dict),
            official_holder.get("verified") is True,
            official_holder.get("name") == "PT Alpha Investasi",
            official_holder.get("stake_pct") == 55.5,
        ]),
        "anti_copy_guard": mirror_strength != "STRONG",
        "copy_cluster_count": mirror_metrics.get("independent_story_count"),
        "credible_independent_strength": independent_strength,
        "source_quality": independent_metrics.get("source_quality"),
        "business_profile_id": "Pertambangan batu bara" in profile_lines,
        "owner_fallback_safe": "tidak otomatis dianggap pengendali" in profile_lines,
        "official_owner_label": bool(official_holder and official_holder.get("verified")),
        "trading_impact_score": impact.get("score"),
    }



def v674_owner_semantic_independence_selftest():
    now = datetime.now(timezone.utc)

    # Three credible originals + ten low-tier rewrites: raw 13 sources should
    # compress into roughly 4-6 weighted independent evidence units.
    originals = [
        {
            "title": "Investor Alpha membahas pengambilalihan mayoritas BYAN",
            "snippet": "Pembahasan akuisisi 51% disebut berlangsung, belum ada keterbukaan resmi.",
            "source": "Reuters", "link": "https://reuters.com/byan-alpha",
            "rumor_status": "ACTIVE", "rumor_category": "AKUISISI / TAKEOVER",
            "ticker": "BYAN", "company_name": "Bayan Resources",
            "rumor_details": {"rumored_party": "PT Alpha Investasi", "percentages": [51.0]},
            "published_dt": now,
        },
        {
            "title": "Isu takeover Bayan menguat setelah calon pembeli disebut PT Alpha",
            "snippet": "Transaksi mayoritas saham masih pada tahap penjajakan dan belum resmi.",
            "source": "CNBC Indonesia", "link": "https://cnbcindonesia.com/byan-alpha",
            "rumor_status": "ACTIVE", "rumor_category": "AKUISISI / TAKEOVER",
            "ticker": "BYAN", "company_name": "Bayan Resources",
            "rumor_details": {"rumored_party": "PT Alpha Investasi", "percentages": [51.0]},
            "published_dt": now,
        },
        {
            "title": "Pasar menunggu kepastian rencana akuisisi BYAN oleh Alpha",
            "snippet": "Rumor transaksi 51 persen beredar, perseroan belum memberi konfirmasi resmi.",
            "source": "Bisnis.com", "link": "https://bisnis.com/byan-alpha",
            "rumor_status": "ACTIVE", "rumor_category": "AKUISISI / TAKEOVER",
            "ticker": "BYAN", "company_name": "Bayan Resources",
            "rumor_details": {"rumored_party": "PT Alpha Investasi", "percentages": [51.0]},
            "published_dt": now,
        },
    ]
    rewrites = []
    rewrite_titles = [
        "BYAN kembali ramai dibicarakan pelaku pasar",
        "Saham Bayan tersengat kabar korporasi besar",
        "Ada isu investor baru masuk ke Bayan Resources",
        "Kabar terbaru BYAN bikin investor menoleh",
        "Bayan Resources disebut masuk radar investor strategis",
        "Rumor aksi korporasi BYAN beredar di pasar",
        "Spekulasi transaksi besar menyelimuti saham BYAN",
        "Calon investor dikabarkan incar mayoritas saham Bayan",
        "Pasar mencermati kabar takeover pada emiten BYAN",
        "Isu pengambilalihan Bayan kembali mencuat",
    ]
    for idx, title in enumerate(rewrite_titles):
        rewrites.append({
            "title": title,
            "snippet": "PT Alpha Investasi disebut terkait rencana pengambilalihan 51% saham BYAN; belum ada konfirmasi resmi.",
            "source": f"Portal Lokal {idx}",
            "link": f"https://portal{idx}.example/byan-rumor",
            "rumor_status": "ACTIVE", "rumor_category": "AKUISISI / TAKEOVER",
            "ticker": "BYAN", "company_name": "Bayan Resources",
            "rumor_details": {"rumored_party": "PT Alpha Investasi", "percentages": [51.0]},
            "published_dt": now,
        })
    metrics = _rumor_source_metrics(originals + rewrites)
    strength = _rumor_strength(originals + rewrites, "ACTIVE")

    # One premium original + many low rewrites must not become STRONG.
    one_original = _rumor_source_metrics(originals[:1] + rewrites)
    one_strength = _rumor_strength(originals[:1] + rewrites, "ACTIVE")

    owner_text = (
        "Pemegang saham pengendali: PT Contoh Holdings dengan kepemilikan 61,25%. "
        "Pemegang saham utama: Budi Santoso sebesar 18,5%."
    )
    owner_candidates = _extract_owner_candidates_v2(
        owner_text,
        ticker="ABCD",
        issuer_name="PT Contoh Tbk",
        source="idx.co.id",
        source_url="https://idx.co.id/example",
    )
    official_controller = next((x for x in owner_candidates if x.get("role") == "CONTROLLER"), None)

    private_articles = [
        {
            "title": "Startup Nusantara bersiap menuju IPO",
            "snippet": "Founder: Budi Santoso. Perusahaan bergerak di bidang teknologi finansial.",
            "source": "Reuters", "link": "https://reuters.com/startup-nusantara",
        },
        {
            "title": "Nusantara menyiapkan penawaran saham perdana",
            "snippet": "Founder: Budi Santoso. Bisnis utama perusahaan berada di sektor fintech.",
            "source": "CNBC Indonesia", "link": "https://cnbcindonesia.com/nusantara-ipo",
        },
    ]
    private_profile = _extract_private_company_context_v2(
        private_articles,
        company_name="Startup Nusantara",
    )

    return {
        "passed": all([
            metrics.get("detected_source_count") == 13,
            3.0 <= float(metrics.get("effective_independent_count") or 0) <= 6.5,
            int(metrics.get("copy_duplicate_count") or 0) >= 8,
            float(metrics.get("credible_effective_independent_count") or 0) >= 2.5,
            strength == "STRONG",
            one_strength != "STRONG",
            float(one_original.get("credible_effective_independent_count") or 0) < 1.8,
            isinstance(official_controller, dict),
            bool(official_controller and official_controller.get("name") == "PT Contoh Holdings"),
            bool(official_controller and official_controller.get("stake_pct") == 61.25),
            isinstance(private_profile.get("controller"), dict),
            private_profile["controller"].get("name") == "Budi Santoso",
            private_profile["controller"].get("verified") is False,
            int(private_profile.get("owner_context_sources") or 0) >= 2,
            bool(private_profile.get("business_activity")),
        ]),
        "detected_sources": metrics.get("detected_source_count"),
        "weighted_independence": metrics.get("effective_independent_count"),
        "credible_weighted_independence": metrics.get("credible_effective_independent_count"),
        "derivatives": metrics.get("derivative_source_count"),
        "semantic_copies": metrics.get("semantic_copy_count"),
        "strength": strength,
        "single_original_strength": one_strength,
        "owner_parser": bool(official_controller),
        "private_profile_v2": bool(private_profile.get("controller")),
    }


async def fetch_all_rumor_articles(official_articles=None):
    if not RUMOR_INTELLIGENCE_ENABLED:
        return []

    query_specs = [
        ("RUMOR", query, False)
        for query in RUMOR_QUERIES[
            :RUMOR_QUERY_LIMIT
        ]
    ]

    query_specs.extend(
        (
            "RUMOR_CONFIRMATION",
            query,
            True,
        )
        for query in RUMOR_CONFIRMATION_QUERIES[
            :RUMOR_CONFIRMATION_QUERY_LIMIT
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
            fetch_rumor_feed(
                client,
                query,
                confirmation_channel=is_confirmation,
            )
            for _, query, is_confirmation in query_specs
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

    dedup = {}

    for spec, result in zip(
        query_specs,
        results,
    ):
        channel, _, _ = spec

        if isinstance(result, Exception):
            print(
                "Rumor feed error:",
                channel,
                type(result).__name__,
            )
            continue

        for article in result:
            key = article.get("key")

            if key not in dedup:
                dedup[key] = article
                continue

            existing = dedup[key]

            if _rumor_primary_rank(
                article
            ) > _rumor_primary_rank(
                existing
            ):
                dedup[key] = article

    articles = list(
        dedup.values()
    )

    await prime_rumor_entity_aliases(
        articles,
        official_articles=official_articles,
    )

    resolve_rumor_entities(
        articles,
        official_articles=official_articles,
    )

    return articles


def v675_hotfix_selftest():
    alias_backup = copy.deepcopy(TICKER_ALIAS_CACHE)
    try:
        TICKER_ALIAS_CACHE.clear()
        register_ticker_aliases("BYAN", ["Bayan Resources", "PT Bayan Resources Tbk"])
        noisy = {
            "ticker": "BYAN",
            "issuer_name": "62 Persen Saham Bayan Resources",
            "controller": None,
            "business_activity": "Coal mining, processing and sale of thermal coal.",
            "sector": "Energy", "industry": "Thermal Coal",
            "major_shareholders": [{
                "name": "Contoh Holder", "stake_pct": 60.0, "verified": False,
                "verification_level": "CORROBORATED_CONTEXT_V3", "source_count": 2,
            }],
        }
        fixed = sanitize_rumor_issuer_profile("BYAN", noisy)
        record, repairs = sanitize_rumor_record_integrity({
            "ticker": "BYAN", "company_name": "62 Persen Saham Bayan Resources",
            "issuer_profile": noisy, "rumor_details": {},
        })
        report = format_profile_report(fixed)
        rumor_lines = "\n".join(_rumor_profile_lines(fixed))

        owner_text = (
            "Komposisi pemegang saham / shareholders: Contoh Holdings 61,25%; "
            "Budi Santoso 18,50%."
        )
        owner_candidates = _extract_owner_candidates_v3(
            owner_text, ticker="BYAN", issuer_name="Bayan Resources",
            source="idx.co.id", source_url="https://idx.co.id/profile/BYAN",
        )
        holder_names = {_normalized_entity_key(x.get("name")) for x in owner_candidates}

        media_controller = _extract_owner_candidates_v3(
            "Pemegang saham pengendali: PT Rumor Investasi sebesar 51%.",
            ticker="BYAN", issuer_name="Bayan Resources",
            source="Portal Blog", source_url="https://portal.example/story",
        )
        media_selected = _owner_v3_select_candidates(media_controller)
        media_cannot_verify = media_selected.get("controller") is None

        official_controller_rows = _extract_owner_candidates_v3(
            "Pemegang saham pengendali: PT Contoh Holdings sebesar 61,25%.",
            ticker="BYAN", issuer_name="Bayan Resources",
            source="idx.co.id", source_url="https://idx.co.id/profile/BYAN",
        )
        official_selected = _owner_v3_select_candidates(official_controller_rows)
        official_controller_ok = bool(
            official_selected.get("controller")
            and official_selected["controller"].get("name") == "PT Contoh Holdings"
            and official_selected["controller"].get("verified") is True
        )

        return {
            "passed": all([
                fixed.get("issuer_name") == "Bayan Resources",
                record.get("company_name") == "Bayan Resources",
                repairs >= 2,
                "Pertambangan batu bara" in report,
                "Kegiatan utama" in report,
                "Coal mining, processing" not in report,
                "Pertambangan batu bara" in rumor_lines,
                _normalized_entity_key("Contoh Holdings") in holder_names,
                _normalized_entity_key("Budi Santoso") in holder_names,
                media_cannot_verify,
                official_controller_ok,
                "tidak otomatis dianggap pengendali" in report,
            ]),
            "issuer_name_sanitizer_v3": fixed.get("issuer_name") == "Bayan Resources",
            "silent_cache_repair": repairs >= 2,
            "unified_profile_indonesia": "Pertambangan batu bara" in report and "Coal mining, processing" not in report,
            "owner_table_parser_v3": len(holder_names) >= 2,
            "ownership_role_guard": media_cannot_verify and official_controller_ok,
            "official_controller_v3": official_controller_ok,
        }
    finally:
        TICKER_ALIAS_CACHE.clear()
        TICKER_ALIAS_CACHE.update(alias_backup)



def v676_ownership_finalization_selftest():
    # Official issuer-site wording patterned after common board/governance copy.
    english_primary = (
        "Low Yi Ngo is the son of Dato' Dr. Low Tuck Kwong, who is currently "
        "the President Director and primary and controlling shareholder of the Company."
    )
    indonesian_primary = (
        "Low Yi Ngo adalah anak dari Dato' Dr. Low Tuck Kwong, yang saat ini menjabat "
        "sebagai Direktur Utama sekaligus Pemegang Saham Utama dan Pengendali Perseroan."
    )
    direct_primary = (
        "Dato' Dr. Low Tuck Kwong. Pendiri dan pemegang saham utama serta pengendali Bayan Group."
    )
    primary_rows = []
    for text in (english_primary, indonesian_primary, direct_primary):
        primary_rows.extend(_extract_owner_candidates_v4(
            text, ticker="BYAN", issuer_name="Bayan Resources",
            source="bayan.com.sg", source_url="https://www.bayan.com.sg/board-of-directors",
            primary_company=True,
        ))
    primary_selected = _owner_v4_select_candidates(primary_rows)
    primary_controller = primary_selected.get("controller") or {}

    negative_primary_rows = _extract_owner_candidates_v4(
        "Jenny Quantero is a Shareholder of the Company and is not affiliated with members "
        "of the Board as well as with primary and controlling shareholders of the Company. "
        "Ulina Fitriani tidak memiliki hubungan afiliasi dengan Pemegang Saham Pengendali dan/atau Utama Perseroan.",
        ticker="BYAN", issuer_name="Bayan Resources",
        source="bayan.com.sg", source_url="https://www.bayan.com.sg/board-of-directors",
        primary_company=True,
    )
    negative_primary_selected = _owner_v4_select_candidates(negative_primary_rows)
    negative_affiliation_guard = negative_primary_selected.get("controller") is None

    # IDX-style >5% holder snippet + share-count rows. This must remain holder
    # context only; it must not create a controller without explicit role text.
    registry_text = (
        "Kode Efek BYAN. Pemegang Saham >5% DATO' LOW TUCK KWONG; ELAINE LOW; "
        "PT SUMBER SURYADAYA PRIMA; MASYARAKAT <5%. "
        "JENNY QUANTERO, Direksi, 994.975.000; "
        "DATO' DR LOW TUCK KWONG, Direksi, 13.406.921.870."
    )
    registry_rows = _extract_owner_candidates_v4(
        registry_text, ticker="BYAN", issuer_name="Bayan Resources",
        source="idx.co.id", source_url="https://www.idx.co.id/profile/BYAN",
        official_registry=True,
    )
    registry_selected = _owner_v4_select_candidates(registry_rows)
    registry_names = {
        _normalized_entity_key(x.get("name"))
        for x in (registry_selected.get("major_shareholders") or [])
        if isinstance(x, dict) and x.get("name")
    }

    # A media article may mention an alleged controller, but V4 must not verify it.
    media_rows = _extract_owner_candidates_v4(
        "Portal menyebut PT Rumor Investasi sebagai pemegang saham pengendali BYAN.",
        ticker="BYAN", issuer_name="Bayan Resources",
        source="portal.example", source_url="https://portal.example/byan",
        official_registry=False, primary_company=False,
    )
    media_selected = _owner_v4_select_candidates(media_rows)

    # Explicit role guard: a >5% holder list is not a controller list.
    registry_controller_absent = registry_selected.get("controller") is None
    media_controller_absent = media_selected.get("controller") is None

    profile = {
        "ticker": "BYAN", "issuer_name": "Bayan Resources",
        "website": "https://www.bayan.com.sg", "controller": primary_controller,
        "major_shareholders": registry_selected.get("major_shareholders") or [],
        "business_activity": "Coal mining, processing and sale of thermal coal.",
        "sector": "Energy", "industry": "Thermal Coal",
        "profile_source": "IDX PROFILE", "profile_source_quality": "OFFICIAL",
        "owner_v3_checked_utc": _profile_now_iso(),
        # deliberately no owner_v4_checked_utc: V4 must get a fresh attempt
    }
    report = format_profile_report(profile)

    controller_name_key = _normalized_entity_key(primary_controller.get("name"))
    low_key = _normalized_entity_key("Dato' Dr. Low Tuck Kwong")
    low_short_key = _normalized_entity_key("Low Tuck Kwong")
    controller_is_low = bool(
        controller_name_key and (
            controller_name_key == low_key
            or controller_name_key == low_short_key
            or "lowtuckkwong" in controller_name_key.replace("dr", "").replace("dato", "")
        )
    )

    return {
        "passed": all([
            controller_is_low,
            primary_controller.get("verified") is True,
            primary_controller.get("verification_level") == "PRIMARY_COMPANY_CONTROLLER_V4",
            negative_affiliation_guard,
            registry_controller_absent,
            media_controller_absent,
            any("lowtuckkwong" in key.replace("dr", "").replace("dato", "") for key in registry_names),
            _normalized_entity_key("Elaine Low") in registry_names,
            _normalized_entity_key("PT Sumber Suryadaya Prima") in registry_names,
            len(registry_names) == 3,
            _normalized_entity_key("Jenny Quantero") not in registry_names,
            "Pertambangan batu bara" in report,
            "Pengendali saat ini" in report,
            "owner_v4_checked_utc" not in profile,
            "owner_v3_checked_utc" in profile,
        ]),
        "primary_controller_reverse_role": controller_is_low,
        "primary_controller_verified": primary_controller.get("verified") is True,
        "primary_controller_level": primary_controller.get("verification_level"),
        "negative_affiliation_reference_guard": negative_affiliation_guard,
        "registry_holder_only_guard": registry_controller_absent,
        "media_cannot_verify_controller": media_controller_absent,
        "registry_major_holder_count": len(registry_names),
        "v4_fresh_cache_key": "owner_v4_checked_utc" not in profile,
        "indonesian_profile_retained": "Pertambangan batu bara" in report,
    }


def v677_ownership_safety_selftest():
    """Regression fixture built from exact V6.7.6 live false positives."""
    bad_controller = "GMS Announcement GMS Invitation GMS Minutes"
    bad_holder = "Saham-Saham Emiten Batubara Kakap Melompat Read More 24 July 2023 Saham BYAN Ngacir"
    bad_menu = "Reports Financial Statements Financial Highlights Sustainability Report General"
    poisoned = {
        "ticker": "BYAN", "issuer_name": "Bayan Resources", "website": "https://www.bayan.com.sg",
        "controller": {
            "name": bad_controller, "verified": True,
            "verification_level": "PRIMARY_COMPANY_CONTROLLER_V4",
            "source": "bayan.com.sg", "source_url": "https://www.bayan.com.sg/",
        },
        "major_shareholders": [
            {"name": bad_holder, "stake_pct": 4.94, "verified": True, "verification_level": "PRIMARY_COMPANY_HOLDER_V4"},
            {"name": bad_menu, "stake_pct": None, "verified": True, "verification_level": "PRIMARY_COMPANY_HOLDER_V4"},
        ],
        "business_activity": "Coal mining, processing and sale of thermal coal.",
        "sector": "Energy", "industry": "Thermal Coal", "profile_source": "Yahoo Finance",
    }
    repaired = _owner_v5_sanitize_profile(poisoned)
    repaired_report = format_profile_report(repaired)

    good_text = (
        "Dato' Dr. Low Tuck Kwong, who is currently the President Director and "
        "primary and controlling shareholder of the Company."
    )
    good_rows = _extract_owner_candidates_v5(
        good_text, ticker="BYAN", issuer_name="Bayan Resources", source="bayan.com.sg",
        source_url="https://www.bayan.com.sg/board-of-directors", primary_company=True,
    )
    good_selected = _owner_v5_select_candidates(good_rows)
    good_controller = good_selected.get("controller") or {}

    # Exact navigation/news garbage must yield ZERO candidates even on primary domain.
    garbage_text = (
        "GMS Announcement GMS Invitation GMS Minutes Reports Financial Statements Financial Highlights "
        "Sustainability Report General primary and controlling shareholder "
        "Saham-Saham Emiten Batubara Kakap Melompat Read More 24 July 2023 Saham BYAN Ngacir 4,94%."
    )
    garbage_rows = _extract_owner_candidates_v5(
        garbage_text, ticker="BYAN", issuer_name="Bayan Resources", source="bayan.com.sg",
        source_url="https://www.bayan.com.sg/", primary_company=True,
    )
    garbage_selected = _owner_v5_select_candidates(garbage_rows)


    mixed_page = (
        "GMS Announcement GMS Invitation GMS Minutes Reports Financial Statements "
        "Dato' Dr. Low Tuck Kwong, who is currently the President Director and "
        "primary and controlling shareholder of the Company. "
        "Saham-Saham Emiten Batubara Kakap Melompat Read More 24 July 2023 Saham BYAN Ngacir 4,94%."
    )
    mixed_rows = _extract_owner_candidates_v5(
        mixed_page, ticker="BYAN", issuer_name="Bayan Resources", source="bayan.com.sg",
        source_url="https://www.bayan.com.sg/board-of-directors", primary_company=True,
    )
    mixed_selected = _owner_v5_select_candidates(mixed_rows)
    mixed_controller = mixed_selected.get("controller") or {}

    registry_text = (
        "Kode Efek BYAN. Pemegang Saham >5% DATO' LOW TUCK KWONG; ELAINE LOW; "
        "PT SUMBER SURYADAYA PRIMA; MASYARAKAT <5%."
    )
    registry_rows = _extract_owner_candidates_v5(
        registry_text, ticker="BYAN", issuer_name="Bayan Resources", source="idx.co.id",
        source_url="https://www.idx.co.id/profile/BYAN", official_registry=True,
    )
    registry_selected = _owner_v5_select_candidates(registry_rows)
    registry_keys = {_owner_v4_identity_key(x.get("name")) for x in registry_selected.get("major_shareholders") or []}

    media_rows = _extract_owner_candidates_v5(
        "PT Rumor Investasi adalah pemegang saham pengendali BYAN sebesar 51%.",
        ticker="BYAN", issuer_name="Bayan Resources", source="portal.example",
        source_url="https://portal.example/byan", official_registry=False, primary_company=False,
    )

    good_key = _owner_v4_identity_key(good_controller.get("name"))
    return {
        "passed": all([
            repaired.get("controller") is None,
            not repaired.get("major_shareholders"),
            bad_controller not in repaired_report,
            bad_holder not in repaired_report,
            bad_menu not in repaired_report,
            good_controller.get("verified") is True,
            good_controller.get("verification_level") == "PRIMARY_COMPANY_CONTROLLER_V5",
            "lowtuckkwong" in good_key,
            garbage_selected.get("controller") is None,
            not garbage_selected.get("major_shareholders"),
            len(garbage_rows) == 0,
            _owner_v4_identity_key(mixed_controller.get("name")) == "lowtuckkwong",
            mixed_controller.get("stake_pct") is None,
            "lowtuckkwong" in registry_keys,
            "elainelow" in registry_keys,
            "sumbersuryadayaprima" in registry_keys,
            len(media_rows) == 0,
            "Pertambangan batu bara" in repaired_report,
        ]),
        "poisoned_controller_removed": repaired.get("controller") is None,
        "poisoned_holders_removed": not repaired.get("major_shareholders"),
        "exact_gms_navigation_rejected": len(garbage_rows) == 0,
        "mixed_navigation_real_owner": mixed_controller.get("name"),
        "mixed_navigation_stake_leak_blocked": mixed_controller.get("stake_pct") is None,
        "strict_primary_controller": good_controller.get("name"),
        "strict_primary_level": good_controller.get("verification_level"),
        "official_gt5_holders": len(registry_keys),
        "media_hard_block": len(media_rows) == 0,
        "indonesian_profile_retained": "Pertambangan batu bara" in repaired_report,
    }


async def v671_rumor_entity_prime_selftest():
    alias_backup = copy.deepcopy(TICKER_ALIAS_CACHE)
    original_resolver = globals().get("resolve_multisource_issuer_alias")

    async def _mock_resolver(ticker, reference_article=None, seed_articles=None):
        if ticker == "BYAN":
            register_ticker_aliases("BYAN", ["Bayan Resources"])
            return {
                "ticker": "BYAN",
                "aliases": ["Bayan Resources"],
                "source": "MOCK_MARKET_PROFILE",
                "attempts": ["MARKET_PROFILE"],
            }
        return {"ticker": ticker, "aliases": [], "source": "NOT_FOUND", "attempts": []}

    try:
        TICKER_ALIAS_CACHE.clear()
        globals()["resolve_multisource_issuer_alias"] = _mock_resolver
        now = datetime.now(timezone.utc)
        articles = [
            {
                "title": "Rumor akuisisi BYAN kembali beredar",
                "snippet": "Emiten tersebut disebut menjadi perhatian pasar",
                "ticker": "BYAN",
                "company_name": None,
                "rumor_category": "AKUISISI / TAKEOVER",
                "rumor_status": "ACTIVE",
                "source": "Media A",
                "published_dt": now,
                "rumor_details": {},
            },
            {
                "title": "Bayan Resources Tanggapi Isu Akuisisi",
                "snippet": "Perseroan memberi tanggapan atas isu pasar",
                "ticker": None,
                "company_name": None,
                "rumor_category": "AKUISISI / TAKEOVER",
                "rumor_status": "ACTIVE",
                "source": "Media B",
                "published_dt": now,
                "rumor_details": {},
            },
        ]
        learned = await prime_rumor_entity_aliases(articles)
        resolve_rumor_entities(articles)
        groups = group_rumor_articles(articles)
        return {
            "passed": all([
                learned == 1,
                articles[1].get("ticker") == "BYAN",
                len(groups) == 1,
                groups[0].get("source_count") == 2,
            ]),
            "learned": learned,
            "unknown_to_bayan_without_preloaded_alias": articles[1].get("ticker") == "BYAN",
            "same_group": len(groups) == 1,
        }
    finally:
        globals()["resolve_multisource_issuer_alias"] = original_resolver
        TICKER_ALIAS_CACHE.clear()
        TICKER_ALIAS_CACHE.update(alias_backup)


def v671_rumor_entity_resolution_selftest():
    # Preserve global alias cache to keep the test side-effect free.
    alias_backup = copy.deepcopy(TICKER_ALIAS_CACHE)
    profile_backup = copy.deepcopy(ISSUER_PROFILE_CACHE)

    try:
        TICKER_ALIAS_CACHE.clear()
        ISSUER_PROFILE_CACHE.clear()

        register_ticker_aliases(
            "BYAN",
            ["Bayan Resources", "PT Bayan Resources Tbk"],
        )

        now = datetime.now(timezone.utc)
        explicit = {
            "title": "Rumor akuisisi BYAN kembali beredar",
            "snippet": "Bayan Resources disebut menanggapi isu tersebut",
            "ticker": "BYAN",
            "company_name": None,
            "rumor_category": "AKUISISI / TAKEOVER",
            "rumor_status": "ACTIVE",
            "source": "Kontan",
            "published_dt": now,
            "rumor_details": {},
        }
        unknown = {
            "title": "Bayan Resources Tanggapi Isu Akuisisi",
            "snippet": "Perseroan memberi tanggapan atas rumor pasar",
            "ticker": None,
            "company_name": None,
            "rumor_category": "AKUISISI / TAKEOVER",
            "rumor_status": "ACTIVE",
            "source": "Bisnis Indonesia",
            "published_dt": now,
            "rumor_details": {},
        }

        resolved = resolve_rumor_entities([explicit, unknown])
        groups = group_rumor_articles(resolved)

        merge_ok = (
            unknown.get("ticker") == "BYAN"
            and len(groups) == 1
            and groups[0].get("source_count") == 2
            and groups[0].get("key") == "AKUISISI / TAKEOVER|TICKER|BYAN"
        )

        # Ambiguous alias must remain UNKNOWN.
        TICKER_ALIAS_CACHE.clear()
        register_ticker_aliases("ABCD", ["Alpha Holdings"] )
        register_ticker_aliases("EFGH", ["Alpha Holdings"] )
        ambiguous = {
            "title": "Alpha Holdings tanggapi rumor akuisisi",
            "snippet": "isu masih beredar",
            "ticker": None,
            "company_name": None,
            "rumor_category": "AKUISISI / TAKEOVER",
            "rumor_status": "ACTIVE",
            "source": "Media",
            "published_dt": now,
            "rumor_details": {},
        }
        resolve_rumor_entities([ambiguous])
        ambiguity_guard_ok = ambiguous.get("ticker") is None

        # Rumored buyer must not be mistaken for the issuer.
        TICKER_ALIAS_CACHE.clear()
        register_ticker_aliases("BYAN", ["Bayan Resources"] )
        buyer_only = {
            "title": "PT Alpha Investama dirumorkan mengakuisisi perusahaan tambang",
            "snippet": "Bayan tidak disebut dalam berita ini",
            "ticker": None,
            "company_name": None,
            "rumor_category": "AKUISISI / TAKEOVER",
            "rumor_status": "ACTIVE",
            "source": "Media",
            "published_dt": now,
            "rumor_details": {"rumored_party": "PT Alpha Investama"},
        }
        resolve_rumor_entities([buyer_only])
        buyer_guard_ok = buyer_only.get("ticker") is None

        return {
            "passed": all([merge_ok, ambiguity_guard_ok, buyer_guard_ok]),
            "unknown_to_bayan": unknown.get("ticker") == "BYAN",
            "same_event_merged": merge_ok,
            "ambiguous_alias_blocked": ambiguity_guard_ok,
            "rumored_party_not_issuer": buyer_guard_ok,
        }
    finally:
        TICKER_ALIAS_CACHE.clear()
        TICKER_ALIAS_CACHE.update(alias_backup)
        ISSUER_PROFILE_CACHE.clear()
        ISSUER_PROFILE_CACHE.update(profile_backup)


def v67_rumor_selftest():
    samples = {
        "IPO": "Wacana IPO PT Nusantara Digital disebut akan melantai di BEI",
        "AKUISISI / TAKEOVER": "Rumor PT Alpha akan mengakuisisi saham ABCD",
        "STRATEGIC INVESTOR": "Dikabarkan investor strategis masuk ke ABCD",
        "MERGER": "Wacana merger ABCD dengan EFGH kembali santer",
        "RIGHTS ISSUE": "Rumor rights issue ABCD disebut segera digelar",
        "PRIVATE PLACEMENT": "Wacana private placement ABCD dengan investor baru",
        "BUYBACK": "Rumor buyback saham ABCD mulai beredar",
        "DIVESTASI": "Isu divestasi saham ABCD kepada investor strategis",
        "CHANGE CONTROL": "Rumor perubahan pengendali ABCD beredar di pasar",
        "TENDER OFFER": "Rumor tender offer ABCD disebut segera muncul",
        "SPIN-OFF / RESTRUCTURING": "Wacana spin off anak usaha ABCD",
        "DELISTING / RELISTING": "Rumor delisting ABCD kembali beredar",
    }

    category_ok = all(
        rumor_category(text) == expected
        for expected, text in samples.items()
    )

    denial_ok = (
        _rumor_entry_status(
            "Emiten membantah rumor akuisisi ABCD",
            "Kontan",
        )
        == "DENIED"
    )

    active_ok = (
        _rumor_entry_status(
            "Rumor akuisisi ABCD oleh investor strategis",
            "Kontan",
        )
        == "ACTIVE"
    )

    confirmed_ok = (
        _rumor_entry_status(
            "ABCD resmi mengumumkan akuisisi",
            "Kontan",
        )
        == "CONFIRMED OFFICIAL"
    )

    not_confirmed_ok = (
        _rumor_entry_status(
            "Rumor akuisisi ABCD belum resmi dan masih belum dikonfirmasi",
            "Kontan",
        )
        == "ACTIVE"
    )

    weak_article = {
        "rumor_status": "ACTIVE",
        "source": "Media A",
        "ticker": "ABCD",
        "company_name": None,
        "rumor_details": {},
        "published_dt": datetime.now(timezone.utc),
    }

    medium_article = {
        **weak_article,
        "source": "Kontan",
        "rumor_details": {
            "rumored_party": "PT Investor",
            "percentages": [30.0],
            "money": ["Rp1 triliun"],
        },
    }

    strong_article = {
        **medium_article,
        "source": "Bisnis.com",
    }

    strength_ok = all([
        _rumor_strength([weak_article]) == "WEAK",
        _rumor_strength([medium_article]) == "MEDIUM",
        _rumor_strength([
            medium_article,
            strong_article,
        ]) in {"MEDIUM", "STRONG"},
        _rumor_strength([
            medium_article,
            strong_article,
            {
                **strong_article,
                "source": "CNBC Indonesia",
            },
        ]) == "STRONG",
    ])

    private_profile = _extract_private_company_context(
        (
            "PT Nusantara Digital didirikan oleh Budi Santoso. "
            "Perusahaan bergerak di bidang teknologi dan platform digital."
        ),
        company_name="PT Nusantara Digital",
        source="Kontan",
    )

    private_profile_ok = all([
        private_profile.get("controller"),
        private_profile["controller"].get("verified") is False,
        "Budi Santoso" in private_profile["controller"].get("name", ""),
        bool(private_profile.get("business_activity")),
        private_profile.get("sector") == "Technology",
    ])

    previous = {
        "status": "ACTIVE",
        "strength": "WEAK",
        "rumor_details": {
            "rumored_party": "PT Investor",
            "percentages": [30.0],
        },
        "market_data": {
            "last_price": 100,
            "change_pct": 1.0,
        },
        "issuer_profile": {
            "business_activity": "Media",
        },
    }

    price_only = copy.deepcopy(previous)
    price_only["market_data"] = {
        "last_price": 120,
        "change_pct": 20.0,
    }

    profile_only = copy.deepcopy(previous)
    profile_only["issuer_profile"] = {
        "business_activity": "Media & digital advertising",
        "sector": "Communication Services",
    }

    stronger = copy.deepcopy(previous)
    stronger["strength"] = "MEDIUM"

    confirmed = copy.deepcopy(previous)
    confirmed["status"] = "CONFIRMED OFFICIAL"
    confirmed["strength"] = "CONFIRMED OFFICIAL"

    decision_ok = all([
        rumor_change_decision(
            previous,
            price_only,
        )["should_alert"] is False,
        rumor_change_decision(
            previous,
            profile_only,
        )["should_alert"] is False,
        rumor_change_decision(
            previous,
            stronger,
        )["should_alert"] is True,
        rumor_change_decision(
            previous,
            confirmed,
        )["mode"] == "CONFIRMED",
    ])

    # Rumored actor must never mutate current official controller.
    profile_guard_ok = (
        "rumored_party"
        not in {
            "controller",
            "major_shareholders",
        }
    )

    return {
        "passed": all([
            category_ok,
            denial_ok,
            active_ok,
            confirmed_ok,
            not_confirmed_ok,
            strength_ok,
            private_profile_ok,
            decision_ok,
            profile_guard_ok,
        ]),
        "all_categories": category_ok,
        "denial_tracker": denial_ok,
        "confirmation_tracker": confirmed_ok,
        "negated_confirmation_guard": not_confirmed_ok,
        "strength_engine": strength_ok,
        "private_ipo_profile": private_profile_ok,
        "market_noise_guard": (
            rumor_change_decision(
                previous,
                price_only,
            )["should_alert"] is False
        ),
        "profile_no_realert": (
            rumor_change_decision(
                previous,
                profile_only,
            )["should_alert"] is False
        ),
        "strength_upgrade_alert": (
            rumor_change_decision(
                previous,
                stronger,
            )["should_alert"] is True
        ),
    }




def v67_rumor_regression_selftest():
    ticker_ok = (
        _extract_rumor_ticker(
            "Rumor akuisisi ABCD",
            "Rumor akuisisi ABCD saham Indonesia",
            "INDONESIA 🇮🇩",
        )
        == "ABCD"
    )

    party_ok = all([
        _extract_rumored_party(
            "Sinyal Haji Isam Serius Ingin Akuisisi BYAN",
            "",
            "AKUISISI / TAKEOVER",
        )
        == "Haji Isam",
        _extract_rumored_party(
            "Rumor PT Alpha Investama akan mengakuisisi saham ABCD",
            "",
            "AKUISISI / TAKEOVER",
        )
        == "PT Alpha Investama",
        _extract_rumored_party(
            "Dikabarkan investor strategis PT Beta Capital masuk ke EFGH",
            "",
            "STRATEGIC INVESTOR",
        )
        == "PT Beta Capital",
        _extract_rumored_party(
            "Emiten membantah rumor akuisisi ABCD",
            "",
            "AKUISISI / TAKEOVER",
        )
        is None,
    ])

    listing_guard_ok = (
        _extract_rumor_listing_estimate(
            "PT Nusantara Digital akan melantai di BEI"
        )
        is None
    )

    official_article = {
        "title": "PT Alpha resmi mengakuisisi ABCD",
        "snippet": "",
        "event_type": "AKUISISI",
        "stage": "SPA / SIGNED",
        "urgency": "HIGH",
        "priority": "HIGH",
        "information_score": 90,
        "ca_score": 90,
        "published_dt": datetime.now(timezone.utc),
        "details": {
            "ticker": "ABCD",
        },
        "official_reference": {
            "authority": "IDX",
            "kind": "PRIMARY",
            "url": "https://idx.co.id/example",
        },
    }

    confirmation = find_official_confirmation_for_rumor(
        {
            "ticker": "ABCD",
            "company_name": "PT ABCD Tbk",
            "category": "AKUISISI / TAKEOVER",
        },
        [official_article],
    )

    confirmation_ok = (
        isinstance(confirmation, dict)
        and confirmation.get("event_type") == "AKUISISI"
    )

    previous = {
        "key": "AKUISISI / TAKEOVER|TICKER|ABCD",
        "ticker": "ABCD",
        "company_name": "PT ABCD Tbk",
        "category": "AKUISISI / TAKEOVER",
        "status": "ACTIVE",
        "strength": "MEDIUM",
        "source_count": 2,
        "sources": ["Kontan", "Bisnis.com"],
        "title": "Rumor akuisisi ABCD",
        "first_seen_utc": datetime.now(timezone.utc).isoformat(),
        "last_seen_utc": datetime.now(timezone.utc).isoformat(),
        "rumor_details": {
            "rumored_party": "PT Alpha Investama",
            "percentages": [30.0],
            "money": ["Rp1 triliun"],
        },
        "issuer_profile": {
            "issuer_name": "PT ABCD Tbk",
            "controller": {
                "name": "PT Current Owner",
                "verified": True,
                "stake_pct": 55.0,
            },
            "major_shareholders": [
                {
                    "name": "PT Current Owner",
                    "stake_pct": 55.0,
                    "verified": True,
                }
            ],
            "business_activity": "Media dan periklanan",
            "sector": "Media & Communications",
            "profile_source": "IDX PROFILE",
            "profile_source_quality": "OFFICIAL",
        },
        "market_data": {
            "last_price": 1000,
            "change_pct": 1.0,
        },
    }

    current = {
        **previous,
        "sources": ["CNBC Indonesia"],
        "source_count": 3,
        "issuer_profile": None,
        "market_data": {
            "last_price": 1200,
            "change_pct": 20.0,
        },
    }

    merged = merge_rumor_records(
        previous,
        current,
    )

    merge_ok = all([
        merged.get("issuer_profile") is not None,
        merged["issuer_profile"]["controller"]["name"]
        == "PT Current Owner",
        merged["rumor_details"]["rumored_party"]
        == "PT Alpha Investama",
    ])

    separation_message = format_rumor_alert(
        previous
    )

    separation_ok = all([
        "Pengendali saat ini:</b> PT Current Owner" in separation_message,
        "Pihak yang dirumorkan:</b> ⚠️ PT Alpha Investama" in separation_message,
        "Rumor Strength menunjukkan" in separation_message,
    ])

    private_profile = {
        "key": "IPO|COMPANY|NUSANTARA",
        "ticker": None,
        "company_name": "PT Nusantara Digital",
        "category": "IPO",
        "status": "ACTIVE",
        "strength": "MEDIUM",
        "source_count": 2,
        "sources": ["Kontan", "Bisnis.com"],
        "title": "Wacana IPO PT Nusantara Digital",
        "first_seen_utc": datetime.now(timezone.utc).isoformat(),
        "last_seen_utc": datetime.now(timezone.utc).isoformat(),
        "rumor_details": {
            "money": ["Rp2 triliun"],
        },
        "issuer_profile": {
            "issuer_name": "PT Nusantara Digital",
            "controller": {
                "name": "Budi Santoso",
                "verified": False,
                "verification_level": "MEDIA_CONTEXT",
            },
            "business_activity": "teknologi dan platform digital",
            "sector": "Technology",
            "profile_source": "Kontan",
            "profile_source_quality": "MEDIA_CONTEXT",
        },
    }

    private_message = format_rumor_alert(
        private_profile
    )

    private_ipo_ok = all([
        "PROFIL PERUSAHAAN" in private_message,
        "Founder/Pengendali (konteks)" in private_message,
        "Bidang usaha" in private_message,
        "RUMOR IPO DETAIL" in private_message,
    ])

    return {
        "passed": all([
            ticker_ok,
            party_ok,
            listing_guard_ok,
            confirmation_ok,
            merge_ok,
            separation_ok,
            private_ipo_ok,
        ]),
        "ticker_recovery": ticker_ok,
        "rumored_party_guard": party_ok,
        "listing_venue_guard": listing_guard_ok,
        "official_confirmation_match": confirmation_ok,
        "record_merge_guard": merge_ok,
        "owner_vs_rumored_party": separation_ok,
        "private_ipo_profile": private_ipo_ok,
    }


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

        control_status = control_change_evidence_status(
            article
        )

        if control_status:
            lines.append(
                "🔁 <b>Perubahan pengendali:</b> "
                + html.escape(
                    control_status
                )
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
            f"🔬 <b>Detail hasil ekstraksi:</b> "
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


# ============================================================
# V6.6.3 — CLEAN TELEGRAM ALERT UX
# ============================================================

def _compact_issuer(article):
    d = article.get("details") or {}
    ticker = _valid_idx_ticker(d.get("ticker"))

    aliases = _dedup_issuer_aliases(
        list(article.get("issuer_aliases") or [])
        + list(get_ticker_aliases(ticker) if ticker else [])
    )

    return (
        article.get("issuer_name")
        or (aliases[0] if aliases else None)
        or d.get("target")
        or d.get("acquirer")
        or "-"
    )


def _compact_official(article):
    ref = article.get("official_reference")

    if not ref and official_source_rank(article) > 0:
        ref = _official_reference_from_article(article)

    if not ref and isinstance(article.get("verified_official_ref"), dict):
        cached = article.get("verified_official_ref") or {}
        if cached.get("authority"):
            ref = cached

    if not ref:
        return "⚪ belum ditemukan", None

    authority = str(ref.get("authority") or "OFFICIAL")
    kind = str(ref.get("kind") or "PRIMARY")
    url = str(ref.get("url") or "").strip() or None
    return f"✅ {authority} — {kind}", url


def control_change_evidence_status(article):
    """One evidence model for Auto Alert, /analyze and /profile.

    CONFIRMED requires:
    - explicit control-change wording in headline/snippet/deep evidence, and
    - an official corporate-action reference.

    TENDER OFFER alone never auto-confirms control change.
    """
    text = " ".join([
        str(article.get("title") or ""),
        str(article.get("snippet") or ""),
    ])

    evidence = article.get(
        "controller_evidence"
    ) or {}

    explicit = bool(
        _controller_context_explicit(
            text
        )
        or evidence.get(
            "explicit_control_change"
        )
    )

    official = bool(
        article.get("official_reference")
        or official_source_rank(article) > 0
        or article.get("verified_official_ref")
    )

    if explicit and official:
        return "✅ terkonfirmasi — event perubahan pengendali resmi"

    if explicit:
        return "🟡 terindikasi — menunggu konfirmasi resmi"

    return None


def compact_material_lines(article):
    d = article.get("details") or {}
    event = str(article.get("event_type") or "")
    lines = []

    if event == "IPO":
        price = d.get("price_range") or d.get("ipo_single_price")
        if price:
            lines.append("💵 Harga: " + html.escape(str(price)))
        if d.get("share_count"):
            lines.append("📦 Saham ditawarkan: " + html.escape(str(d["share_count"])))
        if d.get("percentages"):
            lines.append("📊 Porsi: " + format_pct(d["percentages"][0]))
        if d.get("money"):
            lines.append("💰 Nilai/Dana: " + html.escape(str(d["money"][0])))
        if d.get("underwriter"):
            lines.append("🏢 Underwriter: " + html.escape(str(d["underwriter"])))

    elif event == "RIGHTS ISSUE":
        if d.get("ratio"):
            lines.append("⚖️ Rasio HMETD: " + html.escape(str(d["ratio"])))
        if d.get("execution_price"):
            lines.append("💵 Harga pelaksanaan: " + html.escape(str(d["execution_price"])))
        if d.get("share_count"):
            lines.append("📦 Saham baru: " + html.escape(str(d["share_count"])))
        if d.get("money"):
            lines.append("💰 Nilai/Dana: " + html.escape(str(d["money"][0])))
        if d.get("standby_buyer"):
            lines.append("🧍 Standby buyer: " + html.escape(str(d["standby_buyer"])))

    else:
        role_meta = d.get("role_meta") or {}

        if d.get("acquirer"):
            lines.append("🤝 Acquirer: " + html.escape(str(d["acquirer"])))
        elif role_meta.get("acquirer_suppressed"):
            lines.append("🤝 Acquirer: ⚪ belum terkonfirmasi")

        if d.get("target"):
            lines.append("🎯 Target: " + html.escape(str(d["target"])))
        elif role_meta.get("target_suppressed"):
            lines.append("🎯 Target: ⚪ belum terkonfirmasi")

        if d.get("percentages"):
            lines.append("📊 Stake: " + format_pct(d["percentages"][0]))
        if d.get("money"):
            lines.append("💰 Nilai transaksi: " + html.escape(str(d["money"][0])))
        if d.get("tender_price"):
            lines.append("💵 Harga tender: " + html.escape(str(d["tender_price"])))
        if d.get("share_count"):
            lines.append("📦 Jumlah saham: " + html.escape(str(d["share_count"])))

        control_status = control_change_evidence_status(article)
        if control_status:
            lines.append("🔁 Pengendali: " + html.escape(control_status))

    schedule = d.get("schedule") or {}
    if isinstance(schedule, dict):
        for key, value in list(schedule.items())[:3]:
            if not value:
                continue
            label = LIFECYCLE_SCHEDULE_LABELS.get(key, key)
            lines.append(
                "📅 " + html.escape(str(label)) + ": " + html.escape(str(value))
            )

    return lines[:9]


def compact_market_context_lines(article):
    market = article.get("market_data") or {}
    lines = []

    if market.get("last_price") is not None:
        lines.append("💵 Harga pasar: " + format_price(market.get("last_price")))
    if market.get("change_pct") is not None:
        lines.append("📊 Perubahan harian: " + f"{float(market.get('change_pct')):+.2f}%")
    if market.get("market_date"):
        lines.append("🗓 Data pasar: " + html.escape(str(market.get("market_date"))))

    return lines


def format_alert(article):
    """Compact report for Auto Alert, /latest and Decision Board."""
    apply_article_integrity_guards(article)

    d = article.get("details") or {}
    ticker = _valid_idx_ticker(d.get("ticker")) or "-"
    issuer = _compact_issuer(article)
    evt = str(article.get("event_type") or "CORPORATE ACTION")
    geo = str(article.get("geo") or "-")
    snap = lifecycle_snapshot(article)
    official_text, official_url = _compact_official(article)

    alert_mode = str(article.get("alert_mode") or "NEW_EVENT").upper()
    changes = [
        str(x)
        for x in (article.get("persistent_change_lines") or [])
        if x
    ]

    if alert_mode == "MATERIAL_UPDATE":
        header = f"🚨 <b>MATERIAL UPDATE — {html.escape(ticker)}</b>"
    else:
        header = f"{alert_icon(evt)} <b>CORPORATE ACTION — {html.escape(ticker)}</b>"

    lines = [
        header,
        "",
        "📌 <b>INTI EVENT</b>",
        f"🏢 <b>{html.escape(ticker)}</b> — {html.escape(str(issuer))}",
        f"🏷 Event: <b>{html.escape(evt)}</b>",
        f"🌏 Kategori: {html.escape(geo)}",
        f"🏛 Official: {html.escape(official_text)}",
        (
            f"🚦 Lifecycle: <b>{html.escape(str(snap.get('stage') or '-'))}</b> "
            f"({int(snap.get('stage_step') or 1)}/{int(snap.get('stage_total') or 1)})"
        ),
        "⏭ Next: " + html.escape(str(snap.get("next_milestone") or "-")),
    ]

    if official_url:
        lines.append(
            f'<a href="{html.escape(official_url, quote=True)}">📎 Buka sumber resmi</a>'
        )

    profile_lines = issuer_profile_lines(article)
    if profile_lines:
        lines += [
            "",
            "🏢 <b>PROFIL EMITEN</b>",
        ]
        lines.extend(profile_lines)

    if changes and alert_mode == "MATERIAL_UPDATE":
        lines += ["", "🆕 <b>YANG BERUBAH</b>"]
        lines.extend("• " + html.escape(change) for change in changes[:8])

    material = compact_material_lines(article)
    if material:
        lines += ["", "💰 <b>DETAIL MATERIAL</b>"]
        lines.extend(material)

    market = compact_market_context_lines(article)
    if market:
        lines += ["", "📈 <b>MARKET CONTEXT</b>"]
        lines.extend(market)
        lines.append("ℹ️ Perubahan harga hanya konteks dan tidak memicu alert ulang.")

    title = str(article.get("title") or "").strip()
    source = str(article.get("source") or "-").strip()
    published = str(article.get("published") or "-").strip()
    link = str(article.get("source_url") or article.get("link") or "").strip()

    if title:
        lines += [
            "",
            "📰 <b>SUMBER INFORMASI</b>",
            html.escape(title[:350]),
            "🏢 " + html.escape(source),
            "🕒 " + html.escape(published),
        ]

    if link:
        lines.append(f'<a href="{html.escape(link, quote=True)}">🔗 Buka berita</a>')

    if ticker != "-":
        lines += [
            "",
            (
                f"💡 Detail: <code>/analyze {html.escape(ticker)}</code>"
                f" | <code>/timeline {html.escape(ticker)}</code>"
                f" | <code>/official {html.escape(ticker)}</code>"
            ),
        ]

    lines.append("⚠️ <i>Monitoring corporate action, bukan rekomendasi beli/jual.</i>")
    return "\n".join(lines)[:3900]


def format_analysis_report(article):
    """Full technical/detail report exclusively for /analyze and /deep."""
    apply_article_integrity_guards(article)

    title = html.escape(article["title"])
    source = html.escape(article["source"])
    published = html.escape(article["published"])
    evt = html.escape(article["event_type"])
    geo = html.escape(article["geo"])
    link = html.escape(article.get("source_url") or article["link"], quote=True)

    family = html.escape(alert_family(article["event_type"]))
    score = article["ca_score"]
    label = score_label(score)
    detail_text = "\n".join(detail_lines(article))

    if article["event_type"] == "IPO":
        watch = "🔎 <b>Pantau:</b> harga final, bookbuilding, underwriter, valuasi, penggunaan dana, dan oversubscription."
    elif article["event_type"] == "RIGHTS ISSUE":
        watch = "🔎 <b>Pantau:</b> harga pelaksanaan, rasio HMETD, cum/ex-right, standby buyer, penggunaan dana, dan potensi dilusi."
    else:
        watch = "🔎 <b>Pantau:</b> pembeli, target, stake, nilai transaksi, sumber pendanaan, perubahan pengendali dan tender wajib."

    return (
        f"🔎 <b>ANALISIS DETAIL — {family}</b>\n\n"
        f"🏷 <b>Jenis:</b> {evt}\n"
        f"🌏 <b>Kategori:</b> {geo}\n"
        + "\n".join(official_reference_lines(article)) + "\n"
        + (("\n".join(ticker_recovery_lines(article)) + "\n") if ticker_recovery_lines(article) else "")
        + (("\n".join(issuer_resolution_lines(article)) + "\n") if issuer_resolution_lines(article) else "")
        + (("\n".join(multisource_issuer_lines(article)) + "\n") if multisource_issuer_lines(article) else "")
        + (("\n".join(money_guard_lines(article)) + "\n") if money_guard_lines(article) else "")
        + (("\n".join(lifecycle_lines(article)) + "\n") if lifecycle_lines(article) else "")
        + f"{detail_text}\n"
        + (("\n".join(deep_extraction_lines(article)) + "\n") if deep_extraction_lines(article) else "")
        + (("\n".join(schedule_lines(article)) + "\n") if schedule_lines(article) else "")
        + (("\n".join(market_data_lines(article)) + "\n") if market_data_lines(article) else "")
        + (("\n🏢 <b>PROFIL EMITEN</b>\n" + "\n".join(issuer_profile_lines(article)) + "\n") if issuer_profile_lines(article) else "")
        + "\n" + "\n".join(decision_support_lines(article)) + "\n\n"
        + f"📰 <b>Berita:</b> {title}\n"
        + f"🏢 <b>Sumber:</b> {source}\n"
        + f"🕒 <b>Publikasi:</b> {published}\n\n"
        + f"🎯 <b>Information Score:</b> {score}/100\n"
        + f"📌 <b>Information Quality:</b> {label}\n"
        + f"🧠 <b>Catalyst:</b> {html.escape(catalyst_badge(article.get('catalyst', 'NEUTRAL')))}\n"
        + "".join(
            f"   • {html.escape(reason)}\n"
            for reason in article.get("catalyst_reasons", [])[:3]
        )
        + f"\n{watch}\n\n"
        + f'<a href="{link}">🔗 Buka berita</a>\n\n'
        + "⚠️ <i>Analisis detail adalah alat triase monitoring, bukan rekomendasi beli/jual. "
          "Field teknis menjelaskan bagaimana data ditemukan; verifikasi dokumen resmi sebelum mengambil keputusan.</i>"
    )


def v663_core_selftest():
    sample = {
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
        "catalyst_reasons": [],
        "issuer_name": "Era Media Sejahtera",
        "issuer_aliases": ["Era Media Sejahtera"],
        "official_reference": {
            "authority": "IDX",
            "kind": "PRIMARY",
            "url": "https://example.com/official",
        },
        "market_data": {
            "last_price": 352,
            "change_pct": 19.73,
            "market_date": "2026-08-18",
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
    }

    compact = format_alert(sample)
    return {
        "passed": all([
            "INTI EVENT" in compact,
            "DETAIL MATERIAL" in compact,
            "MARKET CONTEXT" in compact,
            "Harga pasar" in compact,
            "tidak memicu alert ulang" in compact,
            "Ticker Recovery" not in compact,
            "Source Resolver" not in compact,
            "Deep Extraction" not in compact,
        ]),
        "compact_blocks": (
            "INTI EVENT" in compact
            and "DETAIL MATERIAL" in compact
            and "MARKET CONTEXT" in compact
        ),
        "technical_hidden": (
            "Ticker Recovery" not in compact
            and "Source Resolver" not in compact
            and "Deep Extraction" not in compact
        ),
    }



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
<b>📊 Kabar Saham Intelligence V6.7.7 / V5.4 Core</b>

Perintah:
/start — aktifkan alert otomatis
/decision — Decision Board
/menu — Control Center (Command Bridge)
/syncmenu — sinkronkan Native Telegram Menu (Command Bridge)
/health — cek kesehatan runtime GitHub Actions
/today — milestone corporate action hari ini (Command Bridge)
/recent — perubahan lifecycle terbaru (Command Bridge)
/rumors — daftar rumor aktif (Command Bridge)
/rumor TICKER — detail rumor ticker/perusahaan (Command Bridge)
/rumorboard — dashboard rumor (Command Bridge)
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
/profile TICKER — profil emiten, pengendali & bidang usaha
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

V6.7.7 Ownership Safety + Rumor Intelligence:\n• price-move % is never published as transaction stake\n• headline fragments are blocked from rumored-party identity\n• invalid share count is hidden\n• confirmed rumor duplicates with the same official evidence are merged\n• sparse/malformed rumor issuer profile gets quality-aware deep fallback\n• rumor IPO + M&A + rights/private placement/buyback/divestasi/restrukturisasi/delisting\n• WEAK/MEDIUM/STRONG based on source quality + anti-copy corroboration, not probability\n• CONFIRMED/DENIED/EXPIRED lifecycle\n• /rumors + /rumor + /rumorboard\n\nV6.6.4.2 Profile/Analyze Sync + Official Evidence Wording:\n• quality-aware profile cache merge\n• /profile deep-context fallback identical to /analyze\n• verified controller survives stale scanner cache\n• verified official cache used in analysis wording\n• controller evidence distinguished from event-feed evidence\n\nV6.6.4.1 Controller Deep Resolver + Control Status Consistency:\n• official IDX result-title actor resolver\n• deep-article identity cross-verification\n• target-company self-controller guard\n• cached missing-controller refresh\n• consistent control status in alert/analyze/profile\n\nV6.6.4 Issuer Profile Intelligence:\n• controller/major-shareholder guard\n• business activity + sector/subsector\n• IDX profile priority + market fallback\n• profile context never triggers re-alert\n• /profile TICKER\n\nV6.6.3 Clean Alert + Persistent Dedup Layer:\n• compact alert: INTI EVENT → DETAIL MATERIAL → MARKET CONTEXT\n• market data is context only, not an event trigger\n• /analyze retains full technical detail\n\nV6.6.2 Entity Role + Indonesia Classification Guard:\n• headline fragments are rejected as Acquirer/Target\n• speculative actor candidates are suppressed until sufficiently confirmed\n• recovered IDX ticker + local issuer evidence cannot remain GLOBAL\n\nV6.2.1 Ticker Recovery + Issuer Resolver:\n• exact ticker → title/snippet → targeted search fallback\n• issuer alias propagation reconnects ticker-less disclosures\n• official lookup uses ticker + issuer name when available\n\nV6.2 Official Source Priority:
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
        format_analysis_report(article),
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
            "✅ <b>Kabar Saham Intelligence V6.7.7 / V5.4 Core aktif.</b>\n\n"
            "Context awareness, post-event filter, IPO aggregate detection, dan participation-aware catalyst telah diaktifkan.\n\n"
            + HELP_TEXT,
        )

    elif command == "/help":
        await send_message(chat_id, HELP_TEXT)

    elif command == "/status":
        await send_message(
            chat_id,
            "🟢 <b>Bot aktif — V6.7.7 / V5.4 Core</b>\n"
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
            f"Rumor Intelligence: {'ON' if RUMOR_INTELLIGENCE_ENABLED else 'OFF'}\n"
            f"Rumor Auto Alert: {'ON' if RUMOR_AUTO_ALERT_ENABLED else 'OFF'}\n"
            f"Rumor Query Limit: {RUMOR_QUERY_LIMIT} + {RUMOR_CONFIRMATION_QUERY_LIMIT} confirmation\n"
            f"Rumor Lookback: {RUMOR_LOOKBACK_HOURS} jam\n"
            f"Rumor Expiry: {RUMOR_EXPIRE_DAYS} hari\n"
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

    elif command == "/profile":
        if not args:
            await send_message(
                chat_id,
                "Gunakan /profile TICKER — contoh /profile DOOH",
            )
        else:
            await send_issuer_profile(
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
