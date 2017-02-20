#!/usr/bin/env python3

#****************************************************************************
# unitatom.py, provides class to hold data on each available unit
#
# ConvertAll, a units conversion program
# Copyright (C) 2017, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

import re
import copy
import unitdata


class UnitDatum:
    """Reads and stores data for a single unit, without an exponent.
    """
    badOpRegEx = re.compile(r'[^\d\.eE\+\-\*/]')
    eqnRegEx = re.compile(r'\[(.*?)\](.*)')
    def __init__(self, dataStr):
        """Initialize with a string from the data file.
        """
        dataList = dataStr.split('#')
        unitList = dataList.pop(0).split('=', 1)
        self.name = unitList.pop(0).strip()
        self.equiv = ''
        self.factor = 1.0
        self.fromEqn = ''   # used only for non-linear units
        self.toEqn = ''     # used only for non-linear units
        if unitList:
            self.equiv = unitList[0].strip()
            if self.equiv[0] == '[':   # used only for non-linear units
                try:
                    self.equiv, self.fromEqn = (UnitDatum.eqnRegEx.
                                                match(self.equiv).groups())
                    if ';' in self.fromEqn:
                        self.fromEqn, self.toEqn = self.fromEqn.split(';', 1)
                        self.toEqn = self.toEqn.strip()
                    self.fromEqn = self.fromEqn.strip()
                except AttributeError:
                    raise unitdata.UnitDataError(_('Bad equation for "{0}"').
                                                 format(self.name))
            else:                # split factor and equiv unit for linear
                parts = self.equiv.split(None, 1)
                if (len(parts) > 1 and
                    UnitDatum.badOpRegEx.search(parts[0]) == None):
                                      # only allowed digits and operators
                    try:
                        self.factor = float(eval(parts[0]))
                        self.equiv = parts[1]
                    except:
                        pass
            self.comments = [comm.strip() for comm in dataList]
            self.comments.extend([''] * (2 - len(self.comments)))
            self.keyWords = self.name.lower().split()
        self.viewLink = None
        self.typeName = ''

    def description(self):
        """Return name and 1st comment (usu. full name) if applicable.
        """
        if self.comments[0]:
            return '{0}  ({1})'.format(self.name, self.comments[0])
        return self.name

    def columnText(self, colNum):
        """Return text for given column number in the list view.
        """
        if colNum == 0:
            return self.description()
        if colNum == 1:
            return self.typeName
        return self.comments[1]

    def partialMatch(self, wordList):
        """Return True if parts of name start with items from wordList.
        """
        for word in wordList:
            for key in self.keyWords:
                if key.startswith(word):
                    return True
        return False

    def __lt__(self, other):
        """Less than comparison for sorting.
        """
        return self.name.lower() < other.name.lower()

    def __eq__(self, other):
        """Equality test.
        """
        return self.name.lower() == other.name.lower()


class UnitAtom:
    """Stores a unit datum or a temporary name with an exponent.
    """
    invalidExp = 1000
    def __init__(self, name='', unitDatum = None):
        """Initialize with either a text name or a unitDatum.
        """
        self.datum = None
        self.unitName = name
        self.exp = 1
        self.partialExp = ''  # starts with '^' for incomplete exp
        if unitDatum:
            self.datum = unitDatum
            self.unitName = unitDatum.name

    def unitValid(self):
        """Return True if unit and exponent are valid.
        """
        if (self.datum and self.datum.equiv and
            abs(self.exp) < UnitAtom.invalidExp):
            return True
        return False

    def unitText(self, absExp=False):
        """Return text for unit name with exponent or absolute value of exp.
        """
        exp = self.exp
        if absExp:
            exp = abs(self.exp)
        if self.partialExp:
            return '{0}{1}'.format(self.unitName, self.partialExp)
        if exp == 1:
            return self.unitName
        return '{0}^{1}'.format(self.unitName, exp)

    def __lt__(self, other):
        """Less than comparison for sorting.
        """
        return self.unitName.lower() < other.unitName.lower()

    def __eq__(self, other):
        """Equality test.
        """
        return self.unitName.lower() == other.unitName.lower()
