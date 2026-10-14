# Release Qt6 0.9.1 : `.deb` léger et bundles autonomes

À exécuter par l'utilisateur, pas par l'agent. `v0.9.0` reste au SHA
`a3b93db8aed87787c531c6067c43199e4d48159a` : aucun tag/asset publié n'est
retargeté ou remplacé automatiquement. Les nouvelles recettes et la version
0.9.1 attendent la validation de leur nouveau SHA.

## 1. Deux profils distincts

| Asset | Contenu/runtime |
| --- | --- |
| `convertall_0.9.1-1_all.deb` | Seulement code Python + ressources ; Python/PyQt6/Qt/SIP fournis par APT |
| `ConvertAll-0.9.1-qt6-linux-x86_64.tar.gz` | Exécutable et dossier complet autonome |
| `ConvertAll-0.9.1-x86_64.AppImage` | AppImage autonome en un fichier |
| `ConvertAll-0.9.1-qt6-windows-x86_64.zip` | Deux `.exe` et dossier complet de la même CI Windows |
| Archive source, `SHA256SUMS`, rapports | SHA/run, octets, versions réellement chargées et checksums |

Le `.deb` ne contient **aucun ELF, `.so`, PyQt6, libpython, Qt, roue,
.dist-info, bytecode ou environnement virtuel**. Il conserve les sept
catalogues, six QM applicatifs, PNG nécessaires, SVG du menu, aides et licences.
Les TS/scripts de build restent dans l'archive source, pas dans le paquet installé.
La charge utile est compressée en xz niveau 9 par dpkg-deb.

Le lanceur `/usr/bin/convertall` utilise **`/usr/bin/python3 -E -s`** ; il ne
cherche pas le Python du venv dans PATH. Les modules applicatifs sont sous
`/usr/share/convertall`, les aides sous `/usr/share/doc/convertall`.
`Architecture: all` décrit un paquet sans binaire spécifique à une architecture,
pas une certification bureau/GPU de toutes les machines.

Dépendances déclarées dans `Depends` :

- `python3 (>= 3.11)` ;
- `python3-pyqt6 (>= 6.4.2)` ;
- `python3-pyqt6.sip (>= 13.4.1)` ;
- `qt6-translations-l10n (>= 6.4.2)`.

APT résout les bibliothèques Qt/desktop transitives. Elles sont partagées avec
les autres applications, pas copiées dans le `.deb`. **Un fichier plus petit
ne supprime pas leur coût sur une machine qui ne les a pas encore.** Aucun
gain chiffré n'est annoncé avant mesure réelle.

Les bundles/AppImage gardent le profil épinglé PyQt6 6.11.0 / Qt 6.11.2 /
PyQt6-sip 13.13.0. L'installation source avec `install.py` garde son profil
historique épinglé ; le `.deb` dispose de son propre lanceur/QA natifs.

## 2. Préparer les dépendances (vous-même, si absentes)

```bash
sudo apt-get update
sudo apt-get install -y dpkg binutils squashfs-tools desktop-file-utils gh python3-pyqt6 python3-pyqt6.sip qt6-translations-l10n
```

Le venv `.venv/test-all-qt6` reste nécessaire pour les tests/bundles épinglés.
Le script n'exécute aucun apt, pip ou sudo. Les contrôles natifs refusent un
PyQt6 provenant d'un venv ou de `/usr/local`, même s'il a la bonne version.
Le champ Debian Maintainer est public et vient de l'identité Git locale ;
utiliser `--maintainer 'Nom <adresse>'` pour choisir une autre identité.

## 3. Tout tester en local avant la release (répétition)

### D'abord le mainteneur du `.deb` (une seule fois par shell)

Le champ `Maintainer` du paquet publié est vérifié **avant** toute commande
longue. Renseignez-le une fois :

```bash
export CONVERTALL_MAINTAINER="Your Name <you@example.com>"
```

