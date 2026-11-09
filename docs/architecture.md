# Architecture, scope and development

[← Back to the README](../README.md)

## Source layout

```
app/
├── main.py               FastAPI factory, startup migrations, SPA mount
├── config.py             Settings (environment / .env)
├── auth_policy.py        Route classes: public, administrator, inference
├── middleware/auth.py    Session-cookie + CSRF and sk-geek-* enforcement
├── secret_provisioning.py  First-run CREDENTIAL_ENCRYPTION_KEY / API_KEY_PEPPER
├── auto_routing.py       Capability gate, price gate, strategy ranking
├── auto_planner.py       Policy: pools, tiers, fallback, escalation, stickiness
├── routing_policy.py     Policy schema and validation
├── routing_profiles.py   Named Auto profiles
├── router_cache.py       Deployments from provider keys, custom providers, local machines
├── custom_providers.py   Custom OpenAI-compatible providers + discovery
├── model_metadata.py     Catalog matching, tri-state capabilities, price provenance
├── model_intelligence.py Metadata-source parsers (LiteLLM, models.dev, Portkey)
├── quality_scores.py     Artificial Analysis scores + manual overrides
├── prompt_cache.py       Cross-provider exact-match cache (Redis or in-memory LRU)
├── web_search.py         Optional SearXNG / Brave / Tavily search
├── safe_fetch.py         SSRF-hardened outbound fetches
├── attachments/          Upload detection, extraction, storage
├── local_connect/        Local AI Connect hub, dispatcher, enrollment, catalog
├── protocols/            Anthropic and Gemini wire-format translation
└── routes/               HTTP routes (chat, dashboard chat, providers, routing, …)

packages/
├── litellm_adapter/      LiteLLM Router wrapper, built-in catalog, local provider
├── auth/                 Password/key hashing, AES-256-GCM, sessions
└── db/                   Models, engine, startup migrations, guards

geekcubo_connector/       Local AI Connect agent (`geekcubo-connector`)
design/                   Dashboard (HTML, CSS, JS; 12 languages)
integrations/             Tool configuration examples
```

## Scope: what GeekCubo deliberately is not

GeekCubo is a **single-workspace**, single-process server. By design, it has no:
- multi-tenancy, RBAC, SSO
- billing, wallets, points, partner program
- multi-user admin console, audit logs, trust & safety (one local administrator account is built in)
- multi-worker, multi-replica or Kubernetes deployment
- email / Slack / webhooks for alerts

## Testing

```bash
pip install -e ".[dev]"
PYTHONPATH=. pytest -q
```

The suite uses local mock upstreams and never calls a paid provider. Browser tests under `tests/ui` need the `ui` extra plus `playwright install chromium`; they otherwise skip. CI also runs `ruff check .`, `node --check design/app.js`, the localization tests (`python -m unittest design.test_i18n_unittest`), `bash -n install.sh`, a package build and a Docker smoke test. See `.github/workflows/ci.yml` for the exact commands.

## Roadmap

- [x] OpenAI-compatible chat completions
- [x] Streaming (SSE)
- [x] `model="auto"` policy-based routing with selectable strategies
- [x] Inference fallback and escalation
- [x] Encrypted BYOK at rest
- [x] Local analytics dashboard
- [x] CI (GitHub Actions)
- [x] Cross-provider prompt caching
- [x] Continue.dev / Aider / LangChain / Cursor / Vercel AI SDK integrations
- [x] Savings widget (cost of your traffic against a baseline model)
- [x] Local AI Connect (bring your own local models through an outbound agent)
- [ ] Tool calls through Local AI Connect
- [ ] Automatic (per-message) web search
- [ ] Embeddings + image-gen proxy

See [DEMO.md](../DEMO.md) for a scripted failover demo you can record yourself.
