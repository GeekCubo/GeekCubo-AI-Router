"""Artificial Analysis quality + latency metrics — used to rank models in
the `quality`, `balanced`, and `fastest` routing strategies.

The strategy was historically implemented as "pick the most expensive
deployable model" — a fine proxy when newer flagships cost more than
older ones. Anthropic and OpenAI broke that assumption (Opus 4.7 is
3x cheaper than Opus 4 from May 2024 yet measurably stronger), so cost
no longer tracks capability. AA's Intelligence Index is a real
benchmark-aggregator score (MMLU-Pro, GPQA, MATH, HumanEval, etc.),
updated as new models ship and stable across providers.

PR 4 extends this from quality-only to three independent metrics:
  - quality (intelligence_index, max across reasoning variants)
  - TPS (median_output_tokens_per_second, max across variants)
  - TTFT (median_time_to_first_token_seconds, min across variants)

Why per-axis aggregation rules: TPS is stable across reasoning effort
(same token-emission speed) so max picks the best representative.
TTFT explodes with reasoning effort (1.77s → 32s for GPT-5.5 across
variants), so min picks the model's "fast mode" — what an operator
choosing `fastest` actually wants.

Three-layer cache:
  1. In-process dict (1h TTL) — fast, dies with the process
  2. DB snapshot (`quality_score_snapshots` table) — survives restart
     so a typical `docker compose down/up` doesn't burn an AA fetch
  3. AA `/api/v2/language/models/free` (any key; paginated) — truth.
     The legacy `/api/v2/data/llms/models` was retired on 2026-11-04 and
     now answers 410 Gone. Pro keys may opt in to `/api/v2/language/models`.

On AA failure, we serve stale from the in-process layer first, then
the DB layer (no time bound — better to serve old scores than to fall
back to cost-based, which is known wrong). Rotating the AA key
invalidates DB rows via the `api_key_hash` column so a snapshot taken
under one account doesn't get served under another.

Per-axis snapshot preservation: if a fresh AA fetch returns one axis
empty (eg AA renamed `median_output_tokens_per_second`), the saver
keeps the old axis's data instead of overwriting with `{}`. Prevents
upstream regressions from disabling a routing strategy.

Attribution: AA's API terms require attribution on every tier whenever
API data is displayed or shared. The dashboard shows "Powered by
Artificial Analysis" linking to artificialanalysis.ai next to the scores.
Data use is also governed by AA's Terms of Use and Data Platform Terms;
GeekCubo stores only the derived per-model numbers it routes on, locally,
and never redistributes the raw payload.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import math
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import httpx

from packages.db.models.quality_score_snapshot import QualityScoreSnapshot

logger = logging.getLogger("geekcubo.quality_index")

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

_CACHE_TTL_SECONDS = 60 * 60          # 1h
_FETCH_TIMEOUT_SECONDS = 10.0
_STALE_GRACE_SECONDS = 24 * 60 * 60   # 24h: keep serving last good value


@dataclass(frozen=True)
class QualityIndex:
    """One AA fetch result. Maps are keyed by our canonical model IDs.

    Field naming: `scores` is the legacy alias for `quality_scores`,
    preserved so existing callers (`idx.scores`) keep working. Internal
    code prefers `quality_scores` for symmetry with `tps_scores` /
    `ttft_scores`.

    `matched_count` is the union (size of distinct catalog IDs covered
    by ANY axis). Per-axis counts are exposed separately for callers
    that need to distinguish "AA gave us quality but no TPS" from
    "AA gave us neither".
    """

    scores: dict[str, float]
    fetched_at: float                 # monotonic seconds
    source: str                       # "live" | "stale-cache" | "missing-key" | "error"
    raw_count: int                    # how many AA entries were considered
    matched_count: int                # union(三轴): distinct catalog IDs in any axis
    tps_scores: dict[str, float] = field(default_factory=dict)
    ttft_scores: dict[str, float] = field(default_factory=dict)
    matched_count_quality: int = 0
    matched_count_tps: int = 0
    matched_count_ttft: int = 0


@dataclass(frozen=True)
class _AARawMetrics:
    """Raw AA payload after parse + per-axis variant aggregation.

    Internal to this module — exposed via QualityIndex for downstream
    consumers. Doesn't contain manual-override merging; that's the
    caller's job (see `app/quality_scores.py:resolve_model_metrics`).
    """

    quality_scores: dict[str, float]
    tps_scores: dict[str, float]
    ttft_scores: dict[str, float]
    raw_count: int
    matched_count_quality: int
    matched_count_tps: int
    matched_count_ttft: int


# Process-wide cache, keyed by API key (so swapping the key in tests
# or at runtime doesn't return stale data from a different account).
_cache: dict[str, QualityIndex] = {}


# Strip parenthetical qualifiers like "(max)", "(xhigh)", "(high)",
# "(low)", "(Non-reasoning, high)" — these mark reasoning-effort variants
# of the same underlying model. We aggregate per axis (max/max/min).
_QUALIFIER_RE = re.compile(r"\s*\([^)]*\)\s*$")


def _normalize_aa_id(aa_name: str) -> str:
    """Convert an AA display name to our canonical model id form.

    Examples:
      "Claude Opus 4.7 (max)"          -> "claude-opus-4-7"
      "GPT-5.5 (xhigh)"                -> "gpt-5-5"
      "Claude Sonnet 4.6 (max)"        -> "claude-sonnet-4-6"
      "Gemini 3.1 Pro Preview"         -> "gemini-3-1-pro-preview"
      "DeepSeek V4 Pro (Max)"          -> "deepseek-v4-pro"

    The output may not match a LiteLLM catalog id exactly; the lookup
    layer (`_match_catalog_id`) handles strip-prefix and family fallback.
    """
    s = _QUALIFIER_RE.sub("", aa_name).strip()
    s = s.lower()
    s = s.replace(" ", "-")
    s = s.replace(".", "-")
    return s


_DIGIT_DASH_DIGIT_RE = re.compile(r"(\d)-(\d)")


def _dotted_version_variants(bare: str) -> list[str]:
    """Generate alternates that put a dot back at any digit-dash-digit
    position. Handles litellm's inconsistent OpenAI versioning where
    some entries are stored with dots (`gpt-5.5`, `gpt-5.1`) but our
    normalizer's blanket `replace(".", "-")` produces `gpt-5-5`.

    Example: `gpt-5-5-mini` → `["gpt-5.5-mini"]`
             `gpt-5-1-2025-11-13` → `["gpt-5.1-2025-11-13",
                                      "gpt-5-1-2025.11-13",  ...]`

    Cheap to compute (typically 0-2 candidates) and only tried after
    exact + bare lookup fails, so the happy path is unaffected.
    """
    out: list[str] = []
    for m in _DIGIT_DASH_DIGIT_RE.finditer(bare):
        idx = m.start() + 1  # position of the dash
        out.append(bare[:idx] + "." + bare[idx + 1:])
    return out


def _match_catalog_id(normalized: str, catalog_ids: set[str]) -> str | None:
    """Find a LiteLLM catalog id that matches a normalized AA name.

    Tries, in order:
      1. Exact match
      2. Match with provider prefix stripped (the catalog already
         strips prefixes at load, but be defensive)
      3. Dotted-version match: try restoring `.` at any digit-dash-digit
         position. Litellm catalog stores `gpt-5.5` with the dot intact
         while our normalizer produces `gpt-5-5` from AA's "GPT-5.5",
         silently dropping AA scores for the entire OpenAI 5.x family
         without this fallback.
      4. Family match: any catalog id that starts with `normalized + "-"`
         (covers the case where AA gives a base name and the catalog
         has dated/versioned variants like "claude-opus-4-7-20260416")
      5. Last-segment match: half the catalog stores models under
         provider namespaces (`accounts/fireworks/models/qwen3-235b-a22b`,
         `Qwen/Qwen3-235B-A22B-Instruct-2507-tput`). Without unwrapping
         the namespace AND case-folding for compare, the entire Llama 4
         / Qwen3 / Yi / Phi / Mistral-via-Together family silently drops
         from AA matching.

    Returns the first matching catalog id, or None.
    """
    if normalized in catalog_ids:
        return normalized
    bare = normalized.split("/", 1)[-1] if "/" in normalized else normalized
    if bare in catalog_ids:
        return bare
    # Try dotted-version alternates BEFORE the family-prefix scan —
    # a hit here is a more specific match (gpt-5.5 the canonical id
    # vs gpt-5-mini-XXX as a stray family member of `gpt-5`).
    for alt in _dotted_version_variants(bare):
        if alt in catalog_ids:
            return alt
    # Family match — pick the longest suffix-extended id that starts with
    # our normalized base. Stable order via sort so test runs are reproducible.
    family_prefix = bare + "-"
    candidates = [c for c in catalog_ids if c.startswith(family_prefix)]
    if candidates:
        return sorted(candidates)[0]
    # Family match for dotted alternates — handles cases where AA gives
    # a base like "GPT-5.5" → "gpt-5-5" but the catalog only carries
    # the dated form "gpt-5.5-2026-04-23".
    for alt in _dotted_version_variants(bare):
        family_prefix = alt + "-"
        candidates = [c for c in catalog_ids if c.startswith(family_prefix)]
        if candidates:
            return sorted(candidates)[0]
    # Last-segment match (case-insensitive) for namespaced catalog ids.
    # Catalog stores half its entries under provider namespaces — match
    # against the post-slash trailing segment so AA's "Qwen3 235B" finds
    # `accounts/fireworks/models/qwen3-235b-a22b`. We try exact-segment
    # first, then segment-family, both in case-insensitive form.
    bare_lower = bare.lower()
    bare_family_lower = bare_lower + "-"
    exact_segment_hits: list[str] = []
    family_segment_hits: list[str] = []
    for cid in catalog_ids:
        if "/" not in cid:
            continue   # already covered by exact / family above
        last = cid.split("/")[-1].lower()
        if last == bare_lower:
            exact_segment_hits.append(cid)
        elif last.startswith(bare_family_lower):
            family_segment_hits.append(cid)
    if exact_segment_hits:
        return sorted(exact_segment_hits)[0]
    if family_segment_hits:
        return sorted(family_segment_hits)[0]
    # Same last-segment scan with dotted alternates — covers namespaced
    # catalog ids that also use dotted versions (eg unlikely but possible
    # `Qwen/Qwen3.5-...`).
    #
    # Collect ALL hits and pick `sorted(...)[0]` rather than `return cid`
    # mid-iteration. `catalog_ids` is a `set`; Python set iteration order
    # is hash-seeded and non-deterministic across processes (PYTHONHASHSEED
    # randomizes by default). Without sorting, two providers exposing
    # `.../qwen3.5-*` could route AA metrics to a different catalog id
    # on every restart, making routing decisions and tests flaky.
    dotted_exact: list[str] = []
    dotted_family: list[str] = []
    for alt in _dotted_version_variants(bare):
        alt_lower = alt.lower()
        alt_family_lower = alt_lower + "-"
        for cid in catalog_ids:
            if "/" not in cid:
                continue
            last = cid.split("/")[-1].lower()
            if last == alt_lower:
                dotted_exact.append(cid)
            elif last.startswith(alt_family_lower):
                dotted_family.append(cid)
    if dotted_exact:
        return sorted(dotted_exact)[0]
    if dotted_family:
        return sorted(dotted_family)[0]
    return None


def _num(v: Any) -> float | None:
    """Coerce AA's numeric fields. Rejects bool, non-numeric, NaN, inf,
    and negatives. Even one bad value (NaN) would poison min/max
    aggregation and the downstream min-max normalization."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    if not math.isfinite(v) or v < 0:
        return None
    return float(v)


