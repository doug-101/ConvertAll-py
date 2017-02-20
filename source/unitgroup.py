#!/usr/bin/env python3

#****************************************************************************
# unitgroup.py, provides a group of units and does conversions
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
from math import *
import unitatom
import unitdata


class UnitGroup:
    """Stores, updates and converts a group of units.
    """
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
        self.parenthClosed = True

    def flatUnitList(self):
        """Return the units with sub-groups flattened.
        """
        result = []
        for unit in self.unitList:
            if hasattr(unit, 'flatUnitList'):
                result.extend(unit.flatUnitList())
            else:
                result.append(unit)
        return result

    def unitGroups(self):
        """Return a list of this unit group and all sub-groups.
        """
        result = [self]
        for group in self.unitList:
            if hasattr(group, 'unitGroups'):
                result.extend(group.unitGroups())
        return result

    def unitGroupExpSign(self):
        """Return True if the first unit's exponent is positive.
        """
        unitList = self.unitList
        while unitList and not hasattr(unitList[0], 'exp'):
            unitList = unitList[0].unitList
        if unitList and unitList[0].exp < 0:
            return False
        return True

    def currentGroupPos(self):
        """Return a tuple of the group and position of the current unit.
        """
        currentUnit = self.currentUnit()
        if currentUnit:
            for group in self.unitGroups():
                for i in range(len(group.unitList)):
                    if group.unitList[i] is currentUnit:
                        return (group, i)
        return (self, 0)

    def update(self, text, cursorPos=None):
        """Decode user entered text into units.
        """
        self.unitList = self.parseGroup(text)
        if cursorPos != None:
            self.updateCurrentUnit(text, cursorPos)
        else:
            self.currentNum = len(self.flatUnitList()) - 1

    def updateCurrentUnit(self, text, cursorPos):
        """Set current unit number.
        """
        self.currentNum = len(UnitGroup.operRegEx.findall(text[:cursorPos]))

    def currentUnit(self):
        """Return current unit if set, o/w None.
        """
        try:
            return self.flatUnitList()[self.currentNum]
        except IndexError:
            return None

    def replaceCurrent(self, newUnit):
        """Replace the current unit with unit datum.
        """
        if self.unitList:
            oldUnit = self.currentUnit()
            group, pos = self.currentGroupPos()
            group.unitList[pos] = unitatom.UnitAtom('', newUnit)
            group.unitList[pos].exp = oldUnit.exp
        else:
            self.unitList.append(unitatom.UnitAtom('', newUnit))

    def addOper(self, mult):
        """Add new operator & blank unit after current, * if mult is true.
        """
        if self.unitList:
            group, pos = self.currentGroupPos()
            self.currentNum += 1
            group.unitList.insert(pos + 1, unitatom.UnitAtom(''))
            if not mult:
                self.currentUnit().exp = -1

    def changeExp(self, newExp):
        """Change the current unit's exponent.
        """
        currentUnit = self.currentUnit()
        if currentUnit:
            if currentUnit.exp > 0:
                currentUnit.exp = newExp
            else:
                currentUnit.exp = -newExp

    def clearUnit(self):
        """Remove units.
        """
        self.unitList = []
        self.currentNum = 0
        self.factor = 1.0
        self.reducedList = []
        self.linear = True

    def parseGroup(self, text):
        """Return list of units from text string.
        """
        unitList = []
        parts = [part.strip() for part in UnitGroup.operGroupRegEx.split(text)
                 if part.strip()]
        numerator = True
        while parts:
            part = parts.pop(0)
            if part == '*' or part  == '/':
                parts.insert(0, part)
                part = ''      # add blank invalid unit if order wrong
            if part.startswith('('):
                part = part[1:]
                group = UnitGroup(self.unitData, self.option)
                if part.endswith(')'):
                    part = part[:-1]
                else:
                    group.parenthClosed = False
                group.update(part)
                if not group.unitList:
                    group.unitList.append(group.parseUnit(''))
                if not numerator:
                    for unit in group.flatUnitList():
                        unit.exp = -unit.exp
                unitList.append(group)
            else:
                unit = self.parseUnit(part)
                if not numerator:
                    unit.exp = -unit.exp
                unitList.append(unit)
            if parts:
                oper = parts.pop(0)
                if oper == '*' or oper == '/':
                    numerator = oper == '*' and True or False
                    if not parts:
                        parts.insert(0, '')  # add blank invalid unit at end
                else:
                    parts.insert(0, oper)  # put unit back if order wrong
        return unitList

    def parseUnit(self, text):
        """Return a valid or invalid unit with exponent from a text string.
        """
        parts = text.split('^', 1)
        exp = 1
        partialExp = ''
        if len(parts) > 1:   # has exponent
            expText = parts[1].strip()
            try:
                exp = int(expText)
                if exp == 1:
                    partialExp = '^1'  # keep for start of '1.5'
                elif expText == '-0':
                    partialExp = '^-0' # keep for start of '-0.5'
            except ValueError:
                try:
                    exp = float(expText)
                    if expText.endswith('.'):
                        partialExp = '^' + expText
                except ValueError:
                    if expText == '.':
                        partialExp = '^0.'
                    elif expText == '-.':
                        partialExp = '^-0.'
                    elif expText.startswith('-'):
                        partialExp = '^-'
                    else:
                        partialExp = '^'
                    exp = unitatom.UnitAtom.invalidExp
        unitText = parts[0].strip().lower().replace(' ', '')
        unit = self.unitData.get(unitText)
        if not unit and unitText:
            if unitText[-1] in ('2', '3') and self.unitData.get(unitText[:-1]):
                unit = self.unitData.get(unitText[:-1])
                exp = int(unitText[-1])
            elif (unitText[-1] == 's' and not
                  self.unitData.findPartialMatch(unitText)): # check for plural
                unit = self.unitData.get(unitText[:-1])
        if unit:
            unitAtom = unitatom.UnitAtom('', unit)
        else:
            unitAtom = unitatom.UnitAtom(parts[0].strip())  # tmp invalid unit
        unitAtom.exp = exp
        unitAtom.partialExp = partialExp
        return unitAtom

    def unitString(self, unitList=None, swapExpSign=False):
        """Return the full string for this group or a given group.
        """
        if unitList == None:
            unitList = self.unitList
        fullText = ''
        if unitList:
            firstUnit = True
            for unit in unitList:
                if not firstUnit:
                    if hasattr(unit, 'exp'):
                        expSign = unit.exp >= 0
                    else:
                        expSign = unit.unitGroupExpSign()
                    if swapExpSign:
                        expSign = not expSign
                    fullText = '{0} {1} '.format(fullText,
                                                 expSign and '*' or '/')
                if hasattr(unit, 'unitText'):
                    fullText = '{0}{1}'.format(fullText,
                                               unit.unitText(swapExpSign or
                                                             not firstUnit))
                else:
                    if firstUnit and not swapExpSign:
                        swap = False
                    else:
                        swap = not unit.unitGroupExpSign()
                    fullText = '{0}({1}{2}'.format(fullText,
                                              unit.unitString(None, swap),
                                              unit.parenthClosed and ')' or '')
                firstUnit = False
        return fullText

    def groupValid(self):
        """Return True if all units are valid.
        """
        if not self.unitList or not self.parenthClosed:
            return False
        for unit in self.unitList:
            if hasattr(unit, 'unitValid'):
                if not unit.unitValid():
                    return False
            else:
                if not unit.groupValid():
                    return False
        return True

    def reduceGroup(self):
        """Update reduced list of units and factor.
        """
        self.linear = True
        self.reducedList = []
        self.factor = 1.0
        if not self.groupValid():
            return
        count = 0
        tmpList = self.flatUnitList()
        while tmpList:
            count += 1
            if count > 5000:
                raise unitdata.UnitDataError(_('Circular unit definition'))
            unit = tmpList.pop(0)
            if unit.datum.equiv.startswith('!'):
                newUnit = unitatom.UnitAtom('', unit.datum)
                newUnit.exp = unit.exp
                self.reducedList.append(newUnit)
            elif not unit.datum.equiv:
                raise unitdata.UnitDataError(_('Invalid conversion for "{0}"').
                                             format(unit.unitName))
            else:
                if unit.datum.fromEqn:
                    self.linear = False
                equivUnit = UnitGroup(self.unitData, self.option)
                equivUnit.update(unit.datum.equiv)
                newList = equivUnit.flatUnitList()
                for newUnit in newList:
                    newUnit.exp *= unit.exp
                tmpList.extend(newList)
                self.factor *= unit.datum.factor**unit.exp
        self.reducedList.sort()
        tmpList = self.reducedList[:]
        self.reducedList = []
        for unit in tmpList:
            if self.reducedList and unit == self.reducedList[-1]:
                self.reducedList[-1].exp += unit.exp
            else:
                self.reducedList.append(unit)
        self.reducedList = [unit for unit in self.reducedList if
                            unit.datum.equiv != '!!' and
                            unit.datum.name != 'unit' and unit.exp != 0]

    def categoryMatch(self, otherGroup):
        """Return True if unit types are equivalent.
        """
        if not self.checkLinear() or not otherGroup.checkLinear():
            return False
        return (self.reducedList == otherGroup.reducedList and
                [unit.exp for unit in self.reducedList] ==
                [unit.exp for unit in otherGroup.reducedList])

    def checkLinear(self):
        """Return True if linear or acceptable non-linear.
        """
        if not self.linear:
            flatList = self.flatUnitList()
            if len(flatList) > 1 or flatList[0].exp != 1:
                return False
        return True

    def compatStr(self):
        """Return string with reduced unit or linear compatability problem.
        """
        if self.checkLinear():
            return self.unitString(self.reducedList)
        return _('Cannot combine non-linear units')

    def convert(self, num, toGroup):
        """Return num of this group converted to toGroup.
        """
        if self.linear:
            num *= self.factor
        else:
            num = self.nonLinearCalc(num, 1) * self.factor
        if toGroup.linear:
            return num / toGroup.factor
        return toGroup.nonLinearCalc(num / toGroup.factor, 0)

    def nonLinearCalc(self, num, isFrom):
        """Return result of non-linear calculation.
        """
        x = num
        try:
            unit = self.flatUnitList()[0]
            if unit.datum.toEqn:      # regular equations
                if isFrom:
                    return float(eval(unit.datum.fromEqn))
                return float(eval(unit.datum.toEqn))
            data = list(eval(unit.datum.fromEqn))  # extrapolation list
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
            return ((num-data[pos-1][0]) / float(data[pos][0]-data[pos-1][0]) *
                    (data[pos][1]-data[pos-1][1]) + data[pos-1][1])
        except OverflowError:
            return 1e9999
        except:
            raise unitdata.UnitDataError(_('Bad equation for {0}').
                                         format(unit.datum.name))

    def convertStr(self, num, toGroup):
        """Return formatted string of converted number.
        """
        return self.formatNumStr(self.convert(num, toGroup))

    def formatNumStr(self, num):
        """Return num string formatted per options.
        """
        decPlcs = self.option.intData('DecimalPlaces', 0, UnitGroup.maxDecPlcs)
        notation = self.option.strData('Notation')
        if notation == 'fixed':
            return '{0:0.{prec}f}'.format(num, prec = decPlcs)
        if notation == 'scientific':
            return '{0:0.{prec}E}'.format(num, prec = decPlcs)
        if notation == 'engineering':
            exp = 3 * (floor(log10(abs(num))) // 3)
            num = round(num / 10**exp, decPlcs)
            # check if rounding bumps exponent
            if abs(num) >= 1000.0:
                num /= 1000.0
                exp += 3
            return '{0:0.{prec}f}E{1:0=+3d}'.format(num, exp, prec = decPlcs)
        # general short representation
        return '{0:0.{prec}G}'.format(num, prec = decPlcs)


if __name__ == '__main__':
    import unitdata
    import option
    options = option.Option('convertall', 20)
    options.loadAll(["DecimalPlaces       8",
                     "Notation            general"])
    data = unitdata.UnitData()
    data.readData()
    fromText = input('Enter from unit -> ')
    fromUnit = UnitGroup(data, options)
    fromUnit.update(fromText)
    toText = input('Enter to unit -> ')
    toUnit = UnitGroup(data, options)
    toUnit.update(toText)
    print('{0}   TO   {1}'.format(fromUnit.unitString(), toUnit.unitString()))
    fromUnit.reduceGroup()
    toUnit.reduceGroup()
    print('{0}   TO   {1}'.format(fromUnit.unitString(fromUnit.reducedList),
                                  toUnit.unitString(toUnit.reducedList)))
    if not fromUnit.categoryMatch(toUnit):
        print('NO MATCH')
    else:
        print('MATCH')
        numText = input('Enter value -> ')
        num = float(numText)
        print('{0}  IS  {1}'.format(num, fromUnit.convert(num, toUnit)))
