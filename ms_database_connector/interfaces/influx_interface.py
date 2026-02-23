"""Interface definitions for InfluxDB clients."""


class IInfluxClient:
    """Interface for InfluxDB clients."""

    def initialize(self, password: str) -> None:
        """Initialize the InfluxDB client with the given password.

        :param password: The password for the InfluxDB user.
        """
        raise NotImplementedError

    def ping(self) -> bool:
        """Ping the InfluxDB server to check if it's reachable.

        :return: True if the server is reachable, False otherwise.
        """
        raise NotImplementedError

    def write_data(self, fields: dict, measurement: str, tags: dict) -> bool:
        """Write data to the InfluxDB.

        :param fields: The fields to write, must include a 'timestamp' field in ISO format.
        :param measurement: The name of the measurement.
        :param tags: The tags to associate with the data.
        :return: True if the data was written successfully, False otherwise.
        """
        raise NotImplementedError

    def create_database(self):
        """Check if the specified database exists, and create it if it does not."""
        raise NotImplementedError
