#!/usr/bin/env python3

#****************************************************************************
# convertdlg.py, provides the main dialog and GUI interface
#
# ConvertAll, a units conversion program
# Copyright (C) 2016, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

import sys
import os.path
from PyQt5.QtCore import (QPoint, Qt)
from PyQt5.QtGui import (QColor, QFont, QPalette)
from PyQt5.QtWidgets import (QApplication, QCheckBox, QColorDialog, QDialog,
                             QFrame, QGridLayout, QGroupBox, QHBoxLayout,
                             QLabel, QLayout, QMenu, QMessageBox, QPushButton,
                             QSizePolicy, QVBoxLayout, QWidget)
try:
    from __main__ import __version__, __author__, helpFilePath, iconPath
    from __main__ import lang
except ImportError:
    __version__ = __author__ = '??'
    helpFilePath = None
    iconPath = None
    lang = ''
import unitdata
from unitgroup import UnitGroup
from option import Option
import recentunits
import unitedit
import unitlistview
import numedit
import icondict
import optiondefaults
import helpview
import optiondlg


class ConvertDlg(QWidget):
    """Main dialog for ConvertAll program.
    """
    unitData = unitdata.UnitData()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('ConvertAll')
        modPath = os.path.abspath(sys.path[0])
        if modPath.endswith('.zip'):  # for py2exe
            modPath = os.path.dirname(modPath)
        iconPathList = [iconPath, os.path.join(modPath, 'icons/'),
                         os.path.join(modPath, '../icons')]
        self.icons = icondict.IconDict()
        self.icons.addIconPath([path for path in iconPathList if path])
        try:
            QApplication.setWindowIcon(self.icons['convertall_med'])
        except KeyError:
            pass
        self.helpView = None
        self.option = Option('convertall', 20)
        self.option.loadAll(optiondefaults.defaultList)
        self.recentUnits = recentunits.RecentUnits(self.option)
        try:
            num = ConvertDlg.unitData.readData()
        except unitdata.UnitDataError as text:
            QMessageBox.warning(self, 'ConvertAll',
                                _('Error in unit data - {0}').  format(text))
            sys.exit(1)
        try:
            print(_('{0} units loaded').format(num))
        except UnicodeError:
            print('{0} units loaded'.format(num))
        self.fromGroup = UnitGroup(ConvertDlg.unitData, self.option)
        self.toGroup = UnitGroup(ConvertDlg.unitData, self.option)
        self.origPal = QApplication.palette()
        self.updateColors()
        self.unitButtons = []
        self.textButtons = []

        topLayout = QHBoxLayout(self)    # divide main, buttons
        mainLayout = QVBoxLayout()
        mainLayout.setSpacing(8)
        topLayout.addLayout(mainLayout)
        unitLayout = QGridLayout()       # unit selection
        unitLayout.setVerticalSpacing(3)
        unitLayout.setHorizontalSpacing(20)
        mainLayout.addLayout(unitLayout)

        fromLabel = QLabel(_('From Unit'))
        unitLayout.addWidget(fromLabel, 0, 0)
        self.fromUnitEdit = unitedit.UnitEdit(self.fromGroup)
        unitLayout.addWidget(self.fromUnitEdit, 1, 0)
        self.fromUnitEdit.setFocus()

        toLabel = QLabel(_('To Unit'))
        unitLayout.addWidget(toLabel, 0, 1)
        self.toUnitEdit = unitedit.UnitEdit(self.toGroup)
        unitLayout.addWidget(self.toUnitEdit, 1, 1)
        self.fromUnitEdit.gotFocus.connect(self.toUnitEdit.setInactive)
        self.toUnitEdit.gotFocus.connect(self.fromUnitEdit.setInactive)

        vertButtonLayout = QVBoxLayout()
        vertButtonLayout.setSpacing(2)
        mainLayout.addLayout(vertButtonLayout)

        self.unitListView = unitlistview.UnitListView(ConvertDlg.unitData)
        mainLayout.addWidget(self.unitListView)
        self.fromUnitEdit.currentChanged.connect(self.unitListView.
                                                 updateFiltering)
        self.toUnitEdit.currentChanged.connect(self.unitListView.
                                               updateFiltering)
        self.fromUnitEdit.keyPressed.connect(self.unitListView.handleKeyPress)
        self.toUnitEdit.keyPressed.connect(self.unitListView.handleKeyPress)
        self.unitListView.unitChanged.connect(self.fromUnitEdit.unitUpdate)
        self.unitListView.unitChanged.connect(self.toUnitEdit.unitUpdate)
        self.unitListView.haveCurrentUnit.connect(self.enableButtons)
        self.unitListView.setFocusProxy(self.fromUnitEdit)

        textButtonLayout = QHBoxLayout()
        textButtonLayout.setSpacing(6)
        vertButtonLayout.addLayout(textButtonLayout)
        textButtonLayout.addStretch(1)
        self.textButtons.append(QPushButton('{0} (^2)'.format(_('Square'))))
        self.textButtons.append(QPushButton('{0} (^3)'.format(_('Cube'))))
        self.textButtons.append(QPushButton('{0} (*)'.format(_('Multiply'))))
        self.textButtons.append(QPushButton('{0} (/)'.format(_('Divide'))))
        for button in self.textButtons:
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            button.setFocusPolicy(Qt.NoFocus)
            textButtonLayout.addWidget(button)
            button.clicked.connect(self.unitListView.addUnitText)
        textButtonLayout.addStretch(1)

        unitButtonLayout = QHBoxLayout()
        unitButtonLayout.setSpacing(6)
        vertButtonLayout.addLayout(unitButtonLayout)
        unitButtonLayout.addStretch(1)
        self.clearButton = QPushButton(_('Clear Unit'))
        self.clearButton.clicked.connect(self.unitListView.clearUnitText)
        self.recentButton = QPushButton(_('Recent Unit'))
        self.recentButton.clicked.connect(self.recentMenu)
        self.filterButton = QPushButton(_('Filter List'))
        self.filterButton.clicked.connect(self.filterMenu)
        self.unitButtons = [self.clearButton, self.recentButton,
                            self.filterButton]
        for button in self.unitButtons:
            button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            button.setFocusPolicy(Qt.NoFocus)
            unitButtonLayout.addWidget(button)
        unitButtonLayout.addStretch(1)
        self.showHideButtons()

        numberLayout = QGridLayout()
        numberLayout.setVerticalSpacing(3)
        mainLayout.addLayout(numberLayout)
        statusLabel = QLabel(_('Set units'))
        statusLabel.setFrameStyle(QFrame.Panel | QFrame.Sunken)
        mainLayout.addWidget(statusLabel)

        fromNumLabel = QLabel(_('No Unit Set'))
        numberLayout.addWidget(fromNumLabel, 0, 0)
        self.fromNumEdit = numedit.NumEdit(self.fromGroup, self.toGroup,
                                           fromNumLabel, statusLabel,
                                           self.recentUnits, True)
        numberLayout.addWidget(self.fromNumEdit, 1, 0)
        self.fromUnitEdit.unitChanged.connect(self.fromNumEdit.unitUpdate)
        self.fromNumEdit.gotFocus.connect(self.fromUnitEdit.setInactive)
        self.fromNumEdit.gotFocus.connect(self.toUnitEdit.setInactive)
        self.fromNumEdit.gotFocus.connect(self.unitListView.resetFiltering)
        self.fromNumEdit.setEnabled(False)
        equalsLabel = QLabel(' = ')
        equalsLabel.setFont(QFont(self.font().family(), 20))
        numberLayout.addWidget(equalsLabel, 0, 1, 2, 1)

        toNumLabel = QLabel(_('No Unit Set'))
        numberLayout.addWidget(toNumLabel, 0, 3)
        self.toNumEdit = numedit.NumEdit(self.toGroup, self.fromGroup,
                                         toNumLabel, statusLabel,
                                         self.recentUnits, False)
        numberLayout.addWidget(self.toNumEdit, 1, 3)
        self.toUnitEdit.unitChanged.connect(self.toNumEdit.unitUpdate)
        self.toNumEdit.gotFocus.connect(self.fromUnitEdit.setInactive)
        self.toNumEdit.gotFocus.connect(self.toUnitEdit.setInactive)
        self.toNumEdit.gotFocus.connect(self.unitListView.resetFiltering)
        self.toNumEdit.setEnabled(False)
        self.fromNumEdit.convertNum.connect(self.toNumEdit.setNum)
        self.toNumEdit.convertNum.connect(self.fromNumEdit.setNum)
        self.fromNumEdit.convertRqd.connect(self.toNumEdit.convert)
        self.toNumEdit.convertRqd.connect(self.fromNumEdit.convert)

        buttonLayout = QVBoxLayout()     # major buttons
        topLayout.addLayout(buttonLayout)
        closeButton = QPushButton(_('&Close'))
        buttonLayout.addWidget(closeButton)
        closeButton.setFocusPolicy(Qt.NoFocus)
        closeButton.clicked.connect(self.close)
        optionsButton = QPushButton(_('&Options...'))
        buttonLayout.addWidget(optionsButton)
        optionsButton.setFocusPolicy(Qt.NoFocus)
        optionsButton.clicked.connect(self.changeOptions)
        helpButton = QPushButton(_('&Help...'))
        buttonLayout.addWidget(helpButton)
        helpButton.setFocusPolicy(Qt.NoFocus)
        helpButton.clicked.connect(self.help)
        aboutButton = QPushButton(_('&About...'))
        buttonLayout.addWidget(aboutButton)
        aboutButton.setFocusPolicy(Qt.NoFocus)
        aboutButton.clicked.connect(self.about)
        buttonLayout.addStretch()

        xSize = self.option.intData('MainDlgXSize', 0, 10000)
        ySize = self.option.intData('MainDlgYSize', 0, 10000)
        if xSize and ySize:
            self.resize(xSize, ySize)
        self.move(self.option.intData('MainDlgXPos', 0, 10000),
                  self.option.intData('MainDlgYPos', 0, 10000))
        if self.option.boolData('LoadLastUnit') and len(self.recentUnits) > 1:
            self.fromGroup.update(self.recentUnits[0])
            self.fromUnitEdit.unitUpdate()
            self.toGroup.update(self.recentUnits[1])
            self.toUnitEdit.unitUpdate()
            self.unitListView.updateFiltering()
            self.fromNumEdit.setFocus()
            self.fromNumEdit.selectAll()
        if self.option.boolData('ShowStartupTip'):
            self.show()
            tipDialog = TipDialog(self.option, self)
            tipDialog.exec_()

    def recentMenu(self):
        """Show a menu with recently used units.
        """
        button = self.sender()
        menu = QMenu()
        for unit in self.recentUnits:
            action = menu.addAction(unit)
        menu.triggered.connect(self.insertRecent)
        menu.exec_(button.mapToGlobal(QPoint(0, 0)))

    def insertRecent(self, action):
        """Insert the recent unit from the given action.
        """
        editor = (self.fromUnitEdit if self.fromUnitEdit.activeEditor else
                  self.toUnitEdit)
        editor.unitGroup.update(action.text())
        editor.unitUpdate()
        self.unitListView.updateFiltering()

    def filterMenu(self):
        """Show a menu with unit types for filtering or clear filter if set.
        """
        if self.unitListView.typeFilter:  # clear filter
            self.unitListView.typeFilter = ''
            self.unitListView.updateFiltering()
            self.filterButton.setText(_('Filter List'))
        else:  # show filter menu
            button = self.sender()
            menu = QMenu()
            for unitType in ConvertDlg.unitData.typeList:
                action = menu.addAction(unitType)
            menu.triggered.connect(self.startTypeFilter)
            menu.exec_(button.mapToGlobal(QPoint(0, 0)))

    def startTypeFilter(self, action):
        """Start type filter based on the given action.
        """
        self.unitListView.typeFilter = action.text()
        self.unitListView.updateFiltering()
        self.filterButton.setText(_('Clear Filter'))

    def enableButtons(self, editActive, hasUnit):
        """Enable text editing buttons if have a current unit.
        """
        for button in self.textButtons:
            button.setEnabled(hasUnit)
        self.clearButton.setEnabled(editActive)
        self.recentButton.setEnabled(editActive and len(self.recentUnits))

    def showHideButtons(self):
        """Show or hide text modify buttons.
        """
        textButtonsVisible = self.option.boolData('ShowOpButtons')
        unitButtonsVisible = self.option.boolData('ShowUnitButtons')
        for button in self.textButtons:
            if textButtonsVisible:
                button.show()
            else:
                button.hide()
        for button in self.unitButtons:
            if unitButtonsVisible:
                button.show()
            else:
                button.hide()

    def updateColors(self):
        """Adjust the colors to the current option settings.
        """
        if self.option.boolData('UseDefaultColors'):
            pal = self.origPal
        else:
            pal = QPalette()
            pal.setColor(QPalette.Base, self.getOptionColor('Background'))
            pal.setColor(QPalette.Text, self.getOptionColor('Foreground'))
        QApplication.setPalette(pal)

    def changeOptions(self):
        """Show dialog for option changes.
        """
        origBackground = self.getOptionColor('Background')
        origForeground = self.getOptionColor('Foreground')
        dlg = optiondlg.OptionDlg(self.option, self)
        dlg.startGroupBox(_('Result Precision'))
        optiondlg.OptionDlgInt(dlg, 'DecimalPlaces', _('Decimal places'),
                               0, UnitGroup.maxDecPlcs)
        dlg.endGroupBox()
        optiondlg.OptionDlgRadio(dlg, 'Notation', _('Result Display'),
                              [('general', _('Use short representation')),
                               ('fixed', _('Use fixed decimal places')),
                               ('scientific', _('Use scientific notation')),
                               ('engineering', _('Use engineering notation'))])
        dlg.startGroupBox(_('Recent Units'))
        optiondlg.OptionDlgInt(dlg, 'RecentUnits', _('Number saved'), 2, 99)
        optiondlg.OptionDlgBool(dlg, 'LoadLastUnit',
                                _('Load last units at startup'))
        dlg.startGroupBox(_('User Interface'))
        optiondlg.OptionDlgBool(dlg, 'ShowOpButtons',
                                _('Show operator buttons (1st row)'))
        optiondlg.OptionDlgBool(dlg, 'ShowUnitButtons',
                                _('Show unit buttons (2nd row)'))
        optiondlg.OptionDlgBool(dlg, 'ShowStartupTip',
                                _('Show tip at startup'))
        dlg.startGroupBox(_('Colors'))
        optiondlg.OptionDlgBool(dlg, 'UseDefaultColors',
                                _('Use default system colors'))
        optiondlg.OptionDlgPush(dlg, _('Set background color'), self.backColor)
        optiondlg.OptionDlgPush(dlg, _('Set text color'), self.textColor)
        if dlg.exec_() == QDialog.Accepted:
            self.option.writeChanges()
            self.recentUnits.updateQuantity()
            self.updateColors()
            self.showHideButtons()
            self.fromNumEdit.unitUpdate()
            self.toNumEdit.unitUpdate()
        else:
            self.setOptionColor('Background', origBackground)
            self.setOptionColor('Foreground', origForeground)

    def getOptionColor(self, rootName):
        """Return a color from option storage.
        """
        return QColor(self.option.intData(rootName + 'R', 0, 255),
                      self.option.intData(rootName + 'G', 0, 255),
                      self.option.intData(rootName + 'B', 0, 255))

    def setOptionColor(self, rootName, color):
        """Store given color in options.
        """
        self.option.changeData(rootName + 'R', repr(color.red()), True)
        self.option.changeData(rootName + 'G', repr(color.green()), True)
        self.option.changeData(rootName + 'B', repr(color.blue()), True)

    def backColor(self):
        """Allow user to set control background color.
        """
        background = self.getOptionColor('Background')
        newColor = QColorDialog.getColor(background, self)
        if newColor.isValid() and newColor != background:
            self.setOptionColor('Background', newColor)

    def textColor(self):
        """Allow user to set control text color.
        """
        foreground = self.getOptionColor('Foreground')
        newColor = QColorDialog.getColor(foreground, self)
        if newColor.isValid() and newColor != foreground:
            self.setOptionColor('Foreground', newColor)

    def findHelpFile(self):
        """Return the path to the help file.
        """
        modPath = os.path.abspath(sys.path[0])
        if modPath.endswith('.zip'):  # for py2exe
            modPath = os.path.dirname(modPath)
        pathList = [helpFilePath, os.path.join(modPath, '../doc/'),
                    modPath, os.path.join(modPath, 'doc/')]
        fileList = ['README.html']
        if lang and lang != 'C':
            fileList[0:0] = ['README_{0}.html'.format(lang),
                             'README_{0}.html'.format(lang[:2])]
        for path in [path for path in pathList if path]:
            for fileName in fileList:
                fullPath = os.path.join(path, fileName)
                if os.access(fullPath, os.R_OK):
                    return fullPath
        return ''

    def help(self):
        """View the ReadMe file.
        """
        if not self.helpView:
            path = self.findHelpFile()
            if not path:
                QMessageBox.warning(self, 'ConvertAll',
                                    _('Read Me file not found'))
                return
            self.helpView = helpview.HelpView(path,
                                              _('ConvertAll README File'),
                                              self.icons)
        self.helpView.show()

    def about(self):
        """Show about info.
        """
        QMessageBox.about(self, 'ConvertAll',
                          _('ConvertAll Version {0}\nby {1}').
                          format(__version__, __author__))

    def closeEvent(self, event):
        """Save window data on close.
        """
        self.option.changeData('MainDlgXSize', self.width(), True)
        self.option.changeData('MainDlgYSize', self.height(), True)
        self.option.changeData('MainDlgXPos', self.x(), True)
        self.option.changeData('MainDlgYPos', self.y(), True)
        self.recentUnits.writeList()
        self.option.writeChanges()
        event.accept()


