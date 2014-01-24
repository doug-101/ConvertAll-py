#!/usr/bin/env python3

#****************************************************************************
# unitedit.py, provides a line edit for unit entry
#
# ConvertAll, a units conversion program
# Copyright (C) 2014, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

from PyQt4 import QtCore, QtGui


class UnitEdit(QtGui.QLineEdit):
    """Text line editor for unit entry.
    """
    unitChanged = QtCore.pyqtSignal()
    currentChanged = QtCore.pyqtSignal()
    def __init__(self, unitGroup, parent=None):
        QtGui.QLineEdit.__init__(self, parent)
        self.unitGroup = unitGroup
        self.textEdited.connect(self.updateGroup)
        self.cursorPositionChanged.connect(self.updateCurrentUnit)

    def unitUpdate(self):
        """Update text from unit group.
        """
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
        if self.text().replace(' ', '') \
                   != self.unitGroup.unitString().replace(' ', ''):
            self.unitGroup.update(self.text(), self.cursorPosition())
            self.currentChanged.emit()     # update listView
            self.unitUpdate()   # replace text with formatted text

    def updateCurrentUnit(self):
        """Change current unit based on cursor movement.
        """
        self.unitGroup.updateCurrentUnit(self.text(),
                                         self.cursorPosition())
        self.currentChanged.emit()     # update listView

    def keyPressEvent(self, event):
        """Keys for return and up/down.
        """
        if event.key() == QtCore.Qt.Key_Up:
            self.unitGroup.moveToNext(True)
            self.currentChanged.emit()     # update listView
            self.unitUpdate()
        elif event.key() == QtCore.Qt.Key_Down:
            self.unitGroup.moveToNext(False)
            self.currentChanged.emit()     # update listView
            self.unitUpdate()
        elif event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.unitGroup.completePartial()
            self.currentChanged.emit()     # update listView
            self.unitUpdate()
        else:
            QtGui.QLineEdit.keyPressEvent(self, event)

    def event(self, event):
        """Catch tab press to complete unit.
        """
        if event.type() == QtCore.QEvent.KeyPress and \
                 event.key() == QtCore.Qt.Key_Tab:
            self.unitGroup.completePartial()
            self.currentChanged.emit()     # update listView
            self.unitUpdate()
        return QtGui.QLineEdit.event(self, event)
