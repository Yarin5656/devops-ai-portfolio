# Task 6 - Kubernetes Deployment System

A production-style Kubernetes deployment for a Python Flask web service, demonstrating core platform engineering practices including health probing, resource management, and horizontal autoscaling.

---

## Project Overview

This project packages a minimal Flask application into a container and deploys it onto Kubernetes using a complete set of manifests. It is designed to reflect real-world engineering standards:

- Dedicated namespace isolation
- Multi-replica deployment with resource governance
- Liveness and readiness probes
- Horizontal Pod Autoscaling (HPA) based on CPU utilization
- ClusterIP service for internal cluster routing

---

## Application Endpoints

| Endpoint  | Method | Description                          |
|-----------|--------|--------------------------------------|
| `/`       | GET    | Service identity and version info    |
| `/health` | GET    | Liveness check — returns `healthy`   |
| `/ready`  | GET    | Readiness check — returns `ready`    |

---

## Kubernetes Architecture

```
                        ┌─────────────────────────────────┐
                        │         Namespace: task-6        │
                        │                                  │
                        │  ┌────────────────────────────┐  │
                        │  │   HorizontalPodAutoscaler  │  │
                        │  │   min: 2  /  max: 5 pods   │  │
                        │  └────────────┬───────────────┘  │
                        │               │ scales            │
                        │  ┌────────────▼───────────────┐  │
          ┌─────────┐   │  │        Deployment          │  │
          │ Client  │──▶│  │   replicas: 2 (default)    │  │
          └─────────┘   │  │                            │  │
               │        │  │  ┌──────────┐ ┌─────────┐ │  │
               │        │  │  │  Pod 1   │ │  Pod 2  │ │  │
               ▼        │  │  │ :8080    │ │ :8080   │ │  │
     ┌──────────────┐   │  │  └──────────┘ └─────────┘ │  │
     │   Service    │──▶│  └────────────────────────────┘  │
     │  ClusterIP   │   │                                  │
     │  port: 80    │   └─────────────────────────────────┘
     └──────────────┘
```

### Manifest Breakdown

| File               | Resource                    | Purpose                                              |
|--------------------|-----------------------------|------------------------------------------------------|
| `namespace.yaml`   | Namespace                   | Isolates all task-6 resources                        |
| `deployment.yaml`  | Deployment                  | Manages pod lifecycle, replicas, and container spec  |
| `service.yaml`     | Service (ClusterIP)         | Stable internal DNS and load-balancing across pods   |
| `hpa.yaml`         | HorizontalPodAutoscaler     | Auto-scales pods based on CPU pressure               |

---

## Health Probes Explained

Kubernetes uses two probes to manage pod lifecycle:

### Liveness Probe (`/health`)
- **Purpose:** Determines if the container is still alive. If it fails repeatedly, Kubernetes restarts the container.
- **Configured:** `initialDelaySeconds: 10`, `periodSeconds: 15`, `failureThreshold: 3`
- **Use case:** Catches deadlocks or unrecoverable application crashes.

### Readiness Probe (`/ready`)
- **Purpose:** Determines if the container is ready to receive traffic. If it fails, the pod is removed from the Service endpoints — no traffic is sent to it.
- **Configured:** `initialDelaySeconds: 5`, `periodSeconds: 10`, `failureThreshold: 3`
- **Use case:** Prevents traffic from reaching pods that are still initializing or temporarily overloaded.

---

## Horizontal Pod Autoscaler (HPA) Explained

The HPA watches the CPU utilization of the pods in the Deployment and adjusts the replica count automatically:

- **Minimum replicas:** 2 (ensures baseline availability)
- **Maximum replicas:** 5 (caps resource consumption)
- **Scale trigger:** CPU utilization exceeds **70%** averaged across all pods

When load drops, HPA scales back down to the minimum. This requires the Kubernetes Metrics Server to be running in the cluster.

---

## How to Build the Docker Image

```bash
# Build the image
docker build -t YOUR_DOCKERHUB_USERNAME/task-6-web-service:latest .

# Test locally
docker run -p 8080:8080 YOUR_DOCKERHUB_USERNAME/task-6-web-service:latest

# Verify endpoints
curl http://localhost:8080/
curl http://localhost:8080/health
curl http://localhost:8080/ready

# Push to registry
docker push YOUR_DOCKERHUB_USERNAME/task-6-web-service:latest
```

---

## How to Apply Manifests with kubectl

Before applying, replace `YOUR_DOCKERHUB_USERNAME` in `k8s/deployment.yaml` with your actual Docker Hub username or image registry path.

```bash
# Apply all manifests in order
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml

# Or apply the entire directory at once
kubectl apply -f k8s/

# Verify everything is running
kubectl get all -n task-6

# Watch pods come up
kubectl get pods -n task-6 -w

# Check HPA status
kubectl get hpa -n task-6

# View application logs
kubectl logs -l app=task-6-web -n task-6
```

### Cleanup

```bash
kubectl delete namespace task-6
```

---

## Notes for Local Clusters (minikube / kind)

### minikube

```bash
# Start cluster
minikube start

# Enable Metrics Server (required for HPA)
minikube addons enable metrics-server

# Use minikube's Docker daemon to avoid pushing to a registry
eval $(minikube docker-env)
docker build -t task-6-web-service:local .

# Update deployment.yaml image to: task-6-web-service:local
# Set imagePullPolicy: Never in deployment.yaml

kubectl apply -f k8s/

# Access the service
minikube service task-6-web -n task-6
```

### kind

```bash
# Create cluster
kind create cluster --name task-6

# Load local image into kind
docker build -t task-6-web-service:local .
kind load docker-image task-6-web-service:local --name task-6

# Install Metrics Server for HPA
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

kubectl apply -f k8s/
```

---

## Resource Configuration

| Parameter         | Value    | Rationale                                      |
|-------------------|----------|------------------------------------------------|
| CPU Request       | 100m     | Guaranteed CPU slice for scheduling            |
| CPU Limit         | 250m     | Prevents noisy-neighbor CPU starvation         |
| Memory Request    | 128Mi    | Baseline memory guarantee                      |
| Memory Limit      | 256Mi    | Guards against memory leaks crashing the node  |
| Gunicorn Workers  | 2        | Lightweight multi-process serving              |

---

## Future Improvements

- **ConfigMap / Secret management** — externalize environment variables and credentials
- **Ingress controller** — expose the service externally via NGINX or Traefik with TLS termination
- **PodDisruptionBudget (PDB)** — ensure minimum availability during rolling updates or node drains
- **Network Policies** — restrict ingress/egress traffic between namespaces
- **Helm chart** — package manifests for parameterized, versioned deployments
- **CI/CD integration** — automate image builds and `kubectl rollout` on push
- **Vertical Pod Autoscaler (VPA)** — auto-tune resource requests based on observed usage
- **Prometheus metrics** — expose `/metrics` endpoint and integrate with Grafana dashboards
