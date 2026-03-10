"""
Security rules for infrastructure configuration scanning.
Each rule is a function that takes parsed config data and returns a list of findings.
"""

import re
from typing import Any


SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def _make_finding(title: str, severity: str, file: str, explanation: str, remediation: str) -> dict:
    return {
        "title": title,
        "severity": severity,
        "file": file,
        "explanation": explanation,
        "remediation": remediation,
    }


# ---------------------------------------------------------------------------
# Docker Compose rules
# ---------------------------------------------------------------------------

def check_docker_compose(data: dict, filepath: str) -> list[dict]:
    findings = []
    services = data.get("services", {}) if isinstance(data, dict) else {}

    for svc_name, svc in (services or {}).items():
        if not isinstance(svc, dict):
            continue

        # :latest image tag
        image = svc.get("image", "")
        if isinstance(image, str) and (image.endswith(":latest") or (":" not in image and image)):
            findings.append(_make_finding(
                title=f"Service '{svc_name}' uses ':latest' image tag",
                severity=SEVERITY_HIGH,
                file=filepath,
                explanation="Using ':latest' makes builds non-deterministic and can silently pull breaking changes.",
                remediation="Pin the image to a specific digest or version tag, e.g. 'nginx:1.25.3'.",
            ))

        # Privileged containers
        if svc.get("privileged") is True:
            findings.append(_make_finding(
                title=f"Service '{svc_name}' runs in privileged mode",
                severity=SEVERITY_CRITICAL,
                file=filepath,
                explanation="Privileged containers have full access to the host kernel and devices, breaking container isolation.",
                remediation="Remove 'privileged: true'. Use specific Linux capabilities (cap_add) only if required.",
            ))

        # Running as root (user: root or user: '0')
        user = str(svc.get("user", "")).strip()
        if user in ("root", "0", "0:0"):
            findings.append(_make_finding(
                title=f"Service '{svc_name}' runs as root user",
                severity=SEVERITY_HIGH,
                file=filepath,
                explanation="Running containers as root increases the blast radius of a container escape.",
                remediation="Add 'user: <uid>:<gid>' with a non-root UID/GID to the service definition.",
            ))

        # Missing resource limits
        deploy = svc.get("deploy", {}) or {}
        resources = deploy.get("resources", {}) if isinstance(deploy, dict) else {}
        limits = resources.get("limits", {}) if isinstance(resources, dict) else {}
        if not limits:
            # also check top-level mem_limit / cpus
            if not svc.get("mem_limit") and not svc.get("cpus"):
                findings.append(_make_finding(
                    title=f"Service '{svc_name}' has no resource limits",
                    severity=SEVERITY_MEDIUM,
                    file=filepath,
                    explanation="Without CPU/memory limits a single service can exhaust host resources (denial of service).",
                    remediation="Set deploy.resources.limits.cpus and deploy.resources.limits.memory for each service.",
                ))

        # Public port binding on 0.0.0.0
        ports = svc.get("ports", [])
        for port_entry in (ports or []):
            port_str = str(port_entry)
            if port_str.startswith("0.0.0.0:") or re.match(r"^\d+:\d+$", port_str):
                findings.append(_make_finding(
                    title=f"Service '{svc_name}' binds port to 0.0.0.0 ({port_entry})",
                    severity=SEVERITY_HIGH,
                    file=filepath,
                    explanation="Binding to 0.0.0.0 exposes the port on all network interfaces, including public ones.",
                    remediation="Bind to a specific interface, e.g. '127.0.0.1:8080:8080', unless public access is required.",
                ))

        # Hardcoded secrets in environment variables
        env = svc.get("environment", {})
        env_items = env.items() if isinstance(env, dict) else (
            (e.split("=", 1)[0], e.split("=", 1)[1]) for e in env if "=" in str(e)
        )
        secret_patterns = re.compile(
            r"(password|passwd|secret|api[_-]?key|access[_-]?key|token|private[_-]?key|aws[_-]?secret)",
            re.IGNORECASE,
        )
        for key, value in env_items:
            if secret_patterns.search(str(key)) and value and str(value) not in ("", '""', "''"):
                findings.append(_make_finding(
                    title=f"Service '{svc_name}' has hardcoded secret in env var '{key}'",
                    severity=SEVERITY_CRITICAL,
                    file=filepath,
                    explanation=f"The environment variable '{key}' appears to contain a hardcoded secret, which will be visible in the image and process list.",
                    remediation="Use Docker secrets, environment variable injection at runtime, or a secrets manager (Vault, AWS Secrets Manager).",
                ))

    return findings


