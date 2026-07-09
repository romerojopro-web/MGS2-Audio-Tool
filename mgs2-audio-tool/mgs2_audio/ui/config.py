#!/usr/bin/env python3
"""
config.py — Remembered folders, language and last tab.

A small JSON file in the user's home. Losing it costs nothing but a few clicks,
so every failure here is silent on purpose.
"""

import json
import os

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
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass  # silent failure: settings are not critical
