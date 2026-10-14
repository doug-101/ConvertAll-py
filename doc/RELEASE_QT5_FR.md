# ConvertAll 0.8.1 — validation et publication de la release Qt5

> **Guide historique Qt5.** Les sources actuelles sont Qt6 0.9.0 : ne pas
> exécuter les profils/commandes Qt5 ci-dessous sur cet arbre. La référence
> Qt5 validée finale est `b10b8e7837e30a2ec9a957a9a2519e4ac0334db3`
> (CI utilisateur `38075371349`). Utiliser son checkout/archive séparé,
> sans retargeter `v0.8.1`. Voir `RELEASE_QT6_FR.md` pour les nouvelles sources.

**Préparation du 10 octobre 2026.** Cette maintenance conserve **PyQt5** : elle
n'effectue pas la migration Qt6. La version `0.8.1` doit désigner le **nouveau
commit contenant les corrections et tests**, jamais le commit historique
`a71219904b6a27e7578744afcfa227b21fc73fb2` de 0.8.0.

> Rien n'a été committé, poussé, tagué ou publié pendant cette préparation.
> Les résultats locaux portent sur l'arbre de travail corrigé. Il faut refaire
> la validation après votre commit, puis attendre la CI du **même SHA**.

## 1. Ce qui a effectivement été créé

| Domaine | Contrôles automatisés |
|---|---|
| Données | Chacune des **4 104 définitions**, dans les sept catalogues, doit être chargée, sélectionnable par son nom, réductible et convertible aller-retour via les unités fondamentales. Comptages fixes, doublons, noms réservés, relecture, fichier malformé/absent et fallback régional. |
| Moteur | Valeurs de référence indépendantes : longueur, masse, volume, vitesse, temps, énergie, pression, angles, puissances/fractions, Celsius/Fahrenheit/Kelvin, logarithmes et interpolations. Constantes très petites vérifiées avec tolérance relative, sans tolérance absolue masquant un zéro. Valeurs négatives, zéro, erreurs de domaine, références absentes et cycles. |
| CLI | Vrais sous-processus, sortie numérique, précision/notation, unités avec espaces, `--` et nombres négatifs, mode interactif, EOF, erreurs et codes de sortie. `--test`, `--test-all`, `--version`, vrai `main()`/boucle Qt avec `--gui-smoke-test`. Une barrière d'import interdit QtWidgets/QtGui en CLI. |
| Interface Qt5 | Vrais widgets, clavier, signaux, conversion bidirectionnelle, expressions numériques, unités composées, filtrage, tri, navigation/completion, boutons, menus, préférences accepter/annuler, historique, fermeture/réouverture, fontes, couleurs, aide, bases, fractions et erreurs numériques. |
| Traductions/ressources | Les six catalogues applicatifs QM sont comparés à leurs messages TS actifs et à leurs paramètres `{0}`/`{1}`. Catalogues Qt présents, fallback `qtbase` catalan, locales régionales/système, icônes et aide HTML. Les messages obsolètes/inachevés ne sont pas présentés comme des traductions complètes. |
| Préférences | HOME/APPDATA isolés, valeurs par défaut et fallback, UTF-8, commentaires, configuration portable, historique et conservation de la clé historique `RemenberDlgPos`. |
| Installation Unix | Installation et désinstallation sans root, préfixe temporaire contenant espaces/apostrophe, ressources et CLI installée, avec/sans traductions, DESTDIR et conservation des sources originales. Les tests Unix sont explicitement exclus sous Windows. |
| Release source | Versions cohérentes, compilation Python, profil exclusivement Qt5, recette de packaging, archive Git du commit exact, en-tête/provenance du commit, SHA256, reproductibilité dans un même environnement et exécution depuis extraction. Refus d'un arbre sale ou d'un autre commit. |
| CI/binaire | Workflow Linux/Windows sur Python **3.10, 3.11, 3.14**. Après les tests : builds PyInstaller natifs et contrôles des exécutables CLI/GUI, sept catalogues, traductions et ressources. Actions épinglées par SHA ; aucun job de publication automatique. |

