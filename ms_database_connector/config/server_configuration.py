from pydantic import BaseModel, Field


class ServerConfiguration(BaseModel):
    """Represents the HTTP server configuration.

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
