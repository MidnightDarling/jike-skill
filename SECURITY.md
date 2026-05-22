# Security Policy

## Reporting Vulnerabilities

Please report security issues through GitHub Security Advisories for this
repository:

https://github.com/MidnightDarling/jike-skill/security/advisories/new

Do not post Jike tokens, QR payloads, exported private histories, or proof of
exploitation in public issues.

## Token Handling

Jike refresh tokens are long-lived credentials. Prefer environment variables for
normal use, and use `jike auth --out PATH` when writing token JSON to disk so the
file is created with owner-only permissions.
