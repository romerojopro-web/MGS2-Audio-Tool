#!/usr/bin/env python3
"""
MGS2 Substance (2003) plugin.

Provides the VOX, SDX, BGM and DEMOS tabs for the Substance 2003 release.
"""

from ...core.base import GamePlugin, PageSpec


class _Mgs2SubstancePlugin(GamePlugin):
    id = "mgs2_substance"
    name = "Metal Gear Solid 2 — Substance (2003)"

    _cached_pages = None

    def _build_pages(self):
        if _Mgs2SubstancePlugin._cached_pages is None:
            from ...ui.vox_page import VoxPage
            from ...ui.sdx_page import SDXPage
            from ...ui.bgm_page import BGMPage
            from ...ui.demos_page import DEMOSPage
            _Mgs2SubstancePlugin._cached_pages = [
                PageSpec("vox", VoxPage, "tab_vox"),
                PageSpec("sdx", SDXPage, "tab_sdx"),
                PageSpec("bgm", BGMPage, "tab_bgm"),
                PageSpec("demos", DEMOSPage, "tab_demos"),
            ]
        return _Mgs2SubstancePlugin._cached_pages

    @property
    def pages(self):
        return self._build_pages()

    @property
    def modes(self):
        return {
            "substance": {
                "pages": self._build_pages(),
                "subtitle_key": "app_subtitle_substance",
                "style": "substance",  # amber theme
            },
        }

    @property
    def i18n(self):
        return {}  # translations live in the shared i18n.py for now


Plugin = _Mgs2SubstancePlugin()
