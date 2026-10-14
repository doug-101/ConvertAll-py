#!/usr/bin/env bash
# ConvertAll Qt5: un lancement, un résumé, une archive de diagnostic.
# Aucun commit, tag, push, release, sudo ou serveur n'est lancé.
# Utilisation : bash test_all_qt5.sh [--no-build] [--no-install] [--python CHEMIN]
set -uo pipefail

usage() {
    cat <<'HELP'
Usage : bash test_all_qt5.sh [options]

Par défaut :
  1. crée/réutilise .venv/test-all-qt5 et installe les dépendances épinglées ;
  2. exécute toute la suite Qt5, y compris GUI offscreen et couverture ;
  3. construit et teste le bundle PyInstaller SI la suite source réussit ;
  4. produit SUMMARY.txt et une archive contenant uniquement les rapports/logs.

Options :
  --no-build          Plus rapide : tous les tests source, sans build natif.
  --no-install        Réutilise les dépendances existantes, sans venv/install.
  --python CHEMIN     Interpréteur Python 3.10–3.14 à utiliser.
                      Avec --no-install, c'est l'environnement testé.
  -h, --help          Affiche cette aide.

Exemples :
  bash test_all_qt5.sh
  bash test_all_qt5.sh --no-build
  bash test_all_qt5.sh --no-build --no-install --python .venv/test-all-qt5/bin/python

Linux/macOS/WSL : Bash. Windows : Git Bash avec un Python Windows.
Les bibliothèques Qt système doivent déjà être présentes. Le script ne les
installe pas automatiquement et ne mélange pas PyQt5 avec PyQt6/PySide.
Debian 12 / Python 3.11 : installer au besoin python3.11-venv (ensurepip),
libpython3.11 (build natif), libgl1, libegl1, libxkbcommon0, libdbus-1-3,
libxcb-xinerama0 et libxcb-cursor0. Un venv incomplet est réparé au prochain
lancement une fois ensurepip disponible, sans supprimer le répertoire.
Code de sortie : 0 = contrôles demandés réussis, 1 = échec, 2 = prérequis manquant.
HELP
}

