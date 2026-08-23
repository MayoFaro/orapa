# Orapa Mine Assistant

## 1. Objectif

Développer une petite application desktop, locale et hors ligne, destinée à assister son utilisateur dans l’apprentissage et l’analyse d’**Orapa Mine** pendant une partie en ligne.

Le logiciel est un outil personnel, sans objectif de diffusion publique ou commerciale. Il doit aider à comprendre les déductions possibles et à améliorer la manière de jouer.

L’application ne doit pas jouer automatiquement à la place du joueur. Elle doit agir comme un **outil d’analyse en temps réel** capable de :

* enregistrer les résultats des ondes soniques déjà jouées ;
* éliminer les configurations de gemmes incompatibles avec ces résultats ;
* afficher les configurations encore possibles ;
* visualiser les positions et orientations probables des gemmes ;
* recommander la meilleure prochaine onde à envoyer ;
* permettre au joueur de saisir rapidement les informations obtenues pendant la partie ;
* détecter lorsqu’une seule configuration reste possible ;
* permettre d’annuler/corriger une saisie erronée.

L’objectif principal est de réduire le temps de raisonnement manuel tout en restant fidèle aux règles officielles du jeu.

---

# 2. Technologie retenue

## Langage

**Python 3.10+**

Python est adapté pour :

* la génération combinatoire des placements ;
* la simulation géométrique des rayons ;
* le filtrage d’un grand nombre de configurations ;
* le calcul probabiliste et informationnel ;
* le prototypage rapide ;
* les tests unitaires ;
* la construction d’une interface desktop simple.

Le choix desktop est volontaire : il privilégie la rapidité de développement et de validation du solveur, l’accès aux ressources locales, le calcul multiprocessus et la gestion de caches volumineux. La logique métier restera indépendante de l’interface afin de permettre un éventuel portage web ultérieur.

## Interface graphique

**PySide6 / Qt**

PySide6 est préférable à Tkinter car l’application devra probablement afficher :

* une grille 10×8 ;
* des objets graphiques orientés ;
* les parcours des rayons ;
* des superpositions de probabilités ;
* des zones cliquables autour de la grille ;
* des tableaux de résultats ;
* différents modes de visualisation.

L’interface du MVP restera volontairement sobre. Une grille textuelle ou colorée, un formulaire de saisie, un historique et un classement des coups suffisent. Les polygones exacts resteront néanmoins conservés dans le moteur.

---

# 3. Architecture générale proposée

```text
orapa_assistant/
│
├── main.py
│
├── geometry.py
├── pieces.py
├── raytracer.py
├── colors.py
├── placements.py
├── solver.py
├── strategy.py
├── state.py
├── gui/
│   ├── main_window.py
│   ├── board_widget.py
│   ├── observation_panel.py
│   ├── strategy_panel.py
│   └── history_panel.py
│
├── tests/
│   ├── test_geometry.py
│   ├── test_raytracer.py
│   ├── test_colors.py
│   ├── test_placements.py
│   ├── test_solver.py
│   └── test_strategy.py
│
└── data/
    └── optional_precomputed_tables/
```

La logique métier doit être totalement séparée de l’interface graphique.

Le moteur doit pouvoir fonctionner sans GUI, afin d’être facilement testable.

---

# 4. Modèle du plateau

Le plateau visible du prospecteur est une grille de :

* **10 colonnes**
* **8 lignes**

Les entrées/sorties des ondes sont placées autour du plateau.

Convention :

```text
Haut :
1 2 3 4 5 6 7 8 9 10

Gauche :
A B C D E F G H

Bas :
I J K L M N O P Q R

Droite :
11 12 13 14 15 16 17 18
```

Chaque point du bord peut servir :

* d’entrée d’une onde ;
* de sortie d’une onde.

Il existe donc **36 points de bord**.

---

# 5. Pièces du jeu de base

Le solveur doit initialement gérer les cinq gemmes du jeu de base :

* 1 gemme rouge ;
* 1 gemme jaune ;
* 1 gemme bleue ;
* 2 gemmes blanches.

Les formes exactes, dimensions et orientations doivent être modélisées conformément aux règles officielles.

Il faut éviter de réduire les pièces à de simples cases occupées.

Le moteur doit représenter la géométrie réelle de leurs surfaces réfléchissantes.

Chaque pièce devra posséder au minimum :

