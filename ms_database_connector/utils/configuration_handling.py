
from fastapi import HTTPException, status
import logging
from pathlib import Path

from pydantic import ValidationError

from ms_database_connector.config.server_configuration import ServerConfiguration
from ms_database_connector.models.constants import CONFIG_BASE_PATH

_logger = logging.getLogger(__name__)

class ServerConfigurationsHandler:
    """Handler for loading and managing server configurations."""

    aas_registry_configuration: ServerConfiguration
    sm_registry_configuration: ServerConfiguration
    repo_server_configurations: list[ServerConfiguration]

    def __init__(self):
        """Initialize ConfigHandler with default values."""
        self.repo_server_configurations = []
        self._get_config_files()

    def _get_config_files(self):
        config_base_path = Path(CONFIG_BASE_PATH)

        if not config_base_path.exists() or not config_base_path.is_dir():
            _logger.error(f"Configuration base path '{config_base_path}' not found or inaccessible.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Configuration base path '{config_base_path}' not found.",
            )

        self._get_aas_registry_config()
        self._get_sm_registry_config()
        self._get_repos_configs()

    def _get_aas_registry_config(self):
        config_path = Path(f"{CONFIG_BASE_PATH}/aas_registry")

        if not config_path.exists() or not config_path.is_dir():
            _logger.error(f"AAS registry configuration path '{config_path}' not found or inaccessible.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"AAS registry configuration path '{config_path}' not found.",
            )

        json_files = list(config_path.rglob("*.json"))

        if not json_files or len(json_files) == 0:
            _logger.error(f"No AAS registry configuration files found in folder '{config_path}'.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No AAS registry configuration files found in folder '{config_path}'.",
            )

        _logger.debug(f"Found {len(json_files)} AAS registry configuration files in folder '{config_path}'.")

        if len(json_files) > 1:
            _logger.warning(f"Multiple AAS registry configuration files found. Using the first one: '{json_files[0]}'.")

        try:
            self.aas_registry_configuration = ServerConfiguration.model_validate_json(json_files[0].read_text())
        except ValidationError as ve:
            _logger.error(f"Invalid Submodel registry connection file: {ve}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Submodel registry connection file.",
            ) from ve

    def _get_sm_registry_config(self):
        config_path = Path(f"{CONFIG_BASE_PATH}/submodel_registry")

        if not config_path.exists() or not config_path.is_dir():
            _logger.error(f"Submodel registry configuration path '{config_path}' not found or inaccessible.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Submodel registry configuration path '{config_path}' not found.",
            )

        json_files = list(config_path.rglob("*.json"))

        if not json_files or len(json_files) == 0:
            _logger.error(f"No Submodel registry configuration files found in folder '{config_path}'.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No Submodel registry configuration files found in folder '{config_path}'.",
            )

        _logger.debug(f"Found {len(json_files)} Submodel registry configuration files in folder '{config_path}'.")

        if len(json_files) > 1:
            _logger.warning(f"Multiple Submodel registry configuration files found. Using the first one: '{json_files[0]}'.")

        try:
            self.sm_registry_configuration = ServerConfiguration.model_validate_json(json_files[0].read_text())
        except ValidationError as ve:
            _logger.error(f"Invalid Submodel registry connection file: {ve}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Submodel registry connection file.",
            ) from ve

    def _get_repos_configs(self):
        """Get the AAS server configurations from the service configuration.

        :param configuration: The service configuration
        :return: List of AAS server configurations
        """
        config_path = Path(f"{CONFIG_BASE_PATH}/repo_server")

        if not config_path.exists() or not config_path.is_dir():
            _logger.error(f"AAS repository configuration path '{config_path}' not found or inaccessible.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"AAS repository configuration path '{config_path}' not found.",
            )

        json_files = list(config_path.rglob("*.json"))

        if not json_files or len(json_files) == 0:
            _logger.info(f"No AAS repository configuration files found in folder '{config_path}'.")
            return

        for json_file in json_files:
            try:
                aas_server_configuration = ServerConfiguration.model_validate_json(json_file.read_text())
                self.repo_server_configurations.append(aas_server_configuration)
            except ValidationError as ve:
                _logger.error(f"Invalid AAS repository connection file '{json_file}': {ve}")

        _logger.debug(f"Found {len(self.repo_server_configurations)} AAS repository configuration files in folder '{config_path}'.")