import os
import subprocess
import sys

import pytest

from helpers import ROOT, SCRIPT, run_cli

pytestmark = pytest.mark.integration


@pytest.mark.parametrize('args,expected', [
    (['-q', '1', 'in', 'cm'], '1 in = 2.54 cm'),
    (['-q', 'in', 'cm'], '1.0 in = 2.54 cm'),
    (['-q', '0', 'C', 'F'], '0 C = 32 F'),
    (['-q', '-f', '-d', '4', '1', 'in', 'cm'], '1 in = 2.5400 cm'),
    (['1', 'in', 'cm', '-q'], '1 in = 2.54 cm'),
    (['-q', '-s', '-d', '3', '1', 'km', 'm'], '1 km = 1.000E+03 m'),
    (['-q', '-e', '-d', '2', '1', 'km', 'm'], '1 km = 1.00E+03 m'),
    (['-q', '--', '-40', 'C', 'F'], '-40 C = -40 F'),
    (['-q', '1', 'nautical mile', 'm'], '1 nautical mile = 1852 m'),
])
def test_conversion_output_and_zero_exit(args, expected):
    result = run_cli(*args)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected
    assert 'Traceback' not in result.stderr


@pytest.mark.parametrize('args,code', [
    (['-q', '1', 'nonsense', 'm'], 1),
    (['-q', '1', 'm', 's'], 1),
    (['-q'], 1), (['-q', '1', 'm'], 1),
    (['-q', '-d', 'nonsense', 'm', 'cm'], 2),
    (['-q', '-d', '-1', 'm', 'cm'], 2),
    (['-q', '-d', '13', 'm', 'cm'], 2),
    (['--does-not-exist'], 2),
    (['-q', '1', 'm', 'cm', 'extra'], 2),
    (['-q', 'nan', 'm', 'cm'], 1),
    (['-q', 'inf', 'm', 'cm'], 1),
    (['-q', '--', '-inf', 'm', 'cm'], 1),
    (['-q', '0', 'liter per 100 km', 'mpg'], 1),
    (['-q', '--', '-1', 'W', 'dBm'], 1),
])
def test_failure_exit_codes_and_clean_diagnostics(args, code):
    result = run_cli(*args)
    assert result.returncode == code, (result.stdout, result.stderr)
    assert result.stdout or result.stderr
    assert 'Traceback' not in result.stdout + result.stderr


@pytest.mark.parametrize('flag', ['-h', '--help'])
def test_help_documents_validation_and_version(flag):
    result = run_cli(flag)
    assert result.returncode == 0
    for word in ('Usage', '--version', '--test', '--test-all', '--quiet'):
        assert word in result.stdout


def test_version_does_not_start_gui_or_load_catalogues():
    # Even a deliberately invalid GUI platform must not affect a CLI command.
    result = run_cli('--version', env={'QT_QPA_PLATFORM': 'invalid-platform'})
    assert result.returncode == 0
    assert result.stdout.strip() == 'ConvertAll 0.9.3 (Qt6)'


@pytest.mark.parametrize('flag', ['-t', '--test'])
def test_command_test_validates_english(flag):
    result = run_cli(flag)
    assert result.returncode == 0, result.stderr
    assert '626' in result.stdout and 'All units pass tests' in result.stdout


def test_command_test_all_validates_every_catalogue():
    result = run_cli('--test-all')
    assert result.returncode == 0, result.stderr
    for name in ['units.dat', 'units_ca.dat', 'units_de.dat', 'units_es.dat',
                 'units_fr.dat', 'units_ru.dat', 'units_sv.dat']:
        assert name in result.stdout
    assert result.stdout.count('All units pass tests') == 7


def test_interactive_number_reverse_new_and_invalid_input():
    result = run_cli('-i', input='in\ncm\n2\nr\ninvalid\nn\nC\nF\n0\nq\n')
    assert result.returncode == 0, result.stderr
    assert '1.0 in = 2.54 cm' in result.stdout
    assert '2 in = 5.08 cm' in result.stdout
    assert '2 cm = 0.78740157 in' in result.stdout
    assert '0 C = 32 F' in result.stdout


def test_interactive_eof_is_normal_exit():
    assert run_cli('-i').returncode == 0


@pytest.mark.parametrize('locale', ['C', 'C.UTF-8', 'en_US.UTF-8', 'POSIX'])
def test_english_locales_do_not_emit_translation_warnings(locale):
    result = run_cli('-q', 'in', 'cm', env={'LC_MESSAGES': locale})
    assert result.returncode == 0
    assert 'Warning' not in result.stdout + result.stderr