```python
class Piece:
    color
    shape
    position
    orientation
    reflective_segments
    occupied_area
```

---

# 6. Règles de placement

Le générateur de configurations doit respecter toutes les contraintes du jeu.

Notamment :

1. chaque coin de gemme doit correspondre à un coin de la grille ;
2. les lignes des gemmes doivent rester alignées avec la grille ;
3. aucune gemme ne peut dépasser du plateau ;
4. deux gemmes ne peuvent pas être placées côte à côte selon les restrictions prévues par la règle ;
5. les contacts autorisés entre gemmes doivent respecter la règle officielle ;
6. aucune gemme ne doit être entièrement masquée derrière une autre lorsqu’on observe depuis un bord du plateau.

Ces règles doivent être implémentées explicitement et testées.

Les schémas officiels confirment que deux gemmes peuvent se toucher par un sommet ou partager une ligne de bord. Seul le chevauchement de leurs surfaces intérieures est interdit. Le moteur distingue donc explicitement `disjoint`, `touch_point`, `touch_edge` et `overlap`.

---

# 7. Simulation des ondes

La fonction centrale du logiciel sera :

```python
simulate_ray(configuration, entry_point)
```

Elle devra retourner :

```python
RayResult(
    exit_point,
    resulting_color,
    interactions
)
```

Exemple :

```python
RayResult(
    exit_point="12",
    resulting_color="red",
    interactions=[
        ...
    ]
)
```

---

# 8. Propagation géométrique

Une onde :

1. entre depuis un point du bord ;
2. se déplace horizontalement ou verticalement ;
3. continue en ligne droite jusqu’à rencontrer une surface de gemme ;
4. est réfléchie suivant l’inclinaison de cette surface ;
5. poursuit son parcours ;
6. peut rencontrer plusieurs gemmes ;
7. peut rencontrer plusieurs fois la même gemme ;
8. finit par ressortir par l’un des 36 points du bord.

La simulation doit fonctionner de manière déterministe.

Il faut éviter toute approximation graphique ou flottante susceptible de produire des erreurs.

Une représentation géométrique discrète ou rationnelle est préférable si possible.

La représentation retenue utilise des **coordonnées entières doublées** :

```text
grille logique : x = 0..10, y = 0..8
grille interne : x = 0..20, y = 0..16
```

Les sommets des gemmes ont ainsi des coordonnées paires et les axes initiaux des rayons passent par des coordonnées impaires. Les collisions peuvent être calculées exactement, sans nombres flottants. Le moteur doit également détecter la répétition d’un état `(position, direction)` afin de ne jamais boucler indéfiniment.

---

# 9. Gestion des couleurs

Le rayon est initialement transparent.

Lorsqu’il rencontre des gemmes, il prend une couleur correspondant à l’ensemble des couleurs rencontrées.

Une même couleur ne doit être comptée qu’une fois, même si le rayon rencontre plusieurs fois cette couleur.

Exemples :

```text
blanc              -> blanc
rouge               -> rouge
jaune               -> jaune
bleu                -> bleu

rouge + blanc       -> rose
jaune + blanc       -> jaune citron
bleu + blanc        -> bleu ciel

rouge + bleu        -> violet
rouge + jaune       -> orange
bleu + jaune        -> vert

rouge + jaune + bleu + blanc -> gris
```

La table complète des 16 sous-ensembles doit être définie et testée, notamment :

```text
aucune couleur               -> transparent
rouge + jaune + bleu         -> noir
rouge + jaune + blanc        -> orange clair
rouge + bleu + blanc         -> violet clair
jaune + bleu + blanc         -> vert clair
```

Toutes les combinaisons définies par les règles devront être implémentées.

Une représentation interne sous forme d’ensemble est recommandée :

```python
encountered_colors = {"red", "white"}
```

Puis :

```python
result_color = mix_colors(encountered_colors)
```

---

# 10. Observation saisie par le joueur

Chaque résultat connu doit être stocké sous forme structurée.

Exemple :

```python
Observation(
    entry="8",
    exit="12",
    color="red"
)
```

Autre exemple :

```python
Observation(
    entry="N",
    exit="N",
    color="violet"
)
```

La GUI doit permettre une saisie extrêmement rapide.

Le joueur doit pouvoir sélectionner :

* entrée ;
* sortie ;
* couleur.

