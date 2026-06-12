import logging
import os

from aas_http_client import AasHttpClient, SdkWrapper, sdk_wrapper
from fastapi import HTTPException, status

from ms_database_connector.config.server_configuration import ServerConfiguration
from ms_database_connector.config.server_config_loader import ServerConfigLoader

_logger = logging.getLogger(__name__)


class ServerHandler:
    """Manage connections to AAS infrastructure endpoints.

    The handler initializes and caches clients/wrappers for:
    - AAS registry
    - Submodel registry
    - Repository AAS servers

    Instances are intended to be reused so created wrappers can be served from
    an in-memory cache.
    """

    aas_registry_client: AasHttpClient
    sm_registry_client: AasHttpClient
    aas_server_wrappers: dict[str, SdkWrapper]

    def __init__(self):
        """Initialize an empty connection state.

        The created instance starts without connected registry clients and with
        an empty repository-wrapper cache.
        """
        self.aas_registry_client = None
        self.sm_registry_client = None
        self.aas_server_wrappers = {}

    def connect_to_server(self, configuration_loader: ServerConfigLoader):
        """Initialize all configured registry clients and repository wrappers.

        Args:
            configuration_loader: Provider for AAS registry, Submodel
                registry, and repository server configurations.

        Raises:
            HTTPException: Propagated if a required registry client cannot be
                established.
        """
        self.connect_to_aas_registry(configuration_loader.aas_registry_configuration)
        self.connect_to_sm_registry(configuration_loader.sm_registry_configuration)
        self.connect_to_repo_server(configuration_loader.repo_server_configurations)

    def connect_to_aas_registry(
        self, configuration: ServerConfiguration
    ) -> AasHttpClient:
        """Create and store the AAS registry client.

        This method updates ``self.aas_registry_client`` when the connection
        succeeds.

        Args:
            configuration: Server configuration for the AAS registry.

        Raises:
            HTTPException: If the connection to the AAS registry cannot be
                established.
        """
        _logger.info("Create AAS registry client.")
        registry_wrapper = connect_to_aas_server(
            configuration.server_configuration, configuration.secret_var_name
        )

        if registry_wrapper is None:
            _logger.error("Failed to create AAS registry client.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not connect to AAS Registry. Client not created.",
            )

        self.aas_registry_client = registry_wrapper.get_client()

    def connect_to_sm_registry(
        self, configuration: ServerConfiguration
    ) -> AasHttpClient:
        """Create and store the Submodel registry client.

        This method updates ``self.sm_registry_client`` when the connection
        succeeds.

        Args:
            configuration: Server configuration for the Submodel registry.

        Raises:
            HTTPException: If the connection to the Submodel registry cannot
                be established.
        """
        _logger.info("Create Submodel registry client.")
        registry_wrapper = connect_to_aas_server(
            configuration.server_configuration, configuration.secret_var_name
        )

        if registry_wrapper is None:
            _logger.error("Failed to create Submodel registry client.")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not connect to Submodel Registry. Client not created.",
            )

        self.sm_registry_client = registry_wrapper.get_client()

    def connect_to_repo_server(self, configurations: list[ServerConfiguration]):
        """Create and cache wrappers for configured repository servers.

        Existing entries are preserved. New wrappers are cached by their base
        URL and duplicates are ignored.

        Args:
            configurations: List of server configurations for repository servers.
        """
        _logger.info(
            f"Create AAS server wrappers for {len(configurations)} configured AAS servers."
        )

        for configuration in configurations:
            wrapper = connect_to_aas_server(
                configuration.server_configuration, configuration.secret_var_name
            )

            if wrapper is not None and wrapper.base_url not in self.aas_server_wrappers:
                _logger.info(
                    f"AAS server wrapper for base URL '{wrapper.base_url}' created."
                )
                self.aas_server_wrappers[wrapper.base_url] = wrapper

    def get_or_create_repo_wrapper(self, base_url: str) -> SdkWrapper:
        """Return a cached wrapper or create one for a repository base URL.

        If no cached wrapper exists, a new connection attempt is made using the
        provided URL.

        Args:
            base_url: Base URL of the AAS server.

        Returns:
            SdkWrapper: A cached or newly created AAS server wrapper.

        Raises:
            HTTPException: If the wrapper cannot be created.
        """
        if base_url in self.aas_server_wrappers:
            _logger.debug(
                f"AAS server wrapper for base URL '{base_url}' found in cache."
            )
            return self.aas_server_wrappers[base_url]

        _logger.info(
            f"AAS server wrapper for base URL '{base_url}' not found in cache. Create new wrapper."
        )

        wrapper = connect_to_aas_server({"BaseUrl": base_url, "EncodedIds": False}, "")

        if wrapper is not None:
            _logger.info(f"AAS server wrapper for base URL '{base_url}' created.")
            self.aas_server_wrappers[base_url] = wrapper
            return wrapper

        _logger.error(f"Could not create AAS server wrapper for base URL '{base_url}'.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not create AAS server wrapper for base URL '{base_url}'.",
        )


def connect_to_aas_server(
    server_configuration: dict, secret_var_name: str
) -> SdkWrapper | None:
    """Create an AAS SDK wrapper from server configuration and secret.

    The function forces ``EncodedIds`` to ``False`` before wrapper creation to
    ensure a consistent client setup.

    Args:
        server_configuration: AAS server configuration dictionary.
        secret_var_name: Name of the environment variable containing the AAS
            authentication secret.

    Returns:
        SdkWrapper | None: Created server wrapper, or ``None`` if wrapper
            creation fails or returns no wrapper.
    """
    _logger.info("Connect to AAS server.")

    _logger.debug(
        f"Get AAS server secret from environment variable '{secret_var_name}'."
    )
    server_secret: str = os.getenv(secret_var_name, "")

    # Ensure EncodedIds is set to False
    server_configuration["EncodedIds"] = False

    try:
        wrapper: SdkWrapper | None = sdk_wrapper.create_by_dict(
            server_configuration, server_secret, server_secret, server_secret
        )
    except Exception as ve:
        _logger.error(f"Could not create AAS server wrapper: {ve}")
        return None

    if wrapper is None:
        _logger.error("Could not connect to AAS server. Client not created.")
        return None

    return wrapper
