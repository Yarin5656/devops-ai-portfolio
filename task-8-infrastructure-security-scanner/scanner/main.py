#!/usr/bin/env python3
"""
Infrastructure Security Scanner — main entry point.

Usage:
    python scanner/main.py --path sample_configs
    python scanner/main.py --path sample_configs --output reports/security-report.md
    python scanner/main.py --path sample_configs --severity HIGH
"""

import argparse
import sys
import os

# Allow running from the repo root or from inside scanner/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanner.parser import load_directory
from scanner.rules import (
    check_docker_compose,
    check_kubernetes,
    check_terraform,
    check_env_file,
    SEVERITY_ORDER,
)
from scanner.report_generator import generate_markdown


DEFAULT_REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "reports",
    "security-report.md",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="infra-security-scanner",
        description="Scan DevOps configuration files for security misconfigurations.",
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Path to a directory or single file to scan.",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_REPORT_PATH,
        help=f"Output path for the Markdown report (default: {DEFAULT_REPORT_PATH}).",
    )
    parser.add_argument(
        "--severity",
        choices=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        default=None,
        help="Only report findings at or above this severity level.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Print findings to stdout only; do not write a report file.",
    )
    return parser.parse_args()


def run_rules(parsed_files) -> list[dict]:
    """Dispatch each parsed file to the appropriate rule set."""
    all_findings: list[dict] = []

    for pf in parsed_files:
        findings: list[dict] = []

        if pf.file_type == "docker-compose":
            findings = check_docker_compose(pf.data or {}, pf.filepath)
        elif pf.file_type == "kubernetes":
            findings = check_kubernetes(pf.data or {}, pf.filepath)
        elif pf.file_type == "terraform":
            findings = check_terraform(pf.raw, pf.filepath)
        elif pf.file_type == "env":
            findings = check_env_file(pf.raw, pf.filepath)

        all_findings.extend(findings)

    return all_findings


def filter_by_severity(findings: list[dict], min_severity: str) -> list[dict]:
    threshold = SEVERITY_ORDER.get(min_severity, 99)
    return [f for f in findings if SEVERITY_ORDER.get(f.get("severity", "LOW"), 99) <= threshold]


def print_summary(findings: list[dict]) -> None:
    from collections import Counter
    counts = Counter(f["severity"] for f in findings)

    print("\n" + "=" * 60)
    print("  SECURITY SCAN SUMMARY")
    print("=" * 60)
    print(f"  Total findings : {len(findings)}")
    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        print(f"  {sev:<10}: {counts.get(sev, 0)}")
    print("=" * 60)

    if findings:
        print("\nTop findings:")
        for idx, f in enumerate(
            sorted(findings, key=lambda x: SEVERITY_ORDER.get(x.get("severity", "LOW"), 99)), start=1
        ):
            print(f"  [{f['severity']:8}] {f['title']}")
            print(f"             File: {f['file']}")
            if idx >= 10:
                remaining = len(findings) - 10
                if remaining > 0:
                    print(f"\n  ... and {remaining} more finding(s). See the full report.")
                break
    print()


def main() -> int:
    args = parse_args()

    # Resolve scan path relative to cwd or absolute
    scan_path = os.path.abspath(args.path)

    print(f"\nInfrastructure Security Scanner")
    print(f"================================")
    print(f"Scanning: {scan_path}\n")

    # Step 1: Load files
    try:
        parsed_files = load_directory(scan_path)
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if not parsed_files:
        print("[WARN] No supported configuration files found.")
        return 0

    print(f"\nLoaded {len(parsed_files)} file(s). Running security checks...\n")

    # Step 2: Run rules
    findings = run_rules(parsed_files)

    # Step 3: Filter by severity if requested
    if args.severity:
        findings = filter_by_severity(findings, args.severity)

    # Step 4: Print summary
    print_summary(findings)

    # Step 5: Write report
    if not args.no_report:
        report_path = generate_markdown(findings, args.output, scan_path)
        print(f"Report written to: {report_path}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
