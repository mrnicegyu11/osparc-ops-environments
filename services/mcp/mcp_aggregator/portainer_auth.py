"""Portainer authentication helper."""

from __future__ import annotations

import logging
import secrets
import time

import httpx

from . import config as cfg

logger = logging.getLogger("mcp-aggregator.portainer")


def obtain_token(
    server_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    *,
    max_retries: int = 3,
    retry_delay: int = 5,
) -> str | None:
    """Authenticate with Portainer and return a long-lived API token.

    Falls back to a short-lived JWT if API-token creation fails.
    Returns ``None`` after all retries are exhausted.
    """
    server_url = server_url or cfg.PORTAINER_SERVER
    username = username or cfg.PORTAINER_USER
    password = password or cfg.PORTAINER_PASSWORD
    domain = cfg.MONITORING_DOMAIN
    traefik_url = f"https://{domain}/portainer" if domain else ""

    for attempt in range(1, max_retries + 1):
        try:
            with httpx.Client(verify=False, timeout=10) as client:
                # Step 1: JWT
                auth = client.post(
                    f"{server_url}/api/auth",
                    json={"username": username, "password": password},
                )
                auth.raise_for_status()
                jwt = auth.json()["jwt"]

                # Step 2: user ID
                try:
                    me = client.get(
                        f"{server_url}/api/users/me",
                        headers={"Authorization": f"Bearer {jwt}"},
                    )
                    me.raise_for_status()
                    user_id = me.json()["Id"]
                except (httpx.HTTPError, KeyError, OSError):
                    user_id = 1

                # Step 3: API token via Traefik (CSRF-safe) or direct
                desc = f"mcp-aggregator-{secrets.token_hex(4)}"
                origin = f"https://{domain}" if domain else ""
                candidates = ([traefik_url] if traefik_url else []) + [server_url]

                for base in candidates:
                    try:
                        resp = client.post(
                            f"{base}/api/users/{user_id}/tokens",
                            headers={
                                "Authorization": f"Bearer {jwt}",
                                "Origin": origin or base,
                                "Referer": f"{origin or base}/",
                            },
                            json={"description": desc, "password": password},
                        )
                        resp.raise_for_status()
                        api_key = resp.json().get("rawAPIKey", "")
                        if api_key:
                            logger.info(
                                "API token created via %s (attempt %d)", base, attempt
                            )
                            return api_key
                    except (httpx.HTTPError, KeyError, OSError, ValueError) as exc:
                        logger.debug("Token via %s failed: %s", base, exc)

                # Fallback: short-lived JWT
                logger.warning("API token creation failed – falling back to JWT")
                return jwt

        except (httpx.HTTPError, KeyError, OSError) as exc:
            logger.warning("Auth attempt %d/%d failed: %s", attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(retry_delay)

    logger.warning("Could not obtain Portainer token after %d attempts", max_retries)
    return None
