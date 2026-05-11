import logging

from aas_standard_parser import aas_parser, aimc_parser, submodel_parser  # type: ignore
from aas_standard_parser.classes.aimc_parser_classes import MappingConfigurations, ReferenceProperties, SourceSinkRelation  # type: ignore
from basyx.aas import model
from fastapi import HTTPException

from ms_database_connector.core.server_handling import ServerHandler
from ms_database_connector.services.aas_infrastructure_service import get_submodel_via_registry
from http import HTTPStatus as StatusCode

_logger = logging.getLogger(__name__)

def get_aimc_submodel(server_handler: ServerHandler, shell: model.AssetAdministrationShell) -> model.Submodel:
    """Get the Asset Interface Mapping Configuration (AIMC) submodel from the AAS.

    :param server_handler: The handler for the AAS server
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

def extract_target_references_from_mapping_configuration(mapping_configurations: MappingConfigurations) -> list[ReferenceProperties]:
    """Extract the target Submodel references from the mapping configurations.

    :param mapping_configurations: The mapping configurations
    :return: List of target Submodel references
    """
    target_references = []
    for configuration in mapping_configurations.configurations:
        relations: list[SourceSinkRelation] = configuration.source_sink_relations
        for relation in relations:
            target_reference: ReferenceProperties = relation.sink_properties
            target_references.append(target_reference)
    return target_references