#!/usr/bin/env python

#****************************************************************************
# convertdlg.py, provides the main dialog and GUI interface
#
# ConvertAll, a units conversion program
# Copyright (C) 2006, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

import sys
import os.path
from PyQt4 import QtCore, QtGui
try:
    from __main__ import __version__, __author__, helpFilePath, iconPath
except ImportError:
    __version__ = __author__ = '??'
    helpFilePath = None
    iconPath = None
import unitdata
from unitgroup import UnitGroup
from option import Option
import unitedit
import unitlistview
import numedit
from modbutton import ModButton
import finddlg
import icondict
import optiondefaults
import helpview
import optiondlg


class ConvertDlg(QtGui.QWidget):
    """Main dialog for ConvertAll program"""
    unitData = unitdata.UnitData()
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.setWindowTitle('ConvertAll')
        modPath = os.path.abspath(sys.path[0])
        if modPath.endswith('.zip'):  # for py2exe
            modPath = os.path.dirname(modPath)
        iconPathList = [iconPath, os.path.join(modPath, 'icons/'),
                         os.path.join(modPath, '../icons')]
        self.icons = icondict.IconDict()
        self.icons.addIconPath(filter(None, iconPathList))
        try:
            QtGui.QApplication.setWindowIcon(self.icons['convertall_med'])
        except KeyError:
            pass
        self.helpView = None
        self.findDlg = None
        self.option = Option('convertall', 20)
        self.option.loadAll(optiondefaults.defaultList)
        try:
            num = ConvertDlg.unitData.readData()
            print '%d units loaded' % num
        except unitdata.UnitDataError, text:
            QtGui.QMessageBox.warning(self, 'ConvertAll',
                                      'Error in unit data - %s' % text)
            sys.exit(1)
        self.fromGroup = UnitGroup(ConvertDlg.unitData, self.option)
        self.toGroup = UnitGroup(ConvertDlg.unitData, self.option)
        self.origPal = QtGui.QApplication.palette()
        self.updateColors()
        self.textButtons = []

        topLayout = QtGui.QHBoxLayout(self)    # divide main, buttons
        mainLayout = QtGui.QVBoxLayout()
        topLayout.addLayout(mainLayout)
        unitLayout = QtGui.QHBoxLayout()       # unit selection
        mainLayout.addLayout(unitLayout)

        fromBox = QtGui.QGroupBox('From Unit')
        unitLayout.addWidget(fromBox)
        fromLayout = QtGui.QVBoxLayout(fromBox)
        fromLayout.setSpacing(3)
        self.fromUnitEdit = unitedit.UnitEdit(self.fromGroup)
        fromLayout.addWidget(self.fromUnitEdit)
        self.fromUnitEdit.setFocus()
        self.fromUnitListView = unitlistview.UnitListView(self.fromGroup, 0)
        fromLayout.addWidget(self.fromUnitListView)
        self.connect(self.fromUnitEdit, QtCore.SIGNAL('currentChanged'),
                     self.fromUnitListView.updateSelection)
        self.connect(self.fromUnitListView, QtCore.SIGNAL('unitChanged'),
                     self.fromUnitEdit.unitUpdate)
        self.fromUnitListView.setFocusProxy(self.fromUnitEdit)
        self.addButtons(self.fromGroup, self.fromUnitListView, fromLayout)

        toBox = QtGui.QGroupBox('To Unit')
        unitLayout.addWidget(toBox)
        toLayout = QtGui.QVBoxLayout(toBox)
        toLayout.setSpacing(3)
        self.toUnitEdit = unitedit.UnitEdit(self.toGroup)
        toLayout.addWidget(self.toUnitEdit)
        self.toUnitListView = unitlistview.UnitListView(self.toGroup, 1)
        toLayout.addWidget(self.toUnitListView)
        self.connect(self.toUnitEdit, QtCore.SIGNAL('currentChanged'),
                     self.toUnitListView.updateSelection)
        self.connect(self.toUnitListView, QtCore.SIGNAL('unitChanged'),
                     self.toUnitEdit.unitUpdate)
        self.toUnitListView.setFocusProxy(self.toUnitEdit)
        self.addButtons(self.toGroup, self.toUnitListView, toLayout)
        self.showHideButtons()

        numberLayout = QtGui.QHBoxLayout()
        mainLayout.addLayout(numberLayout)
        statusLabel = QtGui.QLabel('Set units')
        statusLabel.setFrameStyle(QtGui.QFrame.Panel | QtGui.QFrame.Sunken)
        mainLayout.addWidget(statusLabel)

        fromNumBox = QtGui.QGroupBox('No Unit Set')
        numberLayout.addWidget(fromNumBox)
        fromNumLayout = QtGui.QVBoxLayout(fromNumBox)
        self.fromNumEdit = numedit.NumEdit(self.fromGroup, self.toGroup,
                                           fromNumBox, statusLabel, True)
        fromNumLayout.addWidget(self.fromNumEdit)
        self.connect(self.fromUnitEdit, QtCore.SIGNAL('unitChanged'),
                     self.fromNumEdit.unitUpdate)
        self.fromNumEdit.setEnabled(False)
        equalsLabel = QtGui.QLabel(' = ')
        equalsLabel.setFont(QtGui.QFont(self.font().family(), 30))
        numberLayout.addWidget(equalsLabel)

        toNumBox = QtGui.QGroupBox('No Unit Set')
        numberLayout.addWidget(toNumBox)
        toNumLayout = QtGui.QVBoxLayout(toNumBox)
        self.toNumEdit = numedit.NumEdit(self.toGroup, self.fromGroup,
                                         toNumBox, statusLabel, False)
        toNumLayout.addWidget(self.toNumEdit)
        self.connect(self.toUnitEdit, QtCore.SIGNAL('unitChanged'),
                     self.toNumEdit.unitUpdate)
        self.toNumEdit.setEnabled(False)
        self.connect(self.fromNumEdit, QtCore.SIGNAL('convertNum(QString &)'),
                     self.toNumEdit.setNum)
        self.connect(self.toNumEdit, QtCore.SIGNAL('convertNum(QString &)'),
                     self.fromNumEdit.setNum)
        self.connect(self.fromNumEdit, QtCore.SIGNAL('convertRqd'),
                     self.toNumEdit.convert)
        self.connect(self.toNumEdit, QtCore.SIGNAL('convertRqd'),
                     self.fromNumEdit.convert)

        buttonLayout = QtGui.QVBoxLayout()     # major buttons
        topLayout.addLayout(buttonLayout)
        closeButton = QtGui.QPushButton('&Close')
        buttonLayout.addWidget(closeButton)
        closeButton.setFocusPolicy(QtCore.Qt.NoFocus)
        self.connect(closeButton, QtCore.SIGNAL('clicked()'), self.close)
        finderButton = QtGui.QPushButton('&Unit Finder...')
        buttonLayout.addWidget(finderButton)
        finderButton.setFocusPolicy(QtCore.Qt.NoFocus)
        self.connect(finderButton, QtCore.SIGNAL('clicked()'), self.showFinder)
        optionsButton = QtGui.QPushButton('&Options...')
        buttonLayout.addWidget(optionsButton)
        optionsButton.setFocusPolicy(QtCore.Qt.NoFocus)
        self.connect(optionsButton, QtCore.SIGNAL('clicked()'),
                     self.changeOptions)
        helpButton = QtGui.QPushButton('&Help...')
        buttonLayout.addWidget(helpButton)
        helpButton.setFocusPolicy(QtCore.Qt.NoFocus)
        self.connect(helpButton, QtCore.SIGNAL('clicked()'), self.help)
        aboutButton = QtGui.QPushButton('&About...')
        buttonLayout.addWidget(aboutButton)
        aboutButton.setFocusPolicy(QtCore.Qt.NoFocus)
        self.connect(aboutButton, QtCore.SIGNAL('clicked()'), self.about)
        buttonLayout.addStretch()

        xSize = self.option.intData('MainDlgXSize', 0, 10000)
        ySize = self.option.intData('MainDlgYSize', 0, 10000)
        if xSize and ySize:
            self.resize(xSize, ySize)
        self.move(self.option.intData('MainDlgXPos', 0, 10000),
                  self.option.intData('MainDlgYPos', 0, 10000))

    def addButtons(self, unitGroup, listView, upperLayout):
        """Add buttons to unit selector"""
        buttonLayout = QtGui.QHBoxLayout()
        upperLayout.addLayout(buttonLayout)
        buttons = []
        buttons.append(ModButton(unitGroup.addOper, 1, 'X'))
        buttons.append(ModButton(unitGroup.addOper, 0, '/'))
        buttons.append(ModButton(unitGroup.changeExp, 2, '^2'))
        buttons.append(ModButton(unitGroup.changeExp, 3, '^3'))
        for button in buttons:
            buttonLayout.addWidget(button)
        listView.buttonList = buttons[:]
        buttons.append(ModButton(unitGroup.clearUnit, None, 'Clear Unit'))
        upperLayout.addWidget(buttons[-1])
        for but in buttons:
            self.connect(but, QtCore.SIGNAL('stateChg'), listView.relayChange)
            but.setEnabled(False)
            self.textButtons.append(but)
        buttons[-1].setEnabled(True)

    def updateColors(self):
        """Adjust the colors to the current option settings"""
        if self.option.boolData('UseDefaultColors'):
            pal = self.origPal
        else:
            pal = QtGui.QPalette()
            pal.setColor(QtGui.QPalette.Base,
                         self.getOptionColor('Background'))
            pal.setColor(QtGui.QPalette.Text,
                         self.getOptionColor('Foreground'))
        QtGui.QApplication.setPalette(pal)

    def showFinder(self):
        """Show dialog for searhing and filtering units"""
        if not self.findDlg:
            self.findDlg = finddlg.FindDlg(self)
        self.findDlg.show()

    def changeOptions(self):
        """Show dialog for option changes"""
        origBackground = self.getOptionColor('Background')
        origForeground = self.getOptionColor('Foreground')
        dlg = optiondlg.OptionDlg(self.option, self)
        dlg.startGroupBox('Result Display')
        optiondlg.OptionDlgInt(dlg, 'DecimalPlaces', 'Decimal places',
                               0, UnitGroup.maxDecPlcs)
        optiondlg.OptionDlgBool(dlg, 'SciNotation', 'Use scientific notation')
        optiondlg.OptionDlgBool(dlg, 'FixedDecimals',
                                'Use fixed decimal places')
        dlg.startGroupBox('Buttons')
        optiondlg.OptionDlgBool(dlg, 'ShowOpButtons', 'Show operator buttons')
        dlg.startGroupBox('Colors')
        optiondlg.OptionDlgBool(dlg, 'UseDefaultColors',
                                'Use default system colors')
        optiondlg.OptionDlgPush(dlg, 'Set background color', self.backColor)
        optiondlg.OptionDlgPush(dlg, 'Set text color', self.textColor)
        if dlg.exec_() == QtGui.QDialog.Accepted:
            self.option.writeChanges()
            self.updateColors()
            self.showHideButtons()
            self.fromNumEdit.unitUpdate()
            self.toNumEdit.unitUpdate()
        else:
            self.setOptionColor('Background', origBackground)
            self.setOptionColor('Foreground', origForeground)

    def getOptionColor(self, rootName):
        """Return a color from option storage"""
        return QtGui.QColor(self.option.intData('%sR' % rootName, 0, 255),
                            self.option.intData('%sG' % rootName, 0, 255),
                            self.option.intData('%sB' % rootName, 0, 255))

    def setOptionColor(self, rootName, color):
        """Store given color in options"""
        self.option.changeData('%sR' % rootName, str(color.red()), True)
        self.option.changeData('%sG' % rootName, str(color.green()), True)
        self.option.changeData('%sB' % rootName, str(color.blue()), True)

    def backColor(self):
        """Allow user to set control background color"""
        background = self.getOptionColor('Background')
        newColor = QtGui.QColorDialog.getColor(background, self)
        if newColor.isValid() and newColor != background:
            self.setOptionColor('Background', newColor)

    def textColor(self):
        """Allow user to set control text color"""
        foreground = self.getOptionColor('Foreground')
        newColor = QtGui.QColorDialog.getColor(foreground, self)
        if newColor.isValid() and newColor != foreground:
            self.setOptionColor('Foreground', newColor)

    def showHideButtons(self):
        """Show or hide text modify buttons"""
        visible = self.option.boolData('ShowOpButtons')
        for button in self.textButtons:
            if visible:
                button.show()
            else:
                button.hide()

    def findHelpFile(self):
        """Return the path to the help file"""
        modPath = os.path.abspath(sys.path[0])
        if modPath.endswith('.zip'):  # for py2exe
            modPath = os.path.dirname(modPath)
        pathList = [helpFilePath, os.path.join(modPath, '../doc/'),
                    modPath, 'doc/']
        for path in filter(None, pathList):
            try:
                fullPath = os.path.join(path, 'README.html')
                f = file(fullPath, 'r')
                f.close()
                return fullPath
            except IOError:
                pass
        return ''

    def help(self):
        """View the ReadMe file"""
        if not self.helpView:
            path = self.findHelpFile()
            if not path:
                QtGui.QMessageBox.warning(self, 'ConvertAll',
                                          'Read Me file not found')
                return
            self.helpView = helpview.HelpView(path, 'ConvertAll README File',
                                              self.icons)
        self.helpView.show()

    def about(self):
        """Show about info"""
        QtGui.QMessageBox.about(self, 'ConvertAll',
                                'ConvertAll Version %s\nby %s' %
                                (__version__, __author__))

    def closeEvent(self, event):
        """Save window data on close"""
        self.option.changeData('MainDlgXSize', self.width(), True)
        self.option.changeData('MainDlgYSize', self.height(), True)
        self.option.changeData('MainDlgXPos', self.x(), True)
        self.option.changeData('MainDlgYPos', self.y(), True)
        if self.findDlg:
            self.option.changeData('FinderXSize', self.findDlg.width(), True)
            self.option.changeData('FinderYSize', self.findDlg.height(), True)
            self.option.changeData('FinderXPos', self.findDlg.x(), True)
            self.option.changeData('FinderYPos', self.findDlg.y(), True)
        self.option.writeChanges()
        event.accept()
