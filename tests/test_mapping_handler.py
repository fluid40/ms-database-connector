"""Unit tests for DbMappingHandler.

Tests cover file I/O, validation, persistence, and defensive copying for
the DB mapping handler.
"""

import json
from pathlib import Path

import pytest

from ms_database_connector.utils.mapping_handler import DbMappingHandler


@pytest.fixture
def valid_mapping():
    """Provide a valid, fully-filled mapping."""
    return {
        "measurement1": {
            "path.to.field1": "field",
            "path.to.field2": "tag",
            "path.to.timestamp": "timestamp",
        },
        "measurement2": {
            "another.path": "field",
        },
    }


@pytest.fixture
def partial_mapping():
    """Provide a partial mapping template with null values."""
    return {
        "measurement1": {
            "path.to.field1": None,
            "path.to.field2": None,
        },
    }


@pytest.fixture
def mapping_with_invalid_enum_value():
    """Provide a mapping with invalid enum value (not field/tag/timestamp)."""
    return {
        "measurement1": {
            "path.to.field1": "one",
        },
    }


class TestDbMappingHandlerFileHandling:
    """Tests for file loading and error handling."""

    def test_missing_file_returns_false_and_logs_error(self, tmp_path, caplog):
        """When db_mapping.json does not exist, reload returns False."""
        handler = DbMappingHandler(config_base_path=str(tmp_path))

        assert handler.is_initialized is False
        assert handler.db_mapping is None
        assert handler.get_raw() is None
        assert "not found or inaccessible" in caplog.text

    def test_invalid_json_returns_false_and_logs_error(self, tmp_path, caplog):
        """When db_mapping.json contains invalid JSON, reload returns False."""
        mapping_file = tmp_path / "db_mapping.json"
        mapping_file.write_text("{ invalid json }")

        handler = DbMappingHandler(config_base_path=str(tmp_path))

        assert handler.is_initialized is False
        assert handler.db_mapping is None
        assert handler.get_raw() is None
        assert "Invalid JSON" in caplog.text

    def test_invalid_schema_returns_false_and_logs_error(self, tmp_path, caplog):
        """When db_mapping.json has invalid schema, reload returns False."""
        mapping_file = tmp_path / "db_mapping.json"
        # Missing required measurement name nesting
        mapping_file.write_text(json.dumps({"invalid": "structure"}))

        handler = DbMappingHandler(config_base_path=str(tmp_path))

        assert handler.is_initialized is False
        assert handler.db_mapping is None
        assert "validation failed" in caplog.text.lower()

    def test_file_read_permission_error_returns_false_and_logs_error(
        self, tmp_path, caplog, monkeypatch
    ):
        """When db_mapping.json cannot be read due to permissions, reload returns False."""
        mapping_file = tmp_path / "db_mapping.json"
        mapping_file.write_text(json.dumps({"measurement": {"path": "field"}}))

        # Mock the read_text method to raise OSError
        original_read_text = Path.read_text

        def mock_read_text(self, *args, **kwargs):
            if "db_mapping.json" in str(self):
                raise OSError("Permission denied")
            return original_read_text(self, *args, **kwargs)

        monkeypatch.setattr(Path, "read_text", mock_read_text)

        handler = DbMappingHandler(config_base_path=str(tmp_path))

        assert handler.is_initialized is False
        assert handler.db_mapping is None
        assert "Failed to read" in caplog.text


class TestDbMappingHandlerValidMapping:
    """Tests for valid, fully-filled mappings."""

    def test_valid_mapping_loads_successfully(self, tmp_path, valid_mapping):
        """A valid mapping is loaded and both typed and raw mappings are set."""
        mapping_file = tmp_path / "db_mapping.json"
        mapping_file.write_text(json.dumps(valid_mapping))

        handler = DbMappingHandler(config_base_path=str(tmp_path))

        assert handler.is_initialized is True
        assert handler.db_mapping is not None
        assert handler.get_raw().model_dump() is not None
        assert handler.get_raw().model_dump() == valid_mapping

    def test_update_db_mapping_with_valid_mapping(self, tmp_path, valid_mapping):
        """Updating with a valid mapping persists to file."""
        mapping_file = tmp_path / "db_mapping.json"
        handler = DbMappingHandler(config_base_path=str(tmp_path))

        from ms_database_connector.config.db_mapping import DbMapping

        db_mapping = DbMapping.model_validate(valid_mapping)
        result = handler.update_db_mapping(db_mapping)

        assert result is True
        assert mapping_file.exists()
        saved_content = json.loads(mapping_file.read_text())
        assert saved_content == valid_mapping


