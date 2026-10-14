"""Real Qt6 signal/keyboard tests. Do not replace the conversion engine."""
from pathlib import Path

import pytest
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QFont, QValidator
from PyQt6.QtWidgets import (QApplication, QDialog, QLabel, QMenu, QMessageBox,
                             QSpinBox)

from helpers import ROOT
import bases
import convertdlg
import fontset
import numedit
import option
import optiondefaults
import optiondlg

pytestmark = pytest.mark.gui


def replace_number(edit, text, qtbot):
    edit.setFocus()
    qtbot.keyClick(edit, Qt.Key.Key_A, modifier=Qt.KeyboardModifier.ControlModifier)
    qtbot.keyClicks(edit, text)


def test_initial_window_and_widgets(window):
    assert window.windowTitle() == 'ConvertAll'
    assert window.unitListView.topLevelItemCount() == 626
    assert not window.fromNumEdit.isEnabled()
    assert not window.toNumEdit.isEnabled()
    assert window.icons.pathList
    assert not window.icons['convertall_med'].isNull()
    assert window.fromNumEdit.status.text() == 'Set units'


@pytest.mark.parametrize('source,target,value,expected', [
    ('in', 'cm', '2', 5.08), ('C', 'F', '0', 32),
    ('m/s', 'km/hr', '10', 36), ('in^2', 'cm^2', '2', 12.9032),
])
def test_keyboard_conversion_signals(enter_units, qtbot, source, target, value, expected):
    widget = enter_units(source, target)
    assert widget.fromNumEdit.isEnabled() and widget.toNumEdit.isEnabled()
    with qtbot.waitSignal(widget.fromNumEdit.convertNum, timeout=1000):
        replace_number(widget.fromNumEdit, value, qtbot)
    assert float(widget.toNumEdit.text()) == pytest.approx(expected)
    assert widget.fromNumEdit.status.text() == 'Converting...'
    assert source.replace(' ', '') in [u.replace(' ', '') for u in widget.recentUnits]


def test_bidirectional_conversion_and_expression(enter_units, qtbot):
    widget = enter_units('in', 'cm')
    replace_number(widget.toNumEdit, '5.08', qtbot)
    assert float(widget.fromNumEdit.text()) == pytest.approx(2)
    replace_number(widget.fromNumEdit, '(2+3)*4', qtbot)
    assert float(widget.toNumEdit.text()) == pytest.approx(50.8)
    replace_number(widget.fromNumEdit, '1/0', qtbot)
    assert not widget.toNumEdit.isEnabled()
    replace_number(widget.fromNumEdit, '2', qtbot)
    assert widget.toNumEdit.isEnabled()


@pytest.mark.parametrize('source,target', [('m', 's'), ('C*m', 'K*m'), ('nonsense', 'cm')])
def test_invalid_and_incompatible_input_disables_numbers(enter_units, source, target):
    widget = enter_units(source, target)
    assert not widget.fromNumEdit.isEnabled()
    assert not widget.toNumEdit.isEnabled()
    assert widget.fromNumEdit.status.text() != 'Converting...'


def test_filter_keyboard_completion_and_operator_buttons(window, qtbot):
    edit = window.fromUnitEdit
    edit.setFocus()
    qtbot.keyClicks(edit, 'milli')
    assert 0 < window.unitListView.topLevelItemCount() < 626
    for key in [Qt.Key.Key_Down, Qt.Key.Key_Up, Qt.Key.Key_PageDown, Qt.Key.Key_PageUp]:
        qtbot.keyClick(edit, key)
    qtbot.keyClick(edit, Qt.Key.Key_Return)
    assert window.fromGroup.groupValid()
    qtbot.mouseClick(window.textButtons[0], Qt.MouseButton.LeftButton)
    assert window.fromGroup.currentUnit().exp == 2
    qtbot.mouseClick(window.textButtons[1], Qt.MouseButton.LeftButton)
    assert window.fromGroup.currentUnit().exp == 3
    qtbot.mouseClick(window.textButtons[2], Qt.MouseButton.LeftButton)
    qtbot.keyClicks(edit, 's')
    assert len(window.fromGroup.flatUnitList()) == 2
    qtbot.mouseClick(window.clearButton, Qt.MouseButton.LeftButton)
    assert edit.text() == '' and not window.fromGroup.groupValid()
    qtbot.keyClick(edit, Qt.Key.Key_Tab)


def test_type_filter_and_sort(window, qtbot):
    action = QAction('length', window)
    window.startTypeFilter(action)
    assert window.unitListView.typeFilter == 'length'
    assert window.unitListView.topLevelItemCount() > 0
    assert all(window.unitListView.topLevelItem(i).unit.typeName == 'length'
               for i in range(window.unitListView.topLevelItemCount()))
    window.filterMenu()  # a second click clears the filter
    assert window.unitListView.topLevelItemCount() == 626
    for column in range(3):
        window.unitListView.header().setSortIndicator(column, Qt.SortOrder.DescendingOrder)
        window.unitListView.changeSort()
        texts = [window.unitListView.topLevelItem(i).text(column).lower()
                 for i in range(window.unitListView.topLevelItemCount())]
        assert texts == sorted(texts, reverse=True)


