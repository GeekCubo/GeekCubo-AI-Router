"""Client integration configuration generator.

Every generator returns REAL, copy-pasteable configuration for a documented
client format, built from this installation's actual routing ids. Rules:

* No secrets. API keys are always referenced through an environment variable
  or a client's own credential store — never embedded in a downloadable file.
* No invented formats. Where a client has no documented file format (Cursor,
  Cline) we return guided steps instead of pretending a JSON file exists.
* Compatibility is stated, not implied. Claude Code is offered because this
  server really implements the Anthropic Messages API; anything unverified is
  marked unsupported rather than shipped as "done".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# The provider id our OpenCode examples register. `geek/economy` in OpenCode
# sends `model: "economy"` to GeekCubo — the provider prefix is OpenCode's,
# the model value is ours.
OPENCODE_PROVIDER_ID = "geek"
OPENCODE_PROVIDER_NAME = "GeekCubo"

ENV_KEY = "GEEKCUBO_API_KEY"

# Every client's model field is rendered without a "/v1" suffix, because each
# SDK appends its own path.
DEFAULT_LOCAL_BASE = "http://127.0.0.1:8787/v1"


@dataclass
class IntegrationResult:
    app: str
    label: str
    filename: str
    language: str
    code: str
    steps: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    docs: str | None = None
    downloadable: bool = True
    supported: bool = True
    # Offered formats for this app (e.g. OpenCode legacy vs current).
    variants: list[dict[str, str]] = field(default_factory=list)
    variant: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "app": self.app,
            "label": self.label,
            "filename": self.filename,
            "language": self.language,
            "code": self.code,
            "steps": self.steps,
            "notes": self.notes,
            "warnings": self.warnings,
            "docs": self.docs,
            "downloadable": self.downloadable,
            "supported": self.supported,
            "variants": self.variants,
            "variant": self.variant,
        }


# ── helpers ───────────────────────────────────────────────────────────────


def _sdk_base(base_url: str) -> str:
    """Base URL without a trailing /v1 (client SDKs add it themselves)."""
    url = base_url.rstrip("/")
    if url.endswith("/v1"):
        url = url[: -len("/v1")]
    return url


def _jsonable(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)


def build(
    app: str,
    *,
    base_url: str,
    model: str,
    variant: str | None = None,
) -> IntegrationResult:
    """Render the configuration for one client.

    `model` is the value the client sends as `model` — `auto`, a profile slug,
    or a canonical provider/model id. `base_url` includes the `/v1` suffix.
    """
    fn = _GENERATORS.get(app)
    if fn is None:
        raise KeyError(app)
    return fn(base_url=base_url, model=model, variant=variant)


# ── OpenCode ──────────────────────────────────────────────────────────────


def _opencode(*, base_url: str, model: str, variant: str | None) -> IntegrationResult:
    """OpenCode supports two config shapes; they are not interchangeable.

    `providers` + `package`/`settings` is the current schema; `provider` +
    `npm`/`options` is the legacy one. Merging them produces a file OpenCode
    rejects, so the caller picks one.
    """
    variants = [
        {"id": "current", "label": "Current (providers / package)"},
        {"id": "legacy", "label": "Legacy (provider / npm)"},
    ]
    variant = variant or "current"
    if variant == "legacy":
        code = _jsonable(
            {
                "$schema": "https://opencode.ai/config.json",
                "provider": {
                    OPENCODE_PROVIDER_ID: {
                        "npm": "@ai-sdk/openai-compatible",
                        "name": OPENCODE_PROVIDER_NAME,
                        "options": {
                            "baseURL": base_url,
                            "apiKey": "{env:" + ENV_KEY + "}",
                        },
                        "models": {model: {"name": f"{OPENCODE_PROVIDER_NAME} {model}"}},
                    }
                },
            }
        )
        filename = "opencode.jsonc"
    else:
        code = _jsonable(
            {
                "$schema": "https://opencode.ai/config.json",
                "providers": {
                    OPENCODE_PROVIDER_ID: {
                        "name": OPENCODE_PROVIDER_NAME,
                        "package": "@ai-sdk/openai-compatible",
                        "settings": {
                            "baseURL": base_url,
                            "apiKey": "{env:" + ENV_KEY + "}",
                        },
                        "models": {model: {"name": f"{OPENCODE_PROVIDER_NAME} {model}"}},
                    }
                },
            }
        )
        filename = "opencode.jsonc"

    return IntegrationResult(
        app="opencode",
        label="OpenCode",
        filename=filename,
        language="json",
        code=code,
        variant=variant,
        variants=variants,
        steps=[
            f"Save this as `{filename}` in your project root (or `~/.config/opencode/{filename}` for every project).",
            f"Export your key: `export {ENV_KEY}=sk-geek-...`",
            "Merge it into your existing config rather than overwriting it — see the notes below.",
            f"Run `opencode`, then pick `{OPENCODE_PROVIDER_ID}/{model}` with the model switcher.",
        ],
        notes=[
            f"In OpenCode the model appears as `{OPENCODE_PROVIDER_ID}/{model}`. The provider prefix is OpenCode's; the value sent to GeekCubo is `{model}`.",
            "The API key is referenced as `{env:GEEKCUBO_API_KEY}` — no secret is written to the file.",
            "If your file is JSONC, comments are allowed; the generated config is plain JSON, which JSONC also accepts.",
        ],
        docs="https://opencode.ai/docs",
    )


# ── Claude Code ───────────────────────────────────────────────────────────


def _claude_code(*, base_url: str, model: str, variant: str | None) -> IntegrationResult:
    """Real environment configuration for the Anthropic Messages surface.

    GeekCubo implements POST /v1/messages (messages, streaming, tool use,
    count_tokens), so Claude Code can use it as an Anthropic-compatible
    gateway. `ANTHROPIC_BASE_URL` must NOT include /v1 — the client appends it.
    """
    root = _sdk_base(base_url)
    code = f"""# Claude Code — GeekCubo gateway
