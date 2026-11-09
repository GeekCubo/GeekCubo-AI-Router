# Security, administrator account and API keys

[← Back to the README](../README.md)

The administrator account, sessions (including Remember me), API keys, which credential goes where, encryption at rest, backups and troubleshooting.

The dashboard signs in with a **username and password**. `sk-geek-*` keys are machine credentials for SDKs and CLIs: they cannot open the dashboard or change settings, and a dashboard session cannot be used for `/v1/chat/completions`. Revoking every API key never locks you out of the dashboard.

## Administrator account

Examples use the bundled Docker base URL, `http://127.0.0.1:8787`. Substitute the port if you changed the Compose mapping.

### First-time setup

When no administrator exists, the server prints a one-time setup token on start:

```
── Administrator setup required ──
One-time setup token (valid 24h): <token>
```

`./install.sh` retrieves and prints this token for you on a fresh install. For a manual install, use the CLI:

```bash
docker compose exec api python -m app.admin_cli setup-token
```

1. Open the dashboard and choose **Create Administrator Account**.
2. Enter a username, a password (8+ characters; a multi-word passphrase is ideal), the confirmation, and the setup token.

There are no default credentials and no public registration; a remote visitor cannot create the account without the token from the server log. The token is single-use and becomes invalid once the administrator exists. After that, `setup-token` refuses to issue another: it never discloses a token after setup and never regenerates one just because the installer ran again. Treat the token like a password and do not share screenshots or terminal transcripts that contain it. Lost it before setup finished? Generate a new one (the old one stops working), or create the account from the shell instead:

```bash
docker compose exec api python -m app.admin_cli setup-token
docker compose exec api python -m app.admin_cli setup --username <name>   # prompts for the password
```

Normal GeekCubo restarts and updates preserve your database, provider credentials, custom providers and `sk-geek-*` keys. Keep the data volume and encryption secrets together; see [Deployment](../DEPLOYMENT.md) for backup and update procedures.

### Sign in, change password, sessions

- Sign in at `/` with your username and password. Sessions are stored server-side and use an HttpOnly, `SameSite=Lax` cookie (`Secure` over HTTPS) with a per-session CSRF token. A normal session ends after 12 hours, or after 60 minutes without activity.
- **Remember me for 14 days** (unchecked by default) keeps this browser signed in for up to 14 days from sign-in, even after it is closed or left idle. The limit is enforced server-side and is never extended by activity. Use it only on a device you trust. Logout, a password change or reset, **Log out all other sessions** and `admin_cli revoke-sessions` end remembered sessions exactly like normal ones.
- **Settings → Security** shows the account, every signed-in browser with its session type (normal or remembered) and expiry, changes the password, and can log out all other sessions. Changing the password signs out every other device; this one stays signed in. API keys are unaffected.

### Forgot the password

Recovery is local-only — no email reset and no HTTP endpoint. Run it where the server runs:

```bash
docker compose exec api python -m app.admin_cli reset-password
```

The new password is read from a hidden prompt (or one line on stdin with `--password-stdin`); there is no `--password` flag. All dashboard sessions are signed out. Provider keys, API keys, models and usage history are not touched.

### Generate an `sk-geek-*` key

**Settings → API Keys** shows the API endpoint clients should use (from `PUBLIC_BASE_URL`, or the local `http://127.0.0.1:8787/v1` when it is not set) with a **Copy URL** button. Name the key (optionally an expiry) → **Generate New API Key**. The new key stays visible until you hide it or leave the page, with **Copy API key**, **Download credentials** (a `.env` file that contains the secret) and ready-to-copy environment examples.

A fresh database also prints a first `sk-geek-*` key to the server log on its first start; it keeps working for inference until you revoke it.

GeekCubo stores only a one-way hash, so an existing key can never be shown or copied again. If you lose one, **Rotate** it: the replacement has the same restrictions and the old key keeps working until you revoke it. **Revoke** takes effect immediately.

## Which key goes where

Three different kinds of credential appear around GeekCubo. They are not interchangeable.

