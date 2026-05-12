# FastAPI app instance and startup
import logging
import os

from basyx.aas import model
import uvicorn

from fastapi import FastAPI
from fastapi.concurrency import asynccontextmanager
from ms_database_connector.services.aas_infrastructure_service import (
    get_shell_via_registry,
)
from ms_database_connector.core.server_handling import ServerHandler
from ms_database_connector.core.influx_mapping import (
    get_aimc_submodel,
    extract_target_references_from_aimc,
)
from ms_database_connector.dependencies import (
    get_influx_client,
    get_mapping_configuration_service,
    get_service_configuration,
)
from ms_database_connector.routers.endpoints import router as mapping_router
from ms_database_connector.utils.configuration_handling import (
    ServerConfigurationsHandler,
)
from ms_database_connector.utils.logging_handler import initialize_logging

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan function for the FastAPI application, handling startup and shutdown events."""
    _logger.info("Starting up the microservice database connector.")

    app.state.startup = {
        "config_loaded": False,
        "mapping_initialized": False,
        "registry_connected": False,
        "influx_connected": False,
        "aimc_loaded": False,
        "degraded": False,
        "errors": [],
    }

    try:
        _logger.info("Loading service configuration.")
        _ = get_service_configuration()
        app.state.startup["config_loaded"] = True
    except Exception as e:
        _logger.exception("Failed to load service configuration: %s", e)
        app.state.startup["errors"].append(f"service_configuration: {e}")
        raise

    # Initialize mapping service singleton (required).
    try:
        _ = get_mapping_configuration_service()
        app.state.startup["mapping_initialized"] = True
    except Exception as e:
        _logger.exception("Failed to initialize mapping configuration service: %s", e)
        app.state.startup["errors"].append(f"mapping_configuration: {e}")
        raise

    # Attempt InfluxDB connection at startup (non-fatal)
    try:
        client = get_influx_client()
        if client:
            _logger.info("InfluxDB connection established during startup.")
            app.state.startup["influx_connected"] = True
        else:
            _logger.warning(
                "InfluxDB connection not established at startup. "
                "Use POST /connect to connect manually."
            )
            app.state.startup["degraded"] = True
            app.state.startup["errors"].append("influxdb: not connected")
    except Exception as e:
        _logger.warning("Could not establish InfluxDB connection at startup: %s", e)
        app.state.startup["degraded"] = True
        app.state.startup["errors"].append(f"influxdb: {e}")

    # AAS connectivity is required for this service.
    try:
        server_handler = ServerHandler()
        server_configurations = ServerConfigurationsHandler()

        server_handler.connect_to_server(server_configurations)
        _logger.info("Connection to AAS servers established during startup.")
        app.state.startup["registry_connected"] = True
    except Exception as e:
        _logger.exception("Could not initialize AAS client: %s", e)
        app.state.startup["errors"].append(f"aas_client: {e}")
        raise

    # Preload AAS and AIMC metadata for early validation.
    try:
        aas_id: str = get_service_configuration().aas_id
        shell: model.AssetAdministrationShell = get_shell_via_registry(
            server_handler, aas_id
        )
        aimc_sm: model.Submodel = get_aimc_submodel(server_handler, shell)
        extract_target_references_from_aimc(aimc_sm)
        _logger.info("AAS and submodels retrieved during startup.")
        app.state.startup["aimc_loaded"] = True
    except Exception as e:
        _logger.exception("Could not retrieve AAS and submodels at startup: %s", e)
        app.state.startup["errors"].append(f"aas_retrieval: {e}")
        raise

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