### Fichiers utiles

- `tests/` : suite applicative pytest/pytest-qt et intégration.
- `tools/test_qt_migration_tools.py` : huit anciens tests des outils de recherche,
  également exécutés par la suite.
- `pytest.ini`, `.coveragerc`, `requirements-{qt5,test,build}.txt` : configuration.
- `tools/validate_release.py` : porte de validation, environnement épinglé,
  couverture et empreintes des fichiers.
- `tools/release_source.py` : archive d'un **HEAD propre et committé**, sans
  commit/tag/push/publication.
- `source/convertall.spec`, `tools/check_bundle.py` : build et contrôles natifs.
- `.github/workflows/qt5-release.yml` : matrice et artefacts CI.
- `doc/RELEASE_NOTES_0.8.1.md` : notes prêtes pour le brouillon GitHub.

## 2. Correctifs protégés par ces tests

- `--test` ne tente plus d'appeler la méthode inexistante `UnitDatum.unitValid`.
  Les erreurs et cycles sont signalés sans traceback ; les échecs rendent un
  code non nul. Codes CLI : **0** succès, **1** données/conversion, **2** syntaxe,
  **130** interruption. Les options inconnues ne déclenchent plus accidentellement
  l'interface. Les diagnostics ne créent pas de fichier de préférences.
