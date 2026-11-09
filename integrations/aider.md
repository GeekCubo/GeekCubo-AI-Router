# Aider + GeekCubo

[Aider](https://aider.chat) speaks any OpenAI-compatible API. Two env vars and you're routing through GeekCubo:

```bash
export OPENAI_API_BASE=http://127.0.0.1:8787/v1
export OPENAI_API_KEY=sk-geek-PASTE-YOUR-KEY-HERE

# Use any catalog model
aider --model openai/auto                       # ← selected by your routing strategy
aider --model openai/gpt-4o
aider --model openai/claude-3-5-sonnet-latest
aider --model openai/gemini-2.5-flash
```

The `openai/` prefix is Aider's way of saying "use the OpenAI-compatible HTTP path." GeekCubo serves that path; the model name after the slash is what gets routed.

## Two-model edit/whole pattern

```bash
# Cheap model proposes diffs, expensive model confirms them.
aider \
  --model openai/auto \
  --weak-model openai/claude-3-5-haiku-latest
```

## Persistent config

`~/.aider.conf.yml`:

```yaml
openai-api-base: http://127.0.0.1:8787/v1
openai-api-key: sk-geek-PASTE-YOUR-KEY-HERE
model: openai/auto
weak-model: openai/claude-3-5-haiku-latest
```

## What you get

- One env var, every model.
- The local dashboard shows exactly what each Aider session cost.
- `model="auto"` picks a capable model per request with your routing strategy; with Adaptive-Gated, tool-heavy or long sessions use your *Hard* pool and routine edits your *Mundane* pool.
