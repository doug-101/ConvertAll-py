#!/usr/bin/env python3

#****************************************************************************
# optiondlg.py, provides classes for option setting dialogs
#
# Copyright (C) 2016, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

import sys
from PyQt5.QtCore import Qt
from PyQt5.QtGui import (QDoubleValidator, QValidator)
from PyQt5.QtWidgets import (QButtonGroup, QCheckBox, QDialog, QGridLayout,
                             QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QRadioButton, QSpinBox, QVBoxLayout)


class OptionDlg(QDialog):
    """Works with Option class to provide a dialog for pref/options.
    """
    def __init__(self, option, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint |
                            Qt.WindowSystemMenuHint)
        self.option = option

        topLayout = QVBoxLayout(self)
        self.setLayout(topLayout)
        self.columnLayout = QHBoxLayout()
        topLayout.addLayout(self.columnLayout)
        self.gridLayout = QGridLayout()
        self.columnLayout.addLayout(self.gridLayout)
        self.oldLayout = self.gridLayout

        ctrlLayout = QHBoxLayout()
        topLayout.addLayout(ctrlLayout)
        ctrlLayout.addStretch(0)
        okButton = QPushButton(_('&OK'), self)
        ctrlLayout.addWidget(okButton)
        okButton.clicked.connect(self.accept)
        cancelButton = QPushButton(_('&Cancel'), self)
        ctrlLayout.addWidget(cancelButton)
        cancelButton.clicked.connect(self.reject)
        self.setWindowTitle(_('Preferences'))
        self.itemList = []
        self.curGroup = None

    def addItem(self, dlgItem, widget, label=None):
        """Add a control with optional label, called by OptionDlgItem.
        """
        row = self.gridLayout.rowCount()
        if label:
            self.gridLayout.addWidget(label, row, 0)
            self.gridLayout.addWidget(widget, row, 1)
        else:
            self.gridLayout.addWidget(widget, row, 0, 1, 2)
        self.itemList.append(dlgItem)

    def startGroupBox(self, title, intSpace=5):
        """Use a group box for next added items.
        """
        self.curGroup = QGroupBox(title, self)
        row = self.oldLayout.rowCount()
        self.oldLayout.addWidget(self.curGroup, row, 0, 1, 2)
        self.gridLayout = QGridLayout(self.curGroup)
        self.gridLayout.setVerticalSpacing(intSpace)

    def endGroupBox(self):
        """Cancel group box for next added items.
        """
        self.gridLayout = self.oldLayout
        self.curGroup = None

    def startNewColumn(self):
        """Cancel any group box and start a second column.
        """
        self.curGroup = None
        row = self.oldLayout.rowCount()
        self.gridLayout = QGridLayout()
        self.columnLayout.addLayout(self.gridLayout)
        self.oldLayout = self.gridLayout

    def parentGroup(self):
        """Return parent for new widgets.
        """
        if self.curGroup:
            return self.curGroup
        return self

    def accept(self):
        """Called by dialog when OK button pressed.
        """
        for item in self.itemList:
            item.updateData()
        QDialog.accept(self)


class OptionDlgItem:
    """Base class for items to add to dialog.
    """
    def __init__(self, dlg, key, writeChg):
        self.dlg = dlg
        self.key = key
        self.writeChg = writeChg
        self.control = None

    def updateData(self):
        """Dummy update function.
        """
        pass

class OptionDlgBool(OptionDlgItem):
    """Holds widget for bool checkbox.
    """
    def __init__(self, dlg, key, menuText, writeChg=True):
        OptionDlgItem.__init__(self, dlg, key, writeChg)
        self.control = QCheckBox(menuText, dlg.parentGroup())
        self.control.setChecked(dlg.option.boolData(key))
        dlg.addItem(self, self.control)

    def updateData(self):
        """Update Option class based on checkbox status.
        """
        if self.control.isChecked() != self.dlg.option.boolData(self.key):
            if self.control.isChecked():
                self.dlg.option.changeData(self.key, 'yes', self.writeChg)
            else:
                self.dlg.option.changeData(self.key, 'no', self.writeChg)

