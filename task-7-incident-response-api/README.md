# Task 7 — Incident Response API

A production-grade REST API that accepts infrastructure or application incident payloads, classifies the problem category, and returns structured remediation guidance along with SRE runbook steps.

Built with **FastAPI**, designed to run standalone or inside a Kubernetes cluster, and optionally enriched with **Claude AI** for deeper root-cause analysis.

---

## Project Overview

When an alert fires at 3 AM, the on-call engineer needs answers fast:

- *What category of problem is this?*
- *How severe is it?*
- *What should I do first?*

This service answers those questions automatically by analysing raw log messages and returning:

| Field | Description |
|---|---|
| `category` | `network`, `permissions`, `dependency`, `timeout`, `resource`, `unknown` |
| `severity` | `low`, `medium`, `high`, `critical` |
| `root_cause` | One-sentence technical explanation |
| `recommended_fix` | Immediate remediation action |
| `runbook_steps` | Ordered SRE operational steps |
| `analysis_mode` | `rule_based` or `ai_enhanced` |

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     FastAPI (main.py)                    │
│                                                          │
│  POST /analyze-incident                                  │
│       │                                                  │
│       ▼                                                  │
│  ┌─────────────┐    always runs    ┌──────────────────┐  │
│  │ rule_engine │ ────────────────► │ runbook_engine   │  │
│  │  (schemas)  │                   │ (per-category    │  │
│  └─────────────┘                   │  runbook steps)  │  │
│       │                            └──────────────────┘  │
│       │ optional (if ANTHROPIC_API_KEY set)              │
│       ▼                                                  │
│  ┌─────────────┐                                         │
│  │  ai_engine  │ ── Claude API ──► enriched root_cause   │
│  │ (graceful   │                   + recommended_fix     │
│  │  fallback)  │                                         │
│  └─────────────┘                                         │
└──────────────────────────────────────────────────────────┘
```

### Components

| File | Role |
|---|---|
| `app/main.py` | FastAPI app, route handlers, logging |
| `app/schemas.py` | Pydantic request/response models, enums |
| `app/rule_engine.py` | Regex pattern matching → category + severity |
| `app/runbook_engine.py` | Category → ordered operational runbook steps |
| `app/ai_engine.py` | Optional Claude API enrichment with graceful fallback |
| `tests/test_api.py` | Full pytest test suite using FastAPI TestClient |

---

## Example API Request / Response

### Request

```bash
curl -X POST http://localhost:8000/analyze-incident \
  -H "Content-Type: application/json" \
  -d '{
    "source": "nginx",
    "environment": "staging",
    "log": "connection refused to upstream service"
  }'
```

### Response

```json
{
  "category": "network",
  "severity": "high",
  "root_cause": "Network-layer failure preventing the service from reaching its upstream or dependency.",
  "recommended_fix": "Verify network policies, service endpoints, DNS resolution, and firewall rules between components.",
  "runbook_steps": [
    "1. Confirm the affected service is listed as healthy in your service registry (Consul/k8s endpoints).",
    "2. Test connectivity: `curl -v <upstream-host>:<port>` or `nc -zv <host> <port>`.",
    "3. Inspect DNS resolution: `dig <hostname>` / `nslookup <hostname>` from inside the pod/container.",
    "4. Review network policies (Kubernetes NetworkPolicy, AWS Security Groups, iptables rules).",
    "5. Check firewall and load balancer logs for dropped packets or backend-unavailable errors.",
    "6. If upstream is a k8s Service, verify Endpoints object has ready addresses: `kubectl get endpoints <svc>`.",
    "7. Review recent infrastructure changes (Terraform plan/apply, AMI replacements, VPC routing changes).",
    "8. Escalate to network/platform team if no root cause is found within 15 minutes."
  ],
  "analysis_mode": "rule_based",
  "source": "nginx",
  "environment": "staging"
}
```

### Additional Example — OOM Resource Incident

```bash
curl -X POST http://localhost:8000/analyze-incident \
  -H "Content-Type: application/json" \
  -d '{
    "source": "api-gateway",
    "environment": "production",
    "log": "OOM killer invoked: out of memory, process killed"
  }'
```

Returns `category: resource`, `severity: critical`.

---

## Local Run Instructions

### Prerequisites

- Python 3.12+
- pip

### Setup

```bash
cd task-7-incident-response-api

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Run the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now available at `http://localhost:8000`.
Interactive docs (Swagger UI): `http://localhost:8000/docs`

### Optional — AI Enrichment

Set your Anthropic API key to enable Claude-powered analysis:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn app.main:app --reload
```

When the key is present the `analysis_mode` field in the response will read `ai_enhanced`.

---

## Test Instructions

```bash
# From the task-7-incident-response-api directory
pytest tests/ -v
```

Expected output: all tests pass without any external service dependencies.

---

## Docker Build / Run Instructions

### Build

```bash
docker build -t incident-response-api:1.0.0 .
```

### Run

```bash
docker run -p 8000:8000 incident-response-api:1.0.0
```

### Run with AI enrichment

```bash
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  incident-response-api:1.0.0
```

### Tune workers and log level

```bash
docker run -p 8000:8000 \
  -e WORKERS=4 \
  -e LOG_LEVEL=warning \
  incident-response-api:1.0.0
```

### Health check

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

## Future Improvements

1. **Webhook / alerting integration** — POST classified incidents to PagerDuty, OpsGenie, or Slack automatically.
2. **Incident history store** — persist incidents to PostgreSQL/Redis with deduplication and trend analysis.
3. **Severity auto-escalation** — automatically page on-call if severity is `critical` and no acknowledgement within N minutes.
4. **Multi-signal correlation** — accept batches of logs and correlate cross-service incidents into a single root cause.
5. **Feedback loop** — allow engineers to mark classifications as correct/incorrect and retrain the rule weights over time.
6. **OpenTelemetry tracing** — instrument each analysis pipeline stage with spans for latency profiling.
7. **Kubernetes deployment manifest** — Helm chart with HPA, PodDisruptionBudget, and NetworkPolicy.
8. **Authentication** — JWT or mTLS enforcement to restrict API access to authorised internal callers only.
