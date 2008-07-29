#!/usr/bin/env python

#****************************************************************************
# finddlg.py, provides dialog interface for unit find dialog
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
import convertdlg


class FindDlg(QtGui.QWidget):
    """Dialog for filtering and searching for units"""
    def __init__(self, mainDlg, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.setAttribute(QtCore.Qt.WA_QuitOnClose, False)
        self.mainDlg = mainDlg
        self.setWindowTitle('Unit Finder')
        self.currentType = ''
        self.currentSearch = ''

        mainLayout = QtGui.QVBoxLayout(self)
        upperLayout = QtGui.QHBoxLayout()
        mainLayout.addLayout(upperLayout)
        filterBox = QtGui.QGroupBox('&Filter Unit Types')
        upperLayout.addWidget(filterBox)
        filterLayout = QtGui.QHBoxLayout(filterBox)
        self.filterCombo = QtGui.QComboBox()
        filterLayout.addWidget(self.filterCombo)

        searchBox = QtGui.QGroupBox('&Search String')
        mainLayout.addWidget(searchBox)
        searchLayout = QtGui.QHBoxLayout(searchBox)
        self.searchEdit = QtGui.QLineEdit()
        searchLayout.addWidget(self.searchEdit)
        clearButton = QtGui.QPushButton('C&lear')
        searchLayout.addWidget(clearButton)
        clearButton.setFocusPolicy(QtCore.Qt.NoFocus)

        self.unitListView = FindUnitListView()
        mainLayout.addWidget(self.unitListView)

        lowerLayout = QtGui.QHBoxLayout()
        mainLayout.addLayout(lowerLayout)
        fromBox = QtGui.QGroupBox('From Unit')
        lowerLayout.addWidget(fromBox)
        fromLayout = QtGui.QVBoxLayout(fromBox)
        fromReplaceButton = QtGui.QPushButton('&Replace')
        fromLayout.addWidget(fromReplaceButton)
        self.connect(fromReplaceButton, QtCore.SIGNAL('clicked()'),
                     self.fromRepl)
        fromInsertButton = QtGui.QPushButton('&Insert')
        fromLayout.addWidget(fromInsertButton)
        self.connect(fromInsertButton, QtCore.SIGNAL('clicked()'),
                     self.fromIns)
        toBox = QtGui.QGroupBox('To Unit')
        lowerLayout.addWidget(toBox)
        toLayout = QtGui.QVBoxLayout(toBox)
        toReplaceButton = QtGui.QPushButton('Replac&e')
        toLayout.addWidget(toReplaceButton)
        self.connect(toReplaceButton, QtCore.SIGNAL('clicked()'), self.toRepl)
        toInsertButton = QtGui.QPushButton('Inser&t')
        toLayout.addWidget(toInsertButton)
        self.connect(toInsertButton, QtCore.SIGNAL('clicked()'), self.toIns)
        self.buttonList = [fromReplaceButton, fromInsertButton,
                           toReplaceButton, toInsertButton]

        closeButton = QtGui.QPushButton('&Close')
        upperLayout.addWidget(closeButton)
        self.connect(closeButton, QtCore.SIGNAL('clicked()'), self.close)

        option = self.mainDlg.option
        xSize = option.intData('FinderXSize', 0, 10000)
        ySize = option.intData('FinderYSize', 0, 10000)
        if xSize and ySize:
            self.resize(xSize, ySize)
        self.move(option.intData('FinderXPos', 0, 10000),
                  option.intData('FinderYPos', 0, 10000))
        self.loadUnits()
        for col in range(3):
            self.unitListView.resizeColumnToContents(col)
        self.loadTypes()
        self.connect(self.filterCombo,
                     QtCore.SIGNAL('activated(const QString&)'),
                     self.changeType)
        self.connect(self.searchEdit,
                     QtCore.SIGNAL('textEdited(const QString&)'),
                     self.changeSearch)
        self.connect(clearButton, QtCore.SIGNAL('clicked()'), self.searchEdit,
                     QtCore.SLOT('clear()'))
        self.connect(self.unitListView,
                     QtCore.SIGNAL('itemSelectionChanged()'), self.updateCtrls)

    def loadUnits(self):
        """Load unit items"""
        self.unitListView.clear()
        for unit in convertdlg.ConvertDlg.unitData.\
                               filteredList(self.currentType,
                                            self.currentSearch):
            FindUnitListItem(unit, self.unitListView)
        self.unitListView.sortItems(0, QtCore.Qt.AscendingOrder)
        if self.unitListView.topLevelItemCount() == 1:
            self.unitListView.setItemSelected(self.unitListView.
                                              topLevelItem(0), True)
        self.updateCtrls()

    def loadTypes(self):
        """Load combobox with type names"""
        types = convertdlg.ConvertDlg.unitData.typeList[:]
        types.sort()
        self.filterCombo.clear()
        self.filterCombo.addItem('[All]')
        prevName = ''
        for name in types:
            if name != prevName:
                self.filterCombo.addItem(name)
            prevName = name

    def updateCtrls(self):
        """Change active status of unit set buttons"""
        item = self.unitListView.selectedItems()
        for button in self.buttonList:
            button.setEnabled(item != [])

    def changeType(self, newType):
        """Change current unit type setting"""
        self.currentType = str(newType)
        if self.currentType == '[All]':
            self.currentType = ''
        self.loadUnits()

    def changeSearch(self, newStr):
        self.currentSearch = str(newStr)
        self.loadUnits()

    def fromRepl(self):
        """Replace from unit with selected unit"""
        item = self.unitListView.currentItem()
        if item:
            unit = item.unit
            self.mainDlg.fromGroup.clearUnit()
            self.mainDlg.fromGroup.replaceCurrent(unit)
            self.mainDlg.fromUnitEdit.unitUpdate()
            self.mainDlg.fromUnitListView.updateSelection()

    def fromIns(self):
        """Insert selected unit into from unit"""
        item = self.unitListView.currentItem()
        if item:
            unit = item.unit
            self.mainDlg.fromGroup.replaceCurrent(unit)
            self.mainDlg.fromUnitEdit.unitUpdate()
            self.mainDlg.fromUnitListView.updateSelection()

    def toRepl(self):
        """Replace to unit with selected unit"""
        item = self.unitListView.currentItem()
        if item:
            unit = item.unit
            self.mainDlg.toGroup.clearUnit()
            self.mainDlg.toGroup.replaceCurrent(unit)
            self.mainDlg.toUnitEdit.unitUpdate()
            self.mainDlg.toUnitListView.updateSelection()

    def toIns(self):
        """Insert selected unit into to unit"""
        item = self.unitListView.currentItem()
        if item:
            unit = item.unit
            self.mainDlg.toGroup.replaceCurrent(unit)
            self.mainDlg.toUnitEdit.unitUpdate()
            self.mainDlg.toUnitListView.updateSelection()


class FindUnitListView(QtGui.QTreeWidget):
    """ListView of units available"""
    def __init__(self, parent=None):
        QtGui.QTreeWidget.__init__(self, parent)
        self.setRootIsDecorated(False)
        self.setColumnCount(3)
        self.setHeaderLabels(['Unit Name', 'Unit Type', 'Comments'])
        self.header().setStretchLastSection(False)
        self.setSortingEnabled(True)

    def sizeHint(self):
        """Adjust width smaller"""
        size = QtGui.QTreeWidget.sizeHint(self)
        size.setWidth(self.columnWidth(0) + self.columnWidth(1) +
                      self.columnWidth(2) + 10 +   # fudge factor
                      self.verticalScrollBar().sizeHint().width())
        return size


class FindUnitListItem(QtGui.QTreeWidgetItem):
    """Item in the find unit list view"""
    def __init__(self, unit, parent=None):
        QtGui.QTreeWidgetItem.__init__(self, parent)
        self.unit = unit
        self.setText(0, unit.description())
        self.setText(1, unit.typeName)
        self.setText(2, unit.comments[1])
