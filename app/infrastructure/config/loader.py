"""
PolicyLoader: Loads policy rules from YAML configuration files into validated PolicyConfig objects.
"""

import os
import logging
import yaml
from typing import Optional, Union

from .schema import PolicyConfig
from .exceptions import PolicyLoadError, PolicyValidationError

logger = logging.getLogger(__name__)


class PolicyLoader:
    """
    Utility for loading and parsing YAML policy rule files.
    """

    @classmethod
    def load_from_yaml(cls, filepath: str) -> PolicyConfig:
        """
        Loads and validates policy configuration from a YAML file path.

        Args:
            filepath: Path to YAML configuration file.

        Returns:
            Validated PolicyConfig object.

        Raises:
            PolicyLoadError: If file reading or YAML parsing fails.
            PolicyValidationError: If YAML contents fail schema validation.
        """
        if not os.path.exists(filepath):
            raise PolicyLoadError(f"Policy configuration file not found at '{filepath}'")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw_data = yaml.safe_load(f)
        except Exception as exc:
            raise PolicyLoadError(f"Failed to read or parse YAML file at '{filepath}': {exc}") from exc

        if not isinstance(raw_data, dict):
            raise PolicyValidationError(f"Invalid YAML structure in '{filepath}': expected top-level dictionary.")

        try:
            config = PolicyConfig(**raw_data)
            logger.info(f"Successfully loaded policy configuration '{config.name}' (v{config.version}) with {len(config.rules)} rules.")
            return config
        except Exception as exc:
            raise PolicyValidationError(f"Policy schema validation error in '{filepath}': {exc}") from exc
