"""`python -m geekcubo_knowledge build|check|search` — index maintenance.

    python -m geekcubo_knowledge build            # rebuild the bundled index
    python -m geekcubo_knowledge check            # exit 1 if stale or unreadable
    python -m geekcubo_knowledge search "searxng"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from geekcubo_knowledge.index import build_index, read_sources
from geekcubo_knowledge.service import KnowledgeService, KnowledgeUnavailable, default_index_path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m geekcubo_knowledge")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--root", type=Path, default=ROOT)
    b.add_argument("--out", type=Path, default=None)
    sub.add_parser("check")
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=5)
    args = p.parse_args(argv)

    if args.cmd == "build":
        out = args.out or default_index_path()
        meta = build_index(args.root, out)
        print(f"built {out} ({out.stat().st_size} bytes): {meta['document_count']} documents, "
              f"{meta['section_count']} sections, version {meta['app_version']}")
        return 0
    if args.cmd == "check":
        svc = KnowledgeService.open_default()
        try:
            v = svc.version()
        except KnowledgeUnavailable as err:
            print(f"unavailable: {err}", file=sys.stderr)
            return 1
        digest = hashlib.sha256()
        for rel, _title, text in read_sources(ROOT):
            digest.update(rel.encode() + b"\0" + text.encode("utf-8") + b"\0")
        if digest.hexdigest() != v["docs_sha256"]:
            print("stale: the documentation changed since the index was built", file=sys.stderr)
            return 1
        print(json.dumps(v))
        return 0
    if args.cmd == "search":
        for hit in KnowledgeService.open_default().search(args.query, args.limit):
            print(f"{hit.score:8.3f}  {hit.id}\n          {hit.reference}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
