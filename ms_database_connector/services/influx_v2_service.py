import json
import logging
import re
import time
import requests
from datetime import datetime
from ms_database_connector.services.influx_service import IInfluxClient
from pydantic import BaseModel, Field, PrivateAttr, ValidationError
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.domain.bucket_retention_rules import BucketRetentionRules

logger = logging.getLogger(__name__)


class InfluxV2Client(IInfluxClient, BaseModel):
    """Client for InfluxDB v2 interactions."""

    url: str = Field(
        default="ms-dbc-influx-v2",
        description="The base URL of the InfluxDB 2 database.",
        alias="Url",
    )
    organization: str = Field(
        ...,
        description="The Organization name to use in InfluxDB.",
        alias="Organization",
    )
    bucket: str = Field(
        ..., description="The Bucket name to use in InfluxDB.", alias="Bucket"
    )
    connection_time_out: int = Field(
        default=100,
        description="Connection establishment timeout in seconds.",
        alias="ConnectionTimeOut",
    )
    trust_env: bool = Field(
        default=False,
        description="Disable proxy usage from environment.",
        alias="TrustEnv",
    )
    _client: InfluxDBClient = PrivateAttr()
    _tag: str = PrivateAttr(default="")
    _organization_id: str = PrivateAttr(default="")
    _bucket_id: str = PrivateAttr(default="")

    def initialize(self, token: str) -> None:
        """Initialize the InfluxDB client with the given token.

        :param token: The token for the InfluxDB user.
        """
        # session = requests.Session()
        # session.trust_env = self.trust_env
        client = InfluxDBClient(url=self.url, token=token, org=self.organization)

        if not client:
            logger.error("Could not create InfluxDB v2 client.")
            return

        orgs_api = client.organizations_api()
        orgs: list = orgs_api.find_organizations(org=self.organization)

        if len(orgs) == 0 or orgs[0] is None:
            logger.error(f"Organization '{self.organization}' not found in InfluxDB.")
        else:
            self._organization_id = orgs[0].id

        self._client = client

    def create_database(self):
        """Check if the specified bucket exists, and create it if it does not."""
        logger.debug(f"Create bucket '{self.bucket}'")
        buckets_api = self._client.buckets_api()

        logger.debug(f"Check if bucket '{self.bucket}' already exists")
        bucket = buckets_api.find_bucket_by_name(self.bucket)

        if bucket is not None:
            logger.debug(f"Bucket '{self.bucket}' already exists")
            self._bucket_id = bucket.id
            return

        logger.debug(f"Creating bucket '{self.bucket}'")
        retention = BucketRetentionRules(type="expire", every_seconds=30 * 24 * 3600)
        bucket = buckets_api.create_bucket(
            bucket_name=self.bucket,
            org_id=self._organization_id,
            retention_rules=retention,
        )

        self._bucket_id = bucket.id

    def ping(self) -> bool:
        """Ping the InfluxDB server to check if it's reachable.

        :return: True if the server is reachable, False otherwise.
        """
        logger.debug(f"Pinging InfluxDB server '{self.url}'.")
        if self._client is None:
            logger.error("InfluxDB client is not initialized.")
            return False

        try:
            health = self._client.health()
        except Exception as e:
            logger.error(f"Failed to ping Influx DB server: {e}")
            return False

        if health.status != "pass":
            logger.error(f"InfluxDB server health check failed: {health.message}")
            return False

        return True

    def _is_valid_measurement_name(self, measurement: str) -> bool:
        """Validate measurement names to avoid accidental high-cardinality series creation."""
        if not isinstance(measurement, str):
            logger.error("Measurement name must be a string.")
            return False

        name = measurement.strip()

        if not name:
            logger.error("Measurement name must be non-empty.")
            return False

        # Keep names simple and predictable: letters, numbers, underscores, dots, colons and hyphens.
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]{0,127}", name):
            logger.error(
                "Measurement name '%s' is invalid. Use a stable identifier starting with a letter and only [A-Za-z0-9_.:-].",
                measurement,
            )
            return False

        # Common accidental dynamic-name patterns that create high cardinality.
        if re.search(r"[0-9]{10,}", name):
            logger.error(
                "Measurement name '%s' appears dynamic (long numeric fragment).",
                measurement,
            )
            return False

        if re.search(
            r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
            name,
        ):
            logger.error(
                "Measurement name '%s' appears dynamic (UUID-like pattern).",
                measurement,
            )
            return False

        if re.search(r"\d{4}-\d{2}-\d{2}", name):
            logger.error(
                "Measurement name '%s' appears dynamic (date-like pattern).",
                measurement,
            )
            return False

        return True

    def write_data(self, fields: dict, measurement: str, tags: dict) -> bool:
        """Write data to the InfluxDB.

        :param fields: The data to write, must include a 'timestamp' field in ISO format.
        :param measurement: The name of the measurement.
        :param tags: The tags to associate with the data point.
        :return: True if the data was written successfully, False otherwise.
        """
        logger.debug(
            f"Writing data to InfluxDB measurement '{measurement}' with tags: {tags}"
        )

        if not self._is_valid_measurement_name(measurement):
            return False

        if fields is None or not isinstance(fields, dict):
            logger.debug(f"'{measurement}': Data must be a non-empty dictionary.")
            return False

        if "timestamp" not in fields and "Timestamp" not in fields:
            logger.error(f"{measurement}: Data must include a 'timestamp' field.")
            return False

        point: Point = Point(measurement)
        for tag_key, tag_value in tags.items():
            point.tag(tag_key, tag_value)
        for field_key, field_value in fields.items():
            if field_key.lower() != "timestamp":
                point.field(field_key, field_value)
        point.time(
            int(
                datetime.fromisoformat(
                    fields["timestamp"].replace("Z", "+00:00")
                ).timestamp()
                * 1e9
            )
        )

        logger.info(
            f"Writing data to InfluxDB:\nMeasurement: '{measurement}'\nTags:\n{json.dumps(tags, indent=4)}'\nValues:\n{json.dumps(fields, indent=4)}"
        )

        try:
            write_api = self._client.write_api(write_options=SYNCHRONOUS)
            write_api.write(record=point, bucket=self.bucket)
        except Exception as e:
            logger.error(f"Failed to write data point '{point}' to InfluxDB: {e}")
            return False

        return True


