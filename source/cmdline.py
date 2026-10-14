#!/usr/bin/env python3

#****************************************************************************
# cmdline.py, provides a class to read and execute command line arguments
#
# ConvertAll, a units conversion program
# Copyright (C) 2015, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

import sys
import glob
import math
import os.path
import option
import optiondefaults
import unitdata
import unitgroup

usage = [_('Usage:'),
         '',
         '   convertall [{0}]'.format(_('qt-options')),
         '',
         _('-or- (non-GUI):'),
         '   convertall [{0}] [{1}] {2} [{3}]'.format(_('options'),
                                                      _('number'),
                                                      _('from_unit'),
                                                      _('to_unit')),
         '',
         _('-or- (non-GUI):'),
         '   convertall -i [{0}]'.format(_('options')),
         '',
         _('Units with spaces must be "quoted"'),
         '',
         _('Options:'),
         '   -d, --decimals={0:6} {1}'.format(_('num'),
                                          _('set number of decimals to show')),
         '   -f, --fixed-decimals  {0}'.format(
                              _('show set number of decimals, even if zeros')),
         '   -s, --sci-notation    {0}'.format(
                                     _('show results in scientific notation')),
         '   -e, --eng-notation    {0}'.format(
                                    _('show results in engineering notation')),
         '   -h, --help            {0}'.format(
                                           _('display this message and exit')),
         '   -i, --interactive     {0}'.format(
                                 _('interactive command line mode (non-GUI)')),
         '   -q, --quiet           {0}'.format(
                                         _('convert without further prompts')),
         '   -v, --version         show application version and exit',
         '       --runtime-info    show actual Qt6/binding/SIP versions as JSON',
         '   -t, --test            validate the selected unit catalogue',
         '       --test-all        validate every installed unit catalogue',
         '       --gui-smoke-test  open/check/close the GUI (release validation)',
         '',
         'Exit codes: 0=success, 1=conversion/data error, 2=usage error,',
         '            130=interrupted. Use -- before negative numbers.',
         '']

