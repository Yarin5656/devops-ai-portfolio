"""
decision_engine.py - Rule-based autoscaling decision engine.

Evaluates multi-signal workload metrics and produces a scaling decision
with a recommended replica count, human-readable reason, and risk note.

Scaling philosophy:
  - Never rely on a single signal. Corroborate across CPU, memory,
    request rate, queue depth, response time, and error rate.
  - Prefer conservative scale-down over aggressive trim.
  - Respect minimum and maximum replica safety bounds.
  - Emit risk notes whenever a decision carries elevated uncertainty.
"""

import math
from dataclasses import dataclass
from typing import List

from metrics_parser import Metrics


# ---------------------------------------------------------------------------
# Thresholds — centralised so they are easy to override or externalise later
# ---------------------------------------------------------------------------

# Scale-up thresholds
CPU_HIGH = 80.0          # %
CPU_CRITICAL = 90.0      # %
MEM_HIGH = 80.0          # %
MEM_CRITICAL = 90.0      # %
RPS_HIGH = 800.0         # requests/min (or per sample window)
QUEUE_HIGH = 500         # items
QUEUE_CRITICAL = 2000    # items
RESPONSE_HIGH_MS = 2000  # ms
ERROR_RATE_HIGH = 0.05   # 5 %

# Scale-down thresholds
CPU_LOW = 25.0
MEM_LOW = 35.0
RPS_LOW = 100.0
QUEUE_LOW = 10

# Replica safety bounds
MIN_REPLICAS = 1
MAX_REPLICAS = 50


# ---------------------------------------------------------------------------
# Output type
# ---------------------------------------------------------------------------