def test_recent_menu_inserts_unit_and_clear_filter_menu(window, enter_units, qtbot, monkeypatch):
    enter_units('in', 'cm')
    window.fromUnitEdit.setFocus()
    def choose(menu, *args):
        action = menu.actions()[0]
        menu.triggered.emit(action)
        return action
    monkeypatch.setattr(QMenu, 'exec', choose)
    qtbot.mouseClick(window.recentButton, Qt.MouseButton.LeftButton)
    assert window.fromGroup.groupValid()
    qtbot.mouseClick(window.filterButton, Qt.MouseButton.LeftButton)
    assert window.unitListView.typeFilter
    qtbot.mouseClick(window.filterButton, Qt.MouseButton.LeftButton)
    assert not window.unitListView.typeFilter


@pytest.mark.parametrize('accept', [True, False])
def test_preferences_accept_cancel_and_persistence(window, qtbot, accept):
    previous = window.option.intData('DecimalPlaces')
    def answer():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, optiondlg.OptionDlg)
        dialog.findChildren(QSpinBox)[0].setValue(5)
        dialog.accept() if accept else dialog.reject()
    QTimer.singleShot(0, answer)
    window.changeOptions()
    assert window.option.intData('DecimalPlaces') == (5 if accept else previous)
    reread = option.Option('convertall')
    reread.loadAll(optiondefaults.defaultList)
    assert reread.intData('DecimalPlaces') == (5 if accept else previous)


def test_about_reports_correct_version(window, monkeypatch):
    messages = []
    monkeypatch.setattr(QMessageBox, 'about', lambda *args: messages.append(args[2]))
    window.about()
    assert '0.9.3' in messages[0] and 'Doug Bell' in messages[0]


def test_close_saves_geometry_history_and_reopens(window, enter_units, qtbot):
    enter_units('in', 'cm')
    window.resize(740, 530)
    window.option.changeData('LoadLastUnit', 'yes', True)
    path = Path(window.option.path)
    window.close()
    assert path.exists()
    reopened = convertdlg.ConvertDlg()
    qtbot.addWidget(reopened)
    reopened.show()
    assert reopened.fromGroup.unitString() == 'in'
    assert reopened.toGroup.unitString() == 'cm'
    assert float(reopened.toNumEdit.text()) == pytest.approx(2.54)
    assert reopened.option.intData('MainDlgXSize') > 0
    assert reopened.option.intData('MainDlgYSize') > 0


def test_startup_tip_can_be_disabled(options, qtbot):
    tip = convertdlg.TipDialog(options)
    qtbot.addWidget(tip)
    tip.showCheck.setChecked(False)
    tip.accept()
    assert not options.boolData('ShowStartupTip')


def test_auxiliary_dialogs_open_and_are_reused(window, qtbot):
    window.showBases()
    window.showFractions()
    qtbot.addWidget(window.basesDialog)
    qtbot.addWidget(window.fractionDialog)
    assert window.basesDialog.isVisible()
    assert window.fractionDialog.isVisible()
    old = window.basesDialog
    window.showBases()
    assert window.basesDialog is old


def test_fonts_system_custom_and_serialization(qapp, qtbot):
    sysfont = QFont(qapp.font())
    dialog = fontset.CustomFontDialog(sysfont)
    qtbot.addWidget(dialog)
    assert dialog.resultingFont() is None
    dialog.defaultCheck.setChecked(False)
    dialog.setFontSelectAvail()
    assert dialog.familyList.count() > 0
    font = dialog.resultingFont()
    assert font is not None
    restored = QFont()
    assert restored.fromString(font.toString())
    assert restored.family() == font.family()
    assert restored.pointSize() == font.pointSize()
    dialog2 = fontset.CustomFontDialog(sysfont, font)
    qtbot.addWidget(dialog2)
    assert not dialog2.defaultCheck.isChecked()


@pytest.mark.parametrize('text,valid', [('1e-3', True), ('(2+3)/4', True),
                                       ('__import__(1)', False), ('abc', False)])
def test_number_expression_validator(qapp, text, valid):
    validator = numedit.FloatExprValidator(None)
    state, _, _ = validator.validate(text, len(text))
    assert (state == QValidator.State.Acceptable) is valid