def parseArgs(opts, args):
    """Parse the command line and output conversion results.
    """
    args = list(args)
    if any(opt in ('-v', '--version') for opt, arg in opts):
        from convertall import __progname__, __version__
        print('{0} {1} (Qt6)'.format(__progname__, __version__))
        return 0
    diagnostic = any(opt in ('-h', '--help', '-t', '--test', '--test-all')
                     for opt, arg in opts)
    options = option.Option('' if diagnostic else 'convertall', 20)
    options.loadAll(optiondefaults.defaultList)
    quiet = False
    dataTestMode = False
    testAll = False
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            printUsage()
            return 0
        if opt in ('-d', '--decimals'):
            try:
                decimals = int(arg)
                if not 0 <= decimals <= unitgroup.UnitGroup.maxDecPlcs:
                    raise ValueError
                options.changeData('DecimalPlaces', arg, False)
            except ValueError:
                print('Decimals must be an integer from 0 to {0}'.
                      format(unitgroup.UnitGroup.maxDecPlcs), file=sys.stderr)
                return 2
        elif opt in ('-f', '--fixed-decimals'):
            options.changeData('Notation', 'fixed', False)
        elif opt in ('-s', '--sci-notation'):
            options.changeData('Notation', 'scientific', False)
        elif opt in ('-e', '--eng-notation'):
            options.changeData('Notation', 'engineering', False)
        elif opt in ('-q', '--quiet'):
            quiet = True
        elif opt in ('-t', '--test', '--test-all'):
            dataTestMode = True
            testAll = opt == '--test-all' or testAll
    if len(args) > 3:
        printUsage()
        return 2
    data = unitdata.UnitData()
    try:
        data.readData()
    except unitdata.UnitDataError as text:
        print('Error in unit data - {0}'.format(text))
        return 1
    if dataTestMode:
        if testAll:
            success = True
            for filePath in sorted(glob.glob(os.path.join(
                    os.path.dirname(data.filePath), 'units*.dat'))):
                catalogue = unitdata.UnitData()
                try:
                    catalogue.readData(filePath)
                    print('{0}: {1} units'.format(os.path.basename(filePath),
                                                 len(catalogue)))
                    success = unitDataTest(catalogue, options) and success
                except unitdata.UnitDataError as error:
                    print('{0}: {1}'.format(os.path.basename(filePath), error))
                    success = False
            return 0 if success else 1
        print('{0}: {1} units'.format(os.path.basename(data.filePath), len(data)))
        return 0 if unitDataTest(data, options) else 1
    numStr = '1.0'
    if args:
        numStr = args[0]
        try:
            number = float(numStr)
            if not math.isfinite(number):
                print('Number must be finite', file=sys.stderr)
                return 1
            del args[0]
        except (ValueError):
            numStr = '1.0'
    fromUnit = None
    try:
        fromUnit = getUnit(data, options, args.pop(0))
    except IndexError:
        pass
    if not fromUnit and quiet:
        print('A valid from unit is required', file=sys.stderr)
        return 1
    toUnit = None
    try:
        toUnit = getUnit(data, options, args[0])
    except IndexError:
        pass
    if not toUnit and quiet:
        print('A valid to unit is required', file=sys.stderr)
        return 1
    while True:
        while not fromUnit:
            text = _('Enter from unit -> ')
            fromText = input(text)
            if not fromText:
                return 0
            fromUnit = getUnit(data, options, fromText)
        while not toUnit:
            text = _('Enter to unit -> ')
            toText = input(text)
            if not toText:
                return 0
            toUnit = getUnit(data, options, toText)
        if fromUnit.categoryMatch(toUnit):
            badEntry = False
            while True:
                if not badEntry:
                    result = fromUnit.convert(float(numStr), toUnit)
                    if not math.isfinite(result):
                        print('Conversion result is not finite', file=sys.stderr)
                        return 1
                    newNumStr = fromUnit.formatNumStr(result)
                    print('{0} {1} = {2} {3}'.format(numStr,
                                                     fromUnit.unitString(),
                                                     newNumStr,
                                                     toUnit.unitString()))
                    if quiet:
                        return 0
                badEntry = False
                text = _('Enter number, [n]ew, [r]everse or [q]uit -> ')
                rep = input(text)
                if not rep or rep[0] in ('q', 'Q'):
                    return 0
                if rep[0] in ('r', 'R'):
                    fromUnit, toUnit = toUnit, fromUnit
                elif rep[0] in ('n', 'N'):
                    fromUnit = None
                    toUnit = None
                    numStr = '1.0'
                    print()
                    break
                else:
                    try:
                        if not math.isfinite(float(rep)):
                            raise ValueError
                        numStr = rep
                    except ValueError:
                        badEntry = True
        else:
            print(_('Units {0} and {1} are not compatible').
                  format(fromUnit.unitString(), toUnit.unitString()))
            if quiet:
                return 1
            fromUnit = None
            toUnit = None

def getUnit(data, options, text):
    """Create unit from text, check unit is valid,
       return reduced unit or None.
    """
    unit = unitgroup.UnitGroup(data, options)
    unit.update(text)
    if unit.groupValid():
        unit.reduceGroup()
        return unit
    print(_('{0} is not a valid unit').format(text))
    return None

def printUsage():
    """Print usage text.
    """
    print('\n'.join(usage))

def unitDataTest(data, options):
    """Run through a test of all units for consistent definitions,
       print results, return True if all pass.
    """
    badUnits = {}
    for unit in data.values():
        group = unitgroup.UnitGroup(data, options)
        group.replaceCurrent(unit)
        try:
            if not group.groupValid():
                raise unitdata.UnitDataError('Invalid unit "{0}"'.format(unit.name))
            group.reduceGroup()
            if not group.checkLinear() or not math.isfinite(group.factor) or group.factor <= 0:
                raise unitdata.UnitDataError('Invalid conversion for "{0}"'.format(unit.name))
            # Also exercise the equations; reducing dimensions alone is not
            # sufficient to find a malformed non-linear definition.
            if not math.isfinite(group.convert(1.0, group)):
                raise unitdata.UnitDataError('Non-finite result for "{0}"'.format(unit.name))
        except (unitdata.UnitDataError, ArithmeticError, ValueError) as error:
            badUnits.setdefault(str(error), []).append(unit.name)
    if not badUnits:
        print('All units pass tests')
        return True
    for key in sorted(badUnits):
        impacts = ', '.join(sorted(badUnits[key]))
        print('{0}\n   Impacts:  {1}\n'.format(key, impacts))
    return False
