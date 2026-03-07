# DevOps AI Portfolio

A growing collection of production-grade DevOps tools and automation projects,
each demonstrating a distinct area of the modern infrastructure engineering stack.

Every task is self-contained, runnable locally, and built to portfolio quality —
clean architecture, proper error handling, logging, and documentation.

---

## Projects

| # | Folder | Title | Stack | Status |
|---|--------|-------|-------|--------|
| 1 | [`task-1-log-analyzer/`](./task-1-log-analyzer/) | AI DevOps Log Analyzer | Python · Anthropic Claude · Regex rule engine | Complete |
| 2 | [`task-2-auto-healing-system/`](./task-2-auto-healing-system/) | Auto-Healing DevOps System | Python · Anthropic Claude · Rule engine · Simulated healing | Complete |

---

## Task 1 — AI DevOps Log Analyzer

> **Location:** `task-1-log-analyzer/`

A CLI tool that parses infrastructure, deployment, and system logs and produces
a structured Markdown diagnostic report including:

- Automatic error classification (network / permissions / dependency / configuration / infrastructure)
- Rule-based root cause analysis (zero external dependencies)
- Optional AI-enhanced analysis via Anthropic Claude (`--ai` flag)
- Graceful fallback when the API key is absent or the call fails
- Evidence lines with line numbers
- Full Markdown report written to `reports/report.md`

**Quick start:**

```bash
cd task-1-log-analyzer
python main.py --log sample_logs/deploy_failure.log
python main.py --log sample_logs/deploy_failure.log --ai   # requires ANTHROPIC_API_KEY
```

---

## Task 2 — Auto-Healing DevOps System

> **Location:** `task-2-auto-healing-system/`

A modular Python system that detects service failures from log files and automatically
triggers simulated self-healing actions, including:

- Keyword-based failure detection (crash, OOM, disk full, connection refused, timeout)
- Rule engine that maps failure types to specific healing prescriptions
- Simulated healing actions (restart service, restart container, disk cleanup, scale out)
- Optional AI-powered root-cause analysis via Anthropic Claude (`--ai` flag)
- Graceful rule-based fallback when AI is unavailable
- Timestamped Markdown healing reports written to `reports/`

**Quick start:**

```bash
cd task-2-auto-healing-system
pip install -r requirements.txt
python main.py --log sample_logs/service_crash.log
python main.py --log sample_logs/disk_full.log --ai        # requires ANTHROPIC_API_KEY
python main.py --log sample_logs/memory_spike.log
```

---

## Roadmap

| # | Title | Area |
|---|-------|------|
| 3 | Local AWS Infrastructure with LocalStack | Cloud / IaC |
| 4 | CI/CD Pipeline Automation | Pipelines |
| 5 | Monitoring and Alerting Stack | Observability |
| 6 | Kubernetes Deployment System | Container orchestration |
| 7 | DevOps Incident Bot | ChatOps / AI |
| 8 | Infrastructure Security Scanner | Security |
| 9 | Auto Scaling Simulation | Resilience |
| 10 | AI DevOps Agent | AI / Automation |

---

## Author

**Yarin** — DevOps Engineer
[github.com/Yarin5656](https://github.com/Yarin5656)