Puis cliquer sur :

```text
AJOUTER
```

---

# 11. Historique

L’application doit conserver durablement l’historique complet des observations.
Chaque modification est sauvegardée automatiquement dans un journal local. La
partie en cours est restaurée au lancement suivant avec ses variantes. Le bouton
« Nouvelle partie » et un changement de variante ouvrent une nouvelle session :
la précédente reste archivée et n’est jamais écrasée.

Le journal conserve également les anciens instantanés. La suppression d’un
indice l’enlève donc des contraintes actives sans effacer la trace de sa saisie.

Exemple :

```text
B  -> 3   blanc
2  -> 2   blanc
C  -> C   blanc
E  -> E   jaune
8  -> 12  rouge
15 -> 15  gris
```

Chaque entrée doit pouvoir être :

* supprimée ;
* corrigée ;
* éventuellement désactivée temporairement.

Une modification de l’historique doit entraîner automatiquement un nouveau calcul des solutions possibles.

---

# 12. Solveur

Le solveur conserve l’ensemble :

```python
possible_configurations
```

À chaque nouvelle observation :

```python
possible_configurations = [
    config
    for config in possible_configurations
    if simulate_ray(config, observation.entry)
       == observation.expected_result
]
```

Le logiciel doit afficher en permanence :

```text
Solutions restantes : N
```

Avant que l'énumération complète soit faisable, le moteur maintient des domaines de placements par pièce. Il applique des contraintes relationnelles exactes dérivées des couleurs : une sortie blanche ne dépend que des deux pièces blanches, violet de rouge et bleu, jaune citron de jaune et des deux blanches, etc. Un placement est supprimé lorsqu'il ne possède aucun support dans la relation correspondante. La recherche exhaustive démarre automatiquement lorsque le produit des domaines passe sous un seuil configurable.

---

# 13. Approche candidate : précalcul à valider

Une optimisation possible consiste à générer toutes les configurations légales une seule fois. Sa faisabilité doit être mesurée avant d’en faire l’architecture définitive. Le générateur doit appliquer les incompatibilités au plus tôt par backtracking, au lieu de construire le produit cartésien complet des placements.

Le comptage corrigé des placements individuels donne 63 placements pour le petit losange blanc, 188 pour le triangle bleu, 248 pour le parallélogramme rouge (rotations des deux chiralités), 252 pour le triangle jaune et 188 pour le grand triangle blanc, soit environ **139,2 milliards de combinaisons brutes**. Un catalogue naïf de toutes les grilles est donc exclu. Le solveur devra utiliser un backtracking fortement contraint, une génération progressive guidée par les observations et, si nécessaire au début d’une partie, un échantillonnage uniforme clairement signalé comme approximatif.

Pour chaque configuration, calculer les résultats des 36 entrées possibles.

Conceptuellement :

```python
ray_table[configuration_id][entry] = RayResult(...)
```

Pendant une partie, le solveur n’a alors presque plus besoin de refaire la géométrie.

Il compare simplement les observations reçues avec les résultats précalculés.

Cela permettrait une réponse quasi instantanée.

---

# 14. Représentation compacte

Si le nombre de configurations légales devient important, utiliser des identifiants numériques.

Exemple :

```text
configuration 0
configuration 1
configuration 2
...
```

Pour chaque observation possible, on peut également conserver directement la liste ou le bitset des configurations compatibles.

Par exemple :

```python
compatible["8"]["12"]["red"]
```

pourrait représenter l’ensemble des configurations produisant :

```text
8 -> 12 rouge
```

Le filtrage devient alors une simple intersection d’ensembles.

---

# 15. Bitsets

Une optimisation possible :

```python
current_candidates &= compatible_candidates
```

où chaque ensemble de configurations est représenté par un bitset.

Cela pourrait rendre les filtrages extrêmement rapides.

À envisager seulement après avoir obtenu une version correcte et testée.

---

# 16. Recommandation de la prochaine onde

L’application ne doit pas seulement afficher les solutions restantes.

Elle doit analyser les **36 entrées possibles** et déterminer laquelle apporte le plus d’information.

Pour chaque onde candidate :

1. simuler cette onde sur toutes les configurations restantes ;
2. regrouper les configurations par résultat possible ;
3. mesurer la qualité de la partition obtenue.

Exemple :

