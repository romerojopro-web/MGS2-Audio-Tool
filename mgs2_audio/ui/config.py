#!/usr/bin/env python3
"""
config.py — Remembered folders, language and last tab.

A small JSON file in the user's home. Losing it costs nothing but a few clicks,
so every failure here is silent on purpose.
"""

import json
import logging
import os
import tempfile

log = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(
    os.path.expanduser("~"), ".mgs2_audio_tool.json")

# Older releases of the tool used this name; read it once so upgrading users
# keep their folders and tags.
LEGACY_CONFIG_PATH = os.path.join(
    os.path.expanduser("~"), ".mgs2_sdt_tool.json")


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        pass
    try:
        with open(LEGACY_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg: dict):
    try:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(CONFIG_PATH) or ".",
                                   suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2)
            os.replace(tmp, CONFIG_PATH)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as e:
        log.warning("could not save config to %s: %s", CONFIG_PATH, e)