class TestDbMappingHandlerUnfilledEntries:
    """Tests for partial mappings and invalid non-enum values."""

    def test_null_values_keep_raw_mapping_clear_typed_mapping(
        self, tmp_path, partial_mapping, caplog
    ):
        """Mappings with null values keep raw mapping but clear typed mapping."""
        caplog.set_level("INFO")
        mapping_file = tmp_path / "db_mapping.json"
        mapping_file.write_text(json.dumps(partial_mapping))

        handler = DbMappingHandler(config_base_path=str(tmp_path))

        assert handler.is_initialized is True
        assert handler.db_mapping is None  # Typed mapping is None
        assert (
            handler.get_raw().model_dump() == partial_mapping
        )  # Raw mapping is preserved
        assert "contains unfilled entries" in caplog.text.lower()

    def test_one_values_fail_validation_and_clear_raw_mapping(
        self, tmp_path, mapping_with_invalid_enum_value, caplog
    ):
        """Mappings with 'one' fail enum validation and keep handler uninitialized."""
        mapping_file = tmp_path / "db_mapping.json"
        mapping_file.write_text(json.dumps(mapping_with_invalid_enum_value))

        handler = DbMappingHandler(config_base_path=str(tmp_path))

        assert handler.is_initialized is False
        assert handler.db_mapping is None  # Typed mapping is None
        assert handler.get_raw() is None
        assert "validation failed" in caplog.text.lower()

    def test_update_from_raw_with_null_values(self, tmp_path, partial_mapping):
        """Updating with partial mapping via update_db_mapping_from_raw."""
        handler = DbMappingHandler(config_base_path=str(tmp_path))
        handler.initialize_db_mapping(partial_mapping)

        result = handler.update_db_mapping_from_raw(persist=False)

        assert result is False
        assert handler.is_initialized is True
        assert handler.db_mapping is None
        assert handler.get_raw().model_dump() == partial_mapping

    def test_update_from_raw_without_loaded_mapping_returns_false(self, tmp_path):
        """Updating from raw fails when no raw mapping is loaded in memory."""
        handler = DbMappingHandler(config_base_path=str(tmp_path))

        result = handler.update_db_mapping_from_raw(persist=False)

        assert result is False
        assert handler.is_initialized is False
        assert handler.db_mapping is None
        assert handler.get_raw() is None

    def test_initialize_db_mapping_creates_template(self, tmp_path):
        """initialize_db_mapping creates a template with null values."""
        mapping_file = tmp_path / "db_mapping.json"
        handler = DbMappingHandler(config_base_path=str(tmp_path))

        template = {
            "new_measurement": {
                "field1": None,
                "field2": None,
            }
        }
        result = handler.initialize_db_mapping(template)

        assert result == {"status": "mapping_initialized"}
        assert handler.is_initialized is True
        assert handler.db_mapping is None
        assert handler.get_raw().model_dump() == template
        assert mapping_file.exists()
        saved_content = json.loads(mapping_file.read_text())
        assert saved_content == template


