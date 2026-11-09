"""Current GeekCubo inference-key generation."""


def test_generated_keys_use_current_format():
    from packages.auth.hashing import generate_api_key

    issued = set()
    for _ in range(20):
        raw, digest, prefix = generate_api_key()
        assert raw.startswith("sk-geek-")
        assert prefix.startswith("sk-geek-....")
        assert digest
        assert raw not in issued
        issued.add(raw)
