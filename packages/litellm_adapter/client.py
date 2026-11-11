"""LiteLLM Router wrapper — the only module that imports litellm.

Lite edition: a thin wrapper. The full SaaS adapter handles streaming,
generation IDs, retry-cost accumulation, and structured error translation.
Lite covers the happy path and basic error mapping; that's enough for a
solo dev to ship a working router.
"""

from __future__ import annotations

import time

import structlog

from packages.litellm_adapter.deployment_attribution import (
    hidden_params_of,
    resolve_provider,
)
from packages.litellm_adapter.types import ProviderDeployment, UpstreamProviderError

logger = structlog.get_logger(__name__)


def _build_allowed_fails_policy():
    """Construct an AllowedFailsPolicy that fails fast on hard errors and is
    lenient on transient ones. Returns None if litellm doesn't expose the type
    (older versions), in which case the caller's `allowed_fails` int applies
    uniformly.

    LiteLLM cooldown semantics (1.83.x): a deployment is cooled down when
    its failure count *exceeds* the resolved allowed-fails value, where
    `resolved = policy_value or router.allowed_fails`. Because `0` is
    falsy in that `or`, a policy value of 0 alone has NO effect — it
    silently inherits the router default. We rely on the caller setting
    `router_allowed_fails=0` (see app/config.py) so 0-valued policy entries
    here actually take effect: cool down on the very first failure for
    hard errors, give transient errors more headroom via non-zero values.
    """
    try:
        from litellm.types.router import AllowedFailsPolicy
    except Exception:
        return None
    return AllowedFailsPolicy(
        # 4xx is a mixed bucket — LiteLLM lumps these together with no way
        # to split them in AllowedFailsPolicy:
        #   - genuine deployment death:   model 404 / deprecated
        #   - client-side request error:  prompt too long, JSON malformed,
        #                                 unsupported parameter, model typo
        # The previous "0 = cool down on first failure" punished a single
        # client typo with a process-wide deployment freeze — actively
        # hostile during dev. 10 means a user can typo / oversize-prompt
        # their way through plenty of mistakes; if the deployment is
        # actually dead, the 11th failure still cools it within seconds.
        BadRequestErrorAllowedFails=10,
        # 401: API key is genuinely wrong / expired. No client-side
        # confusion possible — really cool down immediately.
        AuthenticationErrorAllowedFails=0,
        # 429: transient rate limit. Tolerate up to 3 in-window before cooling.
        RateLimitErrorAllowedFails=3,
        # 5xx: provider-side transient. Two strikes.
        InternalServerErrorAllowedFails=2,
        # Network timeouts: transient. Two strikes.
        TimeoutErrorAllowedFails=2,
    )


def _translate_error(exc: Exception, *, reasoning_sent: bool = False) -> UpstreamProviderError:
    import litellm

    msg = str(exc)
    if reasoning_sent and _refused_reasoning_control(exc, msg):
        return UpstreamProviderError(
            msg, http_status=400, error_type="unsupported_reasoning_effort"
        )
    # Local AI Connect dispatch failures are re-raised as LiteLLM exceptions
    # carrying the local code + status; recover them so callers see
    # `local_offline` / `local_not_approved` / `local_upstream_error` instead
    # of a generic upstream error.
    local_code = getattr(exc, "geek_local_code", None)
    local_status = getattr(exc, "geek_local_status", None)
    if isinstance(local_code, str) and isinstance(local_status, int):
        # A local runtime refusing `think`/`reasoning_effort` (Ollama answers
        # "does not support thinking") arrives as a generic upstream error;
        # it is a compatibility problem with the request, not an outage.
        if local_code == "local_upstream_error" and _names_refused_reasoning(msg):
            return UpstreamProviderError(
                msg, http_status=400, error_type="unsupported_reasoning_effort"
            )
        return UpstreamProviderError(msg, http_status=local_status, error_type=local_code)
    # A parameter the selected model/provider does not accept is a client-side
    # compatibility problem, not an outage. Reporting it as 503 told clients to
    # back off and retry a request that can never succeed.
    unsupported = _unsupported_param_error(exc, msg)
    if unsupported is not None:
        return unsupported
    if isinstance(exc, litellm.ContextWindowExceededError):
        return UpstreamProviderError(msg, http_status=422, error_type="context_length_exceeded")
    if isinstance(exc, litellm.NotFoundError):
        return UpstreamProviderError(msg, http_status=422, error_type="model_not_found")
    if isinstance(exc, litellm.RateLimitError):
        return UpstreamProviderError(msg, http_status=429, error_type="rate_limit_error")
    if isinstance(exc, litellm.AuthenticationError):
        return UpstreamProviderError(msg, http_status=503, error_type="upstream_auth_error")
    if isinstance(exc, litellm.Timeout):
        return UpstreamProviderError(msg, http_status=503, error_type="upstream_timeout")
    return UpstreamProviderError(msg, http_status=503, error_type="upstream_error")


# Markers a provider/adapter uses when it refuses a parameter it does not
# understand. Matched against the error text only after the exception type
# check, so a genuine outage with an unrelated message is unaffected.
_UNSUPPORTED_PARAM_MARKERS = (
    "unsupported parameter",
    "unsupported_parameter",
    "unrecognized request argument",
    "unknown parameter",
    "invalid parameter",
    "does not support",
    "not supported for",
    "unexpected keyword argument",
    "extra fields not permitted",
    "extra inputs are not permitted",
)

_REASONING_MARKERS = ("reasoning", "thinking", "effort")


def _names_refused_reasoning(msg: str) -> bool:
    lowered = msg.lower()
    return any(m in lowered for m in _UNSUPPORTED_PARAM_MARKERS) and any(
        t in lowered for t in _REASONING_MARKERS
    )


# Words a provider uses when it refuses the reasoning control we attached.
# Only consulted for an attempt that actually carried one (see
# `_refused_reasoning_control`), so an unrelated 400 never matches.
_REASONING_REFUSAL_TERMS = ("effort", "thinking", "reasoning", "budget")


def _refused_reasoning_control(exc: Exception, msg: str) -> bool:
    """A 400 for an attempt that carried a reasoning control, naming it.

    Providers word this many ways ("Invalid effort value", "Argument not
    supported on this model: reasoningEffort", "Budget 0 is invalid. This
    model only works in thinking mode"), so matching marker phrases alone
    misses most of them and they surfaced as a 503 outage. The attempt is
    known to have sent reasoning parameters, which is what makes the broader
    term match safe.
    """
    import litellm

    bad_request = getattr(litellm, "BadRequestError", None)
    is_400 = getattr(exc, "status_code", None) == 400 or (
        bad_request is not None and isinstance(exc, bad_request)
    )
    if not is_400:
        return False
    cls = getattr(litellm, "ContextWindowExceededError", None)
    if cls is not None and isinstance(exc, cls):
        return False
    lowered = msg.lower()
    return any(term in lowered for term in _REASONING_REFUSAL_TERMS)


def _unsupported_param_error(exc: Exception, msg: str) -> UpstreamProviderError | None:
    """Translate a refused-parameter failure into a 4xx compatibility error.

    `litellm.UnsupportedParamsError` is explicit. Providers that reject the
    field themselves answer with a 400 whose body names the parameter, so the
    message is checked for both an unsupported-parameter marker and a
    reasoning-related term — anything else keeps its existing treatment, so a
    real provider failure is never downgraded to a client error.
    """
    import litellm

    cls = getattr(litellm, "UnsupportedParamsError", None)
    if cls is not None and isinstance(exc, cls):
        if any(term in msg.lower() for term in _REASONING_MARKERS):
            return UpstreamProviderError(
                msg, http_status=400, error_type="unsupported_reasoning_effort"
            )
        return UpstreamProviderError(
            msg, http_status=400, error_type="unsupported_parameter"
        )
    status = getattr(exc, "status_code", None)
    if status != 400:
        return None
    lowered = msg.lower()
    if not any(marker in lowered for marker in _UNSUPPORTED_PARAM_MARKERS):
        return None
    if any(term in lowered for term in _REASONING_MARKERS):
        return UpstreamProviderError(
            msg, http_status=400, error_type="unsupported_reasoning_effort"
        )
    return UpstreamProviderError(msg, http_status=400, error_type="unsupported_parameter")


def _thinking_on(params: dict) -> bool:
    thinking = params.get("thinking")
    return isinstance(thinking, dict) and thinking.get("type") in ("enabled", "adaptive")


def _messages_for_attempt(messages: list, *, keep_thinking: bool) -> list:
    """Messages for one attempt, with preserved thinking blocks only where needed.

    Signed Anthropic thinking blocks travel on assistant turns as
    `thinking_blocks`. They go back to an Anthropic model with thinking on —
    which requires them on a tool loop — and nowhere else: LiteLLM forwards
    the field verbatim to OpenAI-style providers, which would hand one
    provider's reasoning (and signature) to another. A request without
    reasoning therefore reaches every model exactly as before.
    """
    if keep_thinking or not any(
        isinstance(m, dict) and "thinking_blocks" in m for m in messages or []
    ):
        return messages
    return [
        {k: v for k, v in m.items() if k != "thinking_blocks"} if isinstance(m, dict) else m
        for m in messages
    ]


def is_retryable(exc: Exception, *, reasoning_sent: bool = False) -> bool:
    """Should a failure on one candidate fail over to the next?

    Only failures that are specific to THAT deployment, or transient, fail
    over. Problems with the request itself or the operator's credentials do
    not: another model cannot fix a malformed request, and silently routing
    around a rejected key would hide it from the operator (and could repeat
    non-idempotent work).
    """
    import litellm

    # Never retried (client- or credential-side).
    for name in (
        "AuthenticationError",          # 401
        "PermissionDeniedError",        # 403
        "ContentPolicyViolationError",  # 400 (policy)
        "UnprocessableEntityError",     # 422
    ):
        cls = getattr(litellm, name, None)
        if cls is not None and isinstance(exc, cls):
            return False
    # Retryable (transient, or specific to this one deployment).
    for name in (
        "RateLimitError",               # 429
        "Timeout",
        "APIConnectionError",
        "InternalServerError",          # 500
        "BadGatewayError",              # 502
        "ServiceUnavailableError",      # 503
        "NotFoundError",                # model missing on THIS deployment
        "ContextWindowExceededError",   # another model may have a larger window
    ):
        cls = getattr(litellm, name, None)
        if cls is not None and isinstance(exc, cls):
            return True
    # A model refusing the reasoning control is specific to that model: the
    # next Auto candidate gets its own translation and may well accept it.
    if reasoning_sent and _refused_reasoning_control(exc, str(exc)):
        return True
    refused = _unsupported_param_error(exc, str(exc))
    if refused is not None and refused.error_type == "unsupported_reasoning_effort":
        return True
    bad_request = getattr(litellm, "BadRequestError", None)
    if bad_request is not None and isinstance(exc, bad_request):
        return False
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status == 408 or status == 429 or status >= 500
    # Unknown failure with no status: treat as transient (connection-level).
    return True


# Bounded backoff between attempts after a 429 only (other failures move to
# a different deployment immediately, so waiting would just add latency).
_RATE_LIMIT_BACKOFF_S = (0.25, 0.5, 1.0, 2.0)


