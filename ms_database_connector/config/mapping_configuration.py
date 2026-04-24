from enum import Enum

from pydantic import RootModel, model_validator


class MappingTargetType(str, Enum):
    """Supported target types for an individual mapped sink path."""

    FIELD = "field"
    TAG = "tag"
    TIMESTAMP = "timestamp"


class MeasurementMapping(RootModel[dict[str, MappingTargetType]]):
    """Mapping entries for one measurement, keyed by sink path."""

    @model_validator(mode="after")
    def validate_single_timestamp(self) -> "MeasurementMapping":
        """A measurement can define at most one sink path as timestamp."""
        timestamp_count = sum(1 for value in self.root.values() if value == MappingTargetType.TIMESTAMP)
        if timestamp_count > 1:
            raise ValueError("Only one mapping entry per measurement can use target type 'timestamp'.")
        return self


class MappingConfiguration(RootModel[dict[str, MeasurementMapping]]):
    """Top-level mapping config keyed by measurement name.

    Example:
    {
        "MappingConfigurations[0]": {
            "machineStateData.counter": "tag",
            "EnergyConnection_Electric.EnergyMeasure_EnergyTotal.value": "field"
        }
    }
    """

