#!/usr/bin/env python3

#****************************************************************************
# modbutton.py, provides a button that signals its text
#
# ConvertAll, a units conversion program
# Copyright (C) 2014, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

from PyQt5.QtCore import (QCoreApplication, QTranslator, QPoint, Qt, Qt, QUrl,
                          Qt, Qt, pyqtSignal)
from PyQt5.QtGui import (QColor, QFont, QPalette, QTextDocument, QIcon,
                         QPixmap)
from PyQt5.QtWidgets import (QApplication, QApplication, QCheckBox,
                             QColorDialog, QDialog, QFrame, QGroupBox,
                             QHBoxLayout, QLabel, QMenu, QMessageBox,
                             QPushButton, QVBoxLayout, QWidget, QComboBox,
                             QGroupBox, QHBoxLayout, QLineEdit, QPushButton,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout,
                             QWidget, QAction, QLabel, QLineEdit, QMainWindow,
                             QMenu, QStatusBar, QTextBrowser, QPushButton)


class ModButton(QPushButton):
    """Button used to add operators, change exponent or clear unit.
    """
    stateChg = pyqtSignal()
    def __init__(self, function, param, label, parent=None):
        QPushButton.__init__(self, label, parent)
        self.function = function
        self.param = param
        self.setFocusPolicy(Qt.NoFocus)
        self.clicked.connect(self.exe)

    def exe(self):
        """Execute function on button push.
        """
        if self.param != None:
            self.function(self.param)
        else:
            self.function()
        self.stateChg.emit()       # update listView

    def sizeHint(self):
        """Adjust width smaller.
        """
        size = QPushButton.sizeHint(self)
        size.setWidth(size.width() / 2)
        return size
