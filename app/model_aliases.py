"""Short model aliases: `gpt-6-astra` instead of `apixo/gpt-6-astra`.

Rules, in order of importance:

* **Never guess.** An alias resolves only when exactly one deployable model
  matches its bare id. Two providers exposing the same bare id is the normal
  case for aggregators, so ambiguity is expected, not exceptional.
* **Canonical ids win.** A bare id that is itself a real catalog id is never
  treated as an alias for something else; namespaced ids are never rewritten.
* **Actionable rejection.** An ambiguous alias returns 409 naming both
  candidates, so the caller can pin one instead of retrying blindly.
* **Deployability decides.** Only models with a live deployment count, so an
  alias cannot resolve to a catalog entry for a provider with no key.
"""

from __future__ import annotations


class AliasError(Exception):
    def __init__(self, message: str, *, status_code: int = 409):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def alias_candidates(requested: str, deployable: set[str]) -> list[str]:
    """Deployable names whose bare id equals `requested`."""
    if not requested or "/" in requested:
        return []
    return sorted(n for n in deployable if n.rsplit("/", 1)[-1] == requested)


def needs_resolution(requested: str, deployable: set[str]) -> bool:
    """Whether resolving `requested` can possibly change it.

    Cheap guard so the caller skips the catalog query entirely for the
    overwhelmingly common cases (canonical id, `auto`, or a name with no
    alias match at all).
    """
    return bool(alias_candidates(requested, deployable))


def resolve_alias(
    requested: str,
    *,
    deployable: set[str],
    known_ids: set[str],
) -> str:
    """Resolve `requested` to a canonical deployment name.

    Returns `requested` unchanged when it is already canonical, unknown, or
    has no alias match (the caller's existing "model not found" path). Raises
    `AliasError` only when the alias is genuinely ambiguous.
    """
    if not requested or "/" in requested:
        return requested
    if requested in deployable:
        # Bare id that is itself deployable (built-in providers register bare
        # names). Nothing to resolve.
        return requested
    if requested in known_ids:
        # A real catalog id that simply has no deployment: leave it alone so
        # the existing "provider not configured" error still explains itself.
        return requested

    matches = sorted(
        name for name in deployable
        if name.rsplit("/", 1)[-1] == requested
    )
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise AliasError(
            f"Model '{requested}' is ambiguous: it matches "
            + ", ".join(matches)
            + ". Use the full namespaced id."
        )
    return requested