def _build_metrics_map(
    aa_payload: list[dict[str, Any]], catalog_ids: set[str]
) -> _AARawMetrics:
    """Project AA's response into three per-axis maps.

    Aggregation rules per axis:
      - quality: max across variants (highest intelligence_index)
      - tps: max across variants (output token rate is stable; max picks the best)
      - ttft: min across variants (TTFT explodes with reasoning effort;
        min picks the model's non-reasoning "fast mode")

    Each axis is aggregated independently — we do NOT lock to same-row
    pairing. If we did, GPT-5.5 picked for `fastest` would carry its
    max-quality variant's TTFT (32s) instead of its true fast-mode TTFT
    (1.77s).

    AA fields (V2 language-models schema, Free and Pro):
      - intelligence_index: entry["evaluations"]["artificial_analysis_intelligence_index"]
      - output speed:       entry["performance"]["median_output_tokens_per_second"]
      - time to first token: entry["performance"]["median_time_to_first_token_seconds"]

    The retired legacy endpoint carried the two performance medians at the
    entry's top level; that location is still read as a fallback so old
    fixtures and mirrors keep parsing. `null` means "not measured" in AA's
    conventions and is never turned into a number here.
    """
    quality_scores: dict[str, float] = {}
    tps_scores: dict[str, float] = {}
    ttft_scores: dict[str, float] = {}
    raw_count = 0

    for entry in aa_payload:
        if not isinstance(entry, dict):
            continue
        raw_count += 1

        name = entry.get("name") or entry.get("slug") or entry.get("id")
        if not isinstance(name, str) or not name:
            continue

        normalized = _normalize_aa_id(name)
        catalog_id = _match_catalog_id(normalized, catalog_ids)
        if catalog_id is None:
            continue

        # AA's `evaluations` is normally a dict but we've seen
        # malformed responses pass a list or null; verify before .get().
        evals = entry.get("evaluations")
        if not isinstance(evals, dict):
            evals = {}

        quality = _num(evals.get("artificial_analysis_intelligence_index"))
        perf = entry.get("performance")
        if not isinstance(perf, dict):
            perf = {}
        tps = _num(perf.get("median_output_tokens_per_second",
                            entry.get("median_output_tokens_per_second")))
        ttft = _num(perf.get("median_time_to_first_token_seconds",
                             entry.get("median_time_to_first_token_seconds")))

        # Per-axis aggregate. Each axis keeps the most-useful variant
        # value: max for quality+throughput (higher = better), min for
        # TTFT (lower = faster, picks the non-reasoning variant).
        if quality is not None:
            prior = quality_scores.get(catalog_id)
            if prior is None or quality > prior:
                quality_scores[catalog_id] = quality
        if tps is not None:
            prior = tps_scores.get(catalog_id)
            if prior is None or tps > prior:
                tps_scores[catalog_id] = tps
        if ttft is not None:
            prior = ttft_scores.get(catalog_id)
            if prior is None or ttft < prior:
                ttft_scores[catalog_id] = ttft

    return _AARawMetrics(
        quality_scores=quality_scores,
        tps_scores=tps_scores,
        ttft_scores=ttft_scores,
        raw_count=raw_count,
        matched_count_quality=len(quality_scores),
        matched_count_tps=len(tps_scores),
        matched_count_ttft=len(ttft_scores),
    )


