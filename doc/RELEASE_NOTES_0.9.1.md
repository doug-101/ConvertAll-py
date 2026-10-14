# ConvertAll 0.9.1 — paquet Debian léger

**Candidat : nouvelle QA en attente.** Le tag `v0.9.0` au SHA
`a3b93db8aed87787c531c6067c43199e4d48159a` reste immuable. Les résultats 0.9.0
ne sont pas des résultats 0.9.1.

- Le `.deb` devient un paquet Python `Architecture: all`, sans runtime
  Python, PyQt6, Qt, SIP ou bibliothèques ELF embarqués.
- Dépendances APT : Python >= 3.11, python3-pyqt6 >= 6.4.2,
  python3-pyqt6.sip >= 13.4.1 et qt6-translations-l10n >= 6.4.2.
- Sources applicatives, sept catalogues d'unités, six QM applicatifs,
  icônes, aides et licences conservés. TS/build scripts/bytecode ne sont
  pas installés ; ils restent disponibles dans l'archive source.
- Lanceur utilisant `/usr/bin/python3 -E -s`, et contrôle de l'origine du
  module PyQt6 dans les dist-packages Debian : aucune validation trompeuse
  avec le venv des bundles.
- CI native Debian Bookworm/Trixie : régressions applicatives, couverture
  80 % conservée et contrôle du vrai paquet extrait avec Qt système.
- Traductions de widgets : la distribution peut ne pas fournir toutes les
  langues de `qtbase` (par exemple `qtbase_sv` absent). Le contrôle exige
  donc : catalogue présent ⇒ doit charger ; catalogue réellement absent ⇒
  l'application doit le signaler proprement. Un catalogue applicatif
  manquant reste toujours une erreur. Les paquets 0.9.0/bundles conservent
  leurs six langues de widgets épinglées.
- Les bundles portable, Windows et AppImage restent autonomes et conservent
  le profil exact PyQt6 6.11.0 / Qt 6.11.2 / PyQt6-sip 13.13.0.

La taille exacte et les résultats seront indiqués dans les rapports du build
réel. Le `.deb` est plus petit parce que ses dépendances ne sont plus dedans ;
APT doit néanmoins les installer si elles ne sont pas déjà présentes.
Publication seulement après QA du nouveau SHA, installation réelle/DPI et
revue des licences. Aucun test/build/installation exécuté par l'agent.