# ---------------------------------------------------------------------------
# Kubernetes rules
# ---------------------------------------------------------------------------

def check_kubernetes(data: dict, filepath: str) -> list[dict]:
    findings = []
    if not isinstance(data, dict):
        return findings

    kind = data.get("kind", "")
    spec = data.get("spec", {}) or {}

    containers = []

    if kind in ("Deployment", "DaemonSet", "StatefulSet", "Job"):
        template = spec.get("template", {}) or {}
        pod_spec = template.get("spec", {}) or {}
        containers = pod_spec.get("containers", []) or []
        init_containers = pod_spec.get("initContainers", []) or []
        containers = containers + init_containers

    elif kind == "Pod":
        pod_spec = spec
        containers = pod_spec.get("containers", []) or []

    for container in containers:
        if not isinstance(container, dict):
            continue
        name = container.get("name", "unknown")

        # :latest image tag
        image = container.get("image", "")
        if isinstance(image, str) and (image.endswith(":latest") or (":" not in image and "/" not in image and image)):
            findings.append(_make_finding(
                title=f"Container '{name}' uses ':latest' image tag",
                severity=SEVERITY_HIGH,
                file=filepath,
                explanation="Unpinned images cause non-reproducible deployments and may pull vulnerable versions.",
                remediation="Pin the image to a specific version or SHA digest.",
            ))

        # Privileged security context
        sc = container.get("securityContext", {}) or {}
        if sc.get("privileged") is True:
            findings.append(_make_finding(
                title=f"Container '{name}' runs in privileged mode",
                severity=SEVERITY_CRITICAL,
                file=filepath,
                explanation="A privileged container can access all host devices and bypass Linux namespace isolation.",
                remediation="Remove 'privileged: true'. Apply least-privilege via allowedCapabilities.",
            ))

        # Running as root
        if sc.get("runAsUser") == 0 or sc.get("runAsNonRoot") is False:
            findings.append(_make_finding(
                title=f"Container '{name}' is configured to run as root",
                severity=SEVERITY_HIGH,
                file=filepath,
                explanation="Running as UID 0 inside a container elevates risk if container isolation is bypassed.",
                remediation="Set securityContext.runAsNonRoot: true and specify a non-zero runAsUser.",
            ))

        # Missing resource limits
        resources = container.get("resources", {}) or {}
        limits = resources.get("limits", {}) or {}
        if not limits.get("cpu") or not limits.get("memory"):
            findings.append(_make_finding(
                title=f"Container '{name}' is missing CPU/memory limits",
                severity=SEVERITY_MEDIUM,
                file=filepath,
                explanation="Without resource limits a single container can consume all node resources.",
                remediation="Set resources.limits.cpu and resources.limits.memory for every container.",
            ))

        # Missing liveness probe
        if not container.get("livenessProbe"):
            findings.append(_make_finding(
                title=f"Container '{name}' has no livenessProbe",
                severity=SEVERITY_LOW,
                file=filepath,
                explanation="Without a liveness probe Kubernetes cannot detect and restart stuck/deadlocked containers.",
                remediation="Add a livenessProbe (httpGet, tcpSocket, or exec) appropriate for the service.",
            ))

        # Missing readiness probe
        if not container.get("readinessProbe"):
            findings.append(_make_finding(
                title=f"Container '{name}' has no readinessProbe",
                severity=SEVERITY_LOW,
                file=filepath,
                explanation="Without a readiness probe, traffic may be routed to containers that are not yet ready to serve.",
                remediation="Add a readinessProbe to signal when the container is ready to accept traffic.",
            ))

        # Hardcoded secrets in env
        env_vars = container.get("env", []) or []
        secret_patterns = re.compile(
            r"(password|passwd|secret|api[_-]?key|access[_-]?key|token|private[_-]?key|aws[_-]?secret)",
            re.IGNORECASE,
        )
        for env_var in env_vars:
            if not isinstance(env_var, dict):
                continue
            key = env_var.get("name", "")
            value = env_var.get("value")
            if value is not None and secret_patterns.search(str(key)):
                findings.append(_make_finding(
                    title=f"Container '{name}' has hardcoded secret in env var '{key}'",
                    severity=SEVERITY_CRITICAL,
                    file=filepath,
                    explanation=f"The value of '{key}' is hardcoded in the manifest and will be stored in plaintext in etcd.",
                    remediation="Use a Kubernetes Secret object referenced via envFrom or valueFrom.secretKeyRef.",
                ))

    # Check for hostNetwork / hostPID / hostIPC
    pod_spec: dict = {}
    if kind in ("Deployment", "DaemonSet", "StatefulSet"):
        pod_spec = spec.get("template", {}).get("spec", {}) or {}
    elif kind == "Pod":
        pod_spec = spec

    if pod_spec.get("hostNetwork") is True:
        findings.append(_make_finding(
            title="Pod uses hostNetwork: true",
            severity=SEVERITY_HIGH,
            file=filepath,
            explanation="hostNetwork exposes the pod directly on the host network namespace, bypassing network policies.",
            remediation="Remove hostNetwork or restrict it to DaemonSets with a clear operational need.",
        ))

    if pod_spec.get("hostPID") is True:
        findings.append(_make_finding(
            title="Pod uses hostPID: true",
            severity=SEVERITY_HIGH,
            file=filepath,
            explanation="hostPID gives the container visibility into all host processes, enabling privilege escalation.",
            remediation="Remove hostPID unless explicitly required for a monitoring/debugging use case.",
        ))

    return findings


