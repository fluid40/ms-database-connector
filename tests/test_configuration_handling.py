"""Unit tests for server configuration loading error handling.

Tests in this module focus on malformed or missing configuration files and
verify that the loader either raises HTTP errors or gracefully skips invalid
repository entries as intended.
"""

import json

import pytest

from ms_database_connector.models.exceptions.configuration_errors import (
    ConfigurationFileError,
    ConfigurationPathError,
    ConfigurationValidationError,
)
from ms_database_connector.utils import configuration_handling as configuration_module


def _write_json(path, payload: dict) -> None:
    """Write a JSON payload to disk."""
    path.write_text(json.dumps(payload))


def _valid_server_config(secret_var: str) -> dict:
    """Build a minimal valid ServerConfiguration payload."""
    return {
        "SecretVarName": secret_var,
        "ServerConfiguration": {"baseUrl": "http://localhost:8080"},
    }


def _prepare_required_dirs(base_path) -> None:
    """Create the required configuration directory structure."""
    (base_path / "aas_registry").mkdir(parents=True, exist_ok=True)
    (base_path / "submodel_registry").mkdir(parents=True, exist_ok=True)
    (base_path / "repo_server").mkdir(parents=True, exist_ok=True)


def test_raises_http_exception_when_base_config_path_is_missing(monkeypatch, tmp_path):
    """Raise a path error when the configured base path does not exist."""
    missing_base_path = tmp_path / "does-not-exist"
    monkeypatch.setattr(
        configuration_module, "CONFIG_BASE_PATH", str(missing_base_path)
    )

    with pytest.raises(ConfigurationPathError) as exc_info:
        configuration_module.ServerConfigurationsHandler()

    assert str(missing_base_path) in str(exc_info.value)


def test_raises_http_exception_for_malformed_aas_registry_config(monkeypatch, tmp_path):
    """Raise a validation error when AAS registry config contains malformed JSON."""
    _prepare_required_dirs(tmp_path)
    monkeypatch.setattr(configuration_module, "CONFIG_BASE_PATH", str(tmp_path))

    (tmp_path / "aas_registry" / "aas_registry.json").write_text("{ malformed json")

    with pytest.raises(ConfigurationValidationError) as exc_info:
        configuration_module.ServerConfigurationsHandler()

    assert str(exc_info.value) == "Invalid AAS registry connection file."


def test_raises_http_exception_for_malformed_submodel_registry_config(
    monkeypatch, tmp_path
):
    """Raise a validation error when Submodel registry config contains malformed JSON."""
    _prepare_required_dirs(tmp_path)
    monkeypatch.setattr(configuration_module, "CONFIG_BASE_PATH", str(tmp_path))

    _write_json(
        tmp_path / "aas_registry" / "aas_registry.json",
        _valid_server_config("AAS_SECRET"),
    )
    (tmp_path / "submodel_registry" / "sm_registry.json").write_text("{ malformed json")

    with pytest.raises(ConfigurationValidationError) as exc_info:
        configuration_module.ServerConfigurationsHandler()

    assert str(exc_info.value) == "Invalid Submodel registry connection file."


def test_raises_http_exception_when_aas_registry_has_no_json_files(
    monkeypatch, tmp_path
):
    """Raise a file error when no AAS registry JSON file exists."""
    _prepare_required_dirs(tmp_path)
    monkeypatch.setattr(configuration_module, "CONFIG_BASE_PATH", str(tmp_path))

    with pytest.raises(ConfigurationFileError) as exc_info:
        configuration_module.ServerConfigurationsHandler()

    assert "No AAS registry configuration files found" in str(exc_info.value)


def test_skips_invalid_repo_configs_and_loads_valid_ones(monkeypatch, tmp_path):
    """Ignore malformed repository configs and keep valid repository configs."""
    _prepare_required_dirs(tmp_path)
    monkeypatch.setattr(configuration_module, "CONFIG_BASE_PATH", str(tmp_path))

    _write_json(
        tmp_path / "aas_registry" / "aas_registry.json",
        _valid_server_config("AAS_SECRET"),
    )
    _write_json(
        tmp_path / "submodel_registry" / "sm_registry.json",
        _valid_server_config("SM_SECRET"),
    )

    (tmp_path / "repo_server" / "repo_invalid.json").write_text("{ malformed json")
    _write_json(
        tmp_path / "repo_server" / "repo_valid.json",
        _valid_server_config("REPO_SECRET"),
    )

    handler = configuration_module.ServerConfigurationsHandler()

    assert handler.aas_registry_configuration.secret_var_name == "AAS_SECRET"
    assert handler.sm_registry_configuration.secret_var_name == "SM_SECRET"
    assert len(handler.repo_server_configurations) == 1
    assert handler.repo_server_configurations[0].secret_var_name == "REPO_SECRET"