Sans cette variable, `--maintainer "Name <email>"` fait la même chose, et à
défaut l'identité git locale est utilisée — mais seulement si elle est réellement
configurée (`git config --global user.name` / `user.email`). Un `git commit`
réussit même sans identité configurée : Git invente alors `login@machine`, une
adresse que ce script refuse de publier. C'est exactement ce qui a stoppé la
première tentative 0.9.1 (`Set --maintainer …`).

### Ensuite les deux commandes

Elles suffisent, et **aucune ne consomme de CI ni ne publie quoi que ce soit** :

```bash
bash test_all_qt6.sh                 # étapes 1-2 : venv, 4600+ tests, bundle PyInstaller
bash release_qt6.sh --local-only     # étapes 1-4 : + archive portable, .deb léger, AppImage
```

`--local-only` est une répétition : elle exige un arbre propre et le profil
épinglé, produit les mêmes assets dans `dist/qt6-release/<sha>-<stamp>/`,
écrit `local-rehearsal.json`, et **saute les étapes 5-7** (les `.exe` Windows et
l'archive source viennent de la CI, et il n'y a ni tag ni brouillon). Elle refuse
`--draft`, `--run-id` et `--wait-ci`, pour qu'une répétition ne puisse jamais
devenir une publication. Une fois la répétition verte, la vraie release reste
inchangée : commit marqué, push, `bash release_qt6.sh --wait-ci --draft`.

Pour rejouer seulement la fin d'une répétition qui a échoué (mêmes garanties que
pour une vraie release : chaque hash enregistré est revérifié) :

```bash
bash release_qt6.sh --local-only --resume
```

### Vérifier les assets à la main

```bash
ASSETS=$(ls -dt dist/qt6-release/* | head -1)

tar -xzf "$ASSETS"/ConvertAll-0.9.1-qt6-linux-x86_64.tar.gz -C /tmp/portable
/tmp/portable/ConvertAll-0.9.1-qt6-linux-x86_64/convertall --test-all

dpkg-deb -c "$ASSETS"/convertall_0.9.1-1_all.deb | head -20
sudo apt install "$ASSETS"/convertall_0.9.1-1_all.deb      # dans une VM de préférence

# AppImage : sans FUSE, et sans passer par un intergiciel binfmt
TOOLS=build/qt6-release/*/appimage-tools/runtime-x86_64
TARGET_APPIMAGE="$PWD/$ASSETS"/ConvertAll-0.9.1-x86_64.AppImage \
  $(ls $TOOLS | head -1) --appimage-extract-and-run --runtime-info
```

## 4. Construire et créer le draft 0.9.1

```bash
set -euo pipefail
export CONVERTALL_MAINTAINER="Your Name <you@example.com>"   # si pas déjà exporté
git pull --ff-only origin arena/0adacf84-convertall-py
bash release_qt6.sh --wait-ci --draft
```

`--resume` reprend la même variable d'environnement (ou `--maintainer`), donc un
seul export couvre la release, une reprise et une répétition.

Le lanceur exige la CI du SHA actuel : huit tests Ubuntu/Windows × Python
3.11–3.14, deux bundles et deux jobs **Debian native Qt / bookworm et trixie**.
Ces derniers utilisent Qt/PyQt6/SIP APT, un venv de tests avec
`--system-site-packages` et seulement les dépendances pytest (aucune roue Qt).
Ils exécutent les régressions moteur/GUI/CLI/traductions/préférences, avec le
seuil de couverture 80 % inchangé, puis construisent et contrôlent le `.deb`
avec `/usr/bin/python3` hors de ce venv. Les assertions du profil frozen restent
exécutées intégralement par les huit jobs épinglés.

