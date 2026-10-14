"""Every shipped definition must be usable, not silently skipped."""
import math
import re

import pytest

from conftest import CATALOGUE_COUNTS, catalogue_path
import unitatom
import unitdata
import unitgroup


def catalogue_cases():
    cases = []
    for language in CATALOGUE_COUNTS:
        # Collect the actual file's names independently of UnitData. A loader
        # that drops a broken line must not make the test disappear.
        for line in catalogue_path(language).read_text(encoding='utf-8').splitlines():
            text = line.split('#', 1)[0].strip()
            if '=' in text and not text.startswith('['):
                name = text.split('=', 1)[0].strip()
                cases.append(pytest.param(language, name,
                                          id=f'{language}:{name}'))
    return cases


@pytest.mark.parametrize('language,name', catalogue_cases())
def test_every_definition_parses_reduces_and_round_trips(language, name,
                                                         catalogues, options):
    catalogue = catalogues[language]
    key = name.lower().replace(' ', '')
    assert key in catalogue
    datum = catalogue[key]
    group = unitgroup.UnitGroup(catalogue, options)
    group.update(name)
    assert group.groupValid(), f'{language}: {name} is not selectable by name'
    group.reduceGroup()
    assert group.checkLinear(), name
    assert math.isfinite(group.factor) and group.factor > 0, name
    # Use a separate group of fundamental units, rather than convert(g, g),
    # which could mask a shared reduction error. This is a consistency check;
    # independent physical reference values are in test_engine.py.
    base = unitgroup.UnitGroup(catalogue, options)
    base.unitList = [unitatom.UnitAtom('', item.datum)
                     for item in group.reducedList]
    for atom, reduced in zip(base.unitList, group.reducedList):
        atom.exp = reduced.exp
    base.reducedList = group.reducedList[:]
    for sample in (1.0, 10.0):
        canonical = group.convert(sample, base)
        assert math.isfinite(canonical), name
        assert base.convert(canonical, group) == pytest.approx(sample, rel=2e-9,
                                                              abs=1e-9)


@pytest.mark.parametrize('language,count', CATALOGUE_COUNTS.items())
def test_catalogue_counts_and_idempotent_reload(language, count, catalogues):
    original = catalogues[language]
    assert len(original) == count
    copy = unitdata.UnitData()
    assert copy.readData(catalogue_path(language)) == count
    names, types = list(copy), copy.typeList[:]
    assert copy.readData(catalogue_path(language)) == count
    assert list(copy) == names
    assert copy.typeList == types
    assert len(types) == len(set(types))


def test_files_do_not_contain_reserved_operators_in_unit_names():
    for language in CATALOGUE_COUNTS:
        for line in catalogue_path(language).read_text(encoding='utf-8').splitlines():
            text = line.split('#', 1)[0].strip()
            if '=' in text:
                assert not re.search(r'[*/^()]', text.split('=', 1)[0]), (language, line)


@pytest.mark.parametrize('language', ['ca_ES.UTF-8', 'de_DE', 'es_MX', 'fr_FR',
                                      'ru_RU', 'sv_SE', 'xx_XX'])
def test_locale_fallback(language, monkeypatch):
    monkeypatch.setattr(unitdata, 'lang', language)
    data = unitdata.UnitData()
    expected = language[:2] if language[:2] in CATALOGUE_COUNTS else 'en'
    assert data.readData() == CATALOGUE_COUNTS[expected]


@pytest.mark.parametrize('text', [
    '[length]\nm = !\nM = 2 m\n',  # case/space-insensitive duplicate
    '[length]\nm = !\nm = \n',
    '[length]\nm = [m bad equation\n',
    '[length]\nm = !\ninvalid line\n',
])
def test_bad_file_is_atomic_and_reports_unit_data_error(text, data, tmp_path):
    path = tmp_path / 'broken.dat'
    path.write_text(text, encoding='utf-8')
    before, types = list(data.items()), data.typeList[:]
    with pytest.raises(unitdata.UnitDataError):
        data.readData(path)
    assert list(data.items()) == before
    assert data.typeList == types


def test_missing_file_is_a_domain_error(tmp_path):
    with pytest.raises(unitdata.UnitDataError, match='read'):
        unitdata.UnitData().readData(tmp_path / 'absent.dat')


def test_sort_and_partial_search(catalogues):
    data = unitdata.UnitData()
    data.update(catalogues['en'])
    for column in (0, 1, 2):
        data.sortUnits(column)
        texts = [u.columnText(column).lower() for u in data.values()]
        assert texts == sorted(texts)
        data.sortUnits(column, False)
        assert [u.columnText(column).lower() for u in data.values()] == sorted(texts, reverse=True)
    assert data.findPartialMatch('milli') is not None
    assert data.findPartialMatch('') is None
    assert data.findPartialMatch('nonexistentXYZ') is None
    assert data.partialMatches('milli')
