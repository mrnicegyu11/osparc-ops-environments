"""Tests for mcp_aggregator.portainer_auth — token acquisition with mocked HTTP."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx


class TestObtainToken:
    """Test obtain_token with mocked httpx.Client."""

    def _import(self):
        from mcp_aggregator.portainer_auth import obtain_token

        return obtain_token

    def test_happy_path_api_token(self):
        """Full flow: JWT → user ID → API token."""
        obtain_token = self._import()

        mock_client = MagicMock()
        # auth response
        auth_resp = MagicMock()
        auth_resp.json.return_value = {"jwt": "jwt-123"}
        auth_resp.raise_for_status = MagicMock()
        # users/me response
        me_resp = MagicMock()
        me_resp.json.return_value = {"Id": 42}
        me_resp.raise_for_status = MagicMock()
        # token response
        token_resp = MagicMock()
        token_resp.json.return_value = {"rawAPIKey": "api-key-abc"}
        token_resp.raise_for_status = MagicMock()

        mock_client.post.side_effect = [auth_resp, token_resp]
        mock_client.get.return_value = me_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch(
            "mcp_aggregator.portainer_auth.httpx.Client", return_value=mock_client
        ):
            result = obtain_token(
                server_url="http://portainer:9000",
                username="admin",
                password="pass",
                max_retries=1,
            )
        assert result == "api-key-abc"

    def test_falls_back_to_jwt_when_token_creation_fails(self):
        """When API token creation returns no rawAPIKey, fall back to JWT."""
        obtain_token = self._import()

        mock_client = MagicMock()
        auth_resp = MagicMock()
        auth_resp.json.return_value = {"jwt": "jwt-fallback"}
        auth_resp.raise_for_status = MagicMock()

        me_resp = MagicMock()
        me_resp.json.return_value = {"Id": 1}
        me_resp.raise_for_status = MagicMock()

        token_resp = MagicMock()
        token_resp.json.return_value = {"rawAPIKey": ""}  # empty = failure
        token_resp.raise_for_status = MagicMock()

        mock_client.post.side_effect = [auth_resp, token_resp]
        mock_client.get.return_value = me_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch(
            "mcp_aggregator.portainer_auth.httpx.Client", return_value=mock_client
        ):
            result = obtain_token(
                server_url="http://portainer:9000",
                username="admin",
                password="pass",
                max_retries=1,
            )
        assert result == "jwt-fallback"

    def test_returns_none_after_retries_exhausted(self):
        """All retries fail → returns None."""
        obtain_token = self._import()

        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ConnectError("refused")
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch(
            "mcp_aggregator.portainer_auth.httpx.Client", return_value=mock_client
        ):
            result = obtain_token(
                server_url="http://portainer:9000",
                username="admin",
                password="pass",
                max_retries=2,
                retry_delay=0,
            )
        assert result is None

    def test_retries_on_network_error(self):
        """Network error on first try, succeeds on second."""
        obtain_token = self._import()

        # First call fails
        bad_client = MagicMock()
        bad_client.post.side_effect = httpx.ConnectError("refused")
        bad_client.__enter__ = MagicMock(return_value=bad_client)
        bad_client.__exit__ = MagicMock(return_value=False)

        # Second call succeeds
        good_client = MagicMock()
        auth_resp = MagicMock()
        auth_resp.json.return_value = {"jwt": "jwt-ok"}
        auth_resp.raise_for_status = MagicMock()
        me_resp = MagicMock()
        me_resp.json.return_value = {"Id": 1}
        me_resp.raise_for_status = MagicMock()
        token_resp = MagicMock()
        token_resp.json.return_value = {"rawAPIKey": "key-2"}
        token_resp.raise_for_status = MagicMock()
        good_client.post.side_effect = [auth_resp, token_resp]
        good_client.get.return_value = me_resp
        good_client.__enter__ = MagicMock(return_value=good_client)
        good_client.__exit__ = MagicMock(return_value=False)

        with patch(
            "mcp_aggregator.portainer_auth.httpx.Client",
            side_effect=[bad_client, good_client],
        ):
            result = obtain_token(
                server_url="http://portainer:9000",
                username="admin",
                password="pass",
                max_retries=2,
                retry_delay=0,
            )
        assert result == "key-2"

    def test_users_me_failure_defaults_user_id_to_1(self):
        """If /api/users/me fails, user_id defaults to 1."""
        obtain_token = self._import()

        mock_client = MagicMock()
        auth_resp = MagicMock()
        auth_resp.json.return_value = {"jwt": "jwt-x"}
        auth_resp.raise_for_status = MagicMock()

        mock_client.get.side_effect = httpx.HTTPError("boom")

        token_resp = MagicMock()
        token_resp.json.return_value = {"rawAPIKey": "key-fallback-uid"}
        token_resp.raise_for_status = MagicMock()

        mock_client.post.side_effect = [auth_resp, token_resp]
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch(
            "mcp_aggregator.portainer_auth.httpx.Client", return_value=mock_client
        ):
            result = obtain_token(
                server_url="http://portainer:9000",
                username="admin",
                password="pass",
                max_retries=1,
            )

        assert result == "key-fallback-uid"
        # Verify the token endpoint was called with user_id=1
        create_call = mock_client.post.call_args_list[1]
        assert "/api/users/1/tokens" in create_call.args[0]

    def test_traefik_url_tried_first_when_domain_set(self, monkeypatch):
        """When MONITORING_DOMAIN is set, Traefik URL is tried before direct."""
        obtain_token = self._import()
        monkeypatch.setenv("MONITORING_DOMAIN", "monitoring.example.com")

        # Reload config to pick up the domain
        import importlib

        from mcp_aggregator import config as cfg

        importlib.reload(cfg)

        mock_client = MagicMock()
        auth_resp = MagicMock()
        auth_resp.json.return_value = {"jwt": "jwt-t"}
        auth_resp.raise_for_status = MagicMock()
        me_resp = MagicMock()
        me_resp.json.return_value = {"Id": 5}
        me_resp.raise_for_status = MagicMock()
        token_resp = MagicMock()
        token_resp.json.return_value = {"rawAPIKey": "key-traefik"}
        token_resp.raise_for_status = MagicMock()

        mock_client.post.side_effect = [auth_resp, token_resp]
        mock_client.get.return_value = me_resp
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch(
            "mcp_aggregator.portainer_auth.httpx.Client", return_value=mock_client
        ):
            result = obtain_token(
                username="admin",
                password="pass",
                max_retries=1,
            )
        assert result == "key-traefik"
        # The token creation should go to the Traefik URL first
        token_call_url = mock_client.post.call_args_list[1].args[0]
        assert "monitoring.example.com" in token_call_url