export ANTHROPIC_BASE_URL="{root}"
export ANTHROPIC_AUTH_TOKEN="${{{ENV_KEY}}}"   # your GeekCubo key (sk-geek-...)
export ANTHROPIC_MODEL="{model}"

# Then start Claude Code as usual
claude
"""
    settings = _jsonable(
        {
            "env": {
                "ANTHROPIC_BASE_URL": root,
                "ANTHROPIC_MODEL": model,
            }
        }
    )
    return IntegrationResult(
        app="claude-code",
        label="Claude Code",
        filename="claude-code.env",
        language="bash",
        code=code,
        steps=[
            f"Export your key first: `export {ENV_KEY}=sk-geek-...`",
            "Run the three exports above in the shell where you start Claude Code.",
            f"Start `claude`. Requests go to `{root}/v1/messages` on this GeekCubo.",
            "To make it permanent, add the env block to `~/.claude/settings.json` instead of your shell profile:",
            settings,
        ],
        notes=[
            "ANTHROPIC_BASE_URL has no /v1 suffix — Claude Code appends /v1/messages itself.",
            "ANTHROPIC_AUTH_TOKEN carries your GeekCubo key; GeekCubo then uses its own configured provider keys upstream.",
            f"Model selection: `{model}` resolves like any other request (auto profile, custom profile slug, or provider/model).",
            "Streaming, tool use and token counting are served by /v1/messages, /v1/messages?stream and /v1/messages/count_tokens.",
        ],
        warnings=[
            "Claude Code features that depend on Anthropic-hosted extras outside the Messages API (for example server-side web search tools) may not be available; they fail as ordinary unsupported-tool responses rather than silently degrading.",
        ],
        docs="https://docs.anthropic.com/en/docs/claude-code",
    )


# ── Cursor ────────────────────────────────────────────────────────────────


def _cursor(*, base_url: str, model: str, variant: str | None) -> IntegrationResult:
    """Cursor has no gateway config file — it is configured through its UI.

    Returning guided steps (not a fabricated JSON file) is the honest answer.
    """
    return IntegrationResult(
        app="cursor",
        label="Cursor",
        filename="cursor-setup.txt",
        language="text",
        code=f"""Cursor → Settings → Models → OpenAI API

  Base URL:     {base_url}
  API key:      sk-geek-...   (create one in GeekCubo → API Keys)
  Model name:   {model}
""",
        downloadable=False,
        steps=[
            "Open Cursor → Settings (⌘/Ctrl + ,) → Models.",
            "Under “OpenAI API”, enable “Override OpenAI Base URL”.",
            f"Set the base URL to `{base_url}`.",
            "Paste a GeekCubo key (GeekCubo → API Keys) into the OpenAI API key field.",
            f"Add `{model}` as a custom model name and select it in chat.",
            "Click Verify to confirm Cursor can reach the gateway.",
        ],
        notes=[
            "Cursor's own features (Tab completion, background agents, its hosted Auto) keep using Cursor's models. This integration only changes the model Cursor sends chat requests to.",
            "Cursor sends the OpenAI chat/completions format, which GeekCubo serves natively.",
        ],
        warnings=[
            "Cursor is closed-source and changes this UI between versions; the labels above may differ slightly.",
        ],
        docs="https://docs.cursor.com/settings/models",
    )


# ── Continue ──────────────────────────────────────────────────────────────


def _continue(*, base_url: str, model: str, variant: str | None) -> IntegrationResult:
    """Continue reads config.yaml (or config.json) from ~/.continue/."""
    code = f"""name: geekcubo
