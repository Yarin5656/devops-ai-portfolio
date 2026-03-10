# Task 9 — Auto Scaling Simulation

A professional-grade, rule-based autoscaling simulation system written in Python.
Evaluates multi-signal workload metrics and recommends scaling actions for container replica sets (e.g. Kubernetes Deployments, ECS Services).

---

## Project Overview

Real-world autoscalers (Kubernetes HPA, KEDA, AWS Application Auto Scaling) make decisions by combining multiple workload signals. This project simulates that process:

1. **Load** a JSON metrics snapshot describing the current workload state.
2. **Evaluate** multiple signals — CPU, memory, request rate, queue depth, latency, and error rate.
3. **Recommend** a scaling action: `scale_up`, `scale_down`, or `no_change`.
4. **Publish** a structured Markdown report for audit trails and post-incident review.

---

## Project Structure

```
task-9-auto-scaling-simulation/
├── scaler/
│   ├── main.py              # CLI entry point
│   ├── metrics_parser.py    # JSON loader + validator
│   ├── decision_engine.py   # Multi-signal rule engine
│   └── report_generator.py  # Markdown report writer
├── sample_metrics/
│   ├── high_cpu.json        # Scenario: sustained high CPU + high RPS
│   ├── low_load.json        # Scenario: very low utilisation
│   └── queue_spike.json     # Scenario: message queue spike
├── reports/
│   └── scaling-report.md    # Auto-generated (after first run)
├── requirements.txt
└── README.md
```

---

## Autoscaling Logic Explanation

The decision engine (`decision_engine.py`) operates in four ordered phases:

### Phase 1 — Emergency Scale-Up (critical threshold breached)
Any **single** metric that crosses a critical threshold triggers an immediate, aggressive scale-up:

| Signal | Critical Threshold |
| --- | --- |
| CPU | ≥ 90% |
| Memory | ≥ 90% |
| Queue Depth | ≥ 2,000 items |

Scale factor: **×1.75** (one critical signal) or **×2.0** (two or more).

### Phase 2 — Compound Scale-Up (two+ elevated signals)
If two or more metrics are elevated (but not critical), a moderate scale-up is applied:

| Signal | Elevated Threshold |
| --- | --- |
| CPU | ≥ 80% |
| Memory | ≥ 80% |
| Request Rate | ≥ 800 req/min |
| Queue Depth | ≥ 500 items |
| Avg Response Time | ≥ 2,000 ms |
| Error Rate | ≥ 5% |

Scale factor: **×1.5 – ×2.0** (scales with number of signals fired).

### Phase 3 — Cautious Scale-Up (single elevated signal)
One elevated signal is not enough for a large scale event; a gentle **×1.25** bump is applied and flagged as low confidence.

### Phase 4 — Scale-Down (sustained low utilisation)
Requires **two or more** low signals to prevent premature trim:

| Signal | Low Threshold |
| --- | --- |
| CPU | < 25% |
| Memory | < 35% |
| Request Rate | < 100 req/min |
| Queue Depth | < 10 items |

Scale factor: **×0.65** (two low signals) or **×0.50** (three+ low signals).
Minimum replica floor: **1** pod. Maximum replica ceiling: **50** pods.

### Phase 5 — No Change
All metrics are within acceptable operating bounds. Replica count is held stable.

---

## Example Inputs

### `sample_metrics/high_cpu.json`
```json
{
  "service": "api-gateway",
  "environment": "production",
  "timestamp": "2026-01-15T14:30:00Z",
  "cpu_utilization": 88,
  "memory_utilization": 72,
  "request_rate": 1250,
  "queue_depth": 45,
  "current_replicas": 4,
  "avg_response_time_ms": 850,
  "error_rate": 0.032
}
```

### `sample_metrics/low_load.json`
```json
{
  "service": "api-gateway",
  "environment": "production",
  "timestamp": "2026-01-15T03:00:00Z",
  "cpu_utilization": 11,
  "memory_utilization": 27,
  "request_rate": 42,
  "queue_depth": 1,
  "current_replicas": 8,
  "avg_response_time_ms": 115,
  "error_rate": 0.001
}
```

### `sample_metrics/queue_spike.json`
```json
{
  "service": "message-processor",
  "environment": "production",
  "timestamp": "2026-01-15T09:15:00Z",
  "cpu_utilization": 54,
  "memory_utilization": 62,
  "request_rate": 310,
  "queue_depth": 2850,
  "current_replicas": 3,
  "avg_response_time_ms": 4300,
  "error_rate": 0.079
}
```

