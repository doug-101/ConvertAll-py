#!/usr/bin/env python

#****************************************************************************
# recentunits.py, provides a list of recently used units
#
# ConvertAll, a units conversion program
# Copyright (C) 2010, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************


class RecentUnits(list):
    """A list of recent unit combo names"""
    def __init__(self, options):
        list.__init__(self)
        self.options = options
        self.numEntries = options.intData('RecentUnits', 0, 99)
        self.loadList()

    def loadList(self):
        """Load recent units from option file"""
        self[:] = []
        for num in range(self.numEntries):
            name = self.options.strData(self.optionTitle(num), True)
            if name:
                self.append(name)

    def writeList(self):
        """Write list of paths to options"""
        for num in range(self.numEntries):
            try:
                name = self[num]
            except IndexError:
                name = ''
            self.options.changeData(self.optionTitle(num), name, True)
        self.options.writeChanges()

    def addEntry(self, name):
        """Move name to start if found, otherwise add it"""
        try:
            self.remove(name)
        except ValueError:
            pass
        self.insert(0, name)
        del self[self.numEntries:]

    def optionTitle(self, num):
        """Return option key for the given nummber"""
        return 'RecentUnit%d' % (num + 1)
