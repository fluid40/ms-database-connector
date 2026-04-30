from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import requests

from ms_database_connector.config.aas_service_configuration import KeycloakConfig

logger = logging.getLogger(__name__)


@dataclass
class TokenResponse:
    access_token: str
    expires_in: int
    token_type: str
    _fetched_at: datetime = field(default_factory=datetime.now, init=False)

    @property
    def expires_at(self) -> datetime:
        # 10 Sekunden Puffer vor dem echten Ablauf
        return self._fetched_at + timedelta(seconds=self.expires_in - 10)

    @property
    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at


class AuthService:
    """
    Manages  the authentication against Keycloak
    via Client Credentials Flow.
    """

    def __init__(self, config: KeycloakConfig) -> None:
        self._config = config
        self._current_token: TokenResponse | None = None

    def get_access_token(self) -> str:
        """
        Returns a valid access token.
        Fetches a new one if needed (no token or expired).
        """
        if self._current_token is None or self._current_token.is_expired:
            logger.info("Token not available or expired – fetching new token.")
            self._current_token = self._fetch_token()

        return self._current_token.access_token

    def _fetch_token(self) -> TokenResponse:
        """Performs the Client Credentials Flow against Keycloak."""
        payload = {
            "grant_type": "client_credentials",
            "client_id": self._config.client_id,
            "client_secret": self._config.client_secret.get_secret_value(),
        }

        try:
            response = requests.post(
                url=self._config.token_endpoint,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10,
            )
            response.raise_for_status()

        except requests.HTTPError as e:
            logger.error(
                "Keycloak token request failed: %s – Response: %s",
                e,
                e.response.text if e.response else "no response",
            )
            raise
        except requests.RequestException as e:
            logger.error("Network error during token request: %s", e)
            raise

        data = response.json()

        logger.info(
            "New access token obtained, valid for %s seconds.",
            data.get("expires_in"),
        )

        return TokenResponse(
            access_token=data["access_token"],
            expires_in=data["expires_in"],
            token_type=data["token_type"],
        )

    def get_auth_header(self) -> dict[str, str]:
        """Returns the complete Authorization header."""
        return {"Authorization": f"Bearer {self.get_access_token()}"}
