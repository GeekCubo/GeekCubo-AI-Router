"""Unit tests for custom-provider base URL validation and SSRF guards."""

from __future__ import annotations

import socket

import httpx
import pytest

from app.custom_providers import (
    CustomProviderValidationError,
    _parse_models_body,
    _send_test_request,
    normalize_slug,
    validate_base_url,
)


@pytest.mark.parametrize("eligible", [None, False, True])
@pytest.mark.parametrize("direct_insert", [False, True])
async def test_provider_orm_auto_default_and_explicit_preferences(db_session, eligible, direct_insert):
    from packages.db.models.custom_provider import CustomProvider

    values = {
        "slug": "test-provider",
        "display_name": "Test Provider",
        "base_url": "https://8.8.8.8/v1",
        "encrypted_key": b"test-key",
        "key_prefix": "test",
    }
    if eligible is not None:
        values["eligible_for_auto"] = eligible
    if direct_insert:
        from sqlalchemy import select

        await db_session.execute(CustomProvider.__table__.insert().values(**values))
        await db_session.commit()
        row = (await db_session.execute(select(CustomProvider))).scalar_one()
    else:
        row = CustomProvider(**values)
        db_session.add(row)
        await db_session.commit()
    await db_session.refresh(row)
    assert row.eligible_for_auto is (True if eligible is None else eligible)
    row.display_name = "Renamed"
    await db_session.commit()
    await db_session.refresh(row)
    assert row.eligible_for_auto is (True if eligible is None else eligible)


@pytest.mark.parametrize("eligible", [None, False, True])
async def test_direct_provider_creation_preserves_auto_preference(db_session, isolated_env, eligible):
    from app.routes.custom_providers import (
        CreateProvider,
        UpdateProvider,
        create_custom_provider,
        update_custom_provider,
    )

    values = {
        "display_name": "Test Provider",
        "base_url": "https://8.8.8.8/v1",
        "api_key": "sk-test-1234567890",
    }
    if eligible is not None:
        values["eligible_for_auto"] = eligible
    created = await create_custom_provider(CreateProvider(**values), db=db_session)
    expected = True if eligible is None else eligible
    assert created["eligible_for_auto"] is expected
    saved = await update_custom_provider(
        created["id"], UpdateProvider(display_name="Renamed"), db=db_session
    )
    assert saved["eligible_for_auto"] is expected


class TestNormalizeSlug:
    def test_lowercases_and_dashes(self):
        assert normalize_slug("Apixo AI") == "apixo-ai"

    def test_collapses_symbols(self):
        assert normalize_slug("  Venice/OpenRouter!!  ") == "venice-openrouter"

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            normalize_slug("   ")

    def test_truncates_to_50(self):
        assert len(normalize_slug("a" * 80)) <= 50


class TestValidateBaseUrl:
    def test_https_public_ip_accepted(self):
        assert validate_base_url("https://8.8.8.8/v1") == "https://8.8.8.8/v1"

    def test_trailing_slash_stripped(self):
        assert validate_base_url("https://8.8.8.8/v1/") == "https://8.8.8.8/v1"

    def test_http_remote_rejected(self):
        with pytest.raises(CustomProviderValidationError) as e:
            validate_base_url("http://8.8.8.8/v1")
        assert "https" in str(e.value)

    def test_localhost_rejected(self):
        with pytest.raises(CustomProviderValidationError):
            validate_base_url("https://localhost/v1")

    def test_loopback_rejected(self):
        with pytest.raises(CustomProviderValidationError):
            validate_base_url("https://127.0.0.1/v1")

    def test_private_ip_rejected(self):
        with pytest.raises(CustomProviderValidationError):
            validate_base_url("https://192.168.1.10/v1")

    def test_metadata_ip_rejected(self):
        with pytest.raises(CustomProviderValidationError):
            validate_base_url("https://169.254.169.254/latest")

    def test_userinfo_rejected(self):
        with pytest.raises(CustomProviderValidationError) as e:
            validate_base_url("https://user:pass@8.8.8.8/v1")
        assert "credential" in str(e.value)

    def test_non_http_scheme_rejected(self):
        with pytest.raises(CustomProviderValidationError):
            validate_base_url("ftp://8.8.8.8/v1")

    def test_empty_rejected(self):
        with pytest.raises(CustomProviderValidationError):
            validate_base_url("")

    def test_hostname_resolving_private_is_rejected(self, monkeypatch):
        monkeypatch.setattr(
            socket, "getaddrinfo",
            lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 0))],
        )
        with pytest.raises(CustomProviderValidationError):
            validate_base_url("https://rebind.internal/v1")

    def test_hostname_resolving_public_is_accepted(self, monkeypatch):
        monkeypatch.setattr(
            socket, "getaddrinfo",
            lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
        )
        assert validate_base_url("https://example.com/v1") == "https://example.com/v1"

    def test_resolution_failure_is_rejected(self, monkeypatch):
        def _boom(*a, **k):
            raise OSError("no such host")

        monkeypatch.setattr(socket, "getaddrinfo", _boom)
        with pytest.raises(CustomProviderValidationError) as e:
            validate_base_url("https://nonexistent.invalid/v1")
        assert "resolve" in str(e.value)


