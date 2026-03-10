#!/usr/bin/env python3
"""
main.py - CLI entry point for the Autoscaling Simulation System.

Usage:
    python scaler/main.py --file sample_metrics/high_cpu.json
    python scaler/main.py --file sample_metrics/low_load.json
    python scaler/main.py --file sample_metrics/queue_spike.json [--reset-report]
"""

import argparse
import io
import sys
from pathlib import Path

# Force UTF-8 output on Windows consoles that default to legacy code pages
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Allow running as: python scaler/main.py (adds scaler/ to sys.path)
sys.path.insert(0, str(Path(__file__).parent))

import metrics_parser
import decision_engine
import report_generator


DECISION_COLORS = {
    "scale_up": "\033[91m",    # red
    "scale_down": "\033[93m",  # yellow
    "no_change": "\033[92m",   # green
}
RESET = "\033[0m"
BOLD = "\033[1m"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="scaler",
        description="Autoscaling Simulation System — evaluates workload metrics and recommends scaling actions.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scaler/main.py --file sample_metrics/high_cpu.json
  python scaler/main.py --file sample_metrics/low_load.json --reset-report
  python scaler/main.py --file sample_metrics/queue_spike.json
        """,
    )
    parser.add_argument(
        "--file",
        required=True,
        metavar="METRICS_FILE",
        help="Path to a JSON metrics file describing the current workload state.",
    )
    parser.add_argument(
        "--reset-report",
        action="store_true",
        default=False,
        help="Delete the existing scaling report before writing a new one.",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        default=False,
        help="Skip writing the Markdown report (dry-run mode).",
    )
    return parser.parse_args()


def print_banner() -> None:
    print(f"\n{BOLD}{'=' * 60}")
    print("  Autoscaling Simulation System")
    print(f"{'=' * 60}{RESET}\n")


def print_metrics(m: metrics_parser.Metrics) -> None:
    print(f"{BOLD}Service:{RESET}      {m.service} ({m.environment})")
    if m.timestamp:
        print(f"{BOLD}Timestamp:{RESET}    {m.timestamp}")
    print()
    print(f"{BOLD}--- Workload Metrics ---{RESET}")
    print(f"  CPU Utilization    : {m.cpu_utilization:.1f}%")
    print(f"  Memory Utilization : {m.memory_utilization:.1f}%")
    print(f"  Request Rate       : {m.request_rate:.0f} req/min")
    print(f"  Queue Depth        : {m.queue_depth:,} items")
    print(f"  Current Replicas   : {m.current_replicas}")
    print(f"  Avg Response Time  : {m.avg_response_time_ms:.0f} ms")
    print(f"  Error Rate         : {m.error_rate * 100:.2f}%")
    print()


def print_decision(d: decision_engine.ScalingDecision) -> None:
    color = DECISION_COLORS.get(d.decision, "")
    print(f"{BOLD}--- Scaling Decision ---{RESET}")
    print(f"  Decision           : {color}{BOLD}{d.decision.upper()}{RESET}")
    print(f"  Recommended Pods   : {d.recommended_replicas}")
    print()
    print(f"{BOLD}Reason:{RESET}")
    print(f"  {d.reason}")
    print()
    print(f"{BOLD}Risk Note:{RESET}")
    print(f"  {d.risk_note}")
    print()
    print(f"{BOLD}Signals Fired:{RESET}")
    for sig in d.signals_fired:
        print(f"  • {sig}")
    print()


def main() -> None:
    args = parse_args()
    print_banner()

    # --- Parse metrics ---
    print(f"Loading metrics from: {args.file}")
    m = metrics_parser.load(args.file)
    print_metrics(m)

    # --- Evaluate ---
    d = decision_engine.evaluate(m)
    print_decision(d)

    # --- Report ---
    if not args.no_report:
        if args.reset_report:
            report_generator.reset()
            print("  [INFO] Previous report cleared.")

        report_path = report_generator.generate(m, d, args.file)
        print(f"Report written to: {report_path}")
    else:
        print("  [INFO] Report generation skipped (--no-report).")

    print()


if __name__ == "__main__":
    main()
