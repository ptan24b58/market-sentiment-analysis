"""Locked prompt template structure for Nova Lite persona scoring.

CRITICAL: The SHARED_PREFIX must be identical across all 300 personas and all
events so Bedrock prompt caching hits. Only DEMOGRAPHIC_SUFFIX varies per
persona. Validate cache hit rate >= 80% on first 10 Bedrock calls at H+3.

See plan Section 9 (Data Schema Contracts → Prompt Caching Architecture).
"""

SHARED_PREFIX = """You are evaluating a news headline for its likely impact on stock market sentiment.

Your task:
1. Read the headline provided by the user.
2. Assess whether this headline would cause a positive or negative sentiment reaction among investors.
3. Rate the headline from -1.0 (extremely negative market sentiment) to 1.0 (extremely positive market sentiment).

Respond with ONLY a single decimal number between -1.0 and 1.0, where -1.0 is extremely negative and 1.0 is extremely positive. No other text."""


DEMOGRAPHIC_SUFFIX_TEMPLATE = (
    "\n\nYou are a {age}-year-old {income_bracket}-income resident of "
    "{zip_region}, Texas, earning approximately ${annual_income:,} per year. "
    "You work in {occupation_phrase} and have {investment_exposure_phrase}. "
    "You completed {education_phrase}. "
    "You are registered as a {party_reg} voter and consume primarily "
    "{news_consumption_phrase}. {contextual_anchor}"
)


RETRY_REINFORCEMENT = (
    "\n\nYou must respond with ONLY a decimal number between -1.0 and 1.0. "
    "Example: -0.45"
)


STRUCTURED_FALLBACK_PROMPT = (
    "Rate this headline. Output exactly one number from -1.0 to 1.0."
)


def build_persona_system_prompt(demographic_suffix: str) -> str:
    """Compose a persona system prompt from shared prefix + demographic suffix.

    The returned string is what gets sent to Bedrock as the system prompt. The
    prefix portion (SHARED_PREFIX) is the Bedrock cache key.
    """
    return SHARED_PREFIX + demographic_suffix


def build_user_prompt(headline_text: str, ticker: str) -> str:
    """Build the per-event user prompt. Same across all personas for a given event."""
    return f"Ticker: {ticker}\nHeadline: {headline_text}"


def build_zero_shot_system_prompt() -> str:
    """Zero-shot baseline uses shared prefix ONLY — no demographic suffix."""
    return SHARED_PREFIX
