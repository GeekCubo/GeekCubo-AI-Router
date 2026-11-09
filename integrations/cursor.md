# Cursor + GeekCubo

Cursor lets you bring your own OpenAI-compatible model. GeekCubo slots right in.

## Setup

1. **Settings → Models → Override OpenAI Base URL**: `http://127.0.0.1:8787/v1`
2. **Settings → Models → OpenAI API Key**: paste your `sk-geek-...`
3. **Settings → Models → Custom Model Names**: add the models you care about, e.g.
   - `auto`
   - `gpt-4o`
   - `claude-3-5-sonnet-latest`
   - `claude-3-5-haiku-latest`
   - `gemini-2.5-flash`

Cursor then sends chat requests (Cmd-K, Cmd-L) for those model names through
GeekCubo, which handles the actual provider routing. Cursor's own Tab
completion and background agents keep using Cursor's models.

## Caveat

Cursor's "Composer" mode pins specific models internally and may bypass your
custom config for some flows. Cmd-K and Cmd-L are reliable.
