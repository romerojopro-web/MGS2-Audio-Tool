"""
games — Game-specific modules.

Each subpackage (e.g. ``games.mgs2``) exports a ``Plugin`` instance that
registers itself with the global ``REGISTRY`` on import.
"""

# Trigger plugin discovery when this package is imported.
from ..core.registry import discover
discover()
