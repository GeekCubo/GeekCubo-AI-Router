"""Settings — env-driven configuration for GeekCubo.

Single-workspace edition: ~15 fields versus ~40 in the SaaS settings.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

# Providers we accept from env vars. Must stay in sync with:
#   - the matching `<provider>_api_key` fields on Settings below
#   - `PROVIDERS_KNOWN` in design/app.js (dashboard quick-add chips)
#   - `_PROVIDER_BY_LITELLM_KEY` in packages/litellm_adapter/catalog.py
#     (which decides the runtime provider id for catalog entries)
#
# xAI / DeepSeek were missing here pre-2026-05, leaving their catalog
# models silently un-routable: the catalog had grok-4 + deepseek-v3 etc,
# but Settings didn't read XAI_API_KEY / DEEPSEEK_API_KEY, and the
# dashboard had no chip for them. Operators couldn't configure without
# raw curl PUT (or hit the wrong provider — famously: "grok" PUT'd into
# "groq", which is a different company).
_PROVIDERS_FROM_ENV = (
    "openai",
    "anthropic",
    "google",
    "groq",
    "together",
    "fireworks",
    "xai",          # Grok 2/3/4 series. NOTE: NOT the same as `groq`.
    "deepseek",     # deepseek-chat / -reasoner / -v3 / -v3.2.
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./geekcubo.db"

    # ── Redis (optional) ──────────────────────────────
    redis_url: str | None = None

    # ── Server ────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    # Only trust X-Forwarded-Proto / X-Forwarded-For when a reverse proxy you
    # control sits in front of Lite. Off by default: an untrusted client must
    # not be able to make the server believe an http request was https (which
    # would set Secure cookies on a plain-http origin and silently break
    # sign-in), or forge the client IP in session metadata.
    trust_proxy_headers: bool = False
    # The address clients use to reach this installation, e.g.
    # https://api.example.com. Shown on Settings -> API Keys and pre-filled in
    # Connect a tool (with /v1 appended). Empty = only the local loopback
    # endpoint is shown. Never derived from request headers. ./install.sh also
    # displays it.
    public_base_url: str = ""

    # ── Encryption ──
    # NOTE: credential_encryption_key is NOT auto-generated. If empty, the
    # app seals provider keys with a publicly-known dev key (with a loud
    # warning), and packages.db.guards refuses to boot once real
    # credentials are at stake. Generate one: `openssl rand -hex 32`.
    credential_encryption_key: str = ""
    # Prior CREDENTIAL_ENCRYPTION_KEY, used only during rotation. Startup
    # re-encrypts stored provider keys that still open with this value.
    # Leave empty (and unset the env var) after a successful migrate.
    credential_encryption_previous_key: str = ""
    api_key_pepper: str = ""
    # Explicit opt-out from the startup guard that refuses to run with the
    # publicly-known dev encryption key when real credentials are at stake.
    allow_insecure_dev_key: bool = False

    # ── Custom OpenAI-compatible providers ──
    # Comma-separated list of `host` or `host:port` entries (no scheme) that
    # are explicitly authorized as LOCAL/private custom-provider endpoints.
    # Matching hosts may use http:// and private/loopback IPs. This is the
    # ONLY path that bypasses the remote-HTTPS + public-IP requirement, and it
    # exists for self-hosted proxies the operator runs alongside GeekCubo.
    # Example: "localhost:8080,127.0.0.1:9000,my-proxy.internal"
    custom_provider_allowed_local_hosts: str = ""

    # ── Native Chat attachments ──
    # Directory for uploaded chat attachments. Empty = an `attachments/`
    # folder next to the SQLite database file (or ./attachments on Postgres).
    attachment_dir: str = ""
    # Per-file upload ceiling. Clamped to ABSOLUTE_MAX_UPLOAD_MB.
    attachment_max_mb: int = 25
    # Global switch; when false the upload endpoint rejects every file.
    attachments_enabled: bool = True

    # ── Local AI Connect ──
    # Global switch for the Local AI Connect feature. When false the agent
    # WebSocket endpoint refuses to accept connections and local/* models are
    # never deployed or listed. Useful when the feature must not be exposed.
    local_connect_enabled: bool = True
    # Advertised public base URL of this GeekCubo instance, used to build the
    # one-line install command shown in the wizard (e.g.
    # https://example.com). Empty = the generated command shows a placeholder
    # host; it is not derived from the request.
    local_connect_public_url: str = ""
    # Idle timeout for the agent WebSocket, seconds. The connector pings well
    # inside this window; a silent socket is closed and the machine shows as
    # offline.
    local_connect_heartbeat_seconds: int = 45
    # How long a one-time enrollment code stays valid, in minutes.
    local_connect_enrollment_ttl_minutes: int = 30

    # ── Provider keys via env (alternative to UI-stored keys) ──
    # Keep in sync with `_PROVIDERS_FROM_ENV` above. Pydantic-settings reads
    # case-insensitively (config: `case_sensitive=False`), so XAI_API_KEY,
    # xai_api_key, etc all hit the same field.
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    groq_api_key: str | None = None
    together_api_key: str | None = None
    fireworks_api_key: str | None = None
    xai_api_key: str | None = None
    deepseek_api_key: str | None = None

    # ── Quality scoring (Artificial Analysis) ──
    # API key from https://artificialanalysis.ai. Any key (Free, Pro or
    # Commercial) works with the Free language-models endpoint, which is the
    # default. When set, model="auto" with strategy="quality" picks the model
    # with the highest Intelligence Index from AA's benchmark aggregator.
    # Empty string disables AA scoring; quality strategy degrades to the
    # cost-based fallback. Attribution to AA is displayed in the dashboard
    # whenever scores are in use, as AA's API terms require on every tier.
    artificial_analysis_api_key: str = ""
    # Base of the supported V2 API. The legacy `/api/v2/data/*` endpoints were
    # retired on 2026-11-04 and answer 410 Gone.
    artificial_analysis_api_base: str = "https://artificialanalysis.ai/api/v2"
    # Opt in to the Pro list endpoint (`/language/models`). A key without a Pro
    # subscription gets 403 there; the client then falls back to the Free
    # endpoint, so enabling this never breaks synchronization.
    artificial_analysis_use_pro: bool = False
    # Optional full URL override for the models list (mirrors or tests). Empty
    # means "derive from artificial_analysis_api_base". A value pointing at a
    # retired `/api/v2/data/` path is ignored with a warning.
    artificial_analysis_models_url: str = ""

    # ── Router behavior (LiteLLM Router cooldown + cascade) ──
    # How long a deployment stays cooled-down after a failure. LiteLLM's
    # own default is 1 second (effectively no cooldown — a dead model
    # gets re-picked on the very next request).
    #
    # Our default is 60s — a developer-friendly middle ground:
    #   - long enough that a genuinely dead model isn't hammered every
    #     request while you debug
    #   - short enough that fixing your API key + waiting a minute beats
    #     restarting the process to clear in-memory cooldowns
    # Production deployments under sustained traffic should set this to
    # 600-3600 in `.env` to avoid burning quota on a known-dead model.
    # Tests should set 0 to disable cooldown entirely.
    router_cooldown_seconds: int = 60
    # Global default for failures-before-cooldown across all error types,
    # used by LiteLLM Router as the fallback when AllowedFailsPolicy returns
    # a falsy value. We set 0 so the policy's "fail fast on hard errors"
    # values (also 0) actually take effect — LiteLLM's internal
    # `allowed_fails = policy_value or router.allowed_fails` short-circuits
    # any 0 in the policy back to this default. Per-error-type leniency for
    # transients (429 / 5xx / timeouts) still applies via non-zero policy
    # values, set in client.py:_build_allowed_fails_policy().
    router_allowed_fails: int = 0
    # When True, LiteLLM filters deployments whose context window can't fit
    # the request before dispatching. Cheap pre-flight that prevents wasted
    # round-trips on prompts that would 422 anyway.
    router_pre_call_checks: bool = True
    # In-deployment retry count. The default applies to explicitly-pinned
    # model requests (where the user said "use this exact model, retry it").
    # The auto value is used when the request was model="auto" so cascade
    # to the next fallback candidate happens immediately instead of after
    # 2x in-deployment retries (which would add ~30-90s of perceived latency).
    router_num_retries_default: int = 2
    router_num_retries_auto: int = 0

    def env_provider_keys(self) -> dict[str, str]:
        """Return the configured ENV-sourced provider keys as {provider: key}."""
        out: dict[str, str] = {}
        for prov in _PROVIDERS_FROM_ENV:
            val = getattr(self, f"{prov}_api_key", None)
            if val:
                out[prov] = val
        return out


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
