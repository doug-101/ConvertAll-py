from pathlib import Path
import re
import xml.etree.ElementTree as ET

import pytest
from PyQt6.QtCore import QCoreApplication, QLibraryInfo, QTranslator, QUrl
from PyQt6.QtGui import QTextCursor

from helpers import ROOT
import convertall
import helpview
import icondict

pytestmark = pytest.mark.gui


@pytest.mark.parametrize('language', ['ca', 'de', 'es', 'fr', 'ru', 'sv'])
def test_all_app_catalogues_load_and_translate_active_ts_messages(qapp, language):
    translator = QTranslator()
    assert translator.load(str(ROOT / 'translations' / f'convertall_{language}.qm'))
    assert not translator.isEmpty()
    tree = ET.parse(ROOT / 'translations' / f'convertall_{language}.ts')
    checked = 0
    for context in tree.findall('context'):
        name = context.findtext('name')
        for message in context.findall('message'):
            translation = message.find('translation')
            if translation is None or translation.get('type') in ('obsolete', 'vanished', 'unfinished'):
                continue
            source, expected = message.findtext('source'), translation.text
            if not expected:
                continue
            actual = translator.translate(name, source, message.findtext('comment'))
            assert actual == expected, (language, name, source)
            assert sorted(re.findall(r'\{\d+\}', actual)) == sorted(re.findall(r'\{\d+\}', source))
            checked += 1
    assert checked == {'ca': 69, 'de': 79, 'es': 79, 'fr': 79, 'ru': 90, 'sv': 92}[language]
    assert translator.translate('convertdlg', 'From Unit') != 'From Unit'


@pytest.mark.parametrize('language', ['ca', 'de', 'es', 'fr', 'ru', 'sv'])
def test_qt6_runtime_qtbase_catalogues_are_readable_or_reported_absent(qapp, capsys, monkeypatch,
                                                                      language):
    """Distribution Qt may ship fewer widget languages than the pinned wheels.

    The contract is exact, not lenient: a shipped catalogue must load, and an
    absent one must be reported cleanly instead of breaking the application.
    """
    path = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
    translator = QTranslator()
    if (path / f'qtbase_{language}.qm').is_file():
        assert translator.load(f'qtbase_{language}', str(path))
        assert not translator.isEmpty()
        return
    monkeypatch.setattr(convertall, 'translationPath', str(ROOT / 'translations'))
    before = set(qapp.findChildren(QTranslator))
    try:
        assert not convertall.loadTranslator(f'qt_{language}', qapp)
        output = capsys.readouterr().out
        assert f'translation file "qt_{language}" could not be loaded' in output
        assert 'Traceback' not in output
        assert (ROOT / 'translations' / f'convertall_{language}.qm').is_file()
    finally:
        for extra in set(qapp.findChildren(QTranslator)) - before:
            qapp.removeTranslator(extra)
            extra.deleteLater()


def test_translator_region_fallback_and_missing_file(qapp, monkeypatch, capsys):
    monkeypatch.setattr(convertall, 'translationPath', str(ROOT / 'translations'))
    before = set(qapp.findChildren(QTranslator))
    try:
        assert convertall.loadTranslator('convertall_fr_FR', qapp)
        assert QCoreApplication.translate('convertdlg', 'From Unit') != 'From Unit'
        assert not convertall.loadTranslator('not_a_translation', qapp)
        assert 'could not be loaded' in capsys.readouterr().out
    finally:
        for translator in set(qapp.findChildren(QTranslator)) - before:
            qapp.removeTranslator(translator)
            translator.deleteLater()


@pytest.mark.parametrize('locale,expected', [('C.UTF-8', 'C'), ('POSIX', 'POSIX'),
                                            ('fr-FR.UTF-8', 'fr_FR'),
                                            ('sv_SE.UTF-8@euro', 'sv_SE')])
def test_locale_normalization(qapp, monkeypatch, locale, expected):
    loaded = []
    monkeypatch.setenv('LC_MESSAGES', locale)
    monkeypatch.setattr(convertall, 'loadTranslator',
                        lambda name, app: loaded.append(name) or False)
    monkeypatch.setattr(convertall, 'lang', '')
    convertall.setupTranslator(qapp)
    assert convertall.lang == expected
    assert len(loaded) == (0 if expected in ('C', 'POSIX') else 2)


def test_icon_dictionary_lazy_cache_and_bulk_loading(qapp, tmp_path):
    icons = icondict.IconDict()
    icons.addIconPath([str(tmp_path / 'absent'), str(ROOT / 'icons')])
    icon = icons['helpback']
    assert not icon.isNull() and icons['helpback'] is icon
    with pytest.raises(KeyError):
        icons['not-an-icon']
    icons.loadAllIcons()
    for name in ('helpback', 'helpforward', 'helphome', 'helpnext', 'helpprevious'):
        assert not icons[name].isNull()


def test_help_local_document_find_next_previous_and_links(window, qtbot, monkeypatch):
    window.help()
    view = window.helpView
    qtbot.addWidget(view)
    assert view.isVisible()
    assert 'ConvertAll' in view.textView.toPlainText()
    view.findEdit.setText('ConvertAll')
    view.findTextChanged('ConvertAll')
    assert view.findNextAct.isEnabled() and view.findPreviousAct.isEnabled()
    view.textView.moveCursor(QTextCursor.MoveOperation.Start)
    view.findNext()
    assert view.textView.textCursor().selectedText() == 'ConvertAll'
    view.findPrevious()
    view.findEdit.setText('a-string-that-is-not-in-the-manual')
    view.findNext()
    assert 'not found' in view.statusBar().currentMessage()
    view.showLink(QUrl('https://example.invalid/'))
    assert view.statusBar().currentMessage() == 'https://example.invalid/'
    links = []
    monkeypatch.setattr(helpview.webbrowser, 'open', lambda *args: links.append(args))
    view.textView.setSource(QUrl('https://example.invalid/'))
    assert links == [('https://example.invalid/', True)]
    view.textView.setSource(QUrl.fromLocalFile(str(ROOT / 'doc' / 'README.html')))
    assert 'ConvertAll' in view.textView.toPlainText()
    window.help()
    assert window.helpView is view


def test_catalan_qtbase_fallback_uses_real_runtime_catalogue(qapp, monkeypatch, capsys):
    monkeypatch.setattr(convertall, 'translationPath', str(ROOT / 'translations'))
    before = set(qapp.findChildren(QTranslator))
    try:
        assert convertall.loadTranslator('qt_ca_ES', qapp)
        assert 'Warning' not in capsys.readouterr().out
    finally:
        for translator in set(qapp.findChildren(QTranslator)) - before:
            qapp.removeTranslator(translator)
            translator.deleteLater()


def test_system_locale_fallback_does_not_use_deprecated_python_api(qapp, monkeypatch):
    class FrenchLocale:
        @staticmethod
        def system():
            return FrenchLocale()
        def name(self):
            return 'fr_FR'
    monkeypatch.delenv('LC_MESSAGES', raising=False)
    monkeypatch.delenv('LANG', raising=False)
    monkeypatch.setattr(convertall, 'QLocale', FrenchLocale)
    monkeypatch.setattr(convertall, 'lang', '')
    monkeypatch.setattr(convertall, 'loadTranslator', lambda *args: False)
    convertall.setupTranslator(qapp)
    assert convertall.lang == 'fr_FR'