Les contrôles de traductions natives sont exacts mais non naïfs : Debian ne
fournit pas forcément toutes les langues de widgets (`qtbase_sv` peut manquer).
Un catalogue présent doit charger ; un catalogue réellement absent doit être
signalé par l'application (`Warning: translation file ... could not be loaded`)
sans exception. Les six `convertall_*.qm` applicatifs restent obligatoires,
et leur absence échoue toujours. Les bundles conservent, eux, les six langues
de widgets du profil épinglé.

Localement le lanceur refait la suite épinglée et les bundles. Le `.deb` est
construit depuis les **sources**, jamais en supprimant des `.so` d'un exécutable
PyInstaller. Après extraction sans installation/root : comparaison des octets,
absence de runtime embarqué, quatre conversions, sept catalogues, traductions
applicatives/qtbase système et GUI offscreen. Le rapport
`native-deb-validation.json` donne taille, dépendances et origine Python/Qt.

Les contrôles portable/AppImage/Windows restent inchangés. Le minimum GLIBC
mesuré depuis leurs ELF concerne **portable/AppImage**, pas le paquet Python
Debian : les paquets système gèrent leur propre ABI et leurs dépendances.

Assets : `dist/qt6-release/<SHA>-<run>/`. Logs/staging : `build/qt6-release/<run>/`.
Sans `--draft`, seuls les assets sont préparés. Avec ce flag : tag `v0.9.1`
au SHA testé puis brouillon non publié. Aucun retarget/clobber/force/Latest.

Pour préparer seulement le `.deb`, sans bundles ni publication :

```bash
/usr/bin/python3 -E -s tools/build_deb.py \
  --output-dir dist/debian \
  --maintainer "$(git config user.name) <$(git config user.email)>"
```

Cette commande contrôle le paquet natif ; elle ne remplace ni la suite complète
ni la CI du même SHA avant publication. Pas d'overwrite d'un paquet existant.

### Reprendre un run interrompu

Un échec en étape 4-7 (AppImage, artefacts CI, provenance, draft) ne justifie pas
de reconstruire les trois premières étapes :

```bash
bash release_qt6.sh --resume --wait-ci --draft                  # dernier run
bash release_qt6.sh --resume 20261012T065426Z-418571 --draft    # run précis
```

Les étapes 1-3 sont alors **vérifiées, pas reconstruites** : le rapport du bundle
est re-haché fichier par fichier (seuls les avis de licence et `RELEASE-INFO.json`
ajoutés après coup sont tolérés en plus), l'archive portable est réextraite et son
exécution relancée, le SHA-256 du `.deb` et le `source_commit` de son rapport sont
recontrôlés, et le bundle doit porter le **même** SHA et le **même** run CI que
ceux sélectionnés maintenant. Un dossier d'artefacts appartenant à un autre commit
est refusé (message « drop --resume to rebuild everything ») : les binaires
seraient périmés pour ce SHA. Les outils AppImage déjà téléchargés sont réutilisés
après re-vérification de leur SHA-256 épinglé, jamais sans contrôle.

## 5. Contrôles CI et diagnostic des échecs

La CI Qt6 doit être verte sur **12 jobs** pour le SHA exact avant tout tag. Les
jobs `Debian native Qt / bookworm|trixie` valident le `.deb` léger avec le
Python et le Qt d'APT, hors venv de test ; la vérification du runtime système
est une étape séparée du build, donc le statut des étapes situe déjà la panne.

**Condition de déclenchement** : le workflow ne s'exécute que si le message du
commit contient `[PROD]` (titre ou branche pour une pull request). Un commit
ordinaire ne lance rien, il n'y a donc plus qu'un run par SHA susceptible d'être
release. Pour préparer une version :

```bash
git commit -m "[PROD] Prepare the 0.9.1 release"
git push origin arena/0adacf84-convertall-py
```

GHub met quelques secondes à enregistrer un run après un push : le script
interroge l'API jusqu'à 15 s (60 s avec `--wait-ci`) avant de conclure qu'aucun
run n'existe, il n'y a donc rien à relancer ni à re-pousser dans ce délai.