class TestDbMappingHandlerPersistence:
    """Tests for persistence behavior."""

    def test_persistence_disabled_does_not_write_file(self, tmp_path, valid_mapping):
        """When persist_db_mapping_file_changes=False, no file is written."""
        mapping_file = tmp_path / "db_mapping.json"
        handler = DbMappingHandler(
            config_base_path=str(tmp_path),
            persist_db_mapping_file_changes=False,
        )

        from ms_database_connector.config.db_mapping import DbMapping

        db_mapping = DbMapping.model_validate(valid_mapping)
        result = handler.update_db_mapping(db_mapping)

        assert result is True
        assert not mapping_file.exists()  # File should NOT be written

    def test_reload_from_file_with_persistence_disabled(self, tmp_path, valid_mapping):
        """With persistence disabled, reload still works but won't write on update."""
        mapping_file = tmp_path / "db_mapping.json"
        mapping_file.write_text(json.dumps(valid_mapping))

        handler = DbMappingHandler(
            config_base_path=str(tmp_path),
            persist_db_mapping_file_changes=False,
        )

        assert handler.is_initialized is True
        assert handler.db_mapping is not None

    def test_persistence_enabled_writes_file(self, tmp_path, valid_mapping):
        """With persistence enabled (default), file is written."""
        mapping_file = tmp_path / "db_mapping.json"
        handler = DbMappingHandler(
            config_base_path=str(tmp_path),
            persist_db_mapping_file_changes=True,
        )

        from ms_database_connector.config.db_mapping import DbMapping

        db_mapping = DbMapping.model_validate(valid_mapping)
        result = handler.update_db_mapping(db_mapping)

        assert result is True
        assert mapping_file.exists()

    def test_persistence_failure_logs_error_and_returns_false(
        self, tmp_path, valid_mapping, monkeypatch, caplog
    ):
        """When file write fails, error is logged and False is returned."""
        handler = DbMappingHandler(config_base_path=str(tmp_path))

        from ms_database_connector.config.db_mapping import DbMapping

        db_mapping = DbMapping.model_validate(valid_mapping)

        # Mock mkdir to raise OSError
        original_mkdir = Path.mkdir

        def mock_mkdir(self, *args, **kwargs):
            if self == tmp_path:
                raise OSError("Permission denied")
            return original_mkdir(self, *args, **kwargs)

        monkeypatch.setattr(Path, "mkdir", mock_mkdir)

        result = handler.update_db_mapping(db_mapping)

        assert result is False
        assert "Failed to persist" in caplog.text


class TestDbMappingHandlerDefensiveCopy:
    """Tests for defensive copying of raw mapping."""

    def test_get_raw_returns_defensive_copy(self, tmp_path, valid_mapping):
        """get_raw returns a copy that can be modified without affecting internal state."""
        mapping_file = tmp_path / "db_mapping.json"
        mapping_file.write_text(json.dumps(valid_mapping))

        handler = DbMappingHandler(config_base_path=str(tmp_path))

        # Get the raw mapping and modify it
        raw_copy1 = handler.get_raw().model_dump()
        raw_copy1["measurement1"]["path.to.field1"] = "modified"

        # Get the raw mapping again and verify it's unchanged
        raw_copy2 = handler.get_raw().model_dump()

        assert raw_copy2["measurement1"]["path.to.field1"] == "field"
        assert raw_copy1 != raw_copy2

    def test_get_raw_returns_none_when_no_mapping(self, tmp_path):
        """get_raw returns None when no mapping is loaded."""
        handler = DbMappingHandler(config_base_path=str(tmp_path))

        assert handler.get_raw() is None

    def test_get_raw_defensive_copy_nested_dict(self, tmp_path, valid_mapping):
        """Modifying nested dicts in get_raw copy doesn't affect internal state."""
        mapping_file = tmp_path / "db_mapping.json"
        mapping_file.write_text(json.dumps(valid_mapping))

        handler = DbMappingHandler(config_base_path=str(tmp_path))

        raw_copy = handler.get_raw().model_dump()
        raw_copy["measurement1"]["path.to.field1"] = "modified"
        raw_copy["measurement1"]["new_field"] = "tag"

        # Verify internal state is unchanged
        assert "new_field" not in handler.get_raw().model_dump()["measurement1"]
        assert (
            handler.get_raw().model_dump()["measurement1"]["path.to.field1"] == "field"
        )


