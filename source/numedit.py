#!/usr/bin/env python

#****************************************************************************
# numedit.py, provides a number entry editor
#
# ConvertAll, a units conversion program
# Copyright (C) 2006, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

from __future__ import division

import re
import sys
from PyQt4 import QtCore, QtGui
import unitdata


class NumEdit(QtGui.QLineEdit):
    """Number entry editor"""
    def __init__(self, thisUnit, otherUnit, label, status, recentUnits,
                 primary, parent=None):
        QtGui.QLineEdit.__init__(self, parent)
        self.thisUnit = thisUnit
        self.otherUnit = otherUnit
        self.label = label
        self.status = status
        self.recentUnits = recentUnits
        self.primary = primary
        self.onLeft = primary
        self.setValidator(FloatExprValidator(self))
        self.setText(self.thisUnit.formatNumStr(1.0))
        self.connect(self, QtCore.SIGNAL('textEdited(const QString &)'),
                     self.convert)

    def unitUpdate(self):
        """Update the editor and labels based on a unit change"""
        if self.thisUnit.groupValid():
            self.label.setTitle(self.thisUnit.unitString())
            if self.otherUnit.groupValid():
                try:
                    self.thisUnit.reduceGroup()
                    self.otherUnit.reduceGroup()
                except unitdata.UnitDataError, text:
                    QtGui.QMessageBox.warning(self, 'ConvertAll',
                                              _('Error in unit data - %s')
                                              % text)
                    return
                if self.thisUnit.categoryMatch(self.otherUnit):
                    self.status.setText(_('Converting...'))
                    if self.primary:
                        self.convert()
                    else:
                        self.emit(QtCore.SIGNAL('convertRqd'))
                    return
                if self.onLeft:
                    self.status.setText(_(u'Units are not compatible '\
                              '(%s  vs.  %s)') % (self.thisUnit.compatStr(),
                                                  self.otherUnit.compatStr()))
                else:
                    self.status.setText(_('Units are not compatible '\
                              '(%s  vs.  %s)') % (self.otherUnit.compatStr(),
                                                  self.thisUnit.compatStr()))
            else:
                self.status.setText(_('Set units'))
        else:
            self.status.setText(_('Set units'))
            self.label.setTitle(_('No Unit Set'))
        self.setEnabled(False)
        self.emit(QtCore.SIGNAL('convertNum'), '')

    def convert(self):
        """Do conversion with self primary"""
        self.primary = True
        self.setEnabled(True)
        self.recentUnits.addEntry(self.thisUnit.unitString())
        self.recentUnits.addEntry(self.otherUnit.unitString())
        try:
            num = float(eval(unicode(self.text())))
        except:
            self.emit(QtCore.SIGNAL('convertNum'), '')
            return
        try:
            numText = self.thisUnit.convertStr(num, self.otherUnit)
            self.emit(QtCore.SIGNAL('convertNum'), numText)
        except unitdata.UnitDataError, text:
            QtGui.QMessageBox.warning(self, 'ConvertAll',
                                      _('Error in unit data - %s') % text)

    def setNum(self, numText):
        """Set text based on conversion from other number editor"""
        if not numText:
            self.setEnabled(False)
        else:
            self.primary = False
            self.setEnabled(True)
            self.setText(numText)


class FloatExprValidator(QtGui.QValidator):
    """Validator for float python expressions typed into NumEdit"""
    invalidRe = re.compile(r'[^\d\.eE\+\-\*/\(\)]')
    def __init__(self, parent):
        QtGui.QValidator.__init__(self, parent)

    def validate(self, inputStr, pos):
        """Check for valid characters in entry"""
        if FloatExprValidator.invalidRe.search(unicode(inputStr)):
            return (QtGui.QValidator.Invalid, pos)
        return (QtGui.QValidator.Acceptable, pos)
