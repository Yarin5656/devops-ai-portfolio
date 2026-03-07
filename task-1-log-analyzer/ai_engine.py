"""
ai_engine.py

AI-powered log analysis engine using the Anthropic Claude API.

Design principles
-----------------
- The rule engine always runs first and is the authoritative fallback.
- This module is purely additive: it enriches the report with a second
  opinion, never replaces the rule-based result.
- If ANTHROPIC_API_KEY is absent, the API call fails for any reason, or
  the response JSON is malformed, the engine returns a typed status value
  so the report can show a clear fallback note rather than silently omitting
  the AI section.

Public API
----------
    result = analyse_with_ai(parsed_log)
    if result.analysis:
        # use result.analysis (AIAnalysis dataclass)
    else:
        # show result.detail as fallback note in report
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

from log_parser import ParsedLog

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_API_KEY_ENV = "ANTHROPIC_API_KEY"
_MODEL = "claude-sonnet-4-6"
_MAX_TOKENS = 1024

# Maximum error-context lines sent to the API — keeps token usage predictable
_MAX_CONTEXT_LINES = 60

# Status codes returned by the engine (used by report_generator for fallback notes)
STATUS_SUCCESS = "success"
STATUS_NO_KEY = "no_key"
STATUS_IMPORT_ERROR = "import_error"
STATUS_API_ERROR = "api_error"
STATUS_PARSE_ERROR = "parse_error"
STATUS_NO_ERRORS = "no_errors"

_FALLBACK_MESSAGES = {
    STATUS_NO_KEY: (
        "`ANTHROPIC_API_KEY` environment variable is not set. "
        "AI analysis was skipped. Rule-based analysis is shown above."
    ),
    STATUS_IMPORT_ERROR: (
        "The `anthropic` Python package is not installed. "
        "Run `pip install anthropic` and retry with `--ai`. "
        "Rule-based analysis is shown above."
    ),
    STATUS_API_ERROR: (
        "The Anthropic API returned an error. This may be a transient issue "
        "(rate limit, network timeout, or service disruption). "
        "Rule-based analysis is shown above."
    ),
    STATUS_PARSE_ERROR: (
        "The AI response could not be parsed. The model may have returned "
        "an unexpected format. Rule-based analysis is shown above."
    ),
    STATUS_NO_ERRORS: (
        "No error lines were detected in the log, so AI analysis was not attempted."
    ),
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class AIAnalysis:
    """
    Structured diagnostic result produced by the AI engine.

    Fields map directly to report sections. All fields are text produced
    by the LLM and validated for presence before being stored here.
    """

    category: str
    root_cause: str
    impact: str
    recommended_checks: List[str]
    suggested_fixes: List[str]
    confidence: str
    model: str = _MODEL
    engine: str = "ai"


@dataclass
class AIEngineResult:
    """
    Return value of analyse_with_ai().

    Always populated — callers never need to handle None.
    Check `analysis` to see whether AI succeeded; use `detail` as the
    human-readable fallback note when it did not.
    """

    analysis: Optional[AIAnalysis]
    status: str    # one of the STATUS_* constants
    detail: str    # sentence(s) suitable for display in the Markdown report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _api_key_present() -> bool:
    """Return True if a non-empty Anthropic API key exists in the environment."""
    return bool(os.environ.get(_API_KEY_ENV, "").strip())


def _build_context_excerpt(parsed_log: ParsedLog) -> str:
    """
    Build a focused log excerpt to send to the API.

    Strategy (in priority order):
    1. Primary error context block (lines surrounding the worst error).
    2. Remaining unique error lines not already in the block.
    3. Trimmed to _MAX_CONTEXT_LINES to stay within token budget.

    Args:
        parsed_log: Parsed log from log_parser.parse_log().

    Returns:
        A newline-joined string of the most relevant log lines.
    """
    seen: set = set()
    context: List[str] = []

    for line in parsed_log.primary_error_block:
        if line not in seen:
            context.append(line)
            seen.add(line)

    for _, line in parsed_log.error_lines:
        if line not in seen:
            context.append(line)
            seen.add(line)

    return "\n".join(context[:_MAX_CONTEXT_LINES])


def _build_prompt(parsed_log: ParsedLog, rule_category: Optional[str]) -> str:
    """
    Construct the user prompt sent to Claude.

    The prompt includes:
    - The focused log excerpt (error block + error lines).
    - A hint about what the rule engine already classified (gives the AI
      useful context without constraining its output).
    - A strict JSON schema the model must follow.

    Args:
        parsed_log: Parsed log data.
        rule_category: Category string from the rule engine, or None.

    Returns:
        Fully formatted prompt string.
    """
    excerpt = _build_context_excerpt(parsed_log)

    rule_hint = (
        f"\nThe rule-based engine has already classified this as a "
        f"`{rule_category}` issue. You may agree or propose a different category "
        f"if the evidence warrants it.\n"
        if rule_category
        else ""
    )

    return f"""You are a senior Site Reliability Engineer with deep expertise in \