class _AAFetchUnusable(Exception):
    """Raised when an AA fetch returns nothing usable — schema mismatch,
    empty data array, or all entries unmatched on every axis. Distinct
    from a transport error so the caller can route it through the
    stale-fallback path instead of persisting an empty score map over
    a known-good snapshot.
    """


# ── Supported V2 endpoints ─────────────────────────────────────────────
#
# Verified against AA's OpenAPI spec (https://artificialanalysis.ai/api/v2/openapi)
# and the migration guide (https://artificialanalysis.ai/data-api/migrate-v2-data):
#
#   * Free  `/api/v2/language/models/free` — accepts any valid key (Free, Pro,
#     Commercial). Headline indices, median performance, input/output prices.
#   * Pro   `/api/v2/language/models` — Pro+ only; Free keys get 403. Adds
#     blended pricing, percentiles, context window, etc.
#
# Both share one envelope: {tier, intelligence_index_version, pagination, data}.
# Lists are paginated (`page`, 1-indexed; `pagination.has_more`).
#
# The legacy `/api/v2/data/*` family was retired on 2026-11-04 and returns
# 410 Gone with a link to the migration guide.

AA_FREE_PATH = "/language/models/free"
AA_PRO_PATH = "/language/models"
_LEGACY_PATH_MARKER = "/api/v2/data/"
# Hard cap on pages per sync. The Free list is ~4 pages of 200 today; the cap
# bounds quota use (100 requests/day on Free) if pagination ever misbehaves.
_MAX_PAGES = 20


def aa_models_url(pro: bool | None = None) -> str:
    """The models-list URL GeekCubo will call, derived from settings.

    `artificial_analysis_models_url` (if set) overrides the derived URL, except
    when it points at the retired legacy family — that would guarantee a 410,
    so it is ignored with a warning and the supported endpoint is used.
    """
    from app.config import get_settings

    s = get_settings()
    override = (getattr(s, "artificial_analysis_models_url", "") or "").strip()
    if override and _LEGACY_PATH_MARKER not in override:
        return override
    if override:
        logger.warning("aa_legacy_models_url_ignored")
    base = (getattr(s, "artificial_analysis_api_base", "") or
            "https://artificialanalysis.ai/api/v2").rstrip("/")
    use_pro = bool(getattr(s, "artificial_analysis_use_pro", False)) if pro is None else pro
    return base + (AA_PRO_PATH if use_pro else AA_FREE_PATH)


