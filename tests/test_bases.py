import pytest

import bases


@pytest.mark.parametrize('base', [2, 8, 10, 16])
@pytest.mark.parametrize('number', [0, 1, 42, 127, 255, 65535, 2**32-1])
def test_unsigned_base_round_trip(base, number):
    text = bases.baseNumStr(number, base, 32, False)
    assert bases.baseNum(text, base, 32, False) == number


@pytest.mark.parametrize('base', [2, 8, 10, 16])
@pytest.mark.parametrize('number', [-128, -42, -1, 0, 1, 127])
def test_twos_complement_round_trip(base, number):
    text = bases.baseNumStr(number, base, 8, True)
    assert bases.baseNum(text, base, 8, True) == number


@pytest.mark.parametrize('text,base,bits', [('256', 10, 8), ('2', 2, 8),
                                          ('G', 16, 8), ('not a number', 10, 32)])
def test_invalid_base_input(text, base, bits):
    with pytest.raises(ValueError):
        bases.baseNum(text, base, bits)


def test_empty_sign_and_whitespace():
    assert bases.baseNum('-', 10) == 0
    assert bases.baseNum('FF FF', 16) == 65535


@pytest.mark.parametrize('decimal,expected', [(0.5, (1, 2)), (0.75, (3, 4)),
                                             (0.125, (1, 8)), (-0.5, (-1, 2)),
                                             (2.0, (2, 1))])
def test_fraction_exact_values(decimal, expected):
    assert bases.listFractions(decimal)[-1] == expected


def test_fraction_zero_and_power_of_two():
    assert bases.listFractions(0) == []
    results = bases.listFractions(1/3, True)
    assert results
    assert all(denom & (denom - 1) == 0 for _, denom in results)
    assert abs(results[-1][0]/results[-1][1] - 1/3) < 1e-8


@pytest.mark.parametrize('number,bits', [(128, 8), (-129, 8), (2**32, 32)])
def test_signed_overflow_is_not_silently_reinterpreted(number, bits):
    assert bases.baseNumStr(number, 10, bits, True) == 'overflow'
    with pytest.raises(ValueError):
        bases.baseNum(str(number), 10, bits, True)


@pytest.mark.parametrize('base', [0, 1, 17])
def test_invalid_base_cannot_loop_forever(base):
    with pytest.raises(ValueError):
        bases.baseNumStr(1, base)
    with pytest.raises(ValueError):
        bases.baseNum('1', base)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), -float('inf')])
def test_fraction_non_finite_input_is_rejected(value):
    with pytest.raises(ValueError):
        bases.listFractions(value)


def test_difficult_fraction_inputs_finish_instead_of_scanning_a_billion_denominators():
    from pathlib import Path
    import subprocess
    import sys
    source = Path(__file__).resolve().parents[1] / 'source'
    code = f'''
import builtins, math, sys
builtins._ = lambda text, *args: text
sys.path.insert(0, {str(source)!r})
import bases
for value in (math.pi, -math.sqrt(2), 1e-9, 0.333333333):
    fractions = bases.listFractions(value)
    assert fractions, value
    assert max(q for p, q in fractions) <= 10**9
    assert abs(fractions[-1][0] / fractions[-1][1] - value) < 1e-8
'''
    result = subprocess.run([sys.executable, '-c', code], capture_output=True,
                            text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('value', [1e-100, -1e-100, 1e-12])
def test_fraction_below_denominator_resolution_returns_without_hanging(value):
    assert bases.listFractions(value) == []


@pytest.mark.parametrize('value', [0.75, 3.4, -3.4, 1.23456789])
def test_fraction_approximations_strictly_improve(value):
    results = bases.listFractions(value)
    errors = [abs(value - p/q) for p,q in results]
    assert all(a > b for a,b in zip(errors, errors[1:]))
    assert errors[-1] < 1e-8


@pytest.mark.parametrize('value', [1e308, -1e308])
@pytest.mark.parametrize('power_of_two', [False, True])
def test_fraction_large_finite_integer_does_not_overflow(value, power_of_two):
    result = bases.listFractions(value, power_of_two)
    assert result == [(int(value), 1)]
