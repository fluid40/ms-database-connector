import logging

from aas_standard_parser import descriptor_json_helper, aas_parser, aimc_parser, submodel_parser
from aas_standard_parser.classes.aimc_parser_classes import MappingConfigurations
from basyx.aas import model
from fastapi import HTTPException

from ms_database_connector.core.server_handling import ServerHandler
from http import HTTPStatus as StatusCode

_logger = logging.getLogger(__name__)


def get_shell_via_registry(server_handler: ServerHandler, shell_id: str) -> model.AssetAdministrationShell:
    """Get an Asset Administration Shell from an AAS server environment using the AAS registry.

    :param server_handler: Server handler
    :param shell_id: ID of the Asset Administration Shell to get
    :raises HTTPException: If no Asset Administration Shell ID is provided in the configuration file.
    :raises HTTPException: If the Asset Administration Shell descriptor with the provided ID could not be found in the AAS registry.
    :raises HTTPException: If a repository wrapper for the AAS server could not be created.
    :raises HTTPException: If the Asset Administration Shell with the provided ID could not be found on the AAS server.
    :return: Asset Administration Shell with the provided ID from the AAS server
    """
    if shell_id is None:
        _logger.error("No Asset Administration Shell ID provided in configuration file.")
        raise HTTPException(
            status_code=StatusCode.BAD_REQUEST.value, detail="No Asset Administration Shell ID provided in configuration file."
        )

    _logger.info(f"Get Asset Administration Shell with ID '{shell_id}' from server.")

    _logger.debug(
        f"Retrieving Asset Administration Shell descriptor with ID '{shell_id}' from AAS registry server '{server_handler.aas_registry_client.base_url}'."
    )
    shell_descriptor: dict = server_handler.aas_registry_client.shell_registry.get_asset_administration_shell_descriptor_by_id(shell_id)

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

    shell_repo_wrapper = server_handler.get_or_create_repo_wrapper(shell_href_data.base_url)

    if shell_repo_wrapper is None:
        _logger.error(f"Could not create repository wrapper for base URL '{shell_href_data.base_url}'.")
        raise HTTPException(
            status_code=StatusCode.BAD_REQUEST.value,
            detail=f"Could not connect to Repository server at '{shell_href_data.base_url}'. Repository wrapper not created.",
        )

    _logger.debug(f"Retrieving Asset Administration Shell with ID '{shell_id}' from server '{shell_repo_wrapper.base_url}'.")
    shell: model.AssetAdministrationShell = shell_repo_wrapper.get_asset_administration_shell_by_id(shell_id)

    if shell is None:
        _logger.error(f"Asset Administration Shell with ID '{shell_id}' not found on server.")
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND.value, detail=f"Asset Administration Shell with ID '{shell_id}' not found on server."
        )

    shell_name = shell.display_name if shell.display_name else shell.id_short
    _logger.info(f"Asset Administration Shell '{shell_name}' with ID '{shell_id}' found on server.")
    return shell


def get_submodel_via_registry(server_handler: ServerHandler, submodel_id: str) -> model.Submodel:
    """Get a Submodel from an AAS server environment using the AAS registry.

    :param server_handler: Server handler
    :param submodel_id: ID of the Submodel to get
    :raises HTTPException: If no Submodel ID is provided in the configuration file.
    :raises HTTPException: If the Submodel descriptor with the provided ID could not be found in the AAS registry.
    :raises HTTPException: If a repository wrapper for the AAS server could not be created.
    :raises HTTPException: If the Submodel with the provided ID could not be found on the AAS server.
    :return: Submodel with the provided ID from the AAS server
    """
    if submodel_id is None:
        _logger.error("No Submodel ID provided in configuration file.")
        raise HTTPException(status_code=StatusCode.BAD_REQUEST.value, detail="No Submodel ID provided in configuration file.")

    _logger.info(f"Get Submodel with ID '{submodel_id}' from server.")

    _logger.debug(f"Retrieving Submodel descriptor with ID '{submodel_id}' from AAS registry server '{server_handler.aas_registry_client.base_url}'.")
    submodel_descriptor: dict = server_handler.sm_registry_client.submodel_registry.get_submodel_descriptor_by_id(submodel_id)

    if submodel_descriptor is None:
        _logger.error(f"Submodel descriptor with ID '{submodel_id}' not found in AAS registry.")
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND.value,
            detail=f"Submodel descriptor with ID '{submodel_id}' not found in AAS registry.",
        )

    submodel_href = descriptor_json_helper.get_endpoint_href_by_index(submodel_descriptor, 0)
    submodel_href_data = descriptor_json_helper.parse_endpoint_href(submodel_href)

    submodel_repo_wrapper = server_handler.get_or_create_repo_wrapper(submodel_href_data.base_url)

    if submodel_repo_wrapper is None:
        _logger.error(f"Could not create repository wrapper for base URL '{submodel_href_data.base_url}'.")
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND.value,
            detail=f"Could not connect to Repository server at '{submodel_href_data.base_url}'. Repository wrapper not created.",
        )

    _logger.debug(f"Retrieving Submodel with ID '{submodel_id}' from server '{submodel_repo_wrapper.base_url}'.")
    submodel: model.Submodel = submodel_repo_wrapper.get_submodel_by_id(submodel_id)

    if submodel is None:
        _logger.error(f"Submodel with ID '{submodel_id}' not found on server.")
        raise HTTPException(status_code=StatusCode.NOT_FOUND.value, detail=f"Submodel with ID '{submodel_id}' not found on server.")

    _logger.debug(f"Submodel with ID '{submodel_id}' found on server.")
    return submodel


def get_aimc_submodel(server_handler: ServerHandler, shell: model.AssetAdministrationShell) -> model.Submodel:
    """Get the Asset Interface Mapping Configuration (AIMC) submodel from the AAS.

    :param aas_server_wrapper: The SDK wrapper for the AAS server
    :param shell: The AAS to get the submodel from
    :raises HTTPException: If the AIMC submodel could not be found
    :return: The AIMC submodel
    """
    _logger.info("Get AIMC submodel from Shell.")
    submodel_ids = aas_parser.get_submodel_ids(shell)

    for submodel_id in submodel_ids:
        submodel = get_submodel_via_registry(server_handler, submodel_id)

        semantic_id_value = submodel_parser.get_semantic_id_value(submodel)

        if semantic_id_value and "/idta/AssetInterfacesMappingConfiguration" in semantic_id_value:
            _logger.info(f"AIMC submodel with ID '{submodel_id}' found on server.")
            return submodel

    _logger.error("No Submodel with semantic ID '/idta/AssetInterfacesMappingConfiguration' not found on server.")
    raise HTTPException(
        status_code=StatusCode.NOT_FOUND.value,
        detail="No Submodel with semantic ID '/idta/AssetInterfacesMappingConfiguration' not found on server.",
    )


def get_mapping_configurations(aimc_submodel: model.Submodel) -> MappingConfigurations:
    """Get the mapping configurations from the AIMC submodel.

    :param aimc_submodel: The AIMC submodel
    :return: The mapping configurations
    """
    mapping_configurations = aimc_parser.parse_mapping_configurations(aimc_submodel)

    if mapping_configurations is None or len(mapping_configurations.configurations) == 0:
        _logger.error("No mapping configurations found in AIMC submodel.")
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND.value,
            detail="No mapping configurations found in AIMC submodel.",
        )

    return mapping_configurations