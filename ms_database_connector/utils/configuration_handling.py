from fastapi import HTTPException, status
import logging
from pathlib import Path

from pydantic import ValidationError

from ms_database_connector.config.server_configuration import ServerConfiguration
from ms_database_connector.models.constants import CONFIG_BASE_PATH

_logger = logging.getLogger(__name__)


class ServerConfigurationsHandler:
    """Handler for loading and managing server configurations.

    Loads and manages configuration files for AAS registry, Submodel registry,
    and AAS repository servers from the configuration directory.

    Attributes:
        aas_registry_configuration: Configuration for the AAS registry server.
        sm_registry_configuration: Configuration for the Submodel registry server.
        repo_server_configurations: List of configurations for AAS repository servers.
    """

    aas_registry_configuration: ServerConfiguration
    sm_registry_configuration: ServerConfiguration
    repo_server_configurations: list[ServerConfiguration]

    def __init__(self):
        """Initialize ServerConfigurationsHandler and load all configuration files.

        Loads configuration files from the predefined configuration directory:
        - AAS registry configuration from aas_registry/
        - Submodel registry configuration from submodel_registry/
        - AAS repository configurations from repo_server/

        Raises:
            HTTPException: If configuration directory does not exist or required
                configuration files are not found.
        """
        self.repo_server_configurations = []
        self._get_config_files()

    def _get_config_files(self):
        """Initialize configuration file loading for all server types.

        Verifies that the configuration base path exists and loads configurations
        for AAS registry, Submodel registry, and AAS repositories.

        Raises:
            HTTPException: If the configuration base path does not exist or is
                not accessible.
        """
        config_base_path = Path(CONFIG_BASE_PATH)

        if not config_base_path.exists() or not config_base_path.is_dir():
            _logger.error(
                f"Configuration base path '{config_base_path}' not found or inaccessible."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Configuration base path '{config_base_path}' not found.",
            )

        self._get_aas_registry_config()
        self._get_sm_registry_config()
        self._get_repos_configs()

    def _get_aas_registry_config(self):
        """Load and validate AAS registry server configuration.

        Reads the first JSON configuration file found in the aas_registry directory
        and parses it into a ServerConfiguration object.

        Raises:
            HTTPException: If configuration directory does not exist, no configuration
                files are found, or the configuration file is invalid (validation error).
        """
        config_path = Path(f"{CONFIG_BASE_PATH}/aas_registry")

        if not config_path.exists() or not config_path.is_dir():
            _logger.error(
                f"AAS registry configuration path '{config_path}' not found or inaccessible."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"AAS registry configuration path '{config_path}' not found.",
            )

        json_files = list(config_path.rglob("*.json"))

        if not json_files or len(json_files) == 0:
            _logger.error(
                f"No AAS registry configuration files found in folder '{config_path}'."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No AAS registry configuration files found in folder '{config_path}'.",
            )

        _logger.debug(
            f"Found {len(json_files)} AAS registry configuration files in folder '{config_path}'."
        )

        if len(json_files) > 1:
            _logger.warning(
                f"Multiple AAS registry configuration files found. Using the first one: '{json_files[0]}'."
            )

        try:
            self.aas_registry_configuration = ServerConfiguration.model_validate_json(
                json_files[0].read_text()
            )
        except ValidationError as ve:
            _logger.error(f"Invalid Submodel registry connection file: {ve}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Submodel registry connection file.",
            ) from ve

    def _get_sm_registry_config(self):
        """Load and validate Submodel registry server configuration.

        Reads the first JSON configuration file found in the submodel_registry directory
        and parses it into a ServerConfiguration object.

        Raises:
            HTTPException: If configuration directory does not exist, no configuration
                files are found, or the configuration file is invalid (validation error).
        """
        config_path = Path(f"{CONFIG_BASE_PATH}/submodel_registry")

        if not config_path.exists() or not config_path.is_dir():
            _logger.error(
                f"Submodel registry configuration path '{config_path}' not found or inaccessible."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Submodel registry configuration path '{config_path}' not found.",
            )

        json_files = list(config_path.rglob("*.json"))

        if not json_files or len(json_files) == 0:
            _logger.error(
                f"No Submodel registry configuration files found in folder '{config_path}'."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No Submodel registry configuration files found in folder '{config_path}'.",
            )

        _logger.debug(
            f"Found {len(json_files)} Submodel registry configuration files in folder '{config_path}'."
        )

        if len(json_files) > 1:
            _logger.warning(
                f"Multiple Submodel registry configuration files found. Using the first one: '{json_files[0]}'."
            )

        try:
            self.sm_registry_configuration = ServerConfiguration.model_validate_json(
                json_files[0].read_text()
            )
        except ValidationError as ve:
            _logger.error(f"Invalid Submodel registry connection file: {ve}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Submodel registry connection file.",
            ) from ve

    def _get_repos_configs(self):
        """Load all AAS repository server configurations.

        Reads all JSON configuration files found in the repo_server directory
        and parses them into ServerConfiguration objects. If no files are found,
        the repository configurations list remains empty (not an error).

        Invalid configuration files are logged as errors but do not prevent
        loading of other files.
        """
        config_path = Path(f"{CONFIG_BASE_PATH}/repo_server")

        if not config_path.exists() or not config_path.is_dir():
            _logger.error(
                f"AAS repository configuration path '{config_path}' not found or inaccessible."
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"AAS repository configuration path '{config_path}' not found.",
            )

        json_files = list(config_path.rglob("*.json"))

        if not json_files or len(json_files) == 0:
            _logger.info(
                f"No AAS repository configuration files found in folder '{config_path}'."
            )
            return

        for json_file in json_files:
            try:
                aas_server_configuration = ServerConfiguration.model_validate_json(
                    json_file.read_text()
                )
                self.repo_server_configurations.append(aas_server_configuration)
            except ValidationError as ve:
                _logger.error(
                    f"Invalid AAS repository connection file '{json_file}': {ve}"
                )

        _logger.debug(
            f"Found {len(self.repo_server_configurations)} AAS repository configuration files in folder '{config_path}'."
        )