version: 0.0.1
schema: v1
models:
  - name: {OPENCODE_PROVIDER_NAME} {model}
    provider: openai
    model: {model}
    apiBase: {base_url}
    apiKey: ${ENV_KEY}
    roles:
      - chat
      - edit
      - apply
"""
    return IntegrationResult(
        app="continue",
        label="Continue",
        filename="config.yaml",
        language="yaml",
        code=code,
        steps=[
            "Open (or create) `~/.continue/config.yaml`.",
            "Paste the block above, merging it under your existing `models:` list.",
            f"Export your key so Continue can read it: `export {ENV_KEY}=sk-geek-...`",
            "Reload the Continue panel and select the new model.",
        ],
        notes=[
            "`provider: openai` selects Continue's OpenAI-compatible transport; `apiBase` points it at GeekCubo.",
            f"`{model}` may be `auto`, a profile slug, or a canonical provider/model id.",
            f"Continue resolves `${ENV_KEY}` from your environment; export it in the shell that starts your editor.",
        ],
        docs="https://docs.continue.dev/reference",
    )


# ── Cline ─────────────────────────────────────────────────────────────────


def _cline(*, base_url: str, model: str, variant: str | None) -> IntegrationResult:
    """Cline is configured in the extension UI (OpenAI Compatible provider)."""
    return IntegrationResult(
        app="cline",
        label="Cline",
        filename="cline-setup.txt",
        language="text",
        code=f"""Cline → Settings → API Configuration

  API Provider:      OpenAI Compatible
  Base URL:          {base_url}
  API Key:           sk-geek-...   (GeekCubo → API Keys)
  Model ID:          {model}
""",
        downloadable=False,
        steps=[
            "Open the Cline panel → Settings (gear icon) → API Configuration.",
            "Set API Provider to “OpenAI Compatible”.",
            f"Set Base URL to `{base_url}`.",
            "Paste a GeekCubo key into the API Key field.",
            f"Enter `{model}` as the Model ID and save.",
        ],
        notes=[
            "Cline's tool calling is OpenAI function calling, which GeekCubo forwards unchanged.",
            "Set the model's context window in Cline's model settings if it differs from the default.",
        ],
        docs="https://docs.cline.bot/",
    )


def _kilo_code(*, base_url: str, model: str, variant: str | None) -> IntegrationResult:
    """Kilo Code custom provider.

    Field names and the wizard path follow Kilo's official "OpenAI Compatible"
    documentation (kilo.ai/docs/ai-providers/openai-compatible). Kilo queries
    `<base url>/models` to auto-detect models, which GeekCubo serves.
    """
    root = _sdk_base(base_url)
    return IntegrationResult(
        app="kilo-code",
        label="Kilo Code",
        filename="kilo-setup.txt",
        language="text",
        code=f"""Kilo Code → Settings → Providers → Custom provider

  Provider ID:     geekcubo
  Display name:    GeekCubo
  Provider API:    OpenAI Compatible
  Base URL:        {base_url}
  API key:         sk-geek-...   (GeekCubo → API Keys)
  Models:          {model}       (or pick from the auto-fetched list)
""",
        downloadable=False,
        steps=[
            "Open Kilo Code in VS Code, click the gear icon (Settings), and select the Providers tab.",
            "Scroll to the bottom and click Custom provider.",
            "Set Provider ID to `geekcubo` and Display name to `GeekCubo`.",
            "Set Provider API to OpenAI Compatible.",
            f"Set Base URL to `{base_url}`.",
            "Paste a GeekCubo key into the API key field.",
            f"Click Fetch models, then select `{model}` — or type it manually if discovery fails.",
            "Click Submit. The model appears in Kilo's model picker.",
        ],
        notes=[
            "Kilo discovers models from `/v1/models`, so any model you can reach appears without typing it.",
            f"An existing routing profile slug works in place of `{model}`, e.g. `fast` — clients select a profile by using its slug as the model id.",
            "Provider API must be “OpenAI Compatible”, not “OpenAI Responses”: GeekCubo serves chat/completions.",
            f"Kilo's CLI reads the same provider from `kilo.json` with `baseUrl: \"{root}\"`.",
        ],
        docs="https://kilo.ai/docs/ai-providers/openai-compatible",
    )


# ── SDK / generic ─────────────────────────────────────────────────────────


def _generic(*, base_url: str, model: str, variant: str | None) -> IntegrationResult:
    code = f"""# Any OpenAI-compatible client
