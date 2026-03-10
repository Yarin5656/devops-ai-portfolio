# Task 4 — CI/CD Pipeline System

A portfolio-grade CI/CD demonstration project built with **Flask**, **Docker**, **Kubernetes**, and **GitHub Actions**.

---

## Project Overview

This project implements a minimal Python web service and wraps it in a complete automated delivery pipeline:

- **Application** — A Flask HTTP service exposing a `/health` endpoint.
- **Tests** — Pytest suite that validates HTTP status codes, response fields, and content type.
- **Docker** — Production-style multi-layer image running as a non-root user.
- **Kubernetes** — Deployment (2 replicas) + ClusterIP Service manifests ready for any K8s cluster.
- **GitHub Actions** — Three-job workflow: Test → Build → Validate K8s manifests.

---

## Architecture

```
GitHub Push / PR
       │
       ▼
┌──────────────────────────────────────────────┐
│              GitHub Actions                  │
│                                              │
│  [Job 1: Test]                               │
│   └─ pytest + coverage report                │
│          │ (on success)                      │
│          ├──────────────────┐                │
│  [Job 2: Build Docker]      │                │
│   └─ docker buildx          │                │
│                    [Job 3: Validate K8s]     │
│                     └─ kubectl dry-run       │
└──────────────────────────────────────────────┘
       │  (future: push image + kubectl apply)
       ▼
  Kubernetes Cluster
  ┌────────────────────────────────┐
  │  Deployment (2 replicas)       │
  │  └─ Pod: task-4-cicd-pipeline  │
  │       └─ /health  :8080        │
  │  Service (ClusterIP :80)       │
  └────────────────────────────────┘
```

---

## Directory Structure

```
task-4-cicd-pipeline/
├── app/
│   └── main.py                  # Flask application
├── tests/
│   └── test_main.py             # Pytest test suite
├── k8s/
│   ├── deployment.yaml          # K8s Deployment (2 replicas)
│   └── service.yaml             # K8s ClusterIP Service
├── .github/
│   └── workflows/
│       └── ci-cd.yml            # GitHub Actions pipeline
├── Dockerfile                   # Production container image
├── requirements.txt             # Python dependencies
└── README.md
```

---

## Local Run Instructions

### Prerequisites

- Python 3.12+
- pip
- (Optional) Docker
- (Optional) kubectl + a Kubernetes cluster

### 1. Install Dependencies

```bash
cd task-4-cicd-pipeline
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python -m app.main
```

The service will start on `http://localhost:8080`.

### 3. Test the Endpoint

```bash
curl http://localhost:8080/health
# {"service":"task-4-cicd-pipeline","status":"ok"}
```

---

## How Tests Work

Tests live in `tests/test_main.py` and use Flask's built-in test client — no live server required.

```bash
pytest tests/ -v
```

Three test cases are included:

| Test | What it checks |
|------|---------------|
| `test_health_status_code` | HTTP 200 response |
| `test_health_response_fields` | JSON keys `status` and `service` with correct values |
| `test_health_content_type` | `Content-Type: application/json` header |

Run with coverage:

```bash
pytest tests/ --cov=app --cov-report=term-missing -v
```

---

## How Docker Build Works

The `Dockerfile` follows production best practices:

- **Base image**: `python:3.12-slim` (minimal attack surface)
- **Layer caching**: `requirements.txt` is copied and installed before application code
- **Non-root user**: A dedicated `appuser` account runs the process
- **Exposed port**: `8080`

```bash
# Build
docker build -t task-4-cicd-pipeline:local .

# Run
docker run -p 8080:8080 task-4-cicd-pipeline:local

# Test
curl http://localhost:8080/health
```

---

## How Kubernetes Deployment Works

Manifests are in `k8s/`.

| File | Purpose |
|------|---------|
| `deployment.yaml` | Runs 2 replicas with readiness/liveness probes and resource limits |
| `service.yaml` | ClusterIP service routing port 80 → container port 8080 |

Before deploying, replace `IMAGE_PLACEHOLDER` in `deployment.yaml` with the actual image:

```bash
# Example using sed
IMAGE="ghcr.io/yourorg/task-4-cicd-pipeline:abc1234"
sed "s|IMAGE_PLACEHOLDER|$IMAGE|g" k8s/deployment.yaml | kubectl apply -f -
kubectl apply -f k8s/service.yaml
```

Verify:

```bash
kubectl get pods -l app=task-4-cicd-pipeline
kubectl get svc task-4-cicd-pipeline
```

---

## How GitHub Actions Pipeline Works

Workflow file: `.github/workflows/ci-cd.yml`

The pipeline triggers on every **push** or **pull request** that touches files inside `task-4-cicd-pipeline/`.

### Jobs

```
test ──► build
     └──► validate-k8s
```

| Job | Steps |
|-----|-------|
| **test** | Checkout → Python 3.12 → pip install → pytest with coverage |
| **build** | Checkout → Docker Buildx → build image (no push, cache via GHA) |
| **validate-k8s** | Checkout → kubectl → `--dry-run=client` on both manifests |

`build` and `validate-k8s` both depend on `test` and run in parallel after it passes.

---

## Future Improvements

- **Image registry push** — Authenticate to GHCR/ECR and push the image on merge to `main`.
- **GitOps deployment** — Use ArgoCD or Flux to auto-sync the K8s manifests from the repo.
- **Helm chart** — Package the manifests as a Helm chart for parameterised environments (dev/staging/prod).
- **Secret management** — Integrate Vault or AWS Secrets Manager for runtime secrets.
- **SBOM & image scanning** — Add Trivy or Grype as a pipeline step to catch CVEs before deployment.
- **Staging environment gate** — Add a manual approval step before production promotion.
- **Observability** — Expose Prometheus metrics from the Flask app and scrape in-cluster.
