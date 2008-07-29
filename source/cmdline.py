#!/usr/bin/env python

#****************************************************************************
# cmdline.py, provides a class to read and execute command line arguments
#
# ConvertAll, a units conversion program
# Copyright (C) 2006, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

import sys
import option
import optiondefaults
import unitdata
import unitgroup

usage = ['',
         'usage:  convertall [<qt-options>]',
         '   or:  convertall [<options>] [<number>] <from_unit> <to_unit>',
         '   or:  convertall -i [<options>]',
         '',
         'units with spaces must be "quoted"',
         '',
         'options:',
         '   -d, --decimals=<num>  set number of decimals to show',
         '   -f, --fixed-decimals  show set number of decimals, even if zeros',
         '   -h, --help            display this message and exit',
         '   -i, --interactive     interactive command line mode (non-GUI)',
         '   -q, --quiet           convert without further prompts',
         '   -s, --sci-notation    show results in scientific notation',
         '']

availOptions = 'd:fhiqs'
availLongOptions = ['decimals=', 'fixed-decimals', 'help', 'interactive',
                    'quiet', 'sci-notation']

def parseArgs(opts, args):
    """Parse the command line and output conversion results"""
    options = option.Option('convertall', 20)
    options.loadAll(optiondefaults.defaultList)
    quiet = False
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
    data = unitdata.UnitData()
    try:
        data.readData()
    except unitdata.UnitDataError, text:
        print 'Error in unit data - %s' % text
        sys.exit(1)
    numStr = '1.0'
    if args:
        numStr = args[0]
        try:
            float(numStr)
            del args[0]
        except (ValueError):
            numStr = '1.0'
    fromUnit = None
    if args:
        fromUnit = getUnit(data, options, args.pop(0))
    toUnit = None
    if args:
        toUnit = getUnit(data, options, args[0])
    while True:
        while not fromUnit:
            fromText = raw_input('Enter from unit -> ')
            if not fromText:
                return
            fromUnit = getUnit(data, options, fromText)
        while not toUnit:
            toText = raw_input('Enter to unit -> ')
            if not toText:
                return
            toUnit = getUnit(data, options, toText)
        if fromUnit.categoryMatch(toUnit):
            badEntry = False
            while True:
                if not badEntry:
                    print '%s %s = %s %s' % (numStr, fromUnit.unitString(),
                                             fromUnit.convertStr(float(numStr),
                                                                 toUnit),
                                             toUnit.unitString())
                    if quiet:
                        return
                badEntry = False
                rep = raw_input('Enter number, [n]ew, [r]everse or [q]uit -> ')
                if not rep or rep[0] in ('q', 'Q'):
                    return
                if rep[0] in ('r', 'R'):
                    fromUnit, toUnit = toUnit, fromUnit
                elif rep[0] in ('n', 'N'):
                    fromUnit = None
                    toUnit = None
                    numStr = '1.0'
                    print
                    break
                else:
                    try:
                        float(rep)
                        numStr = rep
                    except ValueError:
                        badEntry = True
        else:
            print 'Units %s and %s are not compatible' % \
                         (fromUnit.unitString(), toUnit.unitString())
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
    print '%s is not a valid unit' % text
    return None

def printUsage():
    """Print usage text"""
    print '\n'.join(usage)