def aa_free_url() -> str:
    """The Free list URL, used as the fallback when a Pro request gets 403."""
    return aa_models_url(pro=False)


@dataclass(frozen=True)
class AAFetchResult:
    """One completed models-list fetch (all pages)."""

    data: list[dict[str, Any]]
    tier: str | None               # caller's actual tier, from `tier` / X-AA-Tier
    endpoint: str                  # URL that served the data (without query)
    pages: int
    intelligence_index_version: Any = None
    rate_limit_remaining: int | None = None
    pro_fallback: bool = False     # True when Pro was requested but Free served


def _envelope_data(body: Any) -> list[dict[str, Any]]:
    """Return the `data` list from a V2 envelope (or a bare list)."""
    if isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, list):
            return data
    if isinstance(body, list):
        return body
    raise _AAFetchUnusable(
        "Artificial Analysis returned an unrecognized response format."
    )


def _int_header(r: httpx.Response, name: str) -> int | None:
    try:
        return int(r.headers.get(name, ""))
    except (TypeError, ValueError):
        return None


async def _fetch_pages(
    client: httpx.AsyncClient, url: str, api_key: str
) -> AAFetchResult:
    headers = {"x-api-key": api_key, "Accept": "application/json"}
    data: list[dict[str, Any]] = []
    tier: str | None = None
    version: Any = None
    remaining: int | None = None
    page = 1
    while True:
        params = {"page": page} if page > 1 else None
        r = await client.get(url, headers=headers, params=params)
        r.raise_for_status()
        try:
            body = r.json()
        except ValueError as exc:
            raise _AAFetchUnusable(
                "Artificial Analysis returned a response that is not valid JSON."
            ) from exc
        data.extend(_envelope_data(body))
        remaining = _int_header(r, "x-ratelimit-remaining")
        if isinstance(body, dict):
            tier = body.get("tier") or tier
            version = body.get("intelligence_index_version", version)
        tier = tier or r.headers.get("x-aa-tier")
        pagination = body.get("pagination") if isinstance(body, dict) else None
        has_more = isinstance(pagination, dict) and pagination.get("has_more") is True
        if not has_more or page >= _MAX_PAGES:
            break
        page += 1
    return AAFetchResult(
        data=data, tier=tier, endpoint=url, pages=page,
        intelligence_index_version=version, rate_limit_remaining=remaining,
    )


# Metadata about the most recent completed models-list fetch in this process
# (tier, endpoint, page count). Read by the sync path for status display; reset
# before each fetch so a stale value is never attributed to a new sync.
_last_fetch_meta: dict[str, Any] = {}


async def fetch_language_models(
    api_key: str,
    url: str | None = None,
    timeout: float = _FETCH_TIMEOUT_SECONDS,
) -> AAFetchResult:
    """Fetch every page of the AA language-models list.

    When the Pro endpoint answers 403 (the key's tier doesn't include it), the
    Free endpoint is used instead, so opting in to Pro never breaks sync for a
    Free key. Every other HTTP error propagates for classification.
    """
    target = url or aa_models_url()
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as c:
        try:
            result = await _fetch_pages(c, target, api_key)
        except httpx.HTTPStatusError as exc:
            free = aa_free_url()
            if exc.response.status_code != 403 or target == free:
                raise
            result = dataclasses.replace(
                await _fetch_pages(c, free, api_key), pro_fallback=True
            )
    _last_fetch_meta.clear()
    _last_fetch_meta.update(
        tier=result.tier, endpoint=result.endpoint, pages=result.pages,
        pro_fallback=result.pro_fallback,
    )
    return result


async def _fetch_remote(url: str, api_key: str, timeout: float = _FETCH_TIMEOUT_SECONDS) -> list[dict[str, Any]]:
    """Fetch the models list and return the raw `data` array (all pages).

    Kept as the narrow seam tests patch. Raises `_AAFetchUnusable` on schema
    mismatch so the caller falls back to stale data rather than persisting
    `{}` and poisoning the DB snapshot. Network/HTTP errors propagate as-is.
    """
    result = await fetch_language_models(api_key, url=url, timeout=timeout)
    return result.data


