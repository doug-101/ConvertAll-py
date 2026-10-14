"""Shared fixtures: never touch the real user's settings or display."""
import builtins
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ['QT_API'] = 'pyqt6'
# Windows' offscreen plugin uses the basic font database, not the native
# Windows font discovery. Point it at fonts already installed on the host,
# before pytest-qt creates QApplication; do not bundle or download fonts.
if (sys.platform == 'win32'
        and os.environ['QT_QPA_PLATFORM'].split(':', 1)[0] == 'offscreen'
        and not os.environ.get('QT_QPA_FONTDIR')):
    windows_dir = os.environ.get('WINDIR') or os.environ.get('SystemRoot')
    if windows_dir:
        font_dir = Path(windows_dir) / 'Fonts'
        if font_dir.is_dir():
            os.environ['QT_QPA_FONTDIR'] = str(font_dir)
builtins._ = lambda text, comment='': text

import option
import optiondefaults
import unitdata
import unitgroup

CATALOGUE_COUNTS = {'en': 626, 'ca': 600, 'de': 637, 'es': 537,
                    'fr': 523, 'ru': 612, 'sv': 569}


def catalogue_path(language):
    return ROOT / 'data' / ('units.dat' if language == 'en'
                            else f'units_{language}.dat')


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    home.mkdir()
    appdata = home / 'appdata'
    appdata.mkdir()
    monkeypatch.setenv('HOME', str(home))
    monkeypatch.setenv('APPDATA', str(appdata))
    monkeypatch.setenv('XDG_CONFIG_HOME', str(home / 'config'))
    monkeypatch.setenv('LC_MESSAGES', 'C')
    monkeypatch.setenv('LANG', 'C.UTF-8')
    monkeypatch.setattr(builtins, '_', lambda text, comment='': text)
    monkeypatch.setattr(unitdata, 'dataFilePath', str(ROOT / 'data'))
    monkeypatch.setattr(unitdata, 'lang', '')
    # Resource discovery must resolve to the checkout, not pytest's executable.
    monkeypatch.setattr(sys, 'path', [str(ROOT / 'source')] + sys.path[1:])
    return home


@pytest.fixture
def options():
    result = option.Option('')
    result.loadAll(optiondefaults.defaultList)
    return result


@pytest.fixture(scope='session')
def catalogues():
    result = {}
    for language in CATALOGUE_COUNTS:
        data = unitdata.UnitData()
        data.readData(catalogue_path(language))
        result[language] = data
    return result


@pytest.fixture
def data(catalogues):
    return catalogues['en']


@pytest.fixture
def make_group(data, options):
    def make(text, catalogue=None):
        group = unitgroup.UnitGroup(data if catalogue is None else catalogue,
                                    options)
        group.update(text)
        assert group.groupValid(), text
        group.reduceGroup()
        return group
    return make


@pytest.fixture
def window(qtbot, monkeypatch, isolated_environment):
    import convertdlg
    monkeypatch.setattr(convertdlg, 'iconPath', str(ROOT / 'icons'))
    monkeypatch.setattr(convertdlg, 'helpFilePath', str(ROOT / 'doc'))
    monkeypatch.setattr(convertdlg, 'unitData', unitdata.UnitData(), raising=False)
    monkeypatch.setattr(convertdlg.ConvertDlg, 'unitData', unitdata.UnitData())
    defaults = [line for line in optiondefaults.defaultList
                if not line.startswith('ShowStartupTip')]
    monkeypatch.setattr(optiondefaults, 'defaultList',
                        defaults + ['ShowStartupTip no'])
    widget = convertdlg.ConvertDlg()
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitUntil(widget.isVisible)
    yield widget
    widget.close()


@pytest.fixture
def enter_units(window, qtbot):
    from PyQt6.QtCore import Qt
    def enter(source, target):
        for edit, text in ((window.fromUnitEdit, source),
                           (window.toUnitEdit, target)):
            edit.setFocus()
            qtbot.keyClick(edit, Qt.Key.Key_A, modifier=Qt.KeyboardModifier.ControlModifier)
            qtbot.keyClicks(edit, text)
        return window
    return enter
