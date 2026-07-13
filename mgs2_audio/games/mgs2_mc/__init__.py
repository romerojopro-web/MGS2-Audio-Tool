#!/usr/bin/env python3
"""
MGS2 Master Collection plugin.

Provides the SDT, BGM (MC), SDX and Sequencer tabs for the PC Master
Collection release.
"""

from ...core.base import GamePlugin, PageSpec


class _Mgs2McPlugin(GamePlugin):
    id = "mgs2_mc"
    name = "Metal Gear Solid 2 — Master Collection"

    _cached_pages = None

    def _build_pages(self):
        if _Mgs2McPlugin._cached_pages is None:
            from ...ui.mcbgm_page import McBgmPage
            from ...ui.sdt_page import SDTPage
            from ...ui.sdx_page import SDXPage
            from ...ui.seq_page import SeqPage
            _Mgs2McPlugin._cached_pages = [
                PageSpec("sdt", SDTPage, "tab_sdt"),
                PageSpec("mcbgm", McBgmPage, "tab_mcbgm"),
                PageSpec("sdx", SDXPage, "tab_sdx"),
                PageSpec("seq", SeqPage, "tab_seq"),
            ]
        return _Mgs2McPlugin._cached_pages

    @property
    def pages(self):
        return self._build_pages()

    @property
    def modes(self):
        return {
            "mc": {
                "pages": self._build_pages(),
                "subtitle_key": "app_subtitle_mc",
                "style": "",  # default green
            },
        }

    @property
    def i18n(self):
        return {}  # translations live in the shared i18n.py for now


Plugin = _Mgs2McPlugin()
