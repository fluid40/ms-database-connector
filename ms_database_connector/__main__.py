# FastAPI app instance and startup
import logging
import os

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


def _init_startup_state() -> dict:
    """Initialize application startup state tracking.

    Returns:
        dict: A dictionary with initialization status flags and error tracking.
    """
    return {
        "config_loaded": False,
        "mapping_initialized": False,
        "registry_connected": False,
        "influx_connected": False,
        "aimc_loaded": False,
        "errors": [],
    }


def _track_startup(state: dict, key: str, flag: str):
    """Context manager helper for tracking initialization steps.

    Args:
        state: The startup state dictionary to track initialization steps.
        key: The key representing the initialization step.
        flag: The flag to set in the startup state upon successful completion.

    Returns:
        StartupTracker: A context manager for tracking the initialization step.
    """

    class StartupTracker:
        def __init__(self, state, key, flag):
            self.state = state
            self.key = key
            self.flag = flag or key

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type is None:
                self.state[self.flag] = True
            else:
                self.state["errors"].append(f"{self.key}: {exc_val}")
            return False

    return StartupTracker(state, key, flag)


def _setup_service_config(startup_state: dict) -> None:
    """Load and validate service configuration.

    Args:
        startup_state: The startup state dictionary to update on success.

    Raises:
        Exception: If service configuration fails to load.
    """
    with _track_startup(startup_state, "service_configuration", "config_loaded"):
        _logger.info("Loading service configuration.")
        get_service_configuration()


def _setup_mapping_service(startup_state: dict) -> None:
    """Initialize mapping configuration service singleton.

    Args:
        startup_state: The startup state dictionary to update on success.

    Raises:
        Exception: If mapping configuration service initialization fails.
    """
    with _track_startup(startup_state, "mapping_configuration", "mapping_initialized"):
        _logger.info("Initializing mapping configuration service.")
        get_mapping_configuration_service()


def _setup_influx_connection(startup_state: dict) -> None:
    """Establish InfluxDB connection.

    Args:
        startup_state: The startup state dictionary to update on success.

    Raises:
        RuntimeError: If InfluxDB connection cannot be established.
    """
    with _track_startup(startup_state, "influxdb", "influx_connected"):
        _logger.info("Establishing InfluxDB connection.")
        client = get_influx_client()
        if not client:
            raise RuntimeError(
                "InfluxDB connection failed. Set INFLUXDB_V2_TOKEN and ensure server reachability."
            )
        _logger.info("InfluxDB connection established.")


def _setup_aas_connection(startup_state: dict) -> ServerHandler:
    """Initialize AAS server connections.

    Args:
        startup_state: The startup state dictionary to update on success.

    Returns:
        ServerHandler: The initialized server handler instance.

    Raises:
        Exception: If AAS server connection initialization fails.
    """
    with _track_startup(startup_state, "aas_client", "registry_connected"):
        _logger.info("Initializing AAS server connections.")
        server_handler = ServerHandler()
        server_configurations = ServerConfigurationsHandler()
        server_handler.connect_to_server(server_configurations)
        _logger.info("AAS server connections established.")
        return server_handler
    return None


def _preload_aas_metadata(server_handler: ServerHandler, startup_state: dict) -> None:
    """Preload AAS and AIMC metadata for early validation.

    Args:
        server_handler: The initialized server handler for AAS communication.
        startup_state: The startup state dictionary to update on success.

    Raises:
        Exception: If AAS or AIMC metadata cannot be retrieved.
    """
    with _track_startup(startup_state, "aas_retrieval", "aimc_loaded"):
        _logger.info("Loading AAS and AIMC metadata.")
        aas_id = get_service_configuration().aas_id
        shell = get_shell_via_registry(server_handler, aas_id)
        aimc_sm = get_aimc_submodel(server_handler, shell)
        extract_target_references_from_aimc(aimc_sm)
        _logger.info("AAS and AIMC metadata loaded successfully.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan function for the FastAPI application.

    Handles startup initialization and shutdown cleanup events. Initializes all
    required services and validates connectivity before the application starts
    serving requests.

    Args:
        app: The FastAPI application instance.

    Yields:
        None: Context is yielded after startup, allowing the app to run.

    Raises:
        Exception: If any required initialization step fails.
    """
    _logger.info("Starting up the microservice database connector.")
    app.state.startup = _init_startup_state()

    try:
        _setup_service_config(app.state.startup)
        _setup_mapping_service(app.state.startup)
        _setup_influx_connection(app.state.startup)
        server_handler = _setup_aas_connection(app.state.startup)
        _preload_aas_metadata(server_handler, app.state.startup)
    except Exception:
        _logger.exception("Startup initialization failed.")
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
