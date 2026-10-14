# Cahier des charges — `cvt`, version en ligne de commande de ConvertAll, écrite en Rust

| | |
|---|---|
| **Document** | Cahier des charges technique et fonctionnel, v1.0 |
| **Date** | 13 octobre 2026 |
| **Produit visé** | `cvt` — convertisseur d'unités en ligne de commande, en Rust |
| **Projet de référence** | `ConvertAll-py` 0.9.1 (Python 3.11–3.14 / PyQt6 6.11.0) |
| **Statut** | À valider avant tout développement |
| **Rédacteur** | À compléter (auteur du portage Rust) |

---

## 0. Fiche synthétique

| Élément | Valeur proposée | Justification |
|---|---|---|
| Nom du binaire principal | `cvt` | Court, sans collision avec la commande `convertall` installée par la version Python |
| Nom du binaire secondaire | `convertall-cli` | Nom explicite pour les paquets et les scripts |
| Crate(s) | workspace : `convertall-core`, `convertall-catalog`, `cvt-cli` | Le cœur doit être utilisable comme bibliothèque (GUI Rust future, WASM, service) |
| Langage / édition | Rust, édition 2024 | Édition 2024 stable depuis Rust 1.85 |
| MSRV | 1.85 minimum, toolchain courante 1.99 (stable du 01/10/2026) | Voir §5.1 |
| Licence | GPL-2.0-or-later | Le catalogue `units.dat` est GPL-2.0 ; voir §8 |
| Données | `data/units.dat` et `data/units_*.dat` du dépôt ConvertAll (7 catalogues), lus à l'identique | Une seule source de vérité pour les unités |
| Plateformes v1.0 | linux-x86_64 (gnu + musl statique), linux-aarch64 (musl), macOS x86_64/aarch64, Windows x86_64 | Voir §7.1 |
| Formes de sortie | texte (compatibles Python), JSON, JSONL, TSV | Scriptabilité |
| Jalons | J0 spike → J1 MVP → J2 REPL/lot/JSON → J3 parité complète + i18n → J4 paquets/CI → J5 1.0 | §9 |
| Effort estimé | ≈ 35–55 jours-personne, hors traduction | Estimation, à recaler après J0 |

---

## 1. Contexte et objectifs

### 1.1 Ce qui existe déjà

`ConvertAll-py` est le portage Python/PyQt6 (version 0.9.1) de ConvertAll, un convertisseur d'unités « libres » : il n'impose pas des unités prédéfinies mais combine des unités arbitraires (« pouces par décennie », « mètres-livres », « milles nautiques au cube »).

Constats vérifiés dans le dépôt :

- **Catalogue de données** : `data/units.dat` (925 lignes, **52 types d'unités** allant de `[mass]` à `[thermal resistance]`) plus six catalogues traduits (`units_ca`, `units_de`, `units_es`, `units_fr`, `units_ru`, `units_sv`).
- **Primitives** : `kg, m, s, K, A, mol, cd, rad, sr, bit, unit` (le `unit` étant « sans dimension », noté `!!` ; les autres primitives sont notées `!`).
- **Unités non linéaires** : définies par des équations (`C = [K] x + 273.15 ; x - 273.15`) ou par des listes d'équivalences interpolées (`Gas mark = [K] [(0.25, 383.15), ...]`).
- **Une CLI Python existe déjà** (`source/cmdline.py`, 256 lignes) : mode non graphique, mode interactif `-i`, test du catalogue `-t`/`--test-all`, et **codes de sortie documentés : `0` succès, `1` erreur de conversion/données, `2` erreur d'usage, `130` interrompu**.
- **Précision** : `maxDecPlcs = 12` chiffres après la virgule, `DecimalPlaces` par défaut à `8`, notations `general | fixed | scientific | engineering`.
- **Qualité** : suite de ≈ 4 673 tests, couverture combinée observée 90,70 % (seuil projet 80 %).
- **Licence** : GNU GPL version 2 (les en-têtes mentionnent « version 2 » ou « version 2 ou ultérieure » selon les fichiers).

### 1.2 Le contrat à préserver

La CLI Rust ne part pas de zéro : elle doit au minimum reproduire le contrat observé de `source/cmdline.py`, sous peine de casser les scripts et l'habitude des utilisateurs.

| Contrat existant | Exigence Rust |
|---|---|
| `convertall 5 ft 10 in to cm` (nombre + unité source + unité cible) | Identique, sans `--` obligatoire pour les nombres négatifs |
| `-d/--decimals N` | Identique, 0 ≤ N ≤ 12, sinon code 2 |
| `-f/--fixed-decimals`, `-s/--sci-notation`, `-e/--eng-notation` | Identiques |
| `-q/--quiet` (pas de question, erreur si unité manquante) | Identique |
| `-i/--interactive` | REPL enrichi (§3.8), sémantique identique (`n` = nouvelle, `r` = inverse, `q` = quitter) |
| `-t/--test`, `--test-all` | `cvt check [FICHIERS...]`, mêmes messages et code de retour |
| `-v/--version`, `--runtime-info` (JSON) | `cvt --version`, `cvt doctor --json` |
| Sortie `1.0 in = 2.54 cm` | Format texte par défaut identique au caractère près (§3.7) |
| Codes `0/1/2/130` | Conservés ; toute addition utilise ≥ 3 |

### 1.3 Pourquoi réécrire en Rust

1. **Démarrage et coût** : pas d'interpréteur Python ni de Qt à charger. Objectif mesuré en J0 : première conversion affichée en moins de 10 ms, contre plusieurs dizaines/centaines de ms aujourd'hui.
2. **Distribution** : un binaire statique musl (`x86_64-unknown-linux-musl`) ne demande ni Python 3.11+, ni PyQt6, ni `apt`. Utile sur serveurs minimalistes, conteneurs `scratch`/`alpine`, Raspberry Pi (aarch64), postes sans droits d'installation.
3. **Embarquable** : `convertall-core` devient une bibliothèque réutilisable (GUI Rust éventuelle, extension WASM pour le site, intégration dans un outil de calcul plus large).
4. **Scriptabilité sérieuse** : sortie JSON stable et versionnée, mode lot, codes de sortie fins — là où la CLI Python reste limitée.
5. **Exactitude** : le Python calcule en `float64`. Rust permet une arithmétique **rationnelle exacte** pour les facteurs linéaires (le catalogue est fait de fractions décimales : `1 in = 2.54 cm` exactement), ce qui supprime les artefacts d'arrondi binaires, tout en restant strictement compatible sur l'affichage.
6. **Robustesse** : parseur de catalogue testé par fuzzing, `#![forbid(unsafe_code)]`, pas d'évaluation de code arbitraire (contrairement à la tentation d'appeler Python pour les équations non linéaires, §5.7).
7. **Coût de maintenance** : l'équipe maintient déjà Qt6/PyInstaller/`.deb`/AppImage pour la GUI ; une CLI Rust supprime toute une classe de pannes (chemins non-ASCII, AppImageLauncher, binfmt_misc, versions SIP…).

### 1.4 Objectifs mesurables (KPI)

| Indicateur | Cible | Mesure |
|---|---|---|
| Démarrage (binaire `--version`) | < 10 ms | `hyperfine`, 100 tirs |
| Conversion simple (catalogue chargé, une conversion) | < 15 ms au total | `hyperfine 'cvt 5 ft 10 in to cm'` |
| Débit en mode lot (une conversion par ligne, processus unique) | ≥ 100 000 conversions/s | `criterion` + `hyperfine` sur 1 M lignes |
| Empreinte mémoire (mode lot) | < 15 Mo RSS | `/usr/bin/time -v` |
| Taille du binaire | < 6 Mo (musl, strippé, LTO) | `ls -l` en CI |
| Parité de sortie avec le Python | 100 % du corpus golden, hors divergences documentées | §6.2 |
| Couverture | ≥ 90 % lignes, plancher CI 80 % | `cargo llvm-cov --fail-under-lines 80` |
| Catalogue complet validé | 52 types, 7 catalogues, 0 erreur | `cvt check data/*.dat` |

### 1.5 Non-objectifs (périmètre exclu)

- **Pas d'interface graphique** : la GUI reste ConvertAll-py (Qt6). Le Rust ne fait pas de fenêtres.
- **Pas de taux de change en réseau** : aucune requête HTTP, aucune dépendance à une base de devises. Les devises pourront être ajoutées plus tard via un fichier de données utilisateur, hors périmètre v1.
- **Pas de CAS** : pas de résolution symbolique, pas d'intégrales, pas de manipulation d'expressions algébriques. Le rejet est explicite dans la documentation.
- **Pas de TUI plein écran** : le REPL est un `readline` (rustyline), pas une application plein écran.
- **Pas de réimplémentation de LaTeX/UnitMath** : la cible est la fidélité au catalogue ConvertAll, pas l'exhaustivité scientifique.

---

## 2. Périmètre et cas d'usage

### 2.1 Personas

- **P1 — Scripteur shell / DevOps** : veut convertir dans un script (`--json`), enchaîner des milliers de valeurs, gérer les erreurs par code de sortie.
- **P2 — Développeur/ingénieur** : tape `cvt 5 ft 10 in to cm` ou ouvre le REPL pour enchaîner des calculs avec unités composées.
- **P3 — Utilisateur de ConvertAll existant** : retrouve exactement les mêmes résultats, les mêmes noms d'unités, les mêmes messages, mais sans Qt.
- **P4 — Embarqueur** : intègre `convertall-core` dans son propre programme Rust.
- **P5 — Traducteur** : complète un catalogue `units_xx.dat` ou un fichier de messages sans toucher au Rust.

