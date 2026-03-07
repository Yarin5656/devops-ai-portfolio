"""
failure_detector.py

Scans log content and extracts structured failure events based on keyword patterns.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)

FAILURE_PATTERNS = [
    {"keyword": "crashed",           "failure_type": "service_crash",       "severity": "critical"},
    {"keyword": "segmentation fault","failure_type": "service_crash",       "severity": "critical"},
    {"keyword": "out of memory",     "failure_type": "memory_spike",        "severity": "critical"},
    {"keyword": "oom killer",        "failure_type": "memory_spike",        "severity": "critical"},
    {"keyword": "disk full",         "failure_type": "disk_full",           "severity": "high"},
    {"keyword": "no space left",     "failure_type": "disk_full",           "severity": "high"},
    {"keyword": "connection refused","failure_type": "connection_refused",  "severity": "high"},
    {"keyword": "timeout",           "failure_type": "timeout",             "severity": "medium"},
    {"keyword": "timed out",         "failure_type": "timeout",             "severity": "medium"},
    {"keyword": "error",             "failure_type": "generic_error",       "severity": "low"},
    {"keyword": "exception",         "failure_type": "generic_error",       "severity": "low"},
]


@dataclass
class FailureEvent:
    """Represents a single detected failure extracted from a log line."""
    line_number: int
    raw_line: str
    failure_type: str
    severity: str
    keyword_matched: str
    service: str = "unknown"

    def __str__(self) -> str:
        return (
            f"[Line {self.line_number}] {self.failure_type.upper()} "
            f"(severity={self.severity}) - matched '{self.keyword_matched}'"
        )


@dataclass
class DetectionResult:
    """Aggregated result of scanning a full log file."""
    log_path: str
    events: List[FailureEvent] = field(default_factory=list)

    @property
    def has_failures(self) -> bool:
        return len(self.events) > 0

    @property
    def highest_severity(self) -> str:
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        if not self.events:
            return "none"
        return min(self.events, key=lambda e: order.get(e.severity, 99)).severity

    def summary(self) -> str:
        if not self.events:
            return "No failures detected."
        types = set(e.failure_type for e in self.events)
        return f"{len(self.events)} failure event(s) detected: {', '.join(sorted(types))}"


def _extract_service_name(line: str) -> str:
    """Best-effort parse of a service name from a log line (e.g. nginx, postgres)."""
    # Common service tokens embedded in log lines
    known_services = [
        "nginx", "postgres", "postgresql", "mysql", "redis",
        "mongodb", "rabbitmq", "kafka", "elasticsearch", "docker",
        "kubernetes", "k8s", "node", "python", "java", "apache",
    ]
    lower = line.lower()
    for svc in known_services:
        if svc in lower:
            return svc
    # Fallback: grab first bracketed token e.g. [nginx]
    match = re.search(r"\[([a-zA-Z0-9_\-]+)\]", line)
    if match:
        return match.group(1)
    return "unknown"


def detect_failures(log_path: str) -> DetectionResult:
    """
    Read a log file and return a DetectionResult containing all matched failure events.

    Args:
        log_path: Absolute or relative path to the log file.

    Returns:
        DetectionResult with zero or more FailureEvent entries.

    Raises:
        FileNotFoundError: If the log file does not exist.
        IOError: If the file cannot be read.
    """
    logger.info("Opening log file: %s", log_path)
    result = DetectionResult(log_path=log_path)

    with open(log_path, "r", encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, start=1):
            lower = line.lower()
            for pattern in FAILURE_PATTERNS:
                if pattern["keyword"] in lower:
                    event = FailureEvent(
                        line_number=line_no,
                        raw_line=line.rstrip(),
                        failure_type=pattern["failure_type"],
                        severity=pattern["severity"],
                        keyword_matched=pattern["keyword"],
                        service=_extract_service_name(line),
                    )
                    result.events.append(event)
                    logger.debug("Matched pattern '%s' on line %d", pattern["keyword"], line_no)
                    # Only record the most-specific (first) match per line
                    break

    logger.info("Detection complete. %s", result.summary())
    return result
