"""Real extraction/preservation tests; no pylupdate6 helper substitution."""
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest

from helpers import ROOT
sys.path.insert(0, str(ROOT / 'tools'))
import update_translations


def test_ast_extracts_module_context_comments_unicode_and_locations(tmp_path):
    (tmp_path / 'aide.py').write_text('''
_('mètre & seconde')
_('Open', 'verb')
_('two ' 'literals')
_('mètre & seconde')
other('not a translation')
_('Close', comment='verb')
''', encoding='utf-8')
    messages = update_translations.extract_messages(tmp_path)
    assert set(messages) == {('aide', 'mètre & seconde', ''),
                             ('aide', 'Open', 'verb'), ('aide', 'two literals', ''),
                             ('aide', 'Close', 'verb')}
    assert messages['aide', 'mètre & seconde', ''] == [('../source/aide.py', 2),
                                                      ('../source/aide.py', 5)]


@pytest.mark.parametrize('expression', ["_(variable)", "_(f'{value}')", "_('a', comment)", '_()'])
def test_ast_refuses_sources_it_cannot_extract_safely(tmp_path, expression):
    (tmp_path / 'bad.py').write_text(expression, encoding='utf-8')
    with pytest.raises(ValueError, match='literal'):
        update_translations.extract_messages(tmp_path)


def test_catalogue_update_preserves_text_comments_and_vanished_history(tmp_path):
    path = tmp_path / 'convertall_fr.ts'
    path.write_text('''<?xml version="1.0" encoding="utf-8"?>
<TS version="2.1" language="fr_FR"><context><name>aide</name>
<message><source>Open</source><comment>verb</comment><extracomment>Translator note</extracomment><translation>Ouvrir</translation></message>
<message><source>Removed</source><translation>Ancien</translation></message>
<message><source>Restored</source><translation type="vanished">Restauré</translation></message>
</context></TS>''', encoding='utf-8')
    extracted = {('aide', 'Open', 'verb'): [('../source/aide.py', 10)],
                 ('aide', 'mètre & seconde', ''): [('../source/aide.py', 20)],
                 ('aide', 'Restored', ''): [('../source/aide.py', 30)]}
    update_translations.update_catalogue(path, extracted)
    catalogue = update_translations.catalogue_messages(path)
    active = catalogue['aide', 'Open', 'verb']
    assert active.findtext('translation') == 'Ouvrir'
    assert active.findtext('extracomment') == 'Translator note'
    assert active.find('location').attrib == {'filename': '../source/aide.py', 'line': '10'}
    assert catalogue['aide', 'Removed', ''].find('translation').get('type') == 'vanished'
    assert catalogue['aide', 'Restored', ''].find('translation').get('type') is None
    new = catalogue['aide', 'mètre & seconde', ''].find('translation')
    assert new.get('type') == 'unfinished'
    before = path.read_bytes()
    update_translations.update_catalogue(path, extracted)
    assert path.read_bytes() == before  # deterministic, stable updates
    assert ET.parse(path).getroot().get('language') == 'fr_FR'


def test_current_extraction_keeps_existing_filename_contexts():
    extracted = update_translations.extract_messages(ROOT / 'source')
    assert ('convertdlg', 'From Unit', '') in extracted
    assert ('fontset', '&OK', '') in extracted
    assert ('colorset', 'Color Settings', '') in extracted
    assert ('helpview', 'Text string not found', '') in extracted
    assert all(filename.startswith('../source/') and line > 0
               for locations in extracted.values() for filename, line in locations)


def test_compiler_is_explicit_and_qt6_version_is_required(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['update_translations.py', '--compile', '--lrelease', 'qt5-tool'])
    monkeypatch.setattr(update_translations.subprocess, 'run',
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, 'lrelease version 5.15.2', ''))
    assert update_translations.main() == 1
    assert 'non-Qt6' in capsys.readouterr().err
    assert update_translations.find_lrelease('custom/qt6/lrelease') == 'custom/qt6/lrelease'


def test_compile_writes_only_generated_application_qm(tmp_path, monkeypatch):
    ts = tmp_path / 'convertall_fr.ts'
    ts.write_text('<TS/>', encoding='utf-8')
    commands = []
    def run(command, **kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b'Qt6-generated-qm')
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(update_translations.subprocess, 'run', run)
    update_translations.compile_catalogue(ts, 'qt6-lrelease')
    assert commands[0][:3] == ['qt6-lrelease', '-nounfinished', str(ts)]
    assert ts.with_suffix('.qm').read_bytes() == b'Qt6-generated-qm'
    assert ts.read_text(encoding='utf-8') == '<TS/>'


def test_compile_refuses_an_empty_output_and_leaves_previous_qm(tmp_path, monkeypatch):
    ts = tmp_path / 'convertall_fr.ts'
    ts.write_text('<TS/>', encoding='utf-8')
    ts.with_suffix('.qm').write_bytes(b'previous')
    monkeypatch.setattr(update_translations.subprocess, 'run',
                        lambda *a, **k: subprocess.CompletedProcess(a, 0))
    with pytest.raises(ValueError, match='No QM generated'):
        update_translations.compile_catalogue(ts, 'qt6-lrelease')
    assert ts.with_suffix('.qm').read_bytes() == b'previous'