# ---------------------------------------------------------------------------
# Terraform rules
# ---------------------------------------------------------------------------

def check_terraform(content: str, filepath: str) -> list[dict]:
    findings = []

    # Wide-open CIDR blocks in security groups / firewall rules
    cidr_patterns = [
        (r'cidr_blocks\s*=\s*\[.*?"0\.0\.0\.0/0"', "AWS Security Group allows 0.0.0.0/0 ingress"),
        (r'source_ranges\s*=\s*\[.*?"0\.0\.0\.0/0"', "GCP Firewall allows 0.0.0.0/0 source"),
        (r'ip_cidr_range\s*=\s*"0\.0\.0\.0/0"', "Subnet or route uses 0.0.0.0/0"),
    ]
    for pattern, description in cidr_patterns:
        if re.search(pattern, content, re.DOTALL):
            findings.append(_make_finding(
                title=description,
                severity=SEVERITY_CRITICAL,
                file=filepath,
                explanation="Allowing traffic from 0.0.0.0/0 exposes resources to the entire internet.",
                remediation="Restrict CIDR blocks to known IP ranges. Use a VPN or bastion host for administrative access.",
            ))

    # Hardcoded secrets / passwords
    secret_patterns = re.compile(
        r'(password|secret|api_key|access_key|private_key|db_password|token)\s*=\s*"(?!var\.|data\.|local\.)([^"]{4,})"',
        re.IGNORECASE,
    )
    for match in secret_patterns.finditer(content):
        key = match.group(1)
        findings.append(_make_finding(
            title=f"Hardcoded secret in Terraform variable '{key}'",
            severity=SEVERITY_CRITICAL,
            file=filepath,
            explanation=f"The attribute '{key}' contains a hardcoded value that will be stored in the Terraform state file in plaintext.",
            remediation="Use terraform variables with sensitive = true or retrieve secrets from Vault/AWS Secrets Manager via a data source.",
        ))

    # S3 bucket with public ACL
    if re.search(r'acl\s*=\s*"public-read(-write)?"', content):
        findings.append(_make_finding(
            title="S3 bucket configured with public ACL",
            severity=SEVERITY_CRITICAL,
            file=filepath,
            explanation="A public-read or public-read-write ACL exposes all bucket objects to the internet.",
            remediation="Remove the public ACL and use bucket policies with explicit principal restrictions.",
        ))

    # Encryption disabled
    if re.search(r'encrypted\s*=\s*false', content):
        findings.append(_make_finding(
            title="Storage volume or RDS instance has encryption disabled",
            severity=SEVERITY_HIGH,
            file=filepath,
            explanation="Disabling encryption at rest leaves data exposed if the underlying storage is accessed outside AWS.",
            remediation="Set 'encrypted = true' and specify a KMS key ID.",
        ))

    # Logging disabled
    if re.search(r'logging\s*=\s*false|enable_logging\s*=\s*false', content):
        findings.append(_make_finding(
            title="Logging is explicitly disabled",
            severity=SEVERITY_MEDIUM,
            file=filepath,
            explanation="Disabled logging prevents audit trails and incident investigation.",
            remediation="Enable access logging and ship logs to a centralised SIEM.",
        ))

    # MFA delete disabled on S3
    if re.search(r'mfa_delete\s*=\s*"Disabled"', content, re.IGNORECASE):
        findings.append(_make_finding(
            title="S3 bucket MFA delete is disabled",
            severity=SEVERITY_MEDIUM,
            file=filepath,
            explanation="Without MFA delete, any compromised credential can permanently delete versioned objects.",
            remediation="Enable MFA delete on versioned buckets that store sensitive data.",
        ))

    # Publicly accessible RDS
    if re.search(r'publicly_accessible\s*=\s*true', content):
        findings.append(_make_finding(
            title="RDS instance is publicly accessible",
            severity=SEVERITY_CRITICAL,
            file=filepath,
            explanation="A publicly accessible RDS instance is directly reachable from the internet, dramatically increasing attack surface.",
            remediation="Set 'publicly_accessible = false' and access the database through a private subnet or VPN.",
        ))

    # Skip TLS verification
    if re.search(r'insecure\s*=\s*true|skip_tls_verify\s*=\s*true|tls_skip_verify\s*=\s*true', content, re.IGNORECASE):
        findings.append(_make_finding(
            title="TLS verification is disabled",
            severity=SEVERITY_HIGH,
            file=filepath,
            explanation="Disabling TLS verification allows man-in-the-middle attacks against API communications.",
            remediation="Remove insecure/skip_tls_verify flags and ensure valid certificates are in use.",
        ))

    return findings


