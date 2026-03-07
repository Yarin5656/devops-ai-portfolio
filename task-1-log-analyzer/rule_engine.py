"""
rule_engine.py

Rule-based error classification and root cause analysis engine.

Each rule maps a set of textual patterns to an error category,
a root cause description, an impact statement, and suggested fixes.
Rules are evaluated in priority order; the first match wins.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional

from log_parser import ParsedLog

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RuleMatch:
    """Result produced by the rule engine for a single log analysis."""

    category: str
    root_cause: str
    impact: str
    suggested_fixes: List[str]
    matched_rule: str
    confidence: str  # "high" | "medium" | "low"


@dataclass
class Rule:
    """A single classification rule."""

    name: str
    patterns: List[str]          # regex patterns (case-insensitive OR match)
    category: str
    root_cause: str
    impact: str
    suggested_fixes: List[str]
    confidence: str = "high"


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

RULES: List[Rule] = [
    # ----- Permissions -----
    Rule(
        name="permission_denied",
        patterns=[
            r"permission denied",
            r"access denied",
            r"operation not permitted",
            r"EACCES",
            r"chmod",
        ],
        category="permissions",
        root_cause=(
            "A process attempted to access a file, directory, or system resource "
            "without the required operating-system permissions. This is commonly "
            "caused by a service account lacking read/write/execute rights, "
            "incorrect file ownership, or overly restrictive umask settings."
        ),
        impact=(
            "The affected process cannot read or write required files, causing it "
            "to abort. In a deployment pipeline this typically means the release "
            "step fails completely and no new version is promoted."
        ),
        suggested_fixes=[
            "Run `ls -la <path>` to inspect current ownership and mode bits.",
            "Grant the correct permissions: `chmod 755 <path>` or `chown <user>:<group> <path>`.",
            "For containerised workloads, verify the `runAsUser` / `fsGroup` fields in the PodSpec.",
            "If using sudo-gated commands, add the service account to the sudoers file with the minimum required scope.",
            "Audit IAM roles or S3 bucket policies when the resource is cloud-hosted.",
        ],
        confidence="high",
    ),

    # ----- Dependency — missing module -----
    Rule(
        name="module_not_found",
        patterns=[
            r"module not found",
            r"ModuleNotFoundError",
            r"ImportError",
            r"cannot find module",
            r"no module named",
            r"requirementnotmet",
            r"package not found",
        ],
        category="dependency",
        root_cause=(
            "The application tried to import a library or module that is not "
            "installed in the current runtime environment. This is typically caused "
            "by a missing `pip install` / `npm install` step, a version pin mismatch, "
            "or a virtualenv/container image built without the required package."
        ),
        impact=(
            "The application process fails at startup and cannot serve any traffic. "
            "In CI/CD this causes an immediate build or deploy stage failure."
        ),
        suggested_fixes=[
            "Install missing dependencies: `pip install -r requirements.txt` (Python) or `npm ci` (Node).",
            "Verify the package name and version pin in the dependency manifest.",
            "Rebuild the container image to include the latest dependency snapshot.",
            "Check that the correct virtual environment or runtime is activated.",
            "Inspect the build cache — a stale layer may be missing a recently added package.",
        ],
        confidence="high",
    ),

    # ----- Network — connection refused -----
    Rule(
        name="connection_refused",
        patterns=[
            r"connection refused",
            r"ECONNREFUSED",
            r"connect: connection refused",
        ],
        category="network",
        root_cause=(
            "The client attempted to open a TCP connection to a host/port "
            "combination that actively rejected it. The target service is not "
            "running, is bound to a different interface, or a firewall/security "
            "group is blocking inbound traffic on that port."
        ),
        impact=(
            "Any component that depends on this downstream service will fail to "
            "initialise, cascade-failing dependent services and potentially "
            "rendering the entire deployment non-functional."
        ),
        suggested_fixes=[
            "Verify the target service is running: `systemctl status <service>` or `docker ps`.",
            "Confirm the correct host and port are configured (check env vars / config maps).",
            "Test connectivity from the failing host: `nc -zv <host> <port>` or `curl -v <url>`.",
            "Review firewall rules, security groups, or network policies blocking the port.",
            "Check service health endpoints and recent restart logs for the target service.",
        ],
        confidence="high",
    ),

    # ----- Network — timeout -----
    Rule(
        name="timeout",
        patterns=[
            r"timed out",
            r"ETIMEDOUT",
            r"deadline exceeded",
            r"read timeout",
            r"connection timeout",
            r"request timeout",
            r"operation timed",
        ],
        category="network",
        root_cause=(
            "A network request or internal operation did not complete within the "
            "configured time limit. This may indicate high latency, an overloaded "
            "downstream service, DNS resolution failure, or a misconfigured timeout "
            "threshold that is too aggressive for the workload."
        ),
        impact=(
            "The requesting component treats the operation as failed and may retry "
            "aggressively, amplifying load on an already stressed service. In "
            "deployments this often causes health-check failures and rollback triggers."
        ),
        suggested_fixes=[
            "Check downstream service latency and CPU/memory utilisation under load.",
            "Increase timeout thresholds in the application config if the operation is legitimately slow.",
            "Inspect DNS resolution: `nslookup <hostname>` or `dig <hostname>`.",
            "Add circuit-breaker logic to prevent timeout storms from cascading.",
            "Review recent infrastructure changes that may have introduced extra hops or latency.",
        ],
        confidence="high",
    ),

    # ----- Dependency — general package / library error -----
    Rule(
        name="dependency_error",
        patterns=[
            r"dependency",
            r"version conflict",
            r"incompatible",
            r"requires.*but.*found",
        ],
        category="dependency",
        root_cause=(
            "A version conflict or incompatibility exists between installed packages. "
            "Two or more components require different versions of the same library, "
            "or the installed version does not satisfy the stated minimum/maximum."
        ),
        impact=(
            "Runtime behaviour is unpredictable — the application may start but "
            "produce silent errors, or fail outright during module initialisation."
        ),
        suggested_fixes=[
            "Run `pip check` (Python) or `npm ls` (Node) to surface dependency conflicts.",
            "Pin all transitive dependencies using a lock file (`poetry.lock`, `package-lock.json`).",
            "Upgrade or downgrade conflicting packages to a mutually compatible version range.",
            "Use isolated environments (virtualenv, Docker) to avoid system-level interference.",
        ],
        confidence="medium",
    ),

    # ----- Infrastructure — out-of-memory -----
    Rule(
        name="oom_killed",
        patterns=[
            r"out of memory",
            r"OOMKilled",
            r"oom.kill",
            r"killed process",
            r"cannot allocate memory",
        ],
        category="infrastructure",
        root_cause=(
            "The operating system or container runtime terminated the process "
            "because it exceeded the available or configured memory limit. "
            "Common causes are memory leaks, under-provisioned resource limits, "
            "or an unexpected surge in data volume processed by the service."
        ),
        impact=(
            "The service is abruptly terminated with no opportunity for graceful "
            "shutdown. Persistent state may be corrupted. In Kubernetes, the pod "
            "will restart repeatedly (CrashLoopBackOff)."
        ),
        suggested_fixes=[
            "Inspect memory usage trend: `kubectl top pod` or `docker stats`.",
            "Raise the container memory limit in the Deployment / Task Definition.",
            "Profile the application for memory leaks using language-native tooling.",
            "Implement pagination or streaming for large data processing operations.",
            "Set JVM heap flags (`-Xmx`) or equivalent runtime memory caps explicitly.",
        ],
        confidence="high",
    ),

    # ----- Infrastructure — disk full -----
    Rule(
        name="disk_full",
        patterns=[
            r"no space left on device",
            r"disk full",
            r"ENOSPC",
            r"filesystem.*full",
        ],
        category="infrastructure",
        root_cause=(
            "The target filesystem has no remaining space. Log rotation may have "
            "failed, a large artifact was written without size guards, or the "
            "volume was under-provisioned for the workload."
        ),
        impact=(
            "Write operations fail across the board. Databases may corrupt on-disk "
            "structures. Log files stop collecting telemetry. Deployments that "
            "require writing artifacts or extracting archives will halt immediately."
        ),
        suggested_fixes=[
            "Free space immediately: `df -h` to identify the full volume, `du -sh /*` to find large consumers.",
            "Purge old Docker images/containers: `docker system prune -af`.",
            "Enforce log rotation with `logrotate` or configure log collection agents to forward and truncate.",
            "Expand the volume via cloud provider console or `lvextend` for LVM-managed disks.",
            "Add disk-usage alerts at 70%/85% thresholds to prevent future incidents.",
        ],
        confidence="high",
    ),

    # ----- Configuration -----
    Rule(
        name="configuration_error",
        patterns=[
            r"configuration error",
            r"invalid config",
            r"missing.*config",
            r"env.*not set",
            r"environment variable.*not",
            r"undefined variable",
            r"parse error",
            r"syntax error",
            r"yaml.*error",
            r"json.*error",
        ],
        category="configuration",
        root_cause=(
            "The application encountered an invalid, incomplete, or malformed "
            "configuration. This may be caused by a missing environment variable, "
            "a typo in a YAML/JSON config file, or a schema mismatch after a "
            "version upgrade."
        ),
        impact=(
            "The service cannot initialise and will refuse to start. "
            "All downstream consumers of this service will be affected."
        ),
        suggested_fixes=[
            "Validate the configuration file against the expected schema: `python -m json.tool config.json`.",
            "Ensure all required environment variables are set in the deployment spec or `.env` file.",
            "Compare the current config against the documented defaults for the running version.",
            "Use a config linting tool (e.g., `yamllint`, `cfn-lint`) in the CI pipeline.",
            "Check recent config-management PRs / Terraform plans for unintended changes.",
        ],
        confidence="medium",
    ),

    # ----- Catch-all -----
    Rule(
        name="generic_error",
        patterns=[
            r"error",
            r"fatal",
            r"exception",
            r"traceback",
            r"failed",
        ],
        category="infrastructure",
        root_cause=(
            "An unclassified error was detected. The log contains generic failure "
            "indicators but does not match any specific known pattern. Manual "
            "investigation of the full log is recommended."
        ),
        impact=(
            "Unknown — the exact blast radius depends on which component produced "
            "the error and whether any retry or fallback logic is in place."
        ),
        suggested_fixes=[
            "Review the full log file for additional context surrounding the error.",
            "Search the error message in the project issue tracker or runbook.",
            "Enable DEBUG-level logging and reproduce the failure in a staging environment.",
            "Consult the on-call runbook for the affected service.",
        ],
        confidence="low",
    ),
]


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def classify_and_analyse(parsed_log: ParsedLog) -> Optional[RuleMatch]:
    """
    Run the rule engine against a parsed log and return the first matching
    RuleMatch, or None if no error lines were found.

    Args:
        parsed_log: Output of log_parser.parse_log().

    Returns:
        RuleMatch on success, None if there is nothing to classify.
    """
    if not parsed_log.error_lines:
        logger.info("No error lines found — nothing to classify.")
        return None

    # Combine all error-line text for pattern matching
    error_corpus = "\n".join(text for _, text in parsed_log.error_lines)

    for rule in RULES:
        for pattern in rule.patterns:
            if re.search(pattern, error_corpus, re.IGNORECASE):
                logger.info(
                    "Rule '%s' matched pattern '%s' (category: %s)",
                    rule.name,
                    pattern,
                    rule.category,
                )
                return RuleMatch(
                    category=rule.category,
                    root_cause=rule.root_cause,
                    impact=rule.impact,
                    suggested_fixes=rule.suggested_fixes,
                    matched_rule=rule.name,
                    confidence=rule.confidence,
                )

    logger.warning("No rule matched — returning None.")
    return None
