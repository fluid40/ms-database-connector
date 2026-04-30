# FastAPI app instance and startup
import logging
import os

import uvicorn

from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from ms_database_connector.core.server_handling import ServerHandler
from ms_database_connector.dependencies import (
	get_aas_registry_wrapper,
    get_influx_client,
    get_mapping_configuration_service,
    get_service_configuration,
)
from ms_database_connector.routers.endpoints import router as mapping_router
from ms_database_connector.utils.configuration_handling import ServerConfigurationsHandler
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
        server_handler = ServerHandler()
        server_configurations = ServerConfigurationsHandler()
        server_handler.connect_to_aas_registry(server_configurations.aas_registry_configuration)
        _logger.info("AAS registry wrapper initialized during startup.")
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

if __name__ == "__main__" and os.getenv("RUN_SERVER", "1") == "1":
    """Run the FastAPI application."""
    initialize_logging()
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", "3088"))
    uvicorn.run(app, host=host, port=port, log_config=None)