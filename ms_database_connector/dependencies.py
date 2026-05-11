"""Global dependency providers (DI) for the FastAPI application."""

from functools import lru_cache
import os

from ms_database_connector.config.service_configuration import (
    ServiceConfiguration,
    load_configuration,
)
from ms_database_connector.core.db_connection import initialize_db_connection
from ms_database_connector.services.influx_service import IInfluxClient
from ms_database_connector.utils.mapping_handler import MappingConfigurationHandler


@lru_cache(maxsize=1)
def get_service_configuration() -> ServiceConfiguration:
    """Load the runtime service configuration from environment.

    Uses a singleton cache to avoid repeated file parsing.
    """
    configuration_file = os.getenv("DBC_CONFIGURATION_FILE", "")
    return load_configuration(configuration_file)


@lru_cache(maxsize=1)
def get_influx_client() -> IInfluxClient | None:
    """Create and cache an InfluxDB client using current service configuration."""
    configuration = get_service_configuration()
    return initialize_db_connection(configuration)


def reconnect_influx_client() -> IInfluxClient | None:
    """Force a fresh InfluxDB client initialisation (used by POST /connect)."""
    get_influx_client.cache_clear()
    return get_influx_client()


@lru_cache(maxsize=1)
def get_mapping_configuration_service() -> MappingConfigurationHandler:
    """Create and cache the mapping configuration handler singleton."""
    return MappingConfigurationHandler()
