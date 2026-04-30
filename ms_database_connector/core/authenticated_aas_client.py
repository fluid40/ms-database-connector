from __future__ import annotations

import logging

import requests
from requests import HTTPError, RequestException

from ms_database_connector.config.aas_service_configuration import BaSyxConfig
from ms_database_connector.core.auth_service import AuthService

logger = logging.getLogger(__name__)


class AASClient:
    """
    Client für die BaSyx AAS-Infrastruktur.
    Authentifiziert sich automatisch via AuthService.
    """

    def __init__(self, config: BaSyxConfig, auth_service: AuthService) -> None:
        self._config = config
        self._auth = auth_service
        self._session = requests.Session()

    def _get(self, url: str) -> dict:
        """Führt einen authentifizierten GET-Request durch."""
        try:
            response = self._session.get(
                url=url,
                headers=self._auth.get_auth_header(),
                timeout=10,
            )
            response.raise_for_status()
            return response.json()

        except HTTPError as e:
            logger.error("HTTP-Fehler bei GET %s: %s", url, e)
            raise
        except RequestException as e:
            logger.error("Netzwerkfehler bei GET %s: %s", url, e)
            raise

    # ------------------------------------------------------------------ #
    # AAS Registry
    # ------------------------------------------------------------------ #

    def get_all_aas_descriptors(self) -> dict:
        """Gibt alle AAS-Deskriptoren aus der AAS Registry zurück."""
        url = f"{self._config.aas_registry_url}/shell-descriptors"
        return self._get(url)

    # ------------------------------------------------------------------ #
    # Submodel Registry
    # ------------------------------------------------------------------ #

    def get_all_sm_descriptors(self) -> dict:
        """Gibt alle Submodel-Deskriptoren aus der SM Registry zurück."""
        url = f"{self._config.sm_registry_url}/submodel-descriptors"
        return self._get(url)

    # ------------------------------------------------------------------ #
    # AAS Repository
    # ------------------------------------------------------------------ #

    def get_all_shells(self) -> dict:
        """Gibt alle Asset Administration Shells zurück."""
        url = f"{self._config.aas_repository_url}/shells"
        return self._get(url)

    def get_shell_by_id(self, aas_id_b64: str) -> dict:
        """Gibt eine AAS anhand ihrer Base64-kodierten ID zurück."""
        url = f"{self._config.aas_repository_url}/shells/{aas_id_b64}"
        return self._get(url)

    # ------------------------------------------------------------------ #
    # Submodel Repository
    # ------------------------------------------------------------------ #

    def get_all_submodels(self) -> dict:
        """Gibt alle Submodels zurück."""
        url = f"{self._config.sm_repository_url}/submodels"
        return self._get(url)

    def get_submodel_by_id(self, sm_id_b64: str) -> dict:
        """Gibt ein Submodel anhand seiner Base64-kodierten ID zurück."""
        url = f"{self._config.sm_repository_url}/submodels/{sm_id_b64}"
        return self._get(url)
