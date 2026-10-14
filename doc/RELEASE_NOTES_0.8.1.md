# ConvertAll 0.8.1 — maintenance Qt5

Cette release conserve **PyQt5**, sans migration Qt6.

## Correctifs

- Six constantes scientifiques anglaises : exposants négatifs correctement lus.
- Références d'unités catalanes et suédoises corrigées ; corrections numériques
  des alias suédois `ct`, `kph` et `kiloton icke-metriskt`.
- Erreurs de définition/cycles signalées proprement ; relecture des catalogues
  idempotente et sans perte des anciennes données en cas de fichier invalide.
- CLI : `--test` réparé, codes de retour fiables, erreurs de précision et de
  domaine signalées ; `--version`, `--test-all` et `--gui-smoke-test` ajoutés.
- Rechargement des dernières unités avec conversion effective à l'ouverture.
- Validation des préférences décimales alignée sur le format Python : point
  décimal indépendant de la locale système, séparateurs de milliers rejetés.
- Décimal signé en complément à deux et fractions à dénominateurs puissances
  de deux corrigés ; fractions continues pour éviter les longues recherches
  sur les irrationnels/petites décimales ; valeurs non finies/overflow mieux traitées.
- Chemins contenant des espaces/apostrophes pris en charge par l'installateur
  Unix ; fallback Catalan vers le vrai catalogue `qtbase` du runtime Qt5.

**Noms corrigés :** `ton*` → `kort ton`, `kiloton*` →
`kiloton icke-metriskt` (suédois). Les deux noms catalans de tailles de chaussures
perdent leurs parenthèses autour de `Estats Units`, réservées aux groupes d'unités.
Si un ancien favori emploie ces noms, resélectionner l'unité.

## Validation et distribution

- Tests automatisés du moteur, des 4 104 définitions dans sept langues, de la
  CLI, de l'interface Qt5, des préférences, traductions, installation et archives.
- Environnements Qt5 épinglés, seuil de couverture de 80 %, rapports et CI
  Linux/Windows sur Python 3.10, 3.11 et 3.14.
- Recette PyInstaller modernisée ; binaire Windows CLI distinct du binaire GUI.
- Archive source d'un commit exact, SHA256 et provenance joints à la release.

La release source n'annonce pas d'installateurs natifs validés. Ne joindre un
binaire qu'après réussite de son job natif et validation sur une machine propre.
Les tests applicatifs ne remplacent pas le support sécurité de Qt5.
Voir `doc/RELEASE_QT5_FR.md` pour les résultats et limites de validation.
