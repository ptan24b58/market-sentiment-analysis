"""Shared constants for the persona sentiment pipeline.

All workstreams import from here to stay aligned on ticker universe, paths,
model config, homophily targets, Deffuant params, and the sentinel gate threshold.
"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
CACHE_DIR = DATA_DIR / "cache"
REPORTS_DIR = PROJECT_ROOT / "reports"

for _d in (DATA_DIR, RAW_DATA_DIR, PROCESSED_DATA_DIR, CACHE_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

TEXAS_15_TICKERS = [
    "TSLA",
    "XOM",
    "OXY",
    "HAL",
    "SLB",
    "T",
    "DELL",
    "AAL",
    "HPE",
    "CVX",
    "KR",
    "WMB",
    "EOG",
    "VLO",
    "COP",
]

EVENT_WINDOW_START = "2024-10-01"
EVENT_WINDOW_END = "2026-04-17"

DEFAULT_PERSONA_COUNT = 300
MIN_PERSONA_COUNT_FALLBACK = 150

# Primary inference model for persona sentiment scoring.
# Claude Sonnet 4.5 — elite persona role-play; ~3x slower than Nova Lite per call.
# Requires Bedrock model access toggled ON in the AWS console for this region.
# If AccessDeniedException at runtime: enable "Claude Sonnet 4.5" in Bedrock → Model access.
BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
BEDROCK_REGION = "us-east-1"
# Fallback only used if explicitly opted into via code; not automatic.
BEDROCK_FALLBACK_MODEL_ID = "amazon.nova-lite-v1:0"

HOMOPHILY_TARGETS = {
    "political": 0.35,
    "income": 0.25,
    "geographic": 0.50,
}
HOMOPHILY_TOLERANCE = 0.05
GRAPH_MEAN_DEGREE_RANGE = (10, 30)

DEFFUANT_EPSILON_SWEEP = [0.2, 0.3, 0.4]
DEFFUANT_EPSILON_PRIMARY = 0.3
DEFFUANT_MU = 0.5
DEFFUANT_ROUNDS = 3

SENTINEL_VARIANCE_THRESHOLD = 0.1
SENTINEL_EVENT_COUNT = 3
SENTINEL_PASS_REQUIRED = 2

AR_ESTIMATION_WINDOW_DAYS = 252
AR_ESTIMATION_GAP_DAYS = 20
AR_MIN_R_SQUARED = 0.3

GDELT_DOC_API_ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_TONE_MAGNITUDE_MIN = 2.0
GDELT_ENTITY_CONFIDENCE_MIN = 0.5

SENTIMENT_REGEX = r"-?[01]?\.\d+"
MAX_PARSE_RETRIES = 1
PARSE_FAILURE_ALERT_THRESHOLD = 0.05
PARSE_FAILURE_TEMPLATE_SWITCH_THRESHOLD = 0.10

BEDROCK_CONCURRENT_SEMAPHORE = 50
BEDROCK_MAX_BACKOFF_SECONDS = 30
BEDROCK_BASE_BACKOFF_SECONDS = 1.0

MIN_EVENT_COUNT = 30
STAGE1_EVENT_BUFFER = 35
MAX_EVENTS_PER_TICKER = 5
MAX_EVENTS_PER_TICKER_RELAXED = 7

MARKET_PROXY_TICKER = "^GSPC"

POLITICAL_LEAN_DISTRIBUTION_TX = {
    "R": 0.52,
    "D": 0.47,
    "I": 0.01,
}
