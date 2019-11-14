#!/usr/bin/env python3

#****************************************************************************
# bases.py, provides conversions of number bases and fractions
#
# ConvertAll, a units conversion program
# Copyright (C) 2019, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

import math
from PyQt5.QtCore import Qt, QRegularExpression
from PyQt5.QtGui import QRegularExpressionValidator
from PyQt5.QtWidgets import (QApplication, QCheckBox, QDialog, QHBoxLayout,
                             QLabel, QLineEdit, QMessageBox, QPushButton,
                             QSpinBox, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout)
import numedit


class BasesDialog(QDialog):
    """A dialog for conversion of number bases.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint |
                            Qt.WindowSystemMenuHint)
        self.setWindowTitle(_('Base Conversions'))
        self.value = 0
        self.numBits = 32
        self.twosComplement = False
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        decimalLabel = QLabel(_('&Decmal'))
        layout.addWidget(decimalLabel)
        decimalEdit = QLineEdit()
        decimalLabel.setBuddy(decimalEdit)
        decimalEdit.base = 10
        decRegEx = QRegularExpression('[-0-9]*')
        decimalEdit.setValidator(QRegularExpressionValidator(decRegEx))
        layout.addWidget(decimalEdit)
        layout.addSpacing(8)
        hexLabel = QLabel(_('&Hex'))
        layout.addWidget(hexLabel)
        hexEdit = QLineEdit()
        hexLabel.setBuddy(hexEdit)
        hexEdit.base = 16
        hexRegEx = QRegularExpression('[-0-9a-fA-F]*')
        hexEdit.setValidator(QRegularExpressionValidator(hexRegEx))
        layout.addWidget(hexEdit)
        layout.addSpacing(8)
        octalLabel = QLabel(_('&Octal'))
        layout.addWidget(octalLabel)
        octalEdit = QLineEdit()
        octalLabel.setBuddy(octalEdit)
        octalEdit.base = 8
        octRegEx = QRegularExpression('[-0-7]*')
        octalEdit.setValidator(QRegularExpressionValidator(octRegEx))
        layout.addWidget(octalEdit)
        layout.addSpacing(8)
        binaryLabel = QLabel(_('&Binary'))
        layout.addWidget(binaryLabel)
        binaryEdit = QLineEdit()
        binaryLabel.setBuddy(binaryEdit)
        binaryEdit.base = 2
        binRegEx = QRegularExpression('[-01]*')
        binaryEdit.setValidator(QRegularExpressionValidator(binRegEx))
        layout.addWidget(binaryEdit)
        layout.addSpacing(8)
        self.bitsButton = QPushButton('')
        self.setButtonLabel()
        layout.addWidget(self.bitsButton)
        self.bitsButton.clicked.connect(self.changeBitSettings)
        layout.addSpacing(8)
        closeButton = QPushButton(_('&Close'))
        layout.addWidget(closeButton)
        closeButton.clicked.connect(self.close)
        self.editors = (decimalEdit, hexEdit, octalEdit, binaryEdit)
        for editor in self.editors:
            editor.textEdited.connect(self.updateValue)

    def updateValue(self):
        """Update the current number base and then the other editors.
        """
        activeEditor = self.focusWidget()
        text = activeEditor.text()
        if text:
            try:
                self.value = baseNum(text, activeEditor.base, self.numBits,
                                     self.twosComplement)
            except ValueError:
                QMessageBox.warning(self, 'ConvertAll', _('Number overflow'))
                activeEditor = None
        else:
            self.value = 0
        for editor in self.editors:
            if editor is not activeEditor:
                editor.setText(baseNumStr(self.value, editor.base,
                                          self.numBits, self.twosComplement))

    def changeBitSettings(self):
        """Show the dialog to update bit settings.
        """
        dlg = QDialog(self)
        dlg.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint |
                           Qt.WindowSystemMenuHint)
        dlg.setWindowTitle(_('Bit Settings'))
        topLayout = QVBoxLayout(dlg)
        dlg.setLayout(topLayout)
        bitLayout = QHBoxLayout()
        topLayout.addLayout(bitLayout)
        bitSizeBox = QSpinBox(dlg)
        bitSizeBox.setMinimum(1)
        bitSizeBox.setMaximum(256)
        bitSizeBox.setSingleStep(16)
        bitSizeBox.setValue(self.numBits)
        bitLayout.addWidget(bitSizeBox)
        label = QLabel(_('&bit overflow limit'), dlg)
        label.setBuddy(bitSizeBox)
        bitLayout.addWidget(label)
        twoCompBox = QCheckBox(_("&Use two's complement\n"
                                 "for negative numbers"), dlg)
        twoCompBox.setChecked(self.twosComplement)
        topLayout.addWidget(twoCompBox)

        ctrlLayout = QHBoxLayout()
        topLayout.addLayout(ctrlLayout)
        ctrlLayout.addStretch(0)
        okButton = QPushButton(_('&OK'), dlg)
        ctrlLayout.addWidget(okButton)
        okButton.clicked.connect(dlg.accept)
        cancelButton = QPushButton(_('&Cancel'), dlg)
        ctrlLayout.addWidget(cancelButton)
        cancelButton.clicked.connect(dlg.reject)
        if dlg.exec_() == QDialog.Accepted:
            self.numBits = bitSizeBox.value()
            self.twosComplement = twoCompBox.isChecked()
            self.setButtonLabel()

    def setButtonLabel(self):
        """Set the text label on the bitsButton to match settings.
        """
        text = '{0} {1}, '.format(self.numBits, _('bit'))
        if self.twosComplement:
            text += _('&two\'s complement')
        else:
            text += _('no &two\'s complement')
        self.bitsButton.setText(text)


class FractionDialog(QDialog):
    """A dialog for conversion of numbers into fractions.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint |
                            Qt.WindowSystemMenuHint)
        self.setWindowTitle(_('Fraction Conversions'))
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        expLabel = QLabel(_('&Expression'))
        layout.addWidget(expLabel)
        horizLayout = QHBoxLayout()
        layout.addLayout(horizLayout)
        horizLayout.setSpacing(5)
        self.exprEdit = QLineEdit()
        expLabel.setBuddy(self.exprEdit)
        horizLayout.addWidget(self.exprEdit)
        self.exprEdit.setValidator(numedit.FloatExprValidator(self))
        self.exprEdit.returnPressed.connect(self.calcFractions)
        enterButton = QPushButton(_('E&nter'))
        horizLayout.addWidget(enterButton)
        enterButton.setAutoDefault(False)
        enterButton.clicked.connect(self.calcFractions)
        layout.addSpacing(10)
        self.resultView = QTreeWidget()
        self.resultView.setColumnCount(2)
        self.resultView.setHeaderLabels([_('Fraction'), _('Decimal')])
        layout.addWidget(self.resultView)
        layout.addSpacing(10)
        self.powerTwoCtrl = QCheckBox(_('Limit denominators to powers of two'))
        layout.addWidget(self.powerTwoCtrl)
        layout.addSpacing(10)
        closeButton = QPushButton(_('&Close'))
        layout.addWidget(closeButton)
        closeButton.setAutoDefault(False)
        closeButton.clicked.connect(self.close)

    def calcFractions(self):
        """Find fractions from the expression in the editor.
        """
        self.resultView.clear()
        text = self.exprEdit.text()
        try:
            num = float(text)
        except ValueError:
            try:
                num = float(eval(text))
                output = [_('Entry'), '{0}'.format(num)]
                self.resultView.addTopLevelItem(QTreeWidgetItem(output))
            except:
                QMessageBox.warning(self, 'ConvertAll',
                                    _('Invalid expresssion'))
                return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        powerOfTwo = self.powerTwoCtrl.isChecked()
        for numer, denom in listFractions(num, powerOfTwo):
            output = ['{0}/{1}'.format(numer, denom),
                      '{0}'.format(numer / denom)]
            self.resultView.addTopLevelItem(QTreeWidgetItem(output))
        QApplication.restoreOverrideCursor()


