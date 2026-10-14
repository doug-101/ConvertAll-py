# ConvertAll-py : release de référence Qt5, étude Qt6 et benchmark

> **La migration de production actuelle est décrite dans [PORTAGE_QT6_FR.md](PORTAGE_QT6_FR.md).**
> Ce document et ses résultats restent un audit historique, pas la validation de Qt6 0.9.0.
>
> **Historique 0.8.0 :** cet audit et ses mesures portent sur le commit indiqué
> ci-dessous, pas sur la maintenance 0.8.1. Pour les tests et la publication
> de Qt5 0.8.1, voir [RELEASE_QT5_FR.md](RELEASE_QT5_FR.md).

**Audit du 10 octobre 2026 — dépôt `jojo8356/ConvertAll-py`.**

Commit étudié : `a71219904b6a27e7578744afcfa227b21fc73fb2`.

Branche de travail : `arena/0adacf84-convertall-py`.

> **Conclusion : oui, le portage vers PyQt6 est assez simple pour l'interface.**
> Un prototype isolé fonctionne et passe les mêmes 50 contrôles ciblés que Qt5.
> En revanche, une release fiable demande aussi du travail sur les données,
> les traductions, les dépendances et les binaires. Qt6 n'est pas un gain de
> performance démontré pour cette application.
>
> **L'application actuelle n'a pas été migrée. Aucune release, aucun tag et
> aucun push n'ont été effectués.** Les modifications permanentes de cet audit
> sont ce rapport, les résultats JSON, des outils de recherche/tests et des
> exclusions d'artefacts dans `.gitignore`.

## 1. D'abord : créer la release de base Qt5 « Latest »

### 1.1 Quel état faut-il publier ?

Le programme annonce toujours **0.8.0**, dans `source/convertall.py:17`.
Le fichier anglais des unités a reçu des ajouts jusqu'en 2026. Le fork ne
contient actuellement ni tag distant, ni release GitHub, ni workflow Actions.
La dernière release du dépôt Python amont est `v0.8.0`, publiée en mars 2020.

Il faut distinguer deux opérations :

- **Photo de référence fidèle** : archiver exactement le commit ci-dessus,
  avec ses défauts connus, pour comparer Qt5 à Qt6 et permettre un retour arrière.
  Je propose l'étiquette **`v0.8.0-qt5`**. Le programme continuera à afficher 0.8.0 :
  le suffixe du tag n'est pas une nouvelle version interne.
- **Release Qt5 stable recommandée aux utilisateurs** : corriger d'abord les
  défauts listés en section 4, ajouter les tests, incrémenter les versions
  concernées, puis publier par exemple **0.8.1**. Dans ce cas, le commit ciblé
  sera celui des corrections, pas `a712199…`.

**Je recommande de commencer par un brouillon.** La baseline exacte n'est pas
une preuve que toutes les unités sont correctes. En particulier, six nouvelles
unités anglaises échouent et le test intégré `--test` plante.

