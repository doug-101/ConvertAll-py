#!/usr/bin/env python3
"""
****************************************************************************
 convertall.py, the main program file

 ConvertAll, a units conversion program
 Copyright (C) 2020, Douglas W. Bell

 This is free software; you can redistribute it and/or modify it under the
 terms of the GNU General Public License, either Version 2 or any later
 version. This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY. See the included LICENSE file for details.
*****************************************************************************
"""

__progname__ = 'ConvertAll'
__version__ = '0.9.3'
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
from PyQt6 import QtCore
from PyQt6.QtCore import (PYQT_VERSION_STR, QCoreApplication, QLibraryInfo,
                         QLocale, QTranslator, qVersion)


def loadTranslator(fileName, app):
    """Load an app catalogue, or the qtbase catalogue from this Qt6 runtime.

    Never load the historical Qt5 qt_*.qm files shipped in old source trees.
    Qt widgets and the application have separate translation catalogues.
    QTranslator.load provides language/region fallback (fr_FR -> fr).
    """
    translator = QTranslator(app)
    if fileName.startswith(('qt_', 'qtbase_')):
        language = fileName.split('_', 1)[1]
        result = translator.load('qtbase_' + language,
                                 QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    else:
        modPath = os.path.abspath(sys.path[0])
        if modPath.endswith('.zip'):
            modPath = os.path.dirname(modPath)
        paths = [os.path.join(modPath, translationPath),
                 os.path.join(modPath, '..', translationPath),
                 os.path.join(modPath, '..', 'i18n', translationPath)]
        result = any(translator.load(fileName, path) for path in paths)
    if result:
        QCoreApplication.installTranslator(translator)
        return True
    translator.deleteLater()
    print('Warning: translation file "{0}" could not be loaded'.format(fileName))
    return False


def setupTranslator(app):
    """Select language and install the context-preserving translation helper."""
    try:
        locale.setlocale(locale.LC_ALL, '')
    except locale.Error:
        pass
    global lang
    lang = os.environ.get('LC_MESSAGES', '') or os.environ.get('LANG', '')
    if not lang:
        lang = QLocale.system().name()
    lang = lang.split('.', 1)[0].split('@', 1)[0].replace('-', '_')
    numTranslators = 0
    if lang and lang not in ('C', 'POSIX') and lang[:2] != 'en':
        numTranslators += loadTranslator('qt_{0}'.format(lang), app)
        numTranslators += loadTranslator('convertall_{0}'.format(lang), app)

    def translate(text, comment=''):
        # Existing TS/QM files use the module filename as context.
        frame = sys._getframe(1)
        try:
            context = os.path.basename(os.path.splitext(frame.f_code.co_filename)[0])
        finally:
            del frame
        return QCoreApplication.translate(context, text, comment)

    def markNoTranslate(text, comment=''):
        return text

    builtins._ = translate if numTranslators else markNoTranslate


def runtimeInfo():
    """Report loaded Qt versions and distinguish SIP package/tool versions.

    sip.SIP_VERSION_STR describes the SIP generator, not the PyQt6-sip
    distribution version. Frozen builds must include its package metadata;
    missing metadata is an error, never replaced by an assumed pin.
    """
    from importlib.metadata import version
    from PyQt6 import sip
    return {'application': __progname__, 'version': __version__,
            'binding': 'PyQt6', 'pyqt_binding': PYQT_VERSION_STR,
            'qt_runtime': qVersion(), 'sip_package': version('PyQt6-sip'),
            'sip_generator': sip.SIP_VERSION_STR,
            'python_executable': sys.executable,
            'python_version': '.'.join(map(str, sys.version_info[:3])),
            'pyqt_location': QtCore.__file__,
            'frozen': bool(getattr(sys, 'frozen', False)),
            'qt_translations_path': QLibraryInfo.path(
                QLibraryInfo.LibraryPath.TranslationsPath)}


def main():
    guiSmokeTest = '--gui-smoke-test' in sys.argv[1:]
    if len(sys.argv) > 1:
        try:
            opts, args = getopt.gnu_getopt(sys.argv[1:], 'd:fhiqsetv',
                                           ['decimals=', 'fixed-decimals',
                                            'help', 'interactive', 'quiet',
                                            'sci-notation', 'eng-notation',
                                            'test', 'test-all', 'version', 'runtime-info',
                                            'gui-smoke-test'])
        except getopt.GetoptError:
            # Only recognised Qt options may enter the GUI path. Unknown CLI
            # options must not open a window or import QtWidgets/QtGui.
            qtOptions = {'display', 'font', 'fn', 'geometry', 'name', 'nograb',
                         'dograb', 'reverse', 'session', 'style', 'stylesheet',
                         'sync', 'title', 'visual', 'widgetcount', 'platform',
                         'platformpluginpath', 'platformtheme', 'plugin',
                         'qmljsdebugger', 'qwindowgeometry', 'qwindowicon',
                         'qwindowtitle', 'testability', 'iconic'}
            if sys.argv[1].lstrip('-').split('=', 1)[0] not in qtOptions:
                app = QCoreApplication(sys.argv)
                setupTranslator(app)
                import cmdline
                cmdline.printUsage()
                return 2
        else:
            if any(opt == '--runtime-info' for opt, value in opts):
                if args or len(opts) != 1:
                    print('--runtime-info does not accept other arguments', file=sys.stderr)
                    return 2
                app = QCoreApplication(sys.argv)
                import json
                from importlib.metadata import PackageNotFoundError
                try:
                    info = runtimeInfo()
                except PackageNotFoundError as error:
                    print('Runtime information unavailable: {0}'.format(error), file=sys.stderr)
                    return 1
                print(json.dumps(info, ensure_ascii=False))
                return 0
            if any(opt == '--gui-smoke-test' for opt, value in opts):
                if args or len(opts) != 1:
                    print('--gui-smoke-test does not accept conversion arguments', file=sys.stderr)
                    return 2
                guiSmokeTest = True
            else:
                app = QCoreApplication(sys.argv)
                setupTranslator(app)
                import cmdline
                import unitdata
                unitdata.lang = lang
                unitdata.dataFilePath = dataFilePath
                try:
                    return cmdline.parseArgs(opts, args)
                except EOFError:
                    return 0
                except KeyboardInterrupt:
                    return 130
                except (unitdata.UnitDataError, ArithmeticError, ValueError) as error:
                    print('Error - {0}'.format(error), file=sys.stderr)
                    return 1
    from PyQt6.QtWidgets import QApplication
    userStyle = any(arg.split('=', 1)[0] in ('-style', '--style') for arg in sys.argv)
    # Qt6 already enables HiDPI with PassThrough rounding. Do not restore the
    # removed Qt5 AA_EnableHighDpiScaling/AA_UseHighDpiPixmaps switches.
    app = QApplication(sys.argv)
    setupTranslator(app)
    import convertdlg
    unitdata = sys.modules['unitdata']
    unitdata.lang = lang
    unitdata.dataFilePath = dataFilePath
    if not userStyle:
        QApplication.setStyle('fusion')
    win = convertdlg.ConvertDlg(showStartupTip=not guiSmokeTest)
    win.show()
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    if guiSmokeTest:
        from PyQt6.QtCore import QTimer
        def checkWindow():
            try:
                if not win.isVisible() or win.unitListView.topLevelItemCount() < 1:
                    raise RuntimeError('Unit list was not displayed')
                win.fromGroup.update('in')
                win.toGroup.update('cm')
                win.fromNumEdit.unitUpdate()
                win.toNumEdit.unitUpdate()
                if abs(float(win.toNumEdit.text()) - 2.54) > 1e-9:
                    raise RuntimeError('GUI conversion failed')
                if win.icons['convertall_med'].isNull() or not win.findHelpFile():
                    raise RuntimeError('GUI resources missing')
                print('GUI smoke test passed (Qt6)')
                result = 0
            except Exception as error:
                print('GUI smoke test failed: {0}'.format(error), file=sys.stderr)
                result = 1
            win.close()
            app.exit(result)
        QTimer.singleShot(0, checkWindow)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