def _api_key_hash(api_key: str) -> str:
    """sha256(key)[:16] — used as cache key in-memory and in the DB
    snapshot row. Same hash → same logical AA account; different hash →
    operator rotated keys, snapshots from before the rotation are stale
    by definition."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class _LoadedSnapshot:
    """A DB-loaded snapshot. Carries wall-clock age so the freshness
    check at the call site doesn't mix monotonic and wall-clock times.

    Per-axis fields populated from the new scores_json shape; legacy
    flat snapshots (quality-only, pre-PR4) hydrate quality_scores from
    the flat dict and leave tps/ttft empty + their counts at 0.
    """
    quality_scores: dict[str, float]
    tps_scores: dict[str, float]
    ttft_scores: dict[str, float]
    source: str
    raw_count: int
    matched_count_quality: int
    matched_count_tps: int
    matched_count_ttft: int
    wall_age_seconds: float   # how long ago the row was written, per the DB clock


def _parse_snapshot_blob(parsed: Any) -> tuple[
    dict[str, float], dict[str, float], dict[str, float], int, int, int, int
]:
    """Detect new vs legacy scores_json shape and extract per-axis maps.

    New shape: {"quality": {...}, "tps": {...}, "ttft": {...}, "meta": {...}}
    Legacy shape: {"model_id": float, ...} (quality-only, pre-PR4)

    Returns (quality, tps, ttft, raw_count, mc_quality, mc_tps, mc_ttft).
    """
    if not isinstance(parsed, dict):
        return ({}, {}, {}, 0, 0, 0, 0)

    if "quality" in parsed and isinstance(parsed.get("quality"), dict) and "meta" in parsed:
        meta = parsed.get("meta") or {}
        quality = {k: float(v) for k, v in (parsed.get("quality") or {}).items()}
        tps = {k: float(v) for k, v in (parsed.get("tps") or {}).items()}
        ttft = {k: float(v) for k, v in (parsed.get("ttft") or {}).items()}
        return (
            quality, tps, ttft,
            int(meta.get("raw_count", 0) or 0),
            int(meta.get("matched_count_quality", 0) or 0),
            int(meta.get("matched_count_tps", 0) or 0),
            int(meta.get("matched_count_ttft", 0) or 0),
        )

    # Legacy flat: {"model_id": float, ...} = quality only.
    quality = {k: float(v) for k, v in parsed.items() if isinstance(v, (int, float))}
    return (quality, {}, {}, len(quality), len(quality), 0, 0)


async def _load_db_snapshot(
    db: "AsyncSession", workspace_id: str, api_key_hash: str
) -> _LoadedSnapshot | None:
    """Read the most recent persisted snapshot for this workspace + key.

    Returns None on miss, JSON parse failure, or any DB error — callers
    treat absent snapshot as "fall through to AA fetch". We never let a
    DB hiccup take down quality routing.

    Wall-clock age is computed at load time using the DB's own `updated_at`
    column. We don't store `time.monotonic()` to the DB because the
    monotonic clock is per-process — a value saved by process A is
    meaningless when read by process B (would always look fresh, defeating
    the TTL).
    """
    from sqlalchemy import select
    try:
        row = (
            await db.execute(
                select(QualityScoreSnapshot).where(
                    QualityScoreSnapshot.workspace_id == workspace_id,
                    QualityScoreSnapshot.api_key_hash == api_key_hash,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        parsed = json.loads(row.scores_json)
        (
            quality, tps, ttft,
            raw_count_meta, mc_q, mc_t, mc_f,
        ) = _parse_snapshot_blob(parsed)
        # Compute wall-clock age. `updated_at` is server-default `func.now()`
        # so it's UTC on both SQLite and Postgres; coerce naive (SQLite) to
        # UTC for consistent arithmetic.
        wall_now = datetime.now(timezone.utc)
        row_ts = row.updated_at
        if row_ts.tzinfo is None:
            row_ts = row_ts.replace(tzinfo=timezone.utc)
        age = max(0.0, (wall_now - row_ts).total_seconds())
        # Prefer the DB column for raw_count (authoritative for legacy rows
        # written before meta carried it); fall back to meta if column 0.
        raw_count = int(row.raw_count) or raw_count_meta
        return _LoadedSnapshot(
            quality_scores=quality,
            tps_scores=tps,
            ttft_scores=ttft,
            source=row.source,
            raw_count=raw_count,
            matched_count_quality=mc_q,
            matched_count_tps=mc_t,
            matched_count_ttft=mc_f,
            wall_age_seconds=age,
        )
    except Exception:
        return None


async def _save_db_snapshot(
    db: "AsyncSession",
    workspace_id: str,
    api_key_hash: str,
    source: str,
    metrics: _AARawMetrics,
) -> None:
    """Upsert the snapshot for this workspace + key. Never raises —
    persisting is best-effort; the in-process cache is still the
    authoritative source for the current request.

    Writes new scores_json shape:
      {"quality": {...}, "tps": {...}, "ttft": {...},
       "meta": {raw_count, matched_count_quality, _tps, _ttft}}

    Updates the legacy `matched_count` column to union(三轴 keys) so the
    "X of Y AA models indexed" UI string still reads as the count of
    catalog IDs with at least one indexed axis (NOT max — max would
    misleadingly under-report when axes cover different model sets).

    Uses `session.merge()` for the upsert: portable across SQLite /
    Postgres / MySQL, race-safe under multi-worker fan-out (vs the
    select-then-insert pattern which would IntegrityError when two
    workers fetch AA simultaneously and both try to insert).
    """
    try:
        blob = {
            "quality": metrics.quality_scores,
            "tps": metrics.tps_scores,
            "ttft": metrics.ttft_scores,
            "meta": {
                "raw_count": metrics.raw_count,
                "matched_count_quality": metrics.matched_count_quality,
                "matched_count_tps": metrics.matched_count_tps,
                "matched_count_ttft": metrics.matched_count_ttft,
            },
        }
        scores_json = json.dumps(blob, separators=(",", ":"))
        union_count = len(
            set(metrics.quality_scores)
            | set(metrics.tps_scores)
            | set(metrics.ttft_scores)
        )
        # `merge` syncs a detached/new instance with whatever is in the DB,
        # keyed by primary key. Inserts when missing, updates when present.
        # Works identically across all SQLAlchemy-supported dialects.
        # `updated_at` is set by the DB's `onupdate=func.now()` trigger —
        # we don't pass it from app code, so the wall-clock timestamp
        # always comes from the same authoritative source (the DB).
        await db.merge(QualityScoreSnapshot(
            workspace_id=workspace_id,
            api_key_hash=api_key_hash,
            source=source,
            raw_count=metrics.raw_count,
            matched_count=union_count,
            scores_json=scores_json,
        ))
        await db.commit()
    except Exception:
        # Never let a write failure kill the request path. The in-process
        # cache still has the fresh value; we'll retry the persist on the
        # next refresh.
        try:
            await db.rollback()
        except Exception:
            pass


async def _persist_with_axis_preservation(
    db: "AsyncSession",
    workspace_id: str,
    api_key_hash: str,
    source: str,
    new: _AARawMetrics,
) -> _AARawMetrics:
    """Save a fresh fetch, preserving any axis that came back empty
    by reusing the previous snapshot's data for that axis.

    Why: AA upstream regressions (renamed field, partial outage) can
    return e.g. quality intact but TPS empty. Without this, the saver
    overwrites the good TPS map with `{}` and disables `fastest`
    routing on the next request.

    Snapshot PK is composite `(workspace_id, api_key_hash)`. Both
    must filter the load — preserving an axis from a different AA
    account's snapshot would silently mix benchmark data across keys.

    Returns the merged metrics that were persisted (so callers can
    promote the merged version into the in-process cache).
    """
    old = await _load_db_snapshot(db, workspace_id, api_key_hash)
    merged = new
    if old is not None:
        # Per-axis: if NEW lost coverage but OLD had it, keep OLD's
        # values for that axis. Only the axis that regressed is held;
        # axes with fresh data are taken from NEW.
        if new.matched_count_quality == 0 and old.matched_count_quality > 0:
            merged = dataclasses.replace(
                merged,
                quality_scores=dict(old.quality_scores),
                matched_count_quality=old.matched_count_quality,
            )
        if new.matched_count_tps == 0 and old.matched_count_tps > 0:
            merged = dataclasses.replace(
                merged,
                tps_scores=dict(old.tps_scores),
                matched_count_tps=old.matched_count_tps,
            )
        if new.matched_count_ttft == 0 and old.matched_count_ttft > 0:
            merged = dataclasses.replace(
                merged,
                ttft_scores=dict(old.ttft_scores),
                matched_count_ttft=old.matched_count_ttft,
            )
    await _save_db_snapshot(db, workspace_id, api_key_hash, source, merged)
    return merged


def _apply_static_baseline(qi: QualityIndex, catalog_ids: set[str]) -> QualityIndex:
    """Merge static quality + latency scores under AA data. Static = floor, AA = ceiling.

    Called at every return path so models absent from AA's dataset
    (new releases, catalog-only IDs) always get routing scores on all three axes.
    Only IDs present in `catalog_ids` are merged — prevents leaking the
    full static tables into callers that pass a restricted/synthetic catalog.
    """
    try:
        from packages.litellm_adapter.quality_scores_static import (
            STATIC_QUALITY,
            STATIC_TPS,
            STATIC_TTFT,
        )
    except ImportError:
        return qi
    if not STATIC_QUALITY and not STATIC_TPS and not STATIC_TTFT:
        return qi

    # AA publishes hyphenated keys (`claude-opus-4-7`) but our catalog carries
    # the dotted form (`claude-opus-4.7`) for some models. Build a reverse index so we can
    # rekey hyphenated static rows to their dotted catalog id — keeping the
    # QualityIndex contract that scores are keyed by catalog id, not AA's
    # canonical name. (A pure dot→hyphen fallback at read time only saves
    # callers that go through `_lookup_score`; direct `scores.get(m.id)`
    # consumers like /v1/quality would still see the model as unscored.)
    hyphen_to_dotted = {
        cid.replace(".", "-"): cid
        for cid in catalog_ids
        if "." in cid
    }

    def _merge(static: dict[str, float], live: dict[str, float]) -> dict[str, float]:
        out: dict[str, float] = {}
        for k, v in static.items():
            if k in catalog_ids:
                out[k] = v
            # Also write under the dotted catalog id when the static row is
            # the hyphenated AA form. Both forms get the score when both are
            # deployable (LiteLLM ships hyphen + supplement adds dotted).
            dotted = hyphen_to_dotted.get(k)
            if dotted is not None:
                out[dotted] = v
        out.update(live)  # live (AA) wins on overlap
        return out

    merged_quality = _merge(STATIC_QUALITY, qi.scores)
    merged_tps     = _merge(STATIC_TPS,     qi.tps_scores)
    merged_ttft    = _merge(STATIC_TTFT,    qi.ttft_scores)

    return dataclasses.replace(
        qi,
        scores=merged_quality,
        tps_scores=merged_tps,
        ttft_scores=merged_ttft,
        matched_count=len(set(merged_quality) | set(merged_tps) | set(merged_ttft)),
        matched_count_quality=len(merged_quality),
        matched_count_tps=len(merged_tps),
        matched_count_ttft=len(merged_ttft),
    )


async def resolve_aa_api_key(
    db: "AsyncSession | None" = None, workspace_id: str = "default"
) -> tuple[str, str]:
    """Return (api_key, origin) where origin is "stored" | "env" | "missing".

    A key saved through the dashboard wins over `ARTIFICIAL_ANALYSIS_API_KEY`.
    The alternative -- env always winning -- means an operator saves a key,
    sees no change, and has no way to tell why; the stored value is the more
    recent, more explicit statement of intent.

    Kept separate from `get_quality_index` so the status endpoint can report
    where the key came from without triggering a fetch.
    """
    if db is not None:
        try:
            from sqlalchemy import select

            from packages.auth.encryption import decrypt_credential
            from packages.db.models.quality_settings import QualitySettings

            row = (
                await db.execute(
                    select(QualitySettings).where(
                        QualitySettings.workspace_id == workspace_id
                    )
                )
            ).scalar_one_or_none()
            if row is not None and row.encrypted_api_key:
                return decrypt_credential(row.encrypted_api_key), "stored"
        except Exception:
            # A corrupt or undecryptable row must not disable quality routing
            # outright; fall through to the environment.
            logger.warning("quality_settings_key_unreadable", exc_info=True)

    from app.config import get_settings

    env_key = get_settings().artificial_analysis_api_key
    return (env_key, "env") if env_key else ("", "missing")


async def get_quality_index(
    *,
    catalog_ids: set[str],
    db: "AsyncSession | None" = None,
    workspace_id: str = "default",
    force_refresh: bool = False,
) -> QualityIndex:
    """Return the current AA metrics map for our catalog.

    Read order:
      1. In-process cache (1h TTL) — fastest, single-process scope.
      2. DB snapshot (`quality_score_snapshots`) — survives restart.
         Only consulted if `db` is supplied; tests of pure parsing logic
         pass `db=None` and skip this layer.
      3. AA `/api/v2/language/models/free` (or the Pro list when enabled) —
         fresh truth. Free keys have 100 requests/day; one sync uses one
         request per page (about four today).

    Write order on AA success: in-process cache + DB snapshot
    (best-effort, with per-axis preservation).

    On AA failure: serve stale from in-process (within 24h grace), then
    from DB (no upper bound — old data is better than no data here).

    `catalog_ids` is the set of model ids we're willing to score —
    typically `set(CATALOG_BY_ID.keys())`. Pass it in (rather than
    importing) so tests can supply a synthetic catalog without dragging
    in litellm.
    """
    api_key, _origin = await resolve_aa_api_key(db, workspace_id)
    if not api_key:
        return _apply_static_baseline(QualityIndex(
            scores={}, fetched_at=0.0, source="missing-key",
            raw_count=0, matched_count=0,
        ), catalog_ids)

    url = aa_models_url()
    key_hash = _api_key_hash(api_key)
    now = time.monotonic()

    # Layer 1: in-process cache.
    if not force_refresh:
        cached = _cache.get(key_hash)
        if cached is not None and (now - cached.fetched_at) < _CACHE_TTL_SECONDS:
            return cached

    # Layer 2: DB snapshot (only if db session provided). Freshness is
    # checked via wall-clock age (computed in `_load_db_snapshot` from
    # the DB's `updated_at`), not monotonic — see `_LoadedSnapshot`.
    db_snapshot: _LoadedSnapshot | None = None
    if db is not None:
        db_snapshot = await _load_db_snapshot(db, workspace_id, key_hash)
        if (
            not force_refresh
            and db_snapshot is not None
            and db_snapshot.wall_age_seconds < _CACHE_TTL_SECONDS
        ):
            # Promote DB row into in-process cache. The in-process layer
            # uses monotonic time, so set `fetched_at = now` (treats this
            # request as the start of a fresh in-process TTL window).
            promoted = QualityIndex(
                scores=db_snapshot.quality_scores,
                fetched_at=now,
                source=db_snapshot.source,
                raw_count=db_snapshot.raw_count,
                matched_count=len(
                    set(db_snapshot.quality_scores)
                    | set(db_snapshot.tps_scores)
                    | set(db_snapshot.ttft_scores)
                ),
                tps_scores=db_snapshot.tps_scores,
                ttft_scores=db_snapshot.ttft_scores,
                matched_count_quality=db_snapshot.matched_count_quality,
                matched_count_tps=db_snapshot.matched_count_tps,
                matched_count_ttft=db_snapshot.matched_count_ttft,
            )
            promoted = _apply_static_baseline(promoted, catalog_ids)
            _cache[key_hash] = promoted
            return promoted

    # Layer 3: fetch AA.
    try:
        _last_fetch_meta.clear()
        raw = await _fetch_remote(url, api_key)
        if not raw:
            # Empty array from AA — almost always a transient outage or
            # a quota-exceeded response that still returned 200. Don't
            # let it overwrite a good DB snapshot with `{}`; route through
            # the stale-fallback path instead.
            raise _AAFetchUnusable("AA returned empty data array")
        metrics = _build_metrics_map(raw, catalog_ids)
        fresh_counts = (
            metrics.raw_count,
            len(set(metrics.quality_scores) | set(metrics.tps_scores) | set(metrics.ttft_scores)),
        )
        # Treat as unusable only if ALL THREE axes are empty AND we have
        # no preservable old snapshot. Per-axis preservation in the
        # saver covers the case where one axis regressed.
        any_axis = (
            metrics.matched_count_quality
            or metrics.matched_count_tps
            or metrics.matched_count_ttft
        )
        if not any_axis:
            raise _AAFetchUnusable(
                f"AA returned {metrics.raw_count} entries but 0 mapped "
                f"to catalog on any axis"
            )
        if db is not None:
            metrics = await _persist_with_axis_preservation(
                db, workspace_id, key_hash, "live", metrics,
            )
        union = len(
            set(metrics.quality_scores)
            | set(metrics.tps_scores)
            | set(metrics.ttft_scores)
        )
        idx = QualityIndex(
            scores=metrics.quality_scores,
            fetched_at=now,
            source="live",
            raw_count=metrics.raw_count,
            matched_count=union,
            tps_scores=metrics.tps_scores,
            ttft_scores=metrics.ttft_scores,
            matched_count_quality=metrics.matched_count_quality,
            matched_count_tps=metrics.matched_count_tps,
            matched_count_ttft=metrics.matched_count_ttft,
        )
        idx = _apply_static_baseline(idx, catalog_ids)
        _cache[key_hash] = idx
        await _record_aa_success(
            db, workspace_id, counts=fresh_counts, tier=_last_fetch_meta.get("tier"),
        )
        return idx
    except Exception as exc:
        # Persist the failure reason so the Quality page can distinguish
        # "invalid key" from "rate limited" from "connection failed".
        await _record_aa_error(db, workspace_id, exc)
        # Stale fallbacks, in order of freshness.
        cached = _cache.get(key_hash)
        if cached is not None and (now - cached.fetched_at) < _STALE_GRACE_SECONDS:
            return dataclasses.replace(cached, source="stale-cache")  # baseline already applied at cache-write
        if db_snapshot is not None:
            # DB row is older than the in-process TTL but we serve it
            # anyway — better than disabling quality routing entirely.
            # `source="stale-db"` lets the dashboard show the operator
            # they're on stale data; no upper bound on age here because
            # the alternative (cost-based) is known wrong, not just stale.
            return _apply_static_baseline(QualityIndex(
                scores=db_snapshot.quality_scores,
                fetched_at=now,  # we just learned this from DB; re-anchor in-process
                source="stale-db",
                raw_count=db_snapshot.raw_count,
                matched_count=len(
                    set(db_snapshot.quality_scores)
                    | set(db_snapshot.tps_scores)
                    | set(db_snapshot.ttft_scores)
                ),
                tps_scores=db_snapshot.tps_scores,
                ttft_scores=db_snapshot.ttft_scores,
                matched_count_quality=db_snapshot.matched_count_quality,
                matched_count_tps=db_snapshot.matched_count_tps,
                matched_count_ttft=db_snapshot.matched_count_ttft,
            ), catalog_ids)
        return _apply_static_baseline(QualityIndex(
            scores={}, fetched_at=now, source="error",
            raw_count=0, matched_count=0,
        ), catalog_ids)


# Stable, machine-readable failure codes shared by the connection test and the
# benchmark sync. Details are short English sentences that never contain key
# material or an upstream response body.
AA_ERROR_CODES = (
    "invalid_key",            # 401: missing / invalid / revoked key
    "insufficient_tier",      # 403: the key's subscription doesn't cover it
    "endpoint_retired",       # 410: a retired endpoint was called
    "rate_limited",           # 429: daily quota exhausted
    "timeout",                # request timed out
    "malformed_response",     # 200 but the body isn't the documented schema
    "no_data",                # 200 with an empty model list
    "no_catalog_match",       # data returned, nothing matched GeekCubo's catalog
    "server_error",           # 5xx from AA
    "connection_failed",      # DNS / TLS / connection errors, other HTTP codes
)


def _classify_fetch_error(exc: Exception) -> tuple[str, str]:
    """Map a fetch exception to (code, human_detail)."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code == 401:
            return "invalid_key", (
                "Artificial Analysis rejected the API key (HTTP 401). Check that "
                "the key is current; regenerating a key revokes the old one."
            )
        if code == 403:
            return "insufficient_tier", (
                "This key's Artificial Analysis plan does not include the "
                "requested endpoint (HTTP 403)."
            )
        if code == 410:
            return "endpoint_retired", (
                "The Artificial Analysis endpoint has been retired (HTTP 410). "
                "Update GeekCubo or remove a custom ARTIFICIAL_ANALYSIS_MODELS_URL."
            )
        if code == 429:
            retry = None
            try:
                retry = int(exc.response.headers.get("retry-after", ""))
            except (TypeError, ValueError, AttributeError):
                retry = None
            when = f" Quota resets in about {max(1, round(retry / 60))} min." if retry else ""
            return "rate_limited", (
                "Artificial Analysis daily request limit reached (HTTP 429)." + when
            )
        if code >= 500:
            return "server_error", f"Artificial Analysis returned a server error (HTTP {code})."
        return "connection_failed", f"Artificial Analysis returned HTTP {code}."
    if isinstance(exc, httpx.TimeoutException):
        return "timeout", "Timed out contacting Artificial Analysis."
    if isinstance(exc, httpx.TransportError):
        return "connection_failed", "Could not reach Artificial Analysis (network error)."
    if isinstance(exc, _AAFetchUnusable):
        msg = str(exc) or ""
        if "empty" in msg:
            return "no_data", "Artificial Analysis returned no models."
        if "0 mapped" in msg:
            return "no_catalog_match", (
                "Artificial Analysis returned models, but none matched GeekCubo's "
                "model catalog."
            )
        return "malformed_response", (
            "Artificial Analysis returned data in an unexpected format."
        )
    return "connection_failed", "Unexpected error contacting Artificial Analysis."


