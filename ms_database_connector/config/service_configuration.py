import logging
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class ServiceConfiguration(BaseModel):
    """Runtime configuration for the microservice application.

    Contains settings for AAS connectivity, InfluxDB configuration, polling intervals,
    and API endpoints.

    Attributes:
        aas_id: Unique identifier of the Asset Administration Shell.
        polling_interval: Interval in seconds for polling data from message broker.
        external_url: External URL for server access (default: http://127.0.0.1).
        external_port: External port for server access (default: 3088).
        influx_db_version: InfluxDB version to use (1 or 2, default: 2).
        influx_db_server_config: Server connection details for InfluxDB.
        persist_db_mapping_file_changes: Whether to persist DB mapping updates to disk.
    """

    aas_id: str = Field(
        ..., alias="AasId", description="The ID of the AAS used by the microservice."
    )
    polling_interval: int = Field(
        default=5,
        alias="PollingInterval",
        description="Polling interval in seconds for retrieving values from the broker.",
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
    influx_db_version: int = Field(
        default=2,
        alias="InfluxDbVersion",
        description="The version of the Influx DB to use (1 or 2).",
    )
    influx_db_server_config: dict = Field(
        default={},
        alias="InfluxDbConfig",
        description="Configuration for the Influx DB server connection.",
    )
    persist_db_mapping_file_changes: bool = Field(
        default=True,
        alias="PersistDbMappingFileChanges",
        description=(
            "Whether DB mapping configuration updates should be persisted to "
            "db_mapping_configuration.json."
        ),
    )


def load_configuration(configuration_file: str) -> ServiceConfiguration:
    """Load and validate the service configuration from a JSON file.

    Reads the configuration file specified by the path parameter, validates it
    against the ServiceConfiguration schema, and returns the parsed object.

    Args:
        configuration_file: Absolute or relative path to the configuration JSON file.

    Returns:
        ServiceConfiguration: The validated configuration object.

    Raises:
        ValueError: If no configuration file path is provided.
        FileNotFoundError: If the configuration file does not exist.
        ValidationError: If the configuration is invalid or missing required fields.
    """
    if not configuration_file:
        raise ValueError("No configuration file provided.")

    config_file = Path(configuration_file)

    config_file = config_file.resolve()
    logger.info(f"Load configuration file '{config_file}'.")
    if not config_file.exists() or not config_file.is_file():
        logger.error(f"Configuration file '{config_file}' not found or inaccessible. ")
        raise FileNotFoundError(
            f"Configuration file '{config_file}' not found or inaccessible. "
        )

    config_string = config_file.read_text(encoding="utf-8")
    logger.debug(f"Configuration  file '{config_file}' found.")
    try:
        return ServiceConfiguration.model_validate_json(config_string)
    except ValidationError as ve:
        raise ValidationError(f"Invalid BaSyx server connection file: {ve}") from ve
