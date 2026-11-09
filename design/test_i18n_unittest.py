"""Localization guardrails for the dashboard.

These are static checks over `design/app.js` and `design/index.html`. They
exist because two classes of defect shipped unnoticed:

  * a locale silently missing keys, so the UI fell back to English mid-screen;
  * the same key defined twice in one locale object, where the later value
    wins and edits to the earlier one appear to do nothing.

The tables are written as object literals, so this parses them textually
rather than importing JavaScript.
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_JS = (ROOT / "app.js").read_text(encoding="utf-8")
INDEX_HTML = (ROOT / "index.html").read_text(encoding="utf-8")

LOCALES = ["en", "zh", "hi", "es", "pt", "ru", "ja", "de", "fr", "it", "ar", "ko"]

# Keys that are allowed to be identical to English in another locale: proper
# nouns, loanwords that are genuinely the standard term, and token forms.
SAME_AS_ENGLISH_OK = {
    # Loanwords and identical terms that are genuinely correct in the target
    # language. Everything else that matches English is a translation miss.
    "en": set(),
    "es": {"auth.password", "ui.endpoint", "ui.manual"},
    "pt": {"auth.password", "ui.status", "ui.pools", "ui.endpoint", "ui.volume", "ui.manual"},
    "de": {"tab.routing.title", "ui.system", "ui.status", "ui.pools", "ui.format",
           "ui.name", "ui.routing", "ui.administrator", "ui.optional"},
    "fr": {"auth.password", "sec.sessions", "ui.pools", "ui.messages", "ui.mode",
           "ui.messages_2", "ui.format", "ui.volume", "ui.actions"},
    "it": {"auth.password", "ui.provider", "ui.legacy", "ui.endpoint", "ui.volume"},
    "zh": set(), "ja": set(), "ko": set(), "ru": set(), "hi": set(), "ar": set(),
}
# A vendor name and a literal URL example are identical in every language.
for _locale in SAME_AS_ENGLISH_OK:
    SAME_AS_ENGLISH_OK[_locale] |= {
        "chat.search_backend_tavily",
        "chat.search_url_ph",
    }


def _locale_blocks() -> dict[str, list[tuple[str, str]]]:
    """Return each locale as an ordered list of (key, value) pairs.

    Kept as a list, not a dict, so duplicate keys stay visible.
    """
    body = re.search(r"const I18N = \{([\s\S]*?)\n\};", APP_JS).group(1)
    blocks: dict[str, list[tuple[str, str]]] = {}
    for loc, inner in re.findall(
        r"\n  ([a-z]{2}): \{([\s\S]*?)\},(?=\n  [a-z]{2}:|\s*$)", body
    ):
        blocks[loc] = [
            (k, json.loads(v))
            for k, v in re.findall(r'"([^"]+)":\s*("(?:[^"\\]|\\.)*")', inner)
        ]
    return blocks


class I18NTests(unittest.TestCase):
    def setUp(self):
        self.blocks = _locale_blocks()

    def test_supported_locales_present(self):
        m = re.search(r"SUPPORTED_LOCALES\s*=\s*\[(.*?)\];", APP_JS, re.S)
        self.assertIsNotNone(m)
        declared = {s.strip().strip('"') for s in m.group(1).split(",") if s.strip()}
        self.assertEqual(declared, set(LOCALES))
        self.assertEqual(set(self.blocks), set(LOCALES))

    def test_every_locale_defines_exactly_the_english_keys(self):
        en_keys = [k for k, _ in self.blocks["en"]]
        for loc in LOCALES:
            keys = [k for k, _ in self.blocks[loc]]
            self.assertEqual(
                len(keys), len(set(keys)),
                f"{loc} repeats a key: "
                f"{sorted({k for k in keys if keys.count(k) > 1})}",
            )
            self.assertEqual(
                sorted(keys), sorted(en_keys),
                f"{loc} key set differs from en: "
                f"missing={sorted(set(en_keys) - set(keys))} "
                f"extra={sorted(set(keys) - set(en_keys))}",
            )

    def test_no_locale_ships_english_text(self):
        en = dict(self.blocks["en"])
        for loc in LOCALES:
            if loc == "en":
                continue
            allowed = SAME_AS_ENGLISH_OK.get(loc, set())
            copied = [
                k for k, v in self.blocks[loc]
                if v == en[k] and k not in allowed
            ]
            self.assertFalse(copied, f"{loc} still shows English for {copied}")

    def test_no_empty_strings(self):
        for loc in LOCALES:
            empty = [k for k, v in self.blocks[loc] if not v.strip()]
            self.assertFalse(empty, f"{loc} has empty strings for {empty}")

    def test_every_tab_meta_key_exists_in_every_locale(self):
        meta_keys = set(re.findall(r'(?:title|sub):\s*"([a-z0-9_.]+)"', APP_JS))
        self.assertTrue(meta_keys, "TAB_META keys not found")
        for loc in LOCALES:
            present = {k for k, _ in self.blocks[loc]}
            missing = meta_keys - present
            self.assertFalse(missing, f"{loc} missing TAB_META keys {sorted(missing)}")

    def test_index_html_i18n_attributes_resolve(self):
        """Every data-i18n hook in the HTML must exist in every locale."""
        used = set(re.findall(r'data-i18n="([^"]+)"', INDEX_HTML))
        self.assertTrue(used, "no data-i18n attributes found in index.html")
        for loc in LOCALES:
            present = {k for k, _ in self.blocks[loc]}
            missing = used - present
            self.assertFalse(missing, f"{loc} missing {sorted(missing)}")

    def test_key_invalid_names_the_current_prefix(self):
        """A stale prefix here tells users to check the wrong thing."""
        for loc in LOCALES:
            value = dict(self.blocks[loc])["auth.key_invalid"]
            self.assertIn("sk-geek-", value, f"{loc} auth.key_invalid must name sk-geek-")

    def test_taglines_are_distinct_per_locale(self):
        """Two locales sharing a tagline means one was never translated."""
        taglines = {loc: dict(self.blocks[loc])["auth.tagline"] for loc in LOCALES}
        self.assertEqual(
            len(set(taglines.values())), len(LOCALES),
            f"duplicate taglines: {taglines}",
        )


    def test_no_hardcoded_english_in_dynamic_messages(self):
        """toast/confirm/prompt must go through t()/tf(), never a literal."""
        import re

        # Calls whose first argument is a plain string or template literal
        # (backtick or quote directly after the opening paren), and which do
        # not already start with t( / tf(.
        for fn in ("toast", "confirm", "prompt"):
            for m in re.finditer(
                fn + r"\s*\(\s*(?!t\s*\()(?!tf\s*\()[`\"]",
                APP_JS,
            ):
                # Error passthroughs (e.message) are not UI copy.
                snippet = APP_JS[m.start():m.start() + 80].replace("\n", " ")
                if "message" in snippet or "problem" in snippet:
                    continue
                # A template literal that interpolates a t(...)/tf(...) call is
                # already translated; only bare English literals are a miss.
                if re.search(r"t\s*\(\s*[`\"']|tf\s*\(", snippet):
                    continue
                line = APP_JS[: m.start()].count("\n") + 1
                self.fail(
                    f"untranslated {fn}() literal near line {line}: {snippet!r}"
                )


if __name__ == "__main__":
    unittest.main()