DO_BUILD=1
DO_INSTALL=1
REQUESTED_PYTHON=''
while (($#)); do
    case "$1" in
        --no-build) DO_BUILD=0; shift ;;
        --no-install) DO_INSTALL=0; shift ;;
        --python)
            if (($# < 2)); then echo 'Il manque le chemin après --python.' >&2; exit 2; fi
            REQUESTED_PYTHON="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'Option inconnue : %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
done

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P) || exit 2
cd "$ROOT" || exit 2
if [[ -f "$ROOT/requirements-qt6.txt" ]]; then
    echo 'Ce checkout est Qt6. Utiliser : bash test_all_qt6.sh' >&2
    echo 'La baseline Qt5 validée est b10b8e7837e30a2ec9a957a9a2519e4ac0334db3.' >&2
    echo 'Exécuter le lanceur Qt5 depuis une archive de ce commit, dans un dossier séparé.' >&2
    exit 2
fi
# Résoudre avant de changer d'environnement, y compris un chemin relatif.
BASE_PYTHON=''
if [[ -n "$REQUESTED_PYTHON" ]]; then
    BASE_PYTHON=$(command -v "$REQUESTED_PYTHON" 2>/dev/null) || true
else
    for candidate in python3.11 python3 python; do
        BASE_PYTHON=$(command -v "$candidate" 2>/dev/null) || true
        [[ -n "$BASE_PYTHON" ]] && break
    done
fi

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
REPORT_DIR="$ROOT/build/qt5-diagnostics/$RUN_ID"
REPORT_ARCHIVE="$ROOT/build/qt5-diagnostics/qt5-results-$RUN_ID.tar.gz"
mkdir -p "$REPORT_DIR" || exit 2
STEPS="$REPORT_DIR/steps.tsv"
printf 'step\tstatus\texit_code\tseconds\tnote\n' > "$STEPS" || exit 2
FAILED=0
LAST_CODE=0
REPORT_PYTHON="$BASE_PYTHON"

# Le validateur écrit dans build/test-results : éviter deux lanceurs simultanés.
LOCK="$ROOT/build/.test-all-qt5.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
    printf 'Un autre lancement semble actif (verrou %s).\n' "$LOCK" >&2
    echo 'Si le précédent a été tué, vérifier qu’il est arrêté puis supprimer ce répertoire vide.' >&2
    exit 2
fi
cleanup() { rmdir "$LOCK" 2>/dev/null || true; }
trap cleanup EXIT
trap 'echo "Lancement interrompu ; logs partiels dans $REPORT_DIR" >&2; exit 130' INT TERM

record_skip() {
    printf '%s\tSKIP\t0\t0\t%s\n' "$1" "$2" >> "$STEPS"
    printf '\n[SKIP] %s : %s\n' "$1" "$2"
}

run_step() {
    local name="$1"; shift
    local start duration code
    local -a pipeline_status
    start=$(date +%s)
    printf '\n========== %s ==========\n' "$name"
    "$@" 2>&1 | tee "$REPORT_DIR/$name.log"
    pipeline_status=("${PIPESTATUS[@]}")
    code=${pipeline_status[0]}
    # Une erreur de collecte des logs est également un échec, jamais un PASS.
    if [[ "$code" -eq 0 && "${pipeline_status[1]}" -ne 0 ]]; then
        code=${pipeline_status[1]}
    fi
    duration=$(( $(date +%s) - start ))
    LAST_CODE=$code
    if [[ "$code" -eq 0 ]]; then
        printf '%s\tPASS\t0\t%s\t\n' "$name" "$duration" >> "$STEPS"
        printf '[PASS] %s (%ss)\n' "$name" "$duration"
    else
        FAILED=1
        printf '%s\tFAIL\t%s\t%s\tvoir %s.log\n' "$name" "$code" "$duration" "$name" >> "$STEPS"
        printf '[FAIL] %s : code %s (%ss)\n' "$name" "$code" "$duration"
    fi
    # Le pilote poursuit les diagnostics ; LAST_CODE garde le résultat réel.
    return 0
}

finish() {
    # Un prérequis peut avoir échoué avant l'exécution de pytest.
    if [[ -n "$REPORT_PYTHON" ]]; then
        "$REPORT_PYTHON" - "$REPORT_DIR" "$DO_BUILD" "$REPORT_ARCHIVE" "$FAILED" <<'PY'
import csv
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

folder = Path(sys.argv[1])
with (folder / 'steps.tsv').open(encoding='utf-8') as stream:
    steps = list(csv.DictReader(stream, delimiter='\t'))
failed = [step for step in steps if step['status'] == 'FAIL']
source_ok = any(s['step'] == '04-tests-source' and s['status'] == 'PASS' for s in steps)
bundle_ok = any(s['step'] == '06-tests-bundle' and s['status'] == 'PASS' for s in steps)
build_requested = sys.argv[2] == '1'
unsuccessful = failed or sys.argv[4] != '0' or not source_ok or (build_requested and not bundle_ok)
status = 'FAIL' if unsuccessful else ('PASS' if bundle_ok else 'PASS_SOURCE_SEULEMENT')
report = {'status': status, 'source_passed': source_ok, 'bundle_passed': bundle_ok,
          'build_requested': build_requested, 'steps': steps, 'errors': []}
lines = ['CONVERTALL — RÉSULTATS QT5', f'Résultat : {status}', '']
for step in steps:
    lines.append(f"{step['status']:4}  {step['step']}  code={step['exit_code']}  {step['seconds']}s")

try:
    environment = json.loads((folder / 'environment.json').read_text(encoding='utf-8'))
    report['environment'] = environment
    lines.extend(['', f"Python : {environment.get('python', '?')}",
                  f"OS : {environment.get('platform', '?')}",
                  f"Qt runtime : {environment.get('qt_runtime', '?')}",
                  f"Commit : {environment.get('commit') or 'sans .git'}",
                  f"Arbre modifié : {environment.get('working_tree_dirty')}"])
except (OSError, ValueError) as error:
    lines.append(f'Inventaire environnement indisponible : {error}')

try:
    root = ET.parse(folder / 'test-results/junit.xml').getroot()
    suites = [root] if root.tag == 'testsuite' else list(root.iter('testsuite'))
    counts = {key: sum(int(s.get(key, '0')) for s in suites)
              for key in ('tests', 'failures', 'errors', 'skipped')}
    report['pytest'] = counts
    lines.extend(['', 'Pytest : ' + ', '.join(f'{k}={v}' for k, v in counts.items())])
    for case in root.iter('testcase'):
        problem = case.find('failure')
        if problem is None:
            problem = case.find('error')
        if problem is not None and len(report['errors']) < 15:
            report['errors'].append({'test': case.get('name'),
                                     'message': problem.get('message', '')[:1500]})
except (OSError, ET.ParseError, ValueError):
    lines.append('Pas de rapport JUnit : consulter le premier stage en échec.')

try:
    totals = json.loads((folder / 'test-results/coverage.json').read_text(encoding='utf-8'))['totals']
    report['coverage'] = totals
    lines.append(f"Couverture instructions/branches combinée : {totals['percent_covered']:.2f}% (seuil 80%)")
except (OSError, ValueError, KeyError):
    pass
if report['errors']:
    lines.extend(['', 'Premiers échecs :'])
    for error in report['errors']:
        lines.append(f"- {error['test']} : {error['message']}")
if not bundle_ok:
    lines.extend(['', 'Le bundle natif n’a PAS été validé par ce lancement.'])
lines.extend(['', 'Les contrôles offscreen ne certifient pas DPI, GPU ou installateurs natifs.',
              'À transmettre : SUMMARY.txt et, si nécessaire, l’archive des logs.',
              f'Archive prévue : {sys.argv[3]}'])
(folder / 'summary.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
(folder / 'SUMMARY.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
PY
        if [[ $? -ne 0 ]]; then
            FAILED=1
            printf 'Résumé structuré indisponible. Consulter steps.tsv et les logs.\n' > "$REPORT_DIR/SUMMARY.txt"
        fi
    else
        printf 'Python introuvable. Installer Python 3.10–3.14 puis relancer.\n' > "$REPORT_DIR/SUMMARY.txt"
    fi
    if command -v tar >/dev/null 2>&1; then
        # Seulement les logs/rapports : aucun venv, bundle, source ou secret env.
        if ! tar -czf "$REPORT_ARCHIVE" -C "$REPORT_DIR" .; then
            FAILED=1
            echo 'Impossible de créer l’archive ; transmettre le dossier de rapports.' >&2
        fi
    else
        echo 'tar absent : transmettre SUMMARY.txt et les fichiers .log du dossier.' >&2
    fi
    printf '\n========== RÉSUMÉ À ME RENVOYER ==========\n'
    cat "$REPORT_DIR/SUMMARY.txt"
    printf '\nDossier : %s\nArchive : %s\n' "$REPORT_DIR" "$REPORT_ARCHIVE"
}

if [[ -z "$BASE_PYTHON" ]]; then
    FAILED=1
    printf '00-python\tFAIL\t2\t0\tPython introuvable\n' >> "$STEPS"
    finish
    exit 2
fi
run_step '00-python' "$BASE_PYTHON" -c 'import sys; print(sys.version); sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 14) else 2)'
if [[ "$LAST_CODE" -ne 0 ]]; then finish; exit 2; fi
if ! command -v git >/dev/null 2>&1; then
    FAILED=1
    printf '00-git\tFAIL\t2\t0\tGit requis pour les tests des archives\n' >> "$STEPS"
    finish
    exit 2
fi
for required in tools/validate_release.py tools/check_bundle.py requirements-test.txt requirements-build.txt source/convertall.spec; do
    if [[ ! -f "$ROOT/$required" ]]; then
        FAILED=1
        printf '00-fichiers\tFAIL\t2\t0\tFichier absent : %s\n' "$required" >> "$STEPS"
        finish
        exit 2
    fi
done

# Test uniquement dans ce processus ; aucune modification de la session appelante.
export QT_API=pyqt5
export QT_QPA_PLATFORM=offscreen
export LC_MESSAGES=C
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1
export PYTHONNOUSERSITE=1
unset PYTHONPATH QT_PLUGIN_PATH QT_QPA_PLATFORM_PLUGIN_PATH

VENV="$ROOT/.venv/test-all-qt5"
TEST_PYTHON="$BASE_PYTHON"
existing_venv_python() {
    if [[ -x "$VENV/bin/python" ]]; then
        printf '%s\n' "$VENV/bin/python"
    elif [[ -x "$VENV/Scripts/python.exe" ]]; then
        printf '%s\n' "$VENV/Scripts/python.exe"
    fi
}
prepare_venv() {
    local interpreter version code
    interpreter=$(existing_venv_python)
    # Un échec de ensurepip peut laisser bin/python présent, mais aucun pip.
    # La présence de l'exécutable seule ne prouve donc pas que le venv est prêt.
    if [[ -n "$interpreter" ]] && "$interpreter" -m pip --version >/dev/null 2>&1; then
        printf 'Venv dédié prêt : %s\n' "$VENV"
        return 0
    fi
    if [[ -n "$interpreter" ]]; then
        printf 'Venv incomplet détecté ; réparation sans supprimer le répertoire.\n'
    fi
    if ! "$BASE_PYTHON" -c 'import importlib.util, sys; sys.exit(0 if importlib.util.find_spec("ensurepip") else 2)'; then
        version=$("$BASE_PYTHON" -c 'import sys; print("{}.{}".format(*sys.version_info[:2]))')
        printf '\nERREUR : ensurepip est absent pour Python %s.\n' "$version" >&2
        printf 'Sur Debian/Ubuntu, exécuter vous-même :\n' >&2
        printf '  sudo apt-get update\n  sudo apt-get install python%s-venv\n' "$version" >&2
        printf 'Puis relancer ce script : il réparera le venv incomplet.\n' >&2
        return 2
    fi
    code=0
    # Refaire venv sur ce répertoire complète notamment le bootstrap de pip.
    # Pas de --clear / rm -rf : les autres fichiers ne sont pas supprimés.
    "$BASE_PYTHON" -m venv "$VENV" || code=$?
    if [[ "$code" -ne 0 ]]; then
        printf 'Création/réparation du venv en échec ; voir le message ci-dessus.\n' >&2
        return "$code"
    fi
    interpreter=$(existing_venv_python)
    if [[ -z "$interpreter" ]] || ! "$interpreter" -m pip --version; then
        printf 'ERREUR : le venv ne dispose toujours pas de pip.\n' >&2
        return 1
    fi
    return 0
}
READY=1
if [[ "$DO_INSTALL" -eq 1 ]]; then
    run_step '01-venv' prepare_venv
    [[ "$LAST_CODE" -eq 0 ]] || READY=0
    TEST_PYTHON=$(existing_venv_python)
    if [[ "$READY" -eq 1 && -n "$TEST_PYTHON" ]]; then
        dependencies=(-r "$ROOT/requirements-test.txt")
        if [[ "$DO_BUILD" -eq 1 ]]; then dependencies+=(-r "$ROOT/requirements-build.txt"); fi
        run_step '02-dependances' "$TEST_PYTHON" -m pip --disable-pip-version-check install "${dependencies[@]}"
        [[ "$LAST_CODE" -eq 0 ]] || READY=0
    else
        READY=0
        record_skip '02-dependances' 'création du venv en échec'
    fi
else
    if [[ -z "$REQUESTED_PYTHON" ]]; then
        candidate=$(existing_venv_python)
        [[ -z "$candidate" ]] || TEST_PYTHON="$candidate"
    fi
    record_skip '01-venv' '--no-install'
    record_skip '02-dependances' '--no-install'
fi

if [[ "$READY" -eq 1 && -n "$TEST_PYTHON" && -x "$TEST_PYTHON" ]]; then
    REPORT_PYTHON="$TEST_PYTHON"
    run_step '03-environnement' "$TEST_PYTHON" - "$REPORT_DIR/environment.json" "$ROOT" <<'PY'
from datetime import datetime, timezone
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

output, root = Path(sys.argv[1]), Path(sys.argv[2])
names = ('PyQt5', 'PyQt5-sip', 'PyQt5-Qt5', 'pytest', 'pytest-qt',
         'pytest-cov', 'coverage', 'PyInstaller', 'pyinstaller-hooks-contrib',
         'PyQt6', 'PySide6', 'PySide2')
packages = {}
for name in names:
    try:
        packages[name] = metadata.version(name)
    except metadata.PackageNotFoundError:
        packages[name] = None
report = {'utc': datetime.now(timezone.utc).isoformat(), 'python': sys.version,
          'executable': sys.executable, 'platform': platform.platform(),
          'machine': platform.machine(), 'packages': packages,
          'qt_platform': os.environ.get('QT_QPA_PLATFORM'),
          'runner_sha256': hashlib.sha256((root / 'test_all_qt5.sh').read_bytes()).hexdigest()}
try:
    from PyQt5.QtCore import PYQT_VERSION_STR, QLocale, qVersion
    qt_locale = QLocale()
    report.update(pyqt_binding=PYQT_VERSION_STR, qt_runtime=qVersion(),
                  qt_default_locale=qt_locale.name(),
                  qt_decimal_point=qt_locale.decimalPoint(),
                  qt_group_separator=qt_locale.groupSeparator())
except Exception as error:
    report['qt_import_error'] = str(error)
def git(*args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True,
                                   stderr=subprocess.DEVNULL).strip()
try:
    report.update(commit=git('rev-parse', 'HEAD'), branch=git('branch', '--show-current'),
                  working_tree_dirty=bool(git('status', '--porcelain')))
except (OSError, subprocess.CalledProcessError):
    report.update(commit=None, branch=None, working_tree_dirty=None)
output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
if report.get('qt_import_error'):
    print('ERREUR : import Qt5 impossible. Vérifier le venv et les dépendances système.')
    sys.exit(2)
if any(packages[name] for name in ('PyQt6', 'PySide6', 'PySide2')):
    print('ERREUR : bindings Qt mélangés. Relancer sans --no-install dans le venv dédié.')
    sys.exit(2)
PY
    [[ "$LAST_CODE" -eq 0 ]] || READY=0
else
    READY=0
    record_skip '03-environnement' 'venv ou installation des dépendances non prêt'
fi

SOURCE_OK=0
if [[ "$READY" -eq 1 ]]; then
    # Ne pas joindre les vieux résultats d'un lancement précédent.
    mkdir -p "$ROOT/build/test-results"
    for name in junit.xml coverage.xml coverage.json validation.json; do
        if ! rm -f "$ROOT/build/test-results/$name"; then READY=0; FAILED=1; fi
    done
    if [[ "$READY" -eq 1 ]]; then
        run_step '04-tests-source' "$TEST_PYTHON" "$ROOT/tools/validate_release.py"
        [[ "$LAST_CODE" -ne 0 ]] || SOURCE_OK=1
        mkdir -p "$REPORT_DIR/test-results"
        for name in junit.xml coverage.xml coverage.json validation.json; do
            if [[ -f "$ROOT/build/test-results/$name" ]]; then
                cp "$ROOT/build/test-results/$name" "$REPORT_DIR/test-results/$name" || FAILED=1
            fi
        done
    fi
else
    record_skip '04-tests-source' 'prérequis ou environnement en échec'
fi

if [[ "$DO_BUILD" -eq 1 && "$SOURCE_OK" -eq 1 ]]; then
    # Le gros bundle reste à part et n'entre jamais dans l'archive de diagnostic.
    NATIVE="$ROOT/build/qt5-native/$RUN_ID"
    run_step '05-build-native' "$TEST_PYTHON" -m PyInstaller --noconfirm --clean \
        --distpath "$NATIVE/dist" --workpath "$NATIVE/work" "$ROOT/source/convertall.spec"
    if [[ "$LAST_CODE" -eq 0 ]]; then
        run_step '06-tests-bundle' "$TEST_PYTHON" "$ROOT/tools/check_bundle.py" "$NATIVE/dist/convertall"
    else
        record_skip '06-tests-bundle' 'build natif en échec ; consulter 05-build-native.log'
    fi
else
    if [[ "$DO_BUILD" -eq 0 ]]; then
        reason='--no-build : validation source uniquement'
    else
        reason='suite source non validée ; ne pas perdre du temps à construire'
    fi
    record_skip '05-build-native' "$reason"
    record_skip '06-tests-bundle' "$reason"
fi

finish
if [[ "$READY" -ne 1 ]]; then exit 2; fi
if [[ "$FAILED" -ne 0 || "$SOURCE_OK" -ne 1 ]]; then exit 1; fi
exit 0
