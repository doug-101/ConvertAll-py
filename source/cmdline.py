#!/usr/bin/env python

#****************************************************************************
# cmdline.py, provides a class to read and execute command line arguments
#
# ConvertAll, a units conversion program
# Copyright (C) 2010, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

import sys
import re
try:
    from __main__ import localEncoding
except ImportError:
    localEncoding = 'utf-8'
import option
import optiondefaults
import unitdata
import unitgroup

usage = [_('Usage:'),
         '',
         '   convertall [%s]' % _('qt-options'),
         '',
         _('-or- (non-GUI):'),
         '   convertall [%s] [%s] %s [%s]' % (_('options'), _('number'),
                                              _('from_unit'), _('to_unit')),
         '',
         _('-or- (non-GUI):'),
         '   convertall -i [%s]' % _('options'),
         '',
         _('Units with spaces must be "quoted"'),
         '',
         _('Options:'),
         '   -d, --decimals=%-6s %s' %
             (_('num'), _('set number of decimals to show')),
         '   -f, --fixed-decimals  %s' %
             _('show set number of decimals, even if zeros'),
         '   -h, --help            %s' %
             _('display this message and exit'),
         '   -i, --interactive     %s' %
             _('interactive command line mode (non-GUI)'),
         '   -q, --quiet           %s' %
             _('convert without further prompts'),
         '   -s, --sci-notation    %s' %
             _('show results in scientific notation'),
         '']

def parseArgs(opts, args):
    """Parse the command line and output conversion results"""
    options = option.Option('convertall', 20)
    options.loadAll(optiondefaults.defaultList)
    quiet = False
    dataTestMode = False
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            printUsage()
            return
        if opt in ('-d', '--decimals'):
            try:
                decimals = int(arg)
                if 0 <= decimals <= unitgroup.UnitGroup.maxDecPlcs:
                    options.changeData('DecimalPlaces', arg, False)
            except ValueError:
                pass
        elif opt in ('-f', '--fixed-decimals'):
            options.changeData('FixedDecimals', 'yes', False)
        elif opt in ('-s', '--sci-notation'):
            options.changeData('SciNotation', 'yes', False)
        elif opt in ('-q', '--quiet'):
            quiet = True
        elif opt in ('-t', '--test'):
            dataTestMode = True
    data = unitdata.UnitData()
    try:
        data.readData()
    except unitdata.UnitDataError, text:
        print u'Error in unit data - %s' % text
        sys.exit(1)
    if dataTestMode:
        unitDataTest(data, options)
        return
    numStr = u'1.0'
    if args:
        numStr = args[0]
        try:
            float(numStr)
            del args[0]
        except (ValueError):
            numStr = u'1.0'
    fromUnit = None
    try:
        fromUnit = getUnit(data, options, args.pop(0))
    except IndexError:
        pass
    if not fromUnit and quiet:
        return
    toUnit = None
    try:
        toUnit = getUnit(data, options, args[0])
    except IndexError:
        pass
    if not toUnit and quiet:
        return
    while True:
        while not fromUnit:
            text = _('Enter from unit -> ')
            fromText = raw_input(text.encode(localEncoding))
            if not fromText:
                return
            fromUnit = getUnit(data, options, fromText)
        while not toUnit:
            text = _('Enter to unit -> ')
            toText = raw_input(text.encode(localEncoding))
            if not toText:
                return
            toUnit = getUnit(data, options, toText)
        if fromUnit.categoryMatch(toUnit):
            badEntry = False
            while True:
                if not badEntry:
                    text = u'%s %s = %s %s' % (numStr, fromUnit.unitString(),
                                             fromUnit.convertStr(float(numStr),
                                                                 toUnit),
                                             toUnit.unitString())
                    print text.encode(localEncoding)
                    if quiet:
                        return
                badEntry = False
                text = _('Enter number, [n]ew, [r]everse or [q]uit -> ')
                rep = raw_input(text.encode(localEncoding))
                if not rep or rep[0] in ('q', 'Q'):
                    return
                if rep[0] in ('r', 'R'):
                    fromUnit, toUnit = toUnit, fromUnit
                elif rep[0] in ('n', 'N'):
                    fromUnit = None
                    toUnit = None
                    numStr = u'1.0'
                    print
                    break
                else:
                    try:
                        float(rep)
                        numStr = rep
                    except ValueError:
                        badEntry = True
        else:
            text = _(u'Units %s and %s are not compatible') % \
                         (fromUnit.unitString(), toUnit.unitString())
            print text.encode(localEncoding)
            if quiet:
                return
            fromUnit = None
            toUnit = None

def getUnit(data, options, text):
    """Create unit from text, check unit is valid,
       return reduced unit or None"""
    unit = unitgroup.UnitGroup(data, options)
    unit.update(text)
    if unit.groupValid():
        unit.reduceGroup()
        return unit
    print (_(u'%s is not a valid unit') % text).encode(localEncoding)
    return None

def printUsage():
    """Print usage text"""
    print ('\n'.join(usage)).encode(localEncoding)

def unitDataTest(data, options):
    """Run through a test of all units for consistent definitions,
       print results, return True if all pass"""
    badUnits = {}
    errorRegEx = re.compile(r'.*"(.*)"$')
    for unit in data.values():
        if not unit.unitValid():
            badUnits.setdefault(unit.name, []).append(unit.name)
        group = unitgroup.UnitGroup(data, options)
        group.replaceCurrent(unit)
        try:
            group.reduceGroup()
        except unitdata.UnitDataError as errorText:
            rootUnitName = errorRegEx.match(unicode(errorText)).group(1)
            badUnits.setdefault(rootUnitName, []).append(unit.name)
    if not badUnits:
        print 'All units pass tests'
        return True
    for key in sorted(badUnits.keys()):
        impacts = ', '.join(sorted(badUnits[key]))
        text = '%s\n   Impacts:  %s\n' % (key, impacts)
        print text.encode(localEncoding)
    return False
