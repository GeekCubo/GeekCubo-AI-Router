"""Artificial Analysis V2 API migration: endpoints, schema, errors.

The legacy `/api/v2/data/llms/models` endpoint was retired on 2026-11-04 and
answers 410 Gone. These tests pin the replacement behavior:

* the Free list (`/api/v2/language/models/free`) is the default and works with
  any key; the Pro list (`/api/v2/language/models`) is opt-in and falls back to
  Free on 403;
* the V2 envelope (`tier`, `intelligence_index_version`, `pagination`, `data`)
  is parsed across every page, with performance medians read from the nested
  `performance` object;
* `null` stays "not measured" — never zero, never invented;
* 401 / 403 / 410 / 429 / timeout / malformed bodies are classified distinctly.

Fixtures follow the documented OpenAPI schema and the live Free response shape
(field names and nesting), with synthetic values.
"""

from __future__ import annotations

from typing import Any, Callable

import httpx
import pytest

FREE_URL = "https://artificialanalysis.ai/api/v2/language/models/free"
PRO_URL = "https://artificialanalysis.ai/api/v2/language/models"
LEGACY_URL = "https://artificialanalysis.ai/api/v2/data/llms/models"
TEST_KEY = "aa-test-key-not-real-0000"


def _evals(ii: float | None) -> dict[str, Any]:
    return {
        "artificial_analysis_intelligence_index": ii,
        "artificial_analysis_coding_index": None,
        "artificial_analysis_agentic_index": None,
        "artificial_analysis_finance_and_accounting_index": None,
        "artificial_analysis_strategy_and_ops_index": None,
        "artificial_analysis_legal_index": None,
        "artificial_analysis_healthcare_and_medical_index": None,
        "artificial_analysis_engineering_index": None,
        "artificial_analysis_economics_index": None,
    }


def free_model(name: str, slug: str, ii: float | None, tps: float | None,
               ttft: float | None, price_in: float | None = 1.0,
               price_out: float | None = 4.0) -> dict[str, Any]:
    """One entry in the Free-shape schema (no Pro-only fields)."""
    return {
        "id": f"00000000-0000-0000-0000-{abs(hash(slug)) % 10**12:012d}",
        "name": name,
        "slug": slug,
        "release_date": "2026-05-01",
        "model_creator": {"id": "11111111-1111-1111-1111-111111111111", "name": "Example"},
        "evaluations": _evals(ii),
        "artificial_analysis_intelligence_index_cost": None,
        "pricing": {
            "price_1m_input_tokens": price_in,
            "price_1m_output_tokens": price_out,
            "price_1m_cache_hit_tokens": None,
            "price_1m_cache_write_tokens": None,
        },
        "performance": {
            "median_output_tokens_per_second": tps,
            "median_time_to_first_token_seconds": ttft,
            "median_time_to_first_answer_token_seconds": ttft,
            "median_end_to_end_response_time_seconds": None,
        },
        "performance_v3": None,
    }


