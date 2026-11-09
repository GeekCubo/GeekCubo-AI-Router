# Security Policy

## Reporting a vulnerability

**Please do not report security vulnerabilities through public GitHub issues,
discussions or pull requests.**

Report them privately through GitHub's private vulnerability reporting:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**
   (<https://github.com/GeekCubo/GeekCubo-AI-Router/security/advisories/new>).
3. Describe the issue, the affected version or commit, and the steps to
   reproduce it. A proof of concept helps, but never include real credentials
   or data from someone else's installation.

You should receive an acknowledgement within **5 business days**. We will keep
you updated while we investigate, agree on a disclosure date with you, and
credit you in the advisory unless you prefer to stay anonymous.

## Supported versions

GeekCubo is a self-hosted project. Security fixes are made on `main` and
shipped in the next release and in the `edge` container image. Please update
to the latest release before reporting, and mention the version you tested.

## Scope

In scope: this repository's code: the router and API, the administrator
dashboard and its authentication and sessions, API-key handling, credential
encryption at rest, the installer, the Local AI Connect connector and the
published container images.

Out of scope: vulnerabilities in third-party AI providers, in your reverse
proxy or host configuration, and reports that require an already-compromised
administrator account or host.

## Security design notes

- GeekCubo API keys (`sk-geek-*`) are stored only as one-way hashes. A full
  key is shown once, at creation or rotation, and can never be retrieved.
- Provider credentials are encrypted at rest with `CREDENTIAL_ENCRYPTION_KEY`.
- The dashboard uses server-side sessions with CSRF protection and binds to
  loopback by default.

See [docs/security.md](docs/security.md) for operator guidance.
