# Security Policy

## Supported Scope

This repository is intended for public collaboration. Please report vulnerabilities responsibly and avoid opening public issues for undisclosed security flaws.

## Reporting

- Email the maintainers or use a private disclosure channel
- Include reproduction steps, impact, and affected paths
- Do not include real secrets or personal data

## Secure Development Notes

- JWT configuration supports production hardening through environment variables
- Exercise verification is pattern-based and intentionally avoids arbitrary command execution
- GitHub OAuth is optional and should be configured only with approved credentials

# Security & Rate Limiting

This project uses Django Rest Framework's built-in throttling to protect authentication endpoints from brute-force and spam attacks.

## How it works
We use custom `_ProxyAwareThrottle` classes that correctly identify client IP addresses even when the application is running behind reverse proxies (like Nginx or AWS ALB).

## Configuration
Rates are defined in `settings.py` under `REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']`.

| Endpoint | Throttle Class | Limit |
| :--- | :--- | :--- |
| Login | `LoginThrottle` | 5/minute |
| Signup | `SignupThrottle` | 10/hour |
| Password Reset | `PasswordResetThrottle` | 3/hour |

## Setting up behind Proxies
If you are deploying this in production behind a load balancer, ensure `TRUSTED_PROXY_COUNT` is set in your environment variables to match the number of proxy hops to ensure IP-based throttling works correctly.