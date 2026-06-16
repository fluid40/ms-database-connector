"""Mapping configuration loading, validation, and in-memory handling."""

import json
import logging
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

from ms_database_connector.config.db_mapping import DbMapping, RawDbMapping
from ms_database_connector.models.constants import CONFIG_BASE_PATH

_logger = logging.getLogger(__name__)


class DbMappingHandler:
    """Load, validate, and manage AIMC-to-InfluxDB field mappings.

    Maintains mapping in memory and optionally persists updates to disk.
    Supports both full validated mappings and partial templates with null values.
    Invalid mapping files are logged and ignored to allow manual correction.

    Attributes:
        is_initialized: Property indicating whether a mapping template or validated
            mapping is currently loaded.
        db_mapping: Property providing typed mapping when fully validated
            (None for partial templates).
    """

    def __init__(
        self,
        config_base_path: str = CONFIG_BASE_PATH,
        persist_db_mapping_file_changes: bool = True,
    ):
        self._db_mapping_file = Path(config_base_path) / "db_mapping.json"
        self._persist_db_mapping_file_changes = persist_db_mapping_file_changes
        self._db_mapping: DbMapping | None = None
        self._raw_db_mapping: RawDbMapping | None = None
        self.reload_db_mapping_from_file()

    @property
    def is_initialized(self) -> bool:
        """Return whether a mapping (template or fully validated) is available."""
        return self._raw_db_mapping is not None

    @property
    def db_mapping(self) -> DbMapping | None:
        """Return the typed mapping when available.

        This is ``None`` when only a template (with ``None`` values) is stored.
        """
        return self._db_mapping

    def get_raw(self) -> RawDbMapping | None:
        """Return a defensive copy of the currently stored raw mapping."""
        if self._raw_db_mapping is None:
            return None
        return deepcopy(self._raw_db_mapping)

    def reload_db_mapping_from_file(self) -> bool:
        """Reload db mapping from disk.

        Reads db_mapping.json and validates it to match the RawDbMapping model. Invalid or missing files
        are logged but do not raise exceptions, allowing recovery via API.

        Returns:
            bool: True if a fully-validated mapping was loaded, False if file is
                missing, invalid, or contains unfilled entries.
        """
        if not self._db_mapping_file.exists() or not self._db_mapping_file.is_file():
            _logger.error(
                "DB mapping file '%s' not found or inaccessible.",
                self._db_mapping_file,
            )
            self._db_mapping = None
            self._raw_db_mapping = None
            return False

        try:
            raw_mapping_json = json.loads(
                self._db_mapping_file.read_text(encoding="utf-8")
            )
            self._raw_db_mapping = RawDbMapping.model_validate(raw_mapping_json)

        except json.JSONDecodeError as exc:
            _logger.error(
                "Invalid JSON in DB mapping file '%s': %s",
                self._db_mapping_file,
                exc,
            )
            self._db_mapping = None
            self._raw_db_mapping = None
            return False
        except OSError as exc:
            _logger.error(
                "Failed to read DB mapping file '%s': %s",
                self._db_mapping_file,
                exc,
            )
            self._db_mapping = None
            self._raw_db_mapping = None
            return False
        except ValidationError as exc:
            _logger.error(
                "Validation failed for DB mapping file '%s': %s",
                self._db_mapping_file,
                exc,
            )
            self._db_mapping = None
            self._raw_db_mapping = None
            return False

        return self.update_db_mapping_from_raw(persist=False)

    def update_db_mapping(self, db_mapping: DbMapping) -> bool:
        """Store and persist a validated db mapping.

        Serializes the typed mapping to raw model format and persists to disk.

        Args:
            db_mapping: A validated DbMapping object.

        Returns:
            bool: True if mapping was updated and persisted successfully,
                False if persistence fails.
        """
        serialized_mapping: dict[str, dict[str, str | None]] = {
            measurement_name: {
                sink_path: target_type.value
                for sink_path, target_type in measurement_mapping.root.items()
            }
            for measurement_name, measurement_mapping in db_mapping.root.items()
        }

        # Convert to RawDbMapping model
        raw_db_mapping = RawDbMapping.model_validate(serialized_mapping)

        self._db_mapping = db_mapping
        self._raw_db_mapping = raw_db_mapping

        try:
            self._persist_db_mapping(raw_db_mapping)
        except OSError as exc:
            _logger.error(
                "Failed to persist DB mapping to '%s': %s",
                self._db_mapping_file,
                exc,
            )
            return False

        return True

    def update_db_mapping_from_raw(
        self,
        persist: bool = True,
    ) -> bool:
        """Validate if raw DB mapping is complete and update typed mapping.

        Args:
            persist: If True, persist the mapping to disk (default: True).

        Returns:
            bool: True if valid and stored/persisted successfully, False otherwise.
        """
        if self._raw_db_mapping is None:
            _logger.error("No raw DB mapping available to update from.")
            self._db_mapping = None
            return False

        if self._raw_db_mapping.has_unfilled_entries():
            _logger.info(
                "DB mapping contains unfilled entries (null values). "
                "Keeping raw template and clearing typed mapping."
            )
            self._db_mapping = None
            return False

        try:
            db_mapping = DbMapping.model_validate(self._raw_db_mapping.model_dump())
        except ValidationError as exc:
            _logger.error("DB mapping validation failed: %s", exc)
            self._db_mapping = None
            return False

        self._db_mapping = db_mapping

        if not persist:
            return True

        try:
            self._persist_db_mapping(self._raw_db_mapping)
        except OSError as exc:
            _logger.error(
                "Failed to persist DB mapping to '%s': %s",
                self._db_mapping_file,
                exc,
            )
            return False

        return True

    def initialize_db_mapping(self, mapping_template: dict) -> dict:
        """Create and persist an unfilled DB mapping template.

        Stores a DB mapping structure with None values for later completion.
        Used when initializing DB mappings based on detected AIMC measurements.

        Args:
            mapping_template: Template dict with structure {"measurement": {"path": None}}.

        Returns:
            dict: Status response with key 'status': 'mapping_initialized'.
        """
        self._db_mapping = None

        try:
            self._raw_db_mapping = RawDbMapping.model_validate(mapping_template)
        except ValidationError as exc:
            self._raw_db_mapping = None
            return {"status": "Invalid mapping structure", "details": exc.json()}

        self._persist_db_mapping(self._raw_db_mapping)
        return {"status": "mapping_initialized"}

    def _persist_db_mapping(self, raw_mapping: RawDbMapping) -> None:
        """Persist a DB mapping structure to disk as formatted JSON.

        Creates parent directories if needed. If persistence is disabled via
        constructor, logs and returns without writing.

        Args:
            raw_mapping: The RawDbMapping model instance to persist.

        Raises:
            OSError: If file writing fails.
        """
        if not self._persist_db_mapping_file_changes:
            _logger.debug(
                "Skipping persistence of DB mapping configuration because "
                "persist_db_mapping_file_changes is disabled."
            )
            return

        self._db_mapping_file.parent.mkdir(parents=True, exist_ok=True)
        self._db_mapping_file.write_text(
            json.dumps(raw_mapping.model_dump(), indent=4, sort_keys=False),
            encoding="utf-8",
        )
