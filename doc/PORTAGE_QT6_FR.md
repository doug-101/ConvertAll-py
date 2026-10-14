# ConvertAll 0.9.0 — portage de production Qt6

## État et références

Le portage remplace l'application Qt5, pas seulement ses imports. **L'agent
n'exécute pas les tests, installations ni builds : l'utilisateur les lance.**
Premier retour utilisateur au SHA `6a51c01` : 4553 tests réussis, 9 échecs,
0 erreurs/0 skips et couverture 90,46 %. Les échecs concernent l'import `QFont`
manquant et la confusion version du générateur SIP/version du paquet PyQt6-sip.
Ces correctifs doivent être revalidés sur leur nouveau SHA ; le bundle a été
ignoré parce que la suite source échouait. Aucune certification DPI/GPU/Inno/
macOS n'est annoncée. Voir [RELEASE_QT6_FR.md](RELEASE_QT6_FR.md).

| Référence | Usage |
|---|---|
| `a71219904b6a27e7578744afcfa227b21fc73fb2` / 0.8.0 | Baseline fidèle de l'audit, avec ses défauts connus |
| `b10b8e7837e30a2ec9a957a9a2519e4ac0334db3` / Qt5 0.8.1 | Maintenance corrigée, CI utilisateur verte `38075371349` ; référence de retour arrière |
| Nouvelle 0.9.0 | Sources PyQt6, nouvelle QA à effectuer, sans modifier les tags Qt5 |

La publication du tag/draft/Latest Qt5 n'a pas été confirmée ici. La référence
est son **SHA**, indépendamment de cette publication. La branche de travail
reste `arena/0adacf84-convertall-py` ; aucune autre branche n'est nécessaire.

## Profil choisi

- Python **3.11–3.14** : politique du fork, pas le minimum théorique de PyQt6.
- **PyQt6 6.11.0**, **PyQt6-Qt6 6.11.2**, **PyQt6-sip 13.13.0** :
  `requirements-qt6.txt`, partagé par profils tests/build.
- PyInstaller **6.22.3**, hooks **2026.8** ; pytest **9.1.1**, pytest-qt **4.5.0**,
  pytest-cov **7.1.0**, coverage **7.16.2**.
- Environnements Qt5 et Qt6 séparés ; gate refusant PyQt5/PySide2/PySide6.
- CI : Ubuntu 24.04 x86-64 + Windows Server 2022 x64, les quatre Python ciblés.
  Bundles sur Python 3.11 après réussite de toute la matrice.

Qt 6.11 a son support standard annoncé jusqu'au **17 mars 2027** dans la
référence officielle consultée. Qt 6.8 LTS ne signifie pas que les roues GPL
PyPI de ce fork ont cinq ans de correctifs garantis : les correctifs LTS
immédiats/étendus relèvent des offres commerciales. Planifier l'entretien
futur du profil, pas une promesse de sécurité permanente.

La cible Windows Qt6 est Windows 10 1809+ / Windows 11, 64 bits ; plus XP/7/8.
macOS 13+ correspond à la famille Qt6 étudiée mais n'est pas une plateforme
certifiée par notre CI. Linux doit fournir ses bibliothèques natives normales
(GL/EGL, xkbcommon, dbus, fontes, XCB) même en offscreen. Les bibliothèques
expérimentales du benchmark sandbox ne font pas partie du produit.

## Code porté

### GUI et API

Tous les modules applicatifs utilisent PyQt6. Les enums sont qualifiés
(`Qt.Key`, `Qt.WindowType`, `QPalette.ColorRole`, `QValidator.State`, etc.),
les boucles/dialogues utilisent `exec()` et `QAction` vient de `QtGui`.
`qApp` a été remplacé par les appels `QApplication` ; les méthodes
`QFontDatabase` sont statiques. Les listes de fontes vides ont une taille
positive et les tailles standard servent de secours aux fontes scalables.
Les groupes de palette sont testés avec `is not None`, pas avec leur vérité
booléenne (le groupe Active vaut zéro).

L'aide utilise `QUrl.fromLocalFile`, le signal `highlighted(QUrl)`,
`QTextDocument.ResourceType` et les opérations de recherche Qt6. Espaces,
Unicode et `#` dans un chemin local ne deviennent pas un fragment URL.
Seuls les liens HTTP/HTTPS sont envoyés au navigateur externe.

