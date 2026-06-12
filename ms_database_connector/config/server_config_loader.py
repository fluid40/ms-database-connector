"""Interface and factory for loading server configurations.

This module provides an abstraction layer for loading server configurations,
enabling dependency injection and easier testing by avoiding direct file system access.
"""

from abc import ABC, abstractmethod

from ms_database_connector.config.server_configuration import ServerConfiguration


class ServerConfigLoader(ABC):
    """Abstract interface for loading server configurations.

    Implementations of this interface provide a way to load server configurations
    for AAS registry, Submodel registry, and AAS repository servers.
    This abstraction allows for easy testing by injecting mock loaders that
    don't touch the file system.
    """

    @property
    @abstractmethod
    def aas_registry_configuration(self) -> ServerConfiguration:
        """Get the AAS registry server configuration.

        Returns:
            ServerConfiguration: The AAS registry configuration.

        Raises:
            Exception: If configuration cannot be loaded.
        """
        pass

    @property
    @abstractmethod
    def sm_registry_configuration(self) -> ServerConfiguration:
        """Get the Submodel registry server configuration.

        Returns:
            ServerConfiguration: The Submodel registry configuration.

        Raises:
            Exception: If configuration cannot be loaded.
        """
        pass

    @property
    @abstractmethod
    def repo_server_configurations(self) -> list[ServerConfiguration]:
        """Get all AAS repository server configurations.

        Returns:
            list[ServerConfiguration]: List of repository server configurations.
                May be empty if no repositories are configured.

        Raises:
            Exception: If configuration cannot be loaded.
        """
        pass
