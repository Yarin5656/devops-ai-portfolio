"""
Runbook engine.

Returns ordered operational remediation steps for each incident category.
All runbooks are offline — no external calls required.
"""

from typing import List

RUNBOOKS = {
    "network_failure": [
        "1. Verify upstream service is running: `systemctl status <upstream-service>` or check pod status with `kubectl get pods`.",
        "2. Test network reachability: `curl -v http://<upstream-host>:<port>/health` from the Nginx host.",
        "3. Inspect Nginx error logs: `tail -n 100 /var/log/nginx/error.log | grep -E 'error|crit|emerg'`.",
        "4. Validate Nginx upstream configuration: `nginx -T | grep upstream`.",
        "5. Check firewall / security group rules blocking upstream ports.",
        "6. Verify SSL certificates are valid and not expired: `openssl s_client -connect <host>:443 -brief`.",
        "7. Reload Nginx after config changes: `nginx -t && systemctl reload nginx`.",
        "8. Review DNS resolution for upstream hostnames: `dig <upstream-hostname>`.",
        "9. If upstream is a container, check container network policies.",
        "10. Escalate to network team if layer-3 routing issues are suspected.",
    ],
    "database_failure": [
        "1. Check PostgreSQL process status: `systemctl status postgresql` or `pg_lsclusters`.",
        "2. Inspect current connections: `SELECT count(*), state FROM pg_stat_activity GROUP BY state;`",
        "3. Identify long-running or idle-in-transaction connections: `SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC LIMIT 20;`",
        "4. Terminate blocking long-running queries: `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE duration > interval '5 minutes' AND state != 'idle';`",
        "5. Check PostgreSQL max_connections: `SHOW max_connections;` — consider increasing or deploying PgBouncer.",
        "6. Review application connection pool settings (pool_size, max_overflow, pool_timeout).",
        "7. Restart PgBouncer if deployed: `systemctl restart pgbouncer`.",
        "8. Check PostgreSQL logs for FATAL errors: `tail -n 200 /var/log/postgresql/postgresql-*.log`.",
        "9. Verify disk space for WAL and data directory: `df -h /var/lib/postgresql/`.",
        "10. Open circuit breaker manually only after confirming DB is healthy; then gradually resume traffic.",
    ],
    "high_cpu": [
        "1. Identify top CPU-consuming processes: `top -bn1 | head -20` or `ps aux --sort=-%cpu | head -15`.",
        "2. Check system load average trend: `uptime` and `sar -u 1 5`.",
        "3. Profile the application for hotspots: enable profiling or attach `py-spy`/`perf` to the process.",
        "4. Identify runaway threads: `ps -eLf | sort -k6 -r | head -20`.",
        "5. Check for CPU steal time (hypervisor contention): `vmstat 1 5` — if steal > 10%, contact cloud provider.",
        "6. If auto-scaling is configured, verify it has triggered: check ASG activity or HPA status with `kubectl get hpa`.",
        "7. Manually scale out if auto-scaling has not triggered: `kubectl scale deployment <name> --replicas=<N>`.",
        "8. Kill runaway worker processes if safe to do so: `kill -9 <pid>`.",
        "9. Implement request rate limiting at the load balancer to shed load.",
        "10. After stabilization, analyze heap dumps and CPU profiles to identify the root cause and apply a code fix.",
    ],
    "resource_exhaustion": [
        "1. Check memory usage: `free -h` and `vmstat -s`.",
        "2. Identify top memory-consuming processes: `ps aux --sort=-%mem | head -15`.",
        "3. Review OOM killer events: `dmesg | grep -i 'oom\\|killed process'`.",
        "4. Check disk usage across all partitions: `df -h` and `du -sh /var/log/* | sort -rh | head -10`.",
        "5. Rotate and compress large log files: `logrotate -f /etc/logrotate.conf`.",
        "6. Check open file descriptors: `lsof | wc -l` and compare against `ulimit -n`.",
        "7. Increase ulimits if needed: `ulimit -n 65536` (apply in /etc/security/limits.conf for persistence).",
        "8. Drain request queues by temporarily pausing non-critical consumers.",
        "9. Scale vertically (increase instance type) or horizontally (add nodes) to increase capacity.",
        "10. Review Kubernetes resource requests/limits and update accordingly.",
    ],
    "service_unavailable": [
        "1. Check service status: `systemctl status <service>` or `kubectl get pods -n <namespace>`.",
        "2. Review recent pod/service events: `kubectl describe pod <pod-name>` for CrashLoopBackOff details.",
        "3. Pull recent application logs: `kubectl logs <pod-name> --previous --tail=100`.",
        "4. Verify the most recent deployment did not introduce regressions: `kubectl rollout history deployment/<name>`.",
        "5. Rollback if deployment is the cause: `kubectl rollout undo deployment/<name>`.",
        "6. Check readiness and liveness probe configurations match actual health endpoints.",
        "7. Verify all upstream dependencies (DB, cache, message queue) are reachable from the pod.",
        "8. Check container resource limits — OOMKilled containers indicate limits are too low.",
        "9. Validate environment variables, secrets, and config maps are correctly mounted.",
        "10. After recovery, update runbooks and post a blameless post-mortem within 48 hours.",
    ],
    "default": [
        "1. Gather all relevant logs from the affected service and its dependencies.",
        "2. Check system resource utilization: CPU, memory, disk, and network.",
        "3. Review recent deployments, configuration changes, and infrastructure changes.",
        "4. Verify all upstream and downstream dependencies are healthy.",
        "5. Engage the on-call engineer and open a war-room channel for coordination.",
        "6. Apply blast-radius-limiting measures (rate limiting, circuit breaking) while investigating.",
        "7. Escalate to service owner if root cause is not identified within 30 minutes.",
        "8. Document timeline of events for post-incident review.",
    ],
}


def get_runbook_steps(categories: List[str]) -> List[str]:
    if not categories:
        return RUNBOOKS["default"]

    primary = categories[0]
    steps = RUNBOOKS.get(primary, RUNBOOKS["default"])

    # Append abbreviated steps for secondary categories
    for secondary in categories[1:2]:  # limit to one additional runbook
        secondary_steps = RUNBOOKS.get(secondary, [])
        if secondary_steps:
            steps = list(steps)
            steps.append(f"\n--- Additional steps for secondary issue: {secondary.replace('_', ' ').title()} ---")
            steps.extend(secondary_steps[:3])

    return steps
