# Exigences : interface ChimeraFlow

Format EARS : « QUAND … LE SYSTÈME DOIT … ». Sources : exigences de `design.md` (même dossier, ancien `ui-spec.md`) et
`Roadmap.md` §7 (R8, R10, R11, R12). Le backend est décrit dans `../chimeraflow-backend/`.
Les numéros R de `design.md` (R1, R2, R3, R6, R7, R8, R10, R12) sont conservés entre parenthèses.

## Exigences

### 1. Tableau de bord (R1)

**Histoire** : en tant que gérant d'une petite entreprise, je veux voir l'état de mes sources et les dernières corrélations, afin de savoir ce qui demande mon attention.

1. QUAND le tableau de bord s'affiche, LE SYSTÈME DOIT montrer l'état des quatre sources, les statistiques et les dernières corrélations.
2. QUAND l'utilisateur active « Exécuter les règles », LE SYSTÈME DOIT lancer l'exécution et afficher les corrélations obtenues.

### 2. Règles (R2)

1. QUAND l'utilisateur ouvre la liste des règles, LE SYSTÈME DOIT afficher chaque règle avec son détail JSON.
2. QUAND l'utilisateur demande la suppression d'une règle, LE SYSTÈME DOIT demander une confirmation avant de la supprimer.
3. QUAND l'utilisateur écrit une règle en langage naturel, LE SYSTÈME DOIT afficher un aperçu du brouillon avant l'enregistrement.
4. SI la conversion en règle est indisponible ou son budget épuisé, ALORS LE SYSTÈME DOIT proposer les règles prédéfinies.

### 3. Corrélations (R3)

1. QUAND une corrélation est affichée, LE SYSTÈME DOIT montrer des badges par source, l'horodatage et la gravité.
2. QUAND une corrélation porte une `explanation`, LE SYSTÈME DOIT afficher la vue « pourquoi ça correspond ».
3. QUAND de nouvelles corrélations arrivent, LE SYSTÈME DOIT les afficher en temps réel par le flux SSE, sinon actualiser toutes les 15 secondes.

### 4. Provenance (R10)

1. QUAND l'utilisateur ouvre le tiroir de provenance d'une corrélation, LE SYSTÈME DOIT montrer pour chaque enregistrement contributeur la source, la référence dans la source et l'identifiant.

### 5. Accessibilité (R6, Roadmap R11)

1. LE SYSTÈME DOIT atteindre le contraste WCAG AA (4,5:1 pour le texte normal, 3:1 pour le grand texte).
2. QUAND l'utilisateur navigue au clavier, LE SYSTÈME DOIT rendre chaque élément interactif atteignable, avec un focus visible et des rôles ARIA corrects.

### 6. Adaptation à l'écran (R7)

1. LE SYSTÈME DOIT rester utilisable à partir de 360 px de large, sans défilement horizontal, avec des mises en page à 768 px et à 1024 px et plus.

### 7. État dégradé (R8)

1. SI une source est absente, ALORS LE SYSTÈME DOIT le signaler par un bandeau et laisser les autres règles s'exécuter.

### 8. Texte de source non fiable (R12)

1. QUAND un texte venu d'un fichier ou d'une conversation est affiché (message de corrélation, gabarit de règle, valeurs d'explication), LE SYSTÈME DOIT le rendre comme texte React, sans `dangerouslySetInnerHTML` ni HTML interprété.

### 9. Langue et thème

1. QUAND l'utilisateur choisit le français ou l'anglais, LE SYSTÈME DOIT mémoriser ce choix, le français étant la langue par défaut.
2. QUAND l'utilisateur choisit le thème clair ou sombre, LE SYSTÈME DOIT mémoriser ce choix, le thème du système étant le défaut.
3. LE SYSTÈME DOIT lire tout texte visible dans les fichiers de traduction, jamais dans le code.

### 10. Bac à sable de normalisation

1. QUAND l'utilisateur saisit un nom dans `/sandbox`, LE SYSTÈME DOIT afficher sa forme normalisée et son score de correspondance avec d'autres noms.
