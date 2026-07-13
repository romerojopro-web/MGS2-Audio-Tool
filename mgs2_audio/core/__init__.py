"""
core — Shared abstractions for the multi-game audio tool.

Provides the ``GamePlugin`` ABC and the global ``REGISTRY`` that the tool
shell (app.py, cli.py) uses to discover and interact with game modules.
"""

from .base import AudioContainer, AudioFormat, GamePlugin, PageSpec
from .registry import REGISTRY, discover

__all__ = [
    "AudioContainer", "AudioFormat", "GamePlugin", "PageSpec",
    "REGISTRY", "discover",
]
