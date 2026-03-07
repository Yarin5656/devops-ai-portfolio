# AI DevOps Log Analyzer

A professional CLI tool that parses infrastructure, deployment, and system logs
and produces a structured Markdown diagnostic report — including root cause analysis,
impact assessment, recommended diagnostic checks, and actionable remediation steps.

Rule-based analysis runs by default with zero external dependencies. An optional
`--ai` flag enriches the report with a second opinion from Anthropic Claude when
an API key is available.

---

## Architecture

```
┌─────────────┐
│   main.py   │  CLI entry point — orchestrates the pipeline
└──────┬──────┘
       │
       ▼
┌──────────────┐    ┌──────────────────────────────────────────────┐
│ log_parser   │───▶│ ParsedLog                                    │
│ .py          │    │  raw_lines, error_lines, primary_error_block │
└──────────────┘    │  detected_indicators, total_lines            │
                    └────────────────┬─────────────────────────────┘
                                     │
                    ┌────────────────▼─────────────────────────────┐
                    │ rule_engine.py  (always runs)                │
                    │  Ordered regex rules → RuleMatch             │
                    │  category | root_cause | impact | fixes      │
                    └────────────────┬─────────────────────────────┘
                                     │
                    ┌────────────────▼─────────────────────────────┐
                    │ ai_engine.py  (only with --ai flag)          │
                    │  Calls Anthropic Claude API → AIAnalysis     │
                    │  Graceful fallback → AIEngineResult.status   │
                    └────────────────┬─────────────────────────────┘
                                     │
                    ┌────────────────▼─────────────────────────────┐
                    │ report_generator.py                          │
                    │  Renders both results into reports/report.md │
                    │  Rule section always present                 │
                    │  AI section shown / fallback note as needed  │
                    └──────────────────────────────────────────────┘
```

### Component Breakdown

| File | Responsibility |
|---|---|
| `main.py` | CLI argument parsing, pipeline orchestration, console output |
| `log_parser.py` | Reads log files, scores/prioritises error lines, extracts primary error context window |
| `rule_engine.py` | Ordered deterministic rules mapping patterns → category, root cause, impact, fixes |
| `ai_engine.py` | Anthropic Claude API call with typed result (`AIEngineResult`), full graceful fallback |
| `report_generator.py` | Composes two separate labelled sections in the Markdown report |

### Error Categories

| Category | Triggered By |
|---|---|
| `network` | connection refused, ECONNREFUSED, timed out, ETIMEDOUT, deadline exceeded |
| `permissions` | permission denied, access denied, EACCES, PermissionError |
| `dependency` | ModuleNotFoundError, ImportError, no module named, package not found |
| `configuration` | invalid config, missing env var, YAML/JSON parse error, syntax error |
| `infrastructure` | OOMKilled, disk full, ENOSPC, killed process, cannot allocate memory |

---

## Requirements

- **Python 3.9+**
- **No external packages** required for standard (rule-based) mode
- For AI mode: `pip install anthropic`

---

## Installation

```bash
git clone <repository-url>
cd task-1

# Optional but recommended: create a virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate         # Windows

# Install AI dependency (only needed for --ai mode)
pip install anthropic
```

---

## Usage

### Standard mode — rule-based analysis, no API key needed

```bash
python main.py --log sample_logs/deploy_failure.log
python main.py --log sample_logs/network_error.log
python main.py --log sample_logs/permission_error.log
```

The rule engine always runs. Reports are written to `reports/report.md`.

---

### AI-enhanced mode

#### Step 1 — Set your Anthropic API key

```bash
# Linux / macOS
export ANTHROPIC_API_KEY="sk-ant-api03-..."

# Windows (Command Prompt)
set ANTHROPIC_API_KEY=sk-ant-api03-...

# Windows (PowerShell)
$env:ANTHROPIC_API_KEY = "sk-ant-api03-..."
```

