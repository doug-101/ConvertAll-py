# ConvertAll 0.9.1 / Qt6 — validation et release

**Code candidat, pas certification.** Aucun test, installation ni build Qt6
n'a été exécuté par l'agent pour ce portage ; l'utilisateur les exécute.
Le benchmark historique 0.8.0 et la CI Qt5 verte ne sont pas des résultats Qt6.

### Premier retour utilisateur et correctif (10 octobre 2026)

Au SHA **`6a51c01fe9a900db2d56a5183e2344529304dc39`**, Linux/Python 3.11.2,
glibc 2.36, PyQt6 6.11.0 / Qt 6.11.2 : **4553 PASS, 9 FAIL, 0 ERROR,
0 SKIP**, 58,59 s pytest, **90,46 %** de couverture. Le build/checker natif
n'ont pas été exécutés, conformément au gate source en échec.

Deux causes : import `QFont` manquant lors de la restauration des fontes (8
échecs) ; diagnostic SIP comparant `sip.SIP_VERSION_STR` **6.17.0** au paquet
**PyQt6-sip 13.13.0** (1 échec). Le correctif importe réellement QFont,
sépare les champs JSON `sip_package` / `sip_generator`, conserve le contrôle
du paquet épinglé et embarque ses métadonnées dans le bundle et les recettes
Inno. Sans ces métadonnées, le diagnostic échoue au lieu d'inventer une version.

Ce premier rapport n'est **pas** une validation du correctif. Après `git pull`,
les dépendances n'ayant pas changé, le même venv peut être réutilisé :

```bash
bash test_all_qt6.sh --no-install --python .venv/test-all-qt6/bin/python
```

Le lanceur reteste tout puis construit/contrôle le bundle si la suite passe.

### Deuxième retour utilisateur : sources/bundle et CI verts

Au SHA **`a72ee1dc5b8cdfe0c58fef0f182f15530e94a081`**, l'utilisateur obtient
**4575 PASS / 0 échecs / 0 erreurs / 0 skips**, 72,49 s pytest, **90,70 %**
de couverture ; build Linux et checker natif PASS, arbre propre.
La [CI 38082849472](https://github.com/jojo8356/ConvertAll-py/actions/runs/38082849472)
est verte pour les huit tests et les deux bundles du **même SHA**.
Ce rapport ne certifie ni le bureau réel ni les nouvelles recettes Debian/
AppImage ajoutées ensuite : voir [RELEASE_LINUX_FR.md](RELEASE_LINUX_FR.md)
et `release_qt6.sh`. Le lanceur release revalide son nouveau SHA et prépare
exécutable Linux, `.deb`, `.AppImage`, ZIP Windows avec `.exe` et sources.

Qt5 0.8.1 reste au SHA `b10b8e7837e30a2ec9a957a9a2519e4ac0334db3`.
Ne pas modifier `v0.8.1` ni fabriquer ses assets depuis les sources Qt6.
Le workflow Qt5 manuel extrait ce commit. Le nouveau workflow Qt6 teste le
nouveau commit avec le nouveau profil, sans publication automatique.

## Paquet Debian 0.9.1 sans runtime embarqué

La 0.9.0 au SHA `a3b93db8aed87787c531c6067c43199e4d48159a` a atteint la
création du draft utilisateur, avec archive portable, ancien `.deb` autonome,
AppImage et ZIP Windows. Son tag est immuable ; publication utilisateur non
confirmée ici. La 0.9.1 change le `.deb` : code/ressources uniquement,
`Architecture: all`, dépendances Python/PyQt6/Qt/SIP résolues par APT.
Voir [RELEASE_LINUX_FR.md](RELEASE_LINUX_FR.md). Les nouveaux profils Debian
Bookworm/Trixie sont distincts des pins des bundles, et doivent être validés
au nouveau SHA ; aucun résultat 0.9.0 ne leur est attribué.

## 1. Mise à jour puis un seul lancement

Sur la branche de session, depuis la racine de votre clone :

```bash
set -euo pipefail
test "$(git branch --show-current)" = 'arena/0adacf84-convertall-py'
git pull --ff-only origin arena/0adacf84-convertall-py
bash test_all_qt6.sh
```

Ce lanceur prépare `.venv/test-all-qt6`, installe `requirements-test.txt` et
`requirements-build.txt`, exécute la suite et la couverture, puis construit
et teste le bundle seulement si la suite source réussit. Git et Python
3.11–3.14 sont requis. Utiliser Git Bash avec un Python Windows pour Windows,
pas WSL pour prétendre construire un bundle Windows.

Premier diagnostic plus rapide (pas une validation binaire) :

```bash
bash test_all_qt6.sh --no-build
```

Pour réutiliser sans installation le venv dédié :

```bash
# Linux/macOS
bash test_all_qt6.sh --no-install --python .venv/test-all-qt6/bin/python
# Windows Git Bash
bash test_all_qt6.sh --no-install --python .venv/test-all-qt6/Scripts/python.exe
```

Sur Debian/Ubuntu, **à installer vous-même seulement si nécessaire** :

```bash
sudo apt-get update
sudo apt-get install python3.11-venv libpython3.11 libgl1 libegl1 libxkbcommon0 libdbus-1-3 libfontconfig1 libfreetype6 fonts-dejavu-core libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xkb1 libx11-xcb1 libxcb-shape0 libxcb-randr0 libxcb-xfixes0 libxcb-sync1
```

Adapter les noms de Python à votre distribution. Le script n'exécute pas sudo,
ne supprime pas un venv incomplet, et explique la réparation ensurepip.
Windows utilise ses fontes système, sans téléchargement de fontes par les tests.

### À transmettre

Le script affiche en fin de parcours :

- `build/qt6-diagnostics/<run>/SUMMARY.txt` : résumé texte à copier ;
- `build/qt6-diagnostics/qt6-results-<run>.tar.gz` : JUnit, couverture,
  provenance, environnement, rapport du bundle et logs de chaque étape.

L'archive ne contient ni venv ni gros bundle ni inventaire complet des variables
d'environnement. Le bundle reste sous `build/qt6-native/<run>/dist/convertall/`.
Codes de sortie : 0 = étapes demandées réussies, 1 = échec, 2 = prérequis absent.
`PASS_SOURCE_SEULEMENT` ne signifie pas bundle validé.

## 2. Gates et provenance

La CI `.github/workflows/qt6-release.yml` comporte huit jobs tests
(Ubuntu 24.04 et Windows 2022 × Python 3.11/3.12/3.13/3.14), puis deux jobs
bundles Python 3.11 qui dépendent de **toute** la matrice. Deux jobs
natifs Debian Bookworm/Trixie s’ajoutent pour tester le `.deb` léger sur Qt
distribution. Le lanceur release exige la réussite des douze jobs.

Le gate refuse profils non épinglés, autres bindings installés, runtime chargé
différent des roues, SHA CI différent de `GITHUB_SHA`, changement de commit
ou d'entrées pendant les tests. La CI demande un arbre Git propre. Les rapports
incluent SHA, branche, dirty avant/après, hashes d'entrée, versions réelles,
commande exécutée, code pytest, JUnit et couverture sous-processus.

Commandes directes, si vous ne souhaitez pas le lanceur :

```bash
python -m pip install -r requirements-test.txt
python tools/validate_release.py --require-clean
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --clean source/convertall.spec
python tools/check_bundle.py dist/convertall --report build/test-results/bundle-validation.json
```

Le checker vérifie le runtime **des exécutables**, les 7 catalogues, des
références numériques, les traductions applicatives/widgets Qt6 internes au
bundle et les deux points d'entrée. Son rapport conserve les hashes des
fichiers du bundle et le SHA du **checkout du checker**. Ce n'est pas une
preuve indépendante du commit de compilation d'un binaire arbitraire : garder
le lien avec les logs et le run CI qui construisent ce même SHA.

Un gate de développement sans `--require-clean` peut réussir sur arbre dirty
ou extrait ; il l'indique avec `release_eligible: false`. Ce résultat ne sert
pas à publier. Toute modification du code/config/traductions après QA implique
un nouveau commit et une nouvelle validation. Ne pas renommer un ancien log
pour le faire correspondre à un autre SHA.

## 3. Acceptation manuelle avant publication

Ne pas confondre offscreen et bureau réel. Sur Linux et Windows :

- démarrage normal, saisie clavier/souris, filtre et tri, menus récents,
  conversions aller/retour, expressions et unités incompatibles ;
- bases/fractions, options OK/Annuler, couleurs, fontes et aide/liens ;
- langues applicatives et widgets ; reprise des préférences Qt5, unités récentes ;
- DPI 100/125/150/200 %, changement d'écran/DPI, coordonnées négatives,
  retrait d'un écran puis réouverture, fenêtres/titres accessibles ;
- X11 et Wayland selon votre bureau, pilotes graphiques réels ;
- installation puis lancement/désinstallation Unix dans un préfixe dédié,
  conservation des préférences ; ne jamais tester en détruisant le vrai HOME.

Pour Inno Setup : recettes `.iss` alignées Qt6/x64 et Windows 10, nécessitant
Inno Setup 6.3+ pour `x64compatible`. Compiler depuis les fichiers du bundle
Windows validé, puis accepter réellement installation utilisateur/admin,
portable, migration depuis Qt5 et désinstallation. La CI PyInstaller **ne
compile/certifie pas Inno**. Ne pas publier un `.exe` installateur non testé.
macOS n'est pas inclus dans notre matrice ; pas de certification macOS ici.
Vérifier les obligations de redistribution de `LICENCES_QT6_FR.md` avant de
publier des binaires. Le bundle CI n'est pas un inventaire complet de licences.

## 4. Créer le draft source à partir du run CI vert

**À faire uniquement après validation/acceptation.** Le bloc Bash ci-dessous
est autonome : il initialise toutes ses variables, trouve le run push vert du
SHA actuel, télécharge son archive source, en vérifie la provenance et refuse
un tag existant visant un autre commit. Il ne retargete aucun tag et ne publie
pas en Latest. Il crée un draft contenant les trois assets source de la CI.

Le run doit être un **push marqué** : le workflow Qt6 ne s'exécute que si le
message du commit contient `[PROD]` (voir `doc/RELEASE_LINUX_FR.md` §4). Un
commit ordinaire ne lance aucun job, donc un lancement manuel seul ne fournit
pas le run exigé par la release.

```bash
set -euo pipefail
REPO='jojo8356/ConvertAll-py'
BRANCH='arena/0adacf84-convertall-py'
TAG='v0.9.1'
ASSET='ConvertAll-0.9.1-qt6-source.tar.gz'
test "$(git branch --show-current)" = "$BRANCH"
test -z "$(git status --porcelain)"
SHA=$(git rev-parse HEAD)
test "${#SHA}" -eq 40
if test -x .venv/test-all-qt6/bin/python; then
  PYTHON='.venv/test-all-qt6/bin/python'
else
  PYTHON='.venv/test-all-qt6/Scripts/python.exe'
fi
test -x "$PYTHON"
gh auth status
test "$(gh api "repos/$REPO/commits/$SHA" --jq .sha)" = "$SHA"
RUN_ID=$(gh api "repos/$REPO/actions/workflows/qt6-release.yml/runs?branch=$BRANCH&head_sha=$SHA&event=push&status=success&per_page=100" \
  --jq '.workflow_runs | map(select(.event == "push" and .conclusion == "success")) | first | .id // empty')
test -n "$RUN_ID"
test "$(gh api "repos/$REPO/actions/runs/$RUN_ID" --jq .head_sha)" = "$SHA"
printf 'SHA=%s\nRUN_ID=%s\n' "$SHA" "$RUN_ID"
gh run view "$RUN_ID" --repo "$REPO"
# Utiliser un dossier neuf : gh refuse d'écraser des téléchargements existants.
ASSETS_DIR="dist/qt6-release-$SHA-$RUN_ID"
test ! -e "$ASSETS_DIR"
mkdir -p "$ASSETS_DIR"
gh run download "$RUN_ID" --repo "$REPO" --name "qt6-source-$SHA" --dir "$ASSETS_DIR"
"$PYTHON" - "$ASSETS_DIR" "$ASSET" "$SHA" <<'PY'
import hashlib, json
from pathlib import Path
import sys
folder, name, sha = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
archive = folder / name
metadata = json.loads(archive.with_name(name + '.provenance.json').read_text(encoding='utf-8'))
assert metadata['source_commit'] == sha, metadata
assert metadata['version'] == '0.9.1' and metadata['binding'] == 'Qt6', metadata
digest = hashlib.sha256(archive.read_bytes()).hexdigest()
assert digest == metadata['sha256'], metadata
assert archive.with_name(name + '.sha256').read_text(encoding='ascii').strip() == f'{digest}  {name}'
print('Archive CI, SHA et checksum vérifiés :', archive)
PY
# Refuser tout tag préexistant visant un autre SHA, y compris un tag annoté.
if REF=$(gh api "repos/$REPO/git/ref/tags/$TAG" --jq '.object.sha + " " + .object.type'); then
  read -r TARGET TYPE <<< "$REF"
  while test "$TYPE" = tag; do
    REF=$(gh api "repos/$REPO/git/tags/$TARGET" --jq '.object.sha + " " + .object.type')
    read -r TARGET TYPE <<< "$REF"
  done
  test "$TYPE" = commit
  test "$TARGET" = "$SHA"
else
  gh api --method POST "repos/$REPO/git/refs" -f ref="refs/tags/$TAG" -f sha="$SHA"
fi
gh release create "$TAG" --repo "$REPO" --verify-tag --draft \
  --title 'ConvertAll 0.9.1 — Qt6' --notes-file doc/RELEASE_NOTES_0.9.1.md \
  "$ASSETS_DIR/$ASSET" "$ASSETS_DIR/$ASSET.sha256" "$ASSETS_DIR/$ASSET.provenance.json"
```

Si le draft existe déjà, **ne pas supprimer/retargeter le tag** pour recommencer.
Consulter son SHA/assets ; corriger le draft volontairement, pas par force.
Une erreur d'authentification GitHub doit être réparée via la connexion Arena,
pas en collant des credentials dans le chat.

L'archive produite manuellement par `tools/release_source.py --commit SHA`
doit venir d'un HEAD propre validé et porte le même nom/provenance ; la voie CI
ci-dessus évite de recomprimer sur un environnement zlib différent. Pour les
bundles, récupérer `qt6-bundle-ubuntu-24.04` / `qt6-bundle-windows-2022` et leurs
rapports, conserver la liaison SHA/run, recontrôler sur la plateforme réelle,
puis archiver avec permissions/checksums avant ajout volontaire au draft.

Compléter le **texte du draft** avec résultats réellement observés et limites
sans modifier l'arbre source déjà validé. Ou, si les sources/notes commitées
changent, refaire la QA du nouveau SHA. Pas de chiffres Qt5 reportés sous Qt6.

## 5. Passer le draft en Latest — action séparée

Seulement après revue des assets, résultats, licences et checklist ci-dessus.
Ce bloc est lui aussi autonome, sans variables héritées du bloc précédent :

```bash
set -euo pipefail
REPO='jojo8356/ConvertAll-py'
TAG='v0.9.1'
gh release view "$TAG" --repo "$REPO"
gh release edit "$TAG" --repo "$REPO" --draft=false --prerelease=false --latest
```

Ce n'est pas une commande à exécuter maintenant par défaut. Si la QA est rouge
ou incomplète, conserver le draft ; ne pas remplacer la Latest Qt5 valide.
Les tags publiés restent immuables. Aucun `--force`, aucun tag flottant `latest`.
