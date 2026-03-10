"""
AI interface module.

Optionally enhances rule-based analysis using a language model.
Falls back gracefully to rule-based analysis when:
  - No API key is configured
  - The 'anthropic' package is not installed
  - An API call fails for any reason
"""

import os
import json
import logging
from typing import Optional

from schemas import Incident, AnalysisResult, AnalysisMode

logger = logging.getLogger(__name__)

_ANTHROPIC_AVAILABLE = False
try:
    import anthropic  # type: ignore
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    pass


def _build_prompt(incident: Incident, rule_result: AnalysisResult) -> str:
    incident_summary = {
        "title": incident.title,
        "description": incident.description,
        "service": incident.service,
        "environment": incident.environment,
        "timestamp": incident.timestamp,
        "recent_logs": incident.logs[-5:],
        "metrics": incident.metrics,
        "tags": incident.tags,
    }

    rule_summary = {
        "detected_categories": rule_result.detected_categories,
        "rule_based_root_cause": rule_result.root_cause,
        "rule_based_severity": rule_result.severity.value,
        "rule_based_fix": rule_result.recommended_fix,
    }

    return f"""You are an expert SRE and DevOps engineer analyzing a production incident.

Below is an incident report along with a preliminary rule-based analysis.
Provide additional expert insights, validate the rule-based findings, and suggest
any non-obvious remediation steps or patterns the rules may have missed.

## Incident Data
{json.dumps(incident_summary, indent=2)}

## Rule-Based Analysis
{json.dumps(rule_summary, indent=2)}

## Your Task
Respond with a single JSON object containing:
{{
  "validated_root_cause": "<concise expert root cause, 1-2 sentences>",
  "validated_severity": "<CRITICAL|HIGH|MEDIUM|LOW>",
  "expert_insights": "<2-3 sentence expert analysis adding context beyond the rules>",
  "additional_steps": ["<step 1>", "<step 2>", "<step 3>"]
}}

Respond ONLY with the JSON object. No markdown, no explanation outside the JSON.
"""


def _parse_ai_response(response_text: str) -> Optional[dict]:
    try:
        text = response_text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
        return json.loads(text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Failed to parse AI response as JSON: %s", exc)
        return None


def enhance_analysis(incident: Incident, rule_result: AnalysisResult) -> AnalysisResult:
    """
    Attempt to enhance the rule-based result with AI insights.
    Returns the original result unchanged if AI is unavailable or fails.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    if not api_key:
        logger.info("ANTHROPIC_API_KEY not set — using rule-based analysis only.")
        return rule_result

    if not _ANTHROPIC_AVAILABLE:
        logger.warning(
            "anthropic package not installed — using rule-based analysis only. "
            "Install with: pip install anthropic"
        )
        return rule_result

    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = _build_prompt(incident, rule_result)

        logger.info("Sending incident to Claude for enhanced analysis…")
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = message.content[0].text if message.content else ""
        parsed = _parse_ai_response(raw_text)

        if not parsed:
            logger.warning("AI returned unparseable response — keeping rule-based result.")
            return rule_result

        from schemas import Severity  # local import to avoid circular

        # Merge AI insights into the existing result
        ai_severity_str = parsed.get("validated_severity", rule_result.severity.value)
        try:
            ai_severity = Severity(ai_severity_str.upper())
        except ValueError:
            ai_severity = rule_result.severity

        additional_steps = parsed.get("additional_steps", [])
        merged_steps = list(rule_result.runbook_steps)
        if additional_steps:
            merged_steps.append("\n--- AI-Recommended Additional Steps ---")
            merged_steps.extend(additional_steps)

        return AnalysisResult(
            root_cause=parsed.get("validated_root_cause", rule_result.root_cause),
            severity=ai_severity,
            recommended_fix=rule_result.recommended_fix,
            runbook_steps=merged_steps,
            analysis_mode=AnalysisMode.AI_ENHANCED,
            detected_categories=rule_result.detected_categories,
            confidence_score=min(rule_result.confidence_score + 0.2, 1.0),
            ai_insights=parsed.get("expert_insights"),
        )

    except Exception as exc:  # pylint: disable=broad-except
        logger.warning("AI enhancement failed (%s) — falling back to rule-based analysis.", exc)
        return rule_result
