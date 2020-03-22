# -*- mode: python -*-

#******************************************************************************
# convertall.spec, provides settings for use with PyInstaller
#
# Creates a standalone windows executable
#
# Run the build process by running the command 'pyinstaller convertall.spec'
#
# If everything works well you should find a 'dist/convertall' subdirectory
# that contains the files needed to run the application
#
# ConvertAll, an information storage program
# Copyright (C) 2019, Douglas W. Bell
#
# This is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License, either Version 2 or any later
# version.  This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY.  See the included LICENSE file for details.
#******************************************************************************

block_cipher = None

extraFiles = [('../data', 'data'),
              ('../doc', 'doc'),
              ('../icons', 'icons'),
              ('../source/*.py', 'source'),
              ('../source/*.pro', 'source'),
              ('../source/*.spec', 'source'),
              ('../translations', 'translations'),
              ('../win/*.*', '.')]

a = Analysis(['convertall.py'],
             pathex=['C:\\git\\convertall\\devel\\source'],
             binaries=[],
             datas=extraFiles,
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='convertall',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=False,
          icon='..\\win\\convertall.ico')
a.binaries = a.binaries - TOC([('d3dcompiler_47.dll', None, None),
                               ('libcrypto-1_1.dll', None, None),
                               ('libeay32.dll', None, None),
                               ('libglesv2.dll', None, None),
                               ('libssl-1_1.dll', None, None),
                               ('opengl32sw.dll', None, None),
                               ('qt5dbus.dll', None, None),
                               ('qt5network.dll', None, None),
                               ('qt5qml.dll', None, None),
                               ('qt5qmlmodels.dll', None, None),
                               ('qt5quick.dll', None, None),
                               ('qt5websockets.dll', None, None)])
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               name='convertall')