class TestDbMappingHandlerReloadBehavior:
    """Tests for reload and update behavior."""

    def test_reload_from_file_replaces_in_memory_mapping(self, tmp_path, valid_mapping):
        """reload_db_mapping_from_file replaces the current in-memory mapping."""
        mapping_file = tmp_path / "db_mapping.json"

        # Start with initial mapping
        initial_mapping = {
            "measurement1": {
                "path.to.field": "field",
            }
        }
        mapping_file.write_text(json.dumps(initial_mapping))
        handler = DbMappingHandler(config_base_path=str(tmp_path))

        assert (
            handler.get_raw().model_dump()["measurement1"]["path.to.field"] == "field"
        )

        # Update file with new mapping
        new_mapping = {
            "measurement2": {
                "other.path": "tag",
            }
        }
        mapping_file.write_text(json.dumps(new_mapping))
        handler.reload_db_mapping_from_file()

        assert handler.get_raw().model_dump()["measurement2"]["other.path"] == "tag"
        assert "measurement1" not in handler.get_raw().model_dump()

    def test_update_from_raw_with_persist_true_writes_file(
        self, tmp_path, valid_mapping
    ):
        """update_db_mapping_from_raw with persist=True writes to file."""
        mapping_file = tmp_path / "db_mapping.json"
        mapping_file.write_text(json.dumps(valid_mapping))
        handler = DbMappingHandler(config_base_path=str(tmp_path))
        mapping_file.unlink()

        result = handler.update_db_mapping_from_raw(persist=True)

        assert result is True
        assert mapping_file.exists()
        saved = json.loads(mapping_file.read_text())
        assert saved == valid_mapping

    def test_update_from_raw_with_persist_false_does_not_write_file(
        self, tmp_path, valid_mapping
    ):
        """update_db_mapping_from_raw with persist=False does not write to file."""
        mapping_file = tmp_path / "db_mapping.json"
        mapping_file.write_text(json.dumps(valid_mapping))
        handler = DbMappingHandler(config_base_path=str(tmp_path))
        mapping_file.unlink()

        result = handler.update_db_mapping_from_raw(persist=False)

        assert result is True
        assert not mapping_file.exists()


class TestDbMappingHandlerMultipleTimestamps:
    """Tests for timestamp validation (at most one per measurement)."""

    def test_multiple_timestamps_invalid_schema(self, tmp_path, caplog):
        """Mapping with multiple timestamp entries is invalid."""
        caplog.set_level("ERROR")
        mapping_file = tmp_path / "db_mapping.json"
        invalid_mapping = {
            "measurement1": {
                "path.to.timestamp1": "timestamp",
                "path.to.timestamp2": "timestamp",
            }
        }
        mapping_file.write_text(json.dumps(invalid_mapping))

        handler = DbMappingHandler(config_base_path=str(tmp_path))

        # Raw mapping loads, but typed validation fails (multiple timestamps).
        assert handler.is_initialized is True
        assert handler.db_mapping is None
        assert handler.get_raw() is not None
        assert "Only one mapping entry" in caplog.text

    def test_single_timestamp_valid(self, tmp_path):
        """Mapping with exactly one timestamp entry is valid."""
        mapping_file = tmp_path / "db_mapping.json"
        valid_mapping = {
            "measurement1": {
                "path.to.field": "field",
                "path.to.timestamp": "timestamp",
            }
        }
        mapping_file.write_text(json.dumps(valid_mapping))

        handler = DbMappingHandler(config_base_path=str(tmp_path))

        assert handler.is_initialized is True
        assert handler.db_mapping is not None


class TestDbMappingHandlerIsInitialized:
    """Tests for is_initialized property."""

    def test_is_initialized_true_with_valid_mapping(self, tmp_path, valid_mapping):
        """is_initialized is True when a valid mapping is loaded."""
        mapping_file = tmp_path / "db_mapping.json"
        mapping_file.write_text(json.dumps(valid_mapping))

        handler = DbMappingHandler(config_base_path=str(tmp_path))

        assert handler.is_initialized is True

    def test_is_initialized_true_with_partial_mapping(self, tmp_path, partial_mapping):
        """is_initialized is True even with partial (null value) mapping."""
        mapping_file = tmp_path / "db_mapping.json"
        mapping_file.write_text(json.dumps(partial_mapping))

        handler = DbMappingHandler(config_base_path=str(tmp_path))

        assert handler.is_initialized is True

    def test_is_initialized_false_with_missing_file(self, tmp_path):
        """is_initialized is False when no mapping file exists."""
        handler = DbMappingHandler(config_base_path=str(tmp_path))

        assert handler.is_initialized is False
