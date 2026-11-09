# GeekCubo

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./design/brand/geekcubo-logo-dark.png">
  <img src="./design/brand/geekcubo-logo.png" alt="GeekCubo" width="320">
</picture>

**One gateway. Every AI model.**
A self-hosted, OpenAI-compatible AI gateway and LLM router. Bring your own provider keys; `model="auto"` picks a capable model for every request, with fallback and local cost tracking.

[![ci](https://github.com/GeekCubo/GeekCubo-AI-Router/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/GeekCubo/GeekCubo-AI-Router/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue)](#license)
[![website](https://img.shields.io/badge/website-geekcubo.com-2563eb)](https://geekcubo.com)

[English](./README.md) | [日本語](./README.ja.md) | [中文](./README.zh.md) | [한국어](./README.ko.md) | [Deutsch](./README.de.md) | [Français](./README.fr.md) | [Español](./README.es.md) | [Italiano](./README.it.md) | [Русский](./README.ru.md) | [Português](./README.pt.md) | [Tiếng Việt](./README.vi.md) | [हिन्दी](./README.hi.md)

## Contents

- [Why GeekCubo](#why-geekcubo)
- [Key features](#key-features)
- [Quickstart](#quickstart)
- [Call it from an SDK](#call-it-from-an-sdk)
- [Keys and endpoints](#keys-and-endpoints)
- [Connect OpenCode and other tools](#connect-opencode-and-other-tools)
- [How Auto routing works](#how-auto-routing-works)
- [Limitations](#limitations)
- [Documentation](#documentation)
- [Support GeekCubo](#support-geekcubo)
- [License](#license)

## Why GeekCubo

Automatic model routing should give developers control, not uncertainty. With your own provider keys it is not always obvious which provider handles a request, whether a fallback might use a separately billed service, or why a particular model was chosen.

GeekCubo is a server you run yourself where routing policies, eligible providers, model capabilities, pricing assumptions and fallback behaviour are visible and configurable: **your keys, your infrastructure, your routing decisions.** There is no hosted account, no routing wallet and no dependency on a GeekCubo-operated host.

GeekCubo builds on [OrcaRouter Lite](https://github.com/Continuum-AI-Corp/OrcaRouter-Lite), an open-source project released under the MIT License, and is independently developed and maintained. It is not affiliated with or endorsed by the original OrcaRouter developers. See [License](#license).

## Key features

- **OpenAI-compatible API** — `/v1/chat/completions` with streaming, plus native Anthropic Messages (`/v1/messages`, used by Claude Code) and Gemini (`/v1beta/models/...`) endpoints on the same routing pipeline.
- **`model="auto"`** — filters models by eligibility, confirmed price, required capabilities and context window, then ranks them with the strategy you choose (Balanced, Cheapest, Quality First, Adaptive, Adaptive-Gated). Unknown never counts as supported or free.
- **Bounded fallback** — retryable upstream failures move to the next capable candidate; every decision is explained in `x-geek-routing-*` response headers.
- **Bring your own keys** — built-in providers (OpenAI, Anthropic, Google, Groq, Together, Fireworks, xAI, DeepSeek), any OpenAI-compatible custom provider, and local models through [Local AI Connect](docs/local-ai-connect.md). Credentials are encrypted at rest.
- **Dashboard** — providers, routing profiles, model metadata, analytics and spend, an in-browser Chat, and **Connect a tool** configuration for OpenCode, Claude Code, Cursor, Continue, Cline, Kilo Code and SDKs. Twelve interface languages.
- **Secure by default** — a local administrator account with server-side sessions and CSRF protection, hash-only `sk-geek-*` inference keys, and a loopback-only default bind.
- **Simple to run** — one container, SQLite by default; Postgres and Redis optional.

## Quickstart

**Prerequisites:** Linux, macOS or WSL with Docker Engine 24+ and the Compose v2 plugin, about 1 GB RAM and 2 GB disk.

```bash
git clone https://github.com/GeekCubo/GeekCubo-AI-Router.git
cd GeekCubo-AI-Router
./install.sh
```

The installer checks Docker and Compose, creates `.env` from `.env.example` only when it is missing, runs `docker compose up -d --build`, waits for `/health`, and prints the dashboard URL. On a fresh install it also prints a **one-time administrator setup token**: open the dashboard, choose **Create Administrator Account**, and paste it. Rerunning the installer is safe; it never deletes the data volume or regenerates credentials.

<details>
<summary><b>Manual install (same Compose file)</b></summary>

```bash
cp .env.example .env
docker compose up -d --build

# Only while no administrator exists:
docker compose exec api python -m app.admin_cli setup-token
```

</details>

Then add provider keys in the dashboard (or as upstream keys in `.env`) and generate an `sk-geek-*` key under **Settings → API Keys**.

**Network exposure.** The bundled Compose file publishes the dashboard on `127.0.0.1:8787` only, so the administrator login is never exposed directly. For remote access use an SSH tunnel (`ssh -L 8787:127.0.0.1:8787 <user>@<server>`) or a TLS reverse proxy with `TRUST_PROXY_HEADERS=true`, and set `PUBLIC_BASE_URL` in `.env` to your own address (for example `https://api.example.com`). See [DEPLOYMENT.md](DEPLOYMENT.md).

**Secrets.** On first start GeekCubo generates `CREDENTIAL_ENCRYPTION_KEY` and `API_KEY_PEPPER` and stores them next to the database (`.geekcubo-secrets`, mode `0600`). Back them up together with the `geekcubo-data` volume, and never run `docker compose down -v`. See [Security](docs/security.md#encryption-at-rest).

## Call it from an SDK

The local base URL is `http://127.0.0.1:8787/v1`. From another machine use your own HTTPS address, `https://<your-host>/v1`; **Settings → API Keys** shows the exact endpoint for your installation.

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8787/v1",
    api_key="sk-geek-...",          # a GeekCubo key, not an OpenAI key
)
r = client.chat.completions.create(
    model="auto",                    # or a routing profile, or a specific model id
    messages=[{"role": "user", "content": "Hello!"}],
)
print(r.choices[0].message.content)
```

<details>
<summary><b>Node.js</b></summary>

```js
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://127.0.0.1:8787/v1",
  apiKey: process.env.GEEKCUBO_API_KEY,   // sk-geek-...
});

const r = await client.chat.completions.create({
  model: "auto",
  messages: [{ role: "user", content: "Hello!" }],
});
console.log(r.choices[0].message.content);
```

</details>

<details>
<summary><b>curl</b></summary>

```bash
curl http://127.0.0.1:8787/v1/chat/completions \
  -H "Authorization: Bearer $GEEKCUBO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"Hello!"}]}'
```

</details>

<details>
<summary><b>Streaming, Anthropic and Gemini SDKs</b></summary>

Streaming uses the standard OpenAI SSE format (`stream=True`). Claude Code and the Anthropic SDKs use `/v1/messages`; the google-genai SDK uses `/v1beta/models`. Base URLs for those clients have **no** `/v1` suffix. See [Connecting tools and SDKs](docs/integrations.md).

</details>

## Keys and endpoints

| Credential | Where it belongs | Purpose |
|---|---|---|
| Upstream provider key (`sk-...`, `sk-ant-...`, ...) | GeekCubo **server**: dashboard or server `.env` | GeekCubo calls OpenAI, Anthropic and others with it |
| GeekCubo inference key (`sk-geek-...`) | The **client**. Generated in **Settings → API Keys**, shown once, stored only as a hash | Clients authenticate to GeekCubo with it |
| `GEEKCUBO_API_KEY` | The client's environment | The variable GeekCubo-specific configs (Connect a tool) read the key from |
| `OPENAI_API_KEY` + `OPENAI_BASE_URL` | The client's environment | What generic OpenAI SDKs read; the value is still your `sk-geek-*` key |

The `OPENAI_API_KEY` in GeekCubo's *server* `.env` is your upstream OpenAI account, not a GeekCubo key. Lost an `sk-geek-*` key? It cannot be recovered; rotate or revoke it. Details: [Which key goes where](docs/security.md#which-key-goes-where).

The dashboard itself signs in with a username and password. Sessions last 12 hours (60 minutes idle), or up to 14 days with **Remember me** on a trusted device. Forgot the password? Run `docker compose exec api python -m app.admin_cli reset-password` on the host. See [Security](docs/security.md).

## Connect OpenCode and other tools

**Settings → Connect a tool** generates configuration for OpenCode, Claude Code, Cursor, Continue, Cline, Kilo Code, generic OpenAI clients, cURL and the Python/TypeScript SDKs, using your installation's endpoint. Keys are referenced through `GEEKCUBO_API_KEY` and never embedded.

For OpenCode 2.x, `opencode.jsonc`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "providers": {
    "geek": {
      "name": "GeekCubo",
      "env": ["GEEKCUBO_API_KEY"],
      "package": "@opencode/ai/providers/openai-compatible",
      "settings": { "baseURL": "http://127.0.0.1:8787/v1" },
      "models": { "auto": { "name": "GeekCubo auto" } }
    }
  }
}
```

Export `GEEKCUBO_API_KEY=sk-geek-...`, then select `geek/auto`. Replace the base URL with `https://<your-host>/v1` for a remote GeekCubo. The OpenCode 1.x format, Claude Code and the other tools are covered in [Connecting tools and SDKs](docs/integrations.md).

## How Auto routing works

Send `model="auto"` (or a routing-profile id) and GeekCubo:

1. keeps only **eligible** models: enabled providers with working keys, enabled models, approved local machines;
2. requires a **confirmed price** — an unknown price is never treated as free;
3. requires every **capability** the request needs (tools, vision, JSON mode, JSON Schema) to be *Supported*;
4. drops models whose known **context window** is too small, and applies the key's allowlist and the profile's restrictions;
5. **ranks** the rest with the selected strategy and tries them in order, up to the fallback limit.

The chosen model is returned in `x-geek-resolved-model`. If nothing qualifies, the request fails with a 422 that names the filter that emptied the pool instead of guessing. **Routing → Test a routing decision** shows the same reasoning without sending anything upstream. Full details: [Routing](docs/routing.md).

## Limitations

- **Single workspace, single process.** No multi-tenancy, RBAC or SSO, and no multi-worker or multi-replica deployment ([scope](docs/architecture.md#scope-what-geekcubo-deliberately-is-not)).
- **Local AI Connect does not return tool calls**, so Auto never routes requests that need tools to local models.
- **Chat web search** is manual per message; the automatic mode is reserved and not implemented. Audio attachments are passed as metadata only.
- **Cursor** works for chat models only; Cursor's own Tab completion and background agents keep using Cursor's models.
- Generated client configurations follow each tool's documented format. The OpenCode configs were verified with OpenCode 2.2.6 for text generation; agentic tool calling also depends on the model GeekCubo routes to.

## Documentation

| | |
|---|---|
| [Security & API keys](docs/security.md) | Administrator account, sessions, keys, encryption, backups, troubleshooting |
| [Routing](docs/routing.md) | Auto, strategies, policies, profiles, fallback |
| [Model Intelligence](docs/model-intelligence.md) | Metadata sources, pricing, capabilities |
| [Connecting tools and SDKs](docs/integrations.md) | Connect a tool, OpenCode, Claude Code, native protocols |
| [Local AI Connect](docs/local-ai-connect.md) | Local models through an outbound connector |
| [Chat](docs/chat.md) | Dashboard chat, web search, attachments |
| [API endpoints](docs/api.md) | Endpoints, model catalog, prompt cache, savings |
| [Architecture & development](docs/architecture.md) | Source layout, tests, roadmap |
| [Deployment](DEPLOYMENT.md) | VPS, reverse proxy, backup, upgrades |

## Support GeekCubo

GeekCubo is free, open-source, and independently developed. You can support its continued development by exploring services that complement your AI setup.

- [**AI API Providers**](https://geekcubo.com/providers/) — Discover compatible AI model providers.
- [**VPS & Cloud Hosting**](https://geekcubo.com/hosting/) — Explore hosting options for self-hosted deployments.
- [**VPN & Privacy**](https://geekcubo.com/vpn/) — Explore optional privacy and secure networking tools.

**Affiliate disclosure:** Some links may earn us a commission at no additional cost to you. Using them is optional and does not influence GeekCubo's model routing or provider compatibility.

## License

MIT. See [LICENSE](./LICENSE).

GeekCubo is derived from OrcaRouter Lite. The upstream MIT license and its
copyright notice ("Copyright (c) 2026 OrcaRouter contributors") are preserved
in [LICENSE](./LICENSE) and must be kept in copies and substantial portions of
the software.

Third-party assets keep their own licenses: the font outlines used in the logo
(Inter, SIL Open Font License 1.1) are covered by
[design/brand/FONT-LICENSE.txt](./design/brand/FONT-LICENSE.txt).
