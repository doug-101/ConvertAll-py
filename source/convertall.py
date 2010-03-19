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
__version__ = '0.4.90'
__author__ = 'Doug Bell'

dataFilePath = None    # modified by install script if required
helpFilePath = None    # modified by install script if required
iconPath = None        # modified by install script if required
translationPath = 'translations'
lang = ''

import sys
import os.path
import locale
import getopt
import signal
import __builtin__
from PyQt4 import QtCore, QtGui

def loadTranslator(fileName, app):
    """Load and install qt translator, return True if sucessful"""
    translator = QtCore.QTranslator(app)
    modPath = unicode(os.path.abspath(sys.path[0]),
                      sys.getfilesystemencoding())
    if modPath.endswith('.zip'):  # for py2exe
        modPath = os.path.dirname(modPath)
    path = os.path.join(modPath, translationPath)
    result = translator.load(fileName, path)
    if not result:
        path = os.path.join(modPath, '..', translationPath)
        result = translator.load(fileName, path)
    if not result:
        path = os.path.join(modPath, '..', 'i18n', translationPath)
        result = translator.load(fileName, path)
    if result:
        QtCore.QCoreApplication.installTranslator(translator)
        return True
    else:
        print 'Warning: translation file "%s" could not be loaded' % fileName
        return False

def setupTranslator(app):
    """Set language, load translators and setup translator function"""
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        pass
    global lang
    lang = os.environ.get('LC_MESSAGES', '')
    if not lang:
        lang = os.environ.get('LANG', '')
        if not lang:
            try:
                lang = locale.getdefaultlocale()[0]
            except ValueError:
                pass
            if not lang:
                lang = ''
    numTranslators = 0
    if lang and lang[:2] not in ['C', 'en']:
        numTranslators += loadTranslator('qt_%s' % lang, app)
        numTranslators += loadTranslator('convertall_%s' % lang, app)

    def translate(text, comment=''):
        """Translation function that sets context to calling module's
           filename"""
        try:
            frame = sys._getframe(1)
            fileName = frame.f_code.co_filename
        finally:
            del frame
        context = os.path.basename(os.path.splitext(fileName)[0])
        return unicode(QtCore.QCoreApplication.translate(context, text,
                                                         comment))

    def markNoTranslate(text, comment=''):
        return text

    if numTranslators:
        __builtin__._ = translate
    else:
        __builtin__._ = markNoTranslate


if __name__ == '__main__':
    userStyle = '-style' in ' '.join(sys.argv)
    app = QtGui.QApplication(sys.argv)
    setupTranslator(app)  # must be before importing any convertall modules
    if len(sys.argv) > 1:
        import cmdline
        try:
            opts, args = getopt.gnu_getopt(sys.argv, cmdline.availOptions,
                                           cmdline.availLongOptions)
        except getopt.GetoptError:
            cmdline.printUsage()
            sys.exit(2)
        try:
            cmdline.parseArgs(opts, args[1:])
        except KeyboardInterrupt:
            pass
    else:
        import convertdlg
        if not userStyle and not sys.platform.startswith('win'):
            QtGui.QApplication.setStyle('plastique')
        win = convertdlg.ConvertDlg()
        win.show()
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        app.exec_()
