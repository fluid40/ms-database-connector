"""Global dependency providers (DI) for the FastAPI application."""

from functools import lru_cache
import os

from aas_http_client import SdkWrapper  # type: ignore[import-untyped]

from ms_database_connector.config.service_configuration import (
	ServiceConfiguration,
	load_configuration,
)
from ms_database_connector.core.db_connection import initialize_db_connection
from ms_database_connector.services.aas_registry_wrapper_factory import (
	create_aas_registry_wrapper,
)
from ms_database_connector.services.influx_service import IInfluxClient
from ms_database_connector.services.mapping_configuration_service import (
	MappingConfigurationService,
)


@lru_cache(maxsize=1)
def get_service_configuration() -> ServiceConfiguration:
	"""Load the runtime service configuration from environment.

	Uses a singleton cache to avoid repeated file parsing.
	"""
	configuration_file = os.getenv("DBC_CONFIGURATION_FILE", "")
	return load_configuration(configuration_file)


@lru_cache(maxsize=1)
def get_mapping_configuration_service() -> MappingConfigurationService:
	"""Create a singleton mapping configuration service."""
	mapping_file = os.getenv(
		"DBC_MAPPING_CONFIG_FILE", "configuration/mapping_configuration.json"
	)
	return MappingConfigurationService(mapping_file)


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
def get_aas_registry_wrapper() -> SdkWrapper:
	"""Create and cache an authenticated AAS registry wrapper."""
	return create_aas_registry_wrapper()