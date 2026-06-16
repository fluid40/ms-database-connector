"""Unit tests for PollingWorker core runtime loop behavior.

Tests cover the collection and write phases of the polling cycle, including
error handling and edge cases for missing dependencies.
"""

from types import SimpleNamespace

from fastapi import FastAPI
import pytest

from ms_database_connector.__main__ import PollingWorker
from ms_database_connector.dependencies import AppRuntimeDeps
from ms_database_connector.models.influx_data import InfluxDataPoint
from ms_database_connector.models.polling import PollingCyclePayload
from ms_database_connector.services.influx_service import IInfluxClient


@pytest.fixture
def build_worker(mocker):
    """Create a configurable PollingWorker test context.

    This fixture returns a builder function so each test can override only the
    dependency that matters for the scenario under test.

    Sentinel behavior:
    - `...` means "use the fixture default".
    - `None` means "explicitly missing/unavailable" (used for negative paths).

    The returned object is a ``SimpleNamespace`` with the worker and all
    relevant mocks/providers for assertions.
    """

    def _build(
        *,
        polling_interval: int = 10,
        target_references=...,
        influx_client=...,
        db_mapping=...,
        mapper_instance=...,
    ):
        """Build one PollingWorker instance and its runtime dependency graph.

        Args:
            polling_interval: Polling interval forwarded to PollingWorker.
            target_references: Value for ``app.state.target_references``.
                Use ``...`` to leave attribute unset, which exercises the
                "attribute missing" code path.
            influx_client: Value returned by ``influx_client_provider``.
                ``...`` creates a mock client, ``None`` simulates unavailable
                client.
            db_mapping: Value assigned to ``mapping_handler.db_mapping``.
                ``...`` uses a minimal valid mapping, ``None`` simulates missing
                mapping configuration.
            mapper_instance: Mapper returned by ``mapper_factory``.
                ``...`` creates a mock mapper that returns an empty batch.

        Returns:
            SimpleNamespace: Aggregated context with ``worker``, ``app``,
            providers/factories, and created mocks to keep assertions concise.
        """
        app = FastAPI()

        # Keep attribute absent when target_references is the sentinel; several
        # tests validate the fallback behavior in that exact state.
        if target_references is not ...:
            app.state.target_references = target_references

        # Server handler is passed into PollingWorker and into mapper_factory.
        server_handler = mocker.Mock()

        # Default client is a strict interface mock; None can be injected to
        # trigger "client unavailable" behavior.
        if influx_client is ...:
            influx_client = mocker.Mock(spec=IInfluxClient)

        mapping_handler = mocker.Mock()
        # Use a minimal mapping by default so collection can proceed unless a
        # test intentionally overrides this input.
        mapping_handler.db_mapping = {"measurement": {"field": "path"}} if db_mapping is ... else db_mapping

        if mapper_instance is ...:
            mapper_instance = mocker.Mock()
            # Empty batch is the safest default for generic setup paths.
            mapper_instance.map_smes_to_influx.return_value = {}

        # Providers/factories are mocks so tests can assert interaction details.
        influx_client_provider = mocker.Mock(return_value=influx_client)
        mapping_handler_provider = mocker.Mock(return_value=mapping_handler)
        mapper_factory = mocker.Mock(return_value=mapper_instance)

        runtime_deps = AppRuntimeDeps(
            config_provider=mocker.Mock(),
            mapping_handler_provider=mapping_handler_provider,
            influx_client_provider=influx_client_provider,
            server_handler_factory=mocker.Mock(),
            config_loader_factory=mocker.Mock(),
            mapper_factory=mapper_factory,
        )

        worker = PollingWorker(
            app,
            server_handler,
            polling_interval=polling_interval,
            runtime_deps=runtime_deps,
        )

        # Expose all frequently asserted components through one object.
        return SimpleNamespace(
            app=app,
            worker=worker,
            server_handler=server_handler,
            runtime_deps=runtime_deps,
            influx_client=influx_client,
            mapping_handler=mapping_handler,
            mapper_instance=mapper_instance,
            influx_client_provider=influx_client_provider,
            mapping_handler_provider=mapping_handler_provider,
            mapper_factory=mapper_factory,
        )

    return _build


