"""Global dependency providers (DI) for the FastAPI application."""

from functools import lru_cache
import os

from ms_database_connector.config.service_configuration import (
    ServiceConfiguration,
    load_configuration,
)
from ms_database_connector.core.db_connection import initialize_db_connection
from ms_database_connector.services.influx_service import IInfluxClient
from ms_database_connector.utils.mapping_handler import DbMappingHandler


@lru_cache(maxsize=1)
def get_service_configuration() -> ServiceConfiguration:
    """Load the runtime service configuration from environment.

    Uses a singleton cache to avoid repeated file parsing. The configuration file
    path is read from the DBC_CONFIGURATION_FILE environment variable.

    Returns:
        ServiceConfiguration: The loaded and parsed service configuration.

    Raises:
        Exception: If configuration file cannot be loaded or parsed.
    """
    configuration_file = os.getenv("DBC_CONFIGURATION_FILE", "")
    return load_configuration(configuration_file)


@lru_cache(maxsize=1)
def get_influx_client() -> IInfluxClient | None:
    """Create and cache an InfluxDB client using current service configuration.

    Initializes a singleton InfluxDB client based on the active service configuration.
    The client is cached to avoid repeated initialization.

    Returns:
        IInfluxClient | None: The initialized InfluxDB client instance, or None if
            initialization fails (e.g., missing credentials or invalid configuration).
    """
    configuration = get_service_configuration()
    return initialize_db_connection(configuration)


def reconnect_influx_client() -> IInfluxClient | None:
    """Force a fresh InfluxDB client initialization.

    Clears the cached client and initializes a new one. This is typically called
    when the user requests to reconnect to the InfluxDB server via the API.

    Returns:
        IInfluxClient | None: The newly initialized InfluxDB client instance,
            or None if initialization fails.
    """
    get_influx_client.cache_clear()
    return get_influx_client()


@lru_cache(maxsize=1)
def get_db_mapping_handler() -> DbMappingHandler:
    """Create and cache the mapping configuration handler singleton.

    Initializes and caches the mapping configuration handler based on the service
    configuration. This handler manages AIMC to InfluxDB field mappings.

    Returns:
        DbMappingHandler: The initialized and cached DB mapping configuration
            handler instance.

    Raises:
        Exception: If DB mapping configuration cannot be loaded or initialized.
    """
    configuration = get_service_configuration()
    mapping_handler = DbMappingHandler()
    mapping_handler._persist_db_mapping_file_changes = (
        configuration.persist_db_mapping_file_changes
    )
    return mapping_handler
