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


class DbMapping(RootModel[dict[str, MeasurementMapping]]):
    """Complete AIMC-to-InfluxDB field mapping configuration.

    Top-level mapping keyed by InfluxDB measurement names, with each measurement
    containing path-to-target-type mappings.

    Example structure:
        {"measurement_name": {"path.to.field": "field"}}
    """

    @model_validator(mode="after")
    def validate_measurements_not_none(self) -> "DbMapping":
        """Ensure all MeasurementMapping values are not None or empty."""
        for measurement_name, mapping in self.root.items():
            if mapping is None:
                raise ValueError(
                    f"MeasurementMapping for '{measurement_name}' must not be None."
                )
            if not mapping.root:
                raise ValueError(
                    f"MeasurementMapping for '{measurement_name}' must not be empty."
                )
        return self


class RawMeasurementMapping(RootModel[dict[str, MappingTargetType | None]]):
    """Raw measurement mapping allowing None values for unfilled templates.

    Similar to MeasurementMapping but allows ``None`` values to represent
    unfilled template entries. Used to store partial/incomplete mappings
    before they are validated and filled in.

    Example structure with unfilled entry:
        {"path.to.field": "field", "path.to.unknown": null}
    """

    @model_validator(mode="before")
    @classmethod
    def validate_value_types(
        cls, data: dict[str, object] | object
    ) -> dict[str, object] | object:
        """Ensure all values are None or valid MappingTargetType values."""
        if not isinstance(data, dict):
            return data

        invalid_entries: list[tuple[str, object]] = []
        allowed_values = {target.value for target in MappingTargetType}

        for sink_path, value in data.items():
            if value is None or isinstance(value, MappingTargetType):
                continue
            if isinstance(value, str) and value in allowed_values:
                continue
            invalid_entries.append((sink_path, value))

        if invalid_entries:
            formatted_entries = ", ".join(
                f"{sink_path}={value!r}" for sink_path, value in invalid_entries
            )
            allowed_values_text = ", ".join(
                sorted(repr(value) for value in allowed_values)
            )
            raise ValueError(
                "RawMeasurementMapping values must be None or one of "
                f"{allowed_values_text}. Invalid entries: {formatted_entries}"
            )

        return data

    def has_unfilled_entries(self) -> bool:
        """Check if this measurement mapping contains any unfilled (None) entries."""
        return any(value is None for value in self.root.values())


class RawDbMapping(RootModel[dict[str, RawMeasurementMapping]]):
    """Raw AIMC-to-InfluxDB mapping with optional unfilled entries.

    Top-level mapping keyed by measurement names, where each measurement can
    contain ``None`` values for unfilled template entries. Used to store
    partial mappings that will be completed later.

    Example structure:
        {"measurement_name": {"path.to.field": "field", "path.to.unknown": null}}
    """

    def has_unfilled_entries(self) -> bool:
        """Check if any measurement mapping contains unfilled (None) entries."""
        return any(m.has_unfilled_entries() for m in self.root.values())
