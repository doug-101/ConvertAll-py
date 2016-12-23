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
import re


class UnitListView(QTreeWidget):
    """ListView of units available.
    """
    unitChanged = pyqtSignal()
    haveCurrentUnit = pyqtSignal(bool, bool)
    # pass True if unitEdit active, then True if have unit text, o/w False
    def __init__(self, unitData, parent=None):
        super().__init__(parent)
        self.unitData = unitData
        self.highlightNum = 0
        self.typeFilter = ''
        self.setRootIsDecorated(False)
        self.setColumnCount(3)
        self.setHeaderLabels([_('Unit Name'), _('Unit Type'), _('Comments')])
        self.header().setStretchLastSection(False)
        self.header().setSortIndicatorShown(True)
        self.header().setSectionsClickable(True)
        self.header().setSortIndicator(0, Qt.AscendingOrder)
        self.header().sectionClicked.connect(self.changeSort)
        self.itemSelectionChanged.connect(self.replaceUnit)
        self.loadUnits()

    def loadUnits(self):
        """Load unit items.
        """
        self.clear()
        for unit in self.unitData.values():
            UnitListViewItem(unit, self)
        for col in range(3):
            self.resizeColumnToContents(col)

    def updateFiltering(self, focusProxy=None):
        """Update list after change to line editor.
           Set focus proxy to line editor if given (no change if None).
        """
        if focusProxy:
            self.setFocusProxy(focusProxy)
        if self.focusProxy():
            currentUnit = self.focusProxy().unitGroup.currentUnit()
        else:
            currentUnit = None
        self.blockSignals(True)
        self.clear()
        if currentUnit and currentUnit.unitName:
            for unit in self.unitData.partialMatches(currentUnit.unitName):
                if not self.typeFilter or unit.typeName == self.typeFilter:
                    UnitListViewItem(unit, self)
                else:
                    unit.viewLink = None
            if currentUnit.datum and currentUnit.datum.viewLink:
                self.setCurrentItem(currentUnit.datum.viewLink)
                self.highlightNum = self.indexOfTopLevelItem(currentUnit.
                                                             datum.viewLink)
        else:
            for unit in self.unitData.values():
                if not self.typeFilter or unit.typeName == self.typeFilter:
                    UnitListViewItem(unit, self)
                else:
                    unit.viewLink = None
        if (not self.currentItem() and self.focusProxy() and
            self.topLevelItemCount()):
            self.setHighlight(0)
        self.blockSignals(False)
        self.haveCurrentUnit.emit(bool(self.focusProxy()),
                                  bool(currentUnit and currentUnit.unitName))

    def resetFiltering(self):
        """Clear the focus proxy and remove search filtering.
        """
        if self.focusProxy():
            self.setFocusProxy(None)
            self.updateFiltering()

    def replaceUnit(self):
        """Replace current unit in response to a selection change.
        """
        selectList = self.selectedItems()
        if selectList:
            selection = selectList[-1]
            if self.focusProxy():
                self.focusProxy().unitGroup.replaceCurrent(selection.unit)
                self.unitChanged.emit()     # update unitEdit
                self.updateFiltering()
            else:
                self.setCurrentItem(None)
                self.setHighlight(self.indexOfTopLevelItem(selection))

    def addUnitText(self):
        """Add exponent or operator text from push button to unit group.
           Autocomplete a highlighted unit if not selected.
        """
        if self.focusProxy():
            button = self.sender()
            text = re.match(r'.*\((.*?)\)$', button.text()).group(1)
            if not self.selectedItems():
                item = self.topLevelItem(self.highlightNum)
                if item:
                    self.setCurrentItem(item)
            if text.startswith('^'):
                self.focusProxy().unitGroup.changeExp(int(text[1:]))
            else:
                self.focusProxy().unitGroup.addOper(text == '*')
                self.updateFiltering()
            self.unitChanged.emit()

    def clearUnitText(self):
        """Remove all unit text.
        """
        if self.focusProxy():
            self.focusProxy().unitGroup.clearUnit()
            self.unitChanged.emit()
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

    def changeSort(self):
        """Change the sort order based on a header click.
        """
        colNum = self.header().sortIndicatorSection()
        order = self.header().sortIndicatorOrder() == Qt.AscendingOrder
        self.unitData.sortUnits(colNum, order)
        self.updateFiltering()

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
        for colNum in range(3):
            self.setText(colNum, unit.columnText(colNum))