### 2.2 Cas d'usage et critères d'acceptation

| Id | Cas d'usage | Critère d'acceptation |
|---|---|---|
| US-01 | Conversion simple | `cvt 5 ft 10 in to cm` → `5 ft 10 in = 177.8 cm` (valeur validée contre Python) |
| US-02 | Conversion d'une valeur simple | `cvt -d 3 1 in cm` → `1 in = 2.540 cm` |
| US-03 | Unité composée | `cvt "mi/hr" "km/h"` → résultat égal à la sortie Python au caractère près |
| US-04 | Unité personnalisée | `cvt --units-file ~/mes.dat "3 lampes/m2" "lampes/cm2"` |
| US-05 | Mode lot depuis stdin | `printf '1 in cm\n1 lb kg\n' \| cvt --batch` produit deux lignes, code 0 |
| US-06 | Mode lot tolérant | `--batch --continue-on-error` : les lignes invalides produisent une erreur sur `stderr`, le code final est 1, les lignes valides restent sur `stdout` |
| US-07 | Sortie machine | `cvt --json 1 in cm` → objet à `schema_version`, parsable par `jq`, jamais de couleur |
| US-08 | REPL | `cvt` ouvre un REPL, `Tab` complète les noms d'unités, `Ctrl-R` cherche l'historique, `q` quitte avec code 0 |
| US-09 | Inventaire | `cvt list --type length` et `cvt list --search 'naut'` listent en colonnes alignées, `--json` disponible |
| US-10 | Fiche d'unité | `cvt info ft` → nom, type, définition, équivalent réduit, commentaires, alias |
| US-11 | Validation d'un catalogue | `cvt check data/units.dat` → `data/units.dat: N units`, code 0 ; catalogue cassé → code 3 |
| US-12 | Catalogue compilé | `cvt data compile data/units.dat -o units.toml` produit un fichier lisible, avec SHA-256 de la source |
| US-13 | Complétion shell | `cvt completions bash \| sudo tee /etc/bash_completion.d/cvt` fonctionne pour `bash`, `zsh`, `fish`, `powershell`, `elvish` |
| US-14 | Locale | `LC_ALL=fr_FR.UTF-8 cvt 1 in cm` affiche les messages et les noms d'unités français (`units_fr.dat`), repli sur l'anglais sinon |
| US-15 | Diagnostic | `cvt doctor --json` → version, catalogue(s) chargé(s), SHA-256, locale, options, sans effet de bord |
| US-16 | Parité | Pour tout le corpus golden (§6.2), la sortie Rust est identique à la sortie Python, au caractère près |

### 2.3 Matrice de parité fonctionnelle (GUI Python → CLI Rust)

| Fonction de ConvertAll-py | v1.0 Rust | Remarque |
|---|---|---|
| Conversion nombre + unités combinées | Oui | Cœur du produit |
| Unités non linéaires (équations, interpolation) | Oui | §3.5 |
| Unités définies par l'utilisateur | Oui | `--units-file`, `~/.config/convertall/` |
| Décimales / notation (general, fixed, scientific, engineering) | Oui | Options `-d/-f/-s/-e` |
| Catalogue par langue (`units_fr.dat`…) | Oui | §3.12 |
| Boutons opérateurs, thème, police, géométrie de fenêtre | Non | Sans objet en CLI |
| Unités récentes, historique de session GUI | Partiel | Historique REPL + « unités récentes » du REPL, `~/.local/state/cvt/history` |
| Test du catalogue (`-t`, `--test-all`) | Oui | `cvt check` |
| `--runtime-info` (versions Qt/SIP) | Remplacé | `cvt doctor --json` (versions Rust/catalogue) |

### 2.4 Hors périmètre explicite de la v1

Devises et taux en ligne, conversions dépendant du lieu ou de la date, incertitudes de mesure, analyse dimensionnelle symbolique d'expressions algébriques, unités définies par l'utilisateur **non linéaires** écrites en Rust (les non linéaires restent celles du catalogue, §5.7), mode serveur/daemon.

---

## 3. Spécifications fonctionnelles

### 3.1 Modèle de données

Une **unité** (`Unit`) est un enregistrement du catalogue :

```text
Unit {
  name        : String        // nom canonique, ex. "ft"
  type        : UnitType      // ex. "length" (52 types)
  quantity    : Expr<Number>  // facteur, ex. 0.3048 (rationnel exact)
  equivalent  : Target        // Unit | Combination | Primitive(!) | PrimitiveUnnamed(!!)
  linear      : bool          // false ⇒ équations ou table d'interpolation
  comment1    : Option<String>  // affiché entre parenthèses après le nom
  comment2    : Option<String>  // colonne commentaire de la liste
  aliases     : Vec<String>   // noms alternatifs (toutes les entrées du catalogue)
}
```

Règles de chargement :

1. Le catalogue est lu depuis `units.dat` au format ConvertAll (§ annexe B), ou depuis un catalogue **compilé** (`units.toml`, §3.10 `data compile`).
2. Un type (`[mass]`, `[length]`, …) ouvre une section ; toutes les unités suivantes appartiennent à ce type jusqu'au type suivant.
3. Une unité dont l'équivalent commence par `!` est une **primitive** ; `!!` désigne la primitive sans dimension.
4. Toute unité doit se réduire à une combinaison de primitives. Les **références circulaires** sont détectées et refusées (erreur de chargement, code 3).
5. Les commentaires de ligne et de fin de ligne sont conservés pour `cvt info` et `cvt list`, jamais interprétés.

### 3.2 Grammaire d'entrée

L'entrée principale est « nombre puis unité(s) », éventuellement combinée et convertie. Grammaire formelle (EBNF) :

```ebnf
(* --- point d'entrée d'une demande de conversion --- *)
conversion      = number, [ unit_expr ], conversion_op, unit_expr
                | number, unit_expr, unit_expr          (* forme courte historique *)
                | unit_expr, conversion_op, unit_expr ; (* nombre implicite = 1 *)

conversion_op   = "to" | "in" | "->" | "→" | "=" ;      (* "in" = mot-clé si suivi d'une unité *)

(* --- nombre --- *)
number          = [ sign ], ( decimal | fraction | mixed | sci ) ;
sign            = "+" | "-" ;
decimal         = digits, [ ".", digits ] | ".", digits ;
sci             = ( digits | decimal ), ( "e" | "E" ), [ sign ], digits ;
fraction        = digits, "/", digits ;                  (* 3/8 *)
mixed           = digits, ( "-" | " " ), digits, "/", digits ;  (* 1-3/8 ou 1 3/8 *)

(* --- unités --- *)
unit_expr       = unit_term, { ( mul_op, unit_term ) | ( space, unit_term ) } ;
unit_term       = unit_atom, [ power ] | "(", unit_expr, ")" ;
power           = ( "^" | "**" ), [ sign ], digits
                | superscript ;                          (* ² ³ ⁻¹ *)
mul_op          = "*" | "·" | "⋅" | "/" | "per" ;
unit_atom       = unit_name | unit_name, "/", unit_name | unit_name, " ", unit_name ;
```

Comportements obligatoires :

- `5 ft 10 in`, `5'10"` (notation pieds/pouces), `6 feet 3 inches` : l'unité source peut être une **combinaison** ; `5 ft 10 in to cm` ≡ `(5 ft) + (10 in)`.
- `mi/hr`, `mi per hr`, `m/s^2`, `m·s⁻¹`, `kg m / s^2` sont équivalents.
- `-3 C to K` : le signe initial est un signe numérique, pas une option ; `--` reste accepté pour lever l'ambiguïté (compatibilité `cmdline.py`).
- La résolution des noms est **d'abord exacte** (`ft` ≠ `FT`), puis, en second recours seulement, insensible à la casse avec un avertissement sur `stderr` (`warning: resolving "FT" as "ft"`). En `--quiet`, l'avertissement est supprimé. Le comportement exact doit être aligné sur Python (§6.2) : c'est le corpus golden qui tranche.
- Les espaces multiples, espaces insécables et tabulations en tête/fin sont ignorés.
- Les nombres sont localisés : `1,5` n'est accepté qu'avec `--decimal-comma` ou une locale l'exigeant explicitement ; par défaut la virgule n'est **pas** un séparateur décimal (compatibilité Python).

### 3.3 Expressions composées

- Produits, quotients, puissances entières (positives, négatives, nulles) et parenthèses.
- Les unités sans dimension (`unit`, `%`, `ppm`) se combinent comme les autres.
- Une conversion n'est possible qu'entre unités **compatibles** (mêmes dimensions réduites). Sinon : message `Units X and Y are not compatible` (compatibilité Python) et code 1.
- Les unités combinées se réduisent à un facteur et un vecteur d'exposants sur les primitives : `mi/hr` → `{m: 1, s: -1}` avec un facteur exact.

### 3.4 Précision, exactitude et affichage

Deux moteurs cohabitent, avec une règle claire :

| Situation | Moteur | Justification |
|---|---|---|
| Facteurs linéaires, puissances, conversions entre unités linéaires | **Rationnel exact** (`dashu-ratio::RBig`) | `1 in = 2.54 cm` exactement ; aucune dérive d'arrondi binaire |
| Unités non linéaires (équations, interpolation) | **`f64`** (IEEE-754, mêmes opérations que Python) | Compatibilité stricte avec le catalogue et le Python |
| Affichage | Rationnel → décimal arrondi selon `-d` (défaut 8, max 12) | Identique à `maxDecPlcs = 12` / `DecimalPlaces = 8` du Python |

