"""
AI enrichment engine — optional enhancement layer using the Anthropic Claude API.

When ANTHROPIC_API_KEY is set in the environment, this engine sends the incident
details to Claude and returns enriched root-cause analysis and remediation advice.
Falls back gracefully to rule-based mode when the key is absent or the API call fails.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_CLIENT = None
_MODEL = "claude-haiku-4-5-20251001"  # fast, cost-effective for triage workloads


def _get_client():
    """Lazily initialise the Anthropic client; returns None if key is absent."""
    global _CLIENT
    if _CLIENT is not None:
        return _CLIENT

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic  # noqa: PLC0415 — intentionally deferred import
        _CLIENT = anthropic.Anthropic(api_key=api_key)
        logger.info("Anthropic client initialised — AI-enhanced mode active.")
    except ImportError:
        logger.warning("anthropic package not installed. Falling back to rule-based mode.")
        _CLIENT = None

    return _CLIENT


def is_available() -> bool:
    """Return True if the AI engine can be used for this request."""
    return _get_client() is not None


def enrich(source: str, environment: str, log: str, rule_category: str, rule_root_cause: str) -> Optional[dict]:
    """
    Call Claude to produce enriched incident analysis.

    Args:
        source: Service name that emitted the incident.
        environment: Deployment environment.
        log: Raw log message.
        rule_category: Category already detected by the rule engine.
        rule_root_cause: Root cause summary from the rule engine.

    Returns:
        dict with keys: root_cause, recommended_fix — or None on failure.
    """
    client = _get_client()
    if client is None:
        return None

    system_prompt = (
        "You are an expert Site Reliability Engineer specialising in incident triage. "
        "Analyse the provided incident details and return a concise JSON object with two keys:\n"
        "  - root_cause: a one-sentence technical explanation of what went wrong.\n"
        "  - recommended_fix: a one-sentence actionable remediation step.\n"
        "Be specific, technical, and operational. Do not include markdown or extra commentary."
    )

    user_message = (
        f"Service: {source}\n"
        f"Environment: {environment}\n"
        f"Log: {log}\n"
        f"Preliminary category (rule-based): {rule_category}\n"
        f"Preliminary root cause (rule-based): {rule_root_cause}\n\n"
        "Provide an enriched, technically precise JSON analysis."
    )

    try:
        response = client.messages.create(
            model=_MODEL,
            max_tokens=256,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()

        import json  # noqa: PLC0415
        # Strip potential markdown code fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)

        if "root_cause" in data and "recommended_fix" in data:
            return data

        logger.warning("AI response missing expected keys: %s", data)
        return None

    except Exception as exc:  # noqa: BLE001
        logger.warning("AI enrichment failed (%s). Falling back to rule-based mode.", exc)
        return None
