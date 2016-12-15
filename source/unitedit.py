#!/usr/bin/env python3

#****************************************************************************
# unitedit.py, provides a line edit for unit entry
#
# ConvertAll, a units conversion program
# Copyright (C) 2016, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

from PyQt5.QtCore import (QEvent, Qt, pyqtSignal)
from PyQt5.QtWidgets import (QLineEdit, QWidget)


class UnitEdit(QLineEdit):
    """Text line editor for unit entry.
    """
    unitChanged = pyqtSignal()
    currentChanged = pyqtSignal(QWidget) # pass line edit for focus proxy
    keyPressed = pyqtSignal(int) # pass key to list view for some key presses
    gotFocus = pyqtSignal()
    def __init__(self, unitGroup, parent=None):
        super().__init__(parent)
        self.unitGroup = unitGroup
        self.activeEditor = False;
        self.textEdited.connect(self.updateGroup)
        self.cursorPositionChanged.connect(self.updateCurrentUnit)

    def unitUpdate(self):
        """Update text from unit group.
        """
        if not self.activeEditor:
            return
        newText = self.unitGroup.unitString()
        cursorPos = len(newText) - len(self.text()) + self.cursorPosition()
        if cursorPos < 0:      # cursor set to same distance from right end
            cursorPos = 0
        self.blockSignals(True)
        self.setText(newText)
        self.setCursorPosition(cursorPos)
        self.blockSignals(False)
        self.unitChanged.emit()

    def updateGroup(self):
        """Update unit based on edit text change (except spacing change).
        """
        if (self.text().replace(' ', '') !=
            self.unitGroup.unitString().replace(' ', '')):
            self.unitGroup.update(self.text(), self.cursorPosition())
            self.currentChanged.emit(self)     # update listView
            self.unitUpdate()   # replace text with formatted text

    def updateCurrentUnit(self):
        """Change current unit based on cursor movement.
        """
        self.unitGroup.updateCurrentUnit(self.text(),
                                         self.cursorPosition())
        self.currentChanged.emit(self)     # update listView

    def keyPressEvent(self, event):
        """Keys for return and up/down.
        """
        if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_PageUp,
                           Qt.Key_PageDown, Qt.Key_Return, Qt.Key_Enter):
            self.keyPressed.emit(event.key())
        else:
            super().keyPressEvent(event)

    def event(self, event):
        """Catch tab press to complete unit.
        """
        if (event.type() == QEvent.KeyPress and
            event.key() == Qt.Key_Tab):
            # self.unitGroup.completePartial()
            self.currentChanged.emit(self)     # update listView
            self.unitUpdate()
        return super().event(event)

    def setInactive(self):
        """Set inactive based on a signal from another editor.
        """
        self.activeEditor = False;

    def focusInEvent(self, event):
        """Signal that this unit editor received focus.
        """
        super().focusInEvent(event)
        if not self.activeEditor:
            self.activeEditor = True
            self.updateCurrentUnit()
            self.gotFocus.emit()
