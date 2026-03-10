"""
Rule-based incident analyzer.

Detects incident categories by inspecting log messages, metrics, tags,
title, and description using pattern matching. No external dependencies.
"""

import re
from typing import List, Tuple

from schemas import Incident, AnalysisResult, Severity, AnalysisMode


# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

PATTERNS = {
    "network_failure": [
        r"connection refused",
        r"no live upstreams",
        r"connection reset by peer",
        r"upstream.*failed",
        r"502\s*bad gateway",
        r"504\s*gateway timeout",
        r"network.*unreachable",
        r"ssl.*failed",
        r"handshake.*failed",
        r"econnrefused",
        r"econnreset",
        r"etimedout",
    ],
    "database_failure": [
        r"connection pool exhausted",
        r"could not acquire.*connection",
        r"max_connections.*reached",
        r"database.*unreachable",
        r"db.*connection.*refused",
        r"connection.*postgresql",
        r"connection.*mysql",
        r"connection.*mongo",
        r"remaining connection slots",
        r"circuit breaker.*open",
        r"db.*timeout",
        r"query timeout",
    ],
    "high_cpu": [
        r"cpu usage.*9[0-9]%",
        r"cpu.*critical",
        r"load average.*\d{2,}",
        r"cpu steal",
        r"thread pool exhausted",
        r"no available workers",
        r"system overload",
        r"cpu.*threshold.*exceeded",
    ],
    "resource_exhaustion": [
        r"oom killer",
        r"out of memory",
        r"disk.*full",
        r"no space left",
        r"inode.*exhausted",
        r"memory.*critical",
        r"swap.*full",
        r"file descriptor.*limit",
        r"too many open files",
        r"request queue.*depth.*\d{3,}",
        r"dropping new requests",
    ],
    "service_unavailable": [
        r"service.*unavailable",
        r"503",
        r"health check failed",
        r"readiness probe failed",
        r"liveness probe failed",
        r"pod.*crashloopbackoff",
        r"container.*exit",
        r"process.*terminated",
        r"worker.*died",
    ],
}

METRIC_RULES = {
    "high_cpu": [
        ("cpu_percent", ">=", 90),
        ("load_average_1m", ">=", 10),
        ("cpu_steal_percent", ">=", 30),
    ],
    "resource_exhaustion": [
        ("memory_percent", ">=", 90),
        ("db_connection_pool_percent", ">=", 95),
        ("request_queue_depth", ">=", 1000),
    ],
    "database_failure": [
        ("db_connection_errors", ">=", 100),
        ("db_query_timeout_count", ">=", 50),
        ("db_connection_pool_percent", ">=", 100),
    ],
    "service_unavailable": [
        ("error_rate_percent", ">=", 80),
        ("request_failure_rate_percent", ">=", 90),
        ("circuit_breaker_state", ">=", 1),
    ],
}

SEVERITY_MAP = {
    "network_failure": Severity.HIGH,
    "database_failure": Severity.CRITICAL,
    "high_cpu": Severity.HIGH,
    "resource_exhaustion": Severity.CRITICAL,
    "service_unavailable": Severity.HIGH,
}

SEVERITY_ORDER = [
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
    Severity.UNKNOWN,
]

ROOT_CAUSE_TEMPLATES = {
    "database_failure": (
        "Database connectivity failure detected. Connection pool exhaustion or server "
        "max_connections limit reached is preventing the application from executing queries."
    ),
    "network_failure": (
        "Network layer failure detected. Upstream services are unreachable due to refused "
        "connections, SSL errors, or misconfigured reverse proxy routing."
    ),
    "high_cpu": (
        "CPU resource saturation detected. Sustained high CPU utilization is causing "
        "request timeouts, thread pool exhaustion, and degraded system response times."
    ),
    "resource_exhaustion": (
        "System resource exhaustion detected. Memory pressure, connection pool limits, "
        "or request queue saturation is triggering cascading failures."
    ),
    "service_unavailable": (
        "Service availability failure detected. Health checks are failing and the service "
        "is not accepting traffic, possibly due to application crash or dependency failure."
    ),
}

