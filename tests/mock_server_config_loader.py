"""Example test usage of ServerConfigLoader interface for dependency injection.

This module demonstrates how to use the ServerConfigLoader interface to inject
mock configurations during unit testing, avoiding side effects of loading real
configuration files from the filesystem.
"""

from ms_database_connector.config.server_config_loader import ServerConfigLoader
from ms_database_connector.config.server_configuration import ServerConfiguration


class MockServerConfigLoader(ServerConfigLoader):
    """Mock implementation of ServerConfigLoader for testing.

    This allows tests to inject predefined or malformed configurations without
    touching the filesystem or having side effects.
    """

    def __init__(
        self,
        aas_reg_config: ServerConfiguration,
        sm_reg_config: ServerConfiguration,
        repo_configs: list[ServerConfiguration] | None = None,
    ):
        """Initialize mock loader with predefined configurations.

        Args:
            aas_reg_config: AAS registry configuration.
            sm_reg_config: Submodel registry configuration.
            repo_configs: Repository configurations (default: empty list).
        """
        self._aas_reg_config = aas_reg_config
        self._sm_reg_config = sm_reg_config
        self._repo_configs = repo_configs or []

    @property
    def aas_registry_configuration(self) -> ServerConfiguration:
        """Return the predefined AAS registry configuration."""
        if self._aas_reg_config is None:
            raise RuntimeError("Mock: AAS registry configuration not set")
        return self._aas_reg_config

    @property
    def sm_registry_configuration(self) -> ServerConfiguration:
        """Return the predefined Submodel registry configuration."""
        if self._sm_reg_config is None:
            raise RuntimeError("Mock: Submodel registry configuration not set")
        return self._sm_reg_config

    @property
    def repo_server_configurations(self) -> list[ServerConfiguration]:
        """Return the predefined repository configurations."""
        return self._repo_configs