---

## Example Decisions

| Scenario | Decision | Replicas | Key Signals |
| --- | --- | --- | --- |
| `high_cpu.json` | `scale_up` | 4 → 6 | CPU_HIGH, RPS_HIGH |
| `low_load.json` | `scale_down` | 8 → 4 | CPU_LOW, MEM_LOW, RPS_LOW, QUEUE_LOW |
| `queue_spike.json` | `scale_up` | 3 → 6 | QUEUE_CRITICAL, LATENCY_HIGH, ERROR_RATE_HIGH |

---

## How to Run

**Prerequisites:** Python 3.9+. No third-party packages required.

### Run against a single scenario
```bash
# From the task root directory:
python scaler/main.py --file sample_metrics/high_cpu.json
python scaler/main.py --file sample_metrics/low_load.json
python scaler/main.py --file sample_metrics/queue_spike.json
```

### Start a fresh report (reset previous output)
```bash
python scaler/main.py --file sample_metrics/high_cpu.json --reset-report
```

### Dry-run (no report written)
```bash
python scaler/main.py --file sample_metrics/queue_spike.json --no-report
```

### Run all scenarios in sequence
```bash
python scaler/main.py --file sample_metrics/high_cpu.json --reset-report
python scaler/main.py --file sample_metrics/low_load.json
python scaler/main.py --file sample_metrics/queue_spike.json
```

---

## Report Format

The generated report at `reports/scaling-report.md` is structured as:

```
# Autoscaling Simulation Report
Generated: <UTC timestamp>

---

## 🔺 SCALE UP — `api-gateway` (production)
**Evaluated:** 2026-01-15T14:30:00Z
**Source file:** `sample_metrics/high_cpu.json`

### Input Metrics
| Metric | Value |
| --- | --- |
| CPU Utilization | 88.0% |
...

### Decision
| Field | Value |
| --- | --- |
| Decision | `scale_up` |
| Recommended Replicas | 6 |
| Change | 4 → 6 (+2) |

**Reason:** ...
> **Risk Note:** ...

**Signals fired:**
- `CPU_HIGH`
- `RPS_HIGH`

---
```

---

## Metric File Schema

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `cpu_utilization` | float (0–100) | Yes | CPU usage percentage |
| `memory_utilization` | float (0–100) | Yes | Memory usage percentage |
| `request_rate` | float | Yes | Requests per minute |
| `queue_depth` | int | Yes | Number of items in the message queue |
| `current_replicas` | int | Yes | Current running pod count |
| `service` | string | No | Service or workload name |
| `environment` | string | No | Deployment environment |
| `timestamp` | ISO 8601 | No | Metric collection time |
| `avg_response_time_ms` | float | No | Average response latency in milliseconds |
| `error_rate` | float (0.0–1.0) | No | Fraction of requests returning errors |

---

## Future Improvements

1. **Time-series awareness** — Ingest a rolling window of metric samples rather than a single snapshot; apply cooldown periods and trend analysis (e.g. EWMA) to avoid flapping.

2. **Predictive scaling** — Integrate a simple linear-regression or LSTM model trained on historical traffic patterns to pre-scale before demand peaks.

3. **KEDA / HPA YAML export** — Translate the recommended replica count directly into Kubernetes `HorizontalPodAutoscaler` or KEDA `ScaledObject` patch manifests ready for `kubectl apply`.

4. **Multi-service orchestration** — Accept a directory of metric files, evaluate each service, and emit a unified scaling plan respecting inter-service dependencies and cluster-wide resource budgets.

5. **Prometheus integration** — Replace JSON files with a live Prometheus query (`/api/v1/query`) so the tool can be scheduled as a CronJob and feed recommendations into GitOps workflows.

6. **Slack / PagerDuty alerts** — Emit webhook notifications when a critical scale-up decision is taken, giving SREs real-time visibility without waiting for the report.

7. **Cost estimation** — Attach cloud pricing data (AWS, GCP, Azure instance types) to compute the estimated hourly cost delta of each scaling recommendation.

8. **Dry-run Kubernetes integration** — Use `kubectl scale --dry-run=server` to validate that a replica change is feasible against the live cluster before committing.
