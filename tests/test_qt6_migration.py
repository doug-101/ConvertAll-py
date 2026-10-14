"""Qt6 API, resources and backwards-readable Qt5 preference regressions."""
import ast
from pathlib import Path

import pytest
from PyQt6.QtCore import QByteArray, QLibraryInfo, QUrl
from PyQt6.QtGui import QAction, QFont, QPalette

from helpers import ROOT
import colorset
import convertdlg
import helpview

pytestmark = pytest.mark.gui


@pytest.mark.parametrize('filename', ['bases.py', 'colorset.py', 'convertall.py',
                                     'convertdlg.py', 'fontset.py', 'helpview.py',
                                     'icondict.py', 'numedit.py', 'optiondlg.py',
                                     'unitedit.py', 'unitlistview.py'])
def test_production_modules_use_only_modern_qt6_apis(filename):
    text = (ROOT / 'source' / filename).read_text(encoding='utf-8')
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or '').startswith(('PyQt5', 'PySide'))
            assert not any(alias.name == 'qApp' for alias in node.names)
            if node.module == 'PyQt6.QtWidgets':
                assert not any(alias.name == 'QAction' for alias in node.names)
        if isinstance(node, ast.Attribute):
            assert node.attr != 'exec_'
            if isinstance(node.value, ast.Name) and node.value.id == 'Qt':
                assert not node.attr.startswith('Key_')
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != 'QFontDatabase'  # Qt6 uses its static methods


def test_the_comments_column_follows_the_list_width():
    """Regression: the comments column was sized to its content, so it overflowed a
    narrow dialog or left the list half empty instead of adapting to the width.

    Two Qt details make this worth pinning in the source:
      * with stretchLastSection(False), the resize mode of the last section applies;
        with True, the property would override it and freeze the column;
      * a Stretch section cannot be resized, so it must stay out of the
        resizeColumnToContents loop.
    """
    text = (ROOT / 'source' / 'unitlistview.py').read_text(encoding='utf-8')
    tree = ast.parse(text)
    stretch_modes, sized_loops, stretch_last = set(), [], None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == 'setSectionResizeMode' and len(node.args) == 2:
                section, mode = node.args
                if (isinstance(section, ast.Constant)
                        and isinstance(mode, ast.Attribute) and mode.attr == 'Stretch'):
                    stretch_modes.add(section.value)
            if (node.func.attr == 'setStretchLastSection' and node.args
                    and isinstance(node.args[0], ast.Constant)):
                stretch_last = node.args[0].value
        if not isinstance(node, ast.For):
            continue
        resizes = [child for statement in node.body for child in ast.walk(statement)
                   if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute)
                   and child.func.attr == 'resizeColumnToContents']
        if resizes:
            sized_loops.append(node.iter)
    assert 2 in stretch_modes, 'the comments column must stretch with the list width'
    assert stretch_last is False, ('stretchLastSection(True) overrides the last section '
                                   'mode, which would freeze the comments column width')
    assert sized_loops, ('measure the sized columns in a loop over an explicit list, '
                        'such as (0, 1)')
    for columns in sized_loops:
        try:
            measured = list(ast.literal_eval(columns))
        except ValueError:
            raise AssertionError('measure the columns from an explicit list, such as (0, 1), '
                                 'so the stretching column stays out of it')
        assert 2 not in measured, 'the comments column must not be sized to its content'


def test_actions_palette_and_qt_runtime_translation_path(qapp):
    action = QAction('Qt6', qapp)
    assert action.text() == 'Qt6'
    assert Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)).is_dir()
    color = colorset.Color('Text-Disabled')
    assert color.group == QPalette.ColorGroup.Disabled
    assert color.role == QPalette.ColorRole.Text
    color.setFromPalette(qapp.palette())
    assert color.currentColor.isValid()


def test_qt5_serialized_font_is_still_readable(qapp):
    family = qapp.font().family()
    legacy = f'{family},10,-1,5,50,0,0,0,0,0'
    font = QFont()
    assert font.fromString(legacy)
    assert font.pointSize() == 10
    assert font.family() == family
    assert font.weight() == QFont.Weight.Normal


def test_new_geometry_state_is_persisted_alongside_legacy_keys(window, qtbot):
    window.resize(740, 530)
    window.close()
    state = window.option.strData('MainDlgGeometry', True)
    assert state and not QByteArray.fromHex(state.encode('ascii')).isEmpty()
    assert window.option.intData('MainDlgXSize') > 0
    reopened = convertdlg.ConvertDlg()
    qtbot.addWidget(reopened)
    assert reopened.option.strData('MainDlgGeometry', True) == state
    assert reopened.geometry().isValid()


@pytest.mark.parametrize('state', ['', 'not-hex', 'écran', 'deadbeef'])
def test_bad_geometry_uses_legacy_fallback_without_an_exception(window, state):
    window.option.changeData('MainDlgGeometry', state, False)
    for name, value in [('MainDlgXSize', '740'), ('MainDlgYSize', '530'),
                        ('MainDlgXPos', '99999'), ('MainDlgYPos', '99999')]:
        window.option.changeData(name, value, False)
    window.restoreWindowGeometry()
    assert window.geometry().isValid()
    assert any(s.availableGeometry().intersects(window.geometry())
               for s in window.screen().virtualSiblings())


def test_remember_geometry_disabled_leaves_current_geometry_unchanged(window):
    window.option.changeData('RemenberDlgPos', 'no', False)
    before = window.geometry()
    window.restoreWindowGeometry()
    assert window.geometry() == before