```text
Entrée D

D -> D bleu       : 12 solutions
D -> 8 blanc      : 10
D -> N violet     : 9
D -> 15 rouge     : 7
...
```

---

# 17. Critères stratégiques

Plusieurs méthodes doivent pouvoir être comparées.

## Entropie de Shannon

Pour une onde donnée :

```text
H = - Σ p_i log2(p_i)
```

Une entropie élevée signifie que l’onde sépare efficacement les solutions.

Le logiciel peut afficher :

```text
Meilleur coup : N
Entropie : 4.72 bits
```

---

## Minimax

Une autre approche consiste à minimiser le pire cas.

Pour chaque onde :

```text
worst_case = taille du groupe de réponses le plus important
```

Choisir l’onde ayant le plus petit `worst_case`.

Cette approche garantit la meilleure réduction possible dans le scénario le moins favorable.

---

## Nombre moyen de solutions restantes

Calcul :

```text
E[N_remaining]
```

Cela peut également servir de critère.

---

# 18. Classement des coups

Afficher plusieurs recommandations :

```text
Solutions actuelles : 84

Entrée     Entropie     Pire cas
N          5.21 bits       11
13         5.07 bits       13
D          4.91 bits       15
6          4.73 bits       18
K          4.45 bits       21
```

Le meilleur coup doit apparaître clairement.

---

# 19. Prise en compte des ondes déjà utilisées

Il faut décider si le jeu en ligne autorise ou non de rejouer une même onde.

Le logiciel doit être conçu pour pouvoir :

* exclure automatiquement les entrées déjà utilisées ;
* ou permettre leur réutilisation selon la règle adoptée.

Faire de cette politique une option configurable.

---

# 20. Carte de fréquences

Lorsque plusieurs configurations restent possibles, calculer pour chaque zone du plateau sa fréquence d’appartenance à une gemme parmi les candidats restants.

Ces valeurs ne doivent être appelées « probabilités » que si la distribution aléatoire utilisée pour produire les grilles est connue. Par défaut, elles reposent sur l’hypothèse uniforme que chaque configuration candidate a le même poids.

Exemple :

```text
        1    2    3    4    5    6    7    8    9   10

A       0    0    4   12   78   64    8    0    0    0
B       0    0   91   88   96   72    1  100    2    0
C       ...
```

Valeurs exprimées en pourcentage.

Il serait encore plus intéressant de produire une carte différente pour chaque couleur :

```text
P(rouge)
P(jaune)
P(bleu)
P(blanc)
```

---

# 21. Probabilité des orientations

Sous la même hypothèse uniforme, le programme doit idéalement être capable d’afficher :

```text
Triangle bleu :
orientation Est : 87 %
orientation Ouest : 8 %
orientation Nord : 5 %
orientation Sud : 0 %
```

Cela permet au joueur de visualiser les hypothèses dominantes.

---

# 22. Affichage graphique

La fenêtre principale pourrait être structurée ainsi :

```text
┌────────────────────────────────────────────────────────────┐
│                    ORAPA ASSISTANT                         │
├───────────────────────────────┬────────────────────────────┤
│                               │ Solutions restantes : 37  │
│                               │                            │
│                               │ Meilleure onde : N        │
│                               │ Entropie : 4.72 bits      │
│         GRILLE 10 × 8         │                            │
│                               │ 1. N        4.72          │
│                               │ 2. 6        4.52          │
│                               │ 3. D        4.31          │
│                               │ 4. 13       4.18          │
│                               │                            │
├───────────────────────────────┴────────────────────────────┤
│ Nouvelle observation                                      │
│                                                           │
│ Entrée [ 8 ▼]  Sortie [12 ▼]  Couleur [rouge ▼]          │
│                                                           │
│                    [ AJOUTER ]                            │
├────────────────────────────────────────────────────────────┤
│ Historique                                                │
│                                                           │
│ B  -> 3   blanc                                           │
│ 2  -> 2   blanc                                           │
│ C  -> C   blanc                                           │
│ 8  -> 12  rouge                                           │
│                                                           │
└────────────────────────────────────────────────────────────┘
```

---

# 23. Modes d’affichage proposés

## Mode 1 — Probabilités

Afficher les zones où les gemmes sont probablement présentes.

## Mode 2 — Solution candidate

