import math

import pytest

import unitatom
import unitdata
import unitgroup

# Expected values are supplied independently of the reduction implementation.
REFERENCES = [
    (1, 'in', 'cm', 2.54), (1, 'ft', 'm', 0.3048),
    (1, 'mi', 'km', 1.609344), (1, 'nmi', 'm', 1852),
    (1, 'lb', 'kg', 0.45359237), (1, 'oz', 'gram', 28.349523125),
    (1, 'liter', 'm^3', 0.001), (1, 'gal', 'liter', 3.785411784),
    (1, 'hr', 's', 3600), (1, 'knot', 'm/s', 1852/3600),
    (60, 'mph', 'km/hr', 96.56064),
    (1, 'acre', 'm^2', 4046.8564224),
    (1, 'atm', 'Pa', 101325), (1, 'bar', 'Pa', 100000),
    (1, 'kWh', 'J', 3600000), (1, 'N*m', 'J', 1),
    (180, 'degree', 'radian', math.pi),
    (1, 'm/(s*s)', 'm/s^2', 1), (1, '(m/s)/s', 'm/s^2', 1),
    (1, 'in^0.5', 'cm^0.5', math.sqrt(2.54)),
    (0, 'C', 'F', 32), (100, 'C', 'F', 212), (-40, 'C', 'F', -40),
    (273.15, 'K', 'C', 0), (32, 'F', 'C', 0),
    (0, 'dBm', 'W', 0.001), (30, 'dBm', 'W', 1),
    (6, 'Beaufort wind', 'm/s', 0.836 * 6**1.5),
    (0, 'gas mark', 'F', 212), (9, 'gas mark', 'F', 464),
    (5, 'liter per 100 km', 'mpg', 3.785411784/(5*0.01609344)),
    (1, 'Planck length', 'm', 1.616255e-35),
    (1, 'Planck mass', 'kg', 2.176434e-8),
    (1, 'Planck time', 's', 5.391247e-44),
    (1, 'elementary charge', 'coulomb', 1.602176634e-19),
    (1, 'Boltzmann constant', 'J/K', 1.380649e-23),
    (1, 'vacuum permittivity', 'farad/m', 8.8541878188e-12),
]


@pytest.mark.parametrize('value,source,target,expected', REFERENCES)
def test_independent_reference_conversions(value, source, target, expected, make_group):
    a, b = make_group(source), make_group(target)
    assert a.categoryMatch(b)
    assert a.convert(value, b) == pytest.approx(expected, rel=1e-11,
                                               abs=1e-12 if expected == 0 else 0)


@pytest.mark.parametrize('value', [-1e12, -42.5, -1e-12, 0, 1e-12, 1, 42.5, 1e12])
@pytest.mark.parametrize('source,target', [('in', 'm'), ('kg', 'lb'),
                                         ('m^3', 'gal'), ('C', 'F'),
                                         ('m/s', 'km/hr')])
def test_signed_linear_and_affine_round_trips(value, source, target, make_group):
    a, b = make_group(source), make_group(target)
    assert b.convert(a.convert(value, b), a) == pytest.approx(value, rel=1e-10, abs=2e-10)


@pytest.mark.parametrize('source,target', [('m', 's'), ('kg', 'm'),
                                         ('m^2', 'm'), ('C*m', 'K*m')])
def test_incompatible_dimensions_or_non_linear_combinations(source, target, make_group):
    assert not make_group(source).categoryMatch(make_group(target))


@pytest.mark.parametrize('text', ['', 'not a unit', 'm/', '/m', 'm**s',
                                  '(m/s', 'm^', 'm^-', 'm^1000', 'm^garbage'])
def test_incomplete_or_invalid_input_does_not_crash(text, data, options):
    group = unitgroup.UnitGroup(data, options)
    group.update(text)
    assert not group.groupValid()
    group.reduceGroup()  # typing an incomplete unit must be safe


@pytest.mark.parametrize('text,expected', [('METERS', 'meter'), ('m2', 'm^2'),
                                          ('m3', 'm^3'), (' m / s ', 'm / s')])
def test_name_alias_plural_and_exponent_syntax(text, expected, make_group):
    assert make_group(text).unitString() == expected


@pytest.mark.parametrize('definition,match', [
    ('bad = absent', 'absent'), ('bad = bad', 'Circular'),
    ('bad = 2e--3 m', 'Invalid'), ('bad = (m', 'Invalid'),
])
def test_invalid_or_cyclic_reference_is_a_domain_error(definition, match, data, options):
    local = unitdata.UnitData()
    local.update(data)
    datum = unitatom.UnitDatum(definition)
    local['bad'] = datum
    group = unitgroup.UnitGroup(local, options)
    group.replaceCurrent(datum)
    with pytest.raises(unitdata.UnitDataError, match=match):
        group.reduceGroup()


def test_broken_equation_and_domain_error(make_group, data):
    datum = unitatom.UnitDatum('bad equation = [m] x / 0; x')
    local = unitdata.UnitData()
    local.update(data)
    local['badequation'] = datum
    bad = make_group('bad equation', local)
    with pytest.raises(unitdata.UnitDataError, match='Bad equation'):
        bad.convert(1, make_group('m'))
    with pytest.raises(unitdata.UnitDataError, match='Bad equation'):
        make_group('W').convert(-1, make_group('dBm'))


@pytest.mark.parametrize('notation,value,places,expected', [
    ('general', 2.54, 8, '2.54'), ('fixed', 2.54, 4, '2.5400'),
    ('scientific', 1234, 2, '1.23E+03'),
    ('engineering', 1234, 2, '1.23E+03'),
    ('engineering', 999.999, 2, '1.00E+03'),
    ('engineering', -0.0000123, 2, '-12.30E-06'),
    ('engineering', 0, 2, '0.00E+00'),
])
def test_formatting(notation, value, places, expected, options, make_group):
    options.changeData('Notation', notation, False)
    options.changeData('DecimalPlaces', str(places), False)
    assert make_group('m').formatNumStr(value) == expected


def test_group_edit_operations(data, options):
    group = unitgroup.UnitGroup(data, options)
    assert group.currentUnit() is None
    group.update('m/s', 0)
    assert group.currentUnit().unitName == 'm'
    group.changeExp(2)
    assert group.unitString() == 'm^2 / s'
    group.updateCurrentUnit('m/s', 3)
    assert group.currentUnit().unitName == 's'
    group.replaceCurrent(data['hr'])
    assert group.unitString() == 'm^2 / hr'
    group.addOper(True)
    group.replaceCurrent(data['kg'])
    assert group.groupValid()
    group.clearUnit()
    assert group.unitString() == '' and not group.groupValid()


@pytest.mark.parametrize('language,source,target,value,expected', [
    ('ca', 'kilotona no mètrica', 'kg', 1, 907184.74),
    ('ca', 'township', 'm^2', 1, 36*1609.344**2),
    ('sv', 'kort ton', 'kg', 1, 907.18474),
    ('sv', 'kiloton icke-metriskt', 'kg', 1, 907184.74),
    ('sv', 'ct', 'gram', 1, 0.2),
    ('sv', 'kph', 'm/s', 36, 10),
    ('sv', 'mAh', 'A*s', 1, 3.6),
    ('sv', 'ljussekund', 'm', 1, 299792458),
    ('sv', 'vecka', 's', 1, 604800),
    ('sv', 'cal', 'J', 1, 4.1868),
    ('sv', 'kWh', 'J', 1, 3600000),
    ('sv', 'ton kraft', 'N', 1, 1000*9.80665),
    ('sv', 'tonne kraft', 'N', 1, 1000*9.80665),
])
def test_localized_numeric_regressions(language, source, target, value, expected,
                                       catalogues, make_group):
    a = make_group(source, catalogues[language])
    b = make_group(target, catalogues[language])
    assert a.categoryMatch(b)
    assert a.convert(value, b) == pytest.approx(expected, rel=1e-10, abs=0)
