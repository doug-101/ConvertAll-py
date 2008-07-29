#!/usr/bin/env python
"""
****************************************************************************
 convertall.py, the main program file

 ConvertAll, a units conversion program
 Copyright (C) 2008, Douglas W. Bell

 This is free software; you can redistribute it and/or modify it under the
 terms of the GNU General Public License, either Version 2 or any later
 version.  This program is distributed in the hope that it will be useful,
 but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
*****************************************************************************
"""

__progname__ = 'ConvertAll'
__version__ = '0.4.2'
__author__ = 'Doug Bell'

dataFilePath = None    # modified by install script if required
helpFilePath = None    # modified by install script if required
iconPath = None        # modified by install script if required

import sys

def hasCmdLineArgs():
    """Return True if command line should be used"""
    if len(sys.argv) <= 1:
        return False
    qtOpts = ['-style', '-stylesheet', '-session', '-widgetcount', '-reverse',
              '-direct3d', '-display', '-geometry', '-fn', '-font', '-bg',
              '-background', '-fg', '-foreground', '-btn', '-button', '-name',
              '-title', '-visual', '-ncols', '-cmap', '-im', '-noxim',
              '-inputstyle']
    for arg in sys.argv[1:]:
        for opt in qtOpts:
            if arg.startswith(opt):
                return False
    return True


if __name__ == '__main__':
    if hasCmdLineArgs():
        import getopt
        import cmdline
        try:
            opts, args = getopt.gnu_getopt(sys.argv, cmdline.availOptions,
                                           cmdline.availLongOptions)
        except getopt.GetoptError:
            cmdline.printUsage()
            sys.exit(2)
        cmdline.parseArgs(opts, args[1:])
    else:
        import signal
        from PyQt4 import QtGui
        import convertdlg
        userStyle = '-style' in ' '.join(sys.argv)
        app = QtGui.QApplication(sys.argv)
        if not userStyle and not sys.platform.startswith('win'):
            QtGui.QApplication.setStyle('plastique')
        win = convertdlg.ConvertDlg()
        win.show()
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        app.exec_()
