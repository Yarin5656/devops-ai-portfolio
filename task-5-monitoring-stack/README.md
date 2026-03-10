# Task 5 — Monitoring and Alerting Stack

A production-style local monitoring stack built with **Flask**, **Prometheus**, and **Grafana**.
Designed as a portfolio demonstration of DevOps/SRE observability best practices.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Network: monitoring            │
│                                                         │
│  ┌──────────────┐        ┌──────────────┐              │
│  │  Flask App   │◄──────►│  Prometheus  │              │
│  │  :5000       │ scrape │  :9090       │              │
│  │              │        │              │              │
│  │  /           │        │  15s scrape  │              │
│  │  /health     │        │  interval    │              │
│  │  /metrics    │        └──────┬───────┘              │
│  └──────────────┘               │ query                │
│                                 ▼                       │
│                          ┌──────────────┐              │
│                          │   Grafana    │              │
│                          │   :3000      │              │
│                          │              │              │
│                          │  Auto-loaded │              │
│                          │  dashboard   │              │
│                          └──────────────┘              │
└─────────────────────────────────────────────────────────┘
```

| Component  | Role                                              | Port |
|------------|---------------------------------------------------|------|
| Flask app  | Demo service exposing HTTP endpoints + `/metrics` | 5000 |
| Prometheus | Metrics collection and storage (TSDB)             | 9090 |
| Grafana    | Visualization and dashboarding                    | 3000 |

---

## Collected Metrics

| Metric                                    | Type      | Labels                          | Description                        |
|-------------------------------------------|-----------|---------------------------------|------------------------------------|
| `http_requests_total`                     | Counter   | `method`, `endpoint`, `http_status` | Total HTTP requests per endpoint |
| `http_request_duration_seconds`           | Histogram | `method`, `endpoint`            | Request latency with buckets       |
| `health_check_requests_total`             | Counter   | —                               | Dedicated /health call counter     |

---

## How to Run

### Prerequisites
- Docker Desktop (or Docker Engine + Compose plugin)

### Start the stack

```bash
cd task-5-monitoring-stack
docker compose up -d
```

### Stop the stack

```bash
docker compose down
```

### Remove volumes (clean slate)

```bash
docker compose down -v
```

---

## Accessing Services

| Service    | URL                        | Credentials         |
|------------|----------------------------|---------------------|
| Flask app  | http://localhost:5000      | —                   |
| Flask /health | http://localhost:5000/health | —               |
| Flask /metrics | http://localhost:5000/metrics | —             |
| Prometheus | http://localhost:9090      | —                   |
| Grafana    | http://localhost:3000      | admin / admin       |

---

## Grafana Dashboard

The **Flask App Overview** dashboard is auto-provisioned on startup.

Panels included:
- **Total Requests** — cumulative request count (stat)
- **Request Rate (5m)** — current req/s (stat)
- **P95 Latency** — 95th percentile response time (stat)
- **Health Checks** — total `/health` calls (stat)
- **Request Rate by Endpoint** — time-series per endpoint
- **Request Duration Percentiles** — p50 / p95 / p99 over time
- **Total Requests by Status Code** — breakdown by HTTP status

---

## Project Structure

```
task-5-monitoring-stack/
├── app/
│   ├── Dockerfile          # Multi-stage Python 3.12 image
│   ├── main.py             # Flask app + Prometheus instrumentation
│   └── requirements.txt    # Python dependencies
├── prometheus/
│   └── prometheus.yml      # Scrape config (app:5000/metrics)
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── datasource.yml     # Auto-wires Prometheus datasource
│       └── dashboards/
│           ├── dashboard.yml      # Dashboard provider config
│           └── app-overview.json  # Pre-built Grafana dashboard
├── docker-compose.yml      # Full stack orchestration
├── requirements.txt        # Python dependencies (root copy)
└── README.md               # This file
```

---

## Future Improvements

- **Alerting rules** — Add Prometheus alerting rules (`alerts.yml`) for high error rate, high latency, and service down
- **Alertmanager** — Route alerts to Slack/PagerDuty via Alertmanager container
- **Custom business metrics** — Add Gauges for in-flight requests, queue depth, active users
- **Multi-service scraping** — Extend Prometheus config to scrape Redis, PostgreSQL, and Nginx exporters
- **Grafana alerting** — Configure Grafana alert panels with notification channels
- **TLS/auth** — Add HTTPS via reverse proxy (Nginx/Traefik) and restrict Prometheus UI access
- **Log aggregation** — Add Loki + Promtail for correlated metrics and logs in Grafana
- **Docker healthchecks** — Extend `depends_on` with service health conditions