Afficher une configuration candidate et permettre de parcourir les autres. Tant que le générateur aléatoire du jeu n’est pas connu, aucune configuration ne doit être présentée comme intrinsèquement plus probable qu’une autre.

## Mode 3 — Toutes les solutions

Permettre de parcourir :

```text
Solution 1 / 37
Solution 2 / 37
...
```

## Mode 4 — Consensus

Afficher uniquement les éléments présents dans 100 % des configurations restantes.

Par exemple :

```text
Rouge : position certaine
Bleu : orientation encore incertaine
```

Ce mode serait particulièrement utile en partie.

---

# 24. Détection de solution

Si :

```python
len(possible_configurations) == 1
```

l’interface doit clairement afficher :

```text
SOLUTION UNIQUE
```

et représenter toutes les gemmes.

Si plusieurs configurations subsistent mais qu’elles sont géométriquement équivalentes pour la proposition finale, le programme doit également être capable de le détecter.

---

# 25. Gestion des contradictions

Si une observation conduit à :

```text
0 configuration possible
```

ne pas simplement afficher une erreur générique.

Afficher :

```text
Aucune configuration compatible.

L'une des observations saisies est probablement incorrecte.
```

Idéalement, tenter d’identifier les observations suspectes.

Exemple :

```text
La suppression de l'observation :

9 -> 16 jaune

rétablirait 42 configurations possibles.
```

Cela serait très utile en jeu réel en cas d’erreur de saisie.

---

# 26. Vérification par les règles officielles

Avant d’implémenter le solveur complet, construire des tests unitaires à partir des exemples présents dans les règles officielles.

Les tests doivent vérifier :

* les réflexions élémentaires ;
* toutes les orientations des gemmes ;
* les parcours avec plusieurs réflexions ;
* les mélanges de couleurs ;
* les rayons revenant à leur point d’entrée ;
* les rayons traversant la grille sans rencontrer de gemme.

Le moteur géométrique doit être considéré comme critique.

Aucun travail d’optimisation ne doit être effectué avant que ces tests soient fiables.

---

# 27. Test d’intégration avec une partie réelle

Utiliser notamment la séquence suivante comme scénario de validation :

```text
B  -> 3   blanc
2  -> 2   blanc
C  -> C   blanc
E  -> E   jaune
8  -> 12  rouge
15 -> 15  gris
M  -> M   jaune citron
H  -> 18  transparent
13 -> 13  rouge
9  -> 16  jaune
K  -> G   blanc
N  -> N   violet
6  -> 6   violet
7  -> O   transparent
D  -> D   bleu
```

Le programme doit progressivement éliminer les configurations incompatibles.

La grille connue doit reproduire exactement les quinze résultats. Un second test mesurera combien de configurations légales subsistent après les quinze observations ; l’unicité ne doit pas être supposée avant cette mesure.

Ce scénario constituera un excellent test d’intégration du système complet.

Premier résultat mesuré : les contraintes transparentes et monochromes ramènent l’historique réel à 108 192 combinaisons brutes. Parmi elles, 26 441 grilles ne présentent aucun chevauchement et une seule satisfait les quinze observations. La recherche Python de référence prend environ 8 secondes avant optimisation et retrouve exactement la grille de la capture.

---

# 28. Phase 1 recommandée

Ne pas commencer par l’interface graphique.

Construire d’abord :

```text
geometry
↓
pieces
↓
raytracer
↓
colors
↓
placements
↓
solver
```

Puis tester entièrement ce noyau en ligne de commande.

Objectif :

```python
config = ...
result = simulate_ray(config, "8")

assert result.exit == "12"
assert result.color == "red"
```

---

# 29. Phase 2

Créer le générateur de toutes les configurations légales.

Mesurer :

```text
nombre total de configurations
temps de génération
mémoire utilisée
```

Puis enregistrer éventuellement le résultat dans un fichier cache.

---

# 30. Phase 3

Construire le solveur :

```python
solver.add_observation("8", "12", "red")
```

Puis :

```python
solver.candidate_count()
solver.candidates()
```

---

# 31. Phase 4

Ajouter le moteur stratégique :

