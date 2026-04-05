"""Tests for preflight readiness checks."""

import asyncio
import unittest.mock

import httpx
import pytest

from arm.services.tvdb import validate_tvdb_key


class TestTvdbKeyValidation:
    """Test validate_tvdb_key() API key validation."""

    def test_validate_tvdb_key_valid(self):
        """Successful TVDB login returns success=True."""
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"data": {"token": "tok_abc123"}}
        mock_response.raise_for_status = unittest.mock.MagicMock()

        async def mock_post(url, json=None):
            return mock_response

        mock_client = unittest.mock.MagicMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = unittest.mock.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = unittest.mock.AsyncMock(return_value=False)

        with unittest.mock.patch("arm.services.tvdb.httpx.AsyncClient",
                                 return_value=mock_client):
            result = asyncio.run(validate_tvdb_key("valid-api-key-123"))

        assert result["success"] is True
        assert "valid" in result["message"].lower()

    def test_validate_tvdb_key_invalid(self):
        """401 response returns success=False with 'Invalid' message."""
        mock_request = unittest.mock.MagicMock()
        mock_resp = unittest.mock.MagicMock()
        mock_resp.status_code = 401

        async def mock_post(url, json=None):
            raise httpx.HTTPStatusError(
                "Unauthorized", request=mock_request, response=mock_resp
            )

        mock_client = unittest.mock.MagicMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = unittest.mock.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = unittest.mock.AsyncMock(return_value=False)

        with unittest.mock.patch("arm.services.tvdb.httpx.AsyncClient",
                                 return_value=mock_client):
            result = asyncio.run(validate_tvdb_key("bad-key"))

        assert result["success"] is False
        assert "Invalid" in result["message"]

    def test_validate_tvdb_key_timeout(self):
        """Timeout returns success=False with 'timeout' in message."""
        async def mock_post(url, json=None):
            raise httpx.ReadTimeout("timed out")

        mock_client = unittest.mock.MagicMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = unittest.mock.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = unittest.mock.AsyncMock(return_value=False)

        with unittest.mock.patch("arm.services.tvdb.httpx.AsyncClient",
                                 return_value=mock_client):
            result = asyncio.run(validate_tvdb_key("some-key"))

        assert result["success"] is False
        assert "timed out" in result["message"].lower()

    def test_validate_tvdb_key_empty(self):
        """Empty API key returns failure without making a network call."""
        result = asyncio.run(validate_tvdb_key(""))
        assert result["success"] is False
        assert "empty" in result["message"].lower()

    def test_validate_tvdb_key_whitespace_only(self):
        """Whitespace-only API key is treated as empty."""
        result = asyncio.run(validate_tvdb_key("   "))
        assert result["success"] is False
        assert "empty" in result["message"].lower()

    def test_validate_tvdb_key_none(self):
        """None API key returns failure."""
        result = asyncio.run(validate_tvdb_key(None))
        assert result["success"] is False
        assert "empty" in result["message"].lower()

    def test_validate_tvdb_key_no_token_in_response(self):
        """Login succeeds but response lacks a token."""
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"data": {}}
        mock_response.raise_for_status = unittest.mock.MagicMock()

        async def mock_post(url, json=None):
            return mock_response

        mock_client = unittest.mock.MagicMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = unittest.mock.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = unittest.mock.AsyncMock(return_value=False)

        with unittest.mock.patch("arm.services.tvdb.httpx.AsyncClient",
                                 return_value=mock_client):
            result = asyncio.run(validate_tvdb_key("some-key"))

        assert result["success"] is False
        assert "no token" in result["message"].lower()

    def test_validate_tvdb_key_connect_error(self):
        """Connection error returns failure with network message."""
        async def mock_post(url, json=None):
            raise httpx.ConnectError("DNS resolution failed")

        mock_client = unittest.mock.MagicMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = unittest.mock.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = unittest.mock.AsyncMock(return_value=False)

        with unittest.mock.patch("arm.services.tvdb.httpx.AsyncClient",
                                 return_value=mock_client):
            result = asyncio.run(validate_tvdb_key("some-key"))

        assert result["success"] is False
        assert "connect" in result["message"].lower()

    def test_validate_tvdb_key_server_error(self):
        """Non-401 HTTP error returns the status code."""
        mock_request = unittest.mock.MagicMock()
        mock_resp = unittest.mock.MagicMock()
        mock_resp.status_code = 500

        async def mock_post(url, json=None):
            raise httpx.HTTPStatusError(
                "Internal Server Error", request=mock_request, response=mock_resp
            )

        mock_client = unittest.mock.MagicMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = unittest.mock.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = unittest.mock.AsyncMock(return_value=False)

        with unittest.mock.patch("arm.services.tvdb.httpx.AsyncClient",
                                 return_value=mock_client):
            result = asyncio.run(validate_tvdb_key("some-key"))

        assert result["success"] is False
        assert "500" in result["message"]

    def test_validate_tvdb_key_strips_whitespace(self):
        """API key with leading/trailing whitespace is stripped before use."""
        mock_response = unittest.mock.MagicMock()
        mock_response.json.return_value = {"data": {"token": "tok_abc"}}
        mock_response.raise_for_status = unittest.mock.MagicMock()

        posted_payloads = []

        async def mock_post(url, json=None):
            posted_payloads.append(json)
            return mock_response

        mock_client = unittest.mock.MagicMock()
        mock_client.post = mock_post
        mock_client.__aenter__ = unittest.mock.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = unittest.mock.AsyncMock(return_value=False)

        with unittest.mock.patch("arm.services.tvdb.httpx.AsyncClient",
                                 return_value=mock_client):
            result = asyncio.run(validate_tvdb_key("  my-key  "))

        assert result["success"] is True
        assert posted_payloads[0]["apikey"] == "my-key"