Qt6 active HiDPI nativement ; aucun switch Qt5 supprimé
`AA_EnableHighDpiScaling` / `AA_UseHighDpiPixmaps` n'est réintroduit.
Les coordonnées Qt6 restent logiques. Les widgets de conversion, bases,
fractions, options, thèmes, polices, menus et historique gardent leurs usages.

### CLI et moteur

La CLI garde un `QCoreApplication` et n'importe pas `QtGui`/`QtWidgets` pour
les conversions/diagnostics. Les codes de sortie, données corrigées, locale
numérique C, rejet des séparateurs de groupes et tests des conversions restent
conservés. `--runtime-info` fournit les versions **réellement chargées** du
binding et de Qt, ainsi que le chemin des traductions Qt6, au format JSON et
sans GUI. Il distingue `sip_package` (version de la distribution **PyQt6-sip**,
13.13.0 dans le profil) et `sip_generator` (valeur de `sip.SIP_VERSION_STR`,
6.17.0 dans le premier retour Linux). Ces deux versions ne désignent pas la
même chose : la version du générateur n'est pas la version du paquet épinglé.
Le bundle conserve les métadonnées PyQt6-sip ; leur absence provoque une erreur
de diagnostic, jamais une version supposée. `--gui-smoke-test` contrôle la
vraie fenêtre puis quitte sa boucle.

Le moteur `unitatom/unitdata/unitgroup`, les sept catalogues et les assertions
numériques ne sont pas réécrits pour Qt6. Seules les API Qt des widgets bases/
fractions changent ; leurs algorithmes corrigés en 0.8.1 sont conservés.
Les nouvelles références/corrections Qt5 ne sont pas remplacées par les six
exceptions connues du benchmark ancien.

### Préférences et géométrie

Même fichier de préférences, anciennes clés conservées, y compris la faute
historique **`RemenberDlgPos`**. Historique des unités, thème/couleurs, notation,
précision et sérialisation des fontes restent lisibles. `GuiFont` reste écrit
au format Qt5 10/11 champs (poids historiques). `GuiFontQt6` conserve en plus
le format complet Qt6 ; `GuiFontQt6Legacy` sert de miroir pour détecter une
modification des fontes effectuée lors d'un retour dans Qt5. Si Qt5 a modifié
l'ancienne clé, Qt6 n'impose pas son ancien état complet. Les poids standard
ont leur correspondance exacte ; un poids OpenType intermédiaire est arrondi
au poids Qt5 nommé le plus proche, sans perdre sa valeur dans l'état Qt6.

Nouvelle clé **`MainDlgGeometry`**, état `saveGeometry()` encodé en hexadécimal :
`restoreGeometry()` la restaure en premier en utilisant les informations Qt6
sur l'écran et la mise à l'échelle. Sans état ou avec état invalide, les anciens
`MainDlgXPos/YPos/XSize/YSize` sont utilisés. Les positions négatives des écrans
à gauche sont admises ; les rectangles hors écran sont rabattus vers un écran
disponible. Les anciens champs restent écrits pour permettre le retour Qt5.
Si la mémorisation est désactivée, rien n'est restauré.

Les tests de cette logique ne remplacent pas des essais physiques sur plusieurs
écrans/DPI ni les restrictions de positionnement du compositeur Wayland.

### Traductions

Les contextes du helper global `_()` restent les **noms de fichiers modules**,
comme dans les TS/QM existants. Les QM applicatifs sont compatibles et restent
inchangés ; leurs nombres de messages actifs restent vérifiés langue par langue.

Les traductions internes des widgets viennent de **`qtbase_<lang>.qm` du
runtime Qt6**, découvert avec `QLibraryInfo.path(LibraryPath.TranslationsPath)`.
Aucun ancien `qt_*.qm` Qt5 n'est chargé par l'application ni ajouté au bundle.
Ces anciens fichiers restent dans l'archive source comme ressource historique.

`pylupdate6` ne sait pas extraire le helper `_()` tel qu'il est utilisé ici.
`tools/update_translations.py` est donc un véritable extracteur AST standard :
contexte, texte littéral, commentaire de désambiguïsation et emplacements.
Il conserve traductions/commentaires existants, marque les nouveaux textes
`unfinished` et les anciens `vanished`, avec résultat déterministe.
Il refuse les textes dynamiques qu'il ne pourrait pas extraire sûrement.

