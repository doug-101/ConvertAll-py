#!/usr/bin/env python

#****************************************************************************
# unitedit.py, provides a line edit for unit entry
#
# ConvertAll, a units conversion program
# Copyright (C) 2006, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

from PyQt4 import QtCore, QtGui


class UnitEdit(QtGui.QLineEdit):
    """Text line editor for unit entry"""
    def __init__(self, unitGroup, parent=None):
        QtGui.QLineEdit.__init__(self, parent)
        self.unitGroup = unitGroup
        self.connect(self,
                     QtCore.SIGNAL('textEdited(const QString &)'),
                     self.updateGroup)
        self.connect(self, QtCore.SIGNAL('cursorPositionChanged(int, int)'),
                     self.updateCurrentUnit)

    def unitUpdate(self):
        """Update text from unit group"""
        newText = self.unitGroup.unitString()
        cursorPos = len(newText) - self.text().length() + self.cursorPosition()
        if cursorPos < 0:      # cursor set to same distance from right end
            cursorPos = 0
        self.blockSignals(True)
        self.setText(newText)
        self.setCursorPosition(cursorPos)
        self.blockSignals(False)
        self.emit(QtCore.SIGNAL('unitChanged'))  # update numEdit

    def updateGroup(self):
        """Update unit based on edit text change (except spacing change)"""
        if str(self.text()).replace(' ', '') \
           != self.unitGroup.unitString().replace(' ', ''):
            self.unitGroup.update(str(self.text()), self.cursorPosition())
            self.emit(QtCore.SIGNAL('currentChanged'))  # update listView
            self.unitUpdate()   # replace text with formatted text

    def updateCurrentUnit(self):
        """Change current unit based on cursor movement"""
        self.unitGroup.updateCurrentUnit(str(self.text()),
                                         self.cursorPosition())
        self.emit(QtCore.SIGNAL('currentChanged'))  # update listView

    def keyPressEvent(self, event):
        """Keys for return and up/down"""
        if event.key() == QtCore.Qt.Key_Up:
            self.unitGroup.moveToNext(True)
            self.emit(QtCore.SIGNAL('currentChanged'))  # update listView
            self.unitUpdate()
        elif event.key() == QtCore.Qt.Key_Down:
            self.unitGroup.moveToNext(False)
            self.emit(QtCore.SIGNAL('currentChanged'))  # update listView
            self.unitUpdate()
        elif event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
            self.unitGroup.completePartial()
            self.emit(QtCore.SIGNAL('currentChanged'))  # update listView
            self.unitUpdate()
        else:
            QtGui.QLineEdit.keyPressEvent(self, event)

    def event(self, event):
        """Catch tab press to complete unit"""
        if event.type() == QtCore.QEvent.KeyPress and \
                 event.key() == QtCore.Qt.Key_Tab:
            self.unitGroup.completePartial()
            self.emit(QtCore.SIGNAL('currentChanged'))  # update listView
            self.unitUpdate()
        return QtGui.QLineEdit.event(self, event)
