#!/usr/bin/env python3
"""
registry.py — Game plugin discovery and global registry.

At import time, ``discover()`` scans ``mgs2_audio.games.*/`` for subpackages
that export a ``Plugin`` instance (a ``GamePlugin`` subclass).  Each plugin
is registered in the module-level ``REGISTRY`` object.

The tool shell (app.py, cli.py) reads from ``REGISTRY`` — it never imports
game-specific code directly.

Pure Python, no dependencies beyond stdlib.
"""

import importlib
import logging
import os
import pkgutil
from typing import Dict, List, Optional

from .base import GamePlugin

log = logging.getLogger(__name__)


class _Registry:
    """Singleton that holds all registered game plugins."""

    def __init__(self) -> None:
        self._plugins: Dict[str, GamePlugin] = {}
        self._order: List[str] = []   # insertion order

    def register(self, plugin: GamePlugin) -> None:
        """Add a plugin.  Later registrations with the same id overwrite."""
        if plugin.id not in self._plugins:
            self._order.append(plugin.id)
        self._plugins[plugin.id] = plugin

    def get(self, game_id: str) -> Optional[GamePlugin]:
        return self._plugins.get(game_id)

    @property
    def ids(self) -> List[str]:
        return list(self._order)

    @property
    def plugins(self) -> List[GamePlugin]:
        return [self._plugins[gid] for gid in self._order]

    def __iter__(self):
        return iter(self.plugins)

    def __len__(self) -> int:
        return len(self._plugins)

    def __contains__(self, game_id: str) -> bool:
        return game_id in self._plugins


REGISTRY = _Registry()


def discover() -> None:
    """Scan ``mgs2_audio.games`` for plugin subpackages and register them."""
    try:
        games_pkg = importlib.import_module("mgs2_audio.games")
    except ImportError:
        return

    pkg_path = getattr(games_pkg, "__path__", None)
    if pkg_path is None:
        return

    for importer, modname, ispkg in pkgutil.iter_modules(pkg_path):
        if not ispkg:
            continue
        try:
            mod = importlib.import_module(f"mgs2_audio.games.{modname}")
        except Exception as exc:
            log.debug("skipping plugin %s: %s", modname, exc)
            continue
        plugin = getattr(mod, "Plugin", None)
        if isinstance(plugin, GamePlugin):
            plugin.register()
