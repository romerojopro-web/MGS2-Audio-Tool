#!/usr/bin/env python3
"""
run.py — Launch MGS2 Audio Tool.

    python run.py

Requires Python 3.10+ and PyQt6 (`pip install PyQt6`). The engine underneath
(`mgs2_audio.codec` and `mgs2_audio.formats`) is pure Python and needs neither.
"""

import sys

if __name__ == "__main__":
    from mgs2_audio.ui.app import main
    sys.exit(main())
