"""
report_generator.py - Generate a Markdown autoscaling report.

Writes (or appends to) reports/scaling-report.md, documenting every
scaling evaluation in a structured, human-readable format.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from metrics_parser import Metrics
from decision_engine import ScalingDecision


REPORT_DIR = Path(__file__).parent.parent / "reports"
REPORT_FILE = REPORT_DIR / "scaling-report.md"

# Map decision → markdown badge emoji
_BADGE = {
    "scale_up": "🔺 SCALE UP",
    "scale_down": "🔻 SCALE DOWN",
    "no_change": "✅ NO CHANGE",
}


def generate(
    metrics: Metrics,
    decision: ScalingDecision,
    source_file: str,
) -> Path:
    """
    Append a scaling evaluation section to the Markdown report.

    Args:
        metrics:     Parsed workload metrics.
        decision:    Output from the decision engine.
        source_file: Path of the input JSON file (for traceability).

    Returns:
        Path to the written report file.
    """
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Build the report section
    section = _render_section(metrics, decision, source_file)

    # Write header once if the file is brand-new
    if not REPORT_FILE.exists():
        header = _render_header()
        REPORT_FILE.write_text(header + section, encoding="utf-8")
    else:
        with REPORT_FILE.open("a", encoding="utf-8") as fh:
            fh.write(section)

    return REPORT_FILE


def reset() -> None:
    """Remove the existing report so a fresh run starts clean."""
    if REPORT_FILE.exists():
        REPORT_FILE.unlink()


def _render_header() -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return (
        "# Autoscaling Simulation Report\n\n"
        f"Generated: {now}\n\n"
        "---\n\n"
    )


def _render_section(
    m: Metrics,
    d: ScalingDecision,
    source_file: str,
) -> str:
    badge = _BADGE.get(d.decision, d.decision.upper())
    timestamp = m.timestamp or datetime.now(timezone.utc).isoformat()

    lines: List[str] = [
        f"## {badge} — `{m.service}` ({m.environment})\n",
        f"**Evaluated:** {timestamp}  ",
        f"**Source file:** `{source_file}`\n",
        "",
        "### Input Metrics\n",
        "| Metric | Value |",
        "| --- | --- |",
        f"| CPU Utilization | {m.cpu_utilization:.1f}% |",
        f"| Memory Utilization | {m.memory_utilization:.1f}% |",
        f"| Request Rate | {m.request_rate:.0f} req/min |",
        f"| Queue Depth | {m.queue_depth:,} items |",
        f"| Current Replicas | {m.current_replicas} |",
        f"| Avg Response Time | {m.avg_response_time_ms:.0f} ms |",
        f"| Error Rate | {m.error_rate * 100:.2f}% |",
        "",
        "### Decision\n",
        "| Field | Value |",
        "| --- | --- |",
        f"| **Decision** | `{d.decision}` |",
        f"| **Recommended Replicas** | {d.recommended_replicas} |",
        f"| **Change** | {m.current_replicas} -> {d.recommended_replicas} "
        f"({'+'if d.recommended_replicas >= m.current_replicas else ''}"
        f"{d.recommended_replicas - m.current_replicas}) |",
        "",
        f"**Reason:** {d.reason}\n",
        f"> **Risk Note:** {d.risk_note}\n",
        "",
        "**Signals fired:**",
    ]

    for sig in d.signals_fired:
        lines.append(f"- `{sig}`")

    lines += ["", "---\n"]
    return "\n".join(lines)
