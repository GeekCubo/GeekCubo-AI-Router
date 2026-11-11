# Chat in the dashboard

[← Back to the README](../README.md)

The built-in **Chat** tab: streaming, context budget, optional web search and attachments.

The **Chat** tab talks to your deployed models from the browser. Requests go
through the same routing pipeline as SDK traffic, so `model="auto"`, profiles,
caching and cost tracking behave identically. The model menu offers **Auto
(router picks)**, your routing profiles and every deployable model; the choice
is saved per conversation.

The **Reasoning** selector next to the model picker sets the reasoning effort.
**Default** sends nothing. The levels listed are the selected model's
confirmed ones, *Support not confirmed* for an Unknown model, or what Auto's
pool can satisfy. The choice is saved per conversation and reused by
Regenerate, and each reply shows the level actually used. See
[Reasoning effort](reasoning.md#native-chat).

Replies stream as they are generated. **Stop** (the Send button while a reply
is streaming) ends the request upstream; the partial answer is kept and marked
as interrupted, and the request log records it as a client disconnect.

Conversations live in your local database only. History saving and retention
are configurable in **Settings → Chat**. With history off, messages are not
stored (the request log still records usage), and uploaded attachments are
deleted once they are a day old.

## Context budget

Before every request the server loads recent history and trims it to what the
selected model can actually accept. The trim is reported back to the browser in
response headers:

| Header | Meaning |
|---|---|
| `x-geek-context-tokens` | Estimated tokens sent for this turn |
| `x-geek-context-budget` | Token budget used for the model |
| `x-geek-context-omitted` | Older messages dropped to fit |
| `x-geek-context-source` | `model` when the window is known for the selected model, `fallback` (16 384 tokens) otherwise, for example under Auto before a model is chosen |

The chat header shows the same numbers ("Context: 1 204 / 128 000 tokens") and
notes when older messages were omitted, so a truncated answer is never mistaken
for a model failure. Token counts are estimates (about four characters per
token, plus a small per-message overhead) and the budget keeps a safety margin.

## Ask GeekCubo

Above the message box, **Normal Chat | Ask GeekCubo** chooses how the next
message is answered. *Ask GeekCubo* answers questions about GeekCubo itself
from the documentation bundled with this release and lists the sections it
used under **Sources**; *Normal Chat* never receives documentation. The mode
is recorded per message, and new conversations start in Normal Chat. This is
not web search: it only searches GeekCubo's own documentation. See
[GeekCubo Knowledge](geekcubo-knowledge.md).

## Web search (optional, off by default)

Chat can search the web before answering and cite the pages it used. Configure
it in **Settings → Chat → Web search**:

- **Mode** — `off` (default) or `manual`, which shows a per-message toggle in
  the composer. `auto` is reserved and not implemented; the option is disabled.
- **Backend** — `searxng` (your own or a private instance, URL required),
  `brave` or `tavily` (API key required, stored encrypted and never shown again).
- **Limits** — searches per conversation, results per search, pages fetched per
  search, and a timeout. Hard caps apply server-side.
- **Test connection** runs one real query and reports the result count and
  latency without saving anything.

A search that did not happen is never described as one that did: failures are
reported in the composer, and citations are rendered only for URLs the backend
actually returned. Search-provider keys are stored separately from inference
provider keys.

SearXNG can be run by the installer (Compose profile `search`):

```bash
docker compose --profile search up -d          # start it
docker compose --profile search down           # stop it
```

Then point the backend at `http://searxng:8080/`. Brave and Tavily need no
container — paste the API key in the dashboard.

## Attachments (images, documents, archives, media)

The composer accepts files three ways: the paperclip button, drag-and-drop
onto the conversation, and paste (a pasted image, including a screenshot with
no file name, becomes an attachment; pasted plain text stays native). Each file
appears as a chip with a preview where possible and a remove button; Send waits
until uploads finish. Files are identified by extension and verified by magic
bytes, stored under an opaque UUID name, served back only to the signed-in
administrator, and never executed.

| Kind | Formats | How the model sees it |
|---|---|---|
| `image` | PNG, JPEG, WebP, GIF, BMP, TIFF | Converted to JPEG and sent as image parts to a vision-capable model |
| `document` | PDF, DOCX, RTF | Extracted text, delimited |
| `spreadsheet` | XLSX, XLS, ODS, CSV, TSV | Sheet-by-sheet text, bounded |
| `text` / `code` | TXT, MD, JSON, YAML, source files | Raw text, delimited |
| `archive` | ZIP, TAR, GZIP | Entry listing plus bounded reads; never unpacked to disk |
| `video` / `audio` | MP4, WebM, MOV, MKV, MP3, WAV, M4A, OGG, FLAC, … | Video: metadata plus up to four evenly spaced frames (needs `ffmpeg`). Audio: metadata only |

Textual attachments always degrade to a delimited block in the user message,
so any model can read them. Images become real image parts only for the
current turn; in older history they collapse to an `[attached: name]` marker to
keep the context window honest. If you pin a model that cannot accept images,
the send is rejected with a `no_vision` diagnosis rather than silently dropping
the file.

Server-side limits (adjustable through env: `ATTACHMENTS_ENABLED`,
`ATTACHMENT_MAX_MB`, `ATTACHMENT_DIR`; see `.env.example`):

- Up to 8 attachments per message.
- 25 MB per file by default, clamped to a hard ceiling.
- Unbound uploads are purged after 24 hours.

An unsupported file type is rejected with an error naming the file. A
supported file that cannot be read (for example a damaged PDF) is still
attached, marked with a warning on its chip, and the model is told it could
not be read. Neither blocks the text you typed.
`GET /api/chat/attachments/limits` tells the browser what it may upload, so the
UI enforces the same rules before sending.

Media needs `ffmpeg`/`ffprobe` on `PATH` for video frames; without them a video
still uploads and the model is told it cannot be read. Audio is documented to
the model as metadata only — automatic speech transcription is deliberately not
enabled, and the model is never told it heard something it did not.