class TestCollectInfluxPoints:
    """Tests for PollingWorker.collect_influx_points() method."""

    def test_returns_none_when_influx_client_missing(self, build_worker):
        """Test that collection returns None when InfluxDB client is unavailable."""
        context = build_worker(influx_client=None)
        result = context.worker.collect_influx_points()
        assert result is None
        context.influx_client_provider.assert_called_once()

    def test_returns_none_when_target_references_missing(self, build_worker):
        """Test that collection returns None when no target references are available."""
        context = build_worker(target_references=[])
        result = context.worker.collect_influx_points()
        assert result is None

    def test_returns_none_when_target_references_attribute_missing(self, build_worker):
        """Test that collection returns None when target_references attribute is not set."""
        context = build_worker(target_references=...)
        result = context.worker.collect_influx_points()
        assert result is None

    def test_returns_none_when_db_mapping_missing(self, mocker, build_worker):
        """Test that collection returns None when DB mapping is unavailable."""
        context = build_worker(target_references=[mocker.Mock()], db_mapping=None)
        result = context.worker.collect_influx_points()
        assert result is None

    def test_returns_none_when_mapper_raises_exception(self, mocker, build_worker):
        """Test that collection returns None when mapper raises an exception during mapping."""
        mapper_instance = mocker.Mock()
        mapper_instance.map_smes_to_influx.side_effect = ValueError("Mapping failed")

        context = build_worker(
            target_references=[mocker.Mock()],
            db_mapping={"test": "mapping"},
            mapper_instance=mapper_instance,
        )
        result = context.worker.collect_influx_points()
        assert result is None
        mapper_instance.map_smes_to_influx.assert_called_once()

    def test_returns_payload_when_all_dependencies_available(self, build_worker, mocker):
        """Test that collection returns PollingCyclePayload when all dependencies are available."""
        target_ref = mocker.Mock()
        data_point = InfluxDataPoint(measurement="measurement1", fields={"value": 42}, tags={"source": "test"})
        influx_points = {"measurement1": [data_point]}

        mapper_instance = mocker.Mock()
        mapper_instance.map_smes_to_influx.return_value = influx_points

        context = build_worker(
            target_references=[target_ref],
            db_mapping={"measurement1": {"field": "path.to.value"}},
            mapper_instance=mapper_instance,
        )

        result = context.worker.collect_influx_points()

        assert isinstance(result, PollingCyclePayload)
        assert result.influx_client == context.influx_client
        assert result.influx_points == influx_points
        context.mapper_factory.assert_called_once_with(
            server_handler=context.server_handler,
            db_mapping={"measurement1": {"field": "path.to.value"}},
            target_references=[target_ref],
        )


class TestWriteInfluxPoints:
    """Tests for PollingWorker.write_influx_points() method."""

    def test_calls_write_data_for_each_point(self, mocker, build_worker):
        """Test that write_data is called once for each point in the batch."""
        context = build_worker()

        # Create test data
        influx_client = context.influx_client
        influx_client.write_data.return_value = True

        points = [
            InfluxDataPoint(
                measurement="temperature",
                fields={"value": 25.5},
                tags={"location": "room1"},
                timestamp="2023-01-01T12:00:00Z",
            ),
            InfluxDataPoint(
                measurement="temperature",
                fields={"value": 26.0},
                tags={"location": "room2"},
                timestamp="2023-01-01T12:00:01Z",
            ),
        ]
        influx_points = {"temperature": points}

        # Act
        context.worker.write_influx_points(influx_client, influx_points)

        # Assert
        assert influx_client.write_data.call_count == 2
        
        # Verify each call with correct arguments
        expected_calls = [
            mocker.call(
                fields=points[0].fields,
                measurement=points[0].measurement,
                tags=points[0].tags,
                time=points[0].timestamp,
            ),
            mocker.call(
                fields=points[1].fields,
                measurement=points[1].measurement,
                tags=points[1].tags,
                time=points[1].timestamp,
            ),
        ]
        influx_client.write_data.assert_has_calls(expected_calls)

    def test_writes_points_across_multiple_measurements(self, mocker, build_worker):
        """Test that write_data is called for points across multiple measurements."""
        context = build_worker()

        # Create test data across multiple measurements
        influx_client = context.influx_client
        influx_client.write_data.return_value = True

        temp_point = InfluxDataPoint(
            measurement="temperature",
            fields={"value": 25.5},
            tags={"location": "room1"},
        )
        humidity_point = InfluxDataPoint(
            measurement="humidity",
            fields={"value": 65},
            tags={"location": "room1"},
        )
        influx_points = {
            "temperature": [temp_point],
            "humidity": [humidity_point],
        }

        # Act
        context.worker.write_influx_points(influx_client, influx_points)

        # Assert
        assert influx_client.write_data.call_count == 2

    def test_logs_failure_when_write_data_returns_false(self, mocker, caplog, build_worker):
        """Test that a failure is logged when write_data returns False."""
        context = build_worker()

        # Create test data where write fails
        influx_client = context.influx_client
        influx_client.write_data.return_value = False  # Write fails

        point = InfluxDataPoint(
            measurement="temperature",
            fields={"value": 25.5},
            tags={"location": "room1"},
        )
        influx_points = {"temperature": [point]}

        # Act
        with caplog.at_level("ERROR"):
            context.worker.write_influx_points(influx_client, influx_points)

        # Assert
        assert "Failed to write point" in caplog.text
        assert "temperature" in caplog.text

    def test_logs_each_failure_independently(self, mocker, caplog, build_worker):
        """Test that each failed write is logged separately."""
        context = build_worker()

        # Create test data with multiple failures
        influx_client = context.influx_client
        influx_client.write_data.return_value = False  # All writes fail

        points = [
            InfluxDataPoint(measurement="temperature", fields={"value": 25.5}),
            InfluxDataPoint(measurement="humidity", fields={"value": 65}),
            InfluxDataPoint(measurement="pressure", fields={"value": 1013}),
        ]
        influx_points = {
            "temperature": [points[0]],
            "humidity": [points[1]],
            "pressure": [points[2]],
        }

        # Act
        with caplog.at_level("ERROR"):
            context.worker.write_influx_points(influx_client, influx_points)

        # Assert
        assert caplog.text.count("Failed to write point") == 3

    def test_continues_writing_after_failure(self, mocker, build_worker):
        """Test that writing continues even when a point fails to write."""
        context = build_worker()

        # Create test data with mixed success/failure
        influx_client = context.influx_client
        influx_client.write_data.side_effect = [True, False, True]  # Second write fails

        points = [
            InfluxDataPoint(measurement="temp1", fields={"value": 25.5}),
            InfluxDataPoint(measurement="temp2", fields={"value": 26.0}),
            InfluxDataPoint(measurement="temp3", fields={"value": 27.0}),
        ]
        influx_points = {
            "temp1": [points[0]],
            "temp2": [points[1]],
            "temp3": [points[2]],
        }

        # Act
        context.worker.write_influx_points(influx_client, influx_points)

        # Assert - all three writes should be attempted
        assert influx_client.write_data.call_count == 3


