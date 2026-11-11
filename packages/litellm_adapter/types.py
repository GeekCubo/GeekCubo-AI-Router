"""Types for the LiteLLM adapter layer.

Vendored from main repo with fields trimmed to what lite needs.
"""

from dataclasses import dataclass, field


@dataclass
class CompletionRequest:
    model: str
    messages: list[dict]
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    stream: bool = False
    stop: list[str] | None = None
    tools: list[dict] | None = None
    tool_choice: str | dict | None = None
    parallel_tool_calls: bool | None = None
    response_format: dict | None = None
    seed: int | None = None
    n: int = 1
    trace_id: str | None = None
    workspace_id: str | None = None
    metadata: dict | None = None


@dataclass
class CompletionResponse:
    id: str
    model: str
    provider: str
    choices: list[dict]
    usage: dict
    cost_usd: float
    latency_ms: int
    created: int
    raw_response: object | None = None
    generation_id: str = ""
    native_finish_reason: str = ""
    cached: bool = False
    routing_strategy: str = ""
    fallback_level: int = 0
    retry_costs: list[dict] = field(default_factory=list)


class UpstreamProviderError(Exception):
    def __init__(self, message: str, *, http_status: int, error_type: str) -> None:
        super().__init__(message)
        self.http_status = http_status
        self.error_type = error_type
        # Failed attempts that preceded this error (inference fallback).
        self.attempts: list[dict] = []


@dataclass
class ProviderDeployment:
    model_name: str
    litellm_model: str
    api_key: str
    api_base: str | None = None
    provider: str = ""
    rpm: int | None = None
    tpm: int | None = None
    custom_llm_provider: str | None = None
    extra_headers: dict | None = None
    # Operator-supplied per-token pricing (USD) for custom providers. When set,
    # LiteLLM uses these instead of its own catalog price for the wire model —
    # the aggregator's price, not the upstream brand's.
    input_cost_per_token: float | None = None
    output_cost_per_token: float | None = None
    # LiteLLM Router keys cooldown/health state by deployment id, which it
    # derives from the entry (model_name included). Two entries that are
    # really the SAME upstream under two names (e.g. an alias) must share one
    # id, or each name probes a dead upstream separately.
    deployment_id: str | None = None
    # True for custom (operator-configured) deployments. Their cost is ALWAYS
    # tokens x the operator's configured price — never a price LiteLLM looks
    # up from the model name the upstream echoes back (an aggregator that
    # answers `"model": "gpt-4o"` must not be billed at OpenAI's list rate).
    operator_priced: bool = False
    # Local AI Connect only: the connector adapter (ollama, lmstudio, ...)
    # serving the model. Reasoning controls differ per runtime (Ollama's
    # `think` vs an OpenAI-compatible `reasoning_effort`).
    local_adapter: str | None = None
    # Local AI Connect only: the `think` values the runtime reported for the
    # model (see app.reasoning.local_thinking_from_metadata); None = unknown.
    local_thinking: tuple[str, ...] | None = None
