# Task 8 — Infrastructure Security Scanner

A professional CLI security scanner that analyses DevOps configuration files and reports risky misconfigurations. Built as part of the **DevOps AI Portfolio** series.

---

## Project Overview

Infrastructure as Code (IaC) and container configuration files are a common source of security vulnerabilities. This scanner performs static analysis on common DevOps file formats and produces an actionable Markdown report highlighting misconfigurations ranked by severity.

The tool is dependency-light (only PyYAML required), runs entirely offline, and is designed to integrate into CI/CD pipelines as a pre-deployment gate.

---

## Project Structure

```
task-8-infrastructure-security-scanner/
├── scanner/
│   ├── __init__.py
│   ├── main.py              # CLI entry point
│   ├── parser.py            # File loading & type detection
│   ├── rules.py             # Security rule implementations
│   └── report_generator.py  # Markdown report writer
├── sample_configs/
│   ├── insecure-docker-compose.yml
│   ├── insecure-deployment.yaml
│   ├── insecure-terraform.tf
│   └── insecure.env
├── reports/                 # Generated reports (git-ignored)
├── requirements.txt
└── README.md
```

---

## Supported File Types

| Extension | Format Detected |
|-----------|----------------|
| `.yml` / `.yaml` | Docker Compose (presence of `services` key) |
| `.yml` / `.yaml` | Kubernetes manifests (`apiVersion` + `kind`) |
| `.tf` | HashiCorp Terraform HCL |
| `.env` | Environment variable files |

---

## Security Checks Implemented

### Docker Compose
| Check | Severity |
|-------|----------|
| `:latest` or untagged image | HIGH |
| `privileged: true` container | CRITICAL |
| Running as `root` user | HIGH |
| Missing CPU/memory resource limits | MEDIUM |
| Port bound to `0.0.0.0` | HIGH |
| Hardcoded secrets in `environment` | CRITICAL |

### Kubernetes Manifests
| Check | Severity |
|-------|----------|
| `:latest` or untagged image | HIGH |
| `securityContext.privileged: true` | CRITICAL |
| `runAsUser: 0` or `runAsNonRoot: false` | HIGH |
| Missing CPU/memory resource limits | MEDIUM |
| Missing `livenessProbe` | LOW |
| Missing `readinessProbe` | LOW |
| Hardcoded secrets in `env[].value` | CRITICAL |
| `hostNetwork: true` | HIGH |
| `hostPID: true` | HIGH |

### Terraform
| Check | Severity |
|-------|----------|
| Security group open to `0.0.0.0/0` | CRITICAL |
| Hardcoded password/secret/API key in attributes | CRITICAL |
| S3 bucket with `public-read` or `public-read-write` ACL | CRITICAL |
| `encrypted = false` on storage/RDS | HIGH |
| `logging = false` / `enable_logging = false` | MEDIUM |
| `mfa_delete = "Disabled"` on versioned S3 | MEDIUM |
| `publicly_accessible = true` on RDS | CRITICAL |
| TLS verification disabled (`skip_tls_verify = true`) | HIGH |

### .env Files
| Check | Severity |
|-------|----------|
| Sensitive variable name with non-empty value | HIGH |
| `DEBUG=true` in production env | MEDIUM |
| Default/weak passwords (e.g. `password`, `admin`, `changeme`) | CRITICAL |

---

## Installation

```bash
cd task-8-infrastructure-security-scanner
pip install -r requirements.txt
```

Python 3.11+ is recommended.

---

## Example Usage

**Scan the bundled sample configs:**
```bash
python scanner/main.py --path sample_configs
```

**Scan a custom directory:**
```bash
python scanner/main.py --path /path/to/your/iac
```

**Filter to HIGH and above only:**
```bash
python scanner/main.py --path sample_configs --severity HIGH
```

**Write report to a custom path:**
```bash
python scanner/main.py --path sample_configs --output /tmp/report.md
```

**Print to stdout only (no file written):**
```bash
python scanner/main.py --path sample_configs --no-report
```

---

## Report Format

Reports are written to `reports/security-report.md` by default. Each finding includes:

```markdown
#### Finding N: <title>

**Severity:** 🔴 CRITICAL
**File:** `path/to/file`

**Explanation:**
Description of why this is a security risk.

**Remediation:**
Actionable steps to fix the issue.
```

The report opens with an executive summary table:

| Severity | Count |
|----------|-------|
| 🔴 CRITICAL | N |
| 🟠 HIGH | N |
| 🟡 MEDIUM | N |
| 🔵 LOW | N |

---

## Running Against Sample Configs

The `sample_configs/` directory contains deliberately insecure configurations covering all supported file types. Running the scanner against them will produce 20+ findings across all severity levels, demonstrating the full capability of the tool.

```
$ python scanner/main.py --path sample_configs

Infrastructure Security Scanner
================================
Scanning: .../sample_configs

  [+] Loaded [docker-compose]: insecure-docker-compose.yml
  [+] Loaded [kubernetes]: insecure-deployment.yaml
  [+] Loaded [env]: insecure.env
  [+] Loaded [terraform]: insecure-terraform.tf

Loaded 4 file(s). Running security checks...

============================================================
  SECURITY SCAN SUMMARY
============================================================
  Total findings : 30+
  CRITICAL  : 12
  HIGH      : 10
  MEDIUM    :  5
  LOW       :  4
============================================================

Report written to: reports/security-report.md
```

---

## Future Improvements

- **SARIF output** — emit findings in SARIF format for native GitHub Advanced Security / VS Code integration
- **JSON output** — machine-readable output for ingestion into SIEMs or dashboards
- **Ansible playbook support** — detect insecure `become: yes` usage and plaintext `vars`
- **Helm chart scanning** — unwrap Helm templates and scan rendered manifests
- **Custom rules via YAML** — allow teams to define project-specific rules without Python
- **CI/CD exit codes** — non-zero exit on CRITICAL findings to block pipeline promotions
- **OPA/Rego integration** — delegate policy evaluation to Open Policy Agent
- **Git pre-commit hook** — auto-scan staged IaC files before every commit
- **False-positive suppression** — inline `# nosec` / annotation-based exclusions
- **Remediation auto-fix** — generate patch files for common fixable issues

---

## License

MIT — see root repository LICENSE.