Trois conséquences pratiques : les push silencieux ne peuvent ni remplacer ni
annuler un run marqué (groupes de concurrence séparés), et
`release_qt6.py` refuse de préparer un SHA sans run **push** marqué dont les
12 jobs sont verts — il l'explique et rappelle le marqueur au lieu de chercher
un autre run. Un lancement manuel (« Run workflow ») sert aux contrôles
ponctuels mais ne remplace pas ce run pour la release.

Commit déjà poussé sans le marqueur ? Ajoutez un commit vide marqué plutôt que
de réécrire l'historique : l'arbre validé reste identique, et c'est ce nouveau
SHA qui sera empaqueté puis tagué.

```bash
export CONVERTALL_MAINTAINER="Your Name <you@example.com>"   # une fois par shell (§3)
git commit --allow-empty -m "[PROD] Validate this tree for the release"
git push origin arena/0adacf84-convertall-py
bash release_qt6.sh --wait-ci --draft
```

`tools/build_deb.py` publie ses jalons en annotations (`notice`) et, en cas
d'échec, une annotation `error` avec l'étape fautive, le message et les
dernières lignes de trace ; le même texte est écrit dans
`build/native-debian/native-deb-failure.txt` (artefact `qt6-native-deb-<suite>`).
Ainsi `gh api .../check-runs/<id>/annotations` suffit à diagnostiquer un échec
même quand les logs et artefacts ne sont pas téléchargeables.

## 6. AppImage verrouillée

`tools/appimage-lock.json` conserve IDs et SHA-256 du builder et du runtime.
Le builder utilise explicitement le runtime épinglé et **zstd**, seul
compresseur de son mksquashfs embarqué. Aucun téléchargement « latest » ni
fallback non vérifié. Le correctif zstd a permis le draft 0.9.0 utilisateur ;
ce n'est pas une certification du nouveau SHA 0.9.1.

