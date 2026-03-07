"""
rule_engine.py

Maps detected failure types to structured healing prescriptions using a rule table.
"""

import logging
from dataclasses import dataclass
from typing import Optional
from failure_detector import FailureEvent, DetectionResult

logger = logging.getLogger(__name__)


@dataclass
class HealingPrescription:
    """
    A structured healing prescription produced by the rule engine for a single failure event.
    """
    failure_type: str
    severity: str
    service: str
    action_id: str          # machine-readable action key
    action_label: str       # human-readable action description
    permanent_fix: str      # advisory text for permanent remediation
    event: FailureEvent     # back-reference to the original event

    def __str__(self) -> str:
        return (
            f"Prescription for {self.failure_type} on '{self.service}': {self.action_label}"
        )


# Rule table: failure_type → prescription details
_RULES: dict[str, dict] = {
    "service_crash": {
        "action_id":     "restart_service",
        "action_label":  "Restart the crashed service",
        "permanent_fix": (
            "Investigate crash dumps and application logs for root cause. "
            "Consider adding a process supervisor (systemd, supervisord) with "
            "automatic restart and memory limits."
        ),
    },
    "memory_spike": {
        "action_id":     "restart_container",
        "action_label":  "Restart container / process to reclaim memory",
        "permanent_fix": (
            "Profile the application for memory leaks. Set container memory limits "
            "and configure OOM thresholds. Consider horizontal scaling."
        ),
    },
    "disk_full": {
        "action_id":     "run_cleanup",
        "action_label":  "Run disk cleanup — purge old logs and temp files",
        "permanent_fix": (
            "Set up log rotation (logrotate) and automated archival. Add disk-usage "
            "alerting at 75% / 90% thresholds. Expand volume or add storage tier."
        ),
    },
    "connection_refused": {
        "action_id":     "restart_dependency",
        "action_label":  "Restart the failing dependency service",
        "permanent_fix": (
            "Implement health-check probes and circuit breakers. Add retry logic "
            "with exponential back-off in the client application."
        ),
    },
    "timeout": {
        "action_id":     "scale_out",
        "action_label":  "Scale out instances and reset connection pool",
        "permanent_fix": (
            "Review timeout thresholds and query/request performance. Add caching "
            "and consider async processing for slow operations."
        ),
    },
    "generic_error": {
        "action_id":     "notify_oncall",
        "action_label":  "Notify on-call engineer for manual investigation",
        "permanent_fix": (
            "Improve structured logging and error categorisation to enable "
            "more specific automated remediation in the future."
        ),
    },
}

_FALLBACK_RULE: dict = {
    "action_id":     "notify_oncall",
    "action_label":  "Unknown failure — notify on-call engineer",
    "permanent_fix": "Add a specific rule for this failure type in rule_engine.py.",
}


def classify(event: FailureEvent) -> HealingPrescription:
    """
    Classify a single FailureEvent and return a HealingPrescription.

    Args:
        event: A FailureEvent produced by failure_detector.detect_failures().

    Returns:
        HealingPrescription with the appropriate action and advisory.
    """
    rule = _RULES.get(event.failure_type, _FALLBACK_RULE)
    logger.debug(
        "Classified event '%s' → action '%s'", event.failure_type, rule["action_id"]
    )
    return HealingPrescription(
        failure_type=event.failure_type,
        severity=event.severity,
        service=event.service,
        action_id=rule["action_id"],
        action_label=rule["action_label"],
        permanent_fix=rule["permanent_fix"],
        event=event,
    )


def classify_all(result: DetectionResult) -> list[HealingPrescription]:
    """
    Classify every event in a DetectionResult, deduplicating by failure_type so
    that repeated log lines for the same failure produce only one prescription.

    Args:
        result: DetectionResult from failure_detector.detect_failures().

    Returns:
        Deduplicated list of HealingPrescription objects.
    """
    seen: set[str] = set()
    prescriptions: list[HealingPrescription] = []

    for event in result.events:
        if event.failure_type not in seen:
            seen.add(event.failure_type)
            prescriptions.append(classify(event))

    logger.info("Rule engine produced %d unique prescription(s).", len(prescriptions))
    return prescriptions
