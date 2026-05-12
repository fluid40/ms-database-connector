import logging

from aas_standard_parser import aas_parser, aimc_parser, submodel_parser  # type: ignore
from aas_standard_parser.classes.aimc_parser_classes import (  # type: ignore
    MappingConfigurations,
    ReferenceProperties,
    SourceSinkRelation,
)
from basyx.aas import model
from fastapi import HTTPException

from ms_database_connector.core.server_handling import ServerHandler
from ms_database_connector.models.influx_data import InfluxDataPoint
from ms_database_connector.services.aas_infrastructure_service import (
    get_submodel_via_registry,
    has_access_to_sme,
)
from http import HTTPStatus as StatusCode

from ms_database_connector.config.db_mapping import DbMapping, MappingTargetType

_logger = logging.getLogger(__name__)


def get_aimc_submodel(
    server_handler: ServerHandler, shell: model.AssetAdministrationShell
) -> model.Submodel:
    """Get the Asset Interface Mapping Configuration (AIMC) submodel from the AAS.

    Args:
        server_handler: The handler for the AAS server.
        shell: The AAS to get the submodel from.

    Returns:
        model.Submodel: The AIMC submodel.

    Raises:
        HTTPException: If the AIMC submodel could not be found.
    """
    _logger.info("Get AIMC submodel from Shell.")
    submodel_ids = aas_parser.get_submodel_ids(shell)

    for submodel_id in submodel_ids:
        submodel = get_submodel_via_registry(server_handler, submodel_id)

        semantic_id_value = submodel_parser.get_semantic_id_value(submodel)

        if (
            semantic_id_value
            and "/idta/AssetInterfacesMappingConfiguration" in semantic_id_value
        ):
            _logger.info(f"AIMC submodel with ID '{submodel_id}' found on server.")
            return submodel

    _logger.error(
        "No Submodel with semantic ID '/idta/AssetInterfacesMappingConfiguration' not found on server."
    )
    raise HTTPException(
        status_code=StatusCode.NOT_FOUND.value,
        detail="No Submodel with semantic ID '/idta/AssetInterfacesMappingConfiguration' not found on server.",
    )


def get_mapping_configurations(aimc_submodel: model.Submodel) -> MappingConfigurations:
    """Get the mapping configurations from the AIMC submodel.

    Args:
        aimc_submodel: The AIMC submodel.

    Returns:
        MappingConfigurations: The mapping configurations.

    Raises:
        HTTPException: If no mapping configurations are found in the AIMC
            submodel.
    """
    mapping_configurations = aimc_parser.parse_mapping_configurations(aimc_submodel)

    if (
        mapping_configurations is None
        or len(mapping_configurations.configurations) == 0
    ):
        _logger.error("No mapping configurations found in AIMC submodel.")
        raise HTTPException(
            status_code=StatusCode.NOT_FOUND.value,
            detail="No mapping configurations found in AIMC submodel.",
        )

    return mapping_configurations


def extract_target_references_from_aimc(
    aimc_sm: model.Submodel,
) -> list[ReferenceProperties]:
    """Extract the target SME references from the AIMC submodel.

    Args:
        aimc_sm: The AIMC submodel.

    Returns:
        list[ReferenceProperties]: List of target SME references.
    """
    mapping_configurations: MappingConfigurations = get_mapping_configurations(aimc_sm)
    return extract_target_references_from_mapping_configuration(mapping_configurations)


def extract_target_references_from_mapping_configuration(
    mapping_configurations: MappingConfigurations,
) -> list[ReferenceProperties]:
    """Extract the target SME references from the mapping configurations (contained in the AIMC submodel).

    Args:
        mapping_configurations: The mapping configurations.

    Returns:
        list[ReferenceProperties]: List of target SME references.
    """
    target_references = []
    for configuration in mapping_configurations.configurations:
        relations: list[SourceSinkRelation] = configuration.source_sink_relations
        _logger.debug(
            f"Found {len(relations)} source-sink relations in mapping configuration with interface reference '{configuration.interface_reference.value}'."
        )
        for relation in relations:
            target_reference: ReferenceProperties = relation.sink_properties
            _logger.debug(
                f"Extracted target SME reference '{target_reference.parent_path}.{target_reference.property_name}' from mapping configuration."
            )
            target_references.append(target_reference)
    return target_references


def check_access_to_elements(
    server_handler: ServerHandler, target_references: list[ReferenceProperties]
) -> bool:
    """Check if the read access to the target SME references is granted.

    Args:
        server_handler: Server handler.
        target_references: List of target SME references.

    Returns:
        bool: ``True`` if access is granted for all target references,
        ``False`` otherwise.
    """
    for reference in target_references:
        submodel_id = reference.submodel_id
        element_path = ".".join(reference.parent_path + [reference.property_name])
        if not has_access_to_sme(server_handler, submodel_id, element_path):
            _logger.warning(
                f"No access to SME '{element_path}' in Submodel with ID '{submodel_id}'."
            )
            return False
    return True