class GeekCuboLLMClient:
    """Wraps a litellm.Router, routes by `model` alias, returns a dict."""

    def __init__(
        self,
        deployments: list[ProviderDeployment],
        *,
        strategy: str | None = None,
        preferred_models: list[str] | None = None,
        litellm_routing_strategy: str | None = None,
        # Router behavior knobs. Defaults keep prior behavior when caller
        # doesn't inject — but app code (router_cache.py) injects from
        # Settings so the deployment respects user config.
        cooldown_time: float = 1.0,
        allowed_fails: int | None = None,
        enable_pre_call_checks: bool = False,
        num_retries: int = 2,
    ):
        # Stash routing config on the instance so chat.py can read it without
        # re-querying the DB on every request.
        self.strategy = strategy or "balanced"
        self.preferred_models = list(preferred_models or [])

        # litellm-suppress-debug
        import litellm
        from litellm import Router
        litellm.suppress_debug_info = True
        litellm.vertex_project = None
        litellm.vertex_location = None

        # Local AI Connect deployments use a `geekcubo_local/...` wire model id;
        # the custom handler must be in LiteLLM's provider map before the
        # Router parses any such entry, or it fails with "provider not map".
        if any(
            getattr(d, "custom_llm_provider", None) == "geekcubo_local" for d in deployments
        ):
            from packages.litellm_adapter import local_provider  # noqa: F401

        model_list = []
        for d in deployments:
            params: dict = {
                "model": d.litellm_model,
                "api_key": d.api_key,
            }
            if d.api_base:
                params["api_base"] = d.api_base
            if d.custom_llm_provider:
                params["custom_llm_provider"] = d.custom_llm_provider
            if d.extra_headers:
                params["extra_headers"] = d.extra_headers
            if d.rpm:
                params["rpm"] = d.rpm
            if d.tpm:
                params["tpm"] = d.tpm
            if d.input_cost_per_token is not None:
                params["input_cost_per_token"] = d.input_cost_per_token
            if d.output_cost_per_token is not None:
                params["output_cost_per_token"] = d.output_cost_per_token
            entry: dict = {"model_name": d.model_name, "litellm_params": params}
            model_info: dict = {}
            if d.deployment_id:
                # Pins the Router's deployment id so aliases of one upstream
                # share cooldown / allowed-fails state instead of each
                # spelling failing its own way into a cooldown.
                model_info["id"] = d.deployment_id
            # Without supports_response_schema, some LiteLLM versions
            # re-wrap or tool-translate LangChain's json_schema
            # response_format and OpenAI rejects it as
            # "Invalid schema for response_format".
            if d.provider == "openai" or d.custom_llm_provider == "openai":
                model_info["supports_response_schema"] = True
            if model_info:
                entry["model_info"] = model_info
            model_list.append(entry)

        if not model_list:
            self._router = None
            self._deployments = []
            return

        router_kwargs: dict = {
            "model_list": model_list,
            "num_retries": num_retries,
            "timeout": 30.0,
            "enable_pre_call_checks": enable_pre_call_checks,
        }
        # cooldown_time=0 must translate to disable_cooldowns=True. Otherwise
        # LiteLLM treats 0 as falsy and silently substitutes its 1-second
        # default — the test/dev "no cooldown" mode wouldn't actually take
        # effect, and a single 4xx in CI would cool a deployment for 1s and
        # cross-contaminate the next test.
        if cooldown_time and cooldown_time > 0:
            router_kwargs["cooldown_time"] = cooldown_time
        else:
            router_kwargs["disable_cooldowns"] = True
        if allowed_fails is not None:
            router_kwargs["allowed_fails"] = allowed_fails
            # Per-error-type policy: 4xx (model_not_found, bad payload) means
            # the deployment is genuinely broken — fail fast. 429 / timeouts
            # are usually transient, so give them more chances before cooldown
            # to avoid taking a model offline because of one rate-limit spike.
            policy = _build_allowed_fails_policy()
            if policy is not None:
                router_kwargs["allowed_fails_policy"] = policy
        if litellm_routing_strategy:
            router_kwargs["routing_strategy"] = litellm_routing_strategy

        self._router = Router(**router_kwargs)
        self._deployments = deployments

    def _is_anthropic(self, model: str) -> bool:
        for d in self._deployments or []:
            if d.model_name == model:
                return d.provider == "anthropic" or str(d.litellm_model).startswith("anthropic/")
        return False

    async def acompletion(
        self,
        *,
        fallbacks: list | None = None,
        model_params: dict[str, dict] | None = None,
        **kwargs,
    ):
        """Dispatch a chat completion through the LiteLLM Router.

        Returns:
          - Streaming (`stream=True`): the LiteLLM stream wrapper, an async
            iterable of chunk objects. The caller (chat.py) is responsible for
            iterating and dict-converting each chunk. We do NOT coerce the
            wrapper to a dict here — that would consume the stream eagerly
            and produce garbage.
          - Non-streaming: a plain dict (the OpenAI ChatCompletion response)
            with an extra `_geekcubo_meta` key carrying provider attribution and
            measured latency.

        The `fallbacks` kwarg is passed through to LiteLLM's internal
        `async_function_with_fallbacks` cascade engine in the format
        `[{primary_model: [fb1, fb2, ...]}]`.

        `model_params` maps a model name to provider-specific parameters
        merged into that model's attempt only (reasoning controls differ per
        provider, so a fallback must never inherit the primary's
        translation). A model absent from a non-empty map is skipped: the
        caller found it unable to honour those parameters.
        """
        if self._router is None:
            raise UpstreamProviderError(
                "No provider keys configured. Set OPENAI_API_KEY (or another) "
                "in your env, or add a key via PUT /v1/providers/{provider}.",
                http_status=503,
                error_type="no_providers_configured",
            )
        # Fallbacks are cascaded HERE, not by LiteLLM: its generic cascade
        # fails over on every exception, including 401/403/400, which must
        # surface to the operator instead. Each attempt is a single-model
        # call; failures are classified before the next one is tried.
        chain: list[str] = [kwargs.get("model")]
        if fallbacks:
            for entry in fallbacks:
                for _primary, rest in (entry or {}).items():
                    chain.extend(m for m in (rest or []) if m not in chain)
        if model_params:
            chain = [m for m in chain if m in model_params] or chain[:1]
        is_streaming = bool(kwargs.get("stream"))
        # Tool-calling requests trigger litellm's MCP gateway import chain
        # (litellm/responses/mcp/...), which hard-imports the optional `mcp`
        # package and raises `No module named 'mcp'` before ever deciding
        # whether an MCP gateway is configured. This router never uses the MCP
        # gateway, so skip that handler explicitly (litellm's own escape hatch).
        if kwargs.get("tools"):
            kwargs["_skip_mcp_handler"] = True
        started = time.perf_counter()
        attempts: list[dict] = []
        resp = None
        for index, model in enumerate(chain):
            try:
                extra = (model_params or {}).get(model) or {}
                attempt = {**kwargs, **extra, "model": model}
                if "messages" in attempt:
                    attempt["messages"] = _messages_for_attempt(
                        attempt["messages"],
                        keep_thinking=self._is_anthropic(model) and _thinking_on(extra),
                    )
                resp = await self._router.acompletion(**attempt)
                break
            except Exception as exc:
                reasoning_sent = bool(extra)
                translated = _translate_error(exc, reasoning_sent=reasoning_sent)
                attempts.append({
                    "model": model,
                    "error_type": translated.error_type,
                    "status": getattr(exc, "status_code", None),
                })
                last = index == len(chain) - 1
                if last or not is_retryable(exc, reasoning_sent=reasoning_sent):
                    translated.attempts = attempts
                    raise translated from exc
                import litellm

                if isinstance(exc, litellm.RateLimitError):
                    import asyncio

                    await asyncio.sleep(
                        _RATE_LIMIT_BACKOFF_S[min(len(attempts) - 1, len(_RATE_LIMIT_BACKOFF_S) - 1)]
                    )
                logger.info(
                    "inference_fallback",
                    failed_model=model,
                    error_type=translated.error_type,
                    next_model=chain[index + 1],
                )

        if is_streaming:
            # Failover happened (if at all) before the stream started: the
            # wrapper is only returned once the upstream accepted the call,
            # so a second model's output is never spliced into a stream.
            try:
                resp._geek_attempts = attempts  # type: ignore[attr-defined]
            except Exception:
                pass
            # Stream wrappers are async iterables, not dicts. Return the raw
            # wrapper so the caller can `async for` over chunks. We forfeit
            # the `_geekcubo_meta` injection on streams (provider attribution and
            # latency for stream requests degrade to defaults in the request
            # log) — a documented tradeoff that keeps this adapter thin and
            # avoids wrapping LiteLLM's stream object.
            return resp

        latency_ms = int((time.perf_counter() - started) * 1000)
        # LiteLLM stashes per-call diagnostics on `_hidden_params` BEFORE we
        # serialize. Pull what we need out first, because `model_dump()` drops
        # private-prefixed attrs and we lose them otherwise.
        #   - response_cost: USD cost LiteLLM computed at the moment it knew
        #     the resolved provider, including cache_creation/cache_read
        #     multipliers and reasoning-token pricing. Authoritative.
        #   - custom_llm_provider: the provider LiteLLM actually routed to
        #     ("openai", "anthropic", "gemini", ...). Beats our own
        #     deployment-loop matching, which can mis-attribute when LiteLLM
        #     rewrites the model name to a dated alias mid-cascade.
        #   - model_id / api_base: which deployment won.
        hidden = hidden_params_of(resp)
        litellm_cost_usd = hidden.get("response_cost")
        litellm_provider = hidden.get("custom_llm_provider")

        # Convert litellm's ModelResponse to a plain dict + attach metadata.
        out = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)

        provider = resolve_provider(
            self._deployments,
            hidden=hidden,
            served_model=out.get("model"),
            requested_model=kwargs.get("model"),
            litellm_provider=litellm_provider,
        )

        out["_geekcubo_meta"] = {
            "provider": provider,
            "latency_ms": latency_ms,
            "cost_usd": litellm_cost_usd,
            # Failed attempts before the one that served. Failed calls return
            # an error body without usage, so they carry no billable tokens.
            "attempts": attempts,
        }
        from packages.litellm_adapter.deployment_attribution import (
            match_served_deployment,
            operator_price_meta,
        )

        out["_geekcubo_meta"].update(
            operator_price_meta(
                match_served_deployment(
                    self._deployments, hidden=hidden, served_model=out.get("model"),
                )
            )
        )
        return out