def create_client(config_dict: dict, token: str) -> IInfluxClient:
    """Initialize an InfluxDb v2 client for interaction with the database.

    :param config_dict: the configuration dictionary for the InfluxDB v2 client.
    :param token: the authentication token for the InfluxDB v2 client.
    :raises ValidationError: if the configuration is invalid.
    :raises RuntimeError: if connection or database creation fails.
    :return: an initialized InfluxV2Client instance.
    """
    logger.info("Create Influx Database client.")

    try:
        config_string = json.dumps(config_dict, indent=4)
        client = InfluxV2Client.model_validate_json(config_string)
    except ValidationError as ve:
        raise ValidationError(f"Invalid Influx DB configuration file: {ve}") from ve

    if not client.organization.endswith("-org"):
        logger.warning(
            f"Adjusting Influx DB organization name from '{client.organization}' to '{client.organization}-org'."
        )
        client.organization = f"{client.organization}-org"

    logger.info(
        f"Using Influx DB configuration: '{client.url}' | organization: '{client.organization}'."
    )

    client.initialize(token)

    connected = _establish_connection(client)

    if not connected:
        raise RuntimeError(
            f"Failed to establish connection to InfluxDB at '{client.url}'"
        )

    try:
        client.create_database()
    except Exception as e:
        logger.error(f"Failed to create InfluxDB database: {e}")
        raise RuntimeError(f"Failed to create InfluxDB database: {e}") from e

    return client


def _establish_connection(client: InfluxV2Client) -> bool:
    start_time = time.time()
    logger.info(
        f"Try to connect to Influx DB '{client.url}' for {client.connection_time_out} seconds"
    )
    counter: int = 0
    while True:
        try:
            root = client.ping()
            if root:
                logger.info(f"Connected to Influx DB at '{client.url}' successfully.")
                return True
        except requests.exceptions.ConnectionError:
            pass
        if time.time() - start_time > client.connection_time_out:
            logger.error(
                f"Connection to Influx DB timed out after {client.connection_time_out} seconds."
            )
            return False

        counter += 1
        logger.warning(f"Retrying connection to Influx DB (attempt: {counter})")
        time.sleep(5)
