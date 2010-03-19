#!/usr/bin/env python

"""
****************************************************************************
 install.py, Linux install script for ConvertAll

 Copyright (C) 2005, Douglas W. Bell

 This is free software; you can redistribute it and/or modify it under the
 terms of the GNU General Public License, either Version 2 or any later
 version.  This program is distributed in the hope that it will be useful,
 but WITTHOUT ANY WARRANTY.  See the included LICENSE file for details.
*****************************************************************************
"""

import sys
import os.path
import getopt
import shutil
import compileall
import py_compile
import glob
import re

prefixDir = '/usr/local'
buildRoot = '/'
progName = 'convertall'
docDir = 'share/doc/%s' % progName
templateDir = 'share/%s/templates' % progName
iconDir = 'share/icons/%s' % progName
testXML = 0
testSpell = 0

def usage(exitCode=2):
    """Display usage info and exit"""
    global prefixDir
    global buildRoot
    print 'Usage:'
    print '    python install.py [-h] [-p dir] [-d dir] [-t dir] [-i dir] '\
          '[-b dir] [-x]'
    print 'where:'
    print '    -h         display this help message'
    print '    -p dir     install prefix [default: %s]' % prefixDir
    print '    -d dir     documentaion dir [default: <prefix>/%s]' % docDir
    print '    -i dir     icon dir [default: <prefix>/%s]' % iconDir
    print '    -b dir     temporary build root for packagers [default: %s]' \
          % buildRoot
    print '    -x         skip all dependency checks (risky)'
    sys.exit(exitCode)


def cmpVersions(versionStr, reqdTuple):
    """Return 1 if point-sep values in versionStr are >= reqdTuple"""
    match = re.search(r'[0-9\.]+', versionStr)
    if not match:
        return 0
    versionStr = match.group()
    versionList = [int(val) for val in versionStr.split('.') if val]
    reqdList = list(reqdTuple)
    while len(versionList) < len(reqdList):
        versionList.append(0)
    while len(reqdList) < len(versionList):
        reqdList.append(0)
    if cmp(versionList, reqdList) != -1:
        return 1
    return 0

def copyDir(srcDir, dstDir):
    """Copy all regular files from srcDir to dstDir,
       dstDir is created if necessary"""
    try:
        if not os.path.isdir(dstDir):
            os.makedirs(dstDir)
        names = os.listdir(srcDir)
        for name in names:
            srcPath = os.path.join(srcDir, name)
            if os.path.isfile(srcPath):
                shutil.copy2(srcPath, os.path.join(dstDir, name))
    except (IOError, OSError), e:
        if str(e).find('Permission denied') >= 0:
            print 'Error - must be root to install files'
            cleanSource()
            sys.exit(4)
        raise

def createWrapper(execDir, execName):
    """Create a wrapper executable file for a python script in execDir
       named execName"""
    text = '#!/bin/sh\n\nexec %s %s/%s.py "$@"' % (sys.executable, execDir,
                                                   execName)
    f = open(execName, 'w')
    f.write(text)
    f.close()
    os.chmod(execName, 0755)

def replaceLine(path, origLineStart, newLine):
    """Searches for origLineStart in file named path, 
       replaces all ocurrances with newLine and re-writes file"""
    f = open(path, 'r')
    lines = f.readlines()
    f.close()
    f = open(path, 'w')
    for line in lines:
        if line.startswith(origLineStart):
            f.write(newLine)
        else:
            f.write(line)
    f.close()

def spellCheck(cmdList):
    """Try spell checkers from list, print result"""
    for cmd in cmdList:
        try:
            stdIn, stdOut, stdErr = os.popen3(cmd)
            stdOut.readline()    # read header
            stdIn.write('!\n')   # set terse mode
            stdIn.flush()
            stdIn.close()
            stdOut.close()
            print '  Spell Checker %s -> OK' % cmd.split()[0]
            return
        except:
            pass
    print '  Spell Checker not found -> install aspell or ispell'
    print '                             if spell checking is desired'

