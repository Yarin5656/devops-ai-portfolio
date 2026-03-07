"""
healer.py

Simulates healing actions for each HealingPrescription.
No real system commands are executed — all actions are safe simulations.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List
from rule_engine import HealingPrescription

logger = logging.getLogger(__name__)

# Simulated latency (seconds) per action to make output feel realistic
_ACTION_DELAY: float = 0.4


@dataclass
class HealingOutcome:
    """Records the simulated result of applying a HealingPrescription."""
    prescription: HealingPrescription
    success: bool
    steps_taken: List[str] = field(default_factory=list)
    status_message: str = ""

    @property
    def status(self) -> str:
        return "HEALED" if self.success else "FAILED"


# Dispatch table: action_id → simulation function
def _restart_service(p: HealingPrescription) -> HealingOutcome:
    svc = p.service if p.service != "unknown" else "target-service"
    steps = [
        f"Sending SIGTERM to {svc} process...",
        f"Waiting for {svc} to shut down gracefully...",
        f"Starting {svc} via service manager...",
        f"{svc} is back online — health check passed.",
    ]
    return _simulate(p, steps)


def _restart_container(p: HealingPrescription) -> HealingOutcome:
    svc = p.service if p.service != "unknown" else "app-container"
    steps = [
        f"Inspecting container '{svc}' resource usage...",
        f"Stopping container '{svc}'...",
        f"Pruning container '{svc}'...",
        f"Pulling latest image for '{svc}'...",
        f"Starting new container '{svc}' with updated memory limits...",
        f"Container '{svc}' healthy — memory usage nominal.",
    ]
    return _simulate(p, steps)


def _run_cleanup(p: HealingPrescription) -> HealingOutcome:
    steps = [
        "Scanning /var/log for files older than 7 days...",
        "Found 2.3 GB of rotatable log files.",
        "Compressing and archiving old logs to /var/log/archive/...",
        "Purging /tmp and application temp directories...",
        "Reclaimed ~3.1 GB of disk space.",
        "Disk usage now at 61% — within safe threshold.",
    ]
    return _simulate(p, steps)


def _restart_dependency(p: HealingPrescription) -> HealingOutcome:
    svc = p.service if p.service != "unknown" else "dependency-service"
    steps = [
        f"Detecting which dependency '{svc}' is refusing connections...",
        f"Stopping dependency service '{svc}'...",
        f"Clearing stale PID file and socket...",
        f"Starting dependency service '{svc}'...",
        f"Verifying TCP connectivity on dependency port...",
        f"Dependency '{svc}' accepting connections — clients reconnecting.",
    ]
    return _simulate(p, steps)


def _scale_out(p: HealingPrescription) -> HealingOutcome:
    steps = [
        "Querying current replica count...",
        "Current replicas: 2 — scaling to 4.",
        "Provisioning 2 additional instances...",
        "Draining existing connection pools...",
        "Load balancer updated — traffic distributed across 4 instances.",
        "Response times returning to baseline.",
    ]
    return _simulate(p, steps)


def _notify_oncall(p: HealingPrescription) -> HealingOutcome:
    steps = [
        "Composing incident alert...",
        "Dispatching PagerDuty alert to on-call engineer...",
        "Creating incident ticket in tracking system...",
        "Alert acknowledged — engineer notified.",
    ]
    return _simulate(p, steps)


def _simulate(p: HealingPrescription, steps: List[str]) -> HealingOutcome:
    """Run a list of simulation steps with logging and optional delay."""
    for step in steps:
        logger.info("  [healer] %s", step)
        print(f"    > {step}")
        time.sleep(_ACTION_DELAY)
    return HealingOutcome(
        prescription=p,
        success=True,
        steps_taken=steps,
        status_message=f"Action '{p.action_id}' completed successfully (simulated).",
    )


_DISPATCH = {
    "restart_service":    _restart_service,
    "restart_container":  _restart_container,
    "run_cleanup":        _run_cleanup,
    "restart_dependency": _restart_dependency,
    "scale_out":          _scale_out,
    "notify_oncall":      _notify_oncall,
}


def heal(prescription: HealingPrescription) -> HealingOutcome:
    """
    Execute the simulated healing action for a given prescription.

    Args:
        prescription: A HealingPrescription from rule_engine.classify().

    Returns:
        HealingOutcome describing what steps were taken and whether it succeeded.
    """
    handler = _DISPATCH.get(prescription.action_id)
    if handler is None:
        logger.warning("No handler for action '%s' — falling back to notify.", prescription.action_id)
        handler = _notify_oncall

    logger.info(
        "Executing healing action '%s' for failure '%s' on service '%s'.",
        prescription.action_id,
        prescription.failure_type,
        prescription.service,
    )
    print(f"\n  [Healing] {prescription.action_label} (service: {prescription.service})")
    return handler(prescription)


def heal_all(prescriptions: list[HealingPrescription]) -> list[HealingOutcome]:
    """
    Apply healing actions to every prescription in order.

    Args:
        prescriptions: List of HealingPrescription objects.

    Returns:
        List of HealingOutcome objects in the same order.
    """
    outcomes: list[HealingOutcome] = []
    for p in prescriptions:
        outcome = heal(p)
        outcomes.append(outcome)
    return outcomes
