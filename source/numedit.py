#!/usr/bin/env python3

#****************************************************************************
# numedit.py, provides a number entry editor
#
# ConvertAll, a units conversion program
# Copyright (C) 2016, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

import re
import sys
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QValidator
from PyQt5.QtWidgets import (QLineEdit, QMessageBox)
import unitdata


class NumEdit(QLineEdit):
    """Number entry editor.
    """
    convertRqd = pyqtSignal()
    convertNum = pyqtSignal(str)
    gotFocus = pyqtSignal()
    def __init__(self, thisUnit, otherUnit, label, status, recentUnits,
                 primary, parent=None):
        super().__init__(parent)
        self.thisUnit = thisUnit
        self.otherUnit = otherUnit
        self.label = label
        self.status = status
        self.recentUnits = recentUnits
        self.primary = primary
        self.onLeft = primary
        self.setValidator(FloatExprValidator(self))
        self.setText(self.thisUnit.formatNumStr(1.0))
        self.textEdited.connect(self.convert)

    def unitUpdate(self):
        """Update the editor and labels based on a unit change.
        """
        if self.thisUnit.groupValid():
            self.label.setText(self.thisUnit.unitString())
            if self.otherUnit.groupValid():
                try:
                    self.thisUnit.reduceGroup()
                    self.otherUnit.reduceGroup()
                except unitdata.UnitDataError as text:
                    QMessageBox.warning(self, 'ConvertAll',
                                              _('Error in unit data - {0}').
                                              format(text))
                    return
                if self.thisUnit.categoryMatch(self.otherUnit):
                    self.status.setText(_('Converting...'))
                    if self.primary:
                        self.convert()
                    else:
                        self.convertRqd.emit()
                    return
                if self.onLeft:
                    self.status.setText(_('Units are not compatible '
                                          '({0}  vs.  {1})').
                                        format(self.thisUnit.compatStr(),
                                               self.otherUnit.compatStr()))
                else:
                    self.status.setText(_('Units are not compatible '
                                          '({0}  vs.  {1})').
                                        format(self.otherUnit.compatStr(),
                                               self.thisUnit.compatStr()))
            else:
                self.status.setText(_('Set units'))
        else:
            self.status.setText(_('Set units'))
            self.label.setText(_('No Unit Set'))
        self.setEnabled(False)
        self.convertNum.emit('')

    def convert(self):
        """Do conversion with self primary.
        """
        self.primary = True
        self.setEnabled(True)
        if self.onLeft:
            self.recentUnits.addEntry(self.otherUnit.unitString())
            self.recentUnits.addEntry(self.thisUnit.unitString())
        else:
            self.recentUnits.addEntry(self.thisUnit.unitString())
            self.recentUnits.addEntry(self.otherUnit.unitString())
        try:
            num = float(eval(self.text()))
        except:
            self.convertNum.emit('')
            return
        try:
            numText = self.thisUnit.convertStr(num, self.otherUnit)
            self.convertNum.emit(numText)
        except unitdata.UnitDataError as text:
            QMessageBox.warning(self, 'ConvertAll',
                                      _('Error in unit data - {0}').
                                      format(text))

    def setNum(self, numText):
        """Set text based on conversion from other number editor.
        """
        if not numText:
            self.setEnabled(False)
        else:
            self.primary = False
            self.setEnabled(True)
            self.setText(numText)

    def focusInEvent(self, event):
        """Signal that this number editor received focus.
        """
        super().focusInEvent(event)
        self.gotFocus.emit()


class FloatExprValidator(QValidator):
    """Validator for float python expressions typed into NumEdit.
    """
    invalidRe = re.compile(r'[^\d\.eE\+\-\*/\(\)]')
    def __init__(self, parent):
        super().__init__(parent)

    def validate(self, inputStr, pos):
        """Check for valid characters in entry.
        """
        if FloatExprValidator.invalidRe.search(inputStr):
            return (QValidator.Invalid, inputStr, pos)
        return (QValidator.Acceptable, inputStr, pos)
