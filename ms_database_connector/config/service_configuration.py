import logging
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

class ServiceConfiguration(BaseModel):
    """Represents the runtime configuration for the application.

    :param BaseModel: Base model class for Pydantic
    """

    aas_id: str = Field(..., alias="AasId", description="The ID of the AAS used by the microservice.")
    polling_interval: int = Field(
        default=5, alias="PollingInterval", description="Polling interval in seconds for retrieving values from the broker."
    )
    external_url: str = Field(
        default="http://127.0.0.1",
        alias="ExternalUrl",
        description="The external URL for the server.",
    )
    external_port: str = Field(
        default="3088",
        alias="ExternalPort",
        description="The external port for the server.",
    )
    influx_db_version: int = Field(default=2, alias="InfluxDbVersion", description="The version of the Influx DB to use (1 or 2).")
    influx_db_server_config: dict = Field(default={}, alias="InfluxDbConfig", description="Configuration for the Influx DB server connection.")


def load_configuration(configuration_file: str) -> ServiceConfiguration:
    """Load the configuration from a file.
    TODO: make utility function for loading configuration files, as this is also needed in the AAS server.

    :param configuration_file: The path to the configuration file.
    :return: The loaded ServiceConfiguration object.
    """
    if not configuration_file:
        raise ValueError("No configuration file provided.")

    config_file = Path(configuration_file)

    config_file = config_file.resolve()
    logger.info(f"Load configuration file '{config_file}'.")
    if not config_file.exists() or not config_file.is_file():
        logger.error(f"Configuration file '{config_file}' not found or inaccessible. ")
        raise FileNotFoundError(f"Configuration file '{config_file}' not found or inaccessible. ")
    
    config_string = config_file.read_text(encoding="utf-8")
    logger.debug(f"Configuration  file '{config_file}' found.")
    try:
        return ServiceConfiguration.model_validate_json(config_string)
    except ValidationError as ve:
        raise ValidationError(f"Invalid BaSyx server connection file: {ve}") from ve