#!/usr/bin/env python
from distutils.core import setup
import py2exe

guiProg = {'script': 'convertall.py',
           'icon_resources': [(1, '../win/convertall.ico')],
           'dest_base': 'convertall'}

consoleProg = {'script': 'convertall.py',
               'icon_resources': [(1, '../win/convertall.ico')],
               'dest_base': 'convertall_dos'}

options = {'py2exe': {'includes': ['sip'],
                      'dist_dir': 'dist/lib'}}

setup(windows=[guiProg], console=[consoleProg], options=options)

# run with: python setup.py py2exe
