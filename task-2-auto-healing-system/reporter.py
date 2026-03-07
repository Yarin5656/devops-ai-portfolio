"""
reporter.py

Generates a Markdown healing report from detection results, prescriptions,
healing outcomes, and optional AI analyses.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List

from failure_detector import DetectionResult
from rule_engine import HealingPrescription
from healer import HealingOutcome
from ai_engine import AIAnalysis

logger = logging.getLogger(__name__)


def generate_report(
    log_path: str,
    detection: DetectionResult,
    prescriptions: List[HealingPrescription],
    outcomes: List[HealingOutcome],
    analyses: List[AIAnalysis],
    report_dir: str = "reports",
) -> str:
    """
    Generate a Markdown healing report and write it to report_dir.

    Args:
        log_path      : Path to the analysed log file.
        detection     : DetectionResult from failure_detector.
        prescriptions : List of HealingPrescription from rule_engine.
        outcomes      : List of HealingOutcome from healer (may be empty).
        analyses      : List of AIAnalysis from ai_engine (may be empty).
        report_dir    : Directory in which to write the report file.

    Returns:
        Absolute path to the generated report file.
    """
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = Path(log_path).stem
    out_path = Path(report_dir) / f"{stem}_healing_report_{ts}.md"

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: List[str] = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines += [
        f"# Auto-Healing Report — `{stem}`",
        "",
        f"**Generated:** {now_str}  ",
        f"**Log file:** `{log_path}`  ",
        f"**Total events detected:** {len(detection.events)}  ",
        f"**Highest severity:** `{detection.highest_severity.upper()}`  ",
        "",
        "---",
        "",
    ]

    # ── Summary table ─────────────────────────────────────────────────────────
    lines += [
        "## Failure Summary",
        "",
        "| # | Line | Failure Type | Severity | Service | Keyword Matched |",
        "|---|------|-------------|----------|---------|-----------------|",
    ]
    for i, event in enumerate(detection.events, start=1):
        lines.append(
            f"| {i} | {event.line_number} | `{event.failure_type}` "
            f"| **{event.severity}** | {event.service} | `{event.keyword_matched}` |"
        )
    lines += ["", "---", ""]

    # ── Per-prescription detail ───────────────────────────────────────────────
    lines += ["## Healing Actions", ""]

    outcomes_by_type = {o.prescription.failure_type: o for o in outcomes}
    analyses_by_type = {a.failure_type: a for a in analyses}

    for i, p in enumerate(prescriptions, start=1):
        outcome = outcomes_by_type.get(p.failure_type)
        analysis = analyses_by_type.get(p.failure_type)

        status_badge = (
            f"**{outcome.status}**" if outcome else "*Not executed*"
        )
        ai_badge = (
            "AI-powered" if (analysis and analysis.ai_powered)
            else ("rule-based" if analysis else "N/A")
        )

        lines += [
            f"### {i}. {p.failure_type.replace('_', ' ').title()}",
            "",
            f"| Field | Value |",
            f"|-------|-------|",
            f"| **Failure detected** | `{p.failure_type}` |",
            f"| **Service** | {p.service} |",
            f"| **Severity** | {p.severity} |",
            f"| **Classification** | {p.action_id} |",
            f"| **Healing action triggered** | {p.action_label} |",
            f"| **Status** | {status_badge} |",
            f"| **Analysis** | {ai_badge} |",
            "",
        ]

        # Log excerpt
        lines += [
            "**Log excerpt:**",
            "```",
            p.event.raw_line[:300],
            "```",
            "",
        ]

        # Healing steps taken
        if outcome and outcome.steps_taken:
            lines += ["**Healing steps executed:**", ""]
            for step in outcome.steps_taken:
                lines.append(f"- {step}")
            lines.append("")

        # AI analysis
        if analysis:
            lines += [
                f"**Root cause ({ai_badge}):**",
                "",
                f"> {analysis.root_cause_explanation}",
                "",
                "**Remediation steps:**",
                "",
            ]
            for step in analysis.remediation_steps:
                lines.append(f"- {step}")
            lines += [
                "",
                f"**Risk if unresolved:** {analysis.risk_assessment}",
                "",
            ]

        # Permanent fix
        lines += [
            "**Suggested permanent fix:**",
            "",
            f"> {p.permanent_fix}",
            "",
            "---",
            "",
        ]

    # ── Footer ────────────────────────────────────────────────────────────────
    healed_count = sum(1 for o in outcomes if o.success)
    lines += [
        "## Overall Status",
        "",
        f"- Failures detected   : {len(detection.events)}",
        f"- Unique failure types: {len(prescriptions)}",
        f"- Healing actions run : {len(outcomes)}",
        f"- Successfully healed : {healed_count}",
        "",
        "_Report generated by Auto-Healing DevOps System_",
        "",
    ]

    report_text = "\n".join(lines)
    out_path.write_text(report_text, encoding="utf-8")
    logger.info("Report written to %s", out_path)
    return str(out_path)