async def _record_aa_success(
    db: "AsyncSession | None",
    workspace_id: str,
    counts: tuple[int, int] | None = None,
    tier: str | None = None,
) -> None:
    """Mark the last fetch as successful, clearing any prior error.

    Best-effort: a write failure here must not disturb the request path.
    """
    if db is None:
        return
    try:
        from sqlalchemy import select

        from packages.db.models.quality_settings import QualitySettings

        row = (
            await db.execute(
                select(QualitySettings).where(
                    QualitySettings.workspace_id == workspace_id
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            now = datetime.now(timezone.utc)
            row.last_status = "live"
            row.last_sync_at = now
            row.last_sync_attempt_at = now
            row.last_error_code = None
            row.last_error_detail = None
            row.last_error_at = None
            if counts is not None:
                row.last_sync_raw_count = counts[0]
                row.last_sync_matched_count = counts[1]
            if tier:
                row.last_tier = tier
            await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass


async def _record_aa_error(
    db: "AsyncSession | None",
    workspace_id: str,
    exc: Exception,
) -> None:
    """Persist the latest fetch failure to quality_settings, best-effort.

    Clears on success instead; this only records the failure reason so the
    Quality page can show "Invalid key" / "Rate limited" / "Connection failed"
    separately from the last successful sync time. Never raises: a write failure
    must not disturb the request path.
    """
    if db is None:
        return
    code, detail = _classify_fetch_error(exc)
    try:
        from sqlalchemy import select

        from packages.db.models.quality_settings import QualitySettings

        row = (
            await db.execute(
                select(QualitySettings).where(
                    QualitySettings.workspace_id == workspace_id
                )
            )
        ).scalar_one_or_none()
        if row is not None:
            now = datetime.now(timezone.utc)
            row.last_status = "error"
            row.last_sync_attempt_at = now
            row.last_error_code = code
            row.last_error_detail = detail
            row.last_error_at = now
            await db.commit()
    except Exception:
        try:
            await db.rollback()
        except Exception:
            pass


def reset_cache() -> None:
    """Clear the in-process cache. Call from test fixtures."""
    _cache.clear()
