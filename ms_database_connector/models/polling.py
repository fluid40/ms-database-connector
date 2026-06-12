"""Polling-related data models."""

from dataclasses import dataclass

from ms_database_connector.models.influx_data import InfluxDataPoint
from ms_database_connector.services.influx_service import IInfluxClient

InfluxPointBatch = dict[str, list[InfluxDataPoint]]


@dataclass(frozen=True)
class PollingCyclePayload:
    """Result payload produced by the collection phase of one poll cycle.

    Combines the active InfluxDB client with mapped points so the write phase
    can persist data without re-reading runtime dependencies.
    """

    influx_client: IInfluxClient
    influx_points: InfluxPointBatch
