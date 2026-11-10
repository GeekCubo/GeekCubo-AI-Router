"""The explicit allowlist of public documentation that GeekCubo Knowledge indexes.

Only these paths (relative to the repository root) are ever read. Nothing is
discovered by globbing, so a new file — public or private — is never indexed
merely because it exists. Add a document here deliberately.

Each entry maps the repository path to a short human title used in source
references ("Routing → Strategies").
"""

from __future__ import annotations

DOC_SOURCES: tuple[tuple[str, str], ...] = (
    ("README.md", "README"),
    ("DEPLOYMENT.md", "Deployment guide"),
    ("CONTRIBUTING.md", "Contributing guide"),
    ("SECURITY.md", "Security policy"),
    ("docs/README.md", "Documentation index"),
    ("docs/security.md", "Security and API keys"),
    ("docs/routing.md", "Routing"),
    ("docs/model-intelligence.md", "Model Intelligence"),
    ("docs/integrations.md", "Connecting tools and SDKs"),
    ("docs/local-ai-connect.md", "Local AI Connect"),
    ("docs/chat.md", "Chat"),
    ("docs/api.md", "API endpoints"),
    ("docs/architecture.md", "Architecture"),
    ("docs/geekcubo-knowledge.md", "GeekCubo Knowledge"),
    ("integrations/README.md", "Example integration configs"),
)

ALLOWED_PATHS: frozenset[str] = frozenset(p for p, _ in DOC_SOURCES)
TITLES: dict[str, str] = dict(DOC_SOURCES)
