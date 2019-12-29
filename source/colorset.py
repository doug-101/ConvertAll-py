#!/usr/bin/env python3

#****************************************************************************
# colorset.py, provides storage/retrieval and dialogs for system colors
#
# ConvertAll, a units conversion program
# Copyright (C) 2019, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

from collections import OrderedDict
from PyQt5.QtCore import pyqtSignal, Qt, QEvent, QObject
from PyQt5.QtGui import QColor, QFontMetrics, QPalette, QPixmap
from PyQt5.QtWidgets import (QApplication, QCheckBox, QColorDialog, QDialog,
                             QFrame, QGroupBox, QHBoxLayout, QLabel,
                             QGridLayout, QPushButton, QVBoxLayout, qApp)

roles = OrderedDict([('Window', _('Dialog background color')),
                     ('WindowText', _('Dialog text color')),
                     ('Base', _('Text widget background color')),
                     ('Text', _('Text widget foreground color')),
                     ('Highlight', _('Selected item background color')),
                     ('HighlightedText', _('Selected item text color')),
                     ('Button', _('Button background color')),
                     ('ButtonText', _('Button text color')),
                     ('Text-Disabled', _('Disabled text foreground color')),
                     ('ButtonText-Disabled', _('Disabled button text color'))])


class ColorSet:
    """Stores color settings and provides dialogs for user changes.
    """
    def __init__(self, option):
        self.option = option
        self.sysPalette = QApplication.palette()
        self.colors = [Color(roleKey) for roleKey in roles.keys()]
        for color in self.colors:
            color.colorChanged.connect(self.endSystemSetting)
            color.setFromPalette(self.sysPalette)
            if not self.option.boolData('UseDefaultColors'):
                color.setFromOption(self.option)

    def setAppColors(self):
        """Set application to current colors.
        """
        newPalette = QApplication.palette()
        for color in self.colors:
            color.updatePalette(newPalette)
        qApp.setPalette(newPalette)


    def showDialog(self, parent):
        """Show a dialog for user color changes.

        Return True if changes were made.
        """
        dialog = QDialog(parent)
        dialog.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint |
                              Qt.WindowSystemMenuHint)
        dialog.setWindowTitle(_('Color Settings'))
        topLayout = QVBoxLayout(dialog)
        dialog.setLayout(topLayout)
        systemBox = QGroupBox(_('System Colors'), dialog)
        topLayout.addWidget(systemBox)
        systemLayout = QVBoxLayout(systemBox)
        self.systemControl = QCheckBox(_('Use default system colors'), dialog)
        self.systemControl.setChecked(self.option.boolData('UseDefaultColors'))
        self.systemControl.stateChanged.connect(self.updateSystemSetting)
        systemLayout.addWidget(self.systemControl)
        self.groupBox = QGroupBox(dialog)
        self.setBoxTitle()
        topLayout.addWidget(self.groupBox)
        gridLayout = QGridLayout(self.groupBox)
        row = 0
        for color in self.colors:
            gridLayout.addWidget(color.getLabel(), row, 0)
            gridLayout.addWidget(color.getSwatch(), row, 1)
            row += 1
        ctrlLayout = QHBoxLayout()
        topLayout.addLayout(ctrlLayout)
        ctrlLayout.addStretch(0)
        okButton = QPushButton(_('&OK'), dialog)
        ctrlLayout.addWidget(okButton)
        okButton.clicked.connect(dialog.accept)
        cancelButton = QPushButton(_('&Cancel'), dialog)
        ctrlLayout.addWidget(cancelButton)
        cancelButton.clicked.connect(dialog.reject)
        if dialog.exec_() == QDialog.Accepted:
            if self.systemControl.isChecked():
                self.option.changeData('UseDefaultColors', 'yes', True)
                qApp.setPalette(self.sysPalette)
            else:
                self.option.changeData('UseDefaultColors', 'no', True)
                for color in self.colors:
                    color.updateOption(self.option)
                self.setAppColors()
        else:
            for color in self.colors:
                color.setFromPalette(self.sysPalette)
                if not self.option.boolData('UseDefaultColors'):
                    color.setFromOption(self.option)

    def setBoxTitle(self):
        """Set title of group box to standard or custom.
        """
        if self.systemControl.isChecked():
            title = _('Default Colors')
        else:
            title = _('Custom Colors')
        self.groupBox.setTitle(title)

    def updateSystemSetting(self):
        """Update the colors based on a system color control change.
        """
        if self.systemControl.isChecked():
            for color in self.colors:
                color.setFromPalette(self.sysPalette)
                color.changeSwatchColor()
        else:
            for color in self.colors:
                color.setFromOption(self.option)
                color.changeSwatchColor()
        self.setBoxTitle()

    def endSystemSetting(self):
        """Set to custom color setting after user color change.
        """
        if self.systemControl.isChecked():
            self.systemControl.blockSignals(True)
            self.systemControl.setChecked(False)
            self.systemControl.blockSignals(False)
            self.setBoxTitle()


class Color(QObject):
    """Stores a single color setting for a role.
    """
    colorChanged = pyqtSignal()
    def __init__(self, roleKey, parent=None):
        super().__init__(parent)
        self.roleKey = roleKey
        if '-' in roleKey:
            roleStr, groupStr = roleKey.split('-')
            self.group = eval('QPalette.' + groupStr)
        else:
            roleStr = roleKey
            self.group = None
        self.role = eval('QPalette.' + roleStr)
        self.currentColor = None
        self.swatch = None

    def setFromPalette(self, palette):
        """Set the color based on the given palette.
        """
        if self.group:
            self.currentColor = palette.color(self.group, self.role)
        else:
            self.currentColor = palette.color(self.role)

    def setFromOption(self, option):
        """Set color based on the option setting.
        """
        colorStr = '#' + option.strData(self.roleKey + 'Color', True)
        color = QColor(colorStr)
        if color.isValid():
            self.currentColor = color

    def updateOption(self, option):
        """Set the option to the current color.
        """
        if self.currentColor:
            colorStr = self.currentColor.name().lstrip('#')
            option.changeData(self.roleKey + 'Color', colorStr, True)

    def updatePalette(self, palette):
        """Set the role in the given palette to the current color.
        """
        if self.group:
            palette.setColor(self.group, self.role, self.currentColor)
        else:
            palette.setColor(self.role, self.currentColor)

    def getLabel(self):
        """Return a label for this role in a dialog.
        """
        return QLabel(roles[self.roleKey])

    def getSwatch(self):
        """Return a label color swatch with the current color.
        """
        self.swatch = QLabel()
        self.changeSwatchColor()
        self.swatch.setFrameStyle(QFrame.Panel | QFrame.Raised)
        self.swatch.setLineWidth(3)
        self.swatch.installEventFilter(self)
        return self.swatch

    def changeSwatchColor(self):
        """Set swatch to currentColor.
        """
        height = QFontMetrics(self.swatch.font()).height()
        pixmap = QPixmap(3 * height, height)
        pixmap.fill(self.currentColor)
        self.swatch.setPixmap(pixmap)

    def eventFilter(self, obj, event):
        """Handle mouse clicks on swatches.
        """
        if obj == self.swatch and event.type() == QEvent.MouseButtonRelease:
            color = QColorDialog.getColor(self.currentColor,
                                          QApplication.activeWindow(),
                                          _('Select {0} color').
                                          format(self.roleKey))
            if color.isValid() and color != self.currentColor:
                self.currentColor = color
                self.changeSwatchColor()
                self.colorChanged.emit()
            return True
        return False
