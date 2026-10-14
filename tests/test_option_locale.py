"""Numeric preference validation must agree with repr()/float(), not OS locale."""
import pytest
from PyQt6.QtCore import QLocale
from PyQt6.QtGui import QValidator

import optiondlg

pytestmark = pytest.mark.gui


@pytest.mark.parametrize('language', ['C', 'fr_FR', 'de_DE'])
@pytest.mark.parametrize('text', ['2.5', '1.25e-3', '1000.125'])
def test_double_preference_accepts_python_numbers_in_any_default_locale(
        language, text, options, qtbot):
    previous = QLocale()
    try:
        QLocale.setDefault(QLocale(language))
        options.addData('TestNumber', '1.0')
        dialog = optiondlg.OptionDlg(options)
        qtbot.addWidget(dialog)
        item = optiondlg.OptionDlgDbl(dialog, 'TestNumber', 'number', 0, 10000)
        assert item.control.text() == '1.0'
        validator = item.control.validator()
        assert validator.locale().name() == 'C'
        assert validator.validate(text, len(text))[0] == QValidator.State.Acceptable
        item.control.setText(text)
        dialog.accept()
        assert options.numData('TestNumber') == pytest.approx(float(text))
        # The fix is scoped to this numeric field, not the whole application.
        assert QLocale().name() == QLocale(language).name()
    finally:
        QLocale.setDefault(previous)


@pytest.mark.parametrize('language', ['C', 'fr_FR', 'de_DE'])
@pytest.mark.parametrize('text', ['2,5', '1,000', '1 000', '1\u202f000', 'bad', ''])
def test_double_preference_rejects_localized_or_grouped_numbers_without_crashing(
        language, text, options, qtbot):
    previous = QLocale()
    try:
        QLocale.setDefault(QLocale(language))
        options.addData('TestNumber', '1.0')
        dialog = optiondlg.OptionDlg(options)
        qtbot.addWidget(dialog)
        item = optiondlg.OptionDlgDbl(dialog, 'TestNumber', 'number', 0, 10000)
        assert item.control.validator().validate(text, len(text))[0] != QValidator.State.Acceptable
        item.control.setText(text)
        dialog.accept()  # no ValueError from float(), and no silent new value
        assert options.numData('TestNumber') == 1.0
    finally:
        QLocale.setDefault(previous)