def pro_model(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Pro-shape entry: Free fields plus Pro-only extras."""
    entry = free_model(*args, **kwargs)
    entry["reasoning_model"] = False
    entry["context_window_tokens"] = 200_000
    entry["pricing"]["price_1m_blended_3_to_1"] = 1.75
    entry["pricing"]["price_1m_blended_7_to_2_to_1"] = 1.6
    entry["performance"]["percentile_05_output_tokens_per_second"] = 10.0
    return entry


def envelope(data: list[dict], *, tier: str = "free", page: int = 1,
             total_pages: int = 1) -> dict[str, Any]:
    return {
        "tier": tier,
        "intelligence_index_version": 5,
        "pagination": {
            "page": page,
            "page_size": 200,
            "total_pages": total_pages,
            "has_more": page < total_pages,
        },
        "data": data,
    }


def error(status: int, message: str, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, json={"error": message}, headers=headers or {})


def _patch_transport(monkeypatch, handler: Callable[[httpx.Request], httpx.Response]) -> list[httpx.Request]:
    """Route quality_index's httpx client through a MockTransport; record requests."""
    from packages.litellm_adapter import quality_index

    seen: list[httpx.Request] = []
    real = httpx.AsyncClient

    def _wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    transport = httpx.MockTransport(_wrapped)

    def _factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = transport
        return real(*args, **kwargs)

    monkeypatch.setattr(quality_index.httpx, "AsyncClient", _factory)
    return seen


@pytest.fixture
def aa_env(monkeypatch):
    from app import config as cfg
    from packages.litellm_adapter import quality_index

    monkeypatch.setenv("ARTIFICIAL_ANALYSIS_API_KEY", TEST_KEY)
    monkeypatch.delenv("ARTIFICIAL_ANALYSIS_MODELS_URL", raising=False)
    monkeypatch.delenv("ARTIFICIAL_ANALYSIS_USE_PRO", raising=False)
    cfg.get_settings.cache_clear()
    quality_index.reset_cache()
    yield monkeypatch
    cfg.get_settings.cache_clear()
    quality_index.reset_cache()


# ── endpoint selection ────────────────────────────────────────────────


def test_default_endpoint_is_free_v2(aa_env):
    from packages.litellm_adapter.quality_index import aa_models_url

    assert aa_models_url() == FREE_URL


def test_pro_endpoint_is_opt_in(aa_env):
    from app import config as cfg
    from packages.litellm_adapter.quality_index import aa_models_url

    aa_env.setenv("ARTIFICIAL_ANALYSIS_USE_PRO", "true")
    cfg.get_settings.cache_clear()
    assert aa_models_url() == PRO_URL


def test_legacy_url_override_is_ignored(aa_env):
    """An old .env still pointing at the retired path must not cause 410s."""
    from app import config as cfg
    from packages.litellm_adapter.quality_index import aa_models_url

    aa_env.setenv("ARTIFICIAL_ANALYSIS_MODELS_URL", LEGACY_URL)
    cfg.get_settings.cache_clear()
    assert aa_models_url() == FREE_URL


def test_custom_mirror_override_is_respected(aa_env):
    from app import config as cfg
    from packages.litellm_adapter.quality_index import aa_models_url

    aa_env.setenv("ARTIFICIAL_ANALYSIS_MODELS_URL", "https://mirror.example.com/models")
    cfg.get_settings.cache_clear()
    assert aa_models_url() == "https://mirror.example.com/models"


# ── schema parsing ────────────────────────────────────────────────────


async def test_free_schema_parses_nested_performance(aa_env):
    from packages.litellm_adapter import quality_index

    seen = _patch_transport(aa_env, lambda req: httpx.Response(200, json=envelope([
        free_model("Claude Opus 4.7 (max)", "claude-opus-4-7", 57.2, 51.3, 1.9),
        free_model("Claude Opus 4.7 (low)", "claude-opus-4-7-low", 50.0, 60.0, 0.8),
        free_model("GPT-5.5 (xhigh)", "gpt-5-5", 60.1, None, None),
    ])))
    idx = await quality_index.get_quality_index(
        catalog_ids={"claude-opus-4-7", "gpt-5.5"}, force_refresh=True,
    )
    assert idx.source == "live"
    # quality: max across variants; tps: max; ttft: min.
    assert idx.scores["claude-opus-4-7"] == 57.2
    assert idx.tps_scores["claude-opus-4-7"] == 60.0
    assert idx.ttft_scores["claude-opus-4-7"] == 0.8
    assert idx.scores["gpt-5.5"] == 60.1
    # Request went to the Free endpoint with the key in x-api-key.
    assert str(seen[0].url) == FREE_URL
    assert seen[0].headers["x-api-key"] == TEST_KEY


async def test_null_metrics_stay_missing_not_zero(aa_env):
    """Nulls mean "not measured"; they must not become 0 or a static guess."""
    from packages.litellm_adapter import quality_index

    _patch_transport(aa_env, lambda req: httpx.Response(200, json=envelope([
        free_model("Zeta Model 1", "zeta-model-1", None, None, None),
        free_model("Claude Opus 4.7", "claude-opus-4-7", 57.0, None, None),
    ])))
    metrics = quality_index._build_metrics_map(
        (await quality_index._fetch_remote(FREE_URL, TEST_KEY)),
        {"zeta-model-1", "claude-opus-4-7"},
    )
    assert "zeta-model-1" not in metrics.quality_scores
    assert "zeta-model-1" not in metrics.tps_scores
    assert "zeta-model-1" not in metrics.ttft_scores
    assert "claude-opus-4-7" not in metrics.tps_scores


async def test_all_pages_are_fetched(aa_env):
    from packages.litellm_adapter import quality_index

    def handler(req: httpx.Request) -> httpx.Response:
        page = int(req.url.params.get("page", "1"))
        if page == 1:
            return httpx.Response(200, json=envelope(
                [free_model("Claude Opus 4.7", "claude-opus-4-7", 57.0, 50.0, 1.0)],
                page=1, total_pages=2))
        return httpx.Response(200, json=envelope(
            [free_model("GPT-5.5", "gpt-5-5", 60.0, 70.0, 2.0)], page=2, total_pages=2))

    seen = _patch_transport(aa_env, handler)
    result = await quality_index.fetch_language_models(TEST_KEY)
    assert [e["slug"] for e in result.data] == ["claude-opus-4-7", "gpt-5-5"]
    assert result.pages == 2
    assert result.tier == "free"
    assert len(seen) == 2
    assert "page" not in seen[0].url.params
    assert seen[1].url.params["page"] == "2"


async def test_pagination_is_bounded(aa_env):
    """A server that always says has_more must not drain the daily quota."""
    from packages.litellm_adapter import quality_index

    def handler(req: httpx.Request) -> httpx.Response:
        page = int(req.url.params.get("page", "1"))
        return httpx.Response(200, json=envelope(
            [free_model(f"M{page}", f"m{page}", 10.0, 1.0, 1.0)], page=page, total_pages=10_000))

    seen = _patch_transport(aa_env, handler)
    result = await quality_index.fetch_language_models(TEST_KEY)
    assert len(seen) == quality_index._MAX_PAGES
    assert result.pages == quality_index._MAX_PAGES


async def test_pro_schema_parses_and_ignores_pro_only_fields(aa_env):
    from app import config as cfg
    from packages.litellm_adapter import quality_index

    aa_env.setenv("ARTIFICIAL_ANALYSIS_USE_PRO", "true")
    cfg.get_settings.cache_clear()
    seen = _patch_transport(aa_env, lambda req: httpx.Response(200, json=envelope([
        pro_model("Claude Opus 4.7 (max)", "claude-opus-4-7", 57.0, 50.0, 1.5),
    ], tier="pro")))
    result = await quality_index.fetch_language_models(TEST_KEY)
    assert str(seen[0].url) == PRO_URL
    assert result.tier == "pro"
    assert result.pro_fallback is False
    metrics = quality_index._build_metrics_map(result.data, {"claude-opus-4-7"})
    assert metrics.quality_scores == {"claude-opus-4-7": 57.0}
    assert metrics.tps_scores == {"claude-opus-4-7": 50.0}
    assert metrics.ttft_scores == {"claude-opus-4-7": 1.5}


async def test_pro_403_falls_back_to_free(aa_env):
    """Opting in to Pro with a Free key must not break synchronization."""
    from app import config as cfg
    from packages.litellm_adapter import quality_index

    aa_env.setenv("ARTIFICIAL_ANALYSIS_USE_PRO", "true")
    cfg.get_settings.cache_clear()

    def handler(req: httpx.Request) -> httpx.Response:
        if str(req.url).startswith(PRO_URL) and not str(req.url).startswith(FREE_URL):
            return error(403, "Language models list requires a Pro subscription")
        return httpx.Response(200, json=envelope([
            free_model("Claude Opus 4.7", "claude-opus-4-7", 57.0, 50.0, 1.5)]))

    seen = _patch_transport(aa_env, handler)
    result = await quality_index.fetch_language_models(TEST_KEY)
    assert result.pro_fallback is True
    assert result.endpoint == FREE_URL
    assert [str(r.url) for r in seen] == [PRO_URL, FREE_URL]


async def test_legacy_flat_fields_still_parse(aa_env):
    """Older mirrors carried the medians at the entry's top level."""
    from packages.litellm_adapter import quality_index

    metrics = quality_index._build_metrics_map([{
        "name": "Claude Opus 4.7",
        "evaluations": {"artificial_analysis_intelligence_index": 57},
        "median_output_tokens_per_second": 55,
        "median_time_to_first_token_seconds": 1.2,
    }], {"claude-opus-4-7"})
    assert metrics.tps_scores == {"claude-opus-4-7": 55.0}
    assert metrics.ttft_scores == {"claude-opus-4-7": 1.2}


# ── error classification ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (401, {"error": "Invalid API key"}, "invalid_key"),
        (403, {"error": "Language models list requires a Pro subscription"}, "insufficient_tier"),
        (410, {"error": "Gone", "message": "The legacy /api/v2/data/* endpoints were retired"}, "endpoint_retired"),
        (429, {"error": "Rate limit exceeded"}, "rate_limited"),
        (500, {"error": "Internal error"}, "server_error"),
        (502, {"error": "Bad gateway"}, "server_error"),
        (404, {"error": "Not found"}, "connection_failed"),
    ],
)
async def test_http_errors_are_classified(aa_env, status, body, expected):
    from packages.litellm_adapter import quality_index

    _patch_transport(aa_env, lambda req: httpx.Response(status, json=body, headers={"retry-after": "3600"}))
    with pytest.raises(httpx.HTTPStatusError) as ei:
        await quality_index.fetch_language_models(TEST_KEY)
    code, detail = quality_index._classify_fetch_error(ei.value)
    assert code == expected
    assert TEST_KEY not in detail
    assert "Invalid API key" not in detail  # upstream body is never echoed


