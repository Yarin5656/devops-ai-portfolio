"""
Rule-based incident classification engine.

Classifies incidents into categories based on keyword and pattern matching
against the log message. Returns category, severity, and a root cause summary.
"""

import re
from dataclasses import dataclass
from typing import Optional
from app.schemas import Category, Severity


@dataclass
class ClassificationResult:
    category: Category
    severity: Severity
    root_cause: str
    recommended_fix: str


# Pattern registry: order matters — first match wins for multi-signal logs.
# Each entry: (category, severity, patterns, root_cause, recommended_fix)
_RULES = [
    (
        Category.PERMISSIONS,
        Severity.HIGH,
        [
            r"permission denied",
            r"access denied",
            r"forbidden",
            r"not authorized",
            r"unauthorized",
            r"EACCES",
            r"privilege",
        ],
        "Operation blocked due to insufficient permissions or misconfigured access control.",
        "Verify IAM roles, file-system ACLs, or service account bindings for the affected resource.",
    ),
    (
        Category.TIMEOUT,
        Severity.HIGH,
        [
            r"timeout",
            r"timed out",
            r"deadline exceeded",
            r"read timeout",
            r"write timeout",
            r"gateway timeout",
            r"504",
        ],
        "A downstream call exceeded its configured time limit, indicating latency or unresponsiveness.",
        "Check downstream service health, increase timeout thresholds if appropriate, and add circuit-breaker logic.",
    ),
    (
        Category.NETWORK,
        Severity.HIGH,
        [
            r"connection refused",
            r"connection reset",
            r"no route to host",
            r"network unreachable",
            r"dns.*fail",
            r"name resolution",
            r"could not connect",
            r"ECONNREFUSED",
            r"ENETUNREACH",
            r"upstream.*unavailable",
            r"502",
            r"503",
        ],
        "Network-layer failure preventing the service from reaching its upstream or dependency.",
        "Verify network policies, service endpoints, DNS resolution, and firewall rules between components.",
    ),
    (
        Category.DEPENDENCY,
        Severity.MEDIUM,
        [
            r"module.{0,3}not.{0,3}found",
            r"modulenotfounderror",
            r"import.{0,5}error",
            r"package.*missing",
            r"no such file",
            r"library.*not found",
            r"dependency.*fail",
            r"cannot find module",
            r"unresolved.*dependency",
            r"version.*conflict",
        ],
        "A required software dependency or configuration file is missing or incompatible.",
        "Reinstall dependencies, check version compatibility, and validate the build/deploy artifact.",
    ),
    (
        Category.RESOURCE,
        Severity.CRITICAL,
        [
            r"out of memory",
            r"OOM",
            r"killed.*memory",
            r"memory.*exhausted",
            r"disk.*full",
            r"no space left",
            r"ENOSPC",
            r"cpu.*limit",
            r"throttl",
            r"resource exhausted",
        ],
        "System or container resource limits (memory, disk, CPU) have been reached or exceeded.",
        "Scale resources, tune limits/requests, prune unused data, and investigate memory or disk leaks.",
    ),
]

_FALLBACK = ClassificationResult(
    category=Category.UNKNOWN,
    severity=Severity.LOW,
    root_cause="Incident does not match any known failure pattern. Manual investigation required.",
    recommended_fix="Review full logs, correlate with recent deployments, and escalate if issue persists.",
)


def classify(log: str, source: str = "") -> ClassificationResult:
    """
    Classify an incident log message using regex pattern matching.

    Args:
        log: Raw log or error text.
        source: Optional service name to influence severity (e.g. 'database' → higher severity).

    Returns:
        ClassificationResult with category, severity, root_cause, recommended_fix.
    """
    text = (log + " " + source).lower()

    for category, severity, patterns, root_cause, recommended_fix in _RULES:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                # Escalate resource issues in production-critical sources
                adjusted_severity = _adjust_severity(severity, source)
                return ClassificationResult(
                    category=category,
                    severity=adjusted_severity,
                    root_cause=root_cause,
                    recommended_fix=recommended_fix,
                )

    return _FALLBACK


def _adjust_severity(base: Severity, source: str) -> Severity:
    """Escalate severity for known critical infrastructure sources."""
    critical_sources = {"database", "postgres", "mysql", "redis", "kafka", "etcd", "vault"}
    if source.lower() in critical_sources and base == Severity.MEDIUM:
        return Severity.HIGH
    return base
