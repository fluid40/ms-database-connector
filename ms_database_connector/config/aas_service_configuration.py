from __future__ import annotations

import os
from yaml import safe_load  # type: ignore
from pathlib import Path

from pydantic import BaseModel, Field, SecretStr, AnyHttpUrl, model_validator
from pydantic_settings import BaseSettings


class AasInfraConfiguration(BaseModel):
    """Deprecated Config Model"""

    oauth_issuer: str = Field(
        ...,
        alias="OAuthIssuer",
        description="The URL of the OAuth issuer for authentication.",
    )
    oauth_client_id: str = Field(
        ...,
        alias="OAuthClientId",
        description="The client ID for OAuth authentication.",
    )
    oauth_client_secret: SecretStr = Field(
        ...,
        alias="OAuthClientSecret",
        description="The client secret for OAuth authentication.",
    )
    oauth_token_url: str = Field(
        ..., alias="OAuthTokenUrl", description="The URL for obtaining OAuth tokens."
    )


class KeycloakConfig(BaseSettings):
    issuer: AnyHttpUrl = Field(
        ...,
        description="Keycloak Realm Issuer URL",
    )
    client_id: str = Field(
        ...,
        description="Client ID for the Client Credentials Flow",
    )
    client_secret: SecretStr = Field(
        ...,
        description="Client Secret",
    )

    @property
    def token_endpoint(self) -> str:
        """Derives the token endpoint from the issuer URL."""
        return f"{str(self.issuer).rstrip('/')}/protocol/openid-connect/token"

    model_config = {"frozen": True}


class BaSyxConfig(BaseSettings):
    aas_registry_url: AnyHttpUrl = Field(..., description="AAS Registry URL")
    sm_registry_url: AnyHttpUrl = Field(..., description="Submodel Registry URL")
    aas_repository_url: AnyHttpUrl = Field(..., description="AAS Repository URL")
    sm_repository_url: AnyHttpUrl = Field(..., description="Submodel Repository URL")

    model_config = {"frozen": True}


class AasServiceConfig(BaseSettings):
    keycloak: KeycloakConfig
    basyx: BaSyxConfig

    model_config = {"frozen": True}

    @model_validator(mode="before")
    @classmethod
    def load_from_yaml(cls, values: dict) -> dict:
        """
        Loads the configuration from the YAML file,
        whose path is defined by the environment variable AAS_SERVICE_CONFIG_PATH.
        """
        config_path = os.getenv("AAS_SERVICE_CONFIG_PATH")

        if not config_path:
            raise ValueError("Environment variable AAS_SERVICE_CONFIG_PATH is not set.")

        path = Path(config_path)

        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with path.open("r", encoding="utf-8") as f:
            yaml_data = safe_load(f)

        # YAML data takes precedence, overwrite directly passed values
        yaml_data.update(values)
        return yaml_data
