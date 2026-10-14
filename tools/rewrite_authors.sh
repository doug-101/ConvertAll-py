#!/usr/bin/env bash
# Réattribue à Johan Polsinelli les commits écrits par l'outillage du portage.
#
# Deux niveaux, volontairement séparés :
#   * rien par défaut : le script montre seulement ce qu'il changerait ;
#   * --apply : réécrit la branche courante (les SHA changent !) ;
#   * --push  : force-pousse la branche réécrite (--force-with-lease).
#
# Ce que le script NE fait jamais : toucher master, toucher une autre branche,
# réécrire un tag, modifier une release, réattribuer Doug W. Bell, ou publier quoi
# que ce soit. Les tags et les releases publiés continuent donc de pointer leurs
# commits d'origine, ce qui reste cohérent avec les artefacts 0.9.1 déjà publiés.
set -uo pipefail

TARGET_NAME='Johan Polsinelli'
TARGET_EMAIL='83455892+jojo8356@users.noreply.github.com'
# Adresses réattribuées par défaut : uniquement l'outillage, jamais les vôtres.
REPLACE_EMAILS=('agent@arena.invalid')
# Adresses déjà vôtres, unifiées seulement si --include-own-variants est donné.
OWN_VARIANTS=('polsinelli@gmx.com' 'pj509414@S651P06L.campus.unice.fr')
BRANCH='arena/0adacf84-convertall-py'

APPLY=0
PUSH=0
INCLUDE_OWN=0
while (($#)); do
    case "$1" in
        --apply) APPLY=1 ;;
        --push) APPLY=1; PUSH=1 ;;
        --include-own-variants) INCLUDE_OWN=1 ;;
        --name) TARGET_NAME="$2"; shift ;;
        --email) TARGET_EMAIL="$2"; shift ;;
        -h|--help)
            sed -n '2,14p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            printf '\nOptions :\n'
            printf '  --apply                     réécrit la branche courante (SHA modifiés)\n'
            printf '  --push                      --apply puis force-push de la branche courante\n'
            printf '  --include-own-variants      unifie aussi vos autres identités connues\n'
            printf '  --name "Nom" --email "a@b"  autre cible (défaut : %s <%s>)\n' \
                   "$TARGET_NAME" "$TARGET_EMAIL"
            exit 0 ;;
        *) printf 'Option inconnue : %s\n' "$1" >&2; exit 2 ;;
    esac
    shift
done

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P) || exit 2
cd "$ROOT" || exit 2
CURRENT=$(git branch --show-current)
if [[ "$CURRENT" != "$BRANCH" ]]; then
    printf 'Réécriture refusée : ce dépôt ne réécrit que %s (branche courante : %s).\n' \
           "$BRANCH" "${CURRENT:-detached}" >&2
    exit 2
fi
if [[ -n "$(git status --porcelain)" ]]; then
    printf 'Arbre non propre : commitez ou remisez d’abord.\n' >&2
    exit 2
fi

if [[ "$INCLUDE_OWN" -eq 1 ]]; then
    REPLACE_EMAILS+=("${OWN_VARIANTS[@]}")
fi
# Construire le filtre d'environnement (fonctionne avec git filter-branch).
ENV_FILTER=$(cat <<FILTER
NEW_NAME='${TARGET_NAME}'
NEW_EMAIL='${TARGET_EMAIL}'
map_email() {
    case "\$1" in
$(for address in "${REPLACE_EMAILS[@]}"; do printf '        %s) printf %%s "$NEW_EMAIL" ;;\n' "$address"; done)
        *) return 1 ;;
    esac
}
if mapped=\$(map_email "\$GIT_AUTHOR_EMAIL"); then
    export GIT_AUTHOR_NAME="\$NEW_NAME" GIT_AUTHOR_EMAIL="\$mapped"
fi
if mapped=\$(map_email "\$GIT_COMMITTER_EMAIL"); then
    export GIT_COMMITTER_NAME="\$NEW_NAME" GIT_COMMITTER_EMAIL="\$mapped"
fi
FILTER
)

