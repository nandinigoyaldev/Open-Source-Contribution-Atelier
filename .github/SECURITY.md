# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| Latest  | ✅ Yes             |
| Older   | ❌ No              |

We only support the latest deployed version of **Open Source Contribution Atelier**. Please ensure you are testing against the current `main` branch before reporting a vulnerability.

## Reporting a Vulnerability

We take the security of this project seriously. If you discover a security vulnerability, please follow the steps below:

### ⚠️ Do NOT open a public issue

Security vulnerabilities should **never** be reported via public GitHub issues, discussions, or pull requests.

### How to Report

1. **Email us directly** at: **nandinigoyaldev@gmail.com**
2. Include the following in your report:
   - A detailed description of the vulnerability
   - Steps to reproduce the issue
   - The potential impact and severity
   - Any suggested fixes (optional but appreciated)

### What to Expect

| Step | Timeline |
|---|---|
| Acknowledgment of your report | Within **48 hours** |
| Initial assessment and triage | Within **5 business days** |
| Fix deployed (if confirmed) | Within **14 business days** |

We will keep you informed of the progress and credit you in the fix (unless you prefer to remain anonymous).

### Scope

The following are **in scope** for security reports:

- Authentication and authorization bypasses (JWT, OAuth)
- Cross-site scripting (XSS) in the frontend
- SQL injection or ORM exploitation in the backend
- Server-side request forgery (SSRF)
- Sensitive data exposure (API keys, tokens, PII)
- Privilege escalation

The following are **out of scope**:

- Denial of service (DoS) attacks
- Social engineering
- Issues in third-party dependencies (report these upstream)
- Vulnerabilities requiring physical access to the server

## Security Best Practices for Contributors

- Never commit secrets, API keys, or tokens to the repository
- Use environment variables (`.env`) for all sensitive configuration
- All `.env` files are listed in `.gitignore` — keep it that way
- Review the [CONTRIBUTING.md](.github/CONTRIBUTING.md) guidelines before submitting code

---

Thank you for helping keep **Open Source Contribution Atelier** safe for everyone! 🛡️
