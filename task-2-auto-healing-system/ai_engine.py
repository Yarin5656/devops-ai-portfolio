"""
ai_engine.py

Optional AI analysis layer using the Anthropic Claude API.
When enabled, generates a detailed root-cause explanation and remediation plan
for each detected failure. Falls back gracefully to rule-based output when the
API is unavailable or not configured.
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional
from rule_engine import HealingPrescription

logger = logging.getLogger(__name__)


@dataclass
class AIAnalysis:
    """
    Structured AI-generated analysis for a single failure event.
    """
    failure_type: str
    service: str
    root_cause_explanation: str
    remediation_steps: list[str]
    risk_assessment: str
    ai_powered: bool  # False when fallback text was used


def _build_prompt(p: HealingPrescription) -> str:
    """Construct the prompt sent to the Claude API."""
    log_context = p.event.raw_line[:500] if p.event.raw_line else "N/A"
    return (
        f"You are a senior Site Reliability Engineer.\n\n"
        f"A production system has experienced a failure. Analyse it and respond with:\n"
        f"1. Root cause explanation (2-3 sentences)\n"
        f"2. Immediate remediation steps (bullet points)\n"
        f"3. Risk assessment if left unaddressed (1 sentence)\n\n"
        f"Failure type   : {p.failure_type}\n"
        f"Affected service: {p.service}\n"
        f"Severity       : {p.severity}\n"
        f"Log excerpt    : {log_context}\n\n"
        f"Respond in plain text only. Use '##' to delimit each section."
    )


def _parse_claude_response(text: str, p: HealingPrescription) -> AIAnalysis:
    """Parse the free-text Claude response into an AIAnalysis structure."""
    sections = [s.strip() for s in text.split("##") if s.strip()]

    root_cause = sections[0] if len(sections) > 0 else "No root cause provided."
    remediation_raw = sections[1] if len(sections) > 1 else ""
    risk = sections[2] if len(sections) > 2 else "Risk unknown."

    # Split remediation block into individual steps
    steps = [
        line.lstrip("-•* ").strip()
        for line in remediation_raw.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not steps:
        steps = [remediation_raw.strip() or "No specific steps provided."]

    return AIAnalysis(
        failure_type=p.failure_type,
        service=p.service,
        root_cause_explanation=root_cause,
        remediation_steps=steps,
        risk_assessment=risk,
        ai_powered=True,
    )


def _fallback_analysis(p: HealingPrescription) -> AIAnalysis:
    """Return a rule-based analysis when the AI API is not available."""
    fallbacks: dict[str, dict] = {
        "service_crash": {
            "root_cause": (
                "The service process terminated unexpectedly, likely due to an unhandled "
                "exception, memory exhaustion, or an external signal. Crash dumps and "
                "application stderr should be inspected for the immediate trigger."
            ),
            "steps": [
                "Review application crash logs and core dumps.",
                "Check recent deployments for regressions.",
                "Restart the service under a process supervisor.",
                "Set resource limits to prevent cascading failures.",
            ],
            "risk": "Continued downtime and potential data loss if the service manages state.",
        },
        "memory_spike": {
            "root_cause": (
                "Available memory was exhausted, causing the OOM killer to terminate "
                "one or more processes. This is commonly caused by a memory leak, "
                "unexpected traffic surge, or misconfigured heap limits."
            ),
            "steps": [
                "Identify which process consumed excess memory via dmesg / /proc.",
                "Restart the container to immediately restore service.",
                "Set container memory limits and request appropriate values.",
                "Profile the application for memory leaks in the next release cycle.",
            ],
            "risk": "System instability and cascading failures across co-located services.",
        },
        "disk_full": {
            "root_cause": (
                "The filesystem reached 100% capacity, blocking all write operations. "
                "This is most commonly caused by unbounded log growth, large temporary "
                "files, or runaway database write activity."
            ),
            "steps": [
                "Immediately remove or compress old log files.",
                "Purge /tmp and application cache directories.",
                "Enable logrotate with sensible retention policies.",
                "Add disk-usage monitoring with alerts at 75% / 90%.",
            ],
            "risk": "Total write failures leading to service crashes and data corruption.",
        },
        "connection_refused": {
            "root_cause": (
                "A downstream dependency is not accepting connections, typically because "
                "the target service has crashed, has not started, or its port is blocked "
                "by a firewall rule or misconfiguration."
            ),
            "steps": [
                "Verify the dependency service is running and healthy.",
                "Check firewall rules and network policies.",
                "Restart the dependency service if it has crashed.",
                "Implement circuit breakers and retry logic in the client.",
            ],
            "risk": "Cascading failure across all services that depend on this component.",
        },
        "timeout": {
            "root_cause": (
                "Requests are exceeding configured time limits, usually caused by slow "
                "database queries, network latency, resource contention, or insufficient "
                "compute capacity to handle current load."
            ),
            "steps": [
                "Identify slow queries or API calls using APM tooling.",
                "Scale out instances to reduce per-node load.",
                "Add caching for expensive repeated operations.",
                "Review and tune timeout thresholds appropriately.",
            ],
            "risk": "Degraded user experience and potential request queue saturation.",
        },
    }

    fb = fallbacks.get(p.failure_type, {
        "root_cause": "Unknown failure type — manual investigation required.",
        "steps": ["Review logs manually.", "Escalate to the engineering team."],
        "risk": "Unknown — treat as high priority until root cause is confirmed.",
    })

    return AIAnalysis(
        failure_type=p.failure_type,
        service=p.service,
        root_cause_explanation=fb["root_cause"],
        remediation_steps=fb["steps"],
        risk_assessment=fb["risk"],
        ai_powered=False,
    )


def analyse(prescription: HealingPrescription) -> AIAnalysis:
    """
    Attempt an AI-powered analysis of the given prescription.

    Tries to import and call the Anthropic SDK. Falls back gracefully if the
    SDK is not installed or the API key is not set.

    Args:
        prescription: HealingPrescription from rule_engine.classify().

    Returns:
        AIAnalysis — AI-powered when available, rule-based otherwise.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        logger.warning(
            "ANTHROPIC_API_KEY not set — using rule-based fallback analysis."
        )
        return _fallback_analysis(prescription)

    try:
        import anthropic  # noqa: PLC0415 — intentional lazy import

        client = anthropic.Anthropic(api_key=api_key)
        prompt = _build_prompt(prescription)

        logger.info("Sending failure context to Claude API for analysis...")
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text
        logger.info("Claude API response received.")
        return _parse_claude_response(response_text, prescription)

    except ImportError:
        logger.warning("anthropic SDK not installed — using rule-based fallback.")
        return _fallback_analysis(prescription)
    except Exception as exc:  # noqa: BLE001
        logger.error("Claude API call failed: %s — using fallback.", exc)
        return _fallback_analysis(prescription)


def analyse_all(prescriptions: list[HealingPrescription]) -> list[AIAnalysis]:
    """
    Run AI (or fallback) analysis for every prescription.

    Args:
        prescriptions: List of HealingPrescription objects.

    Returns:
        List of AIAnalysis objects in the same order.
    """
    return [analyse(p) for p in prescriptions]
