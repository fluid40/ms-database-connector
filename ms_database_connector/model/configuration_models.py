"""Module defining the configuration model class."""

import logging
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

class AasServerConfiguration(BaseModel):
    """Represents the AAS server configuration.

    :param BaseModel: Base model class for Pydantic
    """

    secret_var_name: str = Field(
        default="",
        alias="SecretVarName",
        description="The name of the environment variable that contains the AAS authentication secret.",
    )
    server_configuration: dict = Field(
        default={},
        alias="ServerConfiguration",
        description="The configuration parameters for connecting to the AAS server.",
    )

class ServiceConfiguration(BaseModel):
    """Represents the service configuration.

    :param BaseModel: Base model class for Pydantic
    """

    aimc_submodel_id: str = Field(
        default="",
        alias="AimcSubmodelId",
        description="The identifier of the AIMC submodel.",
    )
    dynamic_submodel_ids: list[str] = Field(
        default_factory=list,
        alias="DynamicSubmodelIds",
        description="A list of identifiers for dynamic submodels.",
    )

def load_configuration_file(config_file: Path) -> ServiceConfiguration | None:
    """Load the runtime configuration from a JSON file.

    :param config_file_path: Path to the configuration file
    :return: ServiceConfiguration object if successful, None otherwise
    """
    if config_file is None:
        logger.error("No configuration file provided.")
        return None

    config_file = config_file.resolve()
    logger.info(f"Load configuration file '{config_file}'.")

    if not config_file.exists() or not config_file.is_file():
        logger.error(f"Configuration file '{config_file}' not found or inaccessible. ")
        return None

    config_string = config_file.read_text(encoding="utf-8")
    logger.debug(f"Configuration  file '{config_file}' found.")

    try:
        return ServiceConfiguration.model_validate_json(config_string)
    except ValidationError as ve:
        logger.error(f"Invalid BaSyx server connection file: {ve}")
        return None