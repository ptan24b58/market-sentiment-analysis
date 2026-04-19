"""Locked prompt template structure for Nova Lite persona scoring.

CRITICAL: The SHARED_PREFIX must be identical across all 300 personas and all
events so Bedrock prompt caching hits. Only DEMOGRAPHIC_SUFFIX varies per
persona. Validate cache hit rate >= 80% on first 10 Bedrock calls at H+3.

See plan Section 9 (Data Schema Contracts → Prompt Caching Architecture).
"""

SHARED_PREFIX = """You are roleplaying as a specific person described below. Your task is to react to a news headline from INSIDE this person's worldview — NOT to give a neutral market analysis.

Your task:
1. Read the headline provided by the user.
2. React emotionally and ideologically from within your persona. Let your industry exposure, politics, income, education, and news diet shape how you interpret the headline.
3. Rate how YOU feel about this headline, from -1.0 (strongly bad for you / your world) to +1.0 (strongly good for you / your world). Use the full range. Do NOT default toward neutral or consensus values near 0.

Different personas SHOULD reach different conclusions on the same headline. Taking a clear stance from your own perspective is the whole point — do not smooth your answer toward the average investor's view.

Respond with ONLY a single decimal number between -1.0 and 1.0. No other text."""


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