Règles d'affichage :

1. `-d N` fixe le nombre de décimales (0 ≤ N ≤ 12) ; hors bornes → code 2.
2. `-f` force les zéros de fin (`2.540`), sinon les zéros superflus sont supprimés (`2.54`).
3. `-s` (scientifique) et `-e` (ingénierie, exposant multiple de 3) comme le Python.
4. Un résultat non fini (`inf`, `nan`) est refusé : `Conversion result is not finite`, code 1.
5. Quand un résultat est exact, le mode `--json` l'indique (`"exact": true`) et peut fournir la fraction réduite (`"as_fraction": "127/50"`).

### 3.5 Unités non linéaires

Le catalogue définit les non-linéaires de deux façons :

1. **Équations** : `C = [K] x + 273.15 ; x - 273.15` — deux fonctions de `x`, l'une de l'unité vers l'équivalent, l'autre en sens inverse.
2. **Liste d'équivalences** : `Gas mark = [K] [(0.25, 383.15), ...]` — points d'une interpolation.

Exigences :

- Un **évaluateur d'expressions restreint** est écrit en Rust (§5.7) : nombres, `x`, `+ - * /`, parenthèses, fonctions de la liste blanche (`abs`, `exp`, `log`, `log10`, `sqrt`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `sinh`, `cosh`, `tanh`, `floor`, `ceil`, `round`, `min`, `max`, `pow`). Toute autre construction (attribut, appel inconnu, `**` avec exposant non entier, accès à un nom global) est **refusée à la compilation du catalogue** avec un message précis et un numéro de ligne.
- La **fonction inverse** doit être fournie par l'équation ou obtenue par inversion numérique (recherche de racine sur un intervalle documenté), avec une tolérance déclarée ; en cas d'échec, l'erreur cite le catalogue et la ligne.
- L'interpolation linéaire se fait entre les points fournis ; **hors intervalle**, le comportement est celui du Python (extrapolation par les deux points extrêmes) et doit être vérifié par le corpus golden.
- Une unité non linéaire ne peut pas entrer dans une combinaison multiplicative : `C m` est une erreur (`non-linear unit in a product`), conformément au modèle ConvertAll.
- Les non-linéaires restent dans les fichiers de données : **aucun code Rust n'est écrit pour une température en particulier**.

### 3.6 Sorties

| Mode | Déclencheur | Contenu |
|---|---|---|
| Texte (défaut) | — | `5 ft 10 in = 177.8 cm`, exactement le format Python |
| JSON | `--json` | Objet unique, schéma versionné (§ annexe C) |
| JSONL | `--json-lines` (mode lot) | Un objet JSON par ligne d'entrée |
| TSV | `--tsv` | `input<TAB>value<TAB>from<TAB>to<TAB>result` — en-tête optionnel `--header` |
| Silencieux | `-q` combiné à `--json`/`--tsv` | Aucun texte humain sur `stdout` |

Règles transverses : les **résultats** vont sur `stdout`, les **messages** (erreurs, avertissements, invites) sur `stderr`. Aucune couleur si `stdout` n'est pas un terminal, si `NO_COLOR` est défini, ou si `--no-color`/`CLICOLOR_FORCE=0`. `--color=auto|always|never` explicite. Les tableaux (`cvt list`) sont alignés avec `unicode-width`, jamais tronqués, et restent lisibles en UTF-8 comme en `LC_ALL=C` (repli ASCII).

### 3.7 Mode lot

- Sources : arguments multiples, `--file FICHIER` (répétable, `-` = stdin), stdin par défaut si `--batch` sans fichier.
- Chaque ligne non vide et non commentée (`#`) est une demande de conversion. Une ligne peut contenir une seule demande complète (les morceaux de `units.dat` ne sont pas acceptés).
- `--continue-on-error` : les erreurs n'arrêtent pas le traitement ; le code de sortie final est 1 si au moins une ligne a échoué, 0 sinon.
- Sans `--continue-on-error`, la première erreur arrête tout : code 1, message sur `stderr` avec numéro de ligne.
- `--jobs N` (défaut 1, `0` = nombre de cœurs) : parallélisme sur l'ordre d'entrée, sorties dans l'ordre strict. Le mode lot parallèle est un objectif de performance (§5.7), pas un changement de sémantique.
- 1 M lignes : mémoire stable, aucune fuite, débit ≥ 100 000 conversions/s.

### 3.8 REPL interactif

Bibliothèque : `rustyline` (**18.0.1**, juin 2026).

- Invite : `> ` (personnalisable `--prompt`), en couleur si TTY.
- **Complétion Tab** : noms d'unités depuis le catalogue chargé, types, mots-clés (`to`, `in`, `per`, `to unit`, `to base`), commandes internes.
- **Indices** en ligne (hint) : unité la plus probable, valeur réduite.
- **Historique** persistant dans `$XDG_STATE_HOME/cvt/history` (repli `~/.local/state/cvt/history`), `Ctrl-R` (recherche inverse), limite configurable, jamais de doublons consécutifs.
- Commandes internes, compatibles Python `-i` : `n` (nouvelle unité), `r` (inverser source/cible), `q` ou `Ctrl-D` (quitter, code 0), `Ctrl-C` (annuler la ligne, pas le programme ; code 130 uniquement si l'utilisateur quitte par une interruption d'entrée).
- `_` / `ans` : dernière valeur, utilisable comme nombre (`_ * 2 to cm`).
- Une ligne `?ft` ou `help ft` affiche la fiche d'unité sans quitter.
- Le REPL démarre aussi par `cvt repl` (équivalent de `cvt -i`).
- Aucune dépendance obligatoire à un terminal : si `stdin` n'est pas un TTY et que `cvt` est appelé sans argument, le REPL est remplacé par le mode lot (comportement documenté et testé).

### 3.9 Sous-commandes

| Commande | Rôle | Options principales |
|---|---|---|
| `cvt [OPTIONS] <DEMANDE>` | Conversion (forme historique, prioritaire pour la compatibilité) | `-d -f -s -e -q --json --tsv --no-color` |
| `cvt convert` | Forme explicite : `cvt convert 5 ft --to cm` | idem + `--to` |
| `cvt repl` / `cvt -i` | REPL | `--prompt`, `--history-file` |
| `cvt list` | Lister les unités | `--type T`, `--search REGEX`, `--sort name\|type`, `--json`, `--columns` |
| `cvt types` | Lister les 52 types | `--json` |
| `cvt info <UNITÉ>` | Fiche complète d'une unité | `--json`, `--show-aliases`, `--show-reduced` |
| `cvt check [FICHIERS...]` | Valider un/des catalogues (équivalent `-t`/`--test-all`) | `--json`, `--strict` |
| `cvt data compile <FICHIER> -o SORTIE` | Compiler un `.dat` en catalogue canonique (TOML) | `--format toml\|json`, `--sha256` |
| `cvt data verify <FICHIER>` | Vérifier l'intégrité d'un catalogue compilé | — |
| `cvt completions <SHELL>` | Générer la complétion | `bash zsh fish powershell elvish` |
| `cvt man` | Générer la page de manuel (roff) | `--out FICHIER` |
| `cvt doctor` | Diagnostic (versions, catalogues, locale, options) | `--json` |
| `cvt --version` / `-v` | Version (compat) | — |

`--help` (et `cvt help <commande>`) est **généré par clap** et capture, exhaustivement, l'ensemble des options de ce document ; le texte d'aide est testé en snapshot (§6.1).

### 3.10 Catalogues : lecture, compilation, personnalisation

Ordre de résolution (le premier gagne, les suivants complètent ou surchargent selon la règle) :