def test_raises_path_error_when_aas_registry_directory_missing(monkeypatch, tmp_path):
    """Raise a path error when aas_registry directory does not exist."""
    _prepare_required_dirs(tmp_path)
    (tmp_path / "aas_registry").rmdir()  # Remove the aas_registry directory
    monkeypatch.setattr(configuration_module, "CONFIG_BASE_PATH", str(tmp_path))

    with pytest.raises(ConfigurationPathError) as exc_info:
        configuration_module.ServerConfigurationsHandler()

    assert "aas_registry" in str(exc_info.value)
    assert "not found" in str(exc_info.value)


def test_raises_path_error_when_sm_registry_directory_missing(monkeypatch, tmp_path):
    """Raise a path error when submodel_registry directory does not exist."""
    _prepare_required_dirs(tmp_path)
    monkeypatch.setattr(configuration_module, "CONFIG_BASE_PATH", str(tmp_path))

    # Create valid AAS registry config
    _write_json(
        tmp_path / "aas_registry" / "aas_registry.json",
        _valid_server_config("AAS_SECRET"),
    )

    # Remove submodel_registry directory
    (tmp_path / "submodel_registry").rmdir()

    with pytest.raises(ConfigurationPathError) as exc_info:
        configuration_module.ServerConfigurationsHandler()

    assert "submodel_registry" in str(exc_info.value)
    assert "not found" in str(exc_info.value)


def test_raises_file_error_when_sm_registry_has_no_json_files(monkeypatch, tmp_path):
    """Raise a file error when no Submodel registry JSON files exist."""
    _prepare_required_dirs(tmp_path)
    monkeypatch.setattr(configuration_module, "CONFIG_BASE_PATH", str(tmp_path))

    # Create valid AAS registry config
    _write_json(
        tmp_path / "aas_registry" / "aas_registry.json",
        _valid_server_config("AAS_SECRET"),
    )

    # submodel_registry directory exists but has no JSON files

    with pytest.raises(ConfigurationFileError) as exc_info:
        configuration_module.ServerConfigurationsHandler()

    assert "Submodel registry" in str(exc_info.value)
    assert "No" in str(exc_info.value)


def test_raises_path_error_when_repo_server_directory_missing(monkeypatch, tmp_path):
    """Raise a path error when repo_server directory does not exist."""
    _prepare_required_dirs(tmp_path)
    monkeypatch.setattr(configuration_module, "CONFIG_BASE_PATH", str(tmp_path))

    # Create valid registry configs
    _write_json(
        tmp_path / "aas_registry" / "aas_registry.json",
        _valid_server_config("AAS_SECRET"),
    )
    _write_json(
        tmp_path / "submodel_registry" / "sm_registry.json",
        _valid_server_config("SM_SECRET"),
    )

    # Remove repo_server directory
    (tmp_path / "repo_server").rmdir()

    with pytest.raises(ConfigurationPathError) as exc_info:
        configuration_module.ServerConfigurationsHandler()

    assert "repo_server" in str(exc_info.value)
    assert "not found" in str(exc_info.value)


def test_empty_repo_configs_when_no_repo_json_files(monkeypatch, tmp_path):
    """Allow empty repository configurations when no repo JSON files exist."""
    _prepare_required_dirs(tmp_path)
    monkeypatch.setattr(configuration_module, "CONFIG_BASE_PATH", str(tmp_path))

    # Create valid registry configs
    _write_json(
        tmp_path / "aas_registry" / "aas_registry.json",
        _valid_server_config("AAS_SECRET"),
    )
    _write_json(
        tmp_path / "submodel_registry" / "sm_registry.json",
        _valid_server_config("SM_SECRET"),
    )

    # repo_server directory exists but has no JSON files

    handler = configuration_module.ServerConfigurationsHandler()

    assert handler.aas_registry_configuration.secret_var_name == "AAS_SECRET"
    assert handler.sm_registry_configuration.secret_var_name == "SM_SECRET"
    assert len(handler.repo_server_configurations) == 0