class InfluxMapper:
    """Maps SubmodelElements from AAS to InfluxDB Point objects based on configuration.

    Responsible for validating element accessibility, retrieving SME values, and
    constructing InfluxDB Point objects with appropriate field/tag assignments.
    """

    def __init__(
        self,
        server_handler: ServerHandler,
        db_mapping: DbMapping,
        target_references: list[ReferenceProperties],
    ):
        """Initialize the mapper with server handler, mapping config, and element references.

        Args:
            server_handler: Handler for AAS server communication.
            db_mapping: Database mapping configuration (measurements to sink paths).
            target_references: List of accessible SubmodelElement references.
        """
        self.server_handler = server_handler
        self.db_mapping = db_mapping
        self.target_references = target_references

    def map_smes_to_influx(self) -> dict[str, list[InfluxDataPoint]]:
        """Create InfluxDB data points from mapped SubmodelElements.

        Validates accessibility of all mapped elements, retrieves their values,
        and constructs InfluxDataPoint objects with fields and tags according to the mapping.

        Returns:
            Dictionary mapping measurement names to lists of InfluxDataPoint objects.

        Raises:
            HTTPException: If elements are not accessible.
        """
        self._validate_element_access()
        reference_map = self._build_reference_map()
        influx_points: dict[str, list[InfluxDataPoint]] = {}

        for measurement_name, measurement_mapping in self.db_mapping.root.items():
            point = self._process_measurement(
                measurement_name, measurement_mapping, reference_map
            )
            if point is not None:
                influx_points[measurement_name] = [point]

        _logger.info(f"Created {len(influx_points)} measurement(s) with data point(s).")
        return influx_points

    def _validate_element_access(self) -> None:
        """Validate that all target elements are accessible.

        Raises:
            HTTPException: If any element is not accessible.
        """
        if not check_access_to_elements(self.server_handler, self.target_references):
            _logger.warning("Some mapped elements are not accessible.")
            raise HTTPException(
                status_code=StatusCode.BAD_REQUEST.value,
                detail="Some mapped elements are not accessible.",
            )

    def _build_reference_map(self) -> dict[str, ReferenceProperties]:
        """Build a lookup map from sink paths to their references.

        Returns:
            Dictionary mapping sink path strings to ReferenceProperties objects.
        """
        return {
            ".".join(ref.parent_path + [ref.property_name]): ref
            for ref in self.target_references
        }

    def _process_measurement(
        self,
        measurement_name: str,
        measurement_mapping,
        reference_map: dict[str, ReferenceProperties],
    ) -> InfluxDataPoint | None:
        """Process a single measurement and its mapped sink paths.

        Args:
            measurement_name: Name of the InfluxDB measurement.
            measurement_mapping: Mapping of sink paths to target types for this measurement.
            reference_map: Lookup map for sink paths to references.

        Returns:
            InfluxDataPoint object with fields/tags, or None if no values were added.
        """
        point = InfluxDataPoint(measurement=measurement_name)
        has_values = False

        for sink_path, target_type in measurement_mapping.root.items():
            if sink_path not in reference_map:
                _logger.debug(
                    f"Sink path '{sink_path}' not found in target references."
                )
                continue

            if self._add_value_to_point(point, sink_path, target_type, reference_map):
                has_values = True

        return point if has_values else None

    def _add_value_to_point(
        self,
        point: InfluxDataPoint,
        sink_path: str,
        target_type,
        reference_map: dict[str, ReferenceProperties],
    ) -> bool:
        """Retrieve a SME value and add it to the Point object.

        Args:
            point: Point object to add value to.
            sink_path: Path identifier for the sink element.
            target_type: Target type (field, tag, or timestamp).
            reference_map: Lookup map for sink paths to references.

        Returns:
            True if value was successfully added, False otherwise.
        """
        try:
            reference = reference_map[sink_path]
            sme_value = self._retrieve_sme_value(reference)

            if sme_value is None:
                return False

            self._assign_value_to_point(point, sink_path, sme_value, target_type)
            return True

        except Exception as e:
            _logger.error(f"Error processing sink path '{sink_path}': {e}")
            return False

    def _retrieve_sme_value(self, reference: ReferenceProperties):
        """Retrieve the value from a SubmodelElement.

        Args:
            reference: Reference properties identifying the element location.

        Returns:
            The element's value, or None if not found or has no value.
        """
        submodel = get_submodel_via_registry(self.server_handler, reference.submodel_id)
        element_path = ".".join(reference.parent_path + [reference.property_name])

        sme = submodel_parser.get_submodel_element_by_id_short_path(
            submodel, element_path
        )

        if sme is None:
            _logger.warning(
                f"SubmodelElement '{element_path}' not found in Submodel '{reference.submodel_id}'."
            )
            return None

        if not hasattr(sme, "value"):
            _logger.warning(f"SubmodelElement '{element_path}' has no value attribute.")
            return None

        return sme.value

    def _assign_value_to_point(
        self, point: InfluxDataPoint, sink_path: str, sme_value, target_type
    ) -> None:
        """Assign a value to the InfluxDataPoint as field, tag, or timestamp.

        Args:
            point: InfluxDataPoint object to add value to.
            sink_path: Identifier for this value.
            sme_value: The value to add.
            target_type: Target type determining assignment method.
        """
        if target_type == MappingTargetType.FIELD:
            point.fields[sink_path] = sme_value
        elif target_type == MappingTargetType.TAG:
            point.tags[sink_path] = str(sme_value)
        elif target_type == MappingTargetType.TIMESTAMP:
            _logger.debug(f"Timestamp field '{sink_path}' will be set separately.")