```bash
# Lecture seule : liste les messages absents des TS.
python tools/update_translations.py --check
# Mise à jour volontaire + compilation avec un VRAI lrelease Qt6.
# Installer au préalable les outils Linguist Qt6 ; ils ne sont pas dans PyQt6.
python tools/update_translations.py --update --compile --lrelease /usr/lib/qt6/bin/lrelease
```

`--compile` refuse un lrelease Qt5. Il ne compile que les TS applicatifs, pas
les catalogues widgets du runtime. Ne pas changer les traductions après QA
sans relancer la validation du nouveau commit. Le manifeste `.pro` est une
liste historique, pas un générateur pylupdate6 fonctionnel pour ce helper.

## Tests, packaging et provenance

La suite existante est portée en **vrais tests PyQt6** (pytest-qt `pyqt6`).
Aucune assertion supprimée pour faire passer Qt6, aucun skip global, même seuil
80 % instructions/branches, sous-processus inclus. Les nouveaux cas couvrent
les API, fontes Qt5 sérialisées, géométries nouvelles/invalides/négatives,
URLs locales et extraction/préservation des traductions, plus les gates.

`tools/validate_release.py` refuse mauvais pins, bindings mélangés et runtime
chargé différent. Il conserve SHA/branche/dirty avant et après, hashes d'entrée,
versions, commande, JUnit, couverture et code pytest. `--require-clean` est le
mode CI/release ; le SHA CI doit égaler `GITHUB_SHA`. Un test de développement
sur arbre modifié ou extrait reste possible, mais `release_eligible` est faux.

`release_source.py` produit `ConvertAll-0.9.0-qt6-source.tar.gz` + SHA256 +
provenance du commit **HEAD propre**, gzip sans timestamp. Un export n'est pas
un résultat QA. Utiliser les assets du run CI validé pour la publication.

Le spec PyInstaller fournit un flat onedir Qt6, ressources et catalogues
applicatifs, traductions qtbase via le hook Qt6, GUI/CLI distinctes sous Windows,
et exclut les autres bindings. `check_bundle.py` exerce les exécutables natifs,
vérifie leurs versions réelles, tous les catalogues unités, traductions Qt6
à l'intérieur du bundle et GUI/ressources, en environnement isolé. Son rapport
associe ces contrôles aux hashes des fichiers et au checkout du **checker** ;
il ne prétend pas déduire indépendamment le commit qui a compilé un binaire
arbitraire. La CI garantit la chaîne checkout testé → build du même SHA.

Le script Unix garde la voie préfixe/DESTDIR et son wrapper UTF-8 ; il contrôle
Python/PyQt6/Qt6 et trouve les ressources installées. L'uninstallateur reste
indépendant de Qt. `source/setup.py build` est désormais un wrapper explicite
PyInstaller, pas une recette cx_Freeze prétendument validée. Les scripts Inno
sont alignés Qt6/x64/Windows 10 et éliminent les restes de binding Qt5, mais
leur compilation/installation effective reste à accepter manuellement.

## Benchmark et licences

Le benchmark conservé dans [MIGRATION_QT6_FR.md](MIGRATION_QT6_FR.md) mesure le
prototype issu de **0.8.0**, pas cette 0.9.0. Il montrait une hausse d'environ
26 % du démarrage médian et une hausse modeste de mémoire ; aucun gain de
performance ne justifie le portage. La motivation est la maintenance Qt6 et
l'arrêt du support standard Qt5, pas une nouvelle mesure de performance.

PyQt6 est **GPLv3 ou commercial, pas LGPL**. Les sources ConvertAll restent
GPL-2.0-ou-ultérieure ; la distribution publique combinée avec les roues PyQt6
GPL doit respecter GPLv3. Texte GPLv3 ajouté, avis historiques conservés ; voir
[LICENCES_QT6_FR.md](LICENCES_QT6_FR.md) avant de distribuer un binaire.

Références documentaires :
- https://www.riverbankcomputing.com/static/Docs/PyQt6/pyqt5_differences.html
- https://www.riverbankcomputing.com/static/Docs/PyQt6/i18n.html
- https://doc.qt.io/qt-6/portingguide.html
- https://doc.qt.io/qt-6/widgets-changes-qt6.html
- https://doc.qt.io/qt-6/localization.html
- https://doc.qt.io/qt-6/restoring-geometry.html
- https://doc.qt.io/qt-6.11/supported-platforms.html
- https://doc.qt.io/qt-6.11/qt-releases.html