def cleanSource():
    """Remove any temporary files added to untarred dirs"""
    for name in glob.glob(os.path.join('source', '*.py[co]')):
        os.remove(name)
    global progName
    if os.path.isfile(progName):
        os.remove(progName)

def removeDir(dir):
    """Remove dir and all files at path, ignore errors"""
    try:
        shutil.rmtree(dir, 1)
    except:    # shouldn't be needed with ignore error param, but
        pass   # some python versions have a bug

def main():
    optLetters = 'hp:d:t:i:b:x'
    try:
        opts, args = getopt.getopt(sys.argv[1:], optLetters)
    except getopt.GetoptError:
        usage(2)
    global prefixDir
    global docDir
    global templateDir
    global iconDir
    global buildRoot
    global progName
    depCheck = 1
    for opt, val in opts:
        if opt == '-h':
            usage(0)
        elif opt == '-p':
            prefixDir = os.path.abspath(val)
        elif opt == '-d':
            docDir = val
        elif opt == '-t':
            templateDir = val
        elif opt == '-i':
            iconDir = val
        elif opt == '-b':
            buildRoot = val
        elif opt == '-x':
            depCheck = 0
    if not os.path.isfile('install.py'):
        print 'Error - %s files not found' % progName
        print 'The directory containing "install.py" must be current'
        sys.exit(4)
    if os.path.isdir('source') and \
           not os.path.isfile('source/%s.py' % progName):
        print 'Error - source files not found'
        print 'Retry the extraction from the tar archive'
        sys.exit(4)
    if depCheck:
        print 'Checking dependencies...'
        try:
            pyVersion = sys.version_info[:3]
        except AttributeError:
            print '  Python Version 1.x -> Sorry, 2.3 or higher is required'
            sys.exit(3)
        pyVersion = '.'.join([str(num) for num in pyVersion])
        if cmpVersions(pyVersion, (2, 3)):
            print '  Python Version %s -> OK' % pyVersion
        else:
            print '  Python Version %s -> Sorry, 2.3 or higher is required' \
                  % pyVersion
            sys.exit(3)
        try:
            from PyQt4 import QtCore, QtGui
        except:
            print '  Sorry, Qt Version 4.1 or higher and '\
                  'PyQt Version 4.0 or higher are required'
            sys.exit(3)
        qtVersion = QtCore.qVersion()
        if cmpVersions(qtVersion, (4, 1)):
            print '  Qt Version %s -> OK' % qtVersion
        else:
            print '  Qt Version %s -> Sorry, 4.1 or higher is required' \
                  % qtVersion
            sys.exit(3)
        pyqtVersion = QtCore.PYQT_VERSION_STR
        if cmpVersions(pyqtVersion, (2, 4)):
            print '  PyQt Version %s -> OK' % pyqtVersion
        else:
            print '  PyQt Version %s -> Sorry, 4.0 or higher is required' \
                  % pyqtVersion
            sys.exit(3)
        global testXML
        if testXML:
            try:
                import xml.sax
                handler = xml.sax.ContentHandler()
                xml.sax.parseString('<XML>test</XML>', handler)
            except:
                print '  XML Parser -> Sorry, the expat library or '\
                      'PyXML package is required'
                sys.exit(3)
            print '  XML Parser -> OK'
        global testSpell
        if testSpell:
            spellCheck(['aspell -a', 'ispell -a'])

    pythonPrefixDir = os.path.join(prefixDir, 'lib', progName)
    pythonBuildDir = os.path.join(buildRoot, pythonPrefixDir[1:])

    if os.path.isdir('source'):
        compileall.compile_dir('source', ddir=os.path.join(prefixDir, 'source'))
        print 'Installing files...'
        print '  Copying python files to %s' % pythonBuildDir
        removeDir(pythonBuildDir)         # remove old?
        copyDir('source', pythonBuildDir)
    if os.path.isdir('source/plugins'):
        pluginBuildDir = os.path.join(pythonBuildDir, 'plugins')
        print '  Creating plugins directory if necessary'
        copyDir('source/plugins', pluginBuildDir)
    if os.path.isdir('translations'):
        translationDir = os.path.join(pythonBuildDir, 'translations')
        print '  Copying translation files to %s' % translationDir
        copyDir('translations', translationDir)
    if os.path.isdir('doc'):
        docPrefixDir = docDir.replace('<prefix>/', '')
        if not os.path.isabs(docPrefixDir):
            docPrefixDir = os.path.join(prefixDir, docPrefixDir)
        docBuildDir = os.path.join(buildRoot, docPrefixDir[1:])
        print '  Copying documentation files to %s' % docBuildDir
        copyDir('doc', docBuildDir)
        # update help file location in main python script
        replaceLine(os.path.join(pythonBuildDir, '%s.py' % progName),
                    'helpFilePath = None',
                    'helpFilePath = \'%s\'   # modified by install script\n'
                    % docPrefixDir)
    if os.path.isdir('templates'):
        templatePrefixDir = templateDir.replace('<prefix>/', '')
        if not os.path.isabs(templatePrefixDir):
            templatePrefixDir = os.path.join(prefixDir, templatePrefixDir)
        templateBuildDir = os.path.join(buildRoot, templatePrefixDir[1:])
        print '  Copying template files to %s' % templateBuildDir
        copyDir('templates', templateBuildDir)
        # update help file location in main python script
        replaceLine(os.path.join(pythonBuildDir, '%s.py' % progName),
                    'templatePath = None',
                    'templatePath = \'%s\'   # modified by install script\n'
                    % templatePrefixDir)
    if os.path.isdir('data'):
        dataPrefixDir = os.path.join(prefixDir, 'share', progName)
        dataBuildDir = os.path.join(buildRoot, dataPrefixDir[1:])
        print '  Copying data files to %s' % dataBuildDir
        copyDir('data', dataBuildDir)
        # update data file location in main python script
        replaceLine(os.path.join(pythonBuildDir, '%s.py' % progName),
                    'dataFilePath = None',
                    'dataFilePath =  \'%s\'   # modified by install script\n'
                    % dataPrefixDir)
    if os.path.isdir('icons'):
        iconPrefixDir = iconDir.replace('<prefix>/', '')
        if not os.path.isabs(iconPrefixDir):
            iconPrefixDir = os.path.join(prefixDir, iconPrefixDir)
        iconBuildDir = os.path.join(buildRoot, iconPrefixDir[1:])
        print '  Copying icon files to %s' % iconBuildDir
        copyDir('icons', iconBuildDir)
        # update icon location in main python script
        replaceLine(os.path.join(pythonBuildDir, '%s.py' % progName),
                    'iconPath = None',
                    'iconPath =  \'%s\'   # modified by install script\n'
                    % iconPrefixDir)
        if os.path.isdir('icons/toolbar'):
            iconToolBuildDir = os.path.join(iconBuildDir, 'toolbar')
            copyDir('icons/toolbar', iconToolBuildDir)
            if os.path.isdir('icons/toolbar/16x16'):
                copyDir('icons/toolbar/16x16',
                        os.path.join(iconToolBuildDir, '16x16'))
            if os.path.isdir('icons/toolbar/32x32'):
                copyDir('icons/toolbar/32x32', 
                        os.path.join(iconToolBuildDir, '32x32'))
        if os.path.isdir('icons/tree'):
            copyDir('icons/tree', os.path.join(iconBuildDir, 'tree'))

    if os.path.isdir('source'):
        createWrapper(pythonPrefixDir, progName)
        binBuildDir = os.path.join(buildRoot, prefixDir[1:], 'bin')
        print '  Copying executable file "%s" to %s' % (progName, binBuildDir)
        if not os.path.isdir(binBuildDir):
            os.makedirs(binBuildDir)
        shutil.copy2(progName, binBuildDir)
        cleanSource()
        print 'Install complete.'


if __name__ == '__main__':
    main()
