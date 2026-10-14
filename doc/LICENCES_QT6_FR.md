# Licences et redistribution de ConvertAll 0.9.0 / Qt6

Les avis de copyright et la licence historique de ConvertAll sont conservés
intacts dans `LICENSE` (GPL-2.0-ou-ultérieure). Le texte de GPLv3 est ajouté dans
`LICENSE-GPL-3.0` : copie de `gcc-mirror/gcc/COPYING3`, récupérée le 10 octobre
2026. Cette copie est le texte de la licence, pas une dépendance GCC.

**PyQt6 n'est pas sous LGPL.** Les roues publiques choisies ici sont GPLv3 ;
Riverbank propose aussi une licence commerciale distincte. La faculté
« ou ultérieure » de ConvertAll permet de distribuer la combinaison avec PyQt6
sous GPLv3. Cela ne modifie ni les copyrights ni rétroactivement les versions
Qt5 archivées. Ne pas remplacer GPLv3 par une assertion « Qt est LGPL, donc
l'ensemble est LGPL ».

Qt6, SIP, PyInstaller, les hooks et les bibliothèques tierces ont leurs propres
licences et avis. Le profil épinglé n'est pas un inventaire juridique complet.
Avant de distribuer un binaire, conserver leurs notices/licences pertinentes,
fournir les sources correspondantes selon les obligations applicables, et
vérifier notamment les conditions de Qt GPL/LGPL et les éventuelles exceptions
PyInstaller. Une CI verte ou un checksum ne satisfait pas à lui seul ces
obligations. Les scripts Inno n'en constituent pas une certification.

Le bundle et l'installateur conservent les fichiers `doc/LICENSE*`. Ne pas
redistribuer les anciennes bibliothèques expérimentales utilisées uniquement
pour l'audit sandbox ; installer les bibliothèques système normales sur Linux.

Références :
- https://www.riverbankcomputing.com/static/Docs/PyQt6/introduction.html
- https://www.riverbankcomputing.com/commercial/license-faq
- https://doc.qt.io/qt-6/licensing.html
- https://www.gnu.org/licenses/gpl-3.0.html
- https://github.com/gcc-mirror/gcc/blob/master/COPYING3