Le runtime [type2-runtime](https://github.com/AppImage/type2-runtime) choisi
est statique (musl/libfuse) ; la QA emploie extraction/exécution sans FUSE.
Le montage FUSE réel et la compatibilité GPU restent à accepter sur le poste.

Deux pannes d'environnement distinctes ont été observées sur un poste réel, et
sont diagnostiquées automatiquement :

1. **Construction** — appimagetool passe chaque argument par la conversion
   locale → UTF-8 de GLib (`g_locale_to_utf8`, y compris pour les types
   « filename ») : dès qu'un chemin contient des octets non-ASCII et que la
   locale du shell n'est pas UTF-8, le tool s'arrête sur
   « Option parsing failed: Séquence d'octets incorrecte en entrée du
   convertisseur » **avant** toute construction. L'étape 4 assemble donc
   toujours l'AppImage dans un dossier de travail ASCII, local et exécutable
   (repli documenté ci-dessous), passe `LC_ALL=C.UTF-8`, copie le runtime
   épinglé dans ce dossier (SHA-256 revérifié) et n'accepte la sortie qu'une
   fois présente, avant de la déplacer vers `dist/`.
2. **Exécution** — un gestionnaire `binfmt_misc` (AppImageLauncher et
   similaires) revendique tout fichier portant la magie `AI\002` **à l'offset
   8** et l'analyse avec son propre lecteur squashfs, incapable de lire notre
   payload zstd : l'AppImage ne démarre plus du tout, même correcte, et
   l'intergiciel peut **bloquer** le processus au lieu d'échouer. Le **runtime
   épinglé porte lui aussi cette magie** : le script de construction de
   `AppImage/type2-runtime` l'écrit dans le binaire après le `strip`. Le
   gestionnaire le revendique donc exactement comme l'image qu'il construit, et
   le lancer comme solution de repli ne sert à rien — il attend le gestionnaire
   jusqu'au délai de la commande (constaté sur un poste équipé
   d'AppImageLauncher : 180 s perdues, étape 4 en échec). L'étape 4 journalise
   l'environnement (`[appimage] locale…`, `[appimage] binfmt_misc…`),
   **n'exécute alors plus aucun fichier porteur de la magie**, et exerce le
   payload lu dans l'image construite sans rien exécuter d'autre que lui
   (extraction du squashfs, puis `AppRun` extrait : application, sept catalogues
   et interface hors écran), en inscrivant
   `"launcher": "extracted payload (the image bytes were read, never executed)"`.
   `appimage_runtime.launcher` dans `release-provenance.json` et une section
   « AppImage acceptance required » dans les notes le rappellent : un double-clic
   réel doit être confirmé avant de publier Latest. Pour obtenir un test en
   direct — recommandé avant publication — désactivez d'abord le gestionnaire :

   ```bash
   sudo systemctl stop appimagelauncherd
   echo -1 | sudo tee /proc/sys/fs/binfmt_misc/appimage-type1
   echo -1 | sudo tee /proc/sys/fs/binfmt_misc/appimage-type2
   ```

   **Conséquence pour les utilisateurs** : AppImageLauncher (dernière version
   2019, enregistré comme `appimage-type1`/`appimage-type2`) ne sait pas lire le
   zstd ; sur un poste qui l'a installé, le double-clic d'une AppImage correcte
   échoue en « This doesn't look like a squashfs image », et l'intergiciel peut
   même **bloquer** le processus au lieu d'échouer. Le `.deb` et l'archive
   portable ne sont pas concernés, et les notes de version générées portent
   désormais cet avertissement en clair.

L'auto-extraction lit `/proc/self/exe` à l'offset calculé depuis la table des
sections ELF : certains montages (dossiers synchronisés ou nuagiques, clone
rangé dans « Téléchargements ») renvoient alors d'autres octets et l'extraction
échoue en « Failed to open squashfs image ». Dans ce cas le script affiche un
`WARNING` puis retente, sans jamais changer de binaire : copie vérifiée sur
disque local (`TMPDIR`, puis `/dev/shm`, en écartant les montages `noexec`),
puis runtime épinglé via `TARGET_APPIMAGE` (lecture par chemin), puis lecture
directe du payload avec `unsquashfs` (`squashfs-tools` est déjà requis). La
vérification runtime de l'AppImage produite reçoit en plus un `TMPDIR` vérifié,
car le runtime s'y décompresse avant d'exécuter l'application. Le repli n'est
pas un contournement : seuls les octets décrits par les pins sont exécutés, et
un échec total affiche la taille, le SHA-256 relu et le pin attendu. Si les
`WARNING` persistent, déplacer le clone sur un disque local.

## 7. Installer et publier séparément

Dans une VM Debian/Ubuntu dédiée, après checksums :

```bash
sudo apt install ./convertall_0.9.1-1_all.deb
convertall
```

APT installe automatiquement les dépendances manquantes. `dpkg -i` seul ne les
résout pas. Tester menu, clavier, réouverture/historique/fontes/langues, upgrade
puis désinstallation ; sauvegarder les préférences avant migration volontaire.
Tester aussi AppImage/portable en bureau réel et ZIP extrait sur Windows.
Le script ne réalise pas cette installation et ne modifie pas votre vrai HOME.

Revoir les licences/sources correspondantes des bundles et compléter le texte
du draft avec les résultats observés. Ne pas modifier l'arbre testé : sinon
nouveau SHA/nouvelle QA. Seulement après acceptation :

```bash
gh release view v0.9.1 --repo jojo8356/ConvertAll-py
gh release edit v0.9.1 --repo jojo8356/ConvertAll-py --draft=false --prerelease=false --latest
```

`v0.9.0` et la baseline Qt5 `v0.8.1` restent immuables. Aucun gain de performance,
certification installateur/desktop/macOS ni inventaire juridique complet n'est
revendiqué par la QA offscreen.
