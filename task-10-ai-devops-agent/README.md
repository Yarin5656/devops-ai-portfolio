# Task 10 — AI DevOps Agent

A production-grade CLI DevOps agent that analyzes incidents, logs, and metrics,
then returns structured remediation guidance with step-by-step runbook procedures.

---

## Project Overview

The DevOps AI Agent bridges the gap between raw operational data (logs, metrics, alert payloads)
and actionable remediation guidance. It operates in two modes:

| Mode | Description |
|------|-------------|
| **Rule-Based** | Fully offline. Pattern-matching against logs, metrics, and tags — no API key required. |
| **AI-Enhanced** | Optionally augments rule-based results with Claude AI insights when `ANTHROPIC_API_KEY` is set. |

The agent is designed to be embedded in on-call workflows, CI/CD pipelines, or invoked
directly from an incident management system.

---

## Architecture

```
task-10-ai-devops-agent/
├── agent/
│   ├── main.py               # CLI entry point, report renderer, orchestration
│   ├── incident_analyzer.py  # Rule-based detection engine (patterns + metrics)
│   ├── runbook_engine.py     # Per-category operational runbook steps
│   ├── ai_interface.py       # Optional Claude AI enhancement layer
│   └── schemas.py            # Dataclasses: Incident, AnalysisResult, Severity enums
├── examples/
│   ├── nginx_failure.json         # Nginx 502 upstream failure scenario
│   ├── high_cpu_incident.json     # CPU saturation + thread pool exhaustion
│   └── db_connection_error.json   # PostgreSQL connection pool exhaustion
├── reports/
│   └── incident-analysis.md      # Generated report output
└── requirements.txt
```

### Component Responsibilities

```
┌─────────────────────────────────────────────────────────────┐
│                        main.py                              │
│  CLI parsing → load incident → orchestrate → render report  │
└──────────────┬──────────────────────────┬───────────────────┘
               │                          │
       ┌───────▼───────┐        ┌─────────▼──────────┐
       │ incident_      │        │   ai_interface.py   │
       │ analyzer.py    │        │ (optional, graceful │
       │ Rule engine    │        │  fallback if N/A)   │
       └───────┬────────┘        └─────────────────────┘
               │
       ┌───────▼────────┐
       │ runbook_engine  │
       │ Operational     │
       │ steps library   │
       └────────────────┘
```

---

## Installation

```bash
cd task-10-ai-devops-agent

# Minimal install (rule-based only — no API key required)
pip install -r requirements.txt

# Or just Python stdlib — the agent works with zero external dependencies
# when anthropic package is absent
```

---

## Usage

### Basic usage (rule-based)
```bash
python agent/main.py --file examples/nginx_failure.json
python agent/main.py --file examples/high_cpu_incident.json
python agent/main.py --file examples/db_connection_error.json
```

### Custom output path
```bash
python agent/main.py --file examples/nginx_failure.json --output reports/nginx-report.md
```

### Force rule-based only (disable AI even if key is set)
```bash
python agent/main.py --file examples/nginx_failure.json --no-ai
```

### With AI enhancement (requires Anthropic API key)
```bash
export ANTHROPIC_API_KEY=sk-ant-...
python agent/main.py --file examples/db_connection_error.json
```

### Verbose logging
```bash
python agent/main.py --file examples/nginx_failure.json --verbose
```

---

## Incident Examples

### nginx_failure.json — Nginx 502 Bad Gateway

Simulates a production Nginx reverse proxy returning 502 errors due to all upstream
application servers refusing connections. The agent detects `network_failure` and
`service_unavailable` categories, assigns HIGH severity, and returns an Nginx-specific
runbook covering SSL, DNS, and upstream health verification.

### high_cpu_incident.json — CPU Saturation

Simulates a sustained CPU overload event with 97% CPU utilization, 45% steal time,
thread pool exhaustion, and OOM killer activity. The agent detects `high_cpu` and
`resource_exhaustion`, assigns CRITICAL severity, and returns a runbook covering
process profiling, auto-scaling validation, and load shedding.

### db_connection_error.json — PostgreSQL Connection Exhaustion

Simulates a database connection pool completely exhausted with max_connections reached
on the PostgreSQL server. Circuit breakers are open and the service is failing 100% of
requests. The agent detects `database_failure` and `service_unavailable`, assigns
CRITICAL severity, and returns a PostgreSQL-specific runbook with live query termination
and PgBouncer remediation steps.

---

## Output Report Explanation

The report (`reports/incident-analysis.md`) contains:

| Section | Description |
|---------|-------------|
| **Incident Summary** | Service, environment, timestamp, and source file |
| **Severity** | CRITICAL / HIGH / MEDIUM / LOW |
| **Root Cause** | Human-readable root cause explanation |
| **Recommended Fix** | Concise top-level remediation action |
| **Detected Categories** | Issue categories identified by the rule engine |
| **Runbook Steps** | Ordered operational steps for the primary (and secondary) category |
| **AI Expert Insights** | (AI mode only) Additional context from the language model |
| **Metrics Snapshot** | All metrics from the incident payload |
| **Recent Log Entries** | Last 10 log lines from the incident |

---

## Detection Categories

| Category | Trigger Signals |
|----------|----------------|
| `network_failure` | Connection refused, 502/504 errors, SSL failures, upstream errors |
| `database_failure` | Connection pool exhaustion, max_connections, circuit breaker open |
| `high_cpu` | CPU > 90%, high load average, CPU steal, thread pool exhaustion |
| `resource_exhaustion` | OOM killer, memory > 90%, disk full, queue depth > 1000 |
| `service_unavailable` | Health check failure, 503, CrashLoopBackOff, process termination |

---

## Future Improvements

- **Multi-incident correlation**: Detect cascading failure patterns across concurrent incidents.
- **Prometheus/Grafana integration**: Pull live metrics directly for real-time analysis.
- **PagerDuty / OpsGenie webhook receiver**: Accept alerts directly from alerting systems.
- **Slack / Teams notification**: Post analysis summaries to incident channels automatically.
- **Historical baseline comparison**: Compare current metrics against rolling baselines to improve severity scoring.
- **Custom runbook YAML**: Allow teams to define their own runbooks in YAML and load them at runtime.
- **Kubernetes operator mode**: Run as a K8s controller watching for pod events and auto-analyzing failures.
- **Multi-model support**: Support OpenAI, Bedrock, and local Ollama models alongside Claude.
- **Confidence scoring tuning**: Train a lightweight classifier on historical incidents to improve pattern weights.
- **Report diff mode**: Compare two incident reports to identify recurring patterns across postmortems.

---

## Author

DevOps AI Portfolio — Task 10
Senior DevOps / SRE / AI Systems Architecture