def test_rate_limit_detail_mentions_reset_time():
    from packages.litellm_adapter import quality_index

    resp = httpx.Response(429, headers={"retry-after": "1800"},
                          request=httpx.Request("GET", FREE_URL))
    code, detail = quality_index._classify_fetch_error(
        httpx.HTTPStatusError("429", request=resp.request, response=resp))
    assert code == "rate_limited"
    assert "30 min" in detail


async def test_timeout_is_classified(aa_env):
    from packages.litellm_adapter import quality_index

    def handler(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=req)

    _patch_transport(aa_env, handler)
    with pytest.raises(httpx.TimeoutException) as ei:
        await quality_index.fetch_language_models(TEST_KEY)
    assert quality_index._classify_fetch_error(ei.value)[0] == "timeout"


@pytest.mark.parametrize("body", [
    {"result": {"models": []}},       # unknown envelope
    {"tier": "free", "data": "nope"},  # data not a list
])
async def test_malformed_body_is_classified(aa_env, body):
    from packages.litellm_adapter import quality_index

    _patch_transport(aa_env, lambda req: httpx.Response(200, json=body))
    with pytest.raises(quality_index._AAFetchUnusable) as ei:
        await quality_index.fetch_language_models(TEST_KEY)
    assert quality_index._classify_fetch_error(ei.value)[0] == "malformed_response"