@dataclass
class ScalingDecision:
    decision: str               # "scale_up" | "scale_down" | "no_change"
    recommended_replicas: int
    reason: str
    risk_note: str
    signals_fired: List[str]    # which rules contributed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate(metrics: Metrics) -> ScalingDecision:
    """
    Evaluate workload metrics and return a scaling decision.

    The engine runs three ordered phases:
      1. Emergency scale-up   — single critical signal sufficient
      2. Compound scale-up    — two or more elevated signals
      3. Scale-down           — sustained low utilisation across signals
      4. No-change            — stable workload; hold current replicas
    """

    signals = _collect_signals(metrics)
    up_signals = [s for s in signals if s.startswith("UP")]
    down_signals = [s for s in signals if s.startswith("DOWN")]

    # --- Phase 1: Emergency / critical scale-up ---
    critical_signals = [s for s in up_signals if "CRITICAL" in s]
    if critical_signals:
        factor = 2.0 if len(critical_signals) >= 2 else 1.75
        replicas = _clamp(math.ceil(metrics.current_replicas * factor))
        return ScalingDecision(
            decision="scale_up",
            recommended_replicas=replicas,
            reason=(
                f"Critical threshold breached: {_fmt(critical_signals)}. "
                f"Aggressive scale-up from {metrics.current_replicas} -> {replicas} replicas."
            ),
            risk_note=(
                "Rapid scale-up may cause thundering-herd if upstream dependencies "
                "cannot absorb the new traffic distribution. Monitor error rates."
            ),
            signals_fired=critical_signals,
        )

    # --- Phase 2: Compound scale-up (two+ elevated signals) ---
    if len(up_signals) >= 2:
        factor = _scale_up_factor(len(up_signals))
        replicas = _clamp(math.ceil(metrics.current_replicas * factor))
        return ScalingDecision(
            decision="scale_up",
            recommended_replicas=replicas,
            reason=(
                f"Multiple elevated signals detected: {_fmt(up_signals)}. "
                f"Scale-up from {metrics.current_replicas} -> {replicas} replicas."
            ),
            risk_note=(
                "Verify that the cluster has sufficient node capacity before "
                "applying this recommendation. Consider a PodDisruptionBudget."
            ),
            signals_fired=up_signals,
        )

    # --- Single elevated signal: cautious scale-up ---
    if len(up_signals) == 1:
        replicas = _clamp(math.ceil(metrics.current_replicas * 1.25))
        return ScalingDecision(
            decision="scale_up",
            recommended_replicas=replicas,
            reason=(
                f"Elevated signal: {_fmt(up_signals)}. "
                f"Cautious scale-up from {metrics.current_replicas} -> {replicas} replicas."
            ),
            risk_note=(
                "Single-signal decision carries more uncertainty. "
                "Confirm the trend persists before applying."
            ),
            signals_fired=up_signals,
        )

    # --- Phase 3: Scale-down ---
    if len(down_signals) >= 2 and not up_signals:
        # require at least two low signals to avoid premature trim
        factor = 0.5 if len(down_signals) >= 3 else 0.65
        replicas = _clamp(math.floor(metrics.current_replicas * factor))
        return ScalingDecision(
            decision="scale_down",
            recommended_replicas=replicas,
            reason=(
                f"Sustained low utilisation: {_fmt(down_signals)}. "
                f"Scale-down from {metrics.current_replicas} -> {replicas} replicas."
            ),
            risk_note=(
                "Ensure a cooldown period has elapsed since the last scale event. "
                "Avoid trimming below minimum SLA-required capacity."
            ),
            signals_fired=down_signals,
        )

    # --- Phase 4: No-change ---
    all_signals = up_signals + down_signals
    return ScalingDecision(
        decision="no_change",
        recommended_replicas=metrics.current_replicas,
        reason=(
            "All metrics are within acceptable operating bounds. "
            f"Maintaining current replica count: {metrics.current_replicas}."
        ),
        risk_note=(
            "Continue monitoring. A sudden spike may require immediate intervention "
            "if autoscaler reaction lag is non-trivial."
        ),
        signals_fired=all_signals if all_signals else ["NONE"],
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _collect_signals(m: Metrics) -> List[str]:
    """
    Return a list of named signals that describe the current metric state.

    Each signal is prefixed with UP (scale-up pressure) or DOWN (scale-down
    candidate). CRITICAL suffix indicates a single-signal emergency.
    """
    signals: List[str] = []

    # --- CPU ---
    if m.cpu_utilization >= CPU_CRITICAL:
        signals.append("UP:CPU_CRITICAL")
    elif m.cpu_utilization >= CPU_HIGH:
        signals.append("UP:CPU_HIGH")
    elif m.cpu_utilization < CPU_LOW:
        signals.append("DOWN:CPU_LOW")

    # --- Memory ---
    if m.memory_utilization >= MEM_CRITICAL:
        signals.append("UP:MEM_CRITICAL")
    elif m.memory_utilization >= MEM_HIGH:
        signals.append("UP:MEM_HIGH")
    elif m.memory_utilization < MEM_LOW:
        signals.append("DOWN:MEM_LOW")

    # --- Request rate ---
    if m.request_rate >= RPS_HIGH:
        signals.append("UP:RPS_HIGH")
    elif m.request_rate < RPS_LOW:
        signals.append("DOWN:RPS_LOW")

    # --- Queue depth ---
    if m.queue_depth >= QUEUE_CRITICAL:
        signals.append("UP:QUEUE_CRITICAL")
    elif m.queue_depth >= QUEUE_HIGH:
        signals.append("UP:QUEUE_HIGH")
    elif m.queue_depth < QUEUE_LOW:
        signals.append("DOWN:QUEUE_LOW")

    # --- Response time ---
    if m.avg_response_time_ms >= RESPONSE_HIGH_MS:
        signals.append("UP:LATENCY_HIGH")

    # --- Error rate ---
    if m.error_rate >= ERROR_RATE_HIGH:
        signals.append("UP:ERROR_RATE_HIGH")

    return signals


def _scale_up_factor(signal_count: int) -> float:
    """Return a scale-up multiplier based on the number of active up-signals."""
    return min(1.5 + (signal_count - 2) * 0.15, 2.0)


def _clamp(replicas: int) -> int:
    """Enforce absolute min/max replica bounds."""
    return max(MIN_REPLICAS, min(MAX_REPLICAS, replicas))


def _fmt(signals: List[str]) -> str:
    """Format a list of signal codes for human-readable output."""
    cleaned = [s.replace("UP:", "").replace("DOWN:", "") for s in signals]
    return ", ".join(cleaned)
