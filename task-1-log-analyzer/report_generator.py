"""
report_generator.py

Generates a structured Markdown diagnostic report from the combined
outputs of the log parser, rule engine, and optional AI engine.

Report structure
----------------
  Header          — log metadata table
  Summary         — severity, category, engines used
  Detected Error  — primary error line + context block
  ── Rule-Based Analysis ──
    Root Cause | Impact | Suggested Fixes
  ── AI-Enhanced Analysis ──  (if --ai was passed)
    Root Cause | Impact | Recommended Checks | Suggested Fixes
    — OR — fallback note explaining why AI is unavailable
  Evidence Lines  — all matched error lines
  Footer

The two analysis sections are kept deliberately separate so the reader
can compare the deterministic rule output against the LLM interpretation.
"""

import logging
import os
from datetime import datetime, timezone
from typing import List, Optional

from log_parser import ParsedLog
from rule_engine import RuleMatch
from ai_engine import AIAnalysis, STATUS_SUCCESS

logger = logging.getLogger(__name__)

DEFAULT_REPORT_DIR = "reports"
DEFAULT_REPORT_NAME = "report.md"

_SEVERITY_MAP = {
    "permissions": "HIGH",
    "network": "HIGH",
    "dependency": "MEDIUM",
    "configuration": "MEDIUM",
    "infrastructure": "HIGH",
}


# ---------------------------------------------------------------------------
# Small formatting helpers
# ---------------------------------------------------------------------------

def _severity(category: str) -> str:
    """Map a category name to a severity label."""
    return _SEVERITY_MAP.get(category.lower(), "UNKNOWN")


def _fmt_code_block(lines: List[str]) -> str:
    """Wrap a list of strings in a fenced Markdown code block."""
    if not lines:
        return "_No content available._\n"
    return "```\n" + "\n".join(lines) + "\n```\n"


def _fmt_numbered_list(items: List[str]) -> str:
    """Render a list of strings as a Markdown numbered list."""
    if not items:
        return "_None._\n"
    return "\n".join(f"{i}. {item}" for i, item in enumerate(items, 1)) + "\n"


def _fmt_evidence(error_lines: List[tuple], max_lines: int = 10) -> str:
    """
    Format matched error lines as an annotated fenced code block.

    Args:
        error_lines: List of (line_number, line_text) tuples.
        max_lines: Maximum lines to include before truncating.

    Returns:
        Markdown-formatted string.
    """
    if not error_lines:
        return "_No error lines captured._\n"

    sample = error_lines[:max_lines]
    body = "\n".join(f"  {lineno:>6} | {text}" for lineno, text in sample)
    omitted = len(error_lines) - len(sample)
    tail = f"\n  ... ({omitted} more lines omitted)" if omitted else ""
    return f"```\n{body}{tail}\n```\n"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _section_header(parsed_log: ParsedLog, log_path: str, now: str) -> List[str]:
    """Build the report header metadata table."""
    log_name = os.path.basename(log_path)
    return [
        "# AI DevOps Log Analyzer — Diagnostic Report",
        "",
        "| Field            | Value |",
        "|------------------|-------|",
        f"| **Log File**     | `{log_name}` |",
        f"| **Generated**    | {now} |",
        f"| **Total Lines**  | {parsed_log.total_lines} |",
        f"| **Error Lines**  | {len(parsed_log.error_lines)} |",
        "",
        "---",
        "",
    ]


def _section_summary(
    parsed_log: ParsedLog,
    rule_result: Optional[RuleMatch],
    ai_analysis: Optional[AIAnalysis],
    ai_requested: bool,
) -> List[str]:
    """Build the summary table showing both engines' status at a glance."""
    category = (rule_result.category if rule_result else "unknown")
    sev = _severity(category)

    indicator_list = (
        ", ".join(f"`{i}`" for i in parsed_log.detected_indicators)
        if parsed_log.detected_indicators
        else "_none_"
    )

    rule_label = (
        f"`{rule_result.matched_rule}` (confidence: `{rule_result.confidence}`)"
        if rule_result
        else "_no rule matched_"
    )

    if not ai_requested:
        ai_label = "_not requested (omit `--ai` flag to suppress this row)_"
    elif ai_analysis:
        ai_label = f"Claude / `{ai_analysis.model}` (confidence: `{ai_analysis.confidence}`)"
    else:
        ai_label = "_unavailable — see AI section for details_"

    return [
        "## Summary",
        "",
        "| Field               | Value |",
        "|---------------------|-------|",
        f"| **Severity**        | {sev} |",
        f"| **Category**        | `{category}` |",
        f"| **Indicators**      | {indicator_list} |",
        f"| **Rule Engine**     | {rule_label} |",
        f"| **AI Engine**       | {ai_label} |",
        "",
        "---",
        "",
    ]


def _section_detected_error(parsed_log: ParsedLog) -> List[str]:
    """Build the detected error + context block section."""
    out = ["## Detected Error", ""]

    if parsed_log.primary_error_line:
        out += [
            f"**Primary error — line {parsed_log.primary_error_lineno}:**",
            "",
            "```",
            parsed_log.primary_error_line,
            "```",
            "",
        ]
    else:
        out += ["_Primary error line could not be isolated._", ""]

    out += [
        "**Context block (± 5 lines):**",
        "",
        _fmt_code_block(parsed_log.primary_error_block),
        "---",
        "",
    ]
    return out


def _section_rule_analysis(rule_result: Optional[RuleMatch]) -> List[str]:
    """
    Build the Rule-Based Analysis section.

    Always rendered — if no rule matched, shows a clear note instead of
    leaving the section empty.
    """
    out = [
        "## Rule-Based Analysis",
        "",
        "> _Deterministic pattern matching. Always runs regardless of `--ai` flag._",
        "",
    ]

    if rule_result is None:
        out += [
            "_No rule matched the detected error patterns. "
            "The log may contain an unknown error type. "
            "Manual investigation recommended._",
            "",
            "---",
            "",
        ]
        return out

    out += [
        f"**Matched rule:** `{rule_result.matched_rule}` &nbsp;|&nbsp; "
        f"**Category:** `{rule_result.category}` &nbsp;|&nbsp; "
        f"**Confidence:** `{rule_result.confidence}`",
        "",
        "### Root Cause",
        "",
        rule_result.root_cause,
        "",
        "### Impact",
        "",
        rule_result.impact,
        "",
        "### Suggested Fixes",
        "",
        _fmt_numbered_list(rule_result.suggested_fixes),
        "---",
        "",
    ]
    return out


def _section_ai_analysis(
    ai_analysis: Optional[AIAnalysis],
    ai_requested: bool,
    ai_status: str,
    ai_detail: str,
) -> List[str]:
    """
    Build the AI-Enhanced Analysis section.

    Three cases:
    1. --ai not passed → section omitted entirely.
    2. --ai passed, AI succeeded → full analysis rendered.
    3. --ai passed, AI failed → fallback note rendered.
    """
    if not ai_requested:
        return []

    out = [
        "## AI-Enhanced Analysis",
        "",
        "> _Powered by Anthropic Claude. Runs only when `--ai` flag is passed "
        "and `ANTHROPIC_API_KEY` is set._",
        "",
    ]

    if ai_analysis is None:
        # Fallback note
        out += [
            "### Status: Unavailable",
            "",
            f"> **{ai_detail}**",
            "",
            "The rule-based analysis above is the authoritative result for this report.",
            "",
            "---",
            "",
        ]
        return out

    out += [
        f"**Model:** `{ai_analysis.model}` &nbsp;|&nbsp; "
        f"**Category:** `{ai_analysis.category}` &nbsp;|&nbsp; "
        f"**Confidence:** `{ai_analysis.confidence}`",
        "",
        "### Root Cause",
        "",
        ai_analysis.root_cause,
        "",
        "### Impact",
        "",
        ai_analysis.impact,
        "",
        "### Recommended Checks",
        "",
        "_Run these diagnostic commands before applying fixes:_",
        "",
        _fmt_numbered_list(ai_analysis.recommended_checks),
        "### Suggested Fixes",
        "",
        _fmt_numbered_list(ai_analysis.suggested_fixes),
        "---",
        "",
    ]
    return out