# base_url: {base_url}
# api_key:  ${ENV_KEY}
# model:    {model}
"""
    return IntegrationResult(
        app="generic",
        label="Generic OpenAI-compatible",
        filename="generic.txt",
        language="text",
        code=code,
        downloadable=False,
        steps=[
            f"Point any OpenAI-compatible client at `{base_url}`.",
            f"Authenticate with a GeekCubo key from the `{ENV_KEY}` environment variable.",
            f"Send `{model}` as the model.",
        ],
    )


def _curl(*, base_url: str, model: str, variant: str | None) -> IntegrationResult:
    code = f"""curl {base_url}/chat/completions \\
  -H "Authorization: Bearer ${{{ENV_KEY}}}" \\
  -H "Content-Type: application/json" \\
  -d '{_jsonable({"model": model, "messages": [{"role": "user", "content": "Hello!"}]})}'
"""
    return IntegrationResult(
        app="curl",
        label="cURL",
        filename="request.sh",
        language="bash",
        code=code,
        steps=[
            f"Export your key: `export {ENV_KEY}=sk-geek-...`",
            "Run the command above.",
            "Add `\"stream\": true` to the JSON body for server-sent events.",
        ],
        notes=[
            "Routing decisions come back in response headers: x-geek-routing-profile, -strategy, -tier and x-geek-resolved-model.",
        ],
    )


def _python(*, base_url: str, model: str, variant: str | None) -> IntegrationResult:
    code = f"""import os
from openai import OpenAI

client = OpenAI(
    base_url="{base_url}",
    api_key=os.environ["{ENV_KEY}"],
)

resp = client.chat.completions.create(
    model="{model}",
    messages=[{{"role": "user", "content": "Hello!"}}],
)
print(resp.choices[0].message.content)
print(resp.model)  # the model that actually served the request
"""
    return IntegrationResult(
        app="python",
        label="Python (OpenAI SDK)",
        filename="geekcubo_client.py",
        language="python",
        code=code,
        steps=[
            "Install the SDK: `pip install openai`",
            f"Export your key: `export {ENV_KEY}=sk-geek-...`",
            "Run the script.",
        ],
        notes=[
            "Streaming: pass `stream=True` and iterate the chunks.",
            "Tools: pass `tools=[...]` exactly as you would to OpenAI.",
        ],
    )


def _typescript(*, base_url: str, model: str, variant: str | None) -> IntegrationResult:
    code = f"""import OpenAI from "openai";

const client = new OpenAI({{
  baseURL: "{base_url}",
  apiKey: process.env.{ENV_KEY},
}});

const resp = await client.chat.completions.create({{
  model: "{model}",
  messages: [{{ role: "user", content: "Hello!" }}],
}});

console.log(resp.choices[0].message.content);
"""
    return IntegrationResult(
        app="typescript",
        label="JavaScript / TypeScript (OpenAI SDK)",
        filename="geekcubo-client.ts",
        language="typescript",
        code=code,
        steps=[
            "Install the SDK: `npm install openai`",
            f"Export your key: `export {ENV_KEY}=sk-geek-...`",
            "Run the file with your usual TS/JS toolchain.",
        ],
        notes=["Works in Node 18+ and in edge runtimes that support fetch."],
    )


_GENERATORS = {
    "opencode": _opencode,
    "claude-code": _claude_code,
    "cursor": _cursor,
    "continue": _continue,
    "cline": _cline,
    "kilo-code": _kilo_code,
    "generic": _generic,
    "curl": _curl,
    "python": _python,
    "typescript": _typescript,
}


def catalog() -> list[dict[str, Any]]:
    """The selectable apps, with an honest support statement for each."""
    return [
        {"id": "opencode", "label": "OpenCode", "supported": True,
         "note": "Two config formats supported."},
        {"id": "claude-code", "label": "Claude Code", "supported": True,
         "note": "Anthropic Messages API (tool use + streaming verified)."},
        {"id": "cursor", "label": "Cursor", "supported": "partial",
         "note": "Chat models only; Cursor's own Tab/agents are unaffected."},
        {"id": "continue", "label": "Continue", "supported": True, "note": "config.yaml."},
        {"id": "cline", "label": "Cline", "supported": True, "note": "OpenAI-compatible provider."},
        {"id": "kilo-code", "label": "Kilo Code", "supported": True,
         "note": "Custom provider (OpenAI Compatible); auto-detects models."},
        {"id": "generic", "label": "Generic OpenAI-compatible", "supported": True,
         "note": "Any client that speaks chat/completions."},
        {"id": "curl", "label": "cURL", "supported": True, "note": ""},
        {"id": "python", "label": "Python SDK", "supported": True, "note": ""},
        {"id": "typescript", "label": "JS / TS SDK", "supported": True, "note": ""},
    ]
