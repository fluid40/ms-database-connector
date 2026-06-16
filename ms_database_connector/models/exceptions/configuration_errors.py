"""Custom exceptions for configuration loading and validation failures."""


class ConfigurationError(Exception):
    """Base exception for configuration-related failures."""


class ConfigurationPathError(ConfigurationError):
    """Raised when a required configuration path is missing or inaccessible."""


class ConfigurationFileError(ConfigurationError):
    """Raised when required configuration files are missing."""


class ConfigurationValidationError(ConfigurationError):
    """Raised when a configuration file cannot be parsed or validated."""
