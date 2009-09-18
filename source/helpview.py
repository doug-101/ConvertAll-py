#!/usr/bin/env python

#****************************************************************************
# helpview.py, provides a window for viewing an html help file
#
# Copyright (C) 2006, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

import os.path
import sys
import webbrowser
from PyQt4 import QtCore, QtGui


class HelpView(QtGui.QMainWindow):
    """Main window for viewing an html help file"""
    def __init__(self, path, caption, icons, parent=None):
        """Helpview initialize with text"""
        QtGui.QMainWindow.__init__(self, parent)
        self.setAttribute(QtCore.Qt.WA_QuitOnClose, False)
        self.setWindowFlags(QtCore.Qt.Window)
        self.setStatusBar(QtGui.QStatusBar())
        self.textView = HelpViewer(self)
        self.setCentralWidget(self.textView)
        path = os.path.abspath(path)
        if sys.platform.startswith('win'):
            path = path.replace('\\', '/')
        self.textView.setSearchPaths([os.path.dirname(path)])
        self.textView.setSource(QtCore.QUrl('file:///%s' % path))
        self.resize(520, 440)
        self.setWindowTitle(caption)
        tools = self.addToolBar('Tools')
        self.menu = QtGui.QMenu(self.textView)
        self.connect(self.textView,
                     QtCore.SIGNAL('highlighted(const QString&)'),
                     self.showLink)

        backAct = QtGui.QAction(_('&Back'), self)
        backAct.setIcon(icons['helpback'])
        tools.addAction(backAct)
        self.menu.addAction(backAct)
        self.connect(backAct, QtCore.SIGNAL('triggered()'),
                     self.textView, QtCore.SLOT('backward()'))
        backAct.setEnabled(False)
        self.connect(self.textView, QtCore.SIGNAL('backwardAvailable(bool)'),
                     backAct, QtCore.SLOT('setEnabled(bool)'))

        forwardAct = QtGui.QAction(_('&Forward'), self)
        forwardAct.setIcon(icons['helpforward'])
        tools.addAction(forwardAct)
        self.menu.addAction(forwardAct)
        self.connect(forwardAct, QtCore.SIGNAL('triggered()'),
                     self.textView, QtCore.SLOT('forward()'))
        forwardAct.setEnabled(False)
        self.connect(self.textView, QtCore.SIGNAL('forwardAvailable(bool)'),
                     forwardAct, QtCore.SLOT('setEnabled(bool)'))

        homeAct = QtGui.QAction(_('&Home'), self)
        homeAct.setIcon(icons['helphome'])
        tools.addAction(homeAct)
        self.menu.addAction(homeAct)
        self.connect(homeAct, QtCore.SIGNAL('triggered()'),
                     self.textView, QtCore.SLOT('home()'))

    def showLink(self, text):
        """Send link text to the statusbar"""
        self.statusBar().showMessage(unicode(text))


class HelpViewer(QtGui.QTextBrowser):
    """Shows an html help file"""
    def __init__(self, parent=None):
        QtGui.QTextBrowser.__init__(self, parent)

    def setSource(self, url):
        """Called when user clicks on a URL"""
        name = unicode(url.toString())
        if name.startswith(u'http'):
            webbrowser.open(name, True)
        else:
            QtGui.QTextBrowser.setSource(self, QtCore.QUrl(name))

    def contextMenuEvent(self, event):
        """Init popup menu on right click"""""
        self.parentWidget().menu.exec_(event.globalPos())
