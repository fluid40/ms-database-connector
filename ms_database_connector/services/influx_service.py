"""Interface definitions for InfluxDB clients."""


class IInfluxClient:
    """Interface for InfluxDB client implementations.

    Defines the contract for database client implementations supporting
    different InfluxDB versions (v1 and v2).
    """

    def initialize(self, password: str) -> None:
        """Initialize the InfluxDB client with credentials.

        Args:
            password: The authentication password or token for the InfluxDB user.
        """
        raise NotImplementedError

    def ping(self) -> bool:
        """Verify InfluxDB server connectivity.

        Returns:
            bool: True if the server is reachable and healthy, False otherwise.
        """
        raise NotImplementedError

    def write_data(self, fields: dict, measurement: str, tags: dict) -> bool:
        """Write a data point to InfluxDB.

        Args:
            fields: Dictionary of field values. Must include a 'timestamp' field
                in ISO 8601 format.
            measurement: The name of the measurement.
            tags: Dictionary of tag key-value pairs for indexing.

        Returns:
            bool: True if the data was written successfully, False otherwise.
        """
        raise NotImplementedError

    def create_database(self):
        """Verify or create the configured database/bucket.

        Ensures the target database or bucket exists, creating it if necessary.
        """
        raise NotImplementedError
