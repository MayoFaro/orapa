# Moteur de propagation à passage unique pour les contraintes de rayon

## Contexte et cause racine

Le moteur CSP (`orapa_csp.py`/`relational_csp.py`/`ray_witness.py`) résout la
cohérence d'arc en interrogeant chaque contrainte via `has_support(variable,
value, domains) -> bool`, une fois par valeur candidate de chaque variable de
sa portée. Pour une contrainte de rayon (`_RaySupportOracle`), chaque
interrogation relance potentiellement une recherche de témoin complète
(`RayWitnessFinder.search_masks`), qui s'arrête dès qu'elle trouve **un**
témoin valide.

Mesuré sur un indice réel ("orange clair" = rouge+blanc+jaune, partie du
2026-09-15) : **827 recherches indépendantes**, **3 041 912 nœuds explorés
au total**, **60,7s**, pour un seul indice. Un indice mono-couleur (une
seule pièce candidate) ne coûte qu'1-2 recherches et 1-2s. Le coût actuel
est proportionnel à la somme des tailles de domaine des pièces impliquées,
pas à la taille réelle de l'espace de recherche partagé entre ces
recherches quasi redondantes.

## Objectif

Rendre le coût de propagation d'une contrainte de rayon proportionnel à la
taille de l'espace de recherche exploré une seule fois, plus jamais au
nombre de valeurs candidates interrogées — pour tous les indices, pas
seulement les couleurs mélangées.

## Approche retenue

Remplacer, uniquement pour la contrainte de rayon, le schéma "une recherche
par valeur" par "une recherche par contrainte" :

1. **`ray_witness.py`** — nouvelle méthode sur `RayWitnessFinder` qui, au
   lieu de retourner au premier témoin trouvé, continue d'explorer (en
   réutilisant la déduplication d'états déjà en place pour éviter les
   cycles) et accumule par OU binaire, pour chaque pièce, l'ensemble des
   valeurs prouvées atteignables par au moins un témoin. Arrêt anticipé dès
   que plus aucune valeur interrogée ne peut être gagnée. Si le budget
   (nœuds/échéance) est épuisé avant preuve complète, les valeurs encore
   incertaines restent conservées (jamais éliminées à tort) — même
   sémantique conservatrice qu'aujourd'hui.

2. **`relational_csp.py`** — le protocole `Constraint` gagne une méthode
   optionnelle de révision en bloc (ex. `bulk_revise(domains) ->
   Mapping[variable, tuple[value, ...]] | None`, `None` signifiant repli sur
   `has_support` valeur par valeur). `_propagate_domains` l'utilise quand
   elle existe, en révisant toutes les variables de la portée de la
   contrainte en un seul passage. Les contraintes spatiales et de case
   n'implémentent pas cette méthode et ne sont pas affectées.

3. **`orapa_csp.py`** — `_RaySupportOracle` implémente `bulk_revise` via la
   nouvelle capacité de `RayWitnessFinder`, en réutilisant le cache de
   témoins existant (conversion vers/depuis une forme indépendante du
   catalogue, déjà en place).

`solve_orapa_csp` et `propagate_orapa_csp` gardent leur signature actuelle.
Aucun changement dans `progressive.py`.

## Exigence de correction

Résultat identique à l'ancien chemin (valeur par valeur), validé par le même
oracle force-brute (`tests/bruteforce_oracle.py`) déjà utilisé par la suite
de tests existante. Ajout de tests de propriété comparant, sur des scénarios
aléatoires, le domaine obtenu par l'ancien chemin et par le nouveau — ils
doivent être strictement égaux.

## Parallélisme

Explicitement hors-scope pour cette itération : on corrige d'abord le
gaspillage algorithmique (travail redondant), le parallélisme des 20 cœurs
disponibles reste une option pour plus tard si le gain algorithmique seul ne
suffit pas.

## Alternatives écartées (gardées en réserve)

- **B** — passe de pré-calcul séparée hors de la boucle AC-3 générique :
  plus simple à isoler mais perd l'entrelacement de la propagation
  générique, duplique une responsabilité qui devrait rester dans le moteur.
- **C** — index géométrique compilé, abandon de la recherche par graphe :
  plafond de performance potentiellement supérieur mais réécriture complète
  d'un algorithme inédit, risque disproportionné par rapport au problème
  mesuré.

Ces deux pistes restent envisageables si l'approche retenue s'avère
insuffisante ou peu concluante à l'usage.

## Validation

- Suite de tests existante inchangée et verte (`test_orapa_csp_oracle.py`,
  `test_relational_csp.py`, `test_relational_csp_properties.py`,
  `test_relational_history_regression.py`, etc.)
- Nouveaux tests de propriété : ancien chemin vs nouveau chemin, domaines
  strictement identiques, sur de nombreux scénarios aléatoires.
- Cas de régression dédié : l'indice "orange clair" mesuré ci-dessus doit
  se résoudre en une fraction du temps actuel (ordre de grandeur : une
  poignée de recherches au lieu de 827).
