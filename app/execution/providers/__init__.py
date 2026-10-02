"""
Provider registry and implementation modules.
"""

from .registry import ProviderRegistry

# Import gmail module to trigger the class auto-registration inside registry
from . import gmail
from . import outlook

__all__ = [
    "ProviderRegistry",
]