```python
solver.rank_next_moves()

## Correctif — observation directe d’une case

L’assistant accepte désormais deux types d’actions dans un même historique :

- une onde, décrite par son entrée et son résultat ;
- l’examen d’une case `A1` à `H10`, dont le résultat est `rien`, une couleur de
  pierre, `diamant` ou `corps noir` lorsque la variante correspondante est active.

L’examen d’une case révèle uniquement la nature de la pierre qui occupe
l’intérieur de cette case. Il ne révèle ni la forme exacte lorsqu’il s’agit
d’une pierre blanche, ni son orientation. Le solveur compare les 36 ondes et
les 80 examens de case encore inutilisés pour proposer l’action qui minimise
d’abord le nombre de solutions dans le pire cas, puis le nombre moyen attendu.

Conformément à la règle officielle, deux pierres peuvent se toucher par un
coin ou partager une ligne de grille entre deux cases. Elles ne peuvent en
revanche pas occuper simultanément les deux moitiés d’une même case : une
diagonale partagée à l’intérieur de cette case rendrait la réponse à un examen
direct ambiguë. Le chevauchement des surfaces intérieures reste interdit.
```

Retour attendu :

```python
[
    MoveScore(entry="N", entropy=5.21, worst_case=11),
    MoveScore(entry="13", entropy=5.07, worst_case=13),
    ...
]
```

---

# 32. Phase 5

Créer l’interface PySide6.

L’interface ne doit communiquer avec le moteur qu’au travers d’une API propre.

Exemple :

```python
solver.add_observation(...)
solver.undo()
solver.get_heatmap()
solver.rank_next_moves()
solver.get_candidates()
```

Les réductions de domaines, la recherche exhaustive et le classement stratégique doivent être exécutés dans un thread de travail Qt. Le thread graphique se limite à la saisie et à l'affichage ; les contrôles sont temporairement désactivés pendant un calcul, mais la fenêtre reste réactive.

---

# 33. Tests indispensables

Utiliser `pytest`.

Tests minimum :

```text
test_piece_geometry
test_each_reflection_orientation
test_ray_without_collision
test_ray_single_collision
test_ray_multiple_collisions
test_ray_return_to_origin
test_color_combinations
test_duplicate_color_not_counted_twice
test_legal_placement
test_illegal_overlap
test_solver_filter
test_solver_zero_candidate_detection
test_entropy_ranking
test_real_game_sequence
```

---

# 34. Priorité absolue

L’ordre de priorité doit être :

```text
1. exactitude géométrique
2. exactitude du solveur
3. tests
4. performances
5. interface graphique
6. esthétique
```

Une interface élégante avec un raytracer approximatif serait inutile.

---

# 35. Extension diamant

Le moteur devrait être conçu de façon suffisamment générique pour intégrer ultérieurement le diamant transparent.

Le diamant :

* réfléchit le rayon ;
* ne modifie pas sa couleur.

Il ne faut donc pas coder la couleur comme une propriété obligatoire de toute interaction.

La pièce est un demi-losange : triangle de dimensions 1×2 cases, ou 2×1 après rotation, avec quatre orientations et 284 placements individuels. Elle est représentée par `D` et les suffixes de demi-case. Le mode diamant invalide le raccourci « transparent = trajet droit » : un rayon transparent peut avoir été dévié par le diamant.

---

# 36. Extension corps noir

Prévoir éventuellement le corps noir.

Il absorbe l’onde.

Le résultat peut alors devenir :

```python
RayResult(
    absorbed=True
)
```

au lieu d’une sortie normale.

La pièce est un rectangle plein de 2×1 cases, orientable horizontalement ou verticalement, soit 142 placements individuels. Elle est représentée par `N`. L’interface propose « L’onde a été absorbée » comme résultat terminal sans sortie ni couleur.

Les variantes diamant et corps noir peuvent être activées séparément ou simultanément par deux cases à cocher. Un changement de variante réinitialise l’historique, puisque le catalogue de pièces et la signification des résultats transparents changent.

---

# 37. Extension future : analyse d’une proposition

Le programme pourrait ultérieurement indiquer :

```text
Configuration suffisamment déterminée pour proposer : OUI/NON
```

Il pourrait notamment distinguer :

```text
1 configuration restante
```

de :

```text
plusieurs configurations internes,
mais toutes correspondent à la même disposition finale
```

---

# 38. Extension future : import de partie

Permettre de coller directement un historique texte :

```text
Valclaterre envoie une onde de 8
L'onde sort de 12 en rouge
...
```

Le programme pourrait parser automatiquement cet historique et remplir les observations.

---

# 39. Extension future : reconnaissance depuis l’écran

