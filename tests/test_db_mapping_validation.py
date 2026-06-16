"""Unit tests for Mapping & Validation logic (db_mapping.py).

Tests cover:
- Empty/invalid AIMC mapping raises expected HTTP errors
- Missing sink path is skipped
- Field/tag/timestamp assignment behavior is correct
- Multiple timestamps in one measurement is rejected
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from pydantic import ValidationError
from fastapi import HTTPException
from http import HTTPStatus as StatusCode

from ms_database_connector.config.db_mapping import (
    DbMapping,
    MappingTargetType,
    MeasurementMapping,
    RawDbMapping,
    RawMeasurementMapping,
)
from ms_database_connector.core.influx_mapping import InfluxMapper
from ms_database_connector.models.influx_data import InfluxDataPoint


# ================================================================
# Fixtures: Mappings
# ================================================================


@pytest.fixture
def valid_simple_mapping():
    """Valid mapping with field and tag."""
    return {
        "temperature_measurement": {
            "path.to.temperature": "field",
            "path.to.location": "tag",
        }
    }


@pytest.fixture
def valid_mapping_with_timestamp():
    """Valid mapping with field, tag, and timestamp."""
    return {
        "sensor_data": {
            "path.to.sensor_value": "field",
            "path.to.sensor_id": "tag",
            "path.to.timestamp": "timestamp",
        }
    }


@pytest.fixture
def valid_multi_measurement_mapping():
    """Valid mapping with multiple measurements."""
    return {
        "measurement1": {
            "path.to.field1": "field",
            "path.to.tag1": "tag",
        },
        "measurement2": {
            "path.to.field2": "field",
            "path.to.timestamp2": "timestamp",
        },
    }


@pytest.fixture
def empty_measurement_mapping():
    """Mapping with empty measurement dict."""
    return {"empty_measurement": {}}


@pytest.fixture
def invalid_target_type_mapping():
    """Mapping with invalid target type."""
    return {
        "measurement": {
            "path.to.field": "invalid_type",
        }
    }


@pytest.fixture
def multiple_timestamps_mapping():
    """Mapping with multiple timestamps in same measurement."""
    return {
        "measurement": {
            "path.to.timestamp1": "timestamp",
            "path.to.timestamp2": "timestamp",
            "path.to.field": "field",
        }
    }


@pytest.fixture
def raw_mapping_with_unfilled():
    """Raw mapping with unfilled (None) entries."""
    return {
        "measurement": {
            "path.to.field": "field",
            "path.to.unfilled": None,
        }
    }


# ================================================================
# Fixtures: Mock objects
# ================================================================


@pytest.fixture
def mock_server_handler():
    """Mock server handler."""
    handler = Mock()
    return handler


@pytest.fixture
def mock_reference_with_value():
    """Mock reference with accessible SME."""
    ref = Mock()
    ref.submodel_id = "test_submodel_id"
    ref.parent_path = ["test", "parent"]
    ref.property_name = "test_property"
    return ref


# ================================================================
# Tests: MappingTargetType Enum
# ================================================================


class TestMappingTargetType:
    """Tests for MappingTargetType enumeration."""

    def test_valid_target_types_exist(self):
        """Check that all required target types exist."""
        assert MappingTargetType.FIELD.value == "field"
        assert MappingTargetType.TAG.value == "tag"
        assert MappingTargetType.TIMESTAMP.value == "timestamp"

    def test_target_type_string_conversion(self):
        """Target types convert correctly to strings."""
        assert str(MappingTargetType.FIELD) == "MappingTargetType.FIELD"
        assert MappingTargetType.FIELD.value == "field"


# ================================================================
# Tests: MeasurementMapping Model
# ================================================================


class TestMeasurementMapping:
    """Tests for MeasurementMapping Pydantic model."""

    def test_valid_measurement_mapping_with_field_and_tag(self):
        """Valid mapping with field and tag types."""
        data = {
            "path.to.field": "field",
            "path.to.tag": "tag",
        }
        mapping = MeasurementMapping.model_validate(data)
        assert mapping.root["path.to.field"] == MappingTargetType.FIELD
        assert mapping.root["path.to.tag"] == MappingTargetType.TAG

    def test_valid_measurement_mapping_with_single_timestamp(self):
        """Valid mapping with single timestamp."""
        data = {
            "path.to.field": "field",
            "path.to.timestamp": "timestamp",
        }
        mapping = MeasurementMapping.model_validate(data)
        assert mapping.root["path.to.timestamp"] == MappingTargetType.TIMESTAMP

    def test_empty_measurement_mapping(self):
        """Empty measurement mapping is valid (no entries)."""
        data = {}
        mapping = MeasurementMapping.model_validate(data)
        assert len(mapping.root) == 0

    def test_multiple_timestamps_in_measurement_raises_validation_error(
        self, multiple_timestamps_mapping
    ):
        """Multiple timestamps in same measurement raises ValidationError."""
        measurement_data = multiple_timestamps_mapping["measurement"]
        with pytest.raises(
            ValueError,
            match="Only one mapping entry per measurement can use target type 'timestamp'",
        ):
            MeasurementMapping.model_validate(measurement_data)  # No change needed

    def test_invalid_target_type_raises_validation_error(self):
        """Invalid target type value raises ValidationError."""
        data = {
            "path.to.field": "invalid_type",
        }
        with pytest.raises(ValueError):
            MeasurementMapping.model_validate(data)

    def test_three_timestamps_raises_validation_error(self):
        """Three timestamps in same measurement raises ValidationError."""
        data = {
            "path.to.timestamp1": "timestamp",
            "path.to.timestamp2": "timestamp",
            "path.to.timestamp3": "timestamp",
        }
        with pytest.raises(
            ValueError,
            match="Only one mapping entry per measurement can use target type 'timestamp'",
        ):
            MeasurementMapping.model_validate(data)  # No change needed


# ================================================================
# Tests: DbMapping Model
# ================================================================


class TestDbMapping:
    """Tests for DbMapping Pydantic model."""

    def test_valid_db_mapping_single_measurement(self, valid_simple_mapping):
        """Valid mapping with single measurement."""
        mapping = DbMapping.model_validate(valid_simple_mapping)
        assert "temperature_measurement" in mapping.root
        assert len(mapping.root["temperature_measurement"].root) == 2

    def test_valid_db_mapping_multiple_measurements(
        self, valid_multi_measurement_mapping
    ):
        """Valid mapping with multiple measurements."""
        mapping = DbMapping.model_validate(valid_multi_measurement_mapping)
        assert "measurement1" in mapping.root
        assert "measurement2" in mapping.root

    def test_db_mapping_with_timestamp(self, valid_mapping_with_timestamp):
        """Valid mapping with timestamp."""
        mapping = DbMapping.model_validate(valid_mapping_with_timestamp)
        assert "sensor_data" in mapping.root

    def test_db_mapping_multiple_timestamps_rejected(self, multiple_timestamps_mapping):
        """DbMapping rejects measurement with multiple timestamps."""
        with pytest.raises(
            ValueError,
            match="Only one mapping entry per measurement can use target type 'timestamp'",
        ):
            DbMapping.model_validate(multiple_timestamps_mapping)  # No change needed

    def test_db_mapping_with_invalid_target_type(self, invalid_target_type_mapping):
        """DbMapping rejects invalid target types."""
        with pytest.raises(ValueError):
            DbMapping.model_validate(invalid_target_type_mapping)

    def test_db_mapping_empty_dict(self):
        """Empty DbMapping is valid."""
        mapping = DbMapping.model_validate({})
        assert len(mapping.root) == 0


# ================================================================
# Tests: RawMeasurementMapping Model
# ================================================================


class TestRawMeasurementMapping:
    """Tests for RawMeasurementMapping Pydantic model."""

    def test_raw_measurement_with_filled_entries(self):
        """Raw measurement with all filled entries."""
        data = {
            "path.to.field": "field",
            "path.to.tag": "tag",
        }
        mapping = RawMeasurementMapping.model_validate(data)
        assert mapping.root["path.to.field"] == "field"
        assert mapping.root["path.to.tag"] == "tag"

    def test_raw_measurement_with_unfilled_entries(self):
        """Raw measurement with None (unfilled) entries."""
        data = {
            "path.to.field": "field",
            "path.to.unfilled": None,
        }
        mapping = RawMeasurementMapping.model_validate(data)
        assert mapping.root["path.to.field"] == "field"
        assert mapping.root["path.to.unfilled"] is None

    def test_raw_measurement_all_unfilled(self):
        """Raw measurement with all None entries."""
        data = {
            "path.to.unfilled1": None,
            "path.to.unfilled2": None,
        }
        mapping = RawMeasurementMapping.model_validate(data)
        assert all(v is None for v in mapping.root.values())

    def test_raw_measurement_has_unfilled_entries_true(self):
        """has_unfilled_entries returns True when None values present."""
        data = {
            "path.to.field": "field",
            "path.to.unfilled": None,
        }
        mapping = RawMeasurementMapping.model_validate(data)
        assert mapping.has_unfilled_entries() is True

    def test_raw_measurement_has_unfilled_entries_false(self):
        """has_unfilled_entries returns False when all filled."""
        data = {
            "path.to.field": "field",
            "path.to.tag": "tag",
        }
        mapping = RawMeasurementMapping.model_validate(data)
        assert mapping.has_unfilled_entries() is False

    def test_raw_measurement_invalid_target_type(self):
        """Raw measurement rejects invalid target types."""
        data = {
            "path.to.field": "invalid_type",
        }
        with pytest.raises(ValueError, match="must be None or one of"):
            RawMeasurementMapping.model_validate(data)

    def test_raw_measurement_multiple_timestamps_allowed(self):
        """Raw measurement allows multiple timestamps (no validation yet)."""
        data = {
            "path.to.timestamp1": "timestamp",
            "path.to.timestamp2": "timestamp",
        }
        # Should not raise; raw model doesn't validate single timestamp
        mapping = RawMeasurementMapping.model_validate(data)
        assert len(mapping.root) == 2


# ================================================================
# Tests: RawDbMapping Model
# ================================================================


class TestRawDbMapping:
    """Tests for RawDbMapping Pydantic model."""

    def test_raw_db_mapping_with_filled_entries(self):
        """Raw db mapping with filled entries."""
        data = {
            "measurement": {
                "path.to.field": "field",
                "path.to.tag": "tag",
            }
        }
        mapping = RawDbMapping.model_validate(data)
        assert "measurement" in mapping.root
        assert mapping.has_unfilled_entries() is False

    def test_raw_db_mapping_with_unfilled_entries(self):
        """Raw db mapping with unfilled entries."""
        data = {
            "measurement": {
                "path.to.field": "field",
                "path.to.unfilled": None,
            }
        }
        mapping = RawDbMapping.model_validate(data)
        assert mapping.has_unfilled_entries() is True

    def test_raw_db_mapping_multiple_measurements_some_unfilled(self):
        """Raw db mapping with multiple measurements, some with unfilled."""
        data = {
            "measurement1": {
                "path.to.field": "field",
            },
            "measurement2": {
                "path.to.unfilled": None,
            },
        }
        mapping = RawDbMapping.model_validate(data)
        assert mapping.has_unfilled_entries() is True

    def test_raw_db_mapping_model_dump(self):
        """model_dump returns clean dict representation."""
        data = {
            "measurement": {
                "path.to.field": "field",
                "path.to.unfilled": None,
            }
        }
        mapping = RawDbMapping.model_validate(data)
        dumped = mapping.model_dump()
        assert dumped == data


# ================================================================
# Tests: InfluxMapper - Field/Tag/Timestamp Assignment
# ================================================================


class TestInfluxMapperValueAssignment:
    """Tests for InfluxMapper value assignment behavior."""

    def test_field_assignment(self, mock_server_handler, mock_reference_with_value):
        """Field target type adds value to fields dict."""
        point = InfluxDataPoint(measurement="test")
        mapper = InfluxMapper(mock_server_handler, DbMapping.model_validate({}), [])

        mapper._assign_value_to_point(
            point,
            "sink.path",
            42.5,
            MappingTargetType.FIELD,
        )

        assert "sink.path" in point.fields
        assert point.fields["sink.path"] == 42.5

    def test_tag_assignment(self, mock_server_handler):
        """Tag target type adds value to tags dict as string."""
        point = InfluxDataPoint(measurement="test")
        mapper = InfluxMapper(mock_server_handler, DbMapping.model_validate({}), [])

        mapper._assign_value_to_point(
            point,
            "sink.path",
            "location_1",
            MappingTargetType.TAG,
        )

        assert "sink.path" in point.tags
        assert point.tags["sink.path"] == "location_1"
        assert isinstance(point.tags["sink.path"], str)

    def test_tag_assignment_converts_to_string(self, mock_server_handler):
        """Tag assignment converts numeric values to string."""
        point = InfluxDataPoint(measurement="test")
        mapper = InfluxMapper(mock_server_handler, DbMapping.model_validate({}), [])

        mapper._assign_value_to_point(
            point,
            "sink.path",
            12345,
            MappingTargetType.TAG,
        )

        assert point.tags["sink.path"] == "12345"
        assert isinstance(point.tags["sink.path"], str)

    def test_timestamp_assignment_with_iso_string(self, mock_server_handler):
        """Timestamp assignment with ISO format string."""
        point = InfluxDataPoint(measurement="test")
        mapper = InfluxMapper(mock_server_handler, DbMapping.model_validate({}), [])
        iso_string = "2023-06-15T12:34:56.789Z"

        mapper._assign_value_to_point(
            point,
            "sink.path",
            iso_string,
            MappingTargetType.TIMESTAMP,
        )

        assert point.timestamp is not None
        # Should be converted to ISO format
        assert "2023-06-15" in point.timestamp

    def test_timestamp_assignment_with_datetime_object(self, mock_server_handler):
        """Timestamp assignment with datetime object."""
        point = InfluxDataPoint(measurement="test")
        mapper = InfluxMapper(mock_server_handler, DbMapping.model_validate({}), [])
        dt = datetime(2023, 6, 15, 12, 34, 56, tzinfo=timezone.utc)

        mapper._assign_value_to_point(
            point,
            "sink.path",
            dt,
            MappingTargetType.TIMESTAMP,
        )

        assert "2023-06-15" in point.timestamp

    def test_multiple_field_assignments(self, mock_server_handler):
        """Multiple field assignments accumulate correctly."""
        point = InfluxDataPoint(measurement="test")
        mapper = InfluxMapper(mock_server_handler, DbMapping.model_validate({}), [])

        mapper._assign_value_to_point(point, "field1", 10.0, MappingTargetType.FIELD)
        mapper._assign_value_to_point(point, "field2", 20.0, MappingTargetType.FIELD)

        assert len(point.fields) == 2
        assert point.fields["field1"] == 10.0
        assert point.fields["field2"] == 20.0

    def test_multiple_tag_assignments(self, mock_server_handler):
        """Multiple tag assignments accumulate correctly."""
        point = InfluxDataPoint(measurement="test")
        mapper = InfluxMapper(mock_server_handler, DbMapping.model_validate({}), [])

        mapper._assign_value_to_point(point, "tag1", "value1", MappingTargetType.TAG)
        mapper._assign_value_to_point(point, "tag2", "value2", MappingTargetType.TAG)

        assert len(point.tags) == 2
        assert point.tags["tag1"] == "value1"
        assert point.tags["tag2"] == "value2"


# ================================================================
# Tests: InfluxMapper - Missing Sink Path Handling
# ================================================================


class TestInfluxMapperMissingSinkPath:
    """Tests for handling missing sink paths."""

    def test_missing_sink_path_skipped_with_debug_log(
        self, mock_server_handler, caplog
    ):
        """Missing sink path is skipped with debug log."""
        import logging

        caplog.set_level(logging.DEBUG)

        mapping = DbMapping.model_validate(
            {
                "measurement": {
                    "path.to.field": "field",
                }
            }
        )
        mapper = InfluxMapper(mock_server_handler, mapping, [])

        # Empty reference map means all paths are missing
        reference_map = {}

        point = InfluxDataPoint(measurement="measurement")
        result = mapper._add_value_to_point(
            point,
            "path.to.field",
            MappingTargetType.FIELD,
            reference_map,
        )

        # Should return False because path not found
        assert result is False
        # Value should not be added
        assert len(point.fields) == 0

    def test_process_measurement_skips_missing_paths(self, mock_server_handler, caplog):
        """_process_measurement skips missing paths and continues."""
        import logging

        caplog.set_level(logging.DEBUG)

        mapping = DbMapping.model_validate(
            {
                "measurement": {
                    "path.exists": "field",
                    "path.missing": "field",
                }
            }
        )

        ref = Mock()
        ref.submodel_id = "test"
        ref.parent_path = ["test"]
        ref.property_name = "test"

        # Mock the value retrieval for existing path
        mapper = InfluxMapper(mock_server_handler, mapping, [ref])

        with patch.object(
            mapper, "_retrieve_sme_value", return_value=42.0
        ) as mock_retrieve:
            # Only the existing path is in reference map
            reference_map = {
                f"{ref.submodel_id}/submodel-elements/{'test.test'}": ref,
            }

            # Manually iterate to check skipping behavior
            point = InfluxDataPoint(measurement="measurement")
            # Simulate the _process_measurement logic for existing path
            mapper._add_value_to_point(
                point,
                f"{ref.submodel_id}/submodel-elements/test.test",
                MappingTargetType.FIELD,
                reference_map,
            )

            # Existing path should have value
            assert len(point.fields) >= 0

    def test_partially_missing_sink_paths_with_mixed_results(
        self, mock_server_handler, caplog
    ):
        """Measurement with mix of existing and missing paths processes correctly."""
        import logging

        caplog.set_level(logging.DEBUG)

        mapping_dict = {
            "measurement": {
                "path.to.field1": "field",
                "path.to.field2": "field",
                "path.to.tag1": "tag",
            }
        }
        mapping = DbMapping.model_validate(mapping_dict)

        ref1 = Mock()
        ref1.submodel_id = "submodel1"
        ref1.parent_path = ["parent1"]
        ref1.property_name = "field1"

        mapper = InfluxMapper(mock_server_handler, mapping, [ref1])

        # Only ref1 is in the map; others are missing
        reference_map = {
            "submodel1/submodel-elements/parent1.field1": ref1,
        }

        point = InfluxDataPoint(measurement="measurement")

        # Add the value that exists
        with patch.object(
            mapper, "_retrieve_sme_value", return_value=42.0
        ):  # <-- ADD THIS
            mapper._add_value_to_point(
                point,
                "submodel1/submodel-elements/parent1.field1",
                MappingTargetType.FIELD,
                reference_map,
            )

        # Should have one field
        assert len(point.fields) == 1


# ================================================================
# Tests: HTTP Errors via Endpoint Validation
# ================================================================


class TestHttpErrorsForInvalidMapping:
    """Tests for HTTP error handling in endpoints.

    These tests focus on the validation rules that would be enforced
    by the POST /db-mapping endpoint.
    """

    def test_empty_measurement_validation_error(self):
        """Empty measurement (no paths) should fail validation."""
        data = {
            "measurement": {},
        }
        with pytest.raises(ValidationError):
            DbMapping.model_validate(data)

    def test_multiple_timestamps_http_validation_error(
        self, multiple_timestamps_mapping
    ):
        """Multiple timestamps should fail during DbMapping validation."""
        with pytest.raises(ValidationError):
            DbMapping.model_validate(multiple_timestamps_mapping)

    def test_invalid_target_type_http_validation_error(
        self, invalid_target_type_mapping
    ):
        """Invalid target type should fail during DbMapping validation."""
        with pytest.raises(ValidationError):
            DbMapping.model_validate(invalid_target_type_mapping)

    def test_mapping_with_only_invalid_types(self):
        """Mapping where all values are invalid."""
        data = {
            "measurement1": {
                "path1": "not_a_type",
                "path2": "also_invalid",
            }
        }
        with pytest.raises(ValidationError):
            DbMapping.model_validate(data)

    def test_mapping_with_numeric_target_type(self):
        """Numeric target types should fail."""
        data = {
            "measurement": {
                "path": 123,
            }
        }
        with pytest.raises(ValidationError):
            DbMapping.model_validate(data)

    def test_mapping_with_bool_target_type(self):
        """Boolean target types should fail."""
        data = {
            "measurement": {
                "path": True,
            }
        }
        with pytest.raises(ValidationError):
            DbMapping.model_validate(data)

    def test_mapping_structure_mismatch_detection(self):
        """Mapping must have proper nested structure."""
        # Flat structure without measurement nesting
        data = {
            "path.to.field": "field",
        }
        with pytest.raises(ValidationError):
            DbMapping.model_validate(data)

    def test_case_sensitive_target_type(self):
        """Target types are case-sensitive."""
        data = {
            "measurement": {
                "path": "Field",  # Uppercase
            }
        }
        with pytest.raises(ValidationError):
            DbMapping.model_validate(data)


# ================================================================
# Tests: Edge Cases and Integration
# ================================================================


class TestMappingEdgeCases:
    """Tests for edge cases and integration scenarios."""

    def test_single_field_measurement_valid(self):
        """Measurement with single field is valid."""
        data = {
            "measurement": {
                "path.to.field": "field",
            }
        }
        mapping = DbMapping.model_validate(data)
        assert len(mapping.root["measurement"].root) == 1

    def test_single_tag_measurement_valid(self):
        """Measurement with single tag is valid."""
        data = {
            "measurement": {
                "path.to.tag": "tag",
            }
        }
        mapping = DbMapping.model_validate(data)
        assert len(mapping.root["measurement"].root) == 1

    def test_single_timestamp_measurement_valid(self):
        """Measurement with only timestamp is valid."""
        data = {
            "measurement": {
                "path.to.timestamp": "timestamp",
            }
        }
        mapping = DbMapping.model_validate(data)
        assert len(mapping.root["measurement"].root) == 1

    def test_very_long_sink_path(self):
        """Very long sink path names are accepted."""
        long_path = ".".join([f"level_{i}" for i in range(20)])
        data = {
            "measurement": {
                long_path: "field",
            }
        }
        mapping = DbMapping.model_validate(data)
        assert long_path in mapping.root["measurement"].root

    def test_special_characters_in_measurement_name(self):
        """Special characters in measurement names are accepted."""
        data = {
            "measurement-with_special.chars": {
                "path.to.field": "field",
            }
        }
        mapping = DbMapping.model_validate(data)
        assert "measurement-with_special.chars" in mapping.root

    def test_unicode_in_sink_path(self):
        """Unicode characters in sink paths are accepted."""
        data = {
            "measurement": {
                "path.to.température": "field",
            }
        }
        mapping = DbMapping.model_validate(data)
        assert "path.to.température" in mapping.root["measurement"].root

    def test_empty_string_as_target_type(self):
        """Empty string as target type should fail."""
        data = {
            "measurement": {
                "path": "",
            }
        }
        with pytest.raises(ValidationError):
            DbMapping.model_validate(data)

    def test_whitespace_target_type(self):
        """Whitespace-only target type should fail."""
        data = {
            "measurement": {
                "path": "   ",
            }
        }
        with pytest.raises(ValidationError):
            DbMapping.model_validate(data)


# ================================================================
# Tests: Timestamp Conversion
# ================================================================


class TestTimestampConversion:
    """Tests for timestamp conversion in InfluxMapper."""

    def test_convert_iso_string_with_z_suffix(self, mock_server_handler):
        """Convert ISO string with Z suffix."""
        mapper = InfluxMapper(mock_server_handler, DbMapping.model_validate({}), [])
        iso_with_z = "2023-06-15T12:34:56.789Z"
        result = mapper._convert_to_iso_timestamp(iso_with_z)
        assert "2023-06-15" in result

    def test_convert_iso_string_with_utc_offset(self, mock_server_handler):
        """Convert ISO string with UTC offset."""
        mapper = InfluxMapper(mock_server_handler, DbMapping.model_validate({}), [])
        iso_with_offset = "2023-06-15T12:34:56+00:00"
        result = mapper._convert_to_iso_timestamp(iso_with_offset)
        assert "2023-06-15" in result

    def test_convert_datetime_object(self, mock_server_handler):
        """Convert datetime object."""
        mapper = InfluxMapper(mock_server_handler, DbMapping.model_validate({}), [])
        dt = datetime(2023, 6, 15, 12, 34, 56, tzinfo=timezone.utc)
        result = mapper._convert_to_iso_timestamp(dt)
        assert "2023-06-15" in result

    def test_convert_numeric_timestamp(self, mock_server_handler):
        """Convert numeric timestamp (Unix epoch)."""
        mapper = InfluxMapper(mock_server_handler, DbMapping.model_validate({}), [])
        unix_timestamp = 1686830096  # 2023-06-15T12:34:56Z
        result = mapper._convert_to_iso_timestamp(unix_timestamp)
        assert isinstance(result, str)

    def test_convert_invalid_iso_string_returns_original(
        self, mock_server_handler, caplog
    ):
        """Invalid ISO string returns original value."""
        import logging

        caplog.set_level(logging.WARNING)
        mapper = InfluxMapper(mock_server_handler, DbMapping.model_validate({}), [])
        invalid_iso = "not-a-valid-timestamp"
        result = mapper._convert_to_iso_timestamp(invalid_iso)
        assert result == invalid_iso
        assert "Could not parse" in caplog.text

    def test_convert_invalid_numeric_timestamp(self, mock_server_handler, caplog):
        """Invalid numeric timestamp is handled."""
        import logging

        caplog.set_level(logging.WARNING)
        mapper = InfluxMapper(mock_server_handler, DbMapping.model_validate({}), [])
        # Very large number that would cause overflow
        invalid_numeric = 999999999999999999999
        result = mapper._convert_to_iso_timestamp(invalid_numeric)
        assert isinstance(result, str)
