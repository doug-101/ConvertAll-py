# Historical qmake manifest only. Qt6 pylupdate6 cannot extract `_()` contexts.
# Use: python tools/update_translations.py --update --compile --lrelease PATH
SOURCES = bases.py colorset.py cmdline.py convertall.py convertdlg.py fontset.py \
          helpview.py icondict.py numedit.py optiondefaults.py optiondlg.py \
          option.py recentunits.py unitatom.py unitdata.py unitedit.py \
          unitgroup.py unitlistview.py

TRANSLATIONS = ../translations/convertall_ca.ts \
               ../translations/convertall_de.ts \
               ../translations/convertall_es.ts \
               ../translations/convertall_fr.ts \
               ../translations/convertall_ru.ts \
               ../translations/convertall_sv.ts
