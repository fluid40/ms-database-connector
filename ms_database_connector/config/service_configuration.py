from pydantic import BaseModel, Field

from ms_database_connector.config.server_configuration import ServerConfiguration

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
    influx_db_server_config: ServerConfiguration = Field(default_factory=ServerConfiguration, alias="InfluxDbServerConfig", description="Configuration for the Influx DB server connection.")