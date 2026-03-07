"""
main.py

AI DevOps Log Analyzer — CLI entry point.

Pipeline (always in this order):
  1. Parse   — read and index the log file
  2a. Rules  — deterministic pattern-matching (always runs)
  2b. AI     — Anthropic Claude enrichment (only with --ai flag)
  3. Summary — print condensed results to console
  4. Report  — write full Markdown report to reports/report.md

Usage:
    python main.py --log <path/to/logfile.log> [--ai] [--report-dir <dir>] [--verbose]
"""

import argparse
import logging
import sys

from log_parser import parse_log
from rule_engine import classify_and_analyse
from ai_engine import analyse_with_ai, STATUS_SUCCESS
from report_generator import generate_report


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _configure_logging(verbose: bool) -> None:
    """Configure root logger format and level."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """Construct and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="log-analyzer",
        description=(
            "AI DevOps Log Analyzer — parse infrastructure logs, classify errors, "
            "identify root causes, and generate Markdown diagnostic reports."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Rule-based analysis (no API key required):
  python main.py --log sample_logs/deploy_failure.log

  # AI-enhanced analysis (requires ANTHROPIC_API_KEY):
  python main.py --log sample_logs/deploy_failure.log --ai

  # Custom output directory + verbose logging:
  python main.py --log sample_logs/network_error.log --ai --report-dir /tmp/reports --verbose

Environment variables:
  ANTHROPIC_API_KEY   Anthropic API key. Required for --ai mode.
                      If absent, the tool falls back to rule-based analysis.
        """,
    )

    parser.add_argument(
        "--log",
        required=True,
        metavar="FILE",
        help="Path to the log file to analyse.",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        default=False,
        help=(
            "Enable AI-powered analysis via Anthropic Claude. "
            "Requires the ANTHROPIC_API_KEY environment variable and "
            "'pip install anthropic'. Falls back gracefully to rule-based "
            "analysis if the key is absent or the API call fails. "
            "Rule-based analysis always runs regardless of this flag."
        ),
    )
    parser.add_argument(
        "--report-dir",
        default="reports",
        metavar="DIR",
        help="Directory to write the Markdown report into (default: reports/).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable DEBUG-level logging.",
    )

    return parser


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_analysis(log_path: str, use_ai: bool, report_dir: str) -> int:
    """
    Execute the full analysis pipeline.

    Steps:
        1. Parse the log file.
        2a. Run the rule engine (always).
        2b. Run the AI engine (only if --ai and API key present).
        3. Print a summary to stdout.
        4. Write the Markdown report.

    Args:
        log_path:   Path to the log file.
        use_ai:     Whether the user passed --ai.
        report_dir: Directory to write the report into.

    Returns:
        0 on success, 1 on unrecoverable error.
    """
    logger = logging.getLogger(__name__)

    # ── Step 1: Parse ──────────────────────────────────────────────────────
    print(f"\n[1/4] Parsing log file: {log_path}")
    try:
        parsed = parse_log(log_path)
    except FileNotFoundError:
        print(f"  ERROR: Log file not found — '{log_path}'", file=sys.stderr)
        return 1
    except IOError as exc:
        print(f"  ERROR: Could not read log file — {exc}", file=sys.stderr)
        return 1

    print(
        f"      {parsed.total_lines} lines read, "
        f"{len(parsed.error_lines)} error line(s) detected, "
        f"{len(parsed.detected_indicators)} indicator(s) matched."
    )

    # ── Step 2a: Rule engine (always) ──────────────────────────────────────
    print("[2/4] Running rule-based analysis …")
    rule_result = classify_and_analyse(parsed)
    if rule_result:
        print(
            f"      Rule '{rule_result.matched_rule}' matched — "
            f"category: {rule_result.category}, confidence: {rule_result.confidence}."
        )
    else:
        print("      No rule matched the detected patterns.")

    # ── Step 2b: AI engine (optional) ──────────────────────────────────────
    ai_analysis = None
    ai_status = "not_requested"
    ai_detail = ""

    if use_ai:
        print("      Attempting AI-enhanced analysis …")
        rule_category = rule_result.category if rule_result else None
        ai_engine_result = analyse_with_ai(parsed, rule_category=rule_category)
        ai_analysis = ai_engine_result.analysis
        ai_status = ai_engine_result.status
        ai_detail = ai_engine_result.detail

        if ai_status == STATUS_SUCCESS:
            print(
                f"      AI analysis complete — "
                f"category: {ai_analysis.category}, confidence: {ai_analysis.confidence}."
            )
        else:
            print(f"      AI analysis unavailable ({ai_status}) — rule-based result is authoritative.")

    # ── Step 3: Console summary ────────────────────────────────────────────
    print("\n[3/4] Analysis summary")

    primary = rule_result  # rule engine is always the primary result
    if primary:
        print(f"  Category    : {primary.category}")
        print(f"  Rule engine : {primary.matched_rule} (confidence: {primary.confidence})")
        if ai_analysis:
            print(f"  AI engine   : {ai_analysis.model} (confidence: {ai_analysis.confidence})")
        elif use_ai:
            print(f"  AI engine   : unavailable ({ai_status})")
        root_preview = primary.root_cause[:120].replace("\n", " ")
        ellipsis = "…" if len(primary.root_cause) > 120 else ""
        print(f"  Root Cause  : {root_preview}{ellipsis}")
    else:
        print("  No errors detected in the log file.")

    # ── Step 4: Generate report ────────────────────────────────────────────
    print(f"\n[4/4] Generating report …")
    try:
        report_path = generate_report(
            log_path=log_path,
            parsed_log=parsed,
            rule_result=rule_result,
            ai_analysis=ai_analysis,
            ai_requested=use_ai,
            ai_status=ai_status,
            ai_detail=ai_detail,
            report_dir=report_dir,
        )
        print(f"  Report written to: {report_path}\n")
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Report generation failed: %s", exc)
        print(f"  ERROR: Could not write report — {exc}", file=sys.stderr)
        return 1

    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Parse CLI arguments and invoke the analysis pipeline."""
    parser = _build_parser()
    args = parser.parse_args()

    _configure_logging(args.verbose)

    print("=" * 60)
    print("  AI DevOps Log Analyzer")
    print("=" * 60)

    sys.exit(run_analysis(
        log_path=args.log,
        use_ai=args.ai,
        report_dir=args.report_dir,
    ))


if __name__ == "__main__":
    main()
