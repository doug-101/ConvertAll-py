"""Regression tests for the formerly broken --test implementation."""
import pytest

import cmdline
import unitatom
import unitdata


def test_bad_definition_returns_false_instead_of_attribute_error(options, capsys):
    data = unitdata.UnitData()
    data['m'] = unitatom.UnitDatum('m = !')
    data['bad'] = unitatom.UnitDatum('bad = missing')
    assert cmdline.unitDataTest(data, options) is False
    assert 'missing' in capsys.readouterr().out


def test_cycle_is_reported_without_regex_type_error(options, capsys):
    data = unitdata.UnitData()
    data['loop'] = unitatom.UnitDatum('loop = loop')
    assert cmdline.unitDataTest(data, options) is False
    assert 'Circular' in capsys.readouterr().out


def test_validator_passes_valid_data(data, options, capsys):
    assert cmdline.unitDataTest(data, options) is True
    assert 'All units pass tests' in capsys.readouterr().out
