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

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (QAbstractItemView, QTreeWidget, QTreeWidgetItem)
import convertdlg


class UnitListView(QTreeWidget):
    """ListView of units available.
    """
    unitChanged = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
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
        for name in convertdlg.ConvertDlg.unitData.sortedKeys:
            UnitListViewItem(convertdlg.ConvertDlg.unitData[name], self)
        for col in range(3):
            self.resizeColumnToContents(col)

    def relayChange(self):
        """Update list after buttons changed the unit group.
        """
        self.updateSelection(None)
        self.setFocus()
        self.unitChanged.emit()     # update unitEdit

    def updateSelection(self, focusProxy):
        """Update list after change to line editor.
           Set focus proxy to line editor if given.
        """
        if focusProxy:
            self.setFocusProxy(focusProxy)
        unitGroup = self.focusProxy().unitGroup
        self.blockSignals(True)
        self.enableButtons(True)
        self.clearSelection()
        unit = unitGroup.currentUnit()
        if unit and unit.equiv:
            self.setCurrentItem(unit.viewLink)
            unit.viewLink.setSelected(True)
        else:
            unit = unitGroup.currentPartialUnit()
            if unit:
                self.setCurrentItem(unit.viewLink)
                unit.viewLink.setSelected(False)
            else:
                unit = unitGroup.currentSortPos()
                self.enableButtons(False)
        self.scrollToCenter(unit)
        self.blockSignals(False)

    def replaceUnit(self):
        """Replace current unit in response to a selection change.
        """
        selectList = self.selectedItems()
        if selectList:
            selection = selectList[-1]
            self.focusProxy().unitGroup.replaceCurrent(selection.unit)
            self.unitChanged.emit()     # update unitEdit
            self.enableButtons(True)

    def enableButtons(self, enable=True):
        """Enable unit modification buttons for valid unit.
        """
        for button in self.buttonList:
            button.setEnabled(enable)

    def scrollToCenter(self, unit):
        """Scroll so given unit is in the center of the viewport.
        """
        unitItem = unit.viewLink
        index = self.indexOfTopLevelItem(unitItem)
        itemHeight = self.visualItemRect(unitItem).height()
        viewHeight = self.viewport().height()
        bottomIndex = index + viewHeight / (2 * itemHeight)
        bottomItem = self.topLevelItem(bottomIndex)
        if not bottomItem:
            bottomItem = self.topLevelItem(self.topLevelItemCount() - 1)
        self.scrollToItem(bottomItem, QAbstractItemView.PositionAtBottom)

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
