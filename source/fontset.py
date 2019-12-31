#!/usr/bin/env python3

#****************************************************************************
# fontset.py, provides storage/retrieval and a dialog for custom fonts
#
# ConvertAll, a units conversion program
# Copyright (C) 2019, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

from PyQt5.QtCore import (QSize, Qt)
from PyQt5.QtGui import (QFontDatabase, QFontInfo, QIntValidator)
from PyQt5.QtWidgets import (QAbstractItemView, QCheckBox, QDialog,
                             QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                             QLineEdit, QListWidget, QPushButton, QVBoxLayout)


class CustomFontDialog(QDialog):
    """Dialog for selecting a custom font.
    """
    def __init__(self, sysFont, currentFont=None, parent=None):
        """Create a font customization dialog.
        """
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint |
                            Qt.WindowCloseButtonHint)
        self.setWindowTitle(_('Customize Font'))
        self.sysFont = sysFont
        self.currentFont = currentFont

        topLayout = QVBoxLayout(self)
        self.setLayout(topLayout)
        defaultBox = QGroupBox(_('Default Font'))
        topLayout.addWidget(defaultBox)
        defaultLayout = QVBoxLayout(defaultBox)
        self.defaultCheck = QCheckBox(_('&Use system default font'))
        defaultLayout.addWidget(self.defaultCheck)
        self.defaultCheck.setChecked(self.currentFont == None)
        self.defaultCheck.clicked.connect(self.setFontSelectAvail)

        self.fontBox = QGroupBox(_('Select Font'))
        topLayout.addWidget(self.fontBox)
        fontLayout = QGridLayout(self.fontBox)
        spacing = fontLayout.spacing()
        fontLayout.setSpacing(0)

        label = QLabel(_('&Font'))
        fontLayout.addWidget(label, 0, 0)
        label.setIndent(2)
        self.familyEdit = QLineEdit()
        fontLayout.addWidget(self.familyEdit, 1, 0)
        self.familyEdit.setReadOnly(True)
        self.familyList = SmallListWidget()
        fontLayout.addWidget(self.familyList, 2, 0)
        label.setBuddy(self.familyList)
        self.familyEdit.setFocusProxy(self.familyList)
        fontLayout.setColumnMinimumWidth(1, spacing)
        families = [family for family in QFontDatabase().families()]
        families.sort(key=str.lower)
        self.familyList.addItems(families)
        self.familyList.currentItemChanged.connect(self.updateFamily)

        label = QLabel(_('Font st&yle'))
        fontLayout.addWidget(label, 0, 2)
        label.setIndent(2)
        self.styleEdit = QLineEdit()
        fontLayout.addWidget(self.styleEdit, 1, 2)
        self.styleEdit.setReadOnly(True)
        self.styleList = SmallListWidget()
        fontLayout.addWidget(self.styleList, 2, 2)
        label.setBuddy(self.styleList)
        self.styleEdit.setFocusProxy(self.styleList)
        fontLayout.setColumnMinimumWidth(3, spacing)
        self.styleList.currentItemChanged.connect(self.updateStyle)

        label = QLabel(_('Si&ze'))
        fontLayout.addWidget(label, 0, 4)
        label.setIndent(2)
        self.sizeEdit = QLineEdit()
        fontLayout.addWidget(self.sizeEdit, 1, 4)
        self.sizeEdit.setFocusPolicy(Qt.ClickFocus)
        validator = QIntValidator(1, 512, self)
        self.sizeEdit.setValidator(validator)
        self.sizeList = SmallListWidget()
        fontLayout.addWidget(self.sizeList, 2, 4)
        label.setBuddy(self.sizeList)
        self.sizeList.currentItemChanged.connect(self.updateSize)

        fontLayout.setColumnStretch(0, 30)
        fontLayout.setColumnStretch(2, 25)
        fontLayout.setColumnStretch(4, 10)

        sampleBox = QGroupBox(_('Sample'))
        topLayout.addWidget(sampleBox)
        sampleLayout = QVBoxLayout(sampleBox)
        self.sampleEdit = QLineEdit()
        sampleLayout.addWidget(self.sampleEdit)
        self.sampleEdit.setAlignment(Qt.AlignCenter)
        self.sampleEdit.setText(_('AaBbCcDdEeFfGg...TtUuVvWvXxYyZz'))
        self.sampleEdit.setFixedHeight(self.sampleEdit.sizeHint().height() * 2)

        ctrlLayout = QHBoxLayout()
        topLayout.addLayout(ctrlLayout)
        ctrlLayout.addStretch()
        self.okButton = QPushButton(_('&OK'))
        ctrlLayout.addWidget(self.okButton)
        self.okButton.clicked.connect(self.accept)
        cancelButton = QPushButton(_('&Cancel'))
        ctrlLayout.addWidget(cancelButton)
        cancelButton.clicked.connect(self.reject)

        self.setFontSelectAvail()

    def setFontSelectAvail(self):
        """Disable font selection if default font is checked.

        Also set the controls with the current or default fonts.
        """
        if self.currentFont and not self.defaultCheck.isChecked():
            self.setFont(self.currentFont)
        else:
            self.setFont(self.sysFont)
        self.fontBox.setEnabled(not self.defaultCheck.isChecked())

    def setFont(self, font):
        """Set the font selector to the given font.
        
        Arguments:
            font -- the QFont to set.
        """
        fontInfo = QFontInfo(font)
        family = fontInfo.family()
        matches = self.familyList.findItems(family, Qt.MatchExactly)
        if matches:
            self.familyList.setCurrentItem(matches[0])
            self.familyList.scrollToItem(matches[0],
                                         QAbstractItemView.PositionAtTop)
        style = QFontDatabase().styleString(fontInfo)
        matches = self.styleList.findItems(style, Qt.MatchExactly)
        if matches:
            self.styleList.setCurrentItem(matches[0])
            self.styleList.scrollToItem(matches[0])
        else:
            self.styleList.setCurrentRow(0)
            self.styleList.scrollToItem(self.styleList.currentItem())
        size = repr(fontInfo.pointSize())
        matches = self.sizeList.findItems(size, Qt.MatchExactly)
        if matches:
            self.sizeList.setCurrentItem(matches[0])
            self.sizeList.scrollToItem(matches[0])

    def updateFamily(self, currentItem, previousItem):
        """Update the family edit box and adjust the style and size options.
        
        Arguments:
            currentItem -- the new list widget family item
            previousItem -- the previous list widget item
        """
        family = currentItem.text()
        self.familyEdit.setText(family)
        if self.familyEdit.hasFocus():
            self.familyEdit.selectAll()
        prevStyle = self.styleEdit.text()
        prevSize = self.sizeEdit.text()
        fontDb = QFontDatabase()
        styles = [style for style in fontDb.styles(family)]
        self.styleList.clear()
        self.styleList.addItems(styles)
        if prevStyle:
            try:
                num = styles.index(prevStyle)
            except ValueError:
                num = 0
            self.styleList.setCurrentRow(num)
            self.styleList.scrollToItem(self.styleList.currentItem())
        sizes = [repr(size) for size in fontDb.pointSizes(family)]
        self.sizeList.clear()
        self.sizeList.addItems(sizes)
        if prevSize:
            try:
                num = sizes.index(prevSize)
            except ValueError:
                num = 0
            self.sizeList.setCurrentRow(num)
            self.sizeList.scrollToItem(self.sizeList.currentItem())
            self.updateSample()

    def updateStyle(self, currentItem, previousItem):
        """Update the style edit box.
        
        Arguments:
            currentItem -- the new list widget style item
            previousItem -- the previous list widget item
        """
        if currentItem:
            style = currentItem.text()
            self.styleEdit.setText(style)
            if self.styleEdit.hasFocus():
                self.styleEdit.selectAll()
            self.updateSample()

    def updateSize(self, currentItem, previousItem):
        """Update the size edit box.
        
        Arguments:
            currentItem -- the new list widget size item
            previousItem -- the previous list widget item
        """
        if currentItem:
            size = currentItem.text()
            self.sizeEdit.setText(size)
            if self.sizeEdit.hasFocus():
                self.sizeEdit.selectAll()
            self.updateSample()

    def updateSample(self):
        """Update the font sample edit font.
        """
        font = self.readFont()
        if font:
            self.sampleEdit.setFont(font)

    def readFont(self):
        """Return the selected font or None.
        """
        family = self.familyEdit.text()
        style = self.styleEdit.text()
        size = self.sizeEdit.text()
        if family and style and size:
            return QFontDatabase().font(family, style, int(size))
        return None

    def resultingFont(self):
        """Return the selected font or None if system font.
        """
        if self.defaultCheck.isChecked():
            return None
        return self.readFont()


class SmallListWidget(QListWidget):
    """ListWidget with a smaller size hint.
    """
    def __init__(self, parent=None):
        """Initialize the widget.

        Arguments:
            parent -- the parent, if given
        """
        super().__init__(parent)

    def sizeHint(self):
        """Return smaller width.
        """
        itemHeight = self.visualItemRect(self.item(0)).height()
        return QSize(100, itemHeight * 6)
