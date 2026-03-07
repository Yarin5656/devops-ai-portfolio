# Auto-Healing DevOps System

A modular Python-based DevOps tool that detects service failures from log files
and automatically triggers simulated recovery actions — with an optional AI layer
powered by Claude for deep root-cause analysis.

---

## Project Idea

Modern production systems generate thousands of log lines per minute. When a
failure occurs, the mean time to resolution (MTTR) is dominated by the time it
takes an engineer to notice, diagnose, and act. This project simulates an
auto-healing pipeline:

1. **Detect** — scan logs for known failure signatures
2. **Classify** — map failure types to proven healing actions via a rule engine
3. **Analyse** — optionally call Claude to generate a root-cause explanation
4. **Heal** — simulate the recovery action (safe, no real system commands)
5. **Report** — produce a Markdown healing report for audit and review

---

## Architecture

```
main.py              ← CLI entry point, orchestrates the pipeline
│
├── failure_detector.py  ← keyword-based log scanner, returns FailureEvent list
├── rule_engine.py       ← maps failure types to HealingPrescription objects
├── healer.py            ← simulates recovery actions, returns HealingOutcome list
├── ai_engine.py         ← Claude API integration with rule-based fallback
└── reporter.py          ← renders a Markdown healing report

sample_logs/         ← realistic synthetic log files for demonstration
reports/             ← generated Markdown healing reports (git-ignored)
```

Each module is independently testable and loosely coupled via plain dataclasses.

---

## How to Run

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

The only runtime dependency is the `anthropic` SDK (for `--ai` mode).
The base system works with no dependencies at all.

### 2. Basic usage — rule-based healing

```bash
python main.py --log sample_logs/service_crash.log
python main.py --log sample_logs/disk_full.log
python main.py --log sample_logs/memory_spike.log
```

### 3. AI-powered analysis

```bash
export ANTHROPIC_API_KEY="your-api-key"
python main.py --log sample_logs/service_crash.log --ai
```

Without an API key the system falls back to rule-based analysis automatically.

### 4. Detect-only (no healing)

```bash
python main.py --log sample_logs/disk_full.log --no-heal
```

### 5. Verbose debug logging

```bash
python main.py --log sample_logs/memory_spike.log --ai --verbose
```

### Full CLI reference

```
usage: main.py --log PATH [--ai] [--no-heal] [--report-dir DIR] [--verbose]

Options:
  --log PATH        Path to the log file to analyse (required)
  --ai              Enable AI root-cause analysis via Claude API
  --no-heal         Classify failures but skip simulated healing
  --report-dir DIR  Directory for Markdown reports (default: reports/)
  --verbose, -v     Enable debug-level logging
```

---

## Example Healing Scenarios

### Scenario 1 — Service Crash (`service_crash.log`)

| Stage | Detail |
|-------|--------|
| Detected | `service_crash` — keyword: `crashed` / `segmentation fault` |
| Classification | restart_service |
| Healing action | Send SIGTERM → wait for shutdown → restart via service manager |
| Permanent fix | Add process supervisor with auto-restart and memory limits |

### Scenario 2 — Disk Full (`disk_full.log`)

| Stage | Detail |
|-------|--------|
| Detected | `disk_full` — keyword: `disk full` / `no space left` |
| Classification | run_cleanup |
| Healing action | Purge old logs, compress archives, reclaim disk space |
| Permanent fix | Enable logrotate, add disk-usage alerting at 75% / 90% |

### Scenario 3 — Memory Spike (`memory_spike.log`)

| Stage | Detail |
|-------|--------|
| Detected | `memory_spike` — keyword: `out of memory` / `oom killer` |
| Classification | restart_container |
| Healing action | Stop container → prune → restart with updated memory limits |
| Permanent fix | Set container limits, profile for memory leaks |

---

## Sample Output

```
============================================================
   Auto-Healing DevOps System
   Failure Detection + Simulated Recovery
============================================================

[1/4] Scanning log file: sample_logs/service_crash.log

  3 failure event(s) detected: connection_refused, service_crash
  Highest severity: CRITICAL
    [Line 4] SERVICE_CRASH (severity=critical) — matched 'segmentation fault'
    [Line 5] SERVICE_CRASH (severity=critical) — matched 'crashed'
    [Line 8] CONNECTION_REFUSED (severity=high) — matched 'connection refused'

[2/4] Classifying failures via rule engine...
  service_crash             → Restart the crashed service
  connection_refused        → Restart the failing dependency service

[3/4] AI analysis skipped (use --ai to enable).

[4/4] Triggering simulated healing actions...

  [Healing] Restart the crashed service (service: nginx)
    > Sending SIGTERM to nginx process...
    > Waiting for nginx to shut down gracefully...
    > Starting nginx via service manager...
    > nginx is back online — health check passed.
  ...

  Healing report written to: reports/service_crash_healing_report_20240307_081500.md
```

---

## Generated Report

Each run produces a Markdown report in `reports/` containing:

- Failure summary table (line number, type, severity, service, keyword)
- Per-failure healing steps executed
- AI or rule-based root-cause explanation
- Suggested permanent fix
- Overall healing status

---

## Future Improvements

| Area | Improvement |
|------|-------------|
| **Input** | Tail live log files in real-time with `inotify` / `watchdog` |
| **Rules** | Load rules from a YAML/JSON file — no code changes needed |
| **Healing** | Integrate with real orchestrators (Kubernetes, systemd, ECS) |
| **AI** | Add multi-turn conversation for iterative diagnosis |
| **Alerting** | Push incidents to PagerDuty, Slack, or OpsGenie |
| **Testing** | Full pytest suite with mocked log inputs |
| **Metrics** | Export MTTR, failure frequency, and heal rate to Prometheus |
| **UI** | Simple web dashboard with healing history |

---

## Project Structure

```
task-2/
├── main.py               # CLI entry point
├── failure_detector.py   # Log scanner and FailureEvent extractor
├── rule_engine.py        # Failure → prescription rule table
├── healer.py             # Simulated healing action dispatcher
├── ai_engine.py          # Claude API integration with fallback
├── reporter.py           # Markdown report generator
├── requirements.txt      # Python dependencies
├── sample_logs/
│   ├── service_crash.log
│   ├── disk_full.log
│   └── memory_spike.log
└── reports/              # Auto-generated healing reports
```

---

_Part of the DevOps AI Portfolio — built with Python and Claude._
