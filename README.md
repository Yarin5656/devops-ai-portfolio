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

## Roadmap

| # | Title | Area |
|---|-------|------|
| 2 | _Coming soon_ | CI/CD pipeline automation |
| 3 | _Coming soon_ | Infrastructure-as-Code linting & drift detection |
| 4 | _Coming soon_ | Kubernetes observability dashboard |

---

## Author

**Yarin** — DevOps Engineer
[github.com/Yarin5656](https://github.com/Yarin5656)
