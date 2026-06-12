# FastAPI app instance and startup
import asyncio
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
    AppRuntimeDeps,
    build_app_runtime_deps,
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


def _setup_service_config(
    startup_state: dict,
    runtime_deps: AppRuntimeDeps,
) -> None:
    """Load and validate service configuration.

    Args:
        startup_state: The startup state dictionary to update on success.
        runtime_deps: Runtime dependency composition object.

    Raises:
        Exception: If service configuration fails to load.
    """
    with _track_startup(startup_state, "service_configuration", "config_loaded"):
        _logger.info("Loading service configuration.")
        runtime_deps.config_provider()


def _setup_mapping_service(
    startup_state: dict,
    runtime_deps: AppRuntimeDeps,
) -> None:
    """Initialize mapping configuration service singleton.

    Args:
        startup_state: The startup state dictionary to update on success.
        runtime_deps: Runtime dependency composition object.

    Raises:
        Exception: If mapping configuration service initialization fails.
    """
    with _track_startup(startup_state, "mapping_configuration", "mapping_initialized"):
        _logger.info("Initializing mapping configuration service.")
        runtime_deps.mapping_handler_provider()


def _setup_influx_connection(
    startup_state: dict,
    runtime_deps: AppRuntimeDeps,
) -> None:
    """Establish InfluxDB connection.

    Args:
        startup_state: The startup state dictionary to update on success.
        runtime_deps: Runtime dependency composition object.

    Raises:
        RuntimeError: If InfluxDB connection cannot be established.
    """
    with _track_startup(startup_state, "influxdb", "influx_connected"):
        _logger.info("Establishing InfluxDB connection.")
        client = runtime_deps.influx_client_provider()
        if not client:
            raise RuntimeError(
                "InfluxDB connection failed. Set INFLUXDB_V2_TOKEN and ensure server reachability."
            )
        _logger.info("InfluxDB connection established.")


def _setup_aas_connection(
    startup_state: dict,
    runtime_deps: AppRuntimeDeps,
    server_config_factory=ServerConfigurationsHandler,
) -> ServerHandler:
    """Initialize AAS server connections.

    Args:
        startup_state: The startup state dictionary to update on success.
        runtime_deps: Runtime dependency composition object.
        server_config_factory: Callable that returns a
            :class:`ServerConfigurationsHandler` instance. Defaults to
            :class:`ServerConfigurationsHandler`. Pass a fake in tests.

    Returns:
        ServerHandler: The initialized server handler instance.

    Raises:
        Exception: If AAS server connection initialization fails.
    """
    with _track_startup(startup_state, "aas_client", "registry_connected"):
        _logger.info("Initializing AAS server connections.")
        server_handler = runtime_deps.server_handler_factory()
        server_configurations = server_config_factory()
        server_handler.connect_to_server(server_configurations)
        _logger.info("AAS server connections established.")
        return server_handler
    return None


def _preload_aas_metadata(
    app: FastAPI,
    server_handler: ServerHandler,
    startup_state: dict,
    runtime_deps: AppRuntimeDeps,
    get_shell=get_shell_via_registry,
    get_aimc_sm=get_aimc_submodel,
    extract_refs=extract_target_references_from_aimc,
) -> None:
    """Preload AAS and AIMC metadata for early validation.

    Args:
        app: The FastAPI application instance to store preloaded references.
        server_handler: The initialized server handler for AAS communication.
        startup_state: The startup state dictionary to update on success.
        runtime_deps: Runtime dependency composition object.
        get_shell: Callable ``(server_handler, aas_id) -> shell``. Defaults to
            :func:`get_shell_via_registry`. Pass a fake in tests.
        get_aimc_sm: Callable ``(server_handler, shell) -> submodel``. Defaults
            to :func:`get_aimc_submodel`. Pass a fake in tests.
        extract_refs: Callable ``(submodel) -> target_references``. Defaults to
            :func:`extract_target_references_from_aimc`. Pass a fake in tests.

    Raises:
        Exception: If AAS or AIMC metadata cannot be retrieved.
    """
    with _track_startup(startup_state, "aas_retrieval", "aimc_loaded"):
        _logger.info("Loading AAS and AIMC metadata.")
        aas_id = runtime_deps.config_provider().aas_id
        shell = get_shell(server_handler, aas_id)
        aimc_sm = get_aimc_sm(server_handler, shell)
        target_references = extract_refs(aimc_sm)
        app.state.target_references = target_references
        _logger.info("AAS and AIMC metadata loaded successfully.")


