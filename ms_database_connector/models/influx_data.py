"""Data structures for InfluxDB operations.

Provides version-agnostic data models for writing time-series data to InfluxDB,
supporting both v1 and v2 APIs.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class InfluxDataPoint:
    """Represents a single data point to be written to InfluxDB.

    This dataclass provides a version-agnostic representation of InfluxDB data,
    allowing the same data structure to be used with both InfluxDB v1 and v2 APIs.

    Attributes:
        measurement: Name of the InfluxDB measurement.
        timestamp: Timestamp for the data point in ISO 8601 format (e.g. 2023-03-15T12:34:56.789Z). If not provided, the current time will be used.
        fields: Dictionary of field key-value pairs (numeric or string values).
        tags: Dictionary of tag key-value pairs for indexing (indexed string values).
    """

    measurement: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )
    fields: dict = field(default_factory=dict)
    tags: dict = field(default_factory=dict)