| Credential | Looks like | Where it lives | What it does |
|---|---|---|---|
| **Upstream provider key** | `sk-...`, `sk-ant-...`, `AIza...` | GeekCubo **server**: dashboard (encrypted) or the server's `.env` (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, ...) | Lets GeekCubo call OpenAI, Anthropic, Google and the others on your behalf |
| **GeekCubo inference key** | `sk-geek-...` | The **client** (your shell, tool or app). Generated in **Settings → API Keys** | Authenticates a client to GeekCubo. GeekCubo stores only its hash |
| **Client environment variable** | a name, not a key | The **client** process | Chosen by the client. GeekCubo-specific configs use `GEEKCUBO_API_KEY`; generic OpenAI SDKs read `OPENAI_API_KEY` and `OPENAI_BASE_URL` |

When a generic OpenAI SDK runs with `OPENAI_API_KEY=sk-geek-...` and `OPENAI_BASE_URL` pointing at GeekCubo, the variable name is OpenAI's but the value is a GeekCubo key. The `OPENAI_API_KEY` in GeekCubo's *server* `.env` is a different credential: your upstream OpenAI account. Never put an `sk-geek-*` key in the server `.env`.

Variable names do not change how GeekCubo authenticates: it accepts the `sk-geek-*` value in `Authorization: Bearer` (OpenAI and Anthropic clients), `x-api-key` (Anthropic) or the Gemini SDK's key parameter, whatever variable the client read it from.

## Encryption at rest

On first start GeekCubo provisions two secrets automatically and writes them to a `.geekcubo-secrets` file next to the database (mode `0600`, never committed, never logged):

- `CREDENTIAL_ENCRYPTION_KEY` — the AES-256 key that seals provider and Artificial Analysis credentials at rest.
- `API_KEY_PEPPER` — the pepper for inference-key hashing.

Restarting never regenerates them (the file is reused). If you set either value in `.env`, it takes precedence and is never overwritten. If the database already holds encrypted records but the key is missing (for example, a partial restore), GeekCubo refuses to start rather than inventing a key that could never decrypt them — restore the key from backup.

### Controlled key rotation

```bash
# 1. In .env, keep the old key and set the new one
#    CREDENTIAL_ENCRYPTION_PREVIOUS_KEY=<old>
#    CREDENTIAL_ENCRYPTION_KEY=<new>
# 2. Restart. Startup re-encrypts stored keys and logs
#    reencrypted_provider_keys / undecryptable_provider_keys.
# 3. Confirm the dashboard shows Enabled, then remove the previous key
#    and restart once more.
```

Rotation covers every field encrypted with the credential key (provider keys, custom-provider keys, the Artificial Analysis key, and custom metadata-source tokens). Re-save any row still marked "Can't decrypt" if a value was already unreadable before the rotation.

## Rebuild safely and back up

```bash
docker compose build api
docker compose up -d api
docker compose logs -f api
```

Your data lives in the `geekcubo-data` named volume, so a rebuild keeps it. Rerunning `./install.sh` is also safe: it reuses the existing volume, `.env`, administrator account, provider credentials, encryption secrets and `sk-geek-*` keys. Never run `docker compose down -v` — it deletes the volume. To back up, stop the service and copy `/data`. It contains the database (with its SQLite `-wal`/`-shm` files), chat attachments and the automatically generated `.geekcubo-secrets` file holding `CREDENTIAL_ENCRYPTION_KEY`, without which stored provider keys can't be decrypted. If you set the encryption secrets in `.env` instead, back up `.env` as well.

```bash
docker compose stop api
docker compose cp api:/data ./geekcubo-data-backup
docker compose start api
```

Behind a reverse proxy that terminates HTTPS, set `TRUST_PROXY_HEADERS=true` so session cookies get the `Secure` flag. Leave it off for direct localhost use.

## Troubleshooting an install

`./install.sh` re-checks Docker, Compose, `.env`, health and administrator state on every run. To diagnose a failure yourself:

```bash
docker compose ps
docker compose logs --tail=100 api
```

If Docker needs elevated permissions, use `sudo docker compose ps` and `sudo docker compose logs --tail=100 api` instead. Re-running the installer after fixing the problem is safe; it reuses the existing `geekcubo-data` volume, `.env`, administrator account, provider credentials, encryption secrets and API keys. It never runs `docker compose down -v`.