class TestLocalAllowlist:
    def test_allowlisted_local_http_accepted(self):
        url = validate_base_url(
            "http://localhost:8080/v1",
            allowed_local_hosts="localhost:8080",
        )
        assert url == "http://localhost:8080/v1"

    def test_allowlisted_private_ip_accepted(self):
        url = validate_base_url(
            "http://127.0.0.1:9000/v1",
            allowed_local_hosts="127.0.0.1:9000",
        )
        assert url == "http://127.0.0.1:9000/v1"

    def test_not_allowlisted_local_rejected(self):
        with pytest.raises(CustomProviderValidationError):
            validate_base_url(
                "http://localhost:9999/v1",
                allowed_local_hosts="localhost:8080",
            )


class TestEncodedAddressDefenses:
    def test_integer_encoded_loopback_rejected(self):
        # 2130706433 == 0x7F000001 == 127.0.0.1 in inet_aton single-number form.
        with pytest.raises(CustomProviderValidationError):
            validate_base_url("https://2130706433/v1")

    def test_hex_encoded_loopback_rejected(self):
        with pytest.raises(CustomProviderValidationError):
            validate_base_url("https://0x7f000001/v1")

    def test_ipv6_loopback_rejected(self):
        with pytest.raises(CustomProviderValidationError):
            validate_base_url("https://[::1]/v1")


@pytest.mark.parametrize(("target", "expected"), [
    ("https://other.example/models", None),
    ("https://origin.example:8443/models", None),
    ("https://origin.example/redirected", "Bearer secret"),
])
async def test_redirect_credential_is_scoped_to_origin(monkeypatch, target, expected):
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))],
    )
    sent = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request.headers.get("authorization"))
        if len(sent) == 1:
            return httpx.Response(302, headers={"location": target})
        return httpx.Response(200, json={"data": []})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), follow_redirects=False
    ) as client:
        result = await _send_test_request(
            client, "https://origin.example/models", api_key="secret", allowed_local_hosts=None
        )

    assert result["ok"] is True
    assert sent == ["Bearer secret", expected]


class TestParseModelsBody:
    def test_standard_openai_envelope(self):
        body = '{"object":"list","data":[{"id":"gpt-4o","object":"model","owned_by":"apixo"},{"id":"gpt-4o-mini"}]}'
        models, err = _parse_models_body(body)
        assert err is None
        assert [m["id"] for m in models] == ["gpt-4o", "gpt-4o-mini"]
        assert models[0]["owned_by"] == "apixo"
        assert models[0]["object"] == "model"

    def test_string_id_entries(self):
        models, err = _parse_models_body('{"data": ["a", "b", ""]}')
        assert err is None
        assert [m["id"] for m in models] == ["a", "b"]

    def test_bare_list_envelope(self):
        models, err = _parse_models_body('[{"id":"x"}, {"id":"y"}]')
        assert err is None
        assert [m["id"] for m in models] == ["x", "y"]

    def test_malformed_json(self):
        models, err = _parse_models_body("not json")
        assert models == []
        assert "malformed" in err

    def test_missing_data_list(self):
        models, err = _parse_models_body('{"object":"list"}')
        assert models == []
        assert err is not None

    def test_empty_list(self):
        models, err = _parse_models_body('{"data": []}')
        assert models == []
        assert "empty" in err

    def test_unknown_capabilities_not_invented(self):
        models, _ = _parse_models_body('{"data":[{"id":"m1"}]}')
        assert set(models[0].keys()) == {"id"}
