# GeekCubo Knowledge: Ask GeekCubo and the documentation MCP server

[← Back to the README](../README.md)

GeekCubo Knowledge answers questions about GeekCubo itself — installation,
configuration, routing, API keys, providers, Chat, web search, Local AI
Connect, integrations and troubleshooting — from GeekCubo's own documentation.

It has two front ends on one shared index:

| | Ask GeekCubo | GeekCubo MCP |
|---|---|---|
| Where | The **Chat** tab of your GeekCubo dashboard | Any MCP client on your own machine, such as OpenCode |
| Runs | Inside your GeekCubo server | `geekcubo-mcp serve`, a local process started by the client (stdio) |
| Answers with | The model you pick in Chat (Auto, a profile, any provider or a Local AI model) | Your client's own model |
| Needs | Nothing extra; on by default | `uv tool install` or `pip install` (below); no GeekCubo server, no network, no keys |

No model is trained or fine-tuned, nothing is downloaded at run time, and no
external search service, vector database or hosting is involved.

GeekCubo Knowledge is **not** web search. Web search looks things up on the public internet; GeekCubo Knowledge only searches the
GeekCubo documentation bundled with the installed release.

## How it works

1. **A prebuilt index.** The documents listed in
   `geekcubo_knowledge/sources.py` — this README, the deployment, contributing
   and security guides, and the guides in `docs/` — are split into Markdown
   sections (a heading and its text, with code examples kept next to the text
   that explains them) and stored in a small SQLite FTS5 file,
   `geekcubo_knowledge/data/knowledge.sqlite3` (about 300 KB). The file ships
   inside the Docker image and the Python package, so it is there after a fresh
   install, a restart, a rebuild or an upgrade, with or without internet.
2. **Search.** A question is turned into keywords and ranked with BM25,
   weighted by how much of the question each section covers (rare, specific
   words count more than common ones). Exact identifiers
   — `API_KEY_PEPPER`, `/v1/chat/completions`, `x-geek-routing-diagnosis` —
   match as written. Sections that share only an incidental word with the
   question are dropped, so an unrelated question returns nothing rather than
   a misleading match.
3. **Bounded context.** Ask GeekCubo adds at most five sections (about
   9 000 characters) to the request, never the whole documentation.

Only allowlisted documents are indexed. `.env` files, databases, logs,
conversations, attachments, credentials, Git history and private notes are
never read, whatever files exist in the directory.

## Ask GeekCubo in Chat

Open **Chat** and choose **Ask GeekCubo** above the message box. The box
shows *Answers grounded in GeekCubo documentation* (hover it for the
documentation version); ask as usual,
for example how a routing strategy behaves or how to set up a feature.

The answer comes from the model selected in the header, with the relevant
documentation sections attached to the request. Below the answer, **Sources**
lists exactly the sections that were retrieved for it — for example
*Chat → Web search (optional, off by default)* — together with each section's
stable id (`docs/chat.md#web-search-optional-off-by-default`). When nothing in
the documentation matches, the answer says that the installed documentation
does not cover the question, and no sources are shown.

How the mode behaves:

- **Per message.** Each question records the mode it was asked in, and the
  conversation history shows an *Ask GeekCubo* label on those questions.
  Normal Chat messages never receive documentation, before or after.
- **New conversations start in Normal Chat.** Reopening a conversation
  restores the mode of its most recent question, so a conversation that
  never used Ask GeekCubo always reopens in Normal Chat. Switching modes
  never sends, deletes or changes anything already in the conversation.
- **Follow-ups.** A short follow-up such as *and how do I disable it?* also
  searches with the previous Ask GeekCubo question. Normal Chat messages are
  never used for retrieval.
- **Regenerate** reruns an answer in the mode its question was asked in.
- **Everything else is unchanged:** model choice, Auto routing, system prompt,
  attachments, history and web search work as in Normal Chat. The
  answering instructions are separate from your own system prompt. Retrieved
  document text is delimited user-role reference material and never receives
  system-level authority.

The model is told to prefer the documentation, say when it does not cover
something, not invent settings or endpoints, and not claim to have inspected
your installation (it cannot see your settings). How well it follows that
depends on the model.

### Turning it off

Set `KNOWLEDGE_ENABLED=false` in `.env` and restart. The Ask GeekCubo switch
disappears; Normal Chat, routing, the API and every integration are
unaffected. If the index file is missing or unreadable, the switch is shown
disabled, and an Ask GeekCubo request fails with a clear message instead of
silently answering without documentation.

## GeekCubo MCP for OpenCode and other MCP clients