class OptionDlgInt(OptionDlgItem):
    """Holds widget for int spinbox.
    """
    def __init__(self, dlg, key, menuText, min, max, writeChg=True, step=1,
                 wrap=False, suffix=''):
        OptionDlgItem.__init__(self, dlg, key, writeChg)
        label = QLabel(menuText, dlg.parentGroup())
        self.control = QSpinBox(dlg.parentGroup())
        self.control.setMinimum(min)
        self.control.setMaximum(max)
        self.control.setSingleStep(step)
        self.control.setWrapping(wrap)
        self.control.setSuffix(suffix)
        self.control.setValue(dlg.option.intData(key, min, max))
        dlg.addItem(self, self.control, label)

    def updateData(self):
        """Update Option class based on spinbox status.
        """
        if self.control.value() != int(self.dlg.option.numData(self.key)):
            self.dlg.option.changeData(self.key, repr(self.control.value()),
                                       self.writeChg)

class OptionDlgDbl(OptionDlgItem):
    """Holds widget for double line edit.
    """
    def __init__(self, dlg, key, menuText, min, max, writeChg=True):
        OptionDlgItem.__init__(self, dlg, key, writeChg)
        label = QLabel(menuText, dlg.parentGroup())
        self.control = QLineEdit(repr(dlg.option.numData(key, min, max)),
                                       dlg.parentGroup())
        valid = QDoubleValidator(min, max, 6, self.control)
        self.control.setValidator(valid)
        dlg.addItem(self, self.control, label)

    def updateData(self):
        """Update Option class based on edit status.
        """
        text = self.control.text()
        unusedPos = 0
        if self.control.validator().validate(text, unusedPos)[0] != \
                QValidator.Acceptable:
            return
        num = float(text)
        if num != self.dlg.option.numData(self.key):
            self.dlg.option.changeData(self.key, repr(num), self.writeChg)

class OptionDlgStr(OptionDlgItem):
    """Holds widget for string line edit.
    """
    def __init__(self, dlg, key, menuText, writeChg=True):
        OptionDlgItem.__init__(self, dlg, key, writeChg)
        label = QLabel(menuText, dlg.parentGroup())
        self.control = QLineEdit(dlg.option.strData(key, True),
                                       dlg.parentGroup())
        dlg.addItem(self, self.control, label)

    def updateData(self):
        """Update Option class based on edit status.
        """
        newStr = self.control.text()
        if newStr != self.dlg.option.strData(self.key, True):
            self.dlg.option.changeData(self.key, newStr, self.writeChg)

class OptionDlgRadio(OptionDlgItem):
    """Holds widget for exclusive radio button group.
    """
    def __init__(self, dlg, key, headText, textList, writeChg=True):
        # textList is list of tuples: optionText, labelText
        OptionDlgItem.__init__(self, dlg, key, writeChg)
        self.optionList = [x[0] for x in textList]
        buttonBox = QGroupBox(headText, dlg.parentGroup())
        self.control = QButtonGroup(buttonBox)
        layout = QVBoxLayout(buttonBox)
        buttonBox.setLayout(layout)
        optionSetting = dlg.option.strData(key)
        id = 0
        for optionText, labelText in textList:
            button = QRadioButton(labelText, buttonBox)
            layout.addWidget(button)
            self.control.addButton(button, id)
            id += 1
            if optionText == optionSetting:
                button.setChecked(True)
        dlg.addItem(self, buttonBox)

    def updateData(self):
        """Update Option class based on button status.
        """
        data = self.optionList[self.control.checkedId()]
        if data != self.dlg.option.strData(self.key):
            self.dlg.option.changeData(self.key, data, self.writeChg)

class OptionDlgPush(OptionDlgItem):
    """Holds widget for extra misc. push button.
    """
    def __init__(self, dlg, text, cmd):
        OptionDlgItem.__init__(self, dlg, '', 0)
        self.control = QPushButton(text, dlg.parentGroup())
        self.control.clicked.connect(cmd)
        dlg.addItem(self, self.control)