def test_help_local_url_preserves_unicode_spaces_and_hash(window, tmp_path, qtbot):
    path = tmp_path / 'manuel mètre # Qt6.html'
    path.write_text('<html><body>Qt6 local help</body></html>', encoding='utf-8')
    view = helpview.HelpView(str(path), 'Qt6 help', window.icons)
    qtbot.addWidget(view)
    assert Path(view.textView.source().toLocalFile()).resolve() == path.resolve()
    assert 'Qt6 local help' in view.textView.toPlainText()
    view.textView.highlighted.emit(QUrl('https://example.invalid/qt6'))
    assert view.statusBar().currentMessage() == 'https://example.invalid/qt6'


def test_negative_legacy_screen_coordinates_are_preserved(window, monkeypatch):
    from types import SimpleNamespace
    from PyQt6.QtCore import QRect
    from PyQt6.QtWidgets import QApplication
    screen = SimpleNamespace(availableGeometry=lambda: QRect(-1920, 0, 1920, 1080))
    monkeypatch.setattr(QApplication, 'screens', lambda: [screen])
    monkeypatch.setattr(QApplication, 'primaryScreen', lambda: screen)
    for name, value in [('MainDlgGeometry', ''), ('MainDlgXPos', '-1200'),
                        ('MainDlgYPos', '100'), ('MainDlgXSize', '740'),
                        ('MainDlgYSize', '530')]:
        window.option.changeData(name, value, False)
    window.restoreWindowGeometry()
    assert window.geometry().x() == -1200
    assert window.geometry().y() == 100


def test_empty_font_list_has_a_positive_qt6_size_hint(qapp, qtbot):
    import fontset
    widget = fontset.SmallListWidget()
    qtbot.addWidget(widget)
    assert widget.count() == 0
    assert widget.sizeHint().height() > 0


def test_zero_valued_active_palette_group_is_not_treated_as_absent(qapp):
    from PyQt6.QtGui import QColor
    palette = QPalette(qapp.palette())
    palette.setColor(QPalette.ColorGroup.Active, QPalette.ColorRole.Text, QColor('#123456'))
    palette.setColor(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Text, QColor('#abcdef'))
    palette.setCurrentColorGroup(QPalette.ColorGroup.Inactive)
    color = colorset.Color('Text-Active')
    color.setFromPalette(palette)
    assert color.currentColor.name() == '#123456'
    color.currentColor = QColor('#654321')
    color.updatePalette(palette)
    assert palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text).name() == '#654321'
    assert palette.color(QPalette.ColorGroup.Inactive, QPalette.ColorRole.Text).name() == '#abcdef'


@pytest.mark.parametrize('weight,legacy_weight', [
    (QFont.Weight.Thin, 0), (QFont.Weight.Light, 25), (QFont.Weight.Normal, 50),
    (QFont.Weight.DemiBold, 63), (QFont.Weight.Bold, 75), (QFont.Weight.Black, 87),
])
def test_font_is_saved_in_qt5_and_full_qt6_formats(qapp, options, weight, legacy_weight):
    import fontset
    font = QFont(qapp.font())
    font.setPointSizeF(12.5)
    font.setWeight(weight)
    fontset.storeFontOptions(options, font)
    legacy = options.strData('GuiFont', True)
    assert len(legacy.split(',')) in (10, 11)
    assert int(legacy.split(',')[4]) == legacy_weight
    assert options.strData('GuiFontQt6', True) == font.toString()
    assert options.strData('GuiFontQt6Legacy', True) == legacy
    restored = fontset.fontFromOptions(options)
    assert restored.pointSizeF() == 12.5
    assert restored.weight() == weight
    old_format = QFont()
    assert old_format.fromString(legacy)
    assert old_format.pointSizeF() == 12.5 and old_format.weight() == weight


def test_font_changed_later_in_qt5_wins_over_stale_qt6_state(qapp, options):
    import fontset
    old = QFont(qapp.font())
    old.setPointSize(12)
    fontset.storeFontOptions(options, old)
    changed = QFont(old)
    changed.setPointSize(18)
    options.changeData('GuiFont', fontset.legacyFontString(changed), True)
    assert fontset.fontFromOptions(options).pointSize() == 18
    fontset.storeFontOptions(options, None)
    assert fontset.fontFromOptions(options) is None
    for key in ('GuiFont', 'GuiFontQt6', 'GuiFontQt6Legacy'):
        assert options.strData(key, True) == ''


def test_invalid_qt6_font_state_uses_valid_legacy_font(qapp, options):
    import fontset
    font = QFont(qapp.font())
    font.setPointSize(15)
    fontset.storeFontOptions(options, font)
    options.changeData('GuiFontQt6', 'invalid,font,state', False)
    assert fontset.fontFromOptions(options).pointSize() == 15


@pytest.mark.parametrize('full_state', [False, True])
def test_main_window_restores_saved_font_on_startup(window, qapp, qtbot, full_state):
    import fontset
    original = QFont(qapp.font())
    font = QFont(original)
    font.setPointSize(15)
    font.setWeight(QFont.Weight.Bold)
    if full_state:
        fontset.storeFontOptions(window.option, font)
    else:
        window.option.changeData('GuiFont', fontset.legacyFontString(font), True)
    assert window.option.writeChanges()
    try:
        reopened = convertdlg.ConvertDlg()
        qtbot.addWidget(reopened)
        assert reopened.guiFont is not None
        assert reopened.guiFont.pointSize() == 15
        assert reopened.guiFont.weight() == QFont.Weight.Bold
        assert qapp.font().pointSize() == 15
    finally:
        qapp.setFont(original)
