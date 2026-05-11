"""Mapping configuration loading, validation, and in-memory handling."""

import json
import logging
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

from ms_database_connector.config.mapping_configuration import MappingConfiguration
from ms_database_connector.models.constants import CONFIG_BASE_PATH

_logger = logging.getLogger(__name__)


class MappingConfigurationHandler:
    """Load and manage the SME-to-DB mapping configuration.

    The handler keeps the latest mapping in memory and can persist updates to disk.
    Invalid mapping files are logged and ignored so they can be corrected and reloaded.
    """

    def __init__(self, config_base_path: str = CONFIG_BASE_PATH):
        self._mapping_file = Path(config_base_path) / "mapping_configuration.json"
        self._mapping_configuration: MappingConfiguration | None = None
        self._raw_mapping: dict[str, dict[str, str | None]] | None = None
        self.reload_mapping_from_file()

    @property
    def is_initialized(self) -> bool:
        """Return whether a mapping (template or fully validated) is available."""
        return self._raw_mapping is not None

    @property
    def mapping_configuration(self) -> MappingConfiguration | None:
        """Return the typed mapping when available.

        This is ``None`` when only a template (with ``null`` values) is stored.
        """
        return self._mapping_configuration

    def get_raw(self) -> dict[str, dict[str, str | None]] | None:
        """Return a defensive copy of the currently stored raw mapping."""
        if self._raw_mapping is None:
            return None
        return deepcopy(self._raw_mapping)

    def reload_mapping_from_file(self) -> bool:
        """Reload mapping_configuration.json from disk.

        Returns ``True`` when a valid filled mapping was loaded, otherwise ``False``.
        Invalid files do not raise and are only logged.
        """
        if not self._mapping_file.exists() or not self._mapping_file.is_file():
            _logger.error(
                "Mapping configuration file '%s' not found or inaccessible.",
                self._mapping_file,
            )
            self._mapping_configuration = None
            self._raw_mapping = None
            return False

        try:
            raw_mapping = json.loads(self._mapping_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            _logger.error(
                "Invalid JSON in mapping configuration file '%s': %s",
                self._mapping_file,
                exc,
            )
            self._mapping_configuration = None
            self._raw_mapping = None
            return False
        except OSError as exc:
            _logger.error(
                "Failed to read mapping configuration file '%s': %s",
                self._mapping_file,
                exc,
            )
            self._mapping_configuration = None
            self._raw_mapping = None
            return False

        return self.update_mapping_from_raw(raw_mapping, persist=False)

    def update_mapping(self, mapping_configuration: MappingConfiguration) -> bool:
        """Store and persist a validated mapping configuration."""
        serialized_mapping: dict[str, dict[str, str | None]] = {
            measurement_name: {
                sink_path: target_type.value
                for sink_path, target_type in measurement_mapping.root.items()
            }
            for measurement_name, measurement_mapping in mapping_configuration.root.items()
        }

        self._mapping_configuration = mapping_configuration
        self._raw_mapping = serialized_mapping

        try:
            self._persist_mapping(serialized_mapping)
        except OSError as exc:
            _logger.error(
                "Failed to persist mapping configuration to '%s': %s",
                self._mapping_file,
                exc,
            )
            return False

        return True

    def update_mapping_from_raw(
        self,
        raw_mapping: dict,
        persist: bool = True,
    ) -> bool:
        """Validate raw mapping data and store it.

        Invalid mappings are logged and return ``False``. No exception is raised.
        """
        if self._contains_unfilled_entries(raw_mapping):
            _logger.error(
                "Mapping validation failed: each mapping entry needs a target type and "
                "no value may remain 'one' or null."
            )
            self._mapping_configuration = None
            self._raw_mapping = (
                deepcopy(raw_mapping) if isinstance(raw_mapping, dict) else None
            )
            return False

        try:
            mapping_configuration = MappingConfiguration.model_validate(raw_mapping)
        except ValidationError as exc:
            _logger.error("Mapping validation failed: %s", exc)
            self._mapping_configuration = None
            self._raw_mapping = (
                deepcopy(raw_mapping) if isinstance(raw_mapping, dict) else None
            )
            return False

        # Keep one source of truth in memory as plain dict for easy API responses.
        self._raw_mapping = {
            measurement_name: {
                sink_path: target_type.value
                for sink_path, target_type in measurement_mapping.root.items()
            }
            for measurement_name, measurement_mapping in mapping_configuration.root.items()
        }
        self._mapping_configuration = mapping_configuration

        if not persist:
            return True

        try:
            self._persist_mapping(self._raw_mapping)
        except OSError as exc:
            _logger.error(
                "Failed to persist mapping configuration to '%s': %s",
                self._mapping_file,
                exc,
            )
            return False

        return True

    def initialize_mapping(self, mapping_template: dict) -> dict:
        """Store and persist an unfilled mapping template.

        The template may contain ``null`` values and is kept as raw structure only.
        """
        self._mapping_configuration = None
        self._raw_mapping = deepcopy(mapping_template)

        self._persist_mapping(self._raw_mapping)
        return {"status": "mapping_initialized"}

    def _persist_mapping(self, raw_mapping: dict) -> None:
        """Persist raw mapping structure to disk as JSON."""
        self._mapping_file.parent.mkdir(parents=True, exist_ok=True)
        self._mapping_file.write_text(
            json.dumps(raw_mapping, indent=4, sort_keys=False),
            encoding="utf-8",
        )

    @staticmethod
    def _contains_unfilled_entries(raw_mapping: dict) -> bool:
        """Check for placeholder/unfilled values in a raw mapping payload."""
        if not isinstance(raw_mapping, dict):
            return True

        for measurement_mapping in raw_mapping.values():
            if not isinstance(measurement_mapping, dict):
                return True
            for target_type in measurement_mapping.values():
                if target_type is None:
                    return True
                if (
                    isinstance(target_type, str)
                    and target_type.strip().lower() == "one"
                ):
                    return True

        return False
