#!/usr/bin/env python

#****************************************************************************
# unitlistview.py, provides a list view of available units
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
import convertdlg


class UnitListView(QtGui.QTreeWidget):
    """ListView of units available"""
    def __init__(self, unitGroup, unitRefNum, parent=None):
        QtGui.QTreeWidget.__init__(self, parent)
        self.unitGroup = unitGroup
        self.unitRefNum = unitRefNum
        self.buttonList = []
        self.setRootIsDecorated(False)
        self.setColumnCount(3)
        self.setHeaderLabels(['Unit Name', 'Unit Type', 'Comments'])
        self.header().setStretchLastSection(False)
        self.connect(self, QtCore.SIGNAL('itemSelectionChanged()'),
                     self.replaceUnit)
        self.loadUnits()

    def loadUnits(self):
        """Load unit items"""
        self.clear()
        for name in convertdlg.ConvertDlg.unitData.sortedKeys:
            UnitListViewItem(convertdlg.ConvertDlg.unitData[name],
                             self.unitRefNum, self)
        for col in range(3):
            self.resizeColumnToContents(col)

    def relayChange(self):
        """Update list after buttons changed the unit group"""
        self.updateSelection()
        self.setFocus()
        self.emit(QtCore.SIGNAL('unitChanged'))   # update unitEdit

    def updateSelection(self):
        """Update list after change to line editor"""
        self.blockSignals(True)
        self.enableButtons(True)
        self.clearSelection()
        unit = self.unitGroup.currentUnit()
        if unit:
            self.setCurrentItem(unit.viewLink[self.unitRefNum])
            self.setItemSelected(unit.viewLink[self.unitRefNum], True)
        else:
            unit = self.unitGroup.currentPartialUnit()
            if unit:
                self.setCurrentItem(unit.viewLink[self.unitRefNum])
                self.setItemSelected(unit.viewLink[self.unitRefNum], False)
            else:
                unit = self.unitGroup.currentSortPos()
                self.enableButtons(False)
        self.scrollToCenter(unit)
        self.blockSignals(False)

    def replaceUnit(self):
        """Replace current unit in response to a selection change"""
        selectList = self.selectedItems()
        if selectList:
            selection = selectList[-1]
            self.unitGroup.replaceCurrent(selection.unit)
            self.emit(QtCore.SIGNAL('unitChanged'))   # update unitEdit
            self.enableButtons(True)

    def enableButtons(self, enable=True):
        """Enable unit modification buttons for valid unit"""
        for button in self.buttonList:
            button.setEnabled(enable)

    def scrollToCenter(self, unit):
        """Scroll so given unit is in the center of the viewport"""
        unitItem = unit.viewLink[self.unitRefNum]
        index = self.indexOfTopLevelItem(unitItem)
        itemHeight = self.visualItemRect(unitItem).height()
        viewHeight = self.viewport().height()
        bottomIndex = index + viewHeight / (2 * itemHeight)
        bottomItem = self.topLevelItem(bottomIndex)
        if not bottomItem:
            bottomItem = self.topLevelItem(self.topLevelItemCount() - 1)
        self.scrollToItem(bottomItem, QtGui.QAbstractItemView.PositionAtBottom)

    def sizeHint(self):
        """Adjust width smaller"""
        size = QtGui.QTreeWidget.sizeHint(self)
        size.setWidth(self.columnWidth(0) + self.columnWidth(1) +
                      self.verticalScrollBar().sizeHint().width())
        return size


class UnitListViewItem(QtGui.QTreeWidgetItem):
    """Item in list view, references unit"""
    def __init__(self, unit, unitRefNum, parent=None):
        QtGui.QTreeWidgetItem.__init__(self, parent)
        self.unit = unit
        unit.viewLink[unitRefNum] = self
        self.setText(0, unit.description())
        self.setText(1, unit.typeName)
        self.setText(2, unit.comments[1])