Le badge GitHub **Latest** se règle avec `--latest`. Il ne faut pas créer un tag
flottant nommé `latest`, ni modifier ultérieurement le tag de référence. La CLI
permet de viser explicitement un commit lors de la création du tag associé à la
release. [1](https://cli.github.com/manual/gh_release_create)

### 1.2 Commandes Bash : archive propre et brouillon GitHub

À lancer **à la racine du dépôt**. `git archive` exporte le commit choisi,
indépendamment des nouveaux fichiers de recherche ou des modifications locales.
Il n'y a ni changement de branche ni besoin de pousser un tag par `git` :
le commit de référence existe déjà sur GitHub et `gh` crée le tag de la release.

```bash
set -euo pipefail

REPO=jojo8356/ConvertAll-py
BASE=a71219904b6a27e7578744afcfa227b21fc73fb2
TAG=v0.8.0-qt5
OUT=dist/qt5

# Vérifications en lecture seule
git status --short --branch
git show --no-patch --oneline "$BASE"
gh release list --repo "$REPO"

mkdir -p "$OUT"
git archive --format=tar --prefix=ConvertAll-0.8.0-qt5/ "$BASE" \
  | gzip -n > "$OUT/ConvertAll-0.8.0-qt5-source.tar.gz"

(
  cd "$OUT"
  sha256sum ConvertAll-0.8.0-qt5-source.tar.gz > SHA256SUMS
  sha256sum -c SHA256SUMS
)

cat > "$OUT/RELEASE_NOTES.md" <<'NOTES'
# ConvertAll 0.8.0 — référence Qt5

Snapshot du commit a71219904b6a27e7578744afcfa227b21fc73fb2,
avant migration vers Qt6. Application Python/PyQt5 avec les ajouts
récents au fichier anglais des unités.

Cette archive est une baseline de comparaison et de retour arrière,
pas une certification de toutes les conversions.
Défauts connus : six nouvelles définitions anglaises utilisent un
signe moins Unicode incompatible avec le parseur ; l'option --test
plante ; certaines données catalanes et suédoises ont des références
invalides. Voir le rapport de migration et les résultats de l'audit.

Environnement Linux testé : Python 3.11.2, PyQt5 5.15.11,
Qt 5.15.19. Les binaires Windows ne sont pas validés par cet audit.
NOTES

# ÉCRITURE SUR GITHUB : à exécuter seulement pour créer le brouillon voulu.
gh release create "$TAG" \
  "$OUT/ConvertAll-0.8.0-qt5-source.tar.gz" \
  "$OUT/SHA256SUMS" \
  --repo "$REPO" \
  --target "$BASE" \
  --title "ConvertAll 0.8.0 — référence Qt5" \
  --notes-file "$OUT/RELEASE_NOTES.md" \
  --draft
```

Après vérification des assets et acceptation explicite des limites de cette
**photo de référence**, la publication en **Latest** se fait ainsi :

```bash
gh release edit v0.8.0-qt5 \
  --repo jojo8356/ConvertAll-py \
  --draft=false --latest

gh release view v0.8.0-qt5 --repo jojo8356/ConvertAll-py
```

Si l'objectif est une vraie stable Qt5 corrigée, remplacer le tag et `BASE` par
la nouvelle version et son commit, après les corrections et leur validation.
Ne pas publier une archive corrigée sous un tag qui pointe encore sur l'ancien
code. Dans cette session, les futurs commits/push restent sur la branche
`arena/0adacf84-convertall-py` ; le push correspondant est uniquement :

```bash
git push origin arena/0adacf84-convertall-py
```

**Vérifié pendant l'audit :** création locale de l'archive, absence de `.git`,
`.venv` et `.cache`, présence du code et de `doc/LICENSE`, contrôle SHA-256.
L'archive obtenue fait **417 789 octets**. Son SHA-256 est :

```text
9739aa7bb717cf2654541dd2b14a4aa329c2646709eff15d503f961e90af7873
```

Les commandes de publication GitHub ci-dessus **n'ont pas été exécutées**.

### 1.3 Environnement de référence Qt5 sous Linux

Ce jeu de versions est celui effectivement utilisé sur Debian 12 x86_64,
avec Python 3.11. Il fige aussi le runtime Qt et SIP, pas seulement PyQt.

```bash
python3 -m venv .venv/qt5
.venv/qt5/bin/python -m pip install \
  'PyQt5==5.15.11' 'PyQt5-Qt5==5.15.19' 'PyQt5-sip==12.20.0'

.venv/qt5/bin/python -c \
  'from PyQt5.QtCore import PYQT_VERSION_STR, qVersion; print(PYQT_VERSION_STR, qVersion())'

LC_MESSAGES=C .venv/qt5/bin/python source/convertall.py -q 1 in cm
LC_MESSAGES=C .venv/qt5/bin/python source/convertall.py -q 0 'deg C' 'deg F'
```

Résultats attendus : `1 in = 2.54 cm` et `0 deg C = 32 deg F`.
Pour vérifier l'interface sur un poste graphique :

```bash
.venv/qt5/bin/python source/convertall.py
```

Sur une image Linux minimale, installer les bibliothèques natives nécessaires.
Pour le mode offscreen de l'audit, les principaux paquets Debian/Ubuntu sont :

```bash
sudo apt install python3-venv libgl1 libegl1 libxkbcommon0 libdbus-1-3 \
  libfontconfig1 libfreetype6 fonts-dejavu-core
```

Un vrai bureau X11 requiert aussi les dépendances du plugin `xcb`, généralement
déjà installées. Pour Qt6, vérifier notamment `libxcb-cursor0`,
`libxkbcommon-x11-0`, `libxcb-icccm4`, `libxcb-image0`, `libxcb-keysyms1`,
`libxcb-render-util0`, `libxcb-xkb1` et `libx11-xcb1`, ainsi que leurs dépendances.
La liste officielle est dans les exigences Linux de Qt.

**Installation Qt5 également testée** : l'ancien `install.py`, exécuté depuis
une extraction indépendante avec un préfixe temporaire, installe correctement
le programme, les données, les icônes, les traductions et le lanceur. Les deux
conversions CLI ci-dessus fonctionnent depuis le lanceur installé. En utilisation
réelle, un préfixe personnel est possible :

```bash
# À exécuter depuis une extraction dédiée de l'archive, contenant install.py.
# Le lanceur conserve le chemin du Python utilisé : garder le venv installé.
/path/to/venv/bin/python install.py -p "$HOME/.local"
```

Ne pas utiliser `--test` comme contrôle de publication en l'état : son plantage
est un défaut constaté, pas un succès silencieux.

### 1.4 Et pour un binaire Windows Qt5 ?

**Attention au mot « latest ».** PyPI fournit PyQt5 5.15.11, mais le runtime
`PyQt5-Qt5` le plus récent disponible sous forme de wheel Windows x86_64 est
**5.15.2**, pas 5.15.19. La wheel 5.15.19 utilisée ici est disponible pour Linux
et macOS. Cette différence a été vérifiée dans les métadonnées PyPI.
[1](https://pypi.org/project/PyQt5-Qt5/)

Donc :

- une baseline Windows via les wheels PyPI conserve **Qt 5.15.2** ;
- elle ne doit pas être présentée comme un binaire Windows utilisant Qt 5.15.19 ;
- obtenir un runtime Qt5 Windows plus récent demanderait un SDK/build Qt5
  approprié et une compilation de PyQt5 contre celui-ci, avec vérification des
  licences et de la disponibilité des correctifs ;
- les binaires Windows doivent être construits et testés **sous Windows**.

Pour une première baseline portable, je choisirais **PyInstaller onedir + ZIP**
plutôt que les vieux installateurs Inno Setup. Exemple PowerShell, à la racine du
dépôt, sur une machine disposant de Python 3.11 et Git :

```powershell
$ErrorActionPreference = 'Stop'
$Base = 'a71219904b6a27e7578744afcfa227b21fc73fb2'
New-Item -ItemType Directory -Force dist, build | Out-Null

git archive --format=zip --prefix=ConvertAll-qt5/ `
  --output=dist/qt5-source.zip $Base
if ($LASTEXITCODE -ne 0) { throw 'git archive a échoué' }
Expand-Archive dist/qt5-source.zip -DestinationPath dist/qt5-source -Force
$Src = (Resolve-Path dist/qt5-source/ConvertAll-qt5).Path

py -3.11 -m venv .venv/qt5-win
if ($LASTEXITCODE -ne 0) { throw 'Création du venv échouée' }
$Py = (Resolve-Path .venv/qt5-win/Scripts/python.exe).Path
& $Py -m pip install 'PyQt5==5.15.11' 'PyQt5-Qt5==5.15.2' `
  'PyQt5-sip==12.20.0' 'PyInstaller==6.22.3'
if ($LASTEXITCODE -ne 0) { throw 'Installation des dépendances échouée' }

& $Py -m PyInstaller --clean --noconfirm --windowed --onedir `
  --contents-directory . --name convertall `
  --specpath "$PWD/build/qt5-spec" `
  --workpath "$PWD/build/qt5-win" --distpath "$PWD/dist/qt5-win" `
  --paths "$Src/source" --icon "$Src/win/convertall.ico" `
  --add-data "$Src/data:data" --add-data "$Src/doc:doc" `
  --add-data "$Src/icons:icons" --add-data "$Src/translations:translations" `
  --add-data "$Src/source:source" `
  "$Src/source/convertall.py"
if ($LASTEXITCODE -ne 0) { throw 'Build PyInstaller échoué' }

# Vérifier MANUELLEMENT dist/qt5-win/convertall/convertall.exe avant publication.
# Tester depuis un répertoire de travail différent et une machine sans Python.
Compress-Archive -Path dist/qt5-win/convertall `
  -DestinationPath dist/ConvertAll-0.8.0-qt5-windows-x64.zip -Force
(Get-FileHash dist/ConvertAll-0.8.0-qt5-windows-x64.zip -Algorithm SHA256).Hash `
  + '  ConvertAll-0.8.0-qt5-windows-x64.zip' `
  | Set-Content dist/ConvertAll-0.8.0-qt5-windows-x64.sha256 -Encoding ascii

# Seulement après tests Windows réussis et création du brouillon/release :
# gh release upload v0.8.0-qt5 `
#   dist/ConvertAll-0.8.0-qt5-windows-x64.zip `
#   dist/ConvertAll-0.8.0-qt5-windows-x64.sha256 `
#   --repo jojo8356/ConvertAll-py
```

Cette recette Windows est **proposée, non exécutée** dans le sandbox Linux.
Elle fournit l'interface graphique ; avec `--windowed`, ce n'est pas un
exécutable CLI de test. Pour une CLI Windows, prévoir un second build console.

`--contents-directory .` conserve volontairement une disposition plate pour la
baseline. PyInstaller 6 met sinon les dépendances sous `_internal`. Il ne faut
pas mélanger les structures de fichiers d'un nouveau bundle et les chemins des
anciens `.iss`.

Avant toute distribution binaire, contrôler les notices de Python, Qt, PyQt et
leurs dépendances, ainsi que la fourniture du code source correspondant.

## 2. Résultat de l'audit du code : migration limitée, pas une réécriture

### 2.1 Architecture réelle

Le dossier `source/` comporte **19 fichiers Python et 3 610 lignes**, dont
**11 modules important PyQt5**. Il s'agit d'une application **Qt Widgets**, pas
d'une application QML/Qt Quick.

Le moteur et les données sont indépendants des widgets : `unitatom.py`,
`unitdata.py`, `unitgroup.py`, `cmdline.py`, `option.py`, `optiondefaults.py` et
`recentunits.py` ne nécessitent pas de remplacement des algorithmes de conversion.
Le prototype les garde **octet pour octet identiques** ; les sept fichiers de
unités le sont aussi. Les SHA-256 avant/après sont conservés dans les résultats.

Pas de code C++ applicatif, pas de `.ui` à régénérer, pas de WebEngine, pas de QML
et pas de widget OpenGL à porter. Le fichier `source/convertall.pro` sert à
l'extraction des traductions, pas à compiler un programme Qt C++ : une conversion
vers CMake n'est pas nécessaire pour ce portage Python.

Le guide Qt recommande de partir de Qt 5.15. Nous avons donc testé la baseline
avec Qt 5.15.19. Le backend graphique des **Qt Widgets** ne change pas comme
celui de Qt Quick : les promesses de gains GPU de Qt6 ne constituent pas ici un
argument de performance. Les macros de suppression d'API obsolètes et les
outils Clazy présentés dans les guides C++ ne s'appliquent pas directement aux
imports Python.

### 2.2 Modifications effectivement nécessaires

Le prototype applique **29 changements d'import**, **9 remplacements de
`exec_()`**, et **77 occurrences de constantes courtes** correspondant à
**33 membres d'enum distincts**, dans les 11 modules Qt.

| Point | Code actuel / fichier | Modification Qt6 |
|---|---|---|
| Binding | `from PyQt5...` dans 11 modules | `from PyQt6...` |
| Enums et flags | `Qt.NoFocus`, `Qt.Key_Down`, `QDialog.Accepted`, `QPalette.Text`… | `Qt.FocusPolicy.NoFocus`, `Qt.Key.Key_Down`, `QDialog.DialogCode.Accepted`, `QPalette.ColorRole.Text`… |
| Boucles et dialogues | 9 appels `exec_()` | `exec()` |
| Actions de l'aide | `helpview.py:19`, `QAction` importé depuis QtWidgets | Importer `QAction` depuis QtGui |
| Application globale | Import `qApp`, puis 2 usages dans `colorset.py` | `QApplication.instance()` |
| Palette dynamique | `eval('QPalette.' + roleStr/groupStr)` | `getattr(QPalette.ColorRole, roleStr)` et `getattr(QPalette.ColorGroup, groupStr)` |
| Polices | 4 constructions `QFontDatabase()` dans `fontset.py` | Appeler les méthodes statiques de `QFontDatabase` |
| Signal de l'aide | `QTextBrowser.highlighted[str]` | Connecter le signal `QUrl`, convertir avec `url.toString()` dans le slot |
| Installation | Vérifications PyQt5/Qt5 ≥ 5.4 dans `install.py` | Contrôler le binding Qt6 réellement choisi et le minimum Python |
| Diffusion | `.spec`, `setup.py`, `.iss` anciens | Ressources, plugins, chemins et versions à moderniser/tester |
| Traductions | `.pro` et fonction `_()` personnalisée | Adapter l'extraction et mettre à jour les catalogues Qt6 |

Les enums, `exec_()` et la disparition de `qApp` sont documentés par Riverbank.
[1](https://www.riverbankcomputing.com/static/Docs/PyQt6/pyqt5_differences.html)
Le déplacement de `QAction` est documenté par Qt.
[9](https://doc.qt.io/qt-6/widgets-changes-qt6.html)
Les méthodes statiques de `QFontDatabase` sont un autre changement Qt6 réel.
[1](https://doc.qt.io/qt-6/gui-changes-qt6.html)
Le signal `highlighted` de Qt6 ne conserve que la version `QUrl`.
[3](https://doc.qt.io/qt-6/qtextbrowser.html)

**Ce qui est déjà prêt :** `QRegularExpression` est utilisé, et la géométrie
utilise déjà `QApplication.primaryScreen()`. Il n'y a donc pas de `QRegExp` ou de
`QDesktopWidget` à remplacer. Il ne faut pas ajouter des modifications de ces
API juste parce qu'elles figurent dans un tutoriel générique.

### 2.3 Choix du binding

| Option | Avantages / coût | Recommandation |
|---|---|---|
| **PyQt6 direct** | Conserve `pyqtSignal`, l'organisation et la plupart des API existantes | **Choix recommandé**, le moins de variables nouvelles |
| PySide6 | Binding officiel Qt for Python, autre modèle de licence ; adaptation des signaux et vérification des différences de binding | Possible, mais migration et benchmark distincts ; non mesuré ici |
| QtPy + deux backends | Utile si un support Qt5/Qt6 simultané est réellement requis | Pas nécessaire pour ce petit projet ; ajoute une dépendance et une matrice de tests |

Je ne mettrais pas une grosse couche de compatibilité dans chaque module. Une
release Qt5 immuable fournit déjà le retour arrière. Si un double support est
vraiment nécessaire, le traiter explicitement, avec deux environnements et une
sélection déterministe du backend, jamais en important les deux bindings dans
le même processus.

Pour les builds gelés, PyInstaller interdit la collecte simultanée de plusieurs
bindings Qt. Les environnements et builds doivent rester séparés.
[1](https://pyinstaller.org/en/v6.5.0/CHANGES.html)

**Licence :** PyQt6 est sous GPLv3 ou licence commerciale, pas sous LGPL. Les
modules du projet annoncent GPLv2 ou ultérieure ; les notices, notamment celles
des données, doivent être revérifiées pour la diffusion. Il ne faut pas
confondre la licence de Qt, celle de PyQt et celle de PySide. Cet audit n'est pas
une certification juridique.

## 3. Benchmark réellement exécuté

### 3.1 Protocole et environnement

- Debian 12 **x86_64**, glibc 2.36, environnement virtualisé.
- Python **3.11.2** pour les deux configurations.
- Qt5 : **PyQt5 5.15.11 / Qt runtime 5.15.19 / SIP 12.20.0**.
- Qt6 : **PyQt6 6.11.0 / Qt runtime 6.11.2 / SIP 13.13.0**.
- Binding compilé contre Qt 5.15.14 / Qt 6.11.0 respectivement : ce n'est pas la
  même information que la version du runtime, obtenue avec `qVersion()`.
- Même source numérique, mêmes données anglaises, **626 unités**.
- Style **Fusion**, police **DejaVu Sans 10**, fenêtre **1024 × 640**, échelle 1.
- Plugin **offscreen**, sans serveur graphique, GPU ou compositeur natif.
- **40 démarrages par binding**, chacun dans un processus neuf ; alternance
  Qt5/Qt6 et inversion de l'ordre une paire sur deux, après un échauffement.
- Les caches OS sont chauds : aucune prétention à mesurer un démarrage disque
  « à froid ».
- La durée de démarrage va du début des imports Qt jusqu'à la création de la
  fenêtre, au traitement des événements et au premier `grab()` non vide.
  **Elle exclut le démarrage de l'interpréteur Python et le bootstrap du script.**
- RSS mesuré après le premier rendu avec `psutil` ; il s'agit de mémoire
  résidente du processus, pas d'une mesure PSS ni de mémoire totale de bureau.
- Opérations : échauffement puis **20 lots** ; 100 filtrages par lot,
  1 000 conversions GUI par lot, 100 000 conversions du moteur par lot.
  Les opérations GUI comprennent `processEvents()`. Les lots d'opérations
  sont exécutés dans un worker par binding, pas dans 40 workers indépendants.
- Chaque worker a un `HOME`/`APPDATA` temporaire, sans toucher aux préférences
  de l'utilisateur. Les dialogues modaux sont pilotés automatiquement.

Les bibliothèques OpenGL/EGL, xkbcommon et D-Bus étaient absentes du sandbox.
Des bibliothèques ELF réelles issues d'une image système archivée sur GitHub
ont été utilisées, avec **la même configuration pour Qt5 et Qt6**, sans shim ni
simulation des widgets. Leur provenance, commit et SHA-256 sont dans le JSON.
Pour reproduire sur une machine normale, préférer les paquets système officiels
indiqués en section 1.3. Aucun benchmark OpenGL/3D n'a été exécuté.

### 3.2 Résultats

Médianes de la campagne finale ; le p95 des démarrages est calculé au rang
supérieur correspondant à 95 % des 40 échantillons.

| Mesure | Qt5 | Prototype Qt6 | Écart Qt6 |
|---|---:|---:|---:|
| Imports + initialisation + premier rendu | **88,07 ms** | **110,86 ms** | **+25,9 %** |
| Même mesure, p95 | 110,93 ms | 140,48 ms | — |
| Mémoire RSS après premier rendu | **60,71 MiB** | **63,56 MiB** | **+4,7 %**, soit environ +2,85 MiB |
| Filtrage / reconstruction de la liste + événements | **2,575 ms** | **3,596 ms** | **+39,7 %** |
| Conversion numérique GUI + événements | **0,129 ms** | **0,288 ms** | **+123,4 %**, soit seulement +0,159 ms |
| Conversion du moteur Python, groupes déjà réduits | **0,151 µs** | **0,149 µs** | Pas de gain significatif ; environ −1 % de bruit |
| Taille du répertoire PyQt installé, tous modules fournis | **195,30 MiB** | **250,25 MiB** | **+28,1 %** |

**Interprétation :** dans cette configuration, le prototype Qt6 n'est pas plus
rapide. La différence du moteur est négligeable et attendue : c'est le même code
Python. La conversion GUI demeure inférieure à une milliseconde, mais les chiffres
ne démontrent pas un gain utilisateur. Le bénéfice attendu de Qt6 est surtout la
maintenance, la compatibilité avec les environnements modernes et le HiDPI.

La taille du répertoire installé **n'est pas la taille d'un exécutable distribué** :
il contient aussi des modules Qt non utilisés par ConvertAll. Ne pas annoncer
un ZIP Windows 28 % plus gros sur cette seule base.

Ces résultats ne permettent pas de conclure que « Qt6 est toujours plus lent »,
ni d'annoncer les mêmes différences sous Windows, Wayland ou macOS. Les latences
natives, le démarrage du bootloader et les tailles des exécutables restent à mesurer.

### 3.3 Tests fonctionnels et limites

**50 contrôles ciblés réussissent sous chaque binding**, notamment :

- conversions linéaires, vitesse, surface et températures 0/100/−40 °C ;
- validateurs, expressions arithmétiques et conversion GUI dans les deux sens ;
- filtrage, tri et sélection au clavier ;
- options, palettes, thème sombre, sélection de police et annulation ;
- conversions des bases et complément à deux ;
- fractions et restriction des dénominateurs ;
- chargement de l'aide HTML, recherche et signal de survol des liens ;
- dialogue des astuces, chargement de six catalogues de traduction et
  correspondance des contextes historiques ;
- sauvegarde des préférences dans un répertoire isolé.

Un essai supplémentaire lance aussi le **vrai `main()` et sa boucle d'événements**
sous Qt5 et Qt6, en offscreen, avec une sortie automatique après 300 ms.
L'ancien installateur Qt5 a été essayé indépendamment. Les outils de recherche
ont **8 tests unitaires stdlib réussis**.

**Cela ne veut pas dire que toutes les unités passent.** Le moteur réduit
correctement **620 définitions anglaises sur 626**. Les six échecs sont identiques
sous Qt5 et Qt6 ; les échecs localisés le sont aussi. Voir la section suivante.

**Non exécuté / non certifié :**

- affichage natif Windows, Wayland, macOS, multi-écrans et HiDPI ;
- création et installation d'un exécutable Windows ou d'un installateur Inno ;
- benchmark du démarrage d'un exécutable gelé ou de sa taille ;
- audit de sécurité complet ou certification juridique.

Une tentative de build PyInstaller dans le sandbox a été **bloquée par l'absence
de `libpython3.11.so`**. Il serait trompeur de présenter le bundle comme construit
ou testé. Sur une machine Debian dédiée au build, le paquet de bibliothèque Python
correspondant à l'interpréteur est nécessaire ; ce problème est indépendant de
la migration Qt. Les ressources passées à PyInstaller doivent aussi utiliser des
chemins absolus lorsque le `.spec` généré est placé dans un autre dossier.

### 3.4 Reproduire le benchmark sans modifier l'application

Outils conservés dans le dépôt :

- `tools/qt6_probe.py` : crée une **copie expérimentale**, refuse une destination
  déjà existante et ne change ni le moteur, ni les données, ni les installateurs ;
- `tools/benchmark_qt.py` : workers séparés, paramètres identiques et résultats bruts ;
- `tools/test_qt_migration_tools.py` : vérification des transformations et protections.

Installer les bibliothèques système nécessaires, puis, à la racine du dépôt :

```bash
set -euo pipefail

python3 -m venv .venv/qt5
python3 -m venv .venv/qt6
.venv/qt5/bin/python -m pip install \
  'PyQt5==5.15.11' 'PyQt5-Qt5==5.15.19' 'PyQt5-sip==12.20.0' 'psutil==7.2.2'
.venv/qt6/bin/python -m pip install \
  'PyQt6==6.11.0' 'PyQt6-Qt6==6.11.2' 'PyQt6-sip==13.13.0' 'psutil==7.2.2'

mkdir -p .cache/qt-migration
RUN=$(mktemp -d "$PWD/.cache/qt-migration/replay-XXXXXX")
mkdir "$RUN/qt5"
git archive a71219904b6a27e7578744afcfa227b21fc73fb2 | tar -x -C "$RUN/qt5"
python3 tools/qt6_probe.py --source "$RUN/qt5" --output "$RUN/qt6"

python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 tools/benchmark_qt.py \
  --python-qt5 .venv/qt5/bin/python \
  --python-qt6 .venv/qt6/bin/python \
  --qt5-root "$RUN/qt5" --qt6-root "$RUN/qt6" \
  --runs 40 --output "$RUN/results.json"
```

Les résultats de cet audit, incluant les échantillons, versions, `pip freeze`,
SHA-256 des sources/données et limites, sont conservés dans :

[`benchmarks/qt-migration-2026-10-10.json`](benchmarks/qt-migration-2026-10-10.json).

Les venvs, copies temporaires et gros binaires ne sont pas ajoutés à Git. Le
prototype n'est pas une migration de production : il laisse exprès `install.py`,
les `.iss`, le `.pro` et le `.spec` inchangés.

## 4. Défauts préexistants : à régler AVANT d'appeler la Qt5 « stable »

### 4.1 Six nouvelles définitions anglaises invalides

Dans `data/units.dat`, les exposants négatifs de ces lignes utilisent le signe
**U+2212 `−`**, alors que `UnitDatum.badOpRegEx` accepte le tiret ASCII `-` :

| Ligne | Unité |
|---:|---|
| 69 | Planck mass |
| 120 | Planck length |
| 250 | Planck time |
| 329 | elementary charge |
| 900 | Boltzmann constant |
| 901 | vacuum permittivity |

Exemple : `2.176434e−8` n'est pas reconnu comme facteur numérique. Le parseur
l'interprète ensuite dans la référence d'unité ; la réduction aboutit à un
`AttributeError` sur `NoneType.equiv`. **Ce défaut existe déjà dans Qt5.**

Correction minimale proposée : normaliser les six nombres en notation ASCII
et ajouter des tests de leurs valeurs physiques. Éventuellement rendre l'erreur
sur une définition invalide plus explicite, dans un changement séparé du port Qt.
La nouvelle `Planck temperature`, avec exposant positif, se réduit correctement.

### 4.2 `--test` ne fonctionne pas

`source/cmdline.py:188` appelle `unit.unitValid()` sur un **`UnitDatum`**, mais
cette méthode est définie sur **`UnitAtom`**. La commande :

```bash
python source/convertall.py --test
```

plante avec `AttributeError: 'UnitDatum' object has no attribute 'unitValid'`.
Le wrapper CLI ne transforme pas non plus automatiquement le résultat booléen
du test en code d'échec utilisable par CI.

Je corrigerais le contrôle pour valider le groupe/atome approprié, conserverais
un diagnostic des définitions fautives et imposerais **un code de sortie non nul
si une définition échoue**. Les tests devraient inclure exprès un fichier
invalide pour vérifier le code de sortie, pas seulement une sortie textuelle.

### 4.3 Les données traduites ne sont pas équivalentes au fichier anglais

Audit de réduction des définitions, sur les mêmes fichiers sous les deux Qt :

| Fichier / langue | Définitions chargées | Échecs de réduction |
|---|---:|---:|
| anglais | 626 | 6 |
| catalan | 600 | 2 |
| allemand | 637 | 0 |
| espagnol | 537 | 0 |
| français | 523 | 0 |
| russe | 612 | 0 |
| suédois | 569 | 107 |

Les deux échecs catalans sont `kilotona no mètrica` et `township`.
Les échecs suédois incluent des chaînes de dépendances vers des noms d'unités
non résolus ; le détail des 107 noms est dans le JSON. Ne pas assimiler 107
échecs à 107 causes racines distinctes.

Le nombre d'unités peut varier avec les synonymes locaux : zéro erreur ne prouve
ni que les données sont à jour, ni que toutes les valeurs numériques sont
correctes. Il faut aussi décider comment répercuter les nouvelles unités dans
les langues. **Ce chantier de qualité des données est indépendant de Qt6** et
peut prendre plus de temps que le changement de binding.

## 5. Traductions : le piège principal au-delà de l'interface

Le chargeur actuel de `.qm` fonctionne dans le prototype : les **six catalogues
applicatifs** existants chargent sous Qt6 et conservent un contexte tel que
`convertdlg / From Unit`. Cela évite de jeter les traductions existantes.

En revanche, la génération n'est pas compatible en l'état :

1. `pylupdate6` ne lit plus les `.pro` comme le faisait `pylupdate5`.
2. Le code utilise une fonction globale personnalisée **`_()`** dont le contexte
   est le nom du module. `pylupdate5` a une option `-tr-function _`, mais
   `pylupdate6` n'expose pas l'équivalent dans sa CLI actuelle.
3. **Essai réel :** `pylupdate6 --ts fichier.ts source/*.py` sur le prototype
   produit **zéro message**. Une mise à jour naïve des catalogues existants
   pourrait marquer les traductions comme obsolètes.
4. Un adaptateur AST expérimental qui rend ces appels explicites avec
   `QCoreApplication.translate("module", ...)` permet d'extraire **147 messages
   distincts**. C'est une preuve de solution, pas encore un outil de release.
5. Le `.pro` historique omet déjà `bases.py`, `colorset.py` et `fontset.py` :
   la chaîne Qt5 doit aussi être revue pour inclure tous les dialogues actuels.

**Plan retenu :** conserver les contextes et les traductions existantes ;
réaliser un outil d'extraction testé qui adapte `_()` sans changer les calculs,
conserve les emplacements source et vérifie le nombre/contenu des messages.
L'autre possibilité est de rendre les appels de traduction explicites dans le
code, mais elle augmente le diff sans être nécessaire au portage de l'interface.
Ne pas livrer l'adaptateur exploratoire basé sur `ast.unparse` tel quel : les
numéros de ligne et chemins du catalogue doivent aussi rester exploitables.

Ensuite : extraction avec `pylupdate6`, vérification des `.ts`, compilation avec
**`lrelease` Qt6** fourni par le SDK/outillage Qt, et tests de chargement.
Pour les dialogues propres à Qt Widgets, utiliser les catalogues **`qtbase_*`**
correspondant à Qt6, par exemple depuis
`QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)`, plutôt que
supposer que les anciens `qt_*.qm` couvrent les nouveaux textes.
[2](https://doc.qt.io/qt-6/localization.html)

L'extraction et la compilation sont deux étapes différentes : `pylupdate6` ne
remplace pas `lrelease` et installer les seules wheels runtime ne fournit pas
nécessairement tout le SDK Linguist.

## 6. Compatibilité, HiDPI et maintenance

### Versions visées

Au jour de l'audit, les versions installables retenues sont **PyQt6 6.11.0** et
**Qt runtime 6.11.2**. Les métadonnées de la wheel PyQt6 imposent **Python ≥ 3.10**.
La page d'introduction Riverbank affiche encore un minimum 3.9 : pour cette
version précise, se fier aux métadonnées du paquet effectivement installé.
[1](https://pypi.org/project/PyQt6/) [2](https://pypi.org/project/PyQt6-Qt6/)

Le minimum de la wheel x86_64 Linux est **glibc 2.34** ; celui de la wheel ARM64
actuelle est **glibc 2.39**. La liste des plateformes Qt prises en charge et les
contraintes d'une wheel PyPI ne sont pas la même chose. Une vieille distribution
peut nécessiter un paquet natif adapté ou une compilation, pas une installation
aveugle de la wheel la plus récente.

Les plateformes bureau officiellement listées pour **Qt 6.11** comprennent
Windows 10 **1809 ou ultérieur** et Windows 11, ainsi que macOS **13 ou ultérieur**.
L'ancien document du projet promettant Windows XP/Vista/7 doit être actualisé ;
ces promesses ne conviennent pas à une nouvelle diffusion Qt6. Ce rapport ne
certifie pas les plateformes qu'il n'a pas testées.

Le support standard Qt 5.15 s'est terminé le **26 mai 2025**, avec des services
ESM/Extended Support possibles. Cela ne signifie pas qu'aucun paquet Qt5 ou
correctif de distribution n'existe encore : la wheel Linux 5.15.19 utilisée ici
est effectivement disponible en 2026.
[3](https://www.qt.io/blog/extended-security-maintenance-for-qt-5.15-begins-may-2025)

Qt 6.11 est listé avec un support standard commercial jusqu'au **17 mars 2027**.
Les maintenances prolongées des séries LTS ont des conditions commerciales : ne
pas promettre toutes les mises à jour LTS simplement parce qu'une version pip
porte le même numéro de série.

### HiDPI, écrans et préférences

Qt6 active automatiquement la gestion HiDPI et change la politique d'arrondi
par défaut des facteurs d'échelle. Je testerai **100/125/150/175/200 %**, les
boutons, le tableau, les icônes, le thème sombre et les boîtes de dialogue.
Les tailles et positions mémorisées doivent être testées en multi-écrans, avec
un écran retiré, ainsi que sous Wayland.

Le code utilise déjà `QScreen`. Il faut conserver les clés de préférences
historiques — y compris `RemenberDlgPos` — pour ne pas perdre les réglages, et
éviter une refonte de la configuration en même temps que le port.

Un essai de compatibilité a chargé sous Qt6 la chaîne de police Qt5
`DejaVu Sans,10,-1,5,50,0,0,0,0,0` : `fromString()` réussit et le poids normal
est converti de 50 à 400. **Pas de conversion manuelle ×10 à ajouter pour ce cas.**
Il reste à tester les polices personnalisées réelles et les préférences des
utilisateurs sur les systèmes cibles.

## 7. Comment je ferai la migration de production

### Étape A — Figer puis assainir Qt5

1. Créer le brouillon de référence du commit actuel avec l'archive et son hash.
2. Corriger les nombres Unicode et le test `--test`, indépendamment de Qt.
3. Traiter les références invalides des données locales et vérifier les valeurs.
4. Ajouter les tests du moteur, les cas invalides et les tests CLI/code de sortie.
5. Publier une baseline Qt5 corrigée si « Latest » doit signifier stable, avec
   une version et un commit cohérents.

**Critère de sortie :** zéro défaut de définition dans les langues annoncées
comme prises en charge ; tests positifs et négatifs reproductibles. Si les
langues défectueuses sont conservées avant correction, leurs limites doivent
être explicitement annoncées, pas masquées par les 50 contrôles GUI.

### Étape B — Porter seulement l'interface vers PyQt6

- Partir de Qt5.15 et qualifier les enums / utiliser `exec()` là où c'est
  compatible avec la baseline PyQt5 moderne.
- Passer les 11 modules à PyQt6.
- Corriger les palettes dynamiques, `qApp`, `QFontDatabase`, `QAction` et le signal
  `highlighted`, selon les modifications déjà éprouvées dans le prototype.
- Garder les algorithmes et formats de données constants pendant cette étape.
- Mettre à jour les contrôles de dépendances et la documentation.

**Critère de sortie :** même corpus de résultats numériques, aucun nouveau
plantage, tous les dialogues couverts. Pas de PySide6, QML, changement de moteur
ou changement esthétique important mélangé à ce commit.

### Étape C — Traductions et ressources

- Finaliser l'extraction compatible avec `_()` et préserver les contextes.
- Actualiser les catalogues applicatifs et les catalogues `qtbase` Qt6.
- Centraliser la résolution des ressources pour le lancement depuis les sources,
  une installation et un bundle. Préférer des chemins ancrés dans `__file__`/
  le bundle plutôt que le répertoire courant ou des hypothèses fragiles sur
  `sys.path[0]`.
- Vérifier l'aide, les icônes, les données et les traductions depuis un répertoire
  de travail quelconque.

### Étape D — Packaging et CI

- Choisir un seul outil de gel principal, **PyInstaller**, avec une version
  verrouillée et un environnement sans l'autre binding Qt.
- Remplacer le chemin absolu local du `.spec` et réviser les suppressions
  manuelles de DLL : les plugins Qt6 peuvent dépendre des bibliothèques retirées.
- L'ancien `setup.py` cx_Freeze cible encore un dossier `convertall-0.7` ; ne pas
  le réutiliser comme procédure de release 0.8/0.9 sans révision.
- Moderniser les `.iss` : version, chemins, architecture, manifeste et disposition
  réelle du bundle ; ne pas se limiter à remplacer `PyQt5` par `PyQt6`.
- Commencer par un **onedir** testé. Le onefile ajoute un bootloader/extraction
  et peut modifier le fonctionnement des réglages portables : essai séparé.
- Construire et tester nativement sur Windows et sur la plus ancienne Linux
  que l'on souhaite réellement distribuer.
- Ajouter une CI pour le moteur et les smoke tests, au minimum Linux/Windows
  et Python 3.10 + une version récente supportée. Mesurer sur des runners
  comparables, sans traiter la CI partagée comme un laboratoire de performance.

### Étape E — Validation native et release Qt6

- Tests manuels HiDPI/multi-écrans, français et autres langues annoncées,
  thème sombre, focus/clavier, aide, fichiers et préférences portables.
- Machine Windows propre sans Python ; installation utilisateur/global si les
  installateurs sont fournis ; désinstallation et mise à jour d'une Qt5 existante.
- Nouveau benchmark natif du démarrage, RSS et taille des assets finaux.
- Publier d'abord **une prérelease Qt6**, par exemple `v0.9.0-rc1`, avec
  **`--prerelease --latest=false`**, sans détrôner la Qt5 stable.
- Passer la Qt6 stable en Latest uniquement après les critères de validation.
  Conserver le tag Qt5 et ses assets comme référence de retour arrière.

**Estimation indicative, pas un engagement de délai :** environ une demi-journée
à une journée pour l'interface et sa mise au propre ; plusieurs jours pour la
qualité des données, les traductions et la validation native/packaging, selon
les systèmes et langues conservés. Le prototype réduit fortement l'incertitude
sur les changements d'API, mais ne remplace pas ces étapes de diffusion.

## 8. Sources consultées et portée de leurs informations

Priorité donnée aux documents des mainteneurs et aux métadonnées des paquets,
plutôt qu'à des dates d'EOL ou comparaisons de performance non vérifiées.

- Riverbank — différences PyQt5/PyQt6 :
  [1](https://www.riverbankcomputing.com/static/Docs/PyQt6/pyqt5_differences.html).
- Qt — guide de portage, départ depuis Qt5.15, Widgets et HiDPI :
  <https://doc.qt.io/qt-6.11/portingguide.html>.
- Qt — changements Qt Widgets :
  [9](https://doc.qt.io/qt-6/widgets-changes-qt6.html).
- Qt — changements Qt GUI, dont `QFontDatabase` :
  [1](https://doc.qt.io/qt-6/gui-changes-qt6.html).
- Qt — signature actuelle de `QTextBrowser.highlighted` :
  [3](https://doc.qt.io/qt-6/qtextbrowser.html).
- Riverbank — internationalisation et syntaxe de `pylupdate6` :
  <https://www.riverbankcomputing.com/static/Docs/PyQt6/i18n.html>.
- Qt — catalogues par module, dont `qtbase` pour Widgets :
  [2](https://doc.qt.io/qt-6/localization.html).
- PyPI — versions, `Requires-Python`, wheel tags et runtimes réellement disponibles :
  [1](https://pypi.org/project/PyQt6/),
  [2](https://pypi.org/project/PyQt6-Qt6/),
  [1](https://pypi.org/project/PyQt5-Qt5/),
  ainsi que leurs endpoints JSON interrogés pendant l'audit.
- Qt — plateformes et dépendances Linux **6.11**, pas une liste non versionnée :
  <https://doc.qt.io/qt-6.11/supported-platforms.html>,
  <https://doc.qt.io/qt-6.11/linux-requirements.html>.
- Qt — périodes de support et conditions LTS :
  <https://doc.qt.io/qt-6.11/qt-releases.html>,
  [3](https://www.qt.io/blog/extended-security-maintenance-for-qt-5.15-begins-may-2025).
- Riverbank — licence PyQt6 :
  <https://www.riverbankcomputing.com/static/Docs/PyQt6/introduction.html#license>.
- PyInstaller — disposition `_internal`, `--contents-directory`, chemins de données
  et informations du bundle :
  <https://pyinstaller.org/en/stable/usage.html>,
  <https://pyinstaller.org/en/stable/runtime-information.html> ;
  limitation des bindings multiples :
  [1](https://pyinstaller.org/en/v6.5.0/CHANGES.html).
- GitHub CLI — création et publication de releases :
  [1](https://cli.github.com/manual/gh_release_create),
  <https://cli.github.com/manual/gh_release_edit>.

Enfin, la version **1.x actuelle de ConvertAll sur le site amont est une
réécriture Dart/Flutter depuis 2023**, pas la version Python/PyQt de ce dépôt.
Il ne faut pas utiliser son numéro 1.0.3 pour nommer cette baseline Python.
[1](https://convertall.bellz.org/)

**Verdict final : portage PyQt6 conseillé et faisable sans réécriture du moteur ;
publication Qt5 de référence d'abord, correction des défauts existants, puis
migration UI, traductions, packaging et validation native.**
