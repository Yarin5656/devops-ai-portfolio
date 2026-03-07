"""
main.py

CLI entry point for the Auto-Healing DevOps System.

Usage:
    python main.py --log sample_logs/service_crash.log
    python main.py --log sample_logs/disk_full.log --ai
    python main.py --log sample_logs/memory_spike.log --ai --no-heal
"""

import argparse
import io
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure stdout/stderr handle UTF-8 on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import failure_detector
import rule_engine
import healer
import ai_engine
from reporter import generate_report


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%H:%M:%S",
        level=level,
    )


def _banner() -> None:
    print("=" * 60)
    print("   Auto-Healing DevOps System")
    print("   Failure Detection + Simulated Recovery")
    print("=" * 60)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detect failures in a log file and trigger simulated healing actions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python main.py --log sample_logs/service_crash.log\n"
            "  python main.py --log sample_logs/disk_full.log --ai\n"
            "  python main.py --log sample_logs/memory_spike.log --ai --verbose\n"
        ),
    )
    parser.add_argument(
        "--log",
        required=True,
        metavar="PATH",
        help="Path to the log file to analyse.",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        default=False,
        help="Enable AI-powered root-cause analysis via the Claude API.",
    )
    parser.add_argument(
        "--no-heal",
        action="store_true",
        default=False,
        help="Detect and classify failures but skip simulated healing.",
    )
    parser.add_argument(
        "--report-dir",
        default="reports",
        metavar="DIR",
        help="Directory to write the Markdown healing report (default: reports/).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Enable debug-level logging.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    _setup_logging(args.verbose)
    _banner()

    log_path = args.log
    if not os.path.isfile(log_path):
        print(f"\n[ERROR] Log file not found: {log_path}")
        return 1

    # ── 1. Detect failures ────────────────────────────────────────────────────
    print(f"\n[1/4] Scanning log file: {log_path}")
    detection = failure_detector.detect_failures(log_path)

    if not detection.has_failures:
        print("\n  No failures detected. System appears healthy.")
        _write_clean_report(args.report_dir, log_path)
        return 0

    print(f"\n  {detection.summary()}")
    print(f"  Highest severity: {detection.highest_severity.upper()}")
    for event in detection.events:
        print(f"    {event}")

    # ── 2. Classify failures ──────────────────────────────────────────────────
    print("\n[2/4] Classifying failures via rule engine...")
    prescriptions = rule_engine.classify_all(detection)
    for p in prescriptions:
        print(f"  {p.failure_type:25s} -> {p.action_label}")

    # ── 3. AI analysis (optional) ─────────────────────────────────────────────
    analyses = []
    if args.ai:
        print("\n[3/4] Running AI analysis...")
        analyses = ai_engine.analyse_all(prescriptions)
        for a in analyses:
            tag = "AI" if a.ai_powered else "rule-based"
            print(f"\n  [{tag}] {a.failure_type} on '{a.service}'")
            print(f"  Root cause: {a.root_cause_explanation}")
            print("  Remediation steps:")
            for step in a.remediation_steps:
                print(f"    - {step}")
            print(f"  Risk: {a.risk_assessment}")
    else:
        print("\n[3/4] AI analysis skipped (use --ai to enable).")

    # ── 4. Simulated healing ──────────────────────────────────────────────────
    outcomes = []
    if not args.no_heal:
        print("\n[4/4] Triggering simulated healing actions...")
        outcomes = healer.heal_all(prescriptions)
        print()
        for outcome in outcomes:
            status_icon = "OK" if outcome.success else "FAIL"
            print(f"  [{status_icon}] {outcome.prescription.failure_type}: {outcome.status}")
    else:
        print("\n[4/4] Healing skipped (--no-heal flag set).")

    # ── Report generation ─────────────────────────────────────────────────────
    report_path = generate_report(
        log_path=log_path,
        detection=detection,
        prescriptions=prescriptions,
        outcomes=outcomes,
        analyses=analyses,
        report_dir=args.report_dir,
    )
    print(f"\n  Healing report written to: {report_path}")
    print("\n" + "=" * 60)
    print("  Auto-healing sequence complete.")
    print("=" * 60 + "\n")
    return 0


def _write_clean_report(report_dir: str, log_path: str) -> None:
    """Write a minimal 'no failures' report."""
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = Path(log_path).stem
    out = Path(report_dir) / f"{name}_clean_{ts}.md"
    out.write_text(
        f"# Healing Report — {name}\n\n"
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n"
        f"**Log file:** `{log_path}`\n\n"
        "## Result\n\nNo failures detected. System is healthy.\n",
        encoding="utf-8",
    )
    print(f"\n  Clean report written to: {out}")


if __name__ == "__main__":
    sys.exit(main())
