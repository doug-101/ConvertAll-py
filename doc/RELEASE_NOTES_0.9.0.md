# ConvertAll 0.9.0 — Python / Qt6

**Candidat : validation complète Qt6 de production en attente.** Le premier
retour utilisateur au SHA `6a51c01` donne 4553 PASS / 9 FAIL (couverture 90,46 %),
pas une version validée. Correctifs : import QFont pour restaurer les fontes ;
diagnostic/checker distinguant paquet PyQt6-sip et générateur SIP, métadonnées
SIP conservées dans le bundle. Leur nouveau SHA doit être revalidé. Avant
publication, compléter le texte du draft avec le SHA/run CI et les résultats
réellement observés.

## Changements

- Portage complet de la GUI et de la CLI à PyQt6 : API, enums qualifiés,
  `exec()`, actions, palettes, polices, aide et signaux QUrl.
- Profil épinglé : Python 3.11–3.14, PyQt6 6.11.0 / Qt 6.11.2 /
  PyQt6-sip 13.13.0 ; environnements séparés de Qt5.
- Traductions applicatives et sept catalogues unités conservés ; widgets
  traduits avec les catalogues qtbase du runtime Qt6. Véritable extraction AST
  pour `_()` et compilation explicite avec lrelease Qt6.
- Préférences historiques conservées, dont `RemenberDlgPos`, unités récentes,
  thèmes et fontes ; géométrie Qt6 persistante avec secours par anciennes clés.
- CLI paresseuse sans import GUI, nouveau diagnostic JSON `--runtime-info`.
- Tests réels Qt6 et nouveaux cas de compatibilité ; seuil couverture combinée
  instructions/branches 80 %, sans retirer les assertions des conversions.
- Gate avec SHA/dirty/hashes/versions ; CI Linux/Windows sur les quatre Python,
  puis bundles PyInstaller Qt6 et archive source exacte, sans publication auto.
- Lanceur `test_all_qt6.sh` : un résumé et une archive de logs à transmettre.
- Recettes Unix et Inno alignées ; ancien setup cx_Freeze remplacé par wrapper
  du spec PyInstaller. Texte GPLv3 ajouté et avis de redistribution documentés.

## Ce qui reste inchangé

Le moteur numérique et les données corrigées en Qt5 0.8.1 ne sont pas
réécrits. Les assertions des 7 catalogues / 4104 définitions et des traductions
restent en place. La référence Qt5 validée est
`b10b8e7837e30a2ec9a957a9a2519e4ac0334db3` (run utilisateur `38075371349`).
Ses tags ne sont ni retargetés ni remplacés.

## Limites et exigences avant Latest

- Pas encore de validation complète Qt6 0.9.0 : correctifs à retester et bundle non validé.
- Les tests/bundles offscreen ne certifient pas bureau réel, DPI fractionnaire,
  multi-écrans, GPU/Wayland ni installation Inno. macOS n'est pas certifié.
- Windows 10 1809+ / Windows 11 x64 ; plus XP/Vista/7/8.
- Linux nécessite ses bibliothèques natives Qt6 et ses fontes normales.
- Le benchmark du prototype 0.8.0 n'est pas une mesure de cette version ;
  aucun gain de performance n'est revendiqué.
- PyQt6 est GPLv3 ou commercial, pas LGPL. Respecter aussi les obligations
  propres à Qt, SIP, PyInstaller et aux bibliothèques tierces pour les binaires.

Voir `doc/RELEASE_QT6_FR.md` pour la procédure de QA et la publication en draft
avant Latest. Aucune release n'est automatiquement publiée par la CI.
