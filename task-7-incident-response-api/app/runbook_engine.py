"""
Runbook engine — returns ordered operational steps for each incident category.

Steps are written as actionable SRE runbook entries, suitable for use in
PagerDuty, OpsGenie, or an internal incident response wiki.
"""

from typing import List
from app.schemas import Category

_RUNBOOKS: dict[Category, List[str]] = {
    Category.NETWORK: [
        "1. Confirm the affected service is listed as healthy in your service registry (Consul/k8s endpoints).",
        "2. Test connectivity: `curl -v <upstream-host>:<port>` or `nc -zv <host> <port>`.",
        "3. Inspect DNS resolution: `dig <hostname>` / `nslookup <hostname>` from inside the pod/container.",
        "4. Review network policies (Kubernetes NetworkPolicy, AWS Security Groups, iptables rules).",
        "5. Check firewall and load balancer logs for dropped packets or backend-unavailable errors.",
        "6. If upstream is a k8s Service, verify Endpoints object has ready addresses: `kubectl get endpoints <svc>`.",
        "7. Review recent infrastructure changes (Terraform plan/apply, AMI replacements, VPC routing changes).",
        "8. Escalate to network/platform team if no root cause is found within 15 minutes.",
    ],
    Category.PERMISSIONS: [
        "1. Identify the exact resource and operation that was denied (file path, API endpoint, secret name).",
        "2. Check IAM/RBAC bindings: `kubectl describe rolebinding` or AWS IAM policy simulator.",
        "3. For filesystem issues: inspect `ls -la` on the target path and compare with service user/group.",
        "4. Validate Vault policies, AWS Secrets Manager resource policies, or GCP IAM conditions.",
        "5. Review recent permission or policy changes in your IaC repository (git log -- policies/).",
        "6. Apply the principle of least-privilege — do not grant wildcard permissions as a quick fix.",
        "7. Rotate credentials if a secret may have been exposed due to the permission misconfiguration.",
        "8. Document the fix and open a post-mortem ticket if production was impacted.",
    ],
    Category.DEPENDENCY: [
        "1. Identify the missing or conflicting dependency from the error message (package name, version).",
        "2. Compare the current lock file (requirements.txt / package-lock.json / go.sum) with last known-good state.",
        "3. Re-run dependency installation in a clean environment: `pip install -r requirements.txt --no-cache-dir`.",
        "4. Check for yanked or deprecated package versions on PyPI/npm/Maven.",
        "5. If a container image changed, compare image digests with `docker image inspect`.",
        "6. Pin dependency versions explicitly to prevent future drift.",
        "7. If a library is missing from the base image, add it to the Dockerfile and rebuild.",
        "8. Run integration tests in staging before promoting the fixed artifact to production.",
    ],
    Category.TIMEOUT: [
        "1. Check if the downstream service is reachable and responding: `curl -w '%{time_total}' <url>`.",
        "2. Review current latency dashboards (Prometheus/Grafana) for the affected service.",
        "3. Inspect recent traffic spikes — compare request rates with baseline using your APM tool.",
        "4. Check for long-running queries: `pg_stat_activity`, `SHOW PROCESSLIST` (MySQL), slow query logs.",
        "5. Evaluate current timeout configuration: connect timeout, read timeout, idle timeout.",
        "6. Check if retries are amplifying load (retry storm) — apply exponential back-off with jitter.",
        "7. Enable circuit-breaker on the affected client (Hystrix, Resilience4j, Envoy outlier detection).",
        "8. Scale out or restart the downstream service if it is healthy but overloaded.",
    ],
    Category.RESOURCE: [
        "1. Identify the exhausted resource from the error: memory, disk, CPU, file descriptors.",
        "2. Check current utilization: `kubectl top pod`, `df -h`, `free -m`, `ulimit -a`.",
        "3. For OOM: review container memory limits vs. actual usage trend in Grafana.",
        "4. Immediately free space if disk is full: clear old logs, temp files, completed job artifacts.",
        "5. Increase resource limits/requests in the Kubernetes Deployment or system configuration.",
        "6. Profile the application for memory leaks: heap dumps, pprof, py-spy, async-profiler.",
        "7. Set up HorizontalPodAutoscaler or cluster autoscaler to handle traffic-driven resource growth.",
        "8. Add alerting thresholds at 75% resource utilization to provide early warning in the future.",
    ],
    Category.UNKNOWN: [
        "1. Collect full log context: 50 lines before and after the error with timestamps.",
        "2. Identify the exact time the incident started and correlate with deployment or config changes.",
        "3. Check all dependent services for simultaneous alerts.",
        "4. Reproduce the issue in a lower environment if possible.",
        "5. Search internal runbook wiki and past post-mortem documents for similar symptoms.",
        "6. Engage on-call engineering team and start a dedicated incident Slack channel.",
        "7. Document all findings in real-time in the incident ticket.",
        "8. Conduct a blameless post-mortem within 48 hours of resolution.",
    ],
}


def get_runbook(category: Category) -> List[str]:
    """Return the operational runbook steps for the given incident category."""
    return _RUNBOOKS.get(category, _RUNBOOKS[Category.UNKNOWN])
