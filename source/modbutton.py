#!/usr/bin/env python

#****************************************************************************
# modbutton.py, provides a button that signals its text
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


class ModButton(QtGui.QPushButton):
    """Button used to add operators, change exponent or clear unit"""
    def __init__(self, function, param, label, parent=None):
        QtGui.QPushButton.__init__(self, label, parent)
        self.function = function
        self.param = param
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.connect(self, QtCore.SIGNAL('clicked()'), self.exe)

    def exe(self):
        """Execute function on button push"""
        if self.param != None:
            self.function(self.param)
        else:
            self.function()
        self.emit(QtCore.SIGNAL('stateChg'))   # update listView

    def sizeHint(self):
        """Adjust width smaller"""
        size = QtGui.QPushButton.sizeHint(self)
        size.setWidth(size.width() / 2)
        return size