FIX_TEMPLATES = {
    "database_failure": (
        "Increase connection pool size or reduce connection hold time. "
        "Investigate long-running queries. Consider read replicas for read-heavy workloads. "
        "Verify PostgreSQL max_connections parameter and apply PgBouncer if needed."
    ),
    "network_failure": (
        "Verify upstream service health and network reachability. "
        "Check Nginx upstream configuration and SSL certificate validity. "
        "Review firewall rules and security group settings."
    ),
    "high_cpu": (
        "Identify and terminate runaway processes. Scale horizontally by adding instances. "
        "Profile application for CPU hotspots. Review hypervisor for noisy-neighbor issues. "
        "Enable auto-scaling triggers if not already configured."
    ),
    "resource_exhaustion": (
        "Free memory by restarting leaking services or scaling vertically. "
        "Tune connection pool limits and request queue depths. "
        "Review OOM killer events and adjust container memory limits."
    ),
    "service_unavailable": (
        "Restart failed service pods/containers. Review recent deployments for regressions. "
        "Check dependency health and circuit breaker states. "
        "Validate readiness/liveness probe configuration."
    ),
}


def _compile_patterns():
    compiled = {}
    for category, pattern_list in PATTERNS.items():
        compiled[category] = [re.compile(p, re.IGNORECASE) for p in pattern_list]
    return compiled


_COMPILED_PATTERNS = _compile_patterns()


def _text_corpus(incident: Incident) -> str:
    parts = [
        incident.title,
        incident.description,
        " ".join(incident.logs),
        " ".join(incident.tags),
    ]
    return " ".join(parts)


def _detect_from_text(corpus: str) -> List[Tuple[str, float]]:
    scores = {}
    for category, patterns in _COMPILED_PATTERNS.items():
        hits = sum(1 for p in patterns if p.search(corpus))
        if hits > 0:
            scores[category] = hits / len(patterns)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def _detect_from_metrics(metrics: dict) -> List[str]:
    detected = []
    for category, rules in METRIC_RULES.items():
        for metric_key, op, threshold in rules:
            value = metrics.get(metric_key)
            if value is None:
                continue
            if op == ">=" and float(value) >= threshold:
                if category not in detected:
                    detected.append(category)
            elif op == "<=" and float(value) <= threshold:
                if category not in detected:
                    detected.append(category)
    return detected


def _pick_severity(categories: List[str]) -> Severity:
    severities = [SEVERITY_MAP.get(c, Severity.UNKNOWN) for c in categories]
    for level in SEVERITY_ORDER:
        if level in severities:
            return level
    return Severity.UNKNOWN


def _build_root_cause(categories: List[str], incident: Incident) -> str:
    if not categories:
        return (
            f"Undetermined root cause for incident '{incident.title}'. "
            "No matching patterns detected. Manual investigation required."
        )
    primary = categories[0]
    template = ROOT_CAUSE_TEMPLATES.get(primary, "Unknown failure mode detected.")
    if len(categories) > 1:
        secondary = ", ".join(categories[1:])
        template += f" Secondary issues detected: {secondary}."
    return template


def _build_fix(categories: List[str]) -> str:
    if not categories:
        return "Perform manual triage. Review logs and metrics for anomalies."
    primary = categories[0]
    return FIX_TEMPLATES.get(primary, "Investigate logs and escalate to on-call engineer.")


def analyze(incident: Incident) -> AnalysisResult:
    corpus = _text_corpus(incident)
    text_scores = _detect_from_text(corpus)
    metric_categories = _detect_from_metrics(incident.metrics)

    # Merge: text-detected + metric-detected (deduplicated, text scores first)
    categories_ordered = [cat for cat, _ in text_scores]
    for cat in metric_categories:
        if cat not in categories_ordered:
            categories_ordered.append(cat)

    # Confidence: average of top text scores or 0.5 if metric-only
    if text_scores:
        top_scores = [s for _, s in text_scores[:3]]
        confidence = min(sum(top_scores) / len(top_scores) * 1.5, 1.0)
    elif metric_categories:
        confidence = 0.6
    else:
        confidence = 0.1

    severity = _pick_severity(categories_ordered) if categories_ordered else Severity.UNKNOWN
    root_cause = _build_root_cause(categories_ordered, incident)
    recommended_fix = _build_fix(categories_ordered)

    return AnalysisResult(
        root_cause=root_cause,
        severity=severity,
        recommended_fix=recommended_fix,
        runbook_steps=[],  # populated by runbook_engine
        analysis_mode=AnalysisMode.RULE_BASED,
        detected_categories=categories_ordered,
        confidence_score=confidence,
    )
