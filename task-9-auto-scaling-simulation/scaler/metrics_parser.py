"""
metrics_parser.py - Load and validate workload metric files.

Supports JSON metric files describing the current state of a service
replica set. Validates expected fields and returns a typed dataclass.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


REQUIRED_FIELDS = {
    "cpu_utilization",
    "memory_utilization",
    "request_rate",
    "queue_depth",
    "current_replicas",
}

OPTIONAL_FIELDS = {
    "service",
    "environment",
    "timestamp",
    "avg_response_time_ms",
    "error_rate",
}


@dataclass
class Metrics:
    # Required
    cpu_utilization: float       # Percentage 0-100
    memory_utilization: float    # Percentage 0-100
    request_rate: float          # Requests per second (or per minute — context-dependent)
    queue_depth: int             # Number of messages/jobs currently queued
    current_replicas: int        # Number of running pod/container replicas

    # Optional enrichment fields
    service: str = "unknown"
    environment: str = "unknown"
    timestamp: str = ""
    avg_response_time_ms: float = 0.0
    error_rate: float = 0.0

    # Raw payload retained for report transparency
    raw: dict = field(default_factory=dict, repr=False)


def load(file_path: str) -> Metrics:
    """
    Parse a JSON metric file and return a validated Metrics instance.

    Args:
        file_path: Path to the JSON metrics file.

    Returns:
        Metrics dataclass populated from the file.

    Raises:
        SystemExit: On file-not-found, invalid JSON, or missing required fields.
    """
    path = Path(file_path)

    if not path.exists():
        print(f"[ERROR] Metrics file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    if path.suffix.lower() != ".json":
        print(f"[ERROR] Expected a .json file, got: {path.suffix}", file=sys.stderr)
        sys.exit(1)

    try:
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except json.JSONDecodeError as exc:
        print(f"[ERROR] Failed to parse JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    _validate(raw, file_path)
    return _build(raw)


def _validate(data: dict, source: str) -> None:
    """Assert all required fields are present and within sane ranges."""
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        print(
            f"[ERROR] Metric file '{source}' is missing required fields: {sorted(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    errors = []

    cpu = data["cpu_utilization"]
    if not (0 <= cpu <= 100):
        errors.append(f"cpu_utilization must be 0-100, got {cpu}")

    mem = data["memory_utilization"]
    if not (0 <= mem <= 100):
        errors.append(f"memory_utilization must be 0-100, got {mem}")

    rps = data["request_rate"]
    if rps < 0:
        errors.append(f"request_rate must be >= 0, got {rps}")

    qd = data["queue_depth"]
    if qd < 0:
        errors.append(f"queue_depth must be >= 0, got {qd}")

    replicas = data["current_replicas"]
    if not (isinstance(replicas, int) and replicas >= 0):
        errors.append(f"current_replicas must be a non-negative integer, got {replicas}")

    if errors:
        for e in errors:
            print(f"[ERROR] Validation: {e}", file=sys.stderr)
        sys.exit(1)


def _build(data: dict) -> Metrics:
    """Construct a Metrics instance from validated raw data."""
    return Metrics(
        cpu_utilization=float(data["cpu_utilization"]),
        memory_utilization=float(data["memory_utilization"]),
        request_rate=float(data["request_rate"]),
        queue_depth=int(data["queue_depth"]),
        current_replicas=int(data["current_replicas"]),
        service=data.get("service", "unknown"),
        environment=data.get("environment", "unknown"),
        timestamp=data.get("timestamp", ""),
        avg_response_time_ms=float(data.get("avg_response_time_ms", 0.0)),
        error_rate=float(data.get("error_rate", 0.0)),
        raw=data,
    )
