"""Data structures for InfluxDB operations.

Provides version-agnostic data models for writing time-series data to InfluxDB,
supporting both v1 and v2 APIs.
"""

from dataclasses import dataclass, field


@dataclass
class InfluxDataPoint:
    """Represents a single data point to be written to InfluxDB.

    This dataclass provides a version-agnostic representation of InfluxDB data,
    allowing the same data structure to be used with both InfluxDB v1 and v2 APIs.

    Attributes:
        measurement: Name of the InfluxDB measurement.
        fields: Dictionary of field key-value pairs (numeric or string values).
                Must include a 'timestamp' field in ISO 8601 format.
        tags: Dictionary of tag key-value pairs for indexing (indexed string values).
    """

    measurement: str
    fields: dict = field(default_factory=dict)
    tags: dict = field(default_factory=dict)
