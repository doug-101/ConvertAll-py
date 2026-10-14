#!/usr/bin/env bash
# ConvertAll Qt6 : lance l'application Python (interface graphique par défaut,
# ligne de commande dès qu'un argument lui est transmis).
# Aucun commit, tag, push, sudo ni test n'est lancé. Les bibliothèques Qt
# système et un serveur graphique restent nécessaires côté machine.
# Utilisation : bash run_qt6.sh [options] [arguments...]
set -uo pipefail

usage() {
    cat <<'HELP'
Usage : bash run_qt6.sh [options] [arguments...]

Par défaut :
  1. crée/réutilise le venv dédié .venv/qt6 (sans toucher à .venv/test-all-qt6) ;
  2. installe les dépendances épinglées de requirements-qt6.txt si nécessaire ;
  3. lance python source/convertall.py.

Sans argument, l'interface graphique démarre. Tout argument non reconnu par ce
script est transmis tel quel à convertall.py, qui bascule alors en mode ligne de
commande :

  bash run_qt6.sh -q 1 in cm            conversion sans question
  bash run_qt6.sh -q 5 ft 10 in to cm   unités composées
  bash run_qt6.sh -i                    mode interactif (REPL)
  bash run_qt6.sh -t                    validation du catalogue
  bash run_qt6.sh --test-all            validation de tous les catalogues
  bash run_qt6.sh --version             version
  bash run_qt6.sh -h                    aide de convertall.py

Options de ce script :
  --no-install        réutilise le venv existant, sans venv ni pip
  --python CHEMIN     interpréteur Python 3.11–3.14 pour créer le venv
  -h, --help          affiche cette aide (celle de convertall.py reste -h)
  --                  fin des options de ce script, le reste va à convertall.py

Exemples :
  bash run_qt6.sh
  bash run_qt6.sh --no-install -q 1 in cm
  bash run_qt6.sh --python python3.13

Prérequis à installer vous-même (ce script n'installe que les paquets Python du
venv) : Debian 12 / Python 3.11 → sudo apt-get install python3.11-venv ;
bibliothèques Qt/XCB système → voir doc/RELEASE_QT6_FR.md. Sur une machine sans
écran, le mode graphique échoue : utilisez les arguments CLI ci-dessus.

Code de sortie : celui de convertall.py (0 = succès, 1 = erreur de
conversion/données, 2 = erreur d'usage, 130 = interrompu).
HELP
}

DO_INSTALL=1
REQUESTED_PYTHON=''
while (($#)); do
    case "$1" in
        --no-install) DO_INSTALL=0; shift ;;
        --python)
            if (($# < 2)); then printf 'Il manque le chemin après --python.\n' >&2; exit 2; fi
            REQUESTED_PYTHON="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        --) shift; break ;;
        *) break ;;
    esac
done
APP_ARGS=("$@")

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P) || exit 2
cd "$ROOT" || exit 2

BASE_PYTHON=''
if [[ -n "$REQUESTED_PYTHON" ]]; then
    BASE_PYTHON=$(command -v "$REQUESTED_PYTHON" 2>/dev/null) || true
    if [[ -z "$BASE_PYTHON" ]]; then
        printf 'Interpréteur introuvable : %s\n' "$REQUESTED_PYTHON" >&2
        exit 2
    fi
else
    for candidate in python3.11 python3 python; do
        BASE_PYTHON=$(command -v "$candidate" 2>/dev/null) || true
        [[ -n "$BASE_PYTHON" ]] && break
    done
fi
if [[ -z "$BASE_PYTHON" ]]; then
    printf 'Aucun interpréteur Python trouvé ; installez Python 3.11–3.14.\n' >&2
    exit 2
fi
version=$("$BASE_PYTHON" -c 'import sys; print("{}.{}".format(*sys.version_info[:2]))') || exit 2
if [[ ! "$version" =~ ^3\.(11|12|13|14)$ ]]; then
    printf 'Python %s détecté : ce profil exige Python 3.11–3.14.\n' "$version" >&2
    printf 'Utilisez --python CHEMIN pour choisir un autre interpréteur.\n' >&2
    exit 2
fi

# Comme les autres lanceurs : pas de fuite d'un PYTHONPATH ou d'un Qt parent.
export PYTHONIOENCODING=utf-8
export PYTHONUNBUFFERED=1
export PYTHONNOUSERSITE=1
export QT_API=pyqt6
unset PYTHONPATH QT_PLUGIN_PATH QT_QPA_PLATFORM_PLUGIN_PATH
# Une AppImage/venv d'un autre outil ne doit pas imposer son interpréteur.
unset VIRTUAL_ENV

VENV="$ROOT/.venv/qt6"
existing_venv_python() {
    if [[ -x "$VENV/bin/python" ]]; then
        printf '%s\n' "$VENV/bin/python"
    elif [[ -x "$VENV/Scripts/python.exe" ]]; then
        printf '%s\n' "$VENV/Scripts/python.exe"
    fi
}

prepare_venv() {
    local interpreter code
    interpreter=$(existing_venv_python)
    # Un échec de ensurepip peut laisser bin/python présent, mais aucun pip :
    # la présence de l'exécutable seule ne prouve donc pas que le venv est prêt.
    if [[ -n "$interpreter" ]] && "$interpreter" -m pip --version >/dev/null 2>&1; then
        printf 'Venv dédié prêt : %s\n' "$VENV"
        return 0
    fi
    if [[ -n "$interpreter" ]]; then
        printf 'Venv incomplet détecté ; réparation sans supprimer le répertoire.\n'
    fi
    if ! "$BASE_PYTHON" -c 'import importlib.util, sys; sys.exit(0 if importlib.util.find_spec("ensurepip") else 2)'; then
        printf '\nERREUR : ensurepip est absent pour Python %s.\n' "$version" >&2
        printf 'Sur Debian/Ubuntu, exécuter vous-même :\n' >&2
        printf '  sudo apt-get update\n  sudo apt-get install python%s-venv\n' "$version" >&2
        printf 'Puis relancer ce script : il réparera le venv incomplet.\n' >&2
        return 2
    fi
    code=0
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

APP_PYTHON=$(existing_venv_python)
if [[ "$DO_INSTALL" -eq 1 ]]; then
    prepare_venv || exit $?
    APP_PYTHON=$(existing_venv_python)
    if [[ -z "$APP_PYTHON" ]]; then
        printf 'ERREUR : venv indisponible après préparation.\n' >&2
        exit 2
    fi
    printf 'Dépendances épinglées (requirements-qt6.txt)…\n'
    if ! "$APP_PYTHON" -m pip --disable-pip-version-check install -r "$ROOT/requirements-qt6.txt"; then
        printf 'Installation des dépendances en échec ; voir le message ci-dessus.\n' >&2
        exit 1
    fi
else
    if [[ -z "$APP_PYTHON" ]]; then
        printf 'Aucun venv dans %s : relancez sans --no-install.\n' "$VENV" >&2
        exit 2
    fi
fi

# Contrôle utile avant de lancer : PyQt6 doit être importable dans ce venv.
if ! "$APP_PYTHON" -c 'import PyQt6.QtCore' 2>/dev/null; then
    printf 'PyQt6 est introuvable dans %s.\n' "$VENV" >&2
    if [[ "$DO_INSTALL" -eq 0 ]]; then
        printf 'Relancez sans --no-install, ou : %s -m pip install -r requirements-qt6.txt\n' \
               "$APP_PYTHON" >&2
    else
        printf 'Vérifiez les bibliothèques Qt système (doc/RELEASE_QT6_FR.md).\n' >&2
    fi
    exit 1
fi

if ((${#APP_ARGS[@]} == 0)) && [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    printf 'Aucun serveur graphique détecté : le mode graphique va échouer.\n' >&2
    printf 'Pour un contrôle sans écran : bash run_qt6.sh -q 1 in cm\n' >&2
fi

printf 'Lancement : %s source/convertall.py %s\n' "$APP_PYTHON" "${APP_ARGS[*]:-}"
"$APP_PYTHON" "$ROOT/source/convertall.py" "${APP_ARGS[@]}"
exit $?
