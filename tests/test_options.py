from pathlib import Path
import sys

import pytest

import option
import optiondefaults
import recentunits


def test_defaults_and_typed_fallback(options):
    assert options.boolData('ShowOpButtons')
    assert options.intData('DecimalPlaces', 0, 12) == 8
    options.userDict['DecimalPlaces'] = 'bad'
    assert options.intData('DecimalPlaces', 0, 12) == 8
    options.userDict['DecimalPlaces'] = '999'
    assert options.numData('DecimalPlaces', 0, 12) == 8
    options.userDict['ShowOpButtons'] = 'bad'
    assert options.boolData('ShowOpButtons')
    assert options.strData('GuiFont', True) == ''
    assert options.changeData('DecimalPlaces', '8', True)
    assert not options.changeData('DecimalPlaces', '8', True)


def test_unknown_keys_have_safe_defaults(options, capsys):
    assert not options.boolData('absent')
    assert options.intData('absent') == 0
    assert options.numData('absent') == 0
    assert options.strData('absent') == ''
    assert not options.changeData('absent', '1', True)
    assert 'Option error' in capsys.readouterr().out


def test_preferences_utf8_comments_and_legacy_key_round_trip(isolated_environment):
    options = option.Option('convertall')
    options.loadAll(optiondefaults.defaultList)
    path = Path(options.path)
    assert path.is_relative_to(isolated_environment)
    original = path.read_text(encoding='utf-8')
    path.write_text(original + '# custom comment\nCustomValue café\n', encoding='utf-8')
    options.loadAll(optiondefaults.defaultList)
    options.changeData('DecimalPlaces', '6', True)
    options.changeData('RemenberDlgPos', 'no', True)  # keep old spelling compatible
    options.changeData('CustomValue', 'mètre', True)
    options.addData('NewValue', 'm³', True)
    assert options.writeChanges()
    reread = option.Option('convertall')
    assert reread.loadAll(optiondefaults.defaultList)
    assert reread.intData('DecimalPlaces') == 6
    assert not reread.boolData('RemenberDlgPos')
    assert reread.strData('CustomValue') == 'mètre'
    assert reread.strData('NewValue') == 'm³'
    assert '# custom comment' in path.read_text(encoding='utf-8')
    # Repeated writes must not duplicate settings.
    options.writeChanges()
    assert sum(line.startswith('NewValue ') for line in path.read_text(encoding='utf-8').splitlines()) == 1


def test_portable_config_is_used_when_no_user_config_exists(tmp_path, monkeypatch):
    portable = tmp_path / ('convertall.ini' if sys.platform.startswith('win') else '.convertall')
    portable.write_text('DecimalPlaces 3\n', encoding='utf-8')
    monkeypatch.setattr(sys, 'path', [str(tmp_path)] + sys.path[1:])
    config = option.Option('convertall')
    assert config.path == str(portable)
    assert config.loadAll(optiondefaults.defaultList)
    assert config.intData('DecimalPlaces') == 3


def test_write_failure_is_reported_without_crashing(tmp_path, options, capsys):
    options.path = str(tmp_path / 'missing-directory' / 'file')
    options.changeData('DecimalPlaces', '3', True)
    assert not options.writeChanges()
    assert 'could not write' in capsys.readouterr().out


def test_recent_units_order_deduplication_truncation_and_persistence(options):
    recent = recentunits.RecentUnits(options)
    assert not recent
    for name in ['m', 's', 'm', 'in', 'cm']:
        recent.addEntry(name)
    assert recent == ['cm', 'in', 'm', 's']
    options.changeData('RecentUnits', '2', False)
    recent.updateQuantity()
    assert recent == ['cm', 'in']
    recent.writeList()
    assert recentunits.RecentUnits(options) == recent
    options.changeData('RecentUnits', '0', False)
    recent.updateQuantity()
    recent.addEntry('m')
    assert not recent