class TestPollOnce:
    """Tests for PollingWorker._poll_once() method."""

    @pytest.mark.asyncio
    async def test_skips_write_when_collection_returns_none(self, mocker, build_worker):
        """Test that _poll_once skips write phase when collection returns None."""
        context = build_worker(influx_client=None)
        write_spy = mocker.spy(context.worker, "write_influx_points")

        # Act
        await context.worker._poll_once()

        # Assert
        write_spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_executes_write_when_collection_succeeds(self, mocker, build_worker):
        """Test that _poll_once executes write phase when collection succeeds."""
        target_ref = mocker.Mock()

        data_point = InfluxDataPoint(
            measurement="test_measurement",
            fields={"value": 42},
        )
        influx_points = {"test_measurement": [data_point]}

        mapper_instance = mocker.Mock()
        mapper_instance.map_smes_to_influx.return_value = influx_points

        context = build_worker(
            target_references=[target_ref],
            db_mapping={"measurement": {"field": "path"}},
            mapper_instance=mapper_instance,
        )
        context.influx_client.write_data.return_value = True

        # Act
        await context.worker._poll_once()

        # Assert
        assert context.influx_client.write_data.called

    @pytest.mark.asyncio
    async def test_poll_once_handles_mapper_exception_gracefully(self, mocker, build_worker):
        """Test that _poll_once returns early when mapper raises an exception."""
        target_ref = mocker.Mock()

        mapper_instance = mocker.Mock()
        mapper_instance.map_smes_to_influx.side_effect = RuntimeError("Mapper error")

        context = build_worker(
            target_references=[target_ref],
            db_mapping={"measurement": {"field": "path"}},
            mapper_instance=mapper_instance,
        )
        write_spy = mocker.spy(context.worker, "write_influx_points")

        # Act - should not raise an exception
        await context.worker._poll_once()

        # Assert - write should not have been called
        write_spy.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_once_with_empty_influx_points(self, mocker, build_worker):
        """Test that _poll_once handles empty point batch gracefully."""
        target_ref = mocker.Mock()

        # Empty points batch
        influx_points: dict[str, list[InfluxDataPoint]] = {}

        mapper_instance = mocker.Mock()
        mapper_instance.map_smes_to_influx.return_value = influx_points

        context = build_worker(
            target_references=[target_ref],
            db_mapping={"measurement": {"field": "path"}},
            mapper_instance=mapper_instance,
        )
        context.influx_client.write_data.return_value = True

        # Act - should not raise an exception
        await context.worker._poll_once()

        # Assert - write_data should not be called for empty batch
        assert not context.influx_client.write_data.called


class TestMapperIntegration:
    """Integration tests for mapper exception handling in collection."""

    def test_different_exception_types_return_none(self, mocker, build_worker):
        """Test that various exception types during mapping result in None return."""
        # Arrange
        exceptions_to_test = [
            ValueError("Value error"),
            RuntimeError("Runtime error"),
            TypeError("Type error"),
            KeyError("Key error"),
            Exception("Generic exception"),
        ]

        for exception in exceptions_to_test:
            mapper_instance = mocker.Mock()
            mapper_instance.map_smes_to_influx.side_effect = exception

            context = build_worker(
                target_references=[mocker.Mock()],
                db_mapping={"measurement": {"field": "path"}},
                mapper_instance=mapper_instance,
            )

            # Act
            result = context.worker.collect_influx_points()

            # Assert
            assert result is None, f"Expected None for {type(exception).__name__}"
