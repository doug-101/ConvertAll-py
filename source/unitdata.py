#!/usr/bin/env python3

#****************************************************************************
# unitdata.py, reads unit data from file
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
import collections
try:
    from __main__ import dataFilePath, lang
except ImportError:
    dataFilePath = None
    lang = ''
import unitatom


class UnitDataError(Exception):
    """General exception for unit data problems.
    """
    pass


class UnitData(collections.OrderedDict):
    """Reads unit data nad stores in a dictionary based on unit name.
    """
    def __init__(self):
        super().__init__()
        self.typeList = []
        self.filePath = None

    def findDataFile(self):
        """Search for data file, return line list or None.
        """
        modPath = os.path.abspath(sys.path[0])
        if modPath.endswith('.zip'):  # for py2exe
            modPath = os.path.dirname(modPath)
        pathList = [dataFilePath, os.path.join(modPath, '../data/'),
                    os.path.join(modPath, 'data/'), modPath]
        fileList = ['units.dat']
        if lang and lang != 'C':
            fileList[0:0] = ['units_{0}.dat'.format(lang),
                             'units_{0}.dat'.format(lang[:2])]
        for path in pathList:
            if path:
                for fileName in fileList:
                    try:
                        with open(os.path.join(path, fileName), 'r',
                                  encoding='utf-8') as f:
                            lineList = f.readlines()
                        self.filePath = os.path.abspath(os.path.join(path, fileName))
                        return lineList
                    except IOError:
                        pass
        raise UnitDataError(_('Can not read "units.dat" file'))

    def readData(self, filePath=None):
        """Read a catalogue atomically; reloading must not accumulate types.

        An explicit path is useful to validate every shipped translation.
        Without it, the original locale/resource discovery is retained.
        """
        if filePath is None:
            lines = self.findDataFile()
        else:
            try:
                with open(filePath, 'r', encoding='utf-8') as stream:
                    lines = stream.readlines()
            except (OSError, UnicodeError) as error:
                raise UnitDataError(_('Can not read "units.dat" file')) from error
        for i in range(len(lines) - 2, -1, -1):
            if lines[i].rstrip().endswith('\\'):
                lines[i] = ''.join([lines[i].rstrip()[:-1], lines[i+1]])
                lines[i+1] = ''
        units = [unitatom.UnitDatum(line) for line in lines if
                 line.split('#', 1)[0].strip()]
        typeText = ''
        typeList = []
        definitions = []
        for unit in units:
            if unit.name.startswith('[') and unit.name.endswith(']'):
                typeText = unit.name[1:-1].strip()
                typeList.append(typeText)
            elif not unit.equiv:
                raise UnitDataError(_('Invalid conversion for "{0}"').
                                    format(unit.name))
            else:
                unit.typeName = typeText
                definitions.append(unit)
        newData = collections.OrderedDict(
            (unit.name.lower().replace(' ', ''), unit)
            for unit in sorted(definitions))
        if len(newData) != len(definitions):
            raise UnitDataError(_('Duplicate unit names found'))
        # Do not change the old catalogue if parsing/validation failed.
        self.clear()
        self.update(newData)
        self.typeList = sorted(set(typeList))
        if filePath is not None:
            self.filePath = os.path.abspath(filePath)
        return len(definitions)

    def sortUnits(self, colNum, ascend=True):
        """Sort units using key from given column.
        """
        unitDict = self.copy()
        self.clear()
        self.update(sorted(unitDict.items(),
                           key=lambda u: u[1].columnText(colNum).lower(),
                           reverse=not ascend))

    def partialMatches(self, text):
        """Return list of units with names starting with parts of text.
        """
        textList = text.lower().split()
        return [unit for unit in self.values() if unit.partialMatch(textList)]

    def findPartialMatch(self, text):
        """Return first partially matching unit or None.
        """
        text = text.lower().replace(' ', '')
        if not text:
            return None
        for name in self.keys():
            if name.startswith(text):
                return self[name]
        return None