class TipDialog(QDialog):
    """Show a static usage tip at startup by default.
    """
    def __init__(self, option, parent=None):
        super().__init__(parent)
        self.option = option
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint |
                            Qt.WindowSystemMenuHint)
        self.setWindowTitle(_('Convertall - Tip'))
        topLayout = QVBoxLayout(self)
        self.setLayout(topLayout)

        box = QGroupBox(_('Combining Units'))
        topLayout.addWidget(box)
        boxLayout = QVBoxLayout(box)
        label = QLabel(self)
        label.setTextFormat(Qt.RichText)
        label.setText(_('<p>ConvertAll\'s strength is the ability to combine '
                        'units:</p>'
                        '<ul><li>Enter "m/s" to get meters per second</li>'
                        '<li>Enter "ft*lbf" to get foot-pounds (torque)</li>'
                        '<li>Enter "in^2" to get square inches</li>'
                        '<li>Enter "m^3" to get cubic meters</li>'
                        '<li>or any other combinations you can imagine</li>'
                        '</ul>'))
        boxLayout.addWidget(label)

        ctrlLayout = QHBoxLayout()
        topLayout.addLayout(ctrlLayout)
        self.showCheck = QCheckBox(_('Show this tip at startup'), self)
        self.showCheck.setChecked(True)
        ctrlLayout.addWidget(self.showCheck)

        ctrlLayout.addStretch()
        okButton = QPushButton(_('&OK'), self)
        ctrlLayout.addWidget(okButton)
        okButton.clicked.connect(self.accept)

    def accept(self):
        """Called by dialog when OK button pressed.
        """
        if not self.showCheck.isChecked():
            self.option.changeData('ShowStartupTip', 'no', True)
        super().accept()