1. `--catalog FICHIER` (répétable) — source explicite, la plus prioritaire ;
2. `--units-file FICHIER` — alias de compatibilité, ajoute des unités utilisateur ;
3. `$XDG_CONFIG_HOME/convertall/cvt.units` (repli `~/.config/convertall/cvt.units`) ;
4. catalogue embarqué dans le binaire (`include_str!` du catalogue compilé, §7.3) ;
5. locales : `units_<lang>.dat` **si** la locale est demandée et le fichier présent, avec **repli sur le catalogue anglais** (jamais d'erreur).

Le chargement est visible : `cvt doctor --json` indique pour chaque catalogue son chemin, son SHA-256, le nombre d'unités et la version de format.

`cvt data compile` produit un fichier **canonique et déterministe** : mêmes entrées → mêmes octets (tri stable, nombres écrits en fraction exacte quand c'est possible, commentaires conservés), en-tête `# généré par cvt <version> depuis <fichier> sha256=<…>`. C'est ce fichier qui est embarqué dans les binaires officiels, et il est diffable en revue.

### 3.11 Configuration et état

- `$XDG_CONFIG_HOME/convertall/cvt.toml` (repli `~/.config/convertall/cvt.toml`) : décimales, notation, couleur, locale, catalogue(s), `jobs`, `prompt`, `history_size`.
- Précédence : options de ligne de commande > variables d'environnement > fichier de configuration > valeurs par défaut.
- Variables : `CVT_CONFIG`, `CVT_CATALOG`, `CVT_DECIMALS`, `CVT_NOTATION`, `CVT_LOCALE`, `CVT_JOBS`, `NO_COLOR`, `CLICOLOR_FORCE`, `XDG_*`.
- Aucune écriture hors de `$XDG_*` ; `cvt` ne crée aucun fichier s'il n'écrit pas d'historique (mode non interactif). Un `--no-config` permet de tester l'état vierge.

### 3.12 Internationalisation

- **Messages** (`help`, erreurs, avertissements, invites) : Fluent (`fluent-bundle` + `unic-langid` + `i18n-embed`), fichiers `locales/<lang>/*.ftl` embarqués, catalogue anglais complet obligatoire, repli en cascade.
- **Données** (noms d'unités et commentaires) : via les catalogues `units_<lang>.dat` existants, donc sans duplication de travail de traduction.
- Langues cibles v1.0 : `en`, `fr`, `de`, `es`, `ca`, `ru`, `sv` — exactement celles du dépôt.
- Sélection : `--locale`, sinon `LC_ALL`/`LC_MESSAGES`/`LANG`, sinon anglais. `LC_ALL=C` → anglais, ASCII, pas de couleur.
- Tests : un test vérifie que **chaque clé Fluent anglaise existe** dans chaque locale (échec si manquante) ; un second vérifie qu'aucune traduction ne casse le formatage (arguments identiques).

---

## 4. Contrat d'interface

### 4.1 Options globales

| Option courte | Option longue | Argument | Effet |
|---|---|---|---|
| `-d` | `--decimals` | `N` (0–12) | Décimales affichées ; hors bornes → code 2 |
| `-f` | `--fixed-decimals` | — | Notation fixe, zéros de fin conservés |
| `-s` | `--sci-notation` | — | Notation scientifique |
| `-e` | `--eng-notation` | — | Notation ingénierie |
| `-q` | `--quiet` | — | Aucune invite, aucun avertissement ; erreur si une unité manque |
| `-i` | `--interactive` | — | REPL |
| `-t` | `--test` | — | Valider le catalogue courant |
| | `--test-all` | — | Valider tous les catalogues trouvés |
| `-v` | `--version` | — | Version et sortie |
| | `--catalog` | `FICHIER` | Catalogue explicite (répétable) |
| | `--units-file` | `FICHIER` | Unités utilisateur supplémentaires |
| | `--locale` | `LANG` | Locale des messages et des données |
| | `--json` | — | Sortie JSON |
| | `--json-lines` | — | Sortie JSONL (lot) |
| | `--tsv` | — | Sortie TSV |
| | `--header` | — | En-tête pour TSV |
| | `--batch` | — | Mode lot (stdin) |
| | `--file` | `FICHIER` | Fichier d'entrées (répétable, `-` = stdin) |
| | `--continue-on-error` | — | Lot tolérant |
| | `--jobs` | `N` | Parallélisme (0 = auto) |
| | `--color` | `auto\|always\|never` | Couleur |
| | `--no-color` | — | Équivalent `--color=never` |
| | `--no-config` | — | Ignorer le fichier de configuration |
| | `--prompt` | `CHAÎNE` | Invite du REPL |
| | `--history-file` | `FICHIER` | Chemin de l'historique |
| | `--verify` | — | Revalider le catalogue avant de convertir |
| `-h` | `--help` | — | Aide (clap) |

**Stabilité** : tout ajout est rétrocompatible ; une option retirée passe par une période de dépréciation d'une version mineure avec avertissement, puis suppression majeure.

### 4.2 Codes de sortie

| Code | Signification | Compatibilité |
|---|---|---|
| `0` | Succès | Identique au Python |
| `1` | Erreur de conversion ou de données (unité inconnue, unités incompatibles, résultat non fini) | Identique au Python |
| `2` | Erreur d'usage (option invalide, argument manquant, nombre de décimales hors bornes) | Identique au Python |
| `3` | Catalogue invalide ou illisible (fichier absent, cycle, équation refusée) | **Nouveau**, justifié : `check` doit distinguer « données cassées » de « conversion impossible » |
| `4` | Erreur de configuration (TOML invalide, `CVT_*` incohérent) | **Nouveau** |
| `130` | Interruption (`SIGINT` au clavier) | Identique au Python |

En mode lot avec `--continue-on-error`, le code final est `0` si toutes les lignes ont réussi, sinon `1` (les codes 3/4 restent réservés aux erreurs globales). Cette règle est documentée dans `--help` et dans la page de manuel.

### 4.3 Format des messages

- Une erreur tient en **une ligne** sur `stderr`, préfixée par `error:`, suivie d'un `hint:` optionnel et d'un `see also:` optionnel :

```text
error: unknown unit "mtr" (nearest: "m", "mt", "mi")
hint: run `cvt list --search mtr` to inspect the catalogue
```

- Les erreurs d'usage (clap) gardent le format clap, avec `Usage:` et le code 2.
- En mode lot, chaque ligne fautive est préfixée par `line N:`.
- `--verbose` (et `CVT_VERBOSE=1`) ajoute les causes profondes ; `RUST_BACKTRACE` n'est jamais exigé de l'utilisateur pour une erreur attendue (aucun `panic!` ne doit être atteignable par une entrée utilisateur — exigence testée par fuzzing et par des tests « panic-free »).

### 4.4 Comportement selon le contexte

| Contexte | Attendu |
|---|---|
| `stdout` non-TTY | Pas de couleur, pas de tableau large, pas d'invite |
| `stdin` non-TTY sans argument | Mode lot implicite |
| Terminal étroit (`COLUMNS` < 60) | `cvt list` réduit les colonnes, jamais de troncature des noms |
| `LC_ALL=C` | Messages en anglais, ASCII, pas de couleur |
| `TZ`/date | Aucun effet (aucune conversion dépendante du temps) |
| Signaux | `SIGINT` → 130 et sortie propre, jamais d'historique corrompu |

---

## 5. Architecture technique Rust

### 5.1 Langage, édition, MSRV

- Édition **2024** (stable depuis Rust 1.85), toolchain de développement **Rust 1.99** (stable du 01/10/2026).
- **MSRV : 1.85**, relevée seulement si une dépendance l'exige, et vérifiée en CI par un job dédié (`cargo build` avec la toolchain MSRV déclarée). Toute relève est documentée dans le journal des changements.
- `#![forbid(unsafe_code)]` dans tous les crates. Aucun `unwrap()`/`expect()` sur un chemin d'entrée utilisateur (revue + lint `clippy::unwrap_used`).
- `panic = "abort"` en profil release (binaire plus petit, pas de démêlage inutile), `lto = "fat"`, `codegen-units = 1`, `strip = "symbols"`.
- `Cargo.lock` versionné ; builds de release en `--locked`.

### 5.2 Organisation du workspace

```text
convertall-rs/
├── Cargo.toml                 # workspace, lints partagés
├── crates/
│   ├── convertall-core/       # modèle, arithmétique exacte, conversion, formatage
│   ├── convertall-catalog/    # lecture .dat, évaluateur restreint, compilation, validation
│   ├── cvt-cli/               # binaire : clap, sorties, lot, REPL
│   └── convertall-i18n/       # messages Fluent (optionnel, peut vivre dans cvt-cli)
├── data/                      # copie synchro ou sous-module du dépôt ConvertAll (units*.dat)
├── locales/                   # *.ftl
├── tests/                     # intégration CLI, corpus golden, tests différentiels
├── benches/                   # criterion
├── fuzz/                      # cargo-fuzz (hors workspace par défaut)
└── .github/workflows/         # CI + release (cargo-dist)
```

Découpage imposé : **`cvt-cli` ne contient aucune logique de conversion** (elle appelle `convertall-core`) ; `convertall-catalog` ne connaît ni clap ni terminal ; `convertall-core` ne fait **aucune E/S** (aucun `std::fs`, aucun accès réseau) — testable seule, embarquable, transposable en WASM.

### 5.3 Dépendances

| Crate | Version visée | Rôle | Justification / alternatives écartées |
|---|---|---|---|
| `clap` (features `derive`, `env`, `wrap_help`) | **4.6.7** (14/09/2026) | Analyse des arguments, aide, erreurs d'usage | Référence de l'écosystème ; `lexopt`/`pico-args` écartés : aide et validation moins complètes |
| `clap_complete` | **4.6.5** | Complétion bash/zsh/fish/powershell/elvish | Officiel, aligné sur clap |
| `clap_mangen` | **0.3.0** | Page de manuel générée | Évite un manuel écrit à la main qui divergerait |
| `dashu-ratio` (via `dashu`) | **0.6.0** | Rationnels exacts (`RBig`) | Pur Rust (musl statique facile) ; les benchmarks de l'auteur donnent ≈ 10,7 ms contre 76,4 ms pour `num-rational` et 1,3 ms pour `rug` sur `fib(2000)` — `num-rational` est écarté pour la performance, `rug` (GMP/C) pour la portabilité statique |
| `num-traits` | 0.2 | Traits numériques communs | Nécessaire pour écrire le code générique `Exact/Float` |
| `thiserror` | 2.x | Erreurs typées des bibliothèques | Standard, sans coût à l'exécution |
| `miette` **ou** `annotate-snippets` | selon J0 | Diagnostics avec extrait de ligne du catalogue | Objectif : montrer la ligne fautive de `units.dat` ; à trancher au spike (poids vs lisibilité) |
| `serde`, `serde_json` | 1.x | Sortie JSON, catalogues compilés | Standard |
| `toml` | 0.9.x | Configuration, catalogue canonique | Le plus utilisé pour ce format |
| `fluent-bundle`, `unic-langid`, `i18n-embed` | `fluent-bundle` **0.16** + `unic-langid` 0.9 + `i18n-embed` 0.15 | Messages localisés | Fluent gère pluriels et genres proprement ; `gettext-rs` écarté (dépendance C, héritage) — le projet Python laisse des catalogues mais la traduction des *messages* doit être propre |
| `rustyline` | **18.0.1** (24/06/2026) | REPL : historique, complétion, hints | Référence du readline en Rust, multiplateforme (y compris Windows) ; `reedline` écarté (orienté shells, plus lourd) |
| `anstream` / `anstyle` | versions alignées sur clap | Couleur, détection TTY, `NO_COLOR` | Évite une dépendance de couleur ad hoc |
| `directories` | 6.x | Chemins XDG multiplateformes | Config/état sans réinventer la logique Windows/macOS |
| `unicode-width` | 0.2.x | Alignement des tableaux | Indispensable pour `list` en Unicode |
| `memchr` | 2.x | Tokenisation rapide du `.dat` et des entrées | Micro-optimisation utile et stable |
| *(dev)* `assert_cmd`, `predicates` | 2.x / 3.x | Tests d'intégration du vrai binaire | Teste codes de sortie, `stdout`/`stderr` réels |
| *(dev)* `insta` | 1.x | Snapshots (aide, erreurs, sorties) | Les messages sont un contrat : ils doivent être figés |
| *(dev)* `proptest` | 1.x | Propriétés (aller-retour, compatibilité) | Trouve les cas limites numériques |
| *(dev)* `criterion` | 0.8.x | Benchmarks | Référence pour la mesure des budgets |
| *(dev)* `trycmd` | 1.x | Tests de sortie de documentation/CLI | Optionnel, à évaluer |
| *(outils CI)* `cargo-nextest`, `cargo-llvm-cov`, `cargo-deny`, `cargo-audit`, `cargo-machete`, `cargo-dist` (**0.33.0**, 10/09/2026), `cargo-deb` | versions courantes | Exécution des tests, couverture, licences/advisories, dépendances inutilisées, paquets et release | Chaîne standard 2026 |

Toute dépendance nouvelle est justifiée en revue (règle : le coût de compilation et la surface d'audit doivent être explicites dans la PR).

### 5.4 Chaîne de traitement interne

```text
[1] Chargement      : .dat ou .toml → Unit définitives (validate, cycles)
[2] Compilation     : équations → closure/fonction; interpolation → table indexée
[3] Résolution      : entrée → Number + UnitGroup (liste d'atomes, exposants)
[4] Compatibilité   : comparaison des dimensions réduites (vecteur d'exposants)
[5] Conversion      : (valeur, unité source) → (valeur, unité cible)
                      - linéaire  : v_cible = v_source * facteur_source / facteur_cible (rationnel exact)
                      - non linéaire: v_equiv = f_source(v) puis v_cible = f_cible⁻¹(v_equiv)
[6] Formatage       : décimale/scientifique/ingénierie, décimales, signes, unité affichée
[7] Sortie          : texte | JSON | JSONL | TSV
```

Points de conception :

- **Réduction** : chaque unité est réduite une fois au chargement en `(facteur_rational, exposants_sur_primitives, booléen_linéaire)`. Une conversion linéaire ne fait ensuite qu'une multiplication/division de rationnels et une comparaison de vecteurs.
- **Détection de cycles** : tri topologique avec détection de dépendance circulaire, message citant la chaîne complète (`a → b → c → a`), code 3.
- **Unités combinées** : un `UnitGroup` est une liste d'atomes avec exposants ([2], `/`, parenthèses, `per`) ; `5 ft 10 in` est un groupe de deux atomes **additifs** (la somme est convertie dans l'unité cible), `mi/hr` un groupe multiplicatif.
- **Non linéaires** : les équations sont compilées en un petit arbre d'expression interprété (pas de génération de code, pas de `dyn Fn` par unité pour rester simple et auditable) ; l'inversion utilise la seconde équation quand elle existe, sinon une recherche de racine (bissection/Newton avec intervalle et tolérance déclarés).
- **Arrondi** : entier, jamais de `f64` sur le chemin exact ; arrondi « demie au pair » non applicable (on arrondit une décimale de rationnel, pas un binaire).
- **Zéro-copie** : les noms du catalogue sont `&'static str` (catalogue embarqué) ou internés dans une `String` unique (`String` arena) ; une conversion en mode lot ne réalloue pas.

### 5.5 Exactitude et compatibilité avec le Python

| Aspect | Règle |
|---|---|
| Facteurs | Rationnels exacts (le Python utilise `float` : `0.1` n'y est pas exact). Divergence **admise et documentée**, uniquement dans le sens « Rust est plus exact ». |
| Non linéaires | `f64`, mêmes formules que le catalogue, mêmes fonctions → résultats identiques à l'ulp près ; le corpus golden fixe les cas sensibles (températures, gas mark). |
| Affichage | Identique au caractère près pour le corpus golden ; toute différence est un **bug**, sauf si elle découle d'une divergence de facteur documentée. |
| Avertissements/erreurs | Texte identique pour les messages historiques (`Units X and Y are not compatible`, `... is not a valid unit`, `Number must be finite`). |
| Tolérance de comparaison | Pour les non-linéaires : égalité sur la chaîne affichée, et |Δ| ≤ 1e-12 en relatif sur la valeur. |

### 5.6 Budgets de performance et techniques

| Chemin | Budget | Technique |
|---|---|---|
| Démarrage | < 10 ms | Catalogue embarqué, aucune allocation avant l'analyse des arguments, `clap` compilé en release |
| Conversion simple | < 15 ms total | Résolution paresseuse : seules les unités citées sont complètement réduites (cache d'unités par nom) |
| Lot 1 M lignes | ≥ 100 000 conv./s | Réutilisation des tampons, pas de formatage intermédiaire, sortie `BufWriter` avec verrou unique |
| Mémoire | < 15 Mo | Pas de duplication du catalogue, `arena` pour les chaînes d'unités |
| Binaire musl | < 6 Mo | `lto=fat`, `codegen-units=1`, `strip`, pas de `regex` lourd sur le chemin chaud |

Les budgets sont **vérifiés en CI** (`criterion` + `hyperfine`) ; une régression de plus de 10 % sur un benchmark échoue la CI.

### 5.7 Sécurité, robustesse, entrées hostiles

- **Aucun code Python, aucun `eval`, aucune commande externe** n'est exécuté à partir des données ou de l'entrée. Les expressions non linéaires du catalogue passent par l'évaluateur restreint (§3.5).
- **Limites** : longueur d'entrée maximale (1 MiB par ligne en mode lot), profondeur de parenthèses maximale (64), nombre d'atomes maximal (256) — dépassements = erreur propre, code 1/2, jamais une panique ni un dépassement de pile.
- **Fuzzing** (cargo-fuzz) sur trois cibles : `parse_dat`, `parse_request`, `format_output`, plus un corpus régressif versionné.
- `cargo-audit` + `cargo-deny` (licences autorisées : MIT, Apache-2.0, BSD, ISC, Unicode-3.0, Zlib, MPL-2.0 ; GPL-2.0+ pour le projet, voir §8) en CI, à chaque PR et chaque semaine.
- Aucune écriture hors des chemins XDG ; aucune télémétrie ; aucun accès réseau (testé : un test échoue si une dépendance réseau apparaît dans l'arbre).

### 5.8 Surface de bibliothèque (`convertall-core`)

API publique minimale, pensée pour durer :

```rust
pub struct Catalog { /* unités, types, primitives */ }
impl Catalog {
    pub fn from_dat(src: &str) -> Result<Catalog, CatalogError>;
    pub fn from_toml(src: &str) -> Result<Catalog, CatalogError>;
    pub fn resolve(&self, name: &str) -> Option<&Unit>;
    pub fn search(&self, query: &str) -> impl Iterator<Item = &Unit>;
    pub fn check(&self) -> Result<Report, Vec<CatalogError>>;
}

pub struct Request<'a> { pub value: Number, pub from: &'a str, pub to: &'a str }
pub struct Outcome { pub value: Number, pub exact: bool, pub text: String /* rendu par le formateur choisi */ }

pub fn convert(catalog: &Catalog, request: &Request<'_>, options: &Options)
    -> Result<Outcome, ConvertError>;
```

`Number` est un type scellé `Exact(RBig) | Float(f64)` : le reste du programme ne manipule jamais directement un `f64`, ce qui rend les divergences d'exactitude visibles et testables. La bibliothèque n'écrit rien, ne lit rien, ne panique pas : `Result` uniquement.

---

## 6. Qualité, tests et critères d'acceptation

### 6.1 Pyramide de tests

| Niveau | Outil | Ce qui est couvert | Exigence |
|---|---|---|---|
| Unitaire | `cargo test` / `cargo nextest` | Arithmétique rationnelle, réduction, évaluateur restreint, formatage, parseur `.dat` | Chaque fonction publique a au moins un test ; cas limites déclarés |
| Intégration CLI | `assert_cmd` + `predicates` | Vrai binaire : options, codes de sortie, `stdout`/`stderr`, fichiers | Toutes les options du §4.1 testées (succès **et** échec) |
| Snapshots | `insta` | Texte d'aide, messages d'erreur, sortie JSON, `list`, `info`, `check` | Un snapshot par sortie stable ; revue obligatoire de tout diff |
| Propriétés | `proptest` | Aller-retour `convert(x, a→b)` puis `b→a` ≈ x ; compatibilité commutative ; monotonie des non-linéaires | Propriétés déclarées dans le code, régressions versionnées sous `proptest-regressions/` |
| Golden | corpus de fichiers | 500+ conversions de référence, dont non-linéaires, unités composées, fractions, bornes | 100 % de réussite, aucune tolérance sur le texte |
| Différentiel | script + corpus | Comparaison Rust ↔ ConvertAll-py (§6.2) | 100 % d'égalité, hors divergences documentées |
| Fuzzing | `cargo fuzz` | `parse_dat`, `parse_request`, `format_output` | 5 minutes par cible en CI nocturne, 0 panique sur 24 h |
| Panique interdite | test dédié | Entrées aléatoires/ineptes | Aucune sortie non-`Result` : le binaire ne doit jamais imprimer `panicked at` |
| Docs | `cargo test --doc` | Exemples de la bibliothèque | Tous les exemples compilent et s'exécutent |

La place du **snapshot** est structurante : l'aide, les messages et le JSON sont des contrats publics. Modifier un message sans mettre à jour le snapshot échoue la CI, ce qui rend la revue explicite.

### 6.2 Test différentiel contre ConvertAll-py (exigence centrale)

La fidélité au projet Python n'est pas une intention, c'est un test :

1. **Génération** : un script (Python, hors CI obligatoire) produit un corpus de demandes à partir du catalogue : nombres aléatoires (dont fractions et notations scientifiques), unités paires compatibles, unités composées, unités non linéaires, cas limites (unités incompatibles, noms inexistants).
2. **Exécution** : le même corpus est passé à `python3 source/convertall.py -q …` (référence) et à `cvt -q …` (candidat).
3. **Comparaison** : égalité stricte des sorties texte et des codes de sortie. Les divergences attendues (facteurs exacts vs `float`) sont déclarées dans un fichier de tolérances **avec justification**, jamais contournées silencieusement.
4. **Corpus figé** : les 500+ cas les plus significatifs sont versionnés (`tests/golden/*.txt`) et exécutés en CI **sans Python**, pour que la parité reste vérifiable après coup.
5. **Non-régression** : toute correction de divergence ajoute un cas au corpus golden.
6. **Indépendance de version** : le corpus enregistre la version de ConvertAll-py utilisée (`0.9.1`) et son SHA ; un changement de catalogue invalide le corpus (échec volontaire).

### 6.3 Couverture

- Cible : **≥ 90 % de couverture de lignes**, plancher bloquant en CI : **80 %** (`cargo llvm-cov --fail-under-lines 80`), soit le même seuil que le projet Python.
- Rapports publiés en artefact (`lcov`), comparaison avec la référence sur la branche principale.
- Exclusion justifiée uniquement (`#[coverage(off)]` documenté), jamais pour « faire passer » le chiffre.

### 6.4 Lints et hygiène

`cargo fmt --check`, `cargo clippy --all-targets --all-features -- -D warnings` (avec `clippy::pedantic` en avertissement, `unwrap_used`/`expect_used` niés hors tests), `cargo machete` (dépendances inutilisées), `cargo deny check` (licences, advisories, sources), `cargo audit`, `cargo publish --dry-run` sur chaque crate destiné à publication.

### 6.5 CI

| Job | Déclencheur | Contenu | Budget |
|---|---|---|---|
| `test` | PR + push | `nextest` sur Linux, macOS, Windows (toolchain stable) | < 5 min |
| `msrv` | PR + push | `cargo build` avec Rust 1.85 | < 3 min |
| `lint` | PR + push | fmt, clippy, machete, deny, audit | < 3 min |
| `coverage` | PR | `llvm-cov`, seuil 80 % | < 8 min |
| `fuzz` | nocturne | 3 cibles × 5 min | < 20 min |
| `bench` | nocturne + PR étiquetée | `criterion`, comparaison à la référence | < 15 min |
| `differential` | PR (sans Python) + nocturne (avec Python) | Corpus golden puis génération complète | < 10 min |
| `package` | tag | `cargo-dist` : binaires, `.deb`, tarballs, checksums, attestations | < 25 min |

Le projet suit le modèle éprouvé du dépôt Python : **CI verte exigée sur le SHA exact avant toute publication**, jamais de publication automatique depuis une branche de travail.

### 6.6 Critères d'acceptation globaux (Definition of Done)

Une fonctionnalité est terminée si et seulement si : le code est fusionné avec tests unitaires **et** un test d'intégration CLI ; l'aide et les messages sont couverts par un snapshot ; la documentation (`README.md`, page de manuel, `--help`) est à jour ; la couverture ne baisse pas ; aucun `unsafe`, aucun `unwrap` de chemin utilisateur ; le comportement est vérifié contre le corpus golden ; et, si la fonctionnalité touche au calcul, le test différentiel passe.

Checklist de release (à valider par l'utilisateur, comme pour ConvertAll-py) :

1. CI verte sur le SHA tagué (tous les jobs) ;
2. `cvt check data/*.dat` vert sur les 7 catalogues ;
3. corpus golden et différentiel verts ;
4. couverture ≥ 90 % (plancher 80 %) ;
5. binaires produits pour toutes les cibles de §7.1, installés et testés **manuellement** sur au moins une distribution Debian/Ubuntu réelle et un Windows ;
6. `.deb` installé/vérifié/purgé à la main (`apt install`, `apt remove`) ;
7. licence et attributions vérifiées (`cargo deny`, `LICENSE`, mention GPL, sources fournies) ;
8. notes de version rédigées, brouillon de release **seulement** ; publication « Latest » décidée après acceptation manuelle.

---

## 7. Distribution et exploitation

### 7.1 Cibles de compilation

| Cible | Statut v1.0 | Usage |
|---|---|---|
| `x86_64-unknown-linux-musl` | Obligatoire | Binaire statique universel (Debian 12/13, Ubuntu, Alpine, conteneurs `scratch`) |
| `x86_64-unknown-linux-gnu` | Obligatoire | Version liée à la glibc, plus petite, pour les paquets Debian |
| `aarch64-unknown-linux-musl` | Obligatoire | Raspberry Pi 4/5, serveurs ARM, macOS Apple Silicon via Rosetta en secours |
| `aarch64-apple-darwin`, `x86_64-apple-darwin` | Obligatoire | macOS (Intel et Apple Silicon) |
| `x86_64-pc-windows-msvc` | Obligatoire | Windows 10/11 x64 |
| `aarch64-pc-windows-msvc`, `riscv64gc-*`, `s390x-*` | Souhaité (post-1.0) | À activer dès que la CI le permet |

Windows : sortie texte sensée dans `cmd.exe` (pas de UTF-8 invalide), `Ctrl-C` propre, `rustyline` fonctionnel (`cmd.exe`/PowerShell/Windows Terminal).

### 7.2 Canaux de distribution

| Canal | Outil | Contenu |
|---|---|---|
| GitHub Releases | `cargo-dist` **0.33.0** | Archives `.tar.gz`/`.zip` par cible, installeur, checksums SHA-256, attestations GitHub |
| Debian/Ubuntu | `cargo-deb` (profil `[package.metadata.deb]`) | `convertall-cli_<version>-1_amd64.deb` : binaire, page de manuel, complétions, `LICENSE`, `copyright` ; `Depends` minimal (musl statique → aucune dépendance) |
| `cargo binstall` | Métadonnées de release standard | Installation sans compilation |
| Homebrew | Formule dans un tap | `brew install <tap>/convertall-cli` |
| Communautaire | AUR, Nix, Scoop/WinGet | Contribué, non bloquant |
| Conteneurs | Image `scratch` + binaire musl | Documentée, non publiée en v1.0 |

Aucun paquet ne doit dépendre de Python, de Qt, de `sip` ni d'une bibliothèque C. Le `.deb` **n'embarque pas** de runtime : c'est un binaire autonome, conformément au choix déjà fait pour la version Python (paquet léger, dépendances gérées par `apt`).

### 7.3 Données embarquées et synchro avec ConvertAll-py

- Le catalogue compilé (`units.toml`, produit par `cvt data compile`) est embarqué via `include_str!` : le binaire est autonome et fonctionne sans fichier externe.
- Le binaire expose `cvt doctor --json` avec le SHA-256 du catalogue **embarqué** et, le cas échéant, du catalogue **surchargé** : on sait toujours ce qui a servi.
- **Synchronisation** : un job CI compare le catalogue embarqué au fichier du dépôt ConvertAll-py (relation documentée : sous-module Git, ou copie + contrôle de SHA). Une divergence échoue la CI ; elle n'est jamais tolérée en silence.
- Mise à jour du catalogue = un commit dédié (`data: sync units.dat <sha>`), donc revue et journal des changements.

### 7.4 Version, compatibilité, maintenance

- **SemVer** : `0.x` avant 1.0 (ruptures possibles sur les mineures, annoncées), `1.0` dès que le contrat CLI et le schéma JSON sont considérés stables.
- **Schéma JSON versionné** (`schema_version: 1`) : l'ajout de champs est autorisé en mineure, la suppression en majeure seulement.
- **MSRV** : politique explicite (relève au maximum une fois par an, documentée, vérifiée par un job).
- **Dépréciations** : toute option retirée est d'abord dépréciée (avertissement `stderr`, mention dans `--help`), puis supprimée après une version mineure complète.
- **Support** : la dernière version mineure reçoit les correctifs ; aucune promesse de support des versions antérieures.
- **Pas de télémétrie, pas d'auto-mise à jour** : un binaire qui se met à jour tout seul est un risque non maîtrisé et complique les paquets (le gestionnaire de paquets possède les fichiers). Le contrôle de version est laissé à `apt`/`brew`/`binstall`.

---

## 8. Licence, attribution et gouvernance

### 8.1 Licence du produit

- **Le binaire et les bibliothèques Rust : GNU GPL v2 ou ultérieure (`GPL-2.0-or-later`).** Ce n'est pas un choix esthétique : le catalogue `data/units.dat` et les catalogues traduits sont sous GPL (« GNU General Public License, Version 2 » dans leurs en-têtes), et un binaire qui les embarque doit respecter ces termes.
- **Compatibilité des dépendances** : toutes les dépendances listées en §5.3 sont sous MIT/Apache-2.0/BSD/ISC/Unicode — compatibles avec la GPL. `cargo deny` impose la liste blanche des licences et échoue sur toute exception ; aucune dépendance copyleft incompatible n'est admise.
- **Conséquence pratique** : les sources complètes de chaque binaire publié sont disponibles (dépôt + archive de sources par release), l'`include_str!` du catalogue n'ajoute aucune restriction supplémentaire (il est déjà GPL), et le champ `Homepage`/`Repository` des paquets pointe le dépôt.
- **À faire confirmer avant J1** : l'auteur d'origine de ConvertAll (Douglas W. Bell) doit être informé et le maintien du choix « version 2 ou ultérieure » doit être explicite pour le nouveau projet. Le fichier `COPYING`/`LICENSE` et l'en-tête de chaque fichier Rust portent la mention GPL.

### 8.2 Attribution

- En-tête de licence dans chaque fichier source, mention de ConvertAll, de son auteur et du maintien actuel.
- `cvt --version` affiche : version, licence (GPL-2.0-or-later), « ConvertAll unit catalogue © Douglas W. Bell and contributors », et le SHA du catalogue.
- La page de manuel reprend cette attribution ; le `README` explique la relation avec ConvertAll-py et avec ConvertAll Flutter (projet amont distinct).

### 8.3 Gouvernance et contribution

- Modèle : un mainteneur principal, revue obligatoire sur les PR touchant le cœur de calcul ou le catalogue ; décisions d'architecture consignées (`doc/adr/NNN-*.md`), comme ce document.
- `CONTRIBUTING.md` : `cargo nextest run` vert, `cargo fmt`, `clippy` sans avertissement, test ajouté pour tout correctif, snapshot mis à jour explicitement, aucune dépendance ajoutée sans justification dans la PR.
- Traductions : les fichiers `locales/*.ftl` et les catalogues `units_*.dat` sont acceptés en contribution séparée ; un test garantit que le catalogue anglais reste complet.
- Nom et marque : `cvt` et `convertall-cli` sont des noms techniques ; la mention « ConvertAll » reste une référence au projet d'origine (voir §8.2), sans revendication de marque.

---

## 9. Planning, jalons et risques

### 9.1 Jalons

| Jalon | Contenu | Critères d'acceptation | Estimation |
|---|---|---|---|
| **J0 — Spike** (mesures et décisions) | Lire `units.dat` (parseur jetable), convertir 10 cas, mesurer démarrage/débit, trancher : `dashu` vs `num-rational`, `miette` vs `annotate-snippets`, granularité des crates | Rapport de mesures écrit, décisions d'architecture figées (ADR), 10 conversions justes | 3–5 j |
| **J1 — MVP** | `convertall-core` + `convertall-catalog` complets, `cvt 5 ft 10 in to cm`, options `-d/-f/-s/-e/-q/-v/-h`, codes 0/1/2, corpus golden initial (150 cas) | Parité sur le corpus MVP, 0 panique, couverture ≥ 85 % | 8–12 j |
| **J2 — Lot, JSON, REPL** | `--batch`, `--file`, `--json`, `--json-lines`, `--tsv`, `--continue-on-error`, `--jobs`, REPL complet, `list`/`types`/`info`, `completions`, `man` | US-05 à US-10, US-13 verts ; benchmarks dans les budgets | 8–12 j |
| **J3 — Parité et i18n** | Test différentiel complet contre ConvertAll-py, 500+ cas golden, catalogues `units_*.dat`, messages Fluent (en/fr/de/es/ca/ru/sv), `check`, `data compile/verify`, `doctor` | 100 % du corpus, 7 catalogues validés, 52 types listés | 8–12 j |
| **J4 — Paquets et CI** | Workflows CI (test/lint/coverage/fuzz/bench/differential), `cargo-dist`, `cargo-deb`, installations réelles Debian et Windows, page de manuel, complétions | Binaires pour toutes les cibles §7.1, `.deb` installé/purgé à la main, CI < 10 min sur PR | 5–8 j |
| **J5 — 1.0** | Documentation utilisateur, guide de migration depuis la CLI Python, notes de version, revue de licence et d'attribution, gel du schéma JSON | Checklist §6.6 complète, décision de publication par l'utilisateur | 3–5 j |

Total estimé : **35–55 j** hors traduction, à recaler après J0. Le projet peut s'arrêter après J1 avec un produit déjà utile (conversion + options compatibles) : c'est le point de sortie de secours.

### 9.2 Risques et parades

| Risque | Impact | Probabilité | Parade |
|---|---|---|---|
| Divergence d'exactitude Rust (`rationnel`) vs Python (`float`) sur certains cas | Élevé (parité) | Moyenne | Corpus différentiel étendu, fichier de divergences justifiées, option `--python-compat` qui force le calcul flottant, tests sur les cas limites (très petites/grandes unités, `5/9`) |
| Ambiguïté du format `units.dat` (jamais spécifié formellement) | Moyen | Élevée | Annexe B formalisée, parseur validé sur les 7 catalogues, refus explicite de tout ce qui n'est pas dans le sous-ensemble documenté, `data compile` produit un format canonique |
| Équations non linéaires impossibles à inverser dans le sous-ensemble accepté | Moyen | Faible | Le catalogue est connu (2 équations symétriques + 1 table) ; sinon inversion numérique avec intervalle, et refus explicite du catalogue si impossible |
| Dérive entre le catalogue embarqué et ConvertAll-py | Moyen | Moyenne | Job CI de comparaison de SHA (§7.3), commit dédié de synchronisation |
| Le REPL ajoute une dépendance fragile (terminal, Windows) | Faible | Moyenne | `rustyline` 18 multiplateforme, tests d'intégration avec `stdin` simulé, mode lot comme repli documenté |
| Périmètre qui gonfle (devises, TUI, CAS) | Moyen | Élevée | Non-objectifs écrits (§1.5), toute demande passe par une ADR |
| Effort sous-estimé (le catalogue a des cas tordus) | Moyen | Moyenne | J0 de mesure avant engagement, corpus golden comme indicateur avancement, sortie de secours après J1 |
| Licence : dépendance GPL-incompatible introduite par mégarde | Élevé (juridique) | Faible | `cargo deny` en CI avec liste blanche, revue de chaque nouvelle dépendance |
| Illusion de parité : tests qui comparent Rust à Rust | Élevé | Moyenne | Le corpus de référence est **produit par le Python**, jamais par le Rust ; le fichier golden est committé et versionné |

---

## 10. Annexes

### Annexe A — Grammaire complète (référence d'implémentation)

La grammaire de §3.2 est normative. S'y ajoutent les règles de désambiguïsation, qui doivent être **testées** :

| Entrée | Interprétation |
|---|---|
| `1 in to cm` | `in` = mot-clé de conversion (pouce à convertir) |
| `1 in in cm` | premier `in` = unité (pouce), second = mot-clé |
| `5 ft 10 in` | combinaison additive (`5 ft` + `10 in`) |
| `5 ft 10 in to cm` | idem, puis conversion |
| `3/8 in` | fraction de pouce |
| `1-3/8 in` | fraction mixte |
| `mi/hr`, `mi per hr`, `mi·hr⁻¹` | identiques |
| `m2`, `m^2`, `m²` | identiques (l'exposant sans `^` n'est accepté qu'avec `--allow-m2` ou une entrée documentée ; à trancher en J0 selon le corpus Python) |
| `cvt 1 in` (sans cible) | erreur d'usage, code 2, message clair (la CLI Python demande l'unité cible) |
| `cvt 1 m kg` | incompatibles, code 1, message historique |

### Annexe B — Format `units.dat` (spécification formelle)

Reprise des règles observées dans le fichier (925 lignes, 52 types) :

```text
ligne         = [ espaces ], [ contenu ], [ "#", commentaire ]
contenu       = section | primitive | unite | suite
section       = "[", nom_de_type, "]"                     (* ex. [mass] *)
primitive     = nom, "=", ( "!" | "!!" ), [ commentaire ]
unite         = nom, "=", [ quantité ], cible, [ commentaire ]
quantité      = expression restreinte à  * / + -  et aux nombres (*)
cible         = nom_unite | nom_unite "/" nom_unite | "[" , nom_unite , "]" , definition_nl
definition_nl = équation, ";", équation | liste_de_points      (* non linéaire *)
liste_de_points = "[", "(", x, ",", y, ")", { ",", "(", x, ",", y, ")" }, "]"   (* parfois sur plusieurs lignes avec "\" *)
commentaire   = texte libre ; le 1er devient la parenthèse après le nom,
                le 2e la colonne « commentaire » de la liste, les suivants sont ignorés
```

Règles de validation (toutes vérifiées par `cvt check`) :

1. Tout nom est unique dans un catalogue (en cas de doublon : erreur, code 3, avec les deux numéros de ligne).
2. Les primitives sont un sous-ensemble de `{kg, m, s, K, A, mol, cd, rad, sr, bit, unit}` et doivent couvrir chaque dimension utilisée.
3. Aucune référence circulaire ; toute unité se réduit aux primitives.
4. Une unité non linéaire ne peut pas apparaître dans un produit.
5. Les équations sont évaluées sur des points témoins ; un résultat non fini, négatif là où le domaine l'interdit, ou une discontinuité détectée sur l'intervalle de définition déclenche une erreur.
6. Tout ce qui sort du sous-ensemble (appel de fonction hors liste blanche, attribut, compréhension, `**` non entier, import) est **refusé**, jamais ignoré.

**Divergence numérique assumée et tracée** : le fichier contient des quantités comme `5/9.0`, que Python évalue en `0.5555555555555556` (float) alors que le Rust calcule `5/9` exactement. `cvt data compile` écrit donc les deux valeurs (`exact`, `python_float`) quand elles diffèrent, et `--python-compat` force le mode flottant. Le rapport de compilation liste ces écarts : aucun écart silencieux.

### Annexe C — Schéma JSON de sortie (`schema_version: 1`)

```json
{
  "schema_version": 1,
  "input": "5 ft 10 in to cm",
  "value_in": "5 ft 10 in",
  "value_out": "177.8 cm",
  "value": 177.8,
  "as_fraction": "889/5",
  "exact": true,
  "from": { "name": "ft in", "type": "length", "reduced": "m", "factor": "0.3048" },
  "to":   { "name": "cm", "type": "length", "reduced": "m", "factor": "0.01" },
  "notation": "general",
  "decimals": 8,
  "locale": "en",
  "catalog": { "file": "units.dat", "sha256": "…", "embedded": true },
  "tool": { "name": "cvt", "version": "1.0.0", "catalog_schema": 1 }
}
```

Erreur (même schéma, `--json`) :

```json
{ "schema_version": 1, "error": { "code": 1, "kind": "incompatible_units",
  "message": "Units m and kg are not compatible" } }
```

Règles : jamais de couleur dans le JSON, clés en `snake_case`, nombres décimaux en chaîne quand l'exactitude compte (`factor`, `value_in`), aucun champ supprimé sans changement majeur de `schema_version`.

### Annexe D — Corpus golden (extrait initial)

Les sorties marquées « SI » découlent de définitions exactes et servent de test d'installation ; les autres sont **figées par le test différentiel** (§6.2), jamais écrites à la main.

| Entrée | Sortie attendue | Origine |
|---|---|---|
| `cvt -q 1 in cm` | `1 in = 2.54 cm` | SI (exact) |
| `cvt -q 5 ft 10 in to cm` | `5 ft 10 in = 177.8 cm` | SI (exact) |
| `cvt -q 1 mi km` | `1 mi = 1.609344 km` | SI (exact) |
| `cvt -q 1 lb kg` | `1 lb = 0.45359237 kg` | SI (exact) |
| `cvt -q 0 C K` | `0 C = 273.15 K` | Non linéaire (équation) |
| `cvt -q 100 C F` | `100 C = 212 F` | Non linéaire (équation) |
| `cvt -q 1 m kg` | erreur, code 1, `Units m and kg are not compatible` | Comportement Python |
| `cvt -q -d 3 1 in cm` | `1 in = 2.540 cm` | Option `-d`/`-f` |
| `cvt -q --json 1 in cm` | JSON conforme à l'annexe C | Contrat |
| `cvt check data/units.dat` | `units.dat: 1 catalogue, N units`, code 0 | Contrat |
| `cvt list --type length --json` | liste JSON des unités de longueur | Contrat |

Le corpus final visé : **≥ 500 cas**, dont au moins 50 unités non linéaires, 50 combinaisons, 50 cas d'erreur, 50 cas de formatage.

### Annexe E — Écosystème Rust : alternatives étudiées

| Projet / crate | Nature | Pourquoi il ne suffit pas ici |
|---|---|---|
| **Numbat** (`numbat-cli`, `numbat` 1.24.0, MSRV 1.88, MIT/Apache-2.0) | Calculatrice scientifique avec unités de premier ordre, REPL, arithmétique rationnelle | Excellent outil, mais langage et catalogue **propres** : il ne lit pas `units.dat`, ne connaît ni les 52 types de ConvertAll ni ses unités non linéaires interpolées, et sa licence n'autorise pas la reprise du catalogue GPL |
| **GNU units** | Référence historique, conversion textuelle | Catalogue et syntaxe différents, pas de parité ConvertAll, packaging ancien |
| **Qalculate!** | Calculatrice, très large | Application complète (librairie C++), pas une CLI légère scriptable |
| **`uom` 0.38.0** | Analyse dimensionnelle à la compilation | Inadapté : les unités sont des **types** connus du compilateur, alors que le catalogue est dynamique (données externes, locales, utilisateur) |
| **`pubunit`** (UCUM, rationnels exacts) | Conversion UCUM exécutable | Démarche très proche (rationnels exacts, refus des produits non linéaires) et excellente référence pour la validation ; mais c'est un vocabulaire **UCUM** (`[ft_i]`), pas le catalogue ConvertAll ni ses noms d'unités et commentaires |
| **UnitMath**, **convertease** (Rust, CLI, JSON/CSV) | Convertisseurs unitaires simples | Périmètres restreints (poids/volume, quelques longueurs), aucun format de catalogue compatible |
| **`rustyline` 18.0.1**, **`clap` 4.6.7**, **`dashu-ratio` 0.6.0**, **`cargo-dist` 0.33.0** | Briques retenues | Voir §5.3 |

Conclusion : aucune brique existante ne couvre le besoin ; le projet se justifie par **la fidélité au catalogue ConvertAll et la parité avec l'implémentation Python**, pas par la conversion d'unités en général.

### Annexe F — Sources et références

**Dépôt ConvertAll-py (vérifié sur place)** : `data/units.dat` et `data/units_*.dat`, `source/cmdline.py` (options, codes de sortie 0/1/2/130), `source/optiondefaults.py` (`DecimalPlaces 8`, `Notation general`), `source/unitgroup.py` (`maxDecPlcs = 12`), `source/unitatom.py`, `README.md` (état 0.9.1, profils Python/PyQt6), en-têtes GPL-2.0.

**Recherches externes (consultées le 13 octobre 2026)** :

- clap 4.6.7 (14/09/2026) et clap_complete 4.6.5 — https://lib.rs/crates/clap , https://lib.rs/crates/clap_complete , https://github.com/clap-rs/clap/tags
- rustyline 18.0.1 (24/06/2026) — https://lib.rs/crates/rustyline
- dashu-ratio 0.6.0 — https://crates.io/keywords/rational ; benchmarks `dashu` vs `num-rational` vs `rug` — https://www.reddit.com/r/rust/comments/yr7a72/dashu_03_libraries_of_arbitrary_precision/ ; `rug` (GMP) — https://docs.rs/rug
- `uom` 0.38.0 — https://crates.io/keywords/units ; `pubunit` (UCUM, rationnels exacts) — https://docs.rs/pubunit/latest/pubunit/
- Numbat — https://lib.rs/crates/numbat-cli , https://numbat.dev/doc/example-numbat_syntax.html , https://crates.io/crates/numbat (MSRV 1.88)
- Fluent pour Rust — https://www.rustfaq.org/en/how-to-localize-a-rust-application-fluent-rs/ ; `i18n-embed`/`cargo-i18n` — https://crates.io/crates/cargo-i18n
- cargo-dist 0.33.0 (10/09/2026) — https://github.com/axodotdev/cargo-dist/releases ; cargo-deb (Rust ≥ 1.76, `[package.metadata.deb]`) — https://github.com/kornelski/cargo-deb
- Chaîne de test et d'audit Rust 2026 : `cargo-nextest`, `cargo-llvm-cov` (`--fail-under-lines`), `insta`, `proptest`, `criterion`, `cargo-fuzz`, `cargo-deny`, `cargo-audit`, `cargo-machete` — https://blog.rajpoot.dev/posts/rust/rust-tooling-cargo-2026/ , https://rustprojectprimer.com/measure/coverage.html , https://corgea.com/learn/rust-security-best-practices
- Rust stable courante : 1.99.0 (01/10/2026) — https://versionlog.com/rust/ ; édition 2024 depuis Rust 1.85 — https://releases.rs/docs/1.85.0/
- UCUM (vocabulaire de référence pour la vérification croisée) et NIST SP 811 (facteurs exacts) — à citer dans le rapport de J0.

---

### Résumé des décisions à valider avant J1

1. Nom du binaire : `cvt` (+ `convertall-cli`), ou `convertall` en remplacement complet de la CLI Python ?
2. Défaut d'exactitude : rationnel exact par défaut avec option `--python-compat`, ou l'inverse ?
3. Granularité des crates : 3 crates (`core`, `catalog`, `cli`) ou un seul crate au départ ?
4. Périmètre J1 : combien de cas golden minimum avant de déclarer le MVP utilisable ?
5. Emplacement du code : nouveau dépôt `convertall-rs` (recommandé) ou sous-dossier du dépôt actuel ?
6. Canal de diffusion prioritaire : GitHub Releases + `.deb`, ou d'abord `cargo install` ?
