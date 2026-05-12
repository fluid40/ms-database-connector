from enum import Enum

from pydantic import RootModel, model_validator


class MappingTargetType(str, Enum):
    """Enumeration of supported InfluxDB target types for mapped fields.

    Attributes:
        FIELD: Target is an InfluxDB field (numeric or string values).
        TAG: Target is an InfluxDB tag (indexed string values).
        TIMESTAMP: Target is the timestamp (exactly one per measurement).
    """

    FIELD = "field"
    TAG = "tag"
    TIMESTAMP = "timestamp"


class MeasurementMapping(RootModel[dict[str, MappingTargetType]]):
    """Mapping configuration for a single InfluxDB measurement.

    Maps AIMC sink paths to InfluxDB target types (field, tag, timestamp).
    Enforces that at most one entry per measurement is marked as timestamp.
    """

    @model_validator(mode="after")
    def validate_single_timestamp(self) -> "MeasurementMapping":
        """A measurement can define at most one sink path as timestamp."""
        timestamp_count = sum(
            1 for value in self.root.values() if value == MappingTargetType.TIMESTAMP
        )
        if timestamp_count > 1:
            raise ValueError(
                "Only one mapping entry per measurement can use target type 'timestamp'."
            )
        return self


class MappingConfiguration(RootModel[dict[str, MeasurementMapping]]):
    """Complete AIMC-to-InfluxDB field mapping configuration.

    Top-level mapping keyed by InfluxDB measurement names, with each measurement
    containing path-to-target-type mappings.

    Example structure:
        {"measurement_name": {"path.to.field": "field"}}
    """