`geekcubo-mcp` is a read-only [Model Context Protocol](https://modelcontextprotocol.io/)
server that runs on your own computer over stdio. It gives an AI coding tool
three tools:

| Tool | Does |
|---|---|
| `search_geekcubo_docs` | Searches the documentation. Input: `query`, optional `limit` (1–10, default 5). Returns ids, titles, headings, excerpts, a citation `reference` and the documentation version. |
| `read_geekcubo_doc` | Reads one section by `id` from the search results (for example `docs/routing.md#strategies`), or a whole document by its path (`docs/chat.md`). |
| `get_geekcubo_version` | Reports which GeekCubo release the bundled documentation describes. It does not know the version of any running server. |

This is a different connection from using GeekCubo as a model provider. The
[OpenCode provider setup](integrations.md#opencode) sends your prompts to your
GeekCubo server with an `sk-geek-*` key; the MCP server only reads
documentation on your machine and needs no key, no server and no network. You
can use either one, or both.

### Install

The MCP server ships in the `geekcubo` Python package with the `mcp` extra.
With [uv](https://docs.astral.sh/uv/) (Python 3.11 or newer):

```bash
uv tool install "geekcubo[mcp] @ git+https://github.com/GeekCubo/GeekCubo-AI-Router"
geekcubo-mcp version
```

or with pip in a virtual environment:

```bash
python -m venv ~/.geekcubo-mcp
~/.geekcubo-mcp/bin/pip install "geekcubo[mcp] @ git+https://github.com/GeekCubo/GeekCubo-AI-Router"
~/.geekcubo-mcp/bin/geekcubo-mcp version
```

No Docker and no GeekCubo server are needed. `geekcubo-mcp search "<words>"`
checks the documentation from a terminal. To update the documentation, reinstall
the package (`uv tool install --reinstall …`).

### Adding the MCP server to OpenCode

Add the server to `opencode.json(c)` in a project, or to
`~/.config/opencode/opencode.jsonc` to use it everywhere. This is the OpenCode
2.x format (servers under `mcp.servers`):

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "geekcubo-knowledge": {
        "type": "local",
        "command": ["geekcubo-mcp", "serve"]
      }
    }
  }
}
```

If `geekcubo-mcp` is not on the `PATH` OpenCode starts from, use the full
path, for example `["/home/you/.local/bin/geekcubo-mcp", "serve"]`. Check the
connection:

```bash
opencode mcp list
# ✓ geekcubo-knowledge  connected
```

Then ask OpenCode a GeekCubo question; it searches, reads the relevant section
and cites it. This configuration was tested with OpenCode 2.2.6: the server
connected, the three tools were discovered, and five reference questions about
setup, routing, web search, keys and upgrades were answered from the right
sections with citations. The MCP server adds tools only; it does not change OpenCode's model
or its other tools.

### Other MCP clients

Any client that launches stdio MCP servers can run `geekcubo-mcp serve` the
same way. Only OpenCode has been tested; check your client's documentation for
its configuration format.

## Keeping the documentation current

The index belongs to the release it ships in. After editing any indexed
document, rebuild and commit it:

```bash
python -m geekcubo_knowledge build    # writes geekcubo_knowledge/data/knowledge.sqlite3
python -m geekcubo_knowledge check    # exits 1 if the index is stale or unreadable
```

CI runs `check`, so a pull request that changes the documentation without
rebuilding the index fails. To index a new public document, add it to
`geekcubo_knowledge/sources.py`; nothing is indexed implicitly.

## Security boundaries

- **Read-only.** Neither interface runs commands, changes settings, reads or
  rotates API keys, or touches conversations, the database or attachments.
- **No arbitrary files.** Tools address documentation only by section id or
  by a path on the allowlist. Anything else (`../.env`, `/etc/passwd`, an
  unindexed file) is rejected. The index is opened read-only.
- **Untrusted text stays text.** Retrieved sections are clearly delimited,
  sent as user-role reference material separately from trusted system
  instructions, and labelled as unable to change instructions.
  Search queries are treated as keywords: search syntax and instructions in
  them have no effect.
- **No exposed endpoint.** The MCP server only talks over stdio to the client
  that started it. There is no hosted or network MCP endpoint.
- **Ask GeekCubo is administrator-only,** like the rest of Chat.

## Limitations

- Answers are only as complete as the documentation. Something that is not
  documented cannot be confirmed.
- Search is keyword-based, not semantic: a question phrased very differently
  from the documentation may miss a relevant section. Rephrasing with the
  feature's name usually helps.
- The model writes the final answer and can still make mistakes. The sources
  list shows exactly what it was given.
- The MCP server describes the release it was installed from, not necessarily
  the version your GeekCubo server runs.
- Translated READMEs are not indexed; questions in other languages work best
  when they include the English feature names.