def baseNumStr(number, base, numBits=32, twosComplement=False):
    """Return string of number in given base (2-16).

    Arguments:
        base -- the number base to convert to
        numBits -- the number of bits available for the result
        twosComplement -- if True, use two's complement for negative numbers
    """
    digits = '0123456789abcdef'
    number = int(round(number))
    result = ''
    sign = ''
    if number == 0:
        return '0'
    if twosComplement:
        if number >= 2**(numBits - 1) or \
                number < -2**(numBits - 1):
            return 'overflow'
        if number < 0:
            number = 2**numBits + number
    else:
        if number < 0:
            number = abs(number)
            sign = '-'
        if number >= 2**numBits:
            return 'overflow'
    while number:
        number, remainder = divmod(number, base)
        result = '{0}{1}'.format(digits[remainder], result)
    return '{0}{1}'.format(sign, result)


def baseNum(numStr, base, numBits=32, twosComplement=False):
    """Convert number string to an integer using given base.

    Arguments:
        base -- the number base to convert from
        numBits -- the number of bits available for the numStr
        twosComplement -- if True, use two's complement for negative numbers
    """
    numStr = numStr.replace(' ', '')
    if numStr == '-':
        return 0
    num = int(numStr, base)
    if num >= 2**numBits:
        raise ValueError
    if base != 10 and twosComplement and num >= 2**(numBits - 1):
        num = num - 2**numBits
    return num


def listFractions(decimal, powerOfTwo=False):
    """Return a list of numerator, denominator tuples.

    The tuples approximate the decimal, becoming more accurate.
    Arguments:
        decimal -- a real number to approximate as a fraction
        powerOfTwo -- if True, restrict the denominator to powers of 2
    """
    results = []
    denom = 2
    denomLimit = 10**9
    minDelta = denomLimit
    numer = round(decimal * denom)
    delta = abs(decimal - numer / denom)
    while denom < denomLimit:
        nextDenom = denom + 1 if not powerOfTwo else denom * 2
        nextNumer = round(decimal * nextDenom)
        nextDelta = abs(decimal - nextNumer / nextDenom)
        if numer != 0 and delta < minDelta and delta <= nextDelta:
            results.append((numer, denom))
            if delta == 0.0:
                break
            minDelta = delta
        denom = nextDenom
        numer = nextNumer
        delta = nextDelta
    if results:  # handle when first result is a whole num (2/2, 4/2, etc.)
        numer, denom = results[0]
        if denom == 2 and numer / denom == round(numer / denom):
            results[0] = (round(numer / denom), 1)
    return results
