"""`geekcubo-mcp` — a read-only MCP server over GeekCubo's bundled documentation.

Runs locally over stdio (launched by the MCP client, e.g. OpenCode). It needs
no GeekCubo installation, no network, no credentials, and opens nothing but
the bundled index file. It has exactly three tools, all read-only:

    search_geekcubo_docs   full-text search over the documentation
    read_geekcubo_doc      read a section or document by its id
    get_geekcubo_version   which documentation release is bundled

This is separate from using GeekCubo as an inference endpoint: that is an
OpenAI-compatible provider in your client's config; this is documentation.
"""

from __future__ import annotations

import argparse
import sys
from typing import Annotated

from pydantic import Field

from geekcubo_knowledge import __version__
from geekcubo_knowledge.service import (
    DEFAULT_RESULTS,
    MAX_QUERY_CHARS,
    MAX_RESULTS,
    DocNotFound,
    KnowledgeUnavailable,
    get_service,
)

SERVER_INSTRUCTIONS = (
    "GeekCubo is a self-hosted, OpenAI-compatible AI router. These tools search and read the "
    "GeekCubo documentation bundled with this package (a specific GeekCubo release). Use "
    "search_geekcubo_docs first, then read_geekcubo_doc with an id from the results when you need "
    "the full section. Answer from the returned text and cite the 'reference' or 'id'. If the "
    "documentation does not cover something, say so; do not invent settings, endpoints or "
    "commands. These tools cannot see or change any user's GeekCubo installation."
)


def build_server():
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.exceptions import ToolError
    from mcp_types import ToolAnnotations

    server = MCPServer(
        name="geekcubo-knowledge",
        title="GeekCubo Knowledge",
        instructions=SERVER_INSTRUCTIONS,
        version=__version__,
    )
    read_only = ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False
    )

    @server.tool(
        name="search_geekcubo_docs",
        title="Search GeekCubo documentation",
        description=(
            "Full-text search of the official GeekCubo documentation (installation, configuration, "
            "routing strategies, API keys, providers, Chat, web search, Local AI Connect, "
            "integrations such as OpenCode, API endpoints, troubleshooting). Returns the best "
            "matching sections, each with an 'id' for read_geekcubo_doc, a document title, section "
            "heading, a short excerpt and a citation 'reference'. Exact identifiers such as "
            "environment variables (API_KEY_PEPPER), endpoints (/v1/chat/completions) or headers "
            "(x-geek-routing-diagnosis) match as written. Read-only; does not access any GeekCubo "
            "installation."
        ),
        annotations=read_only,
    )
    def search_geekcubo_docs(
        query: Annotated[str, Field(
            min_length=1, max_length=MAX_QUERY_CHARS,
            description="What to look for, in plain words or exact identifiers.",
        )],
        limit: Annotated[int, Field(
            ge=1, le=MAX_RESULTS, description=f"Maximum results (default {DEFAULT_RESULTS}).",
        )] = DEFAULT_RESULTS,
    ) -> dict:
        svc = get_service()
        try:
            hits = svc.search(query, limit)
            version = svc.version()["docs_version"]
        except (KnowledgeUnavailable, ValueError) as err:
            raise ToolError(str(err)) from err
        return {
            "docs_version": version,
            "query": query,
            "results": [h.to_dict() for h in hits],
            "note": (
                "No matching documentation. The bundled docs do not cover this; say so rather than guessing."
                if not hits else None
            ),
        }

    @server.tool(
        name="read_geekcubo_doc",
        title="Read a GeekCubo documentation section",
        description=(
            "Read the full text of one GeekCubo documentation section, identified by an 'id' "
            "returned by search_geekcubo_docs (for example 'docs/routing.md#strategies'), or a whole "
            "document by its path (for example 'docs/chat.md'). Only indexed GeekCubo documents can "
            "be read; arbitrary files cannot. Long documents are truncated."
        ),
        annotations=read_only,
    )
    def read_geekcubo_doc(
        id: Annotated[str, Field(
            min_length=1, max_length=300,
            description="Section id from search results, or an indexed document path.",
        )],
    ) -> dict:
        try:
            return get_service().read(id)
        except DocNotFound as err:
            raise ToolError(f"{err} Use search_geekcubo_docs to find valid ids.") from err
        except KnowledgeUnavailable as err:
            raise ToolError(str(err)) from err

    @server.tool(
        name="get_geekcubo_version",
        title="GeekCubo documentation version",
        description=(
            "Report which GeekCubo release the bundled documentation describes and how many "
            "documents and sections it contains. This is the version of the documentation package, "
            "not of any running GeekCubo server, which these tools cannot see."
        ),
        annotations=read_only,
    )
    def get_geekcubo_version() -> dict:
        svc = get_service()
        try:
            v = svc.version()
        except KnowledgeUnavailable as err:
            raise ToolError(str(err)) from err
        return {
            **v,
            "package_version": __version__,
            "documents": svc.documents(),
            "describes": "the GeekCubo release this package was built from; not a live installation",
        }

    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="geekcubo-mcp",
        description="Read-only MCP server for the GeekCubo documentation (stdio).",
    )
    parser.add_argument("--version", action="version", version=f"geekcubo-mcp {__version__}")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("serve", help="Run the MCP server on stdin/stdout (what MCP clients launch).")
    s = sub.add_parser("search", help="Search the bundled docs from the terminal (for checking).")
    s.add_argument("query")
    sub.add_parser("version", help="Print the bundled documentation version.")
    args = parser.parse_args(argv)

    if args.cmd == "serve":
        try:
            import mcp  # noqa: F401
        except ImportError:
            print("geekcubo-mcp needs the 'mcp' package: pip install 'geekcubo[mcp]'", file=sys.stderr)
            return 1
        # stdout carries the protocol; never print to it here.
        build_server().run("stdio")
        return 0
    svc = get_service()
    try:
        if args.cmd == "search":
            for h in svc.search(args.query, 5):
                print(f"{h.id}\n    {h.reference}")
            return 0
        if args.cmd == "version":
            v = svc.version()
            print(f"GeekCubo documentation {v['docs_version']} "
                  f"({v['document_count']} documents, {v['section_count']} sections)")
            return 0
    except KnowledgeUnavailable as err:
        print(str(err), file=sys.stderr)
        return 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