async def test_non_json_body_is_classified(aa_env):
    from packages.litellm_adapter import quality_index

    _patch_transport(aa_env, lambda req: httpx.Response(200, text="<html>maintenance</html>"))
    with pytest.raises(quality_index._AAFetchUnusable) as ei:
        await quality_index.fetch_language_models(TEST_KEY)
    assert quality_index._classify_fetch_error(ei.value)[0] == "malformed_response"


def test_empty_and_unmatched_are_classified():
    from packages.litellm_adapter import quality_index

    empty = quality_index._AAFetchUnusable("AA returned empty data array")
    unmatched = quality_index._AAFetchUnusable("AA returned 12 entries but 0 mapped to catalog on any axis")
    assert quality_index._classify_fetch_error(empty)[0] == "no_data"
    assert quality_index._classify_fetch_error(unmatched)[0] == "no_catalog_match"


# ── sync persistence and fallbacks ────────────────────────────────────


async def test_410_keeps_previous_snapshot(aa_env, db_session):
    """A retired endpoint must not wipe a known-good snapshot."""
    from packages.litellm_adapter import quality_index

    state = {"gone": False}

    def handler(req: httpx.Request) -> httpx.Response:
        if state["gone"]:
            return httpx.Response(410, json={"error": "Gone"})
        return httpx.Response(200, json=envelope([
            free_model("Claude Opus 4.7", "claude-opus-4-7", 57.0, 50.0, 1.5)]))

    _patch_transport(aa_env, handler)
    await quality_index.get_quality_index(
        catalog_ids={"claude-opus-4-7"}, db=db_session, workspace_id="default",
    )
    quality_index.reset_cache()
    state["gone"] = True
    idx = await quality_index.get_quality_index(
        catalog_ids={"claude-opus-4-7"}, db=db_session, workspace_id="default",
        force_refresh=True,
    )
    assert idx.source == "stale-db"
    assert idx.scores["claude-opus-4-7"] == 57.0
