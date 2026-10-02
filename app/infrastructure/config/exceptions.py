"""
Exceptions for infrastructure policy configuration loading and validation.
"""

class ConfigError(Exception):
    """Base exception for policy configuration errors."""
    pass


class PolicyLoadError(ConfigError):
    """Raised when policy YAML file loading fails."""
    pass


class PolicyValidationError(ConfigError):
    """Raised when policy configuration validation fails against schema."""
    pass