# ---------------------------------------------------------------------------
# .env file rules
# ---------------------------------------------------------------------------

def check_env_file(content: str, filepath: str) -> list[dict]:
    findings = []
    secret_key_pattern = re.compile(
        r"^(PASSWORD|PASSWD|SECRET|API[_]?KEY|ACCESS[_]?KEY|TOKEN|PRIVATE[_]?KEY|AWS_SECRET|DATABASE_URL|DB_PASS|AUTH_TOKEN)",
        re.IGNORECASE | re.MULTILINE,
    )
    debug_pattern = re.compile(r"^DEBUG\s*=\s*(true|1|yes)", re.IGNORECASE | re.MULTILINE)
    default_pass_pattern = re.compile(
        r"^(PASSWORD|PASSWD|DB_PASS[A-Z_]*)\s*=\s*(password|admin|123456|changeme|secret|root|qwerty)",
        re.IGNORECASE | re.MULTILINE,
    )

    for match in secret_key_pattern.finditer(content):
        line = content[content.rfind("\n", 0, match.start()) + 1: content.find("\n", match.start())]
        key = line.split("=")[0].strip()
        value_part = line.split("=", 1)[1].strip() if "=" in line else ""
        if value_part and value_part not in ("", '""', "''", '""""""'):
            findings.append(_make_finding(
                title=f"Sensitive variable '{key}' set in .env file",
                severity=SEVERITY_HIGH,
                file=filepath,
                explanation=f"The .env file contains '{key}' with a value. If this file is committed, the secret leaks.",
                remediation="Add .env to .gitignore, use environment variable injection at runtime, or use a secrets manager.",
            ))

    if debug_pattern.search(content):
        findings.append(_make_finding(
            title="DEBUG mode enabled in .env",
            severity=SEVERITY_MEDIUM,
            file=filepath,
            explanation="Running with DEBUG=true in production can expose stack traces, internal paths, and configuration details.",
            remediation="Set DEBUG=false in production environments.",
        ))

    for match in default_pass_pattern.finditer(content):
        key = match.group(1)
        val = match.group(2)
        findings.append(_make_finding(
            title=f"Default/weak password detected for '{key}': '{val}'",
            severity=SEVERITY_CRITICAL,
            file=filepath,
            explanation="Using default or well-known passwords is one of the most exploited misconfiguration categories.",
            remediation="Replace with a strong, randomly generated secret of at least 32 characters.",
        ))

    return findings
