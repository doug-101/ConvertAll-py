#!/usr/bin/env python3

#****************************************************************************
# setup.py, provides a distutils script for use with cx_Freeze
#
# Creates a standalone windows executable
#
# Run the build process by running the command 'python setup.py build'
#
# If everything works well you should find a subdirectory in the build
# subdirectory that contains the files needed to run the application
#
# ConvertAll, a units conversion program
# Copyright (C) 2017, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
#*****************************************************************************

import sys
from cx_Freeze import setup, Executable
from convertall import __version__

base = None
if sys.platform == 'win32':
    base = 'Win32GUI'

extraFiles =  [('../data', 'data'), ('../doc', 'doc'), ('../icons', 'icons'),
               ('../source', 'source'), ('../translations', 'translations'),
               ('../win', '.')]

setup(name = 'convertall',
      version = __version__,
      description = 'ConvertAll, a units conversion program',
      options = {'build_exe': {'includes': 'atexit',
                               'include_files': extraFiles,
                               'excludes': ['*.pyc'],
                               'zip_include_packages': ['*'],
                               'zip_exclude_packages': [],
                               'include_msvcr': True,
                               'build_exe': '../../convertall-0.7'}},
      executables = [Executable('convertall.py', base=base,
                                icon='../win/convertall.ico')])
