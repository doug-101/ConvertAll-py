#!/usr/bin/env python3

#****************************************************************************
# unitlistview.py, provides a list view of available units
#
# ConvertAll, a units conversion program
# Copyright (C) 2016, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

from PyQt5.QtCore import (pyqtSignal, Qt, QItemSelectionModel)
from PyQt5.QtGui import QPalette
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QTreeWidget,
                             QTreeWidgetItem)
import convertdlg


class UnitListView(QTreeWidget):
    """ListView of units available.
    """
    unitChanged = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.highlightNum = 0
        self.buttonList = []
        self.setRootIsDecorated(False)
        self.setColumnCount(3)
        self.setHeaderLabels([_('Unit Name'), _('Unit Type'), _('Comments')])
        self.header().setStretchLastSection(False)
        self.itemSelectionChanged.connect(self.replaceUnit)
        self.loadUnits()

    def loadUnits(self):
        """Load unit items.
        """
        self.clear()
        for unit in convertdlg.ConvertDlg.unitData.values():
            UnitListViewItem(unit, self)
        for col in range(3):
            self.resizeColumnToContents(col)

    def relayChange(self):
        """Update list after buttons changed the unit group.
        """
        self.updateFiltering(None)
        self.setFocus()
        self.unitChanged.emit()     # update unitEdit

    def updateFiltering(self, focusProxy=None):
        """Update list after change to line editor.
           Set focus proxy to line editor if given.
        """
        if focusProxy:
            self.setFocusProxy(focusProxy)
        unitGroup = self.focusProxy().unitGroup
        currentUnit = unitGroup.currentUnit()
        unitData = convertdlg.ConvertDlg.unitData
        self.blockSignals(True)
        self.clear()
        if currentUnit and currentUnit.unitName:
            for unit in unitData.partialMatches(currentUnit.unitName):
                UnitListViewItem(unit, self)
            if currentUnit.datum and currentUnit.datum.viewLink:
                self.setCurrentItem(currentUnit.datum.viewLink)
                self.highlightNum = self.indexOfTopLevelItem(currentUnit.
                                                             datum.viewLink)
            self.enableButtons(True)
        else:
            for unit in unitData.values():
                UnitListViewItem(unit, self)
            self.enableButtons(False)
        if not self.currentItem() and self.topLevelItemCount():
            self.setHighlight(0)
        self.blockSignals(False)

    def replaceUnit(self):
        """Replace current unit in response to a selection change.
        """
        selectList = self.selectedItems()
        if selectList:
            selection = selectList[-1]
            self.focusProxy().unitGroup.replaceCurrent(selection.unit)
            self.unitChanged.emit()     # update unitEdit
            self.updateFiltering()

    def setHighlight(self, num):
        """Set the item at row num to be highlighted.
        """
        self.clearHighlight()
        item = self.topLevelItem(num)
        if item:
            if [item] != self.selectedItems():
                pal = QApplication.palette(self)
                brush = pal.brush(QPalette.Highlight)
                for col in range(3):
                    item.setForeground(col, brush)
            self.scrollToItem(item)
            self.highlightNum = num

    def clearHighlight(self):
        """Clear the highlight from currently highlighted item.
        """
        item = self.topLevelItem(self.highlightNum)
        if item and [item] != self.selectedItems():
            pal = QApplication.palette(self)
            brush = pal.brush(QPalette.Text)
            for col in range(3):
                item.setForeground(col, brush)

    def handleKeyPress(self, key):
        """Handle up/down, page up/down and enter key presses.
        """
        if key == Qt.Key_Up:
            pos = self.highlightNum - 1
        elif key == Qt.Key_Down:
            pos = self.highlightNum + 1
        elif key == Qt.Key_PageUp:
            ht = self.viewport().height()
            numVisible = (self.indexOfTopLevelItem(self.itemAt(0, ht)) -
                          self.indexOfTopLevelItem(self.itemAt(0, 0)))
            pos = self.highlightNum - numVisible
        elif key == Qt.Key_PageDown:
            ht = self.viewport().height()
            numVisible = (self.indexOfTopLevelItem(self.itemAt(0, ht)) -
                          self.indexOfTopLevelItem(self.itemAt(0, 0)))
            pos = self.highlightNum + numVisible
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            item = self.topLevelItem(self.highlightNum)
            if item:
                self.setCurrentItem(item)
            return
        else:
            return
        if pos < 0:
            pos = 0
        if pos >= self.topLevelItemCount():
            pos = self.topLevelItemCount() - 1
        self.setHighlight(pos)

    def enableButtons(self, enable=True):
        """Enable unit modification buttons for valid unit.
        """
        for button in self.buttonList:
            button.setEnabled(enable)

    def sizeHint(self):
        """Adjust width smaller.
        """
        size = super().sizeHint()
        size.setWidth(self.viewportSizeHint().width() + 5 +
                      self.verticalScrollBar().sizeHint().width())
        return size


class UnitListViewItem(QTreeWidgetItem):
    """Item in list view, references unit.
    """
    def __init__(self, unit, parent=None):
        super().__init__(parent)
        self.unit = unit
        unit.viewLink = self
        self.setText(0, unit.description())
        self.setText(1, unit.typeName)
        self.setText(2, unit.comments[1])