You can obtain an API key from [console.anthropic.com](https://console.anthropic.com).

#### Step 2 — Run with `--ai`

```bash
python main.py --log sample_logs/deploy_failure.log --ai
```

Both the rule engine **and** Claude will analyse the log. The report will contain
two separate, labelled sections so you can compare the outputs side by side.

---

### How the AI fallback works

The `--ai` flag is a request, not a requirement. The tool handles every failure
mode without interrupting the pipeline:

| Condition | Behaviour |
|---|---|
| `ANTHROPIC_API_KEY` not set | Skips AI, rule result is authoritative, report shows fallback note |
| `anthropic` package not installed | Same as above — prompts `pip install anthropic` |
| API authentication error | Same — check your key |
| API rate limit / network error | Same — transient, retry later |
| Malformed JSON response | Same — validates schema before accepting |
| No error lines in log | Same — AI is not called when there is nothing to analyse |

The report's **AI-Enhanced Analysis** section will always appear when `--ai` is
passed — either with the full AI output, or with a clear human-readable explanation
of why it is unavailable.

---

### All CLI options

```bash
python main.py \
  --log sample_logs/deploy_failure.log \
  --ai \
  --report-dir /tmp/my-reports \
  --verbose
```

| Flag | Default | Description |
|---|---|---|
| `--log FILE` | _(required)_ | Path to the log file to analyse |
| `--ai` | off | Enable Claude AI analysis (graceful fallback if key absent) |
| `--report-dir DIR` | `reports/` | Output directory for the Markdown report |
| `--verbose` | off | Enable DEBUG-level logging to stderr |

---

## Output

### Console (standard mode)

```
============================================================
  AI DevOps Log Analyzer
============================================================

[1/4] Parsing log file: sample_logs/deploy_failure.log
      34 lines read, 13 error line(s) detected, 5 indicator(s) matched.
[2/4] Running rule-based analysis …
      Rule 'module_not_found' matched — category: dependency, confidence: high.

[3/4] Analysis summary
  Category    : dependency
  Rule engine : module_not_found (confidence: high)
  Root Cause  : The application tried to import a library or module that is not installed …

[4/4] Generating report …
  Report written to: reports/report.md
```

### Console (AI mode — key present)

```
[2/4] Running rule-based analysis …
      Rule 'module_not_found' matched — category: dependency, confidence: high.
      Attempting AI-enhanced analysis …
      AI analysis complete — category: dependency, confidence: high.
```

### Console (AI mode — key absent)

```
[2/4] Running rule-based analysis …
      Rule 'module_not_found' matched — category: dependency, confidence: high.
      Attempting AI-enhanced analysis …
      AI analysis unavailable (no_key) — rule-based result is authoritative.
```

### Report structure (`reports/report.md`)

```markdown
# AI DevOps Log Analyzer — Diagnostic Report

| Log File | deploy_failure.log |
| Generated | 2026-03-07 13:00:00 UTC |
...

## Summary
...

## Detected Error
Primary error + ±5 line context block

---

## Rule-Based Analysis
> Deterministic pattern matching. Always runs.

Root Cause | Impact | Suggested Fixes

---

## AI-Enhanced Analysis            ← only when --ai is passed
> Powered by Anthropic Claude.

Root Cause | Impact | Recommended Checks | Suggested Fixes
(or fallback note if AI is unavailable)

---

## Evidence Lines
All matched error lines with line numbers
```

---

## Sample Logs

| File | Scenario | Expected Category |
|---|---|---|
| `sample_logs/deploy_failure.log` | Kubernetes CrashLoopBackOff — `ModuleNotFoundError: No module named 'pandas'` | `dependency` |
| `sample_logs/network_error.log` | Microservice ECONNREFUSED to inventory-service (OOMKilled pod) | `network` |
| `sample_logs/permission_error.log` | Backup agent blocked by filesystem and PostgreSQL permission errors | `permissions` |

---

## Design Decisions

**Rule engine is always authoritative.** The AI section is explicitly labelled
as supplementary. Engineers should validate AI suggestions before applying them.

**Typed AI result.** `analyse_with_ai()` returns `AIEngineResult` (never `None`).
The `status` field is a typed string constant; `detail` is a human-readable sentence
ready for inclusion in the Markdown report. This makes the fallback logic in
`main.py` trivial and the report always complete.

**Focused API context.** Only the primary error block and unique error lines are
sent to the API (capped at 60 lines). This keeps token usage predictable, costs
low, and latency acceptable.

**Rule hint in prompt.** The rule engine category is passed to the AI prompt as a
non-binding hint. This improves classification agreement while still allowing the
AI to disagree if the evidence warrants a different category.

**No cloud dependencies.** The tool runs entirely locally. For future AWS
simulation requirements, LocalStack is the prescribed integration point.

---

## Project Structure

```
task-1/
├── main.py                    # CLI entry point and pipeline orchestrator
├── log_parser.py              # Log file reader and error extractor
├── rule_engine.py             # Rule-based classification and RCA engine
├── ai_engine.py               # Anthropic Claude integration with typed fallback
├── report_generator.py        # Markdown report builder (dual-section output)
├── README.md                  # This file
├── sample_logs/
│   ├── deploy_failure.log     # Kubernetes deploy failure — missing Python package
│   ├── network_error.log      # Microservice connectivity failure — ECONNREFUSED
│   └── permission_error.log   # Backup agent — filesystem + PostgreSQL permissions
└── reports/
    └── report.md              # Generated diagnostic report (created at runtime)
```

---

## Future Improvements

- **LocalStack integration** — stream logs from simulated S3 / CloudWatch via LocalStack
- **Batch mode** — accept a glob pattern and produce an aggregated multi-log report
- **Slack / PagerDuty webhook** — post the summary directly to an incident channel
- **Historical trending** — store results in SQLite to surface recurring error patterns
- **Web UI** — lightweight FastAPI + HTMX interface for drag-and-drop log upload
- **Additional log formats** — native parsers for JSON-structured logs, syslog RFC 5424, CloudTrail
- **Plugin system** — allow teams to ship custom rule sets as Python packages
