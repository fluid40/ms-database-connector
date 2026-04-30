# FastAPI app instance and startup
import logging
import os
from functools import lru_cache
from typing_extensions import Annotated

import uvicorn

from fastapi import Depends, FastAPI
from fastapi.concurrency import asynccontextmanager
from ms_database_connector.config.aas_service_configuration import get_config, AasServiceConfig
from ms_database_connector.core.auth_service import AuthService
from ms_database_connector.core.authenticated_aas_client import AASClient
from ms_database_connector.dependencies import (
    get_influx_client,
    get_mapping_configuration_service,
    get_service_configuration,
)
from ms_database_connector.routers.mapping import router as mapping_router
from ms_database_connector.utils.logging_handler import initialize_logging

_logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan function for the FastAPI application, handling startup and shutdown events."""
    _logger.info("Starting up the microservice database connector.")
    
    try:
        _logger.info("Loading service configuration.")
        _ = get_service_configuration()
    except Exception as e:
        _logger.exception("Failed to load service configuration: %s", e)
        raise e

    # Initialise mapping service singleton.
    _ = get_mapping_configuration_service()

    # Attempt InfluxDB connection at startup (non-fatal)
    try:
        client = get_influx_client()
        if client:
            _logger.info("InfluxDB connection established during startup.")
        else:
            _logger.warning(
                "InfluxDB connection not established at startup. "
                "Use POST /connect to connect manually."
            )
    except Exception as e:
        _logger.warning("Could not establish InfluxDB connection at startup: %s", e)

    # AAS client (best-effort)
    try:
        aas_client: AASClient = get_aas_client() # To Do, move to DI
    except Exception as e:
        _logger.warning("Could not initialise AAS client: %s", e)

    yield
    
    _logger.info("Shutting down the microservice database connector.")

app = FastAPI(
    title="Microservice Database Connector",
    description="Fluid4.0 Runtime REST API",
    version="v1",
    lifespan=lifespan,
)

app.include_router(mapping_router)

# ------------------------------------------------------------------ #
# Dependency Injection
# ------------------------------------------------------------------ #
@lru_cache(maxsize=1)
def get_auth_service(
    config: Annotated[AasServiceConfig, Depends(get_config)],
) -> AuthService:
    return AuthService(config.keycloak)

@lru_cache(maxsize=1)
def get_aas_client(
    config: Annotated[AasServiceConfig, Depends(get_config)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AASClient:
    return AASClient(config.basyx, auth_service)


@app.get("/aas/shells")
def list_shells(
    client: Annotated[AASClient, Depends(get_aas_client)],
) -> dict:
    """Gibt alle AAS aus dem AAS Repository zurück."""
    return client.get_all_shells()


@app.get("/aas/registry")
def list_aas_descriptors(
    client: Annotated[AASClient, Depends(get_aas_client)],
) -> dict:
    """Gibt alle Deskriptoren aus der AAS Registry zurück."""
    return client.get_all_aas_descriptors()


if __name__ == "__main__" and os.getenv("RUN_SERVER", "1") == "1":
    """Run the FastAPI application."""
    initialize_logging()
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "3088"))
    uvicorn.run(app, host=host, port=port, log_config=None)