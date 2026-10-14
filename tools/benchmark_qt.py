#!/usr/bin/env python3
"""Reproducible, headless Qt5/Qt6 comparison of the audited ConvertAll sources.

Run the driver with the standard-library Python; workers use isolated Qt venvs:
  python3 tools/benchmark_qt.py --python-qt5 .venv/qt5/bin/python \
    --python-qt6 .venv/qt6/bin/python --qt5-root .cache/qt-migration/qt5 \
    --qt6-root .cache/qt-migration/qt6 --runs 30 --output .cache/qt-migration/results.json
Each worker needs its chosen PyQt binding and psutil. On a minimal Linux image,
install the native OpenGL/EGL, xkbcommon and dbus runtime libraries first.
No user settings are modified: each subprocess gets a temporary HOME/APPDATA.

GUI startup includes binding imports, QApplication, the main window and its
first offscreen render, but excludes Python interpreter and script bootstrap.
Operation timings include processEvents for GUI work. Results are diagnostic,
not native-display, GPU, cold-cache or production certification benchmarks.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import traceback


PREFIX = 'QT_BENCHMARK_JSON '
BAD_DEFINITIONS = {
    'Boltzmann constant', 'elementary charge', 'Planck length',
    'Planck mass', 'Planck time', 'vacuum permittivity',
}
CONVERSIONS = (
    (1, 'in', 'cm', 2.54),
    (1, 'mile', 'km', 1.609344),
    (60, 'mile/hr', 'km/hr', 96.56064),
    (36, 'km/hr', 'm/s', 10),
    (1, 'g', 'kg', 0.001),
    (0, 'deg C', 'deg F', 32),
    (100, 'deg C', 'deg F', 212),
    (-40, 'deg C', 'deg F', -40),
    (32, 'deg F', 'deg C', 0),
    (1, 'm^2', 'cm^2', 10000),
    (1, 'acre', 'm^2', 4046.8564224),
    (1, 'Planck temperature', 'K', 1.416784e32),
)


def summary(values):
    ordered = sorted(values)
    return {
        'n': len(values), 'median': statistics.median(values),
        'min': min(values), 'max': max(values),
        'p95': ordered[max(0, math.ceil(0.95 * len(values)) - 1)],
        'samples': values,
    }


def prepare_app(root, binding):
    """Import and render the unchanged Qt5 app or isolated Qt6 prototype."""
    start = time.perf_counter_ns()
    package = 'PyQt5' if binding == 'qt5' else 'PyQt6'
    core = importlib.import_module(package + '.QtCore')
    gui = importlib.import_module(package + '.QtGui')
    widgets = importlib.import_module(package + '.QtWidgets')
    after_import = time.perf_counter_ns()
    sys.path.insert(0, str(root / 'source'))
    import convertall
    app = widgets.QApplication(['convertall-benchmark'])
    app.setStyle('Fusion')
    app.setFont(gui.QFont('DejaVu Sans', 10))
    convertall.setupTranslator(app)
    # Application modules conventionally read resource paths from __main__.
    main = sys.modules['__main__']
    for key in ('__version__', '__author__', 'dataFilePath', 'helpFilePath',
                'iconPath', 'lang'):
        setattr(main, key, getattr(convertall, key))
    import convertdlg
    after_app = time.perf_counter_ns()
    window = convertdlg.ConvertDlg()
    window.resize(1024, 640)
    window.show()
    app.processEvents()
    pixmap = window.grab()
    if pixmap.isNull():
        raise AssertionError('Main-window offscreen render failed')
    app.processEvents()
    ready = time.perf_counter_ns()
    import psutil
    rss = psutil.Process().memory_info().rss
    payload = {
        'gui_startup_ms': (ready - start) / 1e6,
        'binding_import_ms': (after_import - start) / 1e6,
        'app_and_modules_ms': (after_app - after_import) / 1e6,
        'window_and_render_ms': (ready - after_app) / 1e6,
        'rss_mib': rss / 1024 ** 2,
        'python': platform.python_version(),
        'pyqt': core.PYQT_VERSION_STR, 'qt_runtime': core.qVersion(),
        'qt_compiled': core.QT_VERSION_STR,
        'platform_plugin': app.platformName(),
        'window_pixels': [pixmap.width(), pixmap.height()],
        'unit_count': len(window.unitData),
    }
    return app, window, core, gui, widgets, payload


def benchmark_batches(action, count, batches=20, warmup=20):
    for index in range(warmup):
        action(index)
    values = []
    for batch in range(batches):
        start = time.perf_counter_ns()
        for index in range(count):
            action(index + batch * count)
        values.append((time.perf_counter_ns() - start) / count / 1e6)
    return summary(values)


def operations(app, window):
    import unitgroup
    queries = ('', 'm', 'mi', 'mile', 'k', 'kg', 'deg', 'p')

    def filtering(index):
        window.fromGroup.update(queries[index % len(queries)])
        window.unitListView.updateFiltering(window.fromUnitEdit)
        app.processEvents()

    source = unitgroup.UnitGroup(window.unitData, window.option)
    target = unitgroup.UnitGroup(window.unitData, window.option)
    source.update('mile/hr')
    target.update('km/hr')
    source.reduceGroup()
    target.reduceGroup()
    assert source.categoryMatch(target)

    def numeric(index):
        return source.convert(index % 100, target)

    window.fromGroup.update('mile/hr')
    window.toGroup.update('km/hr')
    window.fromNumEdit.unitUpdate()
    window.toNumEdit.unitUpdate()

    def gui_numeric(index):
        window.fromNumEdit.setText(str(index % 100))
        window.fromNumEdit.convert()
        app.processEvents()

    return {
        'filter_update_ms': benchmark_batches(filtering, 100),
        'engine_conversion_ms': benchmark_batches(numeric, 100000),
        'gui_conversion_ms': benchmark_batches(gui_numeric, 1000),
    }


def smoke(app, window, core, gui, widgets, binding, root):
    import bases
    import colorset
    import convertdlg
    import fontset
    import numedit
    import option
    import optiondefaults
    import unitdata
    import unitgroup
    package = 'PyQt5' if binding == 'qt5' else 'PyQt6'
    qtest = importlib.import_module(package + '.QtTest').QTest
    checks = []

    def check(name, condition=True):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    failures = []
    for datum in window.unitData.values():
        group = unitgroup.UnitGroup(window.unitData, window.option)
        group.replaceCurrent(datum)
        try:
            if not group.groupValid():
                raise AssertionError('Invalid unit group')
            group.reduceGroup()
        except Exception as error:
            failures.append({'name': datum.name, 'error': repr(error)})
    check('No NEW failing unit definitions',
          {f['name'] for f in failures} == BAD_DEFINITIONS)
    for number, source, target, expected in CONVERSIONS:
        left = unitgroup.UnitGroup(window.unitData, window.option)
        right = unitgroup.UnitGroup(window.unitData, window.option)
        left.update(source)
        right.update(target)
        left.reduceGroup()
        right.reduceGroup()
        actual = left.convert(number, right)
        check('Conversion %s %s -> %s' % (number, source, target),
              left.groupValid() and right.groupValid() and left.categoryMatch(right)
              and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10))

    validator = numedit.FloatExprValidator(window)
    check('Arithmetic number validator',
          validator.validate('1+2*3', 0)[0] == gui.QValidator.State.Acceptable)
    check('Invalid number validator',
          validator.validate('hello', 0)[0] == gui.QValidator.State.Invalid)
    window.fromGroup.update('mile/hr')
    window.toGroup.update('km/hr')
    window.fromNumEdit.unitUpdate()
    window.toNumEdit.unitUpdate()
    window.fromNumEdit.setText('1+2*3')
    window.fromNumEdit.convert()
    check('Bidirectional GUI number conversion',
          math.isclose(float(window.toNumEdit.text()), 11.265408, rel_tol=1e-8))
    window.toNumEdit.setText('16.09344')
    window.toNumEdit.convert()
    check('Reverse GUI number conversion',
          math.isclose(float(window.fromNumEdit.text()), 10, rel_tol=1e-8))

    window.fromUnitEdit.setFocus()
    app.processEvents()
    window.fromGroup.update('mi')
    window.unitListView.updateFiltering(window.fromUnitEdit)
    check('Unit list filtering', 0 < window.unitListView.topLevelItemCount()
          < len(window.unitData))
    qtest.keyClick(window.fromUnitEdit, core.Qt.Key.Key_Down)
    qtest.keyClick(window.fromUnitEdit, core.Qt.Key.Key_Up)
    qtest.keyClick(window.fromUnitEdit, core.Qt.Key.Key_Return)
    check('Keyboard unit selection', window.unitListView.currentItem() is not None)
    window.unitListView.resetFiltering()
    check('Filter reset', window.unitListView.topLevelItemCount() == len(window.unitData))
    window.unitListView.header().setSortIndicator(1, core.Qt.SortOrder.DescendingOrder)
    window.unitListView.changeSort()
    check('Column sorting', window.unitListView.topLevelItemCount() == len(window.unitData))

    def modal(method, accept=True, edit=None):
        fired = []
        def finish():
            dialog = widgets.QApplication.activeModalWidget()
            if dialog is None:
                raise AssertionError('Expected a modal dialog')
            if edit is not None:
                edit(dialog)
            fired.append(True)
            dialog.accept() if accept else dialog.reject()
        core.QTimer.singleShot(0, finish)
        method()
        check('Modal dialog completed: ' + method.__name__, bool(fired))

    modal(window.changeOptions)
    modal(window.showColorDlg,
          edit=lambda dialog: window.colorSet.themeControl.setCurrentIndex(1))
    check('Dark theme applied',
          app.palette().color(gui.QPalette.ColorRole.Window).name() == '#353535')
    modal(window.showColorDlg, accept=False)
    modal(window.showFontDlg)
    font_dialog = fontset.CustomFontDialog(window.sysFont, None, window)
    check('Font families populated', font_dialog.familyList.count() > 0)
    font_dialog.defaultCheck.setChecked(False)
    font_dialog.setFontSelectAvail()
    check('Custom font can be selected', font_dialog.resultingFont() is not None)
    font_dialog.close()

    window.showBases()
    app.processEvents()
    decimal = window.basesDialog.editors[0]
    decimal.setFocus()
    app.processEvents()
    qtest.keyClicks(decimal, '255')
    check('Base GUI decimal -> hexadecimal',
          window.basesDialog.editors[1].text().lower() == 'ff')
    check('Base GUI decimal -> binary',
          window.basesDialog.editors[3].text() == '11111111')
    modal(window.basesDialog.changeBitSettings)
    check('Twos complement base calculation', bases.baseNum('ff', 16, 8, True) == -1)
    window.basesDialog.close()
    window.showFractions()
    window.fractionDialog.exprEdit.setText('0.125')
    window.fractionDialog.calcFractions()
    results = [window.fractionDialog.resultView.topLevelItem(i).text(0)
               for i in range(window.fractionDialog.resultView.topLevelItemCount())]
    check('Fraction GUI 0.125 -> 1/8', '1/8' in results)
    window.fractionDialog.powerTwoCtrl.setChecked(True)
    window.fractionDialog.calcFractions()
    check('Power-of-two fraction filter',
          window.fractionDialog.resultView.topLevelItemCount() > 0)
    window.fractionDialog.close()

    window.help()
    app.processEvents()
    help_window = window.helpView
    check('HTML help loaded', 'ConvertAll' in help_window.textView.toPlainText())
    help_window.findEdit.setText('ConvertAll')
    help_window.findTextChanged('ConvertAll')
    help_window.findNext()
    help_window.findPrevious()
    url = core.QUrl('https://example.invalid/')
    if binding == 'qt5':
        help_window.textView.highlighted[str].emit(url.toString())
    else:
        help_window.textView.highlighted.emit(url)
    check('Help link hover signal', help_window.statusBar().currentMessage() == url.toString())
    help_window.close()
    tip = convertdlg.TipDialog(window.option, window)
    core.QTimer.singleShot(0, tip.accept)
    result = tip.exec() if binding == 'qt6' else tip.exec_()
    check('Startup-tip dialog', result == widgets.QDialog.DialogCode.Accepted)

    translations = []
    for language in ('ca', 'de', 'es', 'fr', 'ru', 'sv'):
        translator = core.QTranslator()
        loaded = translator.load(str(root / 'translations' / ('convertall_' + language + '.qm')))
        check('Existing application .qm loads: ' + language, loaded)
        translated = translator.translate('convertdlg', 'From Unit')
        check('Existing translation context matches: ' + language, bool(translated))
        translations.append({'language': language, 'from_unit': translated})

    locale_data = []
    previous_lang = unitdata.lang
    try:
        for language in ('ca', 'de', 'es', 'fr', 'ru', 'sv'):
            unitdata.lang = language
            data = unitdata.UnitData()
            count = data.readData()
            bad = []
            for datum in data.values():
                group = unitgroup.UnitGroup(data, window.option)
                group.replaceCurrent(datum)
                try:
                    group.reduceGroup()
                except Exception as error:
                    bad.append({'name': datum.name, 'error': repr(error)})
            locale_data.append({'language': language, 'unit_count': count,
                                'definition_failures': bad})
    finally:
        unitdata.lang = previous_lang

    before = window.option.path
    window.close()
    app.processEvents()
    check('Preference file saved', bool(before) and Path(before).is_file())
    return {
        'smoke_passed': True, 'check_count': len(checks), 'checks': checks,
        'all_unit_definitions_pass': not failures,
        'unit_definition_pass_count': len(window.unitData) - len(failures),
        'existing_unit_definition_failures': failures,
        'application_translations': translations,
        'localized_unit_data': locale_data,
    }


def worker(args):
    callback_errors = []
    def exception_hook(kind, value, tb):
        text = ''.join(traceback.format_exception(kind, value, tb))
        callback_errors.append(text)
        print(text, file=sys.stderr, flush=True)
    sys.excepthook = exception_hook
    root = args.app_root.resolve()
    app, window, core, gui, widgets, payload = prepare_app(root, args.binding)
    if args.worker == 'operations':
        payload['operations'] = operations(app, window)
    elif args.worker == 'smoke':
        payload['smoke'] = smoke(app, window, core, gui, widgets, args.binding, root)
    if callback_errors:
        raise AssertionError('Exceptions in Qt callbacks: ' + '\n'.join(callback_errors))
    package = importlib.import_module('PyQt5' if args.binding == 'qt5' else 'PyQt6')
    folder = Path(package.__file__).parent
    payload['binding_directory_mib'] = sum(p.stat().st_size for p in folder.rglob('*')
                                          if p.is_file() and '__pycache__' not in p.parts) / 1024 ** 2
    # Preserve Qt object ownership until the result has been printed.
    print(PREFIX + json.dumps(payload, ensure_ascii=False), flush=True)
    app.quit()


def driver(args):
    script = Path(__file__).resolve()
    configurations = {
        # Do not resolve the venv's python symlink: that would bypass the venv.
        'qt5': (Path(os.path.abspath(args.python_qt5)), args.qt5_root.resolve()),
        'qt6': (Path(os.path.abspath(args.python_qt6)), args.qt6_root.resolve()),
    }
    samples = {'qt5': [], 'qt6': []}
    result = {
        'schema': 1,
        'method': {
            'date_utc': datetime.now(timezone.utc).date().isoformat(),
            'runs_per_binding': args.runs,
            'locale': 'C.UTF-8, LC_MESSAGES=C (English application data)',
            'order': 'alternating Qt5/Qt6, reversed every second pair',
            'display': 'offscreen', 'style': 'Fusion', 'font': 'DejaVu Sans 10',
            'startup': 'imports + application + main window + first grab; Python bootstrap excluded',
            'caches': 'warm OS caches; no privileged cache flush',
            'operations': '20 batches after warm-up, GUI methods followed by processEvents',
        },
        'host': {'platform': platform.platform(), 'machine': platform.machine(),
                 'driver_python': platform.python_version(), 'cpu_count': os.cpu_count()},
        'results': {},
    }

    def execute(binding, mode, warmup=False):
        python, root = configurations[binding]
        with tempfile.TemporaryDirectory(prefix='convertall-qt-bench-') as folder:
            home = Path(folder)
            # Both Unix and Windows preference lookup paths are isolated.
            (home / 'bellz' / 'convertall').mkdir(parents=True)
            config = 'ShowStartupTip no\nLoadLastUnit no\nRemenberDlgPos no\nColorTheme system\n'
            (home / '.convertall').write_text(config, encoding='utf-8')
            (home / 'bellz' / 'convertall' / 'convertall.ini').write_text(config, encoding='utf-8')
            runtime = home / 'runtime'
            runtime.mkdir(mode=0o700)
            env = dict(os.environ, HOME=folder, APPDATA=folder,
                       XDG_RUNTIME_DIR=str(runtime), QT_QPA_PLATFORM='offscreen',
                       QT_SCALE_FACTOR='1', LANG='C', LC_ALL='C', LC_MESSAGES='C',
                       PYTHONHASHSEED='0')
            command = [str(python), str(script), '--worker', mode,
                       '--app-root', str(root), '--binding', binding]
            completed = subprocess.run(command, env=env, cwd=root, text=True,
                                       capture_output=True, timeout=120)
            if completed.returncode:
                raise RuntimeError('%s %s failed (%s):\n%s\n%s' %
                                   (binding, mode, completed.returncode,
                                    completed.stdout, completed.stderr))
            lines = [line[len(PREFIX):] for line in completed.stdout.splitlines()
                     if line.startswith(PREFIX)]
            if len(lines) != 1:
                raise RuntimeError('Missing/duplicate benchmark result: ' + completed.stdout)
            payload = json.loads(lines[0])
            if not warmup and completed.stderr.strip():
                payload['stderr'] = completed.stderr.strip()
            return payload

    for binding in configurations:
        execute(binding, 'startup', warmup=True)
    for index in range(args.runs):
        order = ('qt5', 'qt6') if index % 2 == 0 else ('qt6', 'qt5')
        for binding in order:
            samples[binding].append(execute(binding, 'startup'))
        print('Startup pair %d/%d' % (index + 1, args.runs), flush=True)
    for binding in configurations:
        metric_names = ('gui_startup_ms', 'binding_import_ms', 'app_and_modules_ms',
                        'window_and_render_ms', 'rss_mib')
        result['results'][binding] = {
            'startup': {name: summary([sample[name] for sample in samples[binding]])
                        for name in metric_names},
            'environment': {key: samples[binding][0][key] for key in
                            ('python', 'pyqt', 'qt_runtime', 'qt_compiled', 'platform_plugin',
                             'window_pixels', 'unit_count', 'binding_directory_mib')},
            'startup_runs': samples[binding],
            'operations': execute(binding, 'operations')['operations'],
            'smoke': execute(binding, 'smoke')['smoke'],
        }
    for binding, (python, root) in configurations.items():
        engine = ('unitatom.py', 'unitdata.py', 'unitgroup.py', 'cmdline.py',
                  'option.py', 'optiondefaults.py', 'recentunits.py')
        result['results'][binding]['engine_sha256'] = {
            name: hashlib.sha256((root / 'source' / name).read_bytes()).hexdigest()
            for name in engine}
    left = result['results']['qt5']['engine_sha256']
    right = result['results']['qt6']['engine_sha256']
    if left != right:
        raise AssertionError('Engine differs between benchmark configurations')
    for key in ('existing_unit_definition_failures', 'localized_unit_data'):
        if result['results']['qt5']['smoke'][key] != result['results']['qt6']['smoke'][key]:
            raise AssertionError('Unit-data validation differs between Qt5 and Qt6: ' + key)
    for binding, (_, root) in configurations.items():
        result['results'][binding]['data_sha256'] = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((root / 'data').glob('*.dat'))}
    if result['results']['qt5']['data_sha256'] != result['results']['qt6']['data_sha256']:
        raise AssertionError('Conversion data differs between benchmark configurations')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print('Results:', args.output)
    for binding in configurations:
        data = result['results'][binding]
        print(binding, 'startup median ms=', data['startup']['gui_startup_ms']['median'],
              'RSS median MiB=', data['startup']['rss_mib']['median'],
              'smoke checks=', data['smoke']['check_count'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-qt5', type=Path)
    parser.add_argument('--python-qt6', type=Path)
    parser.add_argument('--qt5-root', type=Path)
    parser.add_argument('--qt6-root', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--runs', type=int, default=30)
    parser.add_argument('--worker', choices=('startup', 'operations', 'smoke'), help=argparse.SUPPRESS)
    parser.add_argument('--app-root', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--binding', choices=('qt5', 'qt6'), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        if not args.app_root or not args.binding:
            parser.error('Workers need --app-root and --binding')
        worker(args)
    else:
        if not all((args.python_qt5, args.python_qt6, args.qt5_root, args.qt6_root, args.output)):
            parser.error('Driver needs both Python paths, both application roots and --output')
        if args.runs < 5:
            parser.error('--runs must be at least 5')
        driver(args)


if __name__ == '__main__':
    main()
