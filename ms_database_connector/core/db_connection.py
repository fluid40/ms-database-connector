import logging
import os

from ms_database_connector.config.service_configuration import ServiceConfiguration
from ms_database_connector.services import influx_v2_service
from ms_database_connector.services.influx_service import IInfluxClient

_logger = logging.getLogger(__name__)

def initialize_db_connection(configuration: ServiceConfiguration) -> IInfluxClient | None:
    """Initialize the database connection."""

    _logger.info("Get Influx DB password from environment variable 'RUNTIME_INFLUX_PW'")
    password = os.getenv("INFLUXDB_V2_TOKEN")
    if not password:
        _logger.warning("No Influx DB password provided in environment variable 'RUNTIME_INFLUX_PW'. Database interactions disabled.")
        return None
    
    db_version: int = configuration.influx_db_version
    client: IInfluxClient | None = None

    if db_version == 2:
        client = influx_v2_service.create_client(configuration.influx_db_server_config, password)
    # elif db_version == 1:
    #     client = influx_v1_service.create_client(configuration.influx_db_settings, password)
    else:
        _logger.error(f"Unsupported InfluxDB version '{db_version}'. Only version 1 is supported.")

    if not client:
        _logger.error("No InfluxDB client available. Database interactions disabled.")

    return client
