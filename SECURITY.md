# Security Policy

## 🛡️ Commitment to Security

At **Open-Source Contribution Atelier**, security and user trust are paramount. We take vulnerabilities seriously and strive to maintain the highest security standards across our frontend, backend, APIs, and CI/CD automation pipelines.

---

## 📦 Supported Versions

Only the latest release/main branch receives active security updates and patches.

| Version | Supported          | Status |
| ------- | ------------------ | :---: |
| `main` (latest) | :white_check_mark: | Actively Supported |
| `< 1.0.0` (legacy) | :x: | End of Life |

---

## 🔒 Reporting a Vulnerability

If you discover a security vulnerability or potential exploit, please report it responsibly:

1. **Do NOT disclose vulnerabilities publicly** via GitHub Issues, PRs, or public discussions.
2. **Submit a Private Security Advisory**: Use GitHub's private vulnerability reporting feature at:
   👉 **[Report a Security Vulnerability](https://github.com/nandinigoyaldev/Open-Source-Contribution-Atelier/security/advisories/new)**
3. Alternatively, contact the maintainers directly via security email or private message.

### 📋 What to Include in Your Report

To help us triage and resolve issues quickly, please provide:
- A descriptive title and vulnerability classification (e.g., OWASP Top 10 category, CWE identifier).
- Detailed step-by-step reproduction instructions or Proof-of-Concept (PoC) payload.
- Affected endpoints, components, or files.
- Potential impact and severity assessment.
- Suggested fix or mitigation, if known.

---

## ⏱️ Response & Triage Timelines

We acknowledge and triage all security reports in accordance with the following SLA:

| Severity | Initial Response | Remediation / Patch SLA |
| :--- | :---: | :---: |
| **🔴 Critical (CVSS 9.0 - 10.0)** | Within 24 hours | Within 48 hours |
| **🟠 High (CVSS 7.0 - 8.9)** | Within 48 hours | Within 7 days |
| **🟡 Medium (CVSS 4.0 - 6.9)** | Within 72 hours | Within 30 days |
| **🔵 Low (CVSS 0.1 - 3.9)** | Within 5 days | Within 90 days / Next release |

---

## 🔍 Automated Security Scanning Schedule

| Scan Type | Frequency | Engine / Tool | Scope |
| :--- | :--- | :--- | :--- |
| **Dependency Audits** | Daily | Dependabot & `npm audit` / `pip-audit` | Python packages & npm dependencies |
| **Container & OS CVEs** | Weekly / On Push | Grype (SBOM) & Trivy | Docker base images & runtime layers |
| **Static Code Analysis** | On PR / Push | CodeQL & Semgrep | Backend Python & Frontend TypeScript |
| **Secret Scanning** | Real-time / Pre-commit | Gitleaks / GitGuardian | Secret, token, & key leakage prevention |

---

## 🛡️ False-Positive Management

Known false-positive CVEs and vetted non-exploitable risks are documented in `backend/scripts/vuln-allowlist.json`. Entries include technical rationale, review date, and scheduled reassessment windows.

---

Thank you for helping keep **Open-Source Contribution Atelier** safe and secure for the global developer community! 🚀
