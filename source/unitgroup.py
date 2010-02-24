#!/usr/bin/env python

#****************************************************************************
# unitgroup.py, provides a group of units and does conversions
#
# ConvertAll, a units conversion program
# Copyright (C) 2006, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

import re
from math import *
from unitatom import UnitAtom
import unitdata


class UnitGroup(object):
    """Stores, updates and converts a group of units"""
    maxDecPlcs = 12
    operRegEx = re.compile(r'[\*/]')
    operGroupRegEx = re.compile(r'(\(.*\)|\(.*$|[\*/])')
    def __init__(self, unitData, option):
        self.unitData = unitData
        self.option = option
        self.unitList = []
        self.currentNum = 0
        self.factor = 1.0
        self.reducedList = []
        self.linear = True

    def flatUnitList(self):
        """Return the units with sub-groups flattened"""
        result = []
        for unit in self.unitList:
            if hasattr(unit, 'flatUnitList'):
                result.extend(unit.flatUnitList())
            else:
                result.append(unit)
        return result

    def unitGroups(self):
        """Return a list of this unit group and all sub-groups"""
        result = [self]
        for group in self.unitList:
            if hasattr(group, 'unitGroups'):
                result.extend(group.unitGroups())
        return result

    def unitGroupExpSign(self):
        """Return True if the first unit's exponent is positive"""
        unitList = self.unitList
        while unitList and not hasattr(unitList[0], 'exp'):
            unitList = unitList[0].unitList
        if unitList and unitList[0].exp < 0:
            return False
        return True

    def currentGroupPos(self):
        """Return a tuple of the group and position of the current unit"""
        currentUnit = self.currentUnit()
        if currentUnit:
            for group in self.unitGroups():
                for i in range(len(group.unitList)):
                    if group.unitList[i] is currentUnit:
                        return (group, i)
        return (self, 0)

    def update(self, text, cursorPos=None):
        """Decode user entered text into units"""
        self.unitList = self.parseGroup(text)
        if cursorPos != None:
            self.updateCurrentUnit(text, cursorPos)
        else:
            self.currentNum = len(self.flatUnitList()) - 1

    def updateCurrentUnit(self, text, cursorPos):
        """Set current unit number"""
        self.currentNum = len(UnitGroup.operRegEx.findall(text[:cursorPos]))

    def currentUnit(self):
        """Return current unit if set, o/w None"""
        if self.unitList:
            return self.flatUnitList()[self.currentNum]
        return None

    def currentPartialUnit(self):
        """Return unit with at least a partial match, o/w None"""
        currentUnit = self.currentUnit()
        if not currentUnit:
            return None
        return self.unitData.findPartialMatch(currentUnit.name)

    def currentSortPos(self):
        """Return unit near current unit for sorting"""
        if not self.unitList:
            return self.unitData[self.unitData.sortedKeys[0]]
        return self.unitData.findSortPos(self.currentUnit().name)

    def replaceCurrent(self, newUnit):
        """Replace the current unit with unit"""
        if self.unitList:
            oldUnit = self.currentUnit()
            group, pos = self.currentGroupPos()
            group.unitList[pos] = newUnit.copy()
            group.unitList[pos].exp = oldUnit.exp
            return
        self.unitList.append(newUnit.copy())

    def completePartial(self):
        """Replace a partial unit with a full one"""
        partUnit = self.currentUnit()
        if partUnit and not partUnit.equiv:
            newUnit = self.unitData.findPartialMatch(partUnit.name)
            if newUnit:
                self.replaceCurrent(newUnit)

    def moveToNext(self, upward):
        """Replace unit with adjacent one based on match or sort position"""
        unit = self.currentSortPos()
        name = unit.name.lower().replace(' ', '')
        num = self.unitData.sortedKeys.index(name) + (upward and -1 or 1)
        if 0 <= num < len(self.unitData.sortedKeys):
            self.replaceCurrent(self.unitData[self.unitData.sortedKeys[num]])

    def addOper(self, mult):
        """Add new operator & blank unit after current, * if mult is true"""
        if self.unitList:
            self.completePartial()
            prevExp = self.currentUnit().exp
            group, pos = self.currentGroupPos()
            self.currentNum += 1
            group.unitList.insert(pos + 1, UnitAtom(u''))
            # TODO:  Check if prevExp is required
            if (not mult and prevExp > 0) or (mult and prevExp < 0):
                self.currentUnit().exp = -1

    def changeExp(self, newExp):
        """Change the current unit's exponent"""
        self.completePartial()
        currentUnit = self.currentUnit()
        if self.currentUnit:
            if self.currentUnit.exp > 0:
                self.currentUnit.exp = newExp
            else:
                self.currentUnit.exp = -newExp

    def clearUnit(self):
        """Remove units"""
        self.unitList = []
        self.currentNum = 0
        self.factor = 1.0
        self.reducedList = []
        self.linear = True

    def parseGroup(self, text):
        """Return list of units from text string"""
        unitList = []
        parts = [part.strip() for part in UnitGroup.operGroupRegEx.split(text)
                 if part.strip()]
        numerator = True
        while parts:
            part = parts.pop(0)
            if part.startswith('('):
                part = part[1:]
                if part.endswith(')'):
                    part = part[:-1]
                group = UnitGroup(self.unitData, self.option)
                group.update(part)
                if not numerator:
                    for unit in group.flatUnitList():
                        unit.exp = -unit.exp
                unitList.append(group)
            else:
                unit = self.parseUnit(part)
                if not numerator:
                    unit.exp = -unit.exp
                unitList.append(unit)
            if parts and parts.pop(0) == '/':
                numerator = False
        return unitList

    def parseUnit(self, text):
        """Return a valid or invalid unit with exponent from a text string"""
        parts = text.split('^', 1)
        exp = 1
        if len(parts) > 1:   # has exponent
            try:
                exp = int(parts[1])
            except ValueError:
                if parts[1].lstrip().startswith('-'):
                    exp = -UnitAtom.partialExp  # tmp invalid exp
                else:
                    exp = UnitAtom.partialExp
        unitText = parts[0].strip().lower().replace(' ', '')
        unit = self.unitData.get(unitText, None)
        if not unit and unitText and unitText[-1] == 's' and not \
           self.unitData.findPartialMatch(unitText):   # check for plural
            unit = self.unitData.get(unitText[:-1], None)
        if not unit:
            unit = UnitAtom(parts[0].strip())   # tmp invalid unit
        unit = unit.copy()
        unit.exp = exp
        return unit

    def unitString(self, unitList=None):
        """Return the full string for this group or a given group"""
        if unitList == None:
            unitList = self.unitList
        fullText = ''
        if unitList:
            fullText = unitList[0].unitText(False)
            numerator = True
            for unit in unitList[1:]:
                if (numerator and unit.exp > 0) \
                   or (not numerator and unit.exp < 0):
                    fullText = u'%s * %s' % (fullText, unit.unitText(True))
                else:
                    fullText = u'%s / %s' % (fullText, unit.unitText(True))
                    numerator = not numerator
        return fullText

    def groupValid(self):
        """Return True if all units are valid"""
        if not self.unitList:
            return False
        for unit in self.unitList:
            if not unit.unitValid():
                return False
        return True

    def reduceGroup(self):
        """Update reduced list of units and factor"""
        self.linear = True
        self.reducedList = []
        self.factor = 1.0
        if not self.groupValid():
            return
        count = 0
        tmpList = self.unitList[:]
        while tmpList:
            count += 1
            if count > 5000:
                raise unitdata.UnitDataError, _('Circular unit definition')
            unit = tmpList.pop(0)
            if unit.equiv == '!':
                self.reducedList.append(unit.copy())
            elif not unit.equiv:
                raise unitdata.UnitDataError, \
                      _('Invalid conversion for "%s"') % unit.name
            else:
                if unit.fromEqn:
                    self.linear = False
                newList = self.parseGroup(unit.equiv)
                for newUnit in newList:
                    newUnit.exp *= unit.exp
                tmpList.extend(newList)
                self.factor *= unit.factor**unit.exp
        self.reducedList.sort()
        tmpList = self.reducedList[:]
        self.reducedList = []
        for unit in tmpList:
            if self.reducedList and unit == self.reducedList[-1]:
                self.reducedList[-1].exp += unit.exp
            else:
                self.reducedList.append(unit)
        self.reducedList = [unit for unit in self.reducedList if
                            unit.name != u'unit' and unit.exp != 0]

    def categoryMatch(self, otherGroup):
        """Return True if unit types are equivalent"""
        if not self.checkLinear() or not otherGroup.checkLinear():
            return False
        return self.reducedList == otherGroup.reducedList and \
               [unit.exp for unit in self.reducedList] == \
               [unit.exp for unit in otherGroup.reducedList]

    def checkLinear(self):
        """Return True if linear or acceptable non-linear"""
        if not self.linear:
            if len(self.unitList) > 1 or self.unitList[0].exp != 1:
                return False
        return True

    def compatStr(self):
        """Return string with reduced unit or linear compatability problem"""
        if self.checkLinear():
            return self.unitString(self.reducedList)
        return _('Cannot combine non-linear units')

    def convert(self, num, toGroup):
        """Return num of this group converted to toGroup"""
        if self.linear:
            num *= self.factor
        else:
            num = self.nonLinearCalc(num, 1) * self.factor
        if toGroup.linear:
            return num / toGroup.factor
        return toGroup.nonLinearCalc(num / toGroup.factor, 0)

    def nonLinearCalc(self, num, isFrom):
        """Return result of non-linear calculation"""
        x = num
        try:
            if self.unitList[0].toEqn:      # regular equations
                if isFrom:
                    return float(eval(self.unitList[0].fromEqn))
                return float(eval(self.unitList[0].toEqn))
            data = list(eval(self.unitList[0].fromEqn))  # extrapolation list
            if isFrom:
                data = [(float(group[0]), float(group[1])) for group in data]
            else:
                data = [(float(group[1]), float(group[0])) for group in data]
            data.sort()
            pos = len(data) - 1
            for i in range(len(data)):
                if num <= data[i][0]:
                    pos = i
                    break
            if pos == 0:
                pos = 1
            return (num-data[pos-1][0]) / float(data[pos][0]-data[pos-1][0]) \
                   * (data[pos][1]-data[pos-1][1]) + data[pos-1][1]
        except OverflowError:
            return 1e9999
        except:
            raise unitdata.UnitDataError, \
                  _('Bad equation for %s') % self.unitList[0].name

    def convertStr(self, num, toGroup):
        """Return formatted string of converted number"""
        return self.formatNumStr(self.convert(num, toGroup))

    def formatNumStr(self, num):
        """Return num string formatted per options"""
        decPlcs = self.option.intData('DecimalPlaces', 0, UnitGroup.maxDecPlcs)
        if self.option.boolData('SciNotation'):
            return (u'%%0.%dE' % decPlcs) % num
        if self.option.boolData('FixedDecimals'):
            return (u'%%0.%df' % decPlcs) % num
        return (u'%%0.%dG' % decPlcs) % num


if __name__ == '__main__':
    import unitdata
    import option
    options = option.Option('convertall', 20)
    options.loadAll(["DecimalPlaces       8",
                     "SciNotation         no",
                     "FixedDecimals       no"])
    data = unitdata.UnitData()
    data.readData()
    fromText = raw_input('Enter from unit -> ')
    fromUnit = UnitGroup(data, options)
    fromUnit.update(fromText)
    toText = raw_input('Enter to unit -> ')
    toUnit = UnitGroup(data, options)
    toUnit.update(toText)
    print u'%s   TO   %s' % (fromUnit.unitString(), toUnit.unitString())
    fromUnit.reduceGroup()
    toUnit.reduceGroup()
    print u'%s   TO   %s' % (fromUnit.unitString(fromUnit.reducedList),
                             toUnit.unitString(toUnit.reducedList))
    if not fromUnit.categoryMatch(toUnit):
        print 'NO MATCH'
    else:
        print 'MATCH'
        numText = raw_input('Enter value -> ')
        num = float(numText)
        print u'%f   IS  %f' % (num, fromUnit.convert(num, toUnit))