@pytest.mark.parametrize('arguments,expected_output', [
    (['-q', '1', 'in', 'cm'], '2.54'),
    pytest.param(['--runtime-info'], '"sip_package": "13.13.0"',
                 marks=pytest.mark.pinned_qt_profile),
])
def test_cli_never_imports_qt_widgets_or_qt_gui(tmp_path, arguments, expected_output):
    code = f'''
import importlib.abc, sys
sys.path.insert(0, {str(SCRIPT.parent)!r})
class RejectGui(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in ('PyQt6.QtWidgets', 'PyQt6.QtGui'):
            raise RuntimeError('CLI attempted a GUI import: ' + fullname)
sys.meta_path.insert(0, RejectGui())
import convertall
sys.argv = [{str(SCRIPT)!r}] + {arguments!r}
sys.exit(convertall.main())
'''
    result = subprocess.run([sys.executable, '-c', code], capture_output=True,
                            text=True, timeout=20, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert expected_output in result.stdout


def test_real_main_qapplication_event_loop_and_gui_resources():
    result = run_cli('--gui-smoke-test')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'GUI smoke test passed (Qt6)' in result.stdout


def test_gui_smoke_rejects_conversion_arguments():
    assert run_cli('--gui-smoke-test', 'in').returncode == 2


def test_test_all_is_nonzero_for_a_broken_translated_catalogue(tmp_path):
    from helpers import copy_project
    project = copy_project(tmp_path / 'project')
    with (project / 'data/units_fr.dat').open('a', encoding='utf-8') as stream:
        stream.write('\nbroken test = missing reference\n')
    result = run_cli('--test-all', script=project / 'source/convertall.py')
    assert result.returncode == 1
    assert 'missing reference' in result.stdout
    assert 'Traceback' not in result.stdout + result.stderr


def test_main_data_error_has_no_traceback(tmp_path):
    from helpers import copy_project
    project = copy_project(tmp_path / 'project')
    (project / 'data/units.dat').write_text('m =\n', encoding='utf-8')
    result = run_cli('-q', 'in', 'cm', script=project / 'source/convertall.py')
    assert result.returncode == 1 and 'unit data' in result.stdout
    assert 'Traceback' not in result.stdout + result.stderr


@pytest.mark.parametrize('flag', ['-nonsense', '-bad', '-foo', '-invalid'])
def test_unknown_short_options_cannot_accidentally_launch_gui(flag):
    result = run_cli(flag, env={'QT_QPA_PLATFORM': 'invalid-platform'})
    assert result.returncode == 2
    assert 'Usage' in result.stdout and 'Traceback' not in result.stderr


def test_real_gui_qt_style_option_is_still_accepted():
    result = run_cli('-style', 'Fusion', '--gui-smoke-test')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'GUI smoke test passed' in result.stdout


def test_diagnostics_do_not_create_a_user_preferences_file(isolated_environment):
    for flag in ('--version', '--help', '--test-all'):
        result = run_cli(flag)
        assert result.returncode == 0
    assert not list(isolated_environment.rglob('.convertall'))
    assert not list(isolated_environment.rglob('convertall.ini'))


@pytest.mark.pinned_qt_profile
def test_runtime_info_is_actual_qt6_json_without_a_gui_or_preferences(isolated_environment):
    import json
    result = run_cli('--runtime-info', env={'QT_QPA_PLATFORM': 'invalid-platform'})
    assert result.returncode == 0, result.stderr
    info = json.loads(result.stdout)
    assert info['application'] == 'ConvertAll'
    assert info['version'] == '0.9.3'
    assert info['binding'] == 'PyQt6'
    assert info['pyqt_binding'] == '6.11.0'
    assert info['qt_runtime'] == '6.11.2'
    from importlib.metadata import version
    from PyQt6 import sip
    assert info['sip_package'] == version('PyQt6-sip') == '13.13.0'
    assert info['sip_generator'] == sip.SIP_VERSION_STR
    assert info['sip_generator']
    assert info['qt_translations_path']
    assert not list(isolated_environment.rglob('.convertall'))
    assert not list(isolated_environment.rglob('convertall.ini'))


@pytest.mark.parametrize('extra', [['in'], ['--version'], ['--gui-smoke-test']])
def test_runtime_info_rejects_other_arguments(extra):
    result = run_cli('--runtime-info', *extra, env={'QT_QPA_PLATFORM': 'invalid-platform'})
    assert result.returncode == 2
    assert 'does not accept other arguments' in result.stderr


def test_runtime_info_distinguishes_sip_distribution_from_generator(monkeypatch):
    from importlib import metadata
    from PyQt6 import sip
    import convertall
    version = metadata.version
    monkeypatch.setattr(metadata, 'version',
                        lambda name: '13.13.0' if name == 'PyQt6-sip' else version(name))
    monkeypatch.setattr(sip, 'SIP_VERSION_STR', '6.17.0')
    info = convertall.runtimeInfo()
    assert info['sip_package'] == '13.13.0'
    assert info['sip_generator'] == '6.17.0'


def test_runtime_info_missing_metadata_is_a_clean_error(monkeypatch, capsys):
    from importlib import metadata
    import convertall
    version = metadata.version
    def missing(name):
        if name == 'PyQt6-sip':
            raise metadata.PackageNotFoundError(name)
        return version(name)
    monkeypatch.setattr(metadata, 'version', missing)
    # This unit test does not construct another Qt application in the process.
    monkeypatch.setattr(convertall, 'QCoreApplication', lambda args: None)
    monkeypatch.setattr(sys, 'argv', ['convertall.py', '--runtime-info'])
    assert convertall.main() == 1
    output = capsys.readouterr()
    assert output.out == ''
    assert 'Runtime information unavailable' in output.err
    assert 'PyQt6-sip' in output.err
    assert 'Traceback' not in output.err
