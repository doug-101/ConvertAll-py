#!/usr/bin/env python3
"""
****************************************************************************
 convertall.py, the main program file

 ConvertAll, a units conversion program
 Copyright (C) 2017, Douglas W. Bell

 This is free software; you can redistribute it and/or modify it under the
 terms of the GNU General Public License, either Version 2 or any later
 version.  This program is distributed in the hope that it will be useful,
 but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
*****************************************************************************
"""

__progname__ = 'ConvertAll'
__version__ = '0.7.2'
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
import builtins
from PyQt5.QtCore import (QCoreApplication, QTranslator)
from PyQt5.QtWidgets import QApplication

def loadTranslator(fileName, app):
    """Load and install qt translator, return True if sucessful.
    """
    translator = QTranslator(app)
    modPath = os.path.abspath(sys.path[0])
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
        QCoreApplication.installTranslator(translator)
        return True
    else:
        print('Warning: translation file "{0}" could not be loaded'.
              format(fileName))
        return False

def setupTranslator(app):
    """Set language, load translators and setup translator function.
    """
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
        numTranslators += loadTranslator('qt_{0}'.format(lang), app)
        numTranslators += loadTranslator('convertall_{0}'.format(lang), app)

    def translate(text, comment=''):
        """Translation function that sets context to calling module's
           filename.
        """
        try:
            frame = sys._getframe(1)
            fileName = frame.f_code.co_filename
        finally:
            del frame
        context = os.path.basename(os.path.splitext(fileName)[0])
        return QCoreApplication.translate(context, text, comment)

    def markNoTranslate(text, comment=''):
        return text

    if numTranslators:
        builtins._ = translate
    else:
        builtins._ = markNoTranslate


def main():
    if len(sys.argv) > 1:
        try:
            opts, args = getopt.gnu_getopt(sys.argv, 'd:fhiqset',
                                           ['decimals=', 'fixed-decimals',
                                            'help', 'interactive', 'quiet',
                                            'sci-notation', 'eng-notation',
                                            'test'])
        except getopt.GetoptError:
            # check that arguments aren't Qt GUI options
            if sys.argv[1][:3] not in ['-ba', '-bg', '-bt', '-bu', '-cm',
                                       '-di', '-do', '-fg', '-fn', '-fo',
                                       '-ge', '-gr', '-im', '-in', '-na',
                                       '-nc', '-no', '-re', '-se', '-st',
                                       '-sy', '-ti', '-vi', '-wi']:
                app = QCoreApplication(sys.argv)
                setupTranslator(app)
                import cmdline
                cmdline.printUsage()
                sys.exit(2)
        else:
            app = QCoreApplication(sys.argv)
            setupTranslator(app)
            import cmdline
            try:
                cmdline.parseArgs(opts, args[1:])
            except KeyboardInterrupt:
                pass
            return
    userStyle = '-style' in ' '.join(sys.argv)
    app = QApplication(sys.argv)
    setupTranslator(app)  # must be before importing any convertall modules
    import convertdlg
    if not userStyle and not sys.platform.startswith('win'):
        QApplication.setStyle('plastique')
    win = convertdlg.ConvertDlg()
    win.show()
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    app.exec_()


if __name__ == '__main__':
    main()