À beaucoup plus long terme, envisager éventuellement :

* capture de la fenêtre BGA ;
* reconnaissance automatique du journal de partie ;
* ajout automatique des résultats dans le solveur.

Cette fonctionnalité ne doit cependant pas faire partie du MVP.

Le MVP doit rester un assistant à saisie manuelle.

---

# 40. MVP attendu

Le premier produit réellement utilisable doit permettre :

1. lancement de l’application ;
2. affichage de la grille ;
3. saisie d’une observation ;
4. suppression/correction d’une observation ;
5. calcul du nombre de configurations compatibles ;
6. affichage des positions probables ;
7. classement des meilleures prochaines ondes ;
8. affichage d’une solution unique lorsqu’elle est déterminée ;
9. sauvegarde automatique de chaque indice, restauration de la partie en cours
   et archivage des parties précédentes.

---

# 41. Question d’architecture importante à résoudre avant codage

Avant de commencer l’implémentation complète, analyser précisément :

1. la géométrie exacte de chacune des pièces ;
2. toutes leurs orientations légales ;
3. les règles exactes de collision/réflexion ;
4. la définition mathématique des contacts entre pièces ;
5. le nombre théorique de placements possibles ;
6. la faisabilité d’un précalcul exhaustif.

L’agent de codage doit produire cette analyse avant de choisir définitivement la représentation interne.

---

# 42. Approche de développement souhaitée

Procéder par incréments très petits.

Pour chaque étape :

```text
spécification
→ implémentation
→ tests
→ validation
→ étape suivante
```

Éviter de développer simultanément la GUI, le solveur et la géométrie.

Le noyau doit être fiable avant toute intégration graphique.

---

# 43. Résultat final recherché

L’application doit finalement pouvoir fonctionner ainsi :

```text
Nouvelle partie
↓
aucune information connue
↓
le programme propose l'onde ayant la meilleure valeur informationnelle
↓
le joueur joue cette onde sur BGA
↓
il saisit le résultat
↓
le solveur élimine les configurations impossibles
↓
le programme recalcule immédiatement la meilleure prochaine onde
↓
...
↓
une configuration unique reste
↓
le joueur peut proposer la solution
```

Le logiciel doit donc être conçu comme un **solveur de contraintes géométriques interactif avec optimisation informationnelle des coups**.

La priorité n’est pas seulement de trouver la solution, mais de la trouver avec le **plus petit nombre possible d’ondes**, puisque l’adversaire dispose des mêmes informations et cherche lui aussi à résoudre la grille avant nous.

---

# 44. Nouveau cœur relationnel

Le produit indépendant des nombres de placements n'est plus utilisé comme
ensemble de solutions. Le moteur distingue désormais :

* les domaines de placements, qui donnent seulement une borne cartésienne ;
* les relations entre placements imposées par chaque observation ;
* les modèles globaux, qui placent toutes les pièces et reproduisent réellement
  toutes les observations.

Chaque onde est représentée par une contrainte globale sur toutes les pièces.
Un générateur paresseux construit des témoins de trajet sous forme de masques de
placements. Ces témoins tiennent compte des surfaces rencontrées, des pièces
qui doivent rester après le prochain impact, des couleurs, du diamant, du corps
noir, des impacts simultanés et des absorptions.

La recherche d'un support possède trois résultats distincts :

```text
FOUND       un témoin exact existe
IMPOSSIBLE  l'absence de support a été prouvée
UNKNOWN     le budget de calcul a été atteint
```

`UNKNOWN` ne permet jamais d'éliminer un placement ni d'annoncer une
certitude. Les contraintes géométriques et les témoins de rayon sont propagés
jusqu'à stabilité par un CSP à domaines finis. Les modèles retournés sont
ensuite vérifiés une dernière fois avec le simulateur complet.

Les certitudes exactes sont obtenues par absence de contre-exemple. Une
configuration est déclarée unique seulement lorsque la recherche complète ne
trouve aucun second modèle. Lorsque la recherche est bornée, les actions sont
classées sur des modèles globaux vérifiés et l'interface qualifie explicitement
la recommandation d'« estimée ».

La validation du moteur repose d'abord sur des oracles exhaustifs de petits
domaines et des problèmes générés déterministes. Les historiques de parties
réelles servent uniquement de tests de régression et de benchmarks.