cloud infrastructure, Kubernetes, CI/CD pipelines, and Linux systems administration.

Analyse the following log excerpt from a production infrastructure system.{rule_hint}
Return a diagnostic report as a strict JSON object — no markdown fences, no extra text.

### LOG EXCERPT ###
{excerpt}
### END LOG EXCERPT ###

Required JSON schema (every field is mandatory):

{{
  "category": "<one of: network | permissions | dependency | configuration | infrastructure>",
  "root_cause": "<technical explanation of the root cause — 2 to 4 sentences>",
  "impact": "<what fails as a result and who is affected — 1 to 3 sentences>",
  "recommended_checks": [
    "<specific diagnostic command or check to run first>",
    "<specific diagnostic command or check to run second>",
    "<specific diagnostic command or check to run third>"
  ],
  "suggested_fixes": [
    "<concrete, actionable remediation step 1>",
    "<concrete, actionable remediation step 2>",
    "<concrete, actionable remediation step 3>"
  ],
  "confidence": "<high | medium | low>"
}}"""


def _strip_markdown_fences(text: str) -> str:
    """
    Remove leading/trailing markdown code fences if the model added them.

    Handles patterns like:
        ```json
        { ... }
        ```

    Args:
        text: Raw text from the API response.

    Returns:
        Cleaned text with fences removed.
    """
    text = text.strip()
    # Remove opening fence (```json, ```JSON, ```, etc.)
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
    # Remove closing fence
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _validate_response(data: dict) -> Optional[str]:
    """
    Validate that the parsed JSON response contains all required fields
    with acceptable values.

    Args:
        data: Parsed JSON dict from the API.

    Returns:
        An error message string if validation fails, or None on success.
    """
    required = {"category", "root_cause", "impact", "recommended_checks",
                "suggested_fixes", "confidence"}
    missing = required - set(data.keys())
    if missing:
        return f"Missing fields: {sorted(missing)}"

    valid_categories = {"network", "permissions", "dependency", "configuration", "infrastructure"}
    if data["category"].lower() not in valid_categories:
        return f"Invalid category: {data['category']!r}"

    valid_confidence = {"high", "medium", "low"}
    if data["confidence"].lower() not in valid_confidence:
        return f"Invalid confidence: {data['confidence']!r}"

    for list_field in ("recommended_checks", "suggested_fixes"):
        if not isinstance(data[list_field], list):
            return f"Field '{list_field}' must be a list, got {type(data[list_field]).__name__}"
        if not data[list_field]:
            return f"Field '{list_field}' must not be empty"

    return None  # all good


def _call_api(prompt: str) -> dict:
    """
    Call the Anthropic Messages API and return the validated parsed response.

    Handles:
    - ImportError if the `anthropic` package is missing (re-raises with
      a clear installation message).
    - API-level errors (authentication, rate limits, server errors) —
      re-raises as RuntimeError so the caller can catch generically.
    - JSON decode errors — re-raises as ValueError.
    - Response validation — raises ValueError on schema violations.

    Args:
        prompt: Fully formatted prompt string.

    Returns:
        Validated dict matching the JSON schema in _build_prompt().

    Raises:
        ImportError: anthropic package not installed.
        RuntimeError: Anthropic API error.
        ValueError: JSON parse or schema validation failure.
    """
    try:
        import anthropic  # type: ignore
    except ImportError as exc:
        raise ImportError(
            "The 'anthropic' package is not installed. Run: pip install anthropic"
        ) from exc

    api_key = os.environ[_API_KEY_ENV]
    client = anthropic.Anthropic(api_key=api_key)

    logger.info("Calling Anthropic API (model: %s, max_tokens: %d) …", _MODEL, _MAX_TOKENS)

    try:
        message = client.messages.create(
            model=_MODEL,
            max_tokens=_MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError as exc:
        raise RuntimeError(f"Anthropic authentication failed — check your API key: {exc}") from exc
    except anthropic.RateLimitError as exc:
        raise RuntimeError(f"Anthropic rate limit hit: {exc}") from exc
    except anthropic.APIConnectionError as exc:
        raise RuntimeError(f"Network error reaching Anthropic API: {exc}") from exc
    except anthropic.APIStatusError as exc:
        raise RuntimeError(f"Anthropic API error (HTTP {exc.status_code}): {exc.message}") from exc

    raw_text = message.content[0].text
    logger.debug("Raw AI response (%d chars): %.400s …", len(raw_text), raw_text)

    cleaned = _strip_markdown_fences(raw_text)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse AI response as JSON: {exc}") from exc

    error = _validate_response(data)
    if error:
        raise ValueError(f"AI response schema violation: {error}")

    return data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyse_with_ai(
    parsed_log: ParsedLog,
    rule_category: Optional[str] = None,
) -> AIEngineResult:
    """
    Attempt an AI-powered analysis of the parsed log.

    This function never raises — all error conditions are captured in
    the returned AIEngineResult so the caller can gracefully continue.

    Args:
        parsed_log: Output of log_parser.parse_log().
        rule_category: Category from the rule engine (used as a hint in
                       the prompt). Pass None if unavailable.

    Returns:
        AIEngineResult with analysis=AIAnalysis on success, or
        analysis=None with a populated status and detail on failure.
    """
    def _fail(status: str, log_msg: str, *args) -> AIEngineResult:
        """Log at appropriate level and return a failed AIEngineResult."""
        if status in (STATUS_NO_KEY, STATUS_NO_ERRORS):
            logger.info(log_msg, *args)
        else:
            logger.error(log_msg, *args)
        return AIEngineResult(
            analysis=None,
            status=status,
            detail=_FALLBACK_MESSAGES[status],
        )

    # ── Pre-flight checks ──────────────────────────────────────────────────
    if not _api_key_present():
        return _fail(STATUS_NO_KEY, "ANTHROPIC_API_KEY not set — skipping AI analysis.")

    if not parsed_log.error_lines:
        return _fail(STATUS_NO_ERRORS, "No error lines in log — skipping AI analysis.")

    # ── Call API ───────────────────────────────────────────────────────────
    try:
        prompt = _build_prompt(parsed_log, rule_category)
        data = _call_api(prompt)

    except ImportError as exc:
        return _fail(STATUS_IMPORT_ERROR, "anthropic package missing: %s", exc)

    except RuntimeError as exc:
        return _fail(STATUS_API_ERROR, "Anthropic API error: %s", exc)

    except ValueError as exc:
        return _fail(STATUS_PARSE_ERROR, "AI response invalid: %s", exc)

    except Exception as exc:  # pylint: disable=broad-except
        return _fail(STATUS_API_ERROR, "Unexpected AI engine error: %s", exc)

    # ── Build result ───────────────────────────────────────────────────────
    analysis = AIAnalysis(
        category=data["category"].lower(),
        root_cause=data["root_cause"],
        impact=data["impact"],
        recommended_checks=data["recommended_checks"],
        suggested_fixes=data["suggested_fixes"],
        confidence=data["confidence"].lower(),
        model=_MODEL,
        engine="ai",
    )

    logger.info(
        "AI analysis complete — category: %s, confidence: %s.",
        analysis.category,
        analysis.confidence,
    )

    return AIEngineResult(
        analysis=analysis,
        status=STATUS_SUCCESS,
        detail="AI analysis completed successfully.",
    )
