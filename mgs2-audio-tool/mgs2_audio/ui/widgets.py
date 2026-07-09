#!/usr/bin/env python3
"""
widgets.py — Small Qt widgets shared by both pages.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit, QListWidget


class PopupLineEdit(QLineEdit):
    """A line edit that shows its whole completion list on click / focus.

    The tag list is only useful if it is easy to reach: clicking the field pops
    the full list of labels already used, so a label can be reused without
    remembering how it was spelled.
    """

    def _popup(self):
        completer = self.completer()
        if completer and completer.model() and completer.model().rowCount():
            completer.setCompletionPrefix("")
            completer.complete()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if not self.text():
            self._popup()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if not self.text():
            self._popup()


class PlayOnSpaceList(QListWidget):
    """A list where the space bar plays / pauses the selected sound.

    Auditioning hundreds of files means living in this list: arrows to move,
    space to listen. Without it, every preview costs a trip to the mouse.
    """

    def __init__(self, on_space):
        super().__init__()
        self._on_space = on_space

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self._on_space()
            event.accept()
            return
        super().keyPressEvent(event)


# Configuration file (remembered paths + language), in the user's home folder