printf 'Cible        : %s <%s>\n' "$TARGET_NAME" "$TARGET_EMAIL"
printf 'Adresses     : %s\n' "${REPLACE_EMAILS[*]}"
printf 'Branche      : %s\n\n' "$BRANCH"
printf 'Commits concernés sur cette branche :\n'
# --no-use-mailmap est indispensable : git applique le .mailmap à --author, donc
# la recherche des anciennes adresses ne trouverait plus rien.
# Auteur et committer sont cherchés séparément : un commit écrit par l'outillage
# mais enregistré par une autre identité doit aussi être repris.
AFFECTED=''
for address in "${REPLACE_EMAILS[@]}"; do
    AFFECTED+=$(git log --no-use-mailmap --format='%H' --author="$address" "$BRANCH")$'\n'
    AFFECTED+=$(git log --no-use-mailmap --format='%H' --committer="$address" "$BRANCH")$'\n'
done
AFFECTED=$(printf '%s\n' "$AFFECTED" | sed '/^$/d' | sort -u)
if [[ -z "$AFFECTED" ]]; then
    printf '  aucun : rien à faire (le .mailmap suffit pour l’affichage).\n'
    exit 0
fi
printf '%s\n' "$AFFECTED" | while read -r sha; do
    git log -1 --no-use-mailmap --format='  %h  %an <%ae>  %s' "$sha" | cut -c1-96
done
printf '\n  soit %s commit(s).\n' "$(printf '%s\n' "$AFFECTED" | wc -l)"

if [[ "$APPLY" -eq 0 ]]; then
    cat <<'NEXT'

Aucune modification (mode rapport). Pour réécrire :

  bash tools/rewrite_authors.sh --apply     puis vérifier avec git log
  bash tools/rewrite_authors.sh --push      réécrit et force-pousse la branche

Attention, --apply change tous les SHA de la branche :
  * le run CI validé sur l’ancien SHA ne vaut plus pour le nouveau : il faut
    re-marquer un commit vide avec [PROD] et relancer la CI (~10 min) ;
  * les tags v0.9.0 / v0.9.1 et la release publiée restent sur leurs commits
    d’origine : c’est voulu, les artefacts 0.9.1 gardent leur provenance ;
  * tout clone existant devra être refait (git fetch puis git reset --hard).
NEXT
    exit 0
fi

printf '\nRéécriture de %s (les SHA vont changer)…\n' "$BRANCH"
BEFORE=$(git rev-parse "$BRANCH")
BACKUP="refs/backup/rewrite-authors-$(date -u +%Y%m%dT%H%M%SZ)"
git update-ref "$BACKUP" "$BEFORE" || exit 1
printf 'Sauvegarde locale de l’ancien sommet : %s -> %s\n' "$BACKUP" "${BEFORE:0:12}"

FILTER_BRANCH_SQUELCH_WARNING=1 \
git filter-branch -f --env-filter "$ENV_FILTER" -- "$BRANCH"
code=$?
if [[ "$code" -ne 0 ]]; then
    printf 'Échec de la réécriture (code %s) ; rien n’a été poussé.\n' "$code" >&2
    printf 'Restauration possible : git reset --hard %s\n' "$BACKUP" >&2
    exit "$code"
fi

AFTER=$(git rev-parse "$BRANCH")
printf '\nAncien sommet : %s\nNouveau       : %s\n\n' "${BEFORE:0:12}" "${AFTER:0:12}"
printf 'Auteurs réels restants (identités brutes, sans mailmap) :\n'
git log --no-use-mailmap --format='  %an <%ae>' "$BRANCH" | sort | uniq -c | sort -rn
printf '\nVue affichée, mailmap appliqué :\n'
git log --format='  %aN <%aE>' "$BRANCH" | sort | uniq -c | sort -rn
printf '\nLes tags n’ont pas bougé :\n'
git for-each-ref refs/tags --format='  %(refname:short) -> %(objectname:short)'

if [[ "$PUSH" -eq 0 ]]; then
    printf '\nRien n’a été poussé. Pour publier : git push --force-with-lease origin %s\n' "$BRANCH"
    exit 0
fi
printf '\nForce-push de %s…\n' "$BRANCH"
git push --force-with-lease origin "$BRANCH"
code=$?
if [[ "$code" -ne 0 ]]; then
    printf 'Push refusé (code %s) ; la branche locale est réécrite, le remote non.\n' "$code" >&2
    printf 'Restauration : git reset --hard %s\n' "$BACKUP" >&2
fi
exit "$code"