def test_generic_option_controls_apply_only_on_accept(options, qtbot):
    options.addData('TestNumber', '1.0')
    options.addData('TestString', 'old')
    dialog = optiondlg.OptionDlg(options)
    qtbot.addWidget(dialog)
    dialog.startGroupBox('test')
    boolean = optiondlg.OptionDlgBool(dialog, 'ShowOpButtons', 'show')
    integer = optiondlg.OptionDlgInt(dialog, 'DecimalPlaces', 'places', 0, 12)
    real = optiondlg.OptionDlgDbl(dialog, 'TestNumber', 'number', 0, 10)
    text = optiondlg.OptionDlgStr(dialog, 'TestString', 'string')
    dialog.endGroupBox()
    radio = optiondlg.OptionDlgRadio(dialog, 'Notation', 'notation',
                                     [('general', 'General'), ('fixed', 'Fixed')])
    dialog.startNewColumn()
    clicked = []
    push = optiondlg.OptionDlgPush(dialog, 'button', lambda: clicked.append(True))
    qtbot.mouseClick(push.control, Qt.MouseButton.LeftButton)
    assert clicked
    boolean.control.setChecked(False)
    integer.control.setValue(4)
    real.control.setText('2.5')
    text.control.setText('mètre')
    radio.control.button(1).setChecked(True)
    dialog.accept()
    assert not options.boolData('ShowOpButtons')
    assert options.intData('DecimalPlaces') == 4
    assert options.numData('TestNumber') == 2.5
    assert options.strData('TestString') == 'mètre'
    assert options.strData('Notation') == 'fixed'
    real.control.setText('bad')
    real.updateData()
    assert options.numData('TestNumber') == 2.5


def test_numeric_overflow_and_equation_error_do_not_escape_qt_slot(enter_units, qtbot, monkeypatch):
    warnings = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[2]))
    widget = enter_units('W', 'dBm')
    replace_number(widget.fromNumEdit, '-1', qtbot)
    assert warnings and not widget.toNumEdit.isEnabled()
    replace_number(widget.fromNumEdit, '1e999', qtbot)
    assert not widget.toNumEdit.isEnabled()
    widget = enter_units('mi^999', 'm^999')
    assert not widget.fromNumEdit.isEnabled()
    assert not widget.toNumEdit.isEnabled()


def test_bases_dialog_keyboard_and_bit_settings(window, qtbot, monkeypatch):
    window.showBases()
    dialog = window.basesDialog
    qtbot.addWidget(dialog)
    replace_number(dialog.editors[0], '42', qtbot)
    assert dialog.editors[1].text() == '2a'
    assert dialog.editors[2].text() == '52'
    assert dialog.editors[3].text() == '101010'
    def answer():
        popup = QApplication.activeModalWidget()
        popup.findChildren(QSpinBox)[0].setValue(8)
        from PyQt6.QtWidgets import QCheckBox
        popup.findChildren(QCheckBox)[0].setChecked(True)
        popup.accept()
    QTimer.singleShot(0, answer)
    dialog.changeBitSettings()
    assert dialog.numBits == 8 and dialog.twosComplement
    replace_number(dialog.editors[0], '-1', qtbot)
    assert dialog.editors[1].text() == 'ff'
    warnings = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[2]))
    replace_number(dialog.editors[0], '256', qtbot)
    assert warnings


def test_fraction_dialog_expression_results_and_errors(window, qtbot, monkeypatch):
    window.showFractions()
    dialog = window.fractionDialog
    qtbot.addWidget(dialog)
    dialog.exprEdit.setText('3/4')
    dialog.calcFractions()
    assert any(dialog.resultView.topLevelItem(i).text(0) == '3/4'
               for i in range(dialog.resultView.topLevelItemCount()))
    dialog.powerTwoCtrl.setChecked(True)
    dialog.exprEdit.setText('1/3')
    dialog.calcFractions()
    assert dialog.resultView.topLevelItemCount() > 1
    warnings = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[2]))
    for text in ('1/0', '1e999'):
        dialog.exprEdit.setText(text)
        dialog.calcFractions()
    assert len(warnings) == 2


@pytest.mark.parametrize('theme,accept', [('dark', True), ('system', True),
                                        ('custom', True), ('dark', False)])
def test_color_dialog_themes_accept_cancel_and_swatch(window, qapp, qtbot, monkeypatch, theme, accept):
    from PyQt6.QtGui import QColor, QPalette
    from PyQt6.QtWidgets import QColorDialog
    import colorset
    original = qapp.palette()
    before = window.option.strData('ColorTheme')
    def answer():
        popup = QApplication.activeModalWidget()
        control = window.colorSet.themeControl
        control.setCurrentIndex(control.findData(colorset.ThemeSetting[theme]))
        if theme == 'custom':
            monkeypatch.setattr(QColorDialog, 'getColor', lambda *args: QColor('#123456'))
            qtbot.mouseClick(window.colorSet.colors[0].swatch, Qt.MouseButton.LeftButton)
        popup.accept() if accept else popup.reject()
    try:
        QTimer.singleShot(0, answer)
        window.showColorDlg()
        assert window.option.strData('ColorTheme') == (theme if accept else before)
        if theme == 'dark' and accept:
            assert qapp.palette().color(QPalette.ColorRole.Window).name() == '#353535'
        if theme == 'custom':
            assert window.option.strData('WindowColor') == '123456'
    finally:
        qapp.setPalette(original)


@pytest.mark.parametrize('custom', [False, True])
def test_main_window_font_dialog_updates_preference(window, qapp, custom):
    original = QFont(qapp.font())
    def answer():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, fontset.CustomFontDialog)
        dialog.defaultCheck.setChecked(not custom)
        dialog.setFontSelectAvail()
        dialog.accept()
    try:
        QTimer.singleShot(0, answer)
        window.showFontDlg()
        assert bool(window.option.strData('GuiFont', True)) is custom
    finally:
        qapp.setFont(original)