class PollingWorker:
    """Background worker that polls AAS submodel elements and writes values to InfluxDB.

    Uses the polling_interval from the service configuration to schedule
    periodic data collection. The worker holds references to the FastAPI app,
    AAS server handler, and the InfluxDB client established during startup.

    Args:
        app: The FastAPI application instance (holds target references in state).
        server_handler: The connected AAS server handler.
        polling_interval: Interval in seconds between polling cycles.
    """

    def __init__(
        self,
        app: FastAPI,
        server_handler: ServerHandler,
        polling_interval: int,
        runtime_deps: AppRuntimeDeps,
    ) -> None:
        self._app = app
        self._server_handler = server_handler
        self._polling_interval = polling_interval
        self._runtime_deps = runtime_deps
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        """Schedule the polling loop as an asyncio background task."""
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="polling-worker")
        _logger.info("Polling worker started (interval=%ds).", self._polling_interval)

    async def stop(self) -> None:
        """Signal the polling loop to stop and await its completion."""
        _logger.info("Stopping polling worker.")
        self._stop_event.set()
        if self._task is not None:
            await asyncio.wait([self._task], timeout=self._polling_interval + 5)
            self._task = None

    async def _run(self) -> None:
        """Main polling loop.

        On each cycle the worker uses the AAS server handler and InfluxDB
        client established during startup. AAS and AIMC metadata are preloaded
        once at startup via _preload_aas_metadata and are not re-fetched here.
        """
        while not self._stop_event.is_set():
            try:
                await self._poll_once()
            except Exception:
                _logger.exception("Error during polling cycle.")
            try:
                await asyncio.wait_for(
                    asyncio.shield(asyncio.ensure_future(self._stop_event.wait())),
                    timeout=self._polling_interval,
                )
            except asyncio.TimeoutError:
                pass  # normal – interval elapsed, continue loop

    async def _poll_once(self) -> None:
        """Execute a single polling cycle.

        Uses the AAS server handler and InfluxDB client established during
        startup to collect and persist SME values. Target SME references are
        retrieved from the app state.
        """
        _logger.debug("Polling cycle started.")

        influx_client = self._runtime_deps.influx_client_provider()
        if influx_client is None:
            _logger.warning("InfluxDB client unavailable – skipping cycle.")
            return

        target_references = getattr(self._app.state, "target_references", [])
        if not target_references:
            _logger.warning("No target references available – skipping cycle.")
            return

        db_mapping = self._runtime_deps.mapping_handler_provider().db_mapping
        if db_mapping is None:
            _logger.warning("No DB mapping configuration available – skipping cycle.")
            return

        mapper = self._runtime_deps.mapper_factory(
            server_handler=self._server_handler,
            db_mapping=db_mapping,
            target_references=target_references,
        )

        try:
            influx_points = mapper.map_smes_to_influx()
        except Exception:
            _logger.exception("Failed to map SMEs to InfluxDB points.")
            return

        for measurement_name, points in influx_points.items():
            for point in points:
                success = influx_client.write_data(
                    fields=point.fields,
                    measurement=point.measurement,
                    tags=point.tags,
                    time=point.timestamp,
                )
                if not success:
                    _logger.error(
                        "Failed to write point for measurement '%s'.", measurement_name
                    )

        _logger.debug(
            "Polling cycle completed: %d measurement(s) written.", len(influx_points)
        )


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
    app.state.runtime_deps = build_app_runtime_deps()
    runtime_deps: AppRuntimeDeps = app.state.runtime_deps

    try:
        _setup_service_config(app.state.startup, runtime_deps)
        _setup_mapping_service(app.state.startup, runtime_deps)
        _setup_influx_connection(app.state.startup, runtime_deps)
        server_handler = _setup_aas_connection(app.state.startup, runtime_deps)
        _preload_aas_metadata(app, server_handler, app.state.startup, runtime_deps)
    except Exception:
        _logger.exception("Startup initialization failed.")
        raise

    polling_interval = runtime_deps.config_provider().polling_interval
    worker = PollingWorker(app, server_handler, polling_interval, runtime_deps)
    worker.start()

    yield

    await worker.stop()
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
    port = int(os.getenv("APP_PORT", "3090"))
    uvicorn.run(app, host=host, port=port, log_config=None)
