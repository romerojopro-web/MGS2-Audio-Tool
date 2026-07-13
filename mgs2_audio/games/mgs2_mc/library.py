#!/usr/bin/env python3
"""
library.py — Re-export of the central library.db module.

Game plugins import this module; the actual implementation lives in
``mgs2_audio.library.db`` to avoid tripling the code.
"""

from mgs2_audio.library.db import (  # noqa: F401
    LIBRARY_FILENAME,
    SDX_LIBRARY_FILENAME,
    LIBRARY_VERSION,
    ENTRY_DEFAULTS,
    SDX_ENTRY_DEFAULTS,
    MANUAL_FIELDS,
    CACHE_FIELDS,
    library_path,
    load_library,
    save_library,
    load_sdx_library,
    save_sdx_library,
    get_entry,
    set_entry,
    get_sdx_entry,
    set_sdx_entry,
    collect_tags,
    tag_counts,
    counts,
    list_sdt_files,
    quick_header,
    scan_metadata,
    cache_metadata,
)
