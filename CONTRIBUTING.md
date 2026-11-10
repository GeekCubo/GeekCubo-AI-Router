# Contributing to GeekCubo

Thanks for helping improve GeekCubo, a self-hosted, MIT-licensed AI router.
This guide covers the fork-and-pull-request workflow, running the tests, and
how changes are reviewed.

By participating you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md).
**Never report a security vulnerability in a public issue or pull request.**
Use the private process in [SECURITY.md](SECURITY.md).

## Before you start

- **Bugs:** open an issue with the *Bug report* template. Include your version
  (`geekcubo --version` or the image tag), how you run it, and steps to reproduce.
- **Features:** open an issue with the *Feature request* template first, so the
  idea can be discussed before you invest time in code.
- **Small fixes** (typos, docs, an obvious one-line bug) can go straight to a PR.

## 1. Fork and clone

1. Click **Fork** on <https://github.com/GeekCubo/GeekCubo-AI-Router>.
2. Clone your fork and add the upstream remote:

   ```bash
   git clone https://github.com/<your-user>/GeekCubo-AI-Router.git
   cd GeekCubo-AI-Router
   git remote add upstream https://github.com/GeekCubo/GeekCubo-AI-Router.git
   ```

## 2. Create a development branch

Always branch from an up-to-date `main`; never commit to `main` in your fork.

```bash
git fetch upstream
git switch -c fix/short-description upstream/main
```

Use a short, descriptive branch name such as `fix/analytics-range`,
`feat/provider-x` or `docs/deployment-typo`.

## 3. Set up and run the tests

Python 3.11+ and Node.js (only for `node --check`) are required.

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

ruff check .                              # lint
node --check design/app.js                # dashboard syntax
python -m unittest design.test_i18n_unittest   # localization tables
bash -n install.sh                        # installer syntax
PYTHONPATH=. pytest -q                    # full test suite
```

The browser tests in `tests/ui` drive the real dashboard with Playwright. They
skip automatically when Chromium is missing; to run them:

```bash
pip install -e ".[ui]" && playwright install chromium
PYTHONPATH=. pytest -q tests/ui
```

The tests start disposable servers on temporary SQLite files. They never need
real provider keys and never call a paid model. Do not add tests that do.

To try the dashboard locally:

```bash
DATABASE_URL=sqlite+aiosqlite:///./dev.db ALLOW_INSECURE_DEV_KEY=true python scripts/start.py
```

The first-run setup token is printed in the log.

## 4. Make your change

- Keep changes focused: one fix or feature per pull request.
- Follow the style of the surrounding code. The dashboard is plain JavaScript
  with no build step (`design/`); the backend is FastAPI (`app/`, `packages/`).
- Add or update tests for behaviour you change.
- User-visible dashboard text goes through the `I18N` table in `design/app.js`.
  Add the English string and its translations for all 12 locales; the
  localization test enforces this.
- Never commit secrets, `.env` files, databases or real API keys. Use
  placeholders such as `sk-...` and `https://example.com` in docs and tests.
- Code, comments, commit messages and docs are written in English.

## 5. Commit and open a pull request

```bash
git add -A
git commit -m "Analytics: keep the reporting range when switching tabs"
git push -u origin fix/short-description
```

Then open a pull request against `GeekCubo/GeekCubo-AI-Router:main` and fill in
the template. Keep the PR up to date by rebasing on `upstream/main` if it falls
behind.

## How changes are reviewed

1. **CI runs automatically** on every pull request, including documentation-only
   ones: lint, dashboard and installer syntax checks, localization checks, the
   full test suite, a wheel build and a Docker smoke test. CI for pull requests from forks runs with a
   read-only token and **no repository secrets**.
2. **A maintainer reviews** the change for correctness, security, tests,
   documentation and scope. At least one approving review is required.
3. **Requested changes** are pushed to the same branch; the PR updates itself.
4. **Merging** is done by a maintainer once CI passes and the review is
   approved. `main` is protected: no direct pushes, no force pushes.
5. **Releases** (Docker images on GHCR, PyPI packages) are published only by
   maintainer-controlled workflows on pushes to `main` and version tags. A
   pull request never publishes or deploys anything.

## Licensing and attribution

GeekCubo is released under the [MIT License](LICENSE) and is derived from
[OrcaRouter Lite](https://github.com/Continuum-AI-Corp/OrcaRouter-Lite). The
upstream copyright notice in `LICENSE` must be preserved. By submitting a
contribution you agree that it is licensed under the same MIT License.

Any third-party font, image or other asset you add must record its origin and
license next to it.
