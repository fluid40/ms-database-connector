"""REST API endpoints for the database connector.

Endpoints
---------
GET  /health                 – readiness / availability check
POST /connect                – (re-)initialise the InfluxDB connection
GET  /db-mapping             – return current SME-DB mapping
POST /db-mapping             – validate and overwrite SME-DB mapping
PUT  /initialize-db-mapping  – store a null-template mapping
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from ms_database_connector.config.db_mapping import (
    DbMapping,
    MappingTargetType,
)
from ms_database_connector.config.service_configuration import ServiceConfiguration
from ms_database_connector.dependencies import (
    get_influx_client,
    get_mapping_configuration_service,
    get_service_configuration,
    reconnect_influx_client,
)
from ms_database_connector.services.influx_service import IInfluxClient
from ms_database_connector.utils.mapping_handler import DbMappingHandler

_logger = logging.getLogger(__name__)

router = APIRouter()


# ------------------------------------------------------------------ #
# Endpoint: GET /health
# ------------------------------------------------------------------ #


@router.get("/health")
def health_check(
    request: Request,
    service_config: Annotated[ServiceConfiguration, Depends(get_service_configuration)],
    mapping_service: Annotated[
        DbMappingHandler, Depends(get_mapping_configuration_service)
    ],
    influx_client: Annotated[IInfluxClient | None, Depends(get_influx_client)],
) -> dict:
    """Readiness check: verifies service health and connectivity.

    Performs a comprehensive health check including:
    - Service configuration loaded
    - Mapping service initialized
    - AAS registry and AIMC metadata loaded (if available at startup)
    - InfluxDB connectivity and ping

    Returns:
        dict: A status dictionary containing:
            - status: Always "ok" if endpoint responds
            - checks: Dict with boolean checks for each component
            - errors: List of error messages encountered during startup
    """
    influxdb_reachable = False
    if influx_client is not None:
        try:
            influxdb_reachable = influx_client.ping()
        except Exception as exc:
            _logger.warning("InfluxDB ping failed: %s", exc)

    checks: dict = {
        "config_loaded": service_config is not None,
        "mapping_initialized": mapping_service.is_initialized,
        "influxdb_reachable": influxdb_reachable,
    }

    startup_state = getattr(request.app.state, "startup", None)
    # Prefer runtime startup state from FastAPI lifespan when available.
    # During tests or isolated router usage this may be missing.
    if startup_state is None:
        checks["errors"] = (
            []
            if checks["influxdb_reachable"]
            else ["influxdb: ping failed after successful startup"]
        )
    else:
        checks["registry_connected"] = bool(startup_state.get("registry_connected"))
        checks["aimc_loaded"] = bool(startup_state.get("aimc_loaded"))
        checks["errors"] = startup_state.get("errors", [])

    _logger.debug("Health check result: %s", checks)
    return {"status": "ok", "checks": checks}


# ------------------------------------------------------------------ #
# Endpoint: POST /connect
# ------------------------------------------------------------------ #


@router.post("/connect")
def connect(
    service_config: Annotated[ServiceConfiguration, Depends(get_service_configuration)],
) -> dict:
    """Reinitialize the InfluxDB connection.

    Forces a fresh InfluxDB client initialization using the current service
    configuration. This is useful after updating credentials or recovering
    from a connection loss.

    Args:
        service_config: The current service configuration (dependency injection).

    Returns:
        dict: Connection status with keys:
            - status: Always "connected" on success
            - bucket: The InfluxDB bucket name the client is configured to use

    Raises:
        HTTPException: Status 500 if connection initialization fails or InfluxDB
            is not reachable.
    """
    _logger.info("Received request to (re-)initialise InfluxDB connection.")
    try:
        _ = service_config
        client = reconnect_influx_client()
    except Exception as exc:
        _logger.error("Failed to connect to InfluxDB: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to InfluxDB: {exc}",
        ) from exc

    if client is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "InfluxDB connection could not be established. "
                "Check that INFLUXDB_V2_TOKEN is set and the server is reachable."
            ),
        )

    _logger.info("InfluxDB connection established successfully.")

    bucket: str = getattr(client, "bucket", "unknown")
    return {"status": "connected", "bucket": bucket}


# ------------------------------------------------------------------ #
# Endpoint: GET /db-mapping
# ------------------------------------------------------------------ #


@router.get("/db-mapping")
def get_db_mapping(
    mapping_service: Annotated[
        DbMappingHandler, Depends(get_mapping_configuration_service)
    ],
) -> dict:
    """Retrieve the current AIMC-to-InfluxDB field mapping configuration.

    Args:
        mapping_service: The mapping configuration handler (dependency injection).

    Returns:
        dict: The current mapping configuration, or an empty dict if no mapping
            has been initialized yet.
    """
    raw = mapping_service.get_raw()
    if raw is None:
        return {}
    return raw


# ------------------------------------------------------------------ #
# Endpoint: POST /db-mapping
# ------------------------------------------------------------------ #


@router.post("/db-mapping")
def set_db_mapping(
    body: dict,
    mapping_service: Annotated[
        DbMappingHandler, Depends(get_mapping_configuration_service)
    ],
) -> dict:
    """Validate and store the AIMC-to-InfluxDB field mapping configuration.

    Validates the mapping structure and persists it to storage. All target
    types must be either 'field', 'tag', or 'timestamp'.

    Args:
        body: The mapping configuration dict with structure:
            {"measurement_name": {"path": "field|tag|timestamp"}}
        mapping_service: The mapping configuration handler (dependency injection).

    Returns:
        dict: Status response with key:
            - status: "mapping_updated" on success

    Raises:
        HTTPException: Status 400 if validation fails or structure doesn't match
            initialized template. Status 500 if persistence fails.

    Note:
        Validation rules:
        - All target values must be one of: "field", "tag", "timestamp".
        - At most one "timestamp" per measurement.
        - Each measurement must have at least one mapping entry.
        - Posted mapping must match existing measurement structure exactly.
    """
    try:
        mapping = DbMapping.model_validate(body)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # If a template already exists, enforce completeness by requiring the exact
    # measurement/path structure in the posted mapping.
    existing = mapping_service.get_raw() or {}
    if existing:
        existing_measurements = set(existing.keys())
        posted_measurements = set(mapping.root.keys())
        if posted_measurements != existing_measurements:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Posted mapping does not match initialized measurements. "
                    f"Expected: {sorted(existing_measurements)}, "
                    f"got: {sorted(posted_measurements)}."
                ),
            )

        for measurement_name, expected_mapping in existing.items():
            expected_paths = set(expected_mapping.keys())
            posted_paths = set(mapping.root[measurement_name].root.keys())
            if posted_paths != expected_paths:
                missing = sorted(expected_paths - posted_paths)
                extra = sorted(posted_paths - expected_paths)
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Measurement '{measurement_name}' must provide a complete "
                        "mapping. "
                        f"Missing paths: {missing}. Extra paths: {extra}."
                    ),
                )

    for measurement_name, measurement_mapping in mapping.root.items():
        if not measurement_mapping.root:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Measurement '{measurement_name}' must contain at least one "
                    "mapping entry."
                ),
            )

    if not mapping_service.update_db_mapping(mapping):
        raise HTTPException(
            status_code=500,
            detail="Failed to persist mapping.",
        )

    _logger.info("Mapping configuration updated via POST /db-mapping.")
    return {"status": "mapping_updated"}


# ------------------------------------------------------------------ #
# Endpoint: PUT /initialize-db-mapping
# ------------------------------------------------------------------ #

_VALID_TARGET_TYPES = {t.value for t in MappingTargetType} | {None}


@router.put("/initialize-db-mapping")
def initialize_db_mapping(
    body: dict,
    mapping_service: Annotated[
        DbMappingHandler, Depends(get_mapping_configuration_service)
    ],
) -> dict:
    """Create a mapping template with uninitialized (null) values.

    Initializes the mapping structure based on detected AIMC measurements and
    paths, allowing gradual completion via POST /db-mapping afterwards.

    Args:
        body: Template structure: {"measurement_name": {"path": null|"field"|"tag"|"timestamp"}}
        mapping_service: The mapping configuration handler (dependency injection).

    Returns:
        dict: Initialization result with status and any generated template data.

    Raises:
        HTTPException: Status 400 if structure is invalid or target types are not
            recognized. Status 500 if template persistence fails.

    Note:
        Null values are explicitly allowed here for partial initialization.
        Use POST /db-mapping to submit fully-typed mappings.
    """
    for key, value in body.items():
        if not isinstance(value, dict):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid structure for measurement '{key}': "
                    "expected a dict of path -> type mappings."
                ),
            )
        for path, target in value.items():
            if target not in _VALID_TARGET_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Invalid target type '{target}' for path '{path}' in "
                        f"measurement '{key}'. Allowed values: "
                        f"{sorted(t for t in _VALID_TARGET_TYPES if t is not None)} "
                        "or null."
                    ),
                )

    try:
        result = mapping_service.initialize_db_mapping(body)
    except OSError as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to persist mapping template: {exc}"
        ) from exc

    _logger.info("Mapping configuration initialised via PUT /initialize-db-mapping.")
    return result
