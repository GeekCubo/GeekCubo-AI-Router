# Model Intelligence

[← Back to the README](../README.md)

Catalog metadata sources, exact-first matching, confirmed versus reference prices, tri-state capabilities and provider-table administration.

**Settings → Model data** configures where catalog metadata comes from. Three
sources ship built in: LiteLLM's bundled catalog (offline, no network),
[Models.dev](https://models.dev/api.json), and Portkey's per-provider pricing.
Add your own models.dev-compatible HTTPS endpoint if you have an internal
catalog.

Matching is exact-first and never guesses. GeekCubo tries, in order: an exact
`<provider-slug>/<model>` key, the operator-chosen catalog key, an exact
model id that already carries a vendor prefix, and a uniquely matching bare
model id. Prefixes such as `apixo/` are not blindly stripped to manufacture a
match, and no fuzzy or "looks similar" matching is used.

Each discovered or registered model shows one identity status:

| Status | Meaning |
|---|---|
| **Resolved** | Exactly one catalog entry matched, with context, reference prices and tool support known. |
| **Partial** | One entry matched, but at least one of those fields is missing; missing fields stay Unknown. |
| **Ambiguous** | Several catalog entries use the same id (often resellers). Nothing is inherited until you pick the right catalog key. The picker lists the model vendor's own entry first and accepts any exact key you type. |
| **Unmatched** | No catalog entry uses the id, typically a custom, renamed, *abliterated* or *uncensored* variant. Such models never inherit the metadata of a similarly named model. |

Large reseller catalogs make **Ambiguous** common for popular model ids; that
is expected and safe. The counts in **Manage models** and in the discovery list
are filter buttons.

When the provider's own `GET /models` reports `context_window` or
`max_output_tokens` (not part of the OpenAI schema, but some providers include
them), GeekCubo stores those values for that provider's models and shows them
as `via provider_models_endpoint`. They are refreshed whenever you run **Fetch
available models** and never imply capabilities or prices.

## Confirmed custom price vs reference estimate

There are two independent prices for a custom-provider model:

- **Custom price** — the confirmed rate you configured for that provider. It is
  the only rate used for spend accounting, budgets and analytics.
- **Reference price** — a vendor catalog rate shown for comparison. It is
  always labelled as an estimate and never becomes confirmed billing.

Strict pricing is the default. Auto, the **Cheapest** strategy and every
routing-profile cost ceiling compare only confirmed prices: built-in provider
list prices and the custom price you set. A custom model that has only a
reference estimate is reported as `estimate_only` and is not chosen by Auto
until you confirm its price. An unknown price never satisfies a ceiling.

If you prefer to route on estimates, enable it explicitly in the routing
policy:

```json
{ "pricing": { "allow_reference_estimates": true } }
```

With that flag on, reference estimates take part in Auto ranking and cost
ceilings, the routing dry-run reports `pricing_mode: estimate_allowed`, and
each decision that relied on an estimate carries an `estimate-based pricing`
note. Spend accounting still uses only confirmed prices.

`provider_catalog` trust is assigned only when the matched key begins with the
custom provider's own slug (for example `apixo/gpt-4o`). A match against
`openai/gpt-4o` remains a `reference_estimate`. An unknown price is never
treated as zero or free.

Reference precedence, highest first:

1. a reference price you set explicitly on the model,
2. a trusted provider catalog match,
3. another public catalog price (recorded as an estimate),
4. cached catalog data (flagged stale),
5. unknown.

Units are converted per source. Portkey publishes **cents per token**;
`0.00025` becomes **$2.50 / 1M**, and its zero-filled `default` template is
ignored.

## Capabilities and Auto

Metadata is resolved automatically when you **Fetch → Select → Add Selected
Models**. You don't need to open Details first. Tools, Vision, JSON mode,
JSON Schema, context window and reference prices are resolved **field by
field**, each independently. Each
field takes the first enabled source, in priority order, that has an explicit
value for the matched model. A missing price never blocks capabilities: a
model can show Tools and Vision as Supported and JSON Schema as Unsupported while its
price stays Unknown.

JSON mode (OpenAI's `json_object` response format) and JSON Schema (OpenAI's
`json_schema` structured outputs) are two separate capabilities, resolved
independently. Structured-output evidence in the catalog — for example
LiteLLM's `supports_response_schema` — maps only to JSON Schema and is never
treated as evidence of JSON mode.

Each capability has one of three states, **Supported**, **Unsupported** or
**Unknown**, and its source (for example `litellm`, `models-dev` or
`administrator_override`) appears next to it in the model table. A
capability is Supported or Unsupported only when a reliably matched catalog
entry gives an explicit value. Without that evidence it stays Unknown. An
ambiguous model (a bare id listed under several vendors) gets no capabilities,
context or prices until you pick its catalog key from the searchable
candidate list. GeekCubo never borrows another model's metadata.

The context window follows its own precedence: a value you set on the model,
then the limit the provider's `GET /models` reported, then the matched catalog
entry, otherwise Unknown. An unknown window never excludes a model from Auto;
a known window that is too small does.

Any explicit administrator choice is an override and survives catalog
refreshes. That includes choosing **Unknown**. Choose **Use catalog** to drop
the override and return to the resolved value. **Resolve metadata** in the
bulk toolbar re-resolves existing models, and refreshing a Model data source
re-resolves every registered model. Both update catalog-derived values and
leave overrides alone.

Auto routing, Chat and routing profiles all read the same stored
capabilities. A model is chosen for a request that needs a capability only
when that capability is Supported. Unknown is never promoted to Supported,
and GeekCubo does not mark capabilities Supported just so Auto has a
candidate. Neither an unknown price nor a reference estimate meets a price
ceiling unless estimate-based pricing is explicitly enabled.

## Provider-table administration

Inside a custom provider's **Manage models** panel, each row shows the
identity status and matched catalog key, the context window (and the
provider-reported maximum output, when known), reference and confirmed prices,
tri-state capabilities with their source, and an independent Enabled switch.
Disabled models stay registered but are not deployed, listed or Auto-selected.

Selections are independent from discovery and survive table re-renders. The
header checkbox selects the current filtered result set (with an indeterminate
state), and the bulk toolbar can enable, disable, remove or set a capability
across the selected rows. Removal is provider-scoped and asks for confirmation;
it is never performed while a capability save is in flight.

Every request stores immutable cost provenance (`custom`, `upstream_litellm`,
`catalog_estimate` or `unknown`) plus the pricing snapshot used at that moment.
Later catalog refreshes and model edits do not rewrite historical estimates.

Fetching is SSRF-hardened: https only (with an explicit local allowlist
exception), no embedded credentials, DNS resolved once and pinned to the
connection with the hostname preserved for TLS, every redirect re-validated,
32 MB and 20 s caps, and a source's own token is only ever sent to that
source's host. GeekCubo never sends provider keys or prompts to a catalog.

With every source offline, all configured models keep serving.
