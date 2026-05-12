import logging

from aas_standard_parser import descriptor_json_helper, submodel_parser  # type: ignore
from basyx.aas import model
from fastapi import HTTPException

from ms_database_connector.core.server_handling import ServerHandler
from http import HTTPStatus as StatusCode

_logger = logging.getLogger(__name__)


def get_shell_via_registry(
    server_handler: ServerHandler, shell_id: str
) -> model.AssetAdministrationShell:
    """Retrieve an Asset Administration Shell from AAS servers using the registry.

    Looks up the AAS descriptor in the registry, retrieves the server endpoint from
    the descriptor, and fetches the complete AAS object from the repository server.

    Args:
        server_handler: Server handler managing AAS registry and repository connections.
        shell_id: Unique identifier of the Asset Administration Shell to retrieve.

    Returns:
        model.AssetAdministrationShell: The complete AAS object with the given ID.

    Raises:
        HTTPException: Status 400 if no shell_id provided or repository connection fails.
        HTTPException: Status 404 if AAS descriptor or object not found on servers.
    """
    if shell_id is None:
        _logger.error(
            "No Asset Administration Shell ID provided in configuration file."
        )
        raise HTTPException(
            status_code=StatusCode.BAD_REQUEST.value,
            detail="No Asset Administration Shell ID provided in configuration file.",
        )

    _logger.info(f"Get Asset Administration Shell with ID '{shell_id}' from server.")

    _logger.debug(
        f"Retrieving Asset Administration Shell descriptor with ID '{shell_id}' from AAS registry server '{server_handler.aas_registry_client.base_url}'."
    )
    shell_descriptor: dict = server_handler.aas_registry_client.shell_registry.get_asset_administration_shell_descriptor_by_id(
        shell_id
    )

    if shell_descriptor is None:
        _logger.error(
            f"Asset Administration Shell descriptor with ID '{shell_id}' not found on AAS registry server '{server_handler.aas_registry_client.base_url}'."
        )
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND.value,
            detail=f"Asset Administration Shell descriptor with ID '{shell_id}' not found on AAS registry server '{server_handler.aas_registry_client.base_url}'.",
        )

    shell_href = descriptor_json_helper.get_endpoint_href_by_index(shell_descriptor, 0)
    shell_href_data = descriptor_json_helper.parse_endpoint_href(shell_href)

    shell_repo_wrapper = server_handler.get_or_create_repo_wrapper(
        shell_href_data.base_url
    )

    if shell_repo_wrapper is None:
        _logger.error(
            f"Could not create repository wrapper for base URL '{shell_href_data.base_url}'."
        )
        raise HTTPException(
            status_code=StatusCode.BAD_REQUEST.value,
            detail=f"Could not connect to Repository server at '{shell_href_data.base_url}'. Repository wrapper not created.",
        )

    _logger.debug(
        f"Retrieving Asset Administration Shell with ID '{shell_id}' from server '{shell_repo_wrapper.base_url}'."
    )
    shell: model.AssetAdministrationShell = (
        shell_repo_wrapper.get_asset_administration_shell_by_id(shell_id)
    )

    if shell is None:
        _logger.error(
            f"Asset Administration Shell with ID '{shell_id}' not found on server."
        )
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND.value,
            detail=f"Asset Administration Shell with ID '{shell_id}' not found on server.",
        )

    shell_name = shell.display_name if shell.display_name else shell.id_short
    _logger.info(
        f"Asset Administration Shell '{shell_name}' with ID '{shell_id}' found on server."
    )
    return shell


def get_submodel_via_registry(
    server_handler: ServerHandler, submodel_id: str
) -> model.Submodel:
    """Retrieve a Submodel from AAS servers using the registry.

    Looks up the Submodel descriptor in the registry, retrieves the server endpoint from
    the descriptor, and fetches the complete Submodel object from the repository server.

    Args:
        server_handler: Server handler managing AAS registry and repository connections.
        submodel_id: Unique identifier of the Submodel to retrieve.

    Returns:
        model.Submodel: The complete Submodel object with the given ID.

    Raises:
        HTTPException: Status 400 if no submodel_id provided or repository connection fails.
        HTTPException: Status 404 if Submodel descriptor or object not found on servers.
    """
    if submodel_id is None:
        _logger.error("No Submodel ID provided in configuration file.")
        raise HTTPException(
            status_code=StatusCode.BAD_REQUEST.value,
            detail="No Submodel ID provided in configuration file.",
        )

    _logger.info(f"Get Submodel with ID '{submodel_id}' from server.")

    _logger.debug(
        f"Retrieving Submodel descriptor with ID '{submodel_id}' from AAS registry server '{server_handler.aas_registry_client.base_url}'."
    )
    submodel_descriptor: dict = server_handler.sm_registry_client.submodel_registry.get_submodel_descriptor_by_id(
        submodel_id
    )

    if submodel_descriptor is None:
        _logger.error(
            f"Submodel descriptor with ID '{submodel_id}' not found in AAS registry."
        )
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND.value,
            detail=f"Submodel descriptor with ID '{submodel_id}' not found in AAS registry.",
        )

    submodel_href = descriptor_json_helper.get_endpoint_href_by_index(
        submodel_descriptor, 0
    )
    submodel_href_data = descriptor_json_helper.parse_endpoint_href(submodel_href)

    submodel_repo_wrapper = server_handler.get_or_create_repo_wrapper(
        submodel_href_data.base_url
    )

    if submodel_repo_wrapper is None:
        _logger.error(
            f"Could not create repository wrapper for base URL '{submodel_href_data.base_url}'."
        )
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND.value,
            detail=f"Could not connect to Repository server at '{submodel_href_data.base_url}'. Repository wrapper not created.",
        )

    _logger.debug(
        f"Retrieving Submodel with ID '{submodel_id}' from server '{submodel_repo_wrapper.base_url}'."
    )
    submodel: model.Submodel = submodel_repo_wrapper.get_submodel_by_id(submodel_id)

    if submodel is None:
        _logger.error(f"Submodel with ID '{submodel_id}' not found on server.")
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND.value,
            detail=f"Submodel with ID '{submodel_id}' not found on server.",
        )

    _logger.debug(f"Submodel with ID '{submodel_id}' found on server.")
    return submodel


def has_access_to_sme(
    server_handler: ServerHandler, sm_id: str, element_path: str
) -> bool:
    """Check if read access to a SubmodelElement is available.

    Attempts to retrieve the Submodel and then locate the SubmodelElement by its
    path. Returns False if either operation fails.

    Args:
        server_handler: Server handler managing AAS connections.
        sm_id: Unique identifier of the Submodel containing the element.
        element_path: IdShortPath (dot-separated) of the SubmodelElement to access.

    Returns:
        bool: True if the SubmodelElement exists and is accessible, False otherwise.
    """
    try:
        submodel = get_submodel_via_registry(server_handler, sm_id)
        submodel_element: model.SubmodelElement = (
            submodel_parser.get_submodel_element_by_id_short_path(
                submodel, element_path
            )
        )
        return submodel_element is not None
    except Exception as e:
        _logger.warning("Could not access to SME: %s", e)
        return False