def _section_evidence(parsed_log: ParsedLog) -> List[str]:
    """Build the evidence lines section."""
    return [
        "## Evidence Lines",
        "",
        "_All log lines that matched a known error indicator:_",
        "",
        _fmt_evidence(parsed_log.error_lines),
        "---",
        "",
    ]


def _section_footer() -> List[str]:
    """Build the report footer."""
    return [
        "_Report generated by **AI DevOps Log Analyzer**. "
        "Rule-based analysis is always the authoritative result. "
        "AI analysis is supplementary and should be validated by an engineer._",
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_report(
    log_path: str,
    parsed_log: ParsedLog,
    rule_result: Optional[RuleMatch],
    ai_analysis: Optional[AIAnalysis] = None,
    ai_requested: bool = False,
    ai_status: str = "not_requested",
    ai_detail: str = "",
) -> str:
    """
    Compose the full Markdown diagnostic report as a string.

    Args:
        log_path:     Path to the original log file (used for filename display).
        parsed_log:   Structured output from log_parser.parse_log().
        rule_result:  Output from rule_engine.classify_and_analyse(), or None.
        ai_analysis:  AIAnalysis from ai_engine.analyse_with_ai(), or None.
        ai_requested: True if --ai flag was passed by the user.
        ai_status:    Status string from AIEngineResult (for fallback notes).
        ai_detail:    Human-readable fallback message from AIEngineResult.

    Returns:
        Complete Markdown report as a string.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    sections: List[List[str]] = [
        _section_header(parsed_log, log_path, now),
    ]

    # Short-circuit: no errors at all
    if rule_result is None and not parsed_log.error_lines:
        sections.append([
            "## Status",
            "",
            "> **No errors detected.** "
            "The log file contains no known error indicators.",
            "",
            "No further action is required based on automated analysis.",
        ])
        return "\n".join(line for section in sections for line in section)

    sections += [
        _section_summary(parsed_log, rule_result, ai_analysis, ai_requested),
        _section_detected_error(parsed_log),
        _section_rule_analysis(rule_result),
        _section_ai_analysis(ai_analysis, ai_requested, ai_status, ai_detail),
        _section_evidence(parsed_log),
        _section_footer(),
    ]

    return "\n".join(line for section in sections for line in section)


def write_report(
    content: str,
    report_dir: str = DEFAULT_REPORT_DIR,
    report_name: str = DEFAULT_REPORT_NAME,
) -> str:
    """
    Write the report Markdown to disk, creating the directory if needed.

    Args:
        content:     Markdown string to write.
        report_dir:  Target directory (created if absent).
        report_name: Filename for the report.

    Returns:
        Path to the written report file.
    """
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, report_name)

    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write(content)

    logger.info("Report written to: %s", report_path)
    return report_path


def generate_report(
    log_path: str,
    parsed_log: ParsedLog,
    rule_result: Optional[RuleMatch],
    ai_analysis: Optional[AIAnalysis] = None,
    ai_requested: bool = False,
    ai_status: str = "not_requested",
    ai_detail: str = "",
    report_dir: str = DEFAULT_REPORT_DIR,
) -> str:
    """
    End-to-end report pipeline: build content and write to disk.

    Args:
        log_path:     Path to the original log file.
        parsed_log:   Parsed log data.
        rule_result:  Rule engine output.
        ai_analysis:  AI engine output (None if unavailable or not requested).
        ai_requested: Whether the user passed --ai.
        ai_status:    AI engine status code.
        ai_detail:    AI engine fallback message.
        report_dir:   Output directory.

    Returns:
        Path to the generated report file.
    """
    logger.info("Generating diagnostic report …")
    content = build_report(
        log_path=log_path,
        parsed_log=parsed_log,
        rule_result=rule_result,
        ai_analysis=ai_analysis,
        ai_requested=ai_requested,
        ai_status=ai_status,
        ai_detail=ai_detail,
    )
    return write_report(content, report_dir=report_dir)
