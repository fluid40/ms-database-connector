"""Service for managing the SME-DB mapping configuration."""

import json
import logging
from pathlib import Path

from ms_database_connector.config.mapping_configuration import MappingConfiguration

_logger = logging.getLogger(__name__)


class MappingConfigurationService:
    """Manages loading, validating, and persisting the SME-DB mapping configuration.

    In-memory state keeps two representations:
    - ``_raw``:     the last persisted dict (may contain ``null`` values when only
                    initialized as a template via PUT /initialize-db-mapping).
    - ``_mapping``: a validated :class:`MappingConfiguration` instance, or ``None``
                    when the in-memory state still contains null/invalid values.
    """

    def __init__(self, config_file_path: str) -> None:
        self._config_file = Path(config_file_path)
        self._raw: dict | None = None
        self._mapping: MappingConfiguration | None = None
        self._load_from_file()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    @property
    def is_initialized(self) -> bool:
        """Return ``True`` if any mapping data (including templates) is loaded."""
        return self._raw is not None

    def get_raw(self) -> dict | None:
        """Return the raw mapping dict (may contain null values)."""
        return self._raw

    def get_mapping(self) -> MappingConfiguration | None:
        """Return the validated mapping, or ``None`` if only a template is stored."""
        return self._mapping

    def update_mapping(self, mapping: MappingConfiguration) -> None:
        """Persist a fully-validated mapping (no null values).

        :param mapping: A validated :class:`MappingConfiguration` instance.
        :raises OSError: If the file cannot be written.
        """
        serialised = json.loads(mapping.model_dump_json())
        self._mapping = mapping
        self._raw = serialised
        self._save_to_file(serialised)
        _logger.info("Mapping configuration updated.")

    def initialize_mapping(self, raw: dict) -> dict:
        """Store a mapping template that may contain null values.

        Clears the validated in-memory mapping so that :meth:`get_mapping`
        returns ``None`` until a proper POST /db-mapping replaces it.

        :param raw: Raw mapping dict (paths may map to ``None``).
        :raises OSError: If the file cannot be written.
        :return: The stored raw dict.
        """
        self._raw = raw
        self._mapping = None
        self._save_to_file(raw)
        _logger.info("Mapping configuration initialized with template.")
        return raw

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _load_from_file(self) -> None:
        if not self._config_file.exists():
            _logger.info(
                "Mapping config file '%s' not found. Starting with empty mapping.",
                self._config_file,
            )
            return
        try:
            content = self._config_file.read_text(encoding="utf-8")
            self._raw = json.loads(content)
            # Attempt strict parse; if the file is a null-template this will fail.
            try:
                self._mapping = MappingConfiguration.model_validate(self._raw)
                _logger.info(
                    "Loaded and validated mapping configuration from '%s'.",
                    self._config_file,
                )
            except Exception:
                _logger.info(
                    "Mapping file '%s' loaded but contains null/invalid values; "
                    "stored as template only.",
                    self._config_file,
                )
        except Exception as exc:
            _logger.warning(
                "Could not load mapping configuration from '%s': %s",
                self._config_file,
                exc,
            )

    def _save_to_file(self, data: dict) -> None:
        try:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            self._config_file.write_text(
                json.dumps(data, indent=4), encoding="utf-8"
            )
            _logger.info(
                "Saved mapping configuration to '%s'.", self._config_file
            )
        except OSError as exc:
            _logger.error(
                "Failed to save mapping configuration to '%s': %s",
                self._config_file,
                exc,
            )
            raise
