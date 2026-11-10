"""GeekCubo Knowledge: local, read-only search over GeekCubo's public docs.

One index and one retrieval service, shared by Ask GeekCubo in native Chat
and by the `geekcubo-mcp` stdio server.
"""

__version__ = "0.1.0"

from geekcubo_knowledge.service import (
    DocNotFound,
    KnowledgeService,
    KnowledgeUnavailable,
    SearchHit,
    get_service,
)

__all__ = ["DocNotFound", "KnowledgeService", "KnowledgeUnavailable", "SearchHit", "get_service"]