- Six exposants Unicode négatifs des constantes anglaises corrigés ; références
  catalanes/suédoises réparées. Alias suédois `ct` (masse, pas pureté de l'or),
  `kph` (vitesse, pas longueur/masse) et kilotonne non métrique vérifiés numériquement.
- Deux noms catalans de tailles de chaussures perdent les parenthèses réservées
  au regroupement. En suédois, `ton*` devient `kort ton` et `kiloton*` devient
  `kiloton icke-metriskt`. Un ancien favori contenant ces noms doit être resélectionné.
- Rechargement des données idempotent et atomique pour les définitions/types ;
  les références invalides et facteurs non représentables produisent une erreur
  du domaine, pas un déréférencement de `None`.
- Reprise des dernières unités au démarrage avec texte et conversion effectifs.
  Affichage décimal signé en complément à deux, limites d'overflow et fractions
  à dénominateurs puissances de deux corrigés. Erreurs/valeurs non finies traitées
  sans exception échappant des slots testés. Les fractions continues remplacent
  la recherche pouvant parcourir un milliard de dénominateurs pour les
  irrationnels/petites décimales ; un sous-processus borné protège ce cas.
- Wrapper Unix et chemins Python correctement cités. Le catalogue `qt_ca.qm`
  de 146 octets était un simple renvoi vers des fichiers absents : retiré au
  profit du vrai `qtbase_ca` du runtime Qt5. La recherche système utilise QLocale,
  sans `locale.getdefaultlocale()` déprécié.
- Version **0.8.1** cohérente dans application, recettes et en-têtes documentaires.
  Les anciennes entrées de changelog/liens 0.8.0 restent historiques.

## 3. Résultats locaux et limites

### Exécuté ici

- Debian 12 x86_64, **Python 3.11.2**.
- PyQt5 **5.15.11**, Qt Linux **5.15.19**, SIP **12.20.0**.
- Widgets sous `offscreen` ; préférences et installations isolées.
- **4 475 tests réussis, 0 échec, 0 skip** lors de la validation finale.
- Couverture applicative combinant instructions et branches : **environ 90 %** ;
  seuil bloquant **80 %**. Le script legacy cx_Freeze `setup.py` est exclu de la
  mesure : la chaîne de release cible PyInstaller et n'annonce pas un build
  cx_Freeze validé.
- Le test de non-régression ciblé initial a reproduit **quatre échecs** de l'ancien
  état : noms réservés et `--test` cassé. Un test supplémentaire a reproduit
  une recherche de fractions dépassant son timeout de 10 secondes. Ces défauts
  ont ensuite été corrigés.
- Les contrôles d'archives utilisent un dépôt/commit temporaires : ils ne créent
  pas le tag de publication et ne modifient pas le dépôt de travail.

Les résultats détaillés d'une exécution sont dans `build/test-results/` :
`junit.xml`, `coverage.xml`, `coverage.json`, `validation.json`. Ce dernier
contient versions, SHA Git, indicateur d'arbre sale et SHA256 des fichiers testés.
Ils sont ignorés par Git et sauvegardés comme artefacts par la CI.

### Retour de validation sur Debian en locale utilisateur

Le lancement utilisateur au commit `e521ae3` a produit **4 474 succès et un
échec**, couverture **89,98 %**, dans le contrôle générique de préférence
numérique. Le validateur Qt dépendait de la locale système alors que le champ
utilise `repr()` / `float()` avec un point décimal. Correctif ajouté : locale C
limitée à ce validateur et rejet des séparateurs de milliers, sans modifier la
locale générale de l'application. **27 contrôles de non-régression** C/français/
allemand ont été ajoutés. Au commit `9a16283`, l'utilisateur a confirmé **4 502
succès, zéro échec, zéro skip, couverture 90,15 %** sur Debian/Python 3.11.2/Qt
5.15.19. Le build PyInstaller et le contrôle du bundle Linux (CLI, sept
catalogues, traductions, GUI/ressources offscreen) ont également réussi. Aucun
test n'a été relancé ici après ces retours.

### Premier retour CI multiplateforme

La CI `38072767122`, au commit `9a16283`, a réussi les trois jobs Ubuntu/Python
3.10, 3.11 et 3.14, mais échoué les trois jobs Windows. Le rapport JUnit Windows
3.11 indique cinq échecs : deux contrôles de polices sans font directory en mode
offscreen, un wrapper POSIX utilisant le séparateur du système hôte, un manuel
UTF-8 lu via CP1252, et des clés d'empreintes contenant des antislashs. Correctifs
ajoutés sans retirer ces contrôles : `QT_QPA_FONTDIR` pointe sur les polices
Windows déjà installées, chemins de wrapper explicitement POSIX, lectures des
fichiers du dépôt explicitement UTF-8, clés de provenance via `as_posix()`.
Les six jobs tests et les deux builds du **nouveau SHA** restent à confirmer.
Les jobs bundle du premier run étaient ignorés, pas réussis.

### Pas encore validé ici

- **CI complète du candidat corrigé encore en attente** : le premier run a
  confirmé les trois jobs Linux, mais pas Windows ni les deux bundles CI.
  Ne pas présenter toute la matrice comme réussie avant un run entièrement vert.
- Tentative du **nouveau** spec PyInstaller local : arrêt avant l'analyse complète
  faute de `libpython3.11.so.1.0` dans ce sandbox. **Aucun binaire local validé.**
  Les runners `setup-python` doivent vérifier le build natif réel.
- Aucun installateur **Inno Setup** compilé/accepté, aucun macOS natif testé.
  Les deux recettes Inno ont leurs versions/layout actualisés, pas un certificat
  de fonctionnement. La recette cx_Freeze reste une voie legacy non validée.
- `offscreen` ne certifie pas X11/Wayland réels, presse-papiers, multi-écran,
  100/150/200 % de DPI, styles natifs, GPU, antivirus ou droits d'installation.
- Les bibliothèques ELF de recherche utilisées ici via `LD_LIBRARY_PATH` restent
  dans le cache local. **Ne pas les redistribuer** : utiliser les paquets système
  officiels sur votre machine/CI. Voir l'audit historique pour leur provenance.
- Des tests de cohérence/aller-retour ne prouvent pas à eux seuls la précision
  métrologique de toutes les définitions : les valeurs de référence indépendantes
  protègent les catégories/correctifs ciblés, pas tous les standards possibles.

**Décision :** préparer une release **source** 0.8.1 ; ne la publier comme stable
qu'après succès de la CI du commit final et revue de la checklist ci-dessous.
Ne pas joindre de binaires simplement parce que leurs recettes sont présentes.
Une release applicative stable ne rétablit pas le support sécurité amont de Qt5.

## 4. Refaire la validation sur votre machine

### Linux — environnement neuf

Depuis la racine du dépôt, avec Python 3.11 installé :

```bash
set -euo pipefail
python3.11 -m venv .venv/release
source .venv/release/bin/activate
python -m pip install -r requirements-test.txt
python tools/validate_release.py
```

Le script exige les versions du profil. Un environnement mélangé Qt5/Qt6 ou une
version différente doit être remplacé par un venv propre. Pour Debian/Ubuntu,
installer au besoin les dépendances Qt via les paquets officiels :

```bash
sudo apt-get update
sudo apt-get install -y libgl1 libegl1 libxkbcommon0 libdbus-1-3 \
  libxcb-xinerama0 libxcb-cursor0
```

Le script choisit `offscreen` par défaut si `QT_QPA_PLATFORM` n'est pas déjà fixé.
Pour une passe GUI visible, exécuter depuis une session graphique :

```bash
QT_QPA_PLATFORM=xcb python -m pytest -m gui
```

Adapter `xcb` à votre plateforme ; il ne s'agit pas d'un serveur Web.

### Windows — PowerShell

```powershell
py -3.11 -m venv .venv\release
& .\.venv\release\Scripts\python.exe -m pip install -r requirements-test.txt
& .\.venv\release\Scripts\python.exe tools\validate_release.py
if ($LASTEXITCODE -ne 0) { throw 'Validation Qt5 en échec' }
```

Qt5 Windows du profil PyPI est **5.15.2**, pas 5.15.19. Pour une passe visible,
mettre `$env:QT_QPA_PLATFORM = 'windows'` puis lancer les tests GUI. Ne pas appeler
les commandes Bash suivantes telles quelles depuis PowerShell ; utiliser Git
Bash, ou adapter explicitement leurs garde-fous et codes de sortie.

## 5. Commandes de publication source : commit → CI → brouillon → Latest

**Les commandes suivantes sont à exécuter par vous.** Elles n'ont pas été
exécutées pendant la préparation. GitHub est utilisé via `gh`, sans mot de passe
ou token à copier dans les commandes. Le travail reste sur la branche de cette
session, **`arena/0adacf84-convertall-py`**.

### A. Enregistrer puis tester le commit exact

Dans une session **Bash**, après création/activation du venv de la section 4 :

```bash
set -euo pipefail
REPO='jojo8356/ConvertAll-py'
BRANCH='arena/0adacf84-convertall-py'
VERSION='0.8.1'
TAG="v$VERSION"

# Refuser une mauvaise branche ; ne pas changer de branche.
test "$(git branch --show-current)" = "$BRANCH"
git diff --check
python tools/validate_release.py

# Relire le diff avant de créer votre commit.
git status --short
git diff --stat
git add README.md .gitignore .gitattributes .coveragerc pytest.ini \
  requirements-qt5.txt requirements-test.txt requirements-build.txt \
  source data translations install.py win doc docs tests tools .github
git commit -m "Prepare tested Qt5 maintenance release 0.8.1"

SHA=$(git rev-parse HEAD)
test "$SHA" != 'a71219904b6a27e7578744afcfa227b21fc73fb2'
test -z "$(git status --porcelain)"
test "$(python source/convertall.py --version)" = "ConvertAll $VERSION (Qt5)"

# Cette passe doit réussir sur le commit que vous allez réellement publier.
python tools/validate_release.py
test -z "$(git status --porcelain)"
git push origin arena/0adacf84-convertall-py
printf 'Commit candidat : %s\n' "$SHA"
```

Les rapports, venv, caches, `build/` et `dist/` ne sont pas ajoutés au commit.
L'ancien audit Qt6 conservé dans `doc/` décrit **0.8.0**, pas un nouveau benchmark
0.8.1. Une PR peut être revue ensuite depuis cette branche, mais aucune commande
ci-dessus ne change de branche ou ne pousse `master`.

### B. Attendre et vérifier la CI du même SHA

La recherche suivante fonctionne aussi avec `gh` 2.23 : elle ne dépend pas du
flag récent `gh run list --commit`.

```bash
RUN_ID=$(gh run list --repo "$REPO" --branch "$BRANCH" --limit 30 \
  --json databaseId,headSha,workflowName \
  --jq "[.[] | select(.headSha == \"$SHA\" and .workflowName == \"Qt5 release validation\")][0].databaseId")

# Si la CI n'est pas encore apparue, attendre puis relancer cette recherche.
test -n "$RUN_ID" && test "$RUN_ID" != 'null'
gh run watch "$RUN_ID" --repo "$REPO" --exit-status
test "$(gh run view "$RUN_ID" --repo "$REPO" --json conclusion --jq .conclusion)" = 'success'
```

Attendre **les six jobs tests et les deux jobs bundle**, pas seulement un test
Linux isolé. Si Actions est désactivé sur le fork, l'activer dans le dépôt et
relancer le workflow pour cette branche. S'il échoue, corriger/tester/committer,
pousser **la même branche**, puis recalculer `SHA` et sélectionner son nouveau
run. **Ne pas publier la stable en contournant un job en échec.**

### C. Créer et vérifier les assets du commit testé

```bash
# Refuser de publier un autre HEAD après un changement de code.
test "$(git rev-parse HEAD)" = "$SHA"
test -z "$(git status --porcelain)"
python tools/release_source.py --commit "$SHA" --output-dir dist/release

ASSET="ConvertAll-$VERSION-qt5-source.tar.gz"
(
  cd dist/release
  sha256sum --check "$ASSET.sha256"
)
python -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["source_commit"] == sys.argv[2]' \
  "dist/release/$ASSET.provenance.json" "$SHA"
```

Cette archive provient de `git archive` du SHA vérifié, pas d'une copie approximative
ou d'un `tar` du répertoire contenant caches/venv. Le timestamp et nom gzip sont
fixés ; les tests comparent deux créations dans un même environnement. Le JSON
de provenance et le checksum doivent rester joints au même asset.

Contrôle supplémentaire recommandé de **l'archive réelle** avant publication :

```bash
CHECK_DIR=$(mktemp -d)
tar -xzf "dist/release/$ASSET" -C "$CHECK_DIR"
PYTHON=$(python -c 'import sys; print(sys.executable)')
(
  cd "$CHECK_DIR/ConvertAll-$VERSION-qt5-source"
  "$PYTHON" tools/validate_release.py
)
```

Les tests créent eux-mêmes des dépôts et préfixes temporaires. Le contrôle de
l'archive n'exige pas qu'elle contienne votre `.git`. Les quelques outils de
publication/recherche, eux, ont besoin de Git installé sur la machine de test.

### D. Créer le tag immuable puis le brouillon

Cette variante crée le tag à travers l'API GitHub, **au SHA précis** : pas de
push vers une autre branche, pas de déplacement du tag de référence 0.8.0.
L'appel échoue si ce tag existe déjà ; ne pas le forcer.

```bash
# Dernières barrières avant toute création distante.
test "$(git rev-parse HEAD)" = "$SHA"
test -z "$(git status --porcelain)"
test "$(gh run view "$RUN_ID" --repo "$REPO" --json conclusion --jq .conclusion)" = 'success'

# Nouveau tag lightweight immuable. NE PAS ajouter --force ou supprimer un tag.
gh api --method POST "repos/$REPO/git/refs" \
  -f ref="refs/tags/$TAG" -f sha="$SHA"
test "$(gh api "repos/$REPO/git/ref/tags/$TAG" --jq .object.sha)" = "$SHA"

gh release create "$TAG" \
  "dist/release/$ASSET" \
  "dist/release/$ASSET.sha256" \
  "dist/release/$ASSET.provenance.json" \
  --repo "$REPO" --verify-tag --draft \
  --title "ConvertAll $VERSION — Qt5" \
  --notes-file doc/RELEASE_NOTES_0.8.1.md

gh release view "$TAG" --repo "$REPO"
```

Relire le brouillon et ses assets. En cas d'interruption après création du tag,
reprendre à `gh release create` seulement après avoir revérifié que le tag
existant pointe exactement vers `SHA`. Ne pas relancer la création du tag ni le
retargeter. Laisser le brouillon en place tant que les contrôles manuels ne sont
pas satisfaits. L'ancien snapshot éventuel `v0.8.0-qt5` reste inchangé.

### E. Publier comme stable « Latest »

Seulement après la checklist, la CI et la revue du brouillon :

```bash
test "$(gh api "repos/$REPO/git/ref/tags/$TAG" --jq .object.sha)" = "$SHA"
test "$(gh run view "$RUN_ID" --repo "$REPO" --json conclusion --jq .conclusion)" = 'success'
gh release edit "$TAG" --repo "$REPO" --draft=false --prerelease=false --latest
gh release view "$TAG" --repo "$REPO"
```

`--latest` fixe le **badge GitHub Latest**. Il ne faut pas créer de tag flottant
`latest`, ni modifier `v0.8.0-qt5` ou `v0.8.1` après publication. Un correctif
ultérieur reçoit une nouvelle version, par exemple `0.8.2`.

## 6. Binaires et checklist avant publication

### Construire et contrôler un bundle natif, séparément

Sur chaque OS cible, dans un venv Qt5 dédié :

```bash
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm --clean source/convertall.spec
python tools/check_bundle.py dist/convertall
```

Le spec utilise des chemins absolus calculés depuis son emplacement et un layout
plat `contents_directory='.'`. Windows produit **`convertall.exe` (GUI)** et
**`convertall_dos.exe` (CLI)**. Ne pas déduire qu'un bundle Windows marche à partir
d'un build Linux, ni appeler un bundle Ubuntu 24.04 un binaire Linux universel.
Les artefacts CI sont des résultats de QA, pas des installateurs publiés.

Pour fabriquer un installateur Inno, copier les fichiers du bundle Windows dans
un répertoire de staging plat puis compiler la recette `.iss` qui s'y trouve.
Les chemins `Source:` de la recette sont relatifs à ce répertoire. Tester
installation/désinstallation/mise à jour **sur une VM propre**, pour les deux
modes utilisateur et administrateur. Vérifier aussi les licences, avis et
obligations de distribution Qt/PyQt5/PyInstaller avant de joindre un binaire :
le `LICENSE` historique de l'application ne remplace pas les licences tierces.

### Checklist à remplir, pas des tests déjà effectués

- [ ] Commit final propre ; version 0.8.1 partout ; tests et hashes du même SHA.
- [ ] Six jobs tests et deux jobs bundle CI réussis pour ce SHA.
- [ ] Archive réelle extraite/retestée, checksum/provenance et tag revérifiés.
- [ ] Session graphique Linux réelle : lancement, conversions simples/composées,
  négatives, température, erreurs, menus, aide/icônes, police et couleurs.
- [ ] Windows réel : mêmes conversions ; historique conservé à la réouverture ;
  aucun modal inattendu, fenêtre visible et réglages persistants.
- [ ] Fenêtre déplacée/redimensionnée puis rouverte, écran débranché/multi-écran,
  échelles 100/150/200 %, champs lisibles et navigation au clavier.
- [ ] Coller des expressions/unités avec espaces ; caractères accentués,
  français/catalan/suédois et fallback d'une langue non fournie.
- [ ] Si un binaire est joint : machine cible **sans Python/PyQt préinstallés**,
  console CLI et GUI, ressources, antivirus ; package compatible avec l'OS annoncé.
- [ ] Si un installateur est joint : droits, chemins avec espaces, mise à jour,
  installation/désinstallation propre, mode portable et conservation des préférences.
- [ ] Notes et licences relues ; pas de promesse de validation Windows/macOS,
  Inno, DPI ou de support sécurité amont non effectivement acquise.

Aucune suite ne garantit l'absence universelle de bugs. Cette porte de validation
rend les critères vérifiables, reproduit les régressions connues et empêche de
confondre une recette/un workflow préparé avec un résultat de test obtenu.
