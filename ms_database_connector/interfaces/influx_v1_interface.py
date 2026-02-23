import json
import logging
import time
from datetime import datetime

import requests
from influxdb import InfluxDBClient
from pydantic import BaseModel, Field, PrivateAttr, ValidationError

from ms_database_connector.interfaces.influx_interface import IInfluxClient

logger = logging.getLogger(__name__)


class InfluxClient(BaseModel, IInfluxClient):
    """Client for InfluxDB interactions."""

    host: str = Field(default="influx_database", description="The hostname or IP address of the InfluxDB 1 database.", alias="Host")
    port: int = Field(default=8086, description="The port number of the InfluxDB database.", alias="Port")
    username: str = Field(default="", description="The username for the InfluxDB database.", alias="Username")
    database: str = Field(default="", description="The database name to use in InfluxDB.", alias="Database")
    connection_time_out: int = Field(default=100, description="Connection establishment timeout in seconds.", alias="ConnectionTimeOut")
    trust_env: bool = Field(default=False, description="Disable proxy usage from environment.", alias="TrustEnv")
    _client: InfluxDBClient = PrivateAttr(default=None)

    def initialize(self, password: str) -> None:
        """Initialize the InfluxDB client with the given password.

        :param password: The password for the InfluxDB user.
        """
        session = requests.Session()
        session.trust_env = False

        client = InfluxDBClient(host=self.host, port=self.port, username=self.username, password=password, database=self.database, session=session)

        if not client:
            logger.error("Could not create InfluxDB v1 client.")

        self._client = client

    def create_database(self):
        """Check if the specified database exists, and create it if it does not."""

        logger.debug(f"Create database '{self.database}'")
        dbs = [db["name"] for db in self._client.get_list_database()]

        logger.debug(f"Check if database '{self.database}' already exists")
        if self.database not in dbs:
            logger.debug(f"Creating database '{self.database}'")
            self._client.create_database(self.database)

        logger.debug(f"Switch to database '{self.database}'.")
        self._client.switch_database(self.database)

    def ping(self) -> bool:
        """Ping the InfluxDB server to check if it's reachable.

        :return: True if the server is reachable, False otherwise.
        """
        logger.debug(f"Pinging InfluxDB server '{self.host}:{self.port}'.")
        if self._client is None:
            logger.error("InfluxDB client is not initialized.")
            return False

        try:
            self._client.ping()
            return True
        except Exception as e:
            logger.error(f"Failed to ping Influx DB server: {e}")
            return False

    def write_data(self, fields: dict, measurement: str, tags: dict) -> bool:
        """Write data to the InfluxDB.

        :param fields: The data to write, must include a 'timestamp' field in ISO format.
        :param measurement: The name of the measurement.
        :param tags: The tags to associate with the data point.
        :return: True if the data was written successfully, False otherwise.
        """
        logger.debug(f"Writing data to InfluxDB measurement '{measurement}' with tags: {tags}")

        if fields is None or not isinstance(fields, dict):
            logger.debug(f"'{measurement}': Data must be a non-empty dictionary.")
            return False

        if "timestamp" not in fields and "Timestamp" not in fields:
            logger.error(f"{measurement}: Data must include a 'timestamp' field.")
            return False

        point = {
            "measurement": measurement,
            "tags": tags,
            "fields": fields,
            "time": int(datetime.fromisoformat(fields["timestamp"].replace("Z", "+00:00")).timestamp() * 1e9),
        }

        logger.info(
            f"Writing data to InfluxDB:\nMeasurement: '{measurement}'\nTags:\n{json.dumps(tags, indent=4)}'\nValues:\n{json.dumps(fields, indent=4)}"
        )
        success: bool = self._client.write_points([point], time_precision="n")

        if not success:
            logger.error(f"Failed to write data point to InfluxDB: {point}")
            return False

        return True


def create_client(config_dict: dict, password: str) -> IInfluxClient:
    """Create a HTTP client for a asset connector connection from a given configuration.

    :param config_dict: The configuration dictionary for the asset connector.
    :param password: The password for the InfluxDB user.
    :raises ValidationError: If the configuration is invalid.
    :return: A ConnectorClient instance or None if creation failed.
    """
    logger.info("Create Influx Database client.")

    try:
        config_string = json.dumps(config_dict, indent=4)
        client = InfluxClient.model_validate_json(config_string)
    except ValidationError as ve:
        raise ValidationError(f"Invalid Influx DB configuration file: {ve}") from ve

    logger.info(f"Using Influx DB configuration: '{client.host}:{client.port}' | username: '{client.username}' | database: '{client.database}'.")

    client.initialize(password)

    connected = _establish_connection(client)

    if not connected:
        raise ConnectionError(f"Failed to establish connection to Influx DB '{client.host}:{client.port}'")

    client.create_database()

    return client


def _establish_connection(client: InfluxClient) -> bool:
    start_time = time.time()
    logger.info(f"Try to connect to Influx DB '{client.host}:{client.port}' for {client.connection_time_out} seconds")
    counter: int = 0
    while True:
        try:
            root = client.ping()
            if root:
                logger.info(f"Connected to Influx DB at '{client.host}:{client.port}' successfully.")
                return True
        except requests.exceptions.ConnectionError:
            pass
        if time.time() - start_time > client.connection_time_out:
            logger.error(f"Connection to Influx DB timed out after {client.connection_time_out} seconds.")
            return False

        counter += 1
        logger.warning(f"Retrying connection to Influx DB (attempt: {counter})")
        time.sleep(5)
