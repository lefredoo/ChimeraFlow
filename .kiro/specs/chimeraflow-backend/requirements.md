# Exigences : backend ChimeraFlow

Format EARS : « QUAND … LE SYSTÈME DOIT … ». Sources : `connectors-spec.md`, `rule-engine-spec.md`, `api-spec.md`
(même dossier) et `Roadmap.md` §7 (R1 à R13). Les exigences de l'interface sont dans `../chimeraflow-ui/requirements.md`.
Conception : `design.md`. Avancement : `tasks.md`.

## Glossaire

- **Source** : fichier Excel, base Access, export WhatsApp ou CSV Mobile Money, en lecture seule.
- **Enregistrement unifié** : objet `id`, `source`, `source_ref`, `timestamp`, `lang`, `entities`, `payload` (AGENTS.md §19).
- **Règle** : document JSON déclaratif (AGENTS.md §20), jamais du code.
- **Corrélation** : résultat d'une règle, avec la provenance de chaque enregistrement qui y contribue.

## Exigences

### 1. Contrat MCP des connecteurs

**Histoire** : en tant que développeur, je veux interroger chaque source par le même contrat, afin de les corréler sans connaître leur format.

1. QUAND un client MCP appelle `fetch_records(limit)` sur un serveur, LE SYSTÈME DOIT renvoyer au plus `limit` enregistrements unifiés de sa source (défaut 100, maximum 1000).
2. QUAND un client MCP appelle `health_check()`, LE SYSTÈME DOIT renvoyer l'état de la source sans lever d'exception, y compris quand la source est illisible.
3. QUAND une lecture dépasse 5 secondes, LE SYSTÈME DOIT l'interrompre et signaler l'erreur dans la réponse.
4. LE SYSTÈME DOIT n'exposer que des outils en lecture seule.

### 2. Enregistrement unifié et normalisation

1. QUAND une source renvoie des enregistrements, LE SYSTÈME DOIT les convertir au schéma unifié (`source`, `source_ref`, `timestamp`, `lang`, `entities`, `payload`).
2. QUAND une entité est extraite, LE SYSTÈME DOIT calculer sa forme normalisée (minuscules, accents retirés, espaces réduits, ponctuation retirée sauf le trait d'union, synonymes FR/EN).
3. QUAND la normalisation est appliquée à une valeur déjà normalisée, LE SYSTÈME DOIT renvoyer la même valeur (idempotence).

### 3. Robustesse du parsing

1. SI une ligne ou une cellule ne peut pas être lue, ALORS LE SYSTÈME DOIT l'ignorer, l'ajouter au compteur d'erreurs et poursuivre.
2. SI une source est injoignable, ALORS LE SYSTÈME DOIT le signaler dans `health_check()` sans arrêter le processus.
3. LE SYSTÈME DOIT journaliser pour chaque opération le connecteur, l'opération, le nombre d'enregistrements, le nombre d'erreurs et la durée, sans donnée personnelle.

### 4. Connecteur Excel

1. QUAND une feuille contient des cellules fusionnées ou une mise en forme irrégulière, LE SYSTÈME DOIT extraire `Produit`, `Prix_Unitaire`, `Fournisseur` et `Date_MAJ` des lignes lisibles.

### 5. Connecteur Access

1. QUAND la base `.mdb` est lue, LE SYSTÈME DOIT extraire les tables `Articles` et `Mouvements` (`id`, `designation`, `unite`, `qty_stock`) avec le lecteur choisi par `ACCESS_READER`.
2. SI `ACCESS_READER` est absent ou inconnu, ALORS LE SYSTÈME DOIT s'arrêter au démarrage, sans valeur de repli.

### 6. Connecteur WhatsApp

1. QUAND un export est lu, LE SYSTÈME DOIT accepter les formats Android et iOS, les dates françaises et anglaises, l'horloge 12 h et les messages sur plusieurs lignes.
2. QUAND un message est une pièce jointe, LE SYSTÈME DOIT garder l'enregistrement avec `payload.attachment = true`.
3. QUAND une ligne est un message système, LE SYSTÈME DOIT l'ignorer et la compter à part des erreurs.
4. QUAND l'ordre jour/mois est ambigu, LE SYSTÈME DOIT le déduire du fichier entier, sinon appliquer le défaut du connecteur et l'indiquer.
5. QUAND les messages d'un export sont relus après avoir été ré-exportés, LE SYSTÈME DOIT retrouver les mêmes messages (aller-retour).

### 7. Connecteur Mobile Money

1. QUAND le CSV est lu, LE SYSTÈME DOIT extraire `transaction_id`, `phone`, `amount`, `status` et `timestamp`.
2. LE SYSTÈME DOIT ne jamais exposer `phone` ni `customer_name` dans un gabarit de règle ou une corrélation.

### 8. Schéma de règle

1. QUAND une règle est soumise, LE SYSTÈME DOIT la valider contre le schéma JSON : opérateurs `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `contains`, `in`, au plus 10 conditions par liste, `value` d'au plus 200 caractères ou 50 scalaires, `template` d'au plus 500 caractères, `on.field` obligatoire.
2. SI une règle nomme une colonne absente de sa source, ALORS LE SYSTÈME DOIT la refuser.
3. QUAND une condition porte `ref` avec `tolerance_pct` (0 à 1000), LE SYSTÈME DOIT comparer l'écart relatif `|champ − ref| / |ref|` en pourcentage et considérer la condition fausse si la référence est nulle.
4. LE SYSTÈME DOIT ne jamais exécuter de code généré : les règles sont des données.

### 9. Conversion langage naturel vers règle

1. QUAND l'utilisateur soumet une règle en français ou en anglais, LE SYSTÈME DOIT renvoyer une règle conforme au schéma ou une erreur de validation.
2. SI la réponse du modèle est invalide, ALORS LE SYSTÈME DOIT réessayer deux fois, puis refuser.
3. SI le fournisseur du modèle répond par une erreur transitoire (5xx, connexion, délai), ALORS LE SYSTÈME DOIT réessayer au plus deux fois avec attente croissante, dans une limite de 45 secondes au total, et ne jamais réessayer une erreur 4xx.
4. QUAND le budget global du modèle est épuisé, LE SYSTÈME DOIT proposer les règles prédéfinies à la place.
5. QUAND le texte de l'utilisateur est transmis au modèle, LE SYSTÈME DOIT le séparer des instructions et valider la sortie contre le schéma strict.

### 10. Interpréteur et provenance

1. QUAND les mêmes enregistrements et la même règle sont fournis, LE SYSTÈME DOIT produire les mêmes corrélations (déterminisme).
2. QUAND une corrélation est émise, LE SYSTÈME DOIT conserver `source` et `source_ref` de chaque enregistrement contributeur, et ne citer que des enregistrements présents en entrée.
3. QUAND la fenêtre temporelle d'une règle s'élargit, LE SYSTÈME DOIT conserver toutes les corrélations de la fenêtre étroite (monotonie).
4. LE SYSTÈME DOIT n'émettre aucune valeur absente des enregistrements sources.
5. QUAND un nom de produit est comparé, LE SYSTÈME DOIT accepter la correspondance exacte, par synonyme, par faute de frappe (mots longs) ou par inclusion de jetons, et refuser deux noms qui portent des nombres différents.

### 11. Sources indisponibles

1. SI une source est indisponible, ALORS LE SYSTÈME DOIT renvoyer les résultats partiels des autres règles et signaler la source manquante.

### 12. Règles prédéfinies

1. LE SYSTÈME DOIT fournir au moins cinq règles prédéfinies : alerte de stock bas, variation de prix, confirmation de commande client, rapprochement de paiement, détection d'anomalie.

### 13. Limitation de débit et budget

1. QUAND une adresse IP dépasse le quota de créations de règles (10 par 60 s par défaut), LE SYSTÈME DOIT répondre 429.
2. QUAND le cumul des dépenses du modèle atteint le plafond (5 USD), LE SYSTÈME DOIT refuser tout nouvel appel au modèle.
3. QUAND Redis est indisponible, LE SYSTÈME DOIT refuser l'appel au modèle plutôt que de le laisser sans compteur.

### 14. API et authentification

1. QUAND une requête vise `/api/v1` sans jeton valide, LE SYSTÈME DOIT répondre 401, sauf pour `POST /api/v1/auth/login`.
2. QUAND une entrée est reçue, LE SYSTÈME DOIT la valider côté serveur et ne jamais renvoyer la valeur rejetée dans une erreur 422.
3. QUAND une origine non listée appelle l'API, LE SYSTÈME DOIT la refuser (CORS en liste blanche).
4. LE SYSTÈME DOIT n'écrire aucune donnée personnelle ni aucun secret dans les journaux.

### 15. Configuration

1. SI une variable d'environnement requise manque ou est invalide, ALORS LE SYSTÈME DOIT s'arrêter au démarrage en nommant la variable et son usage, sans valeur de repli.
2. LE SYSTÈME DOIT ne lire les secrets que dans l'environnement.

### 16. Alertes par e-mail

1. QUAND une exécution produit de nouvelles corrélations de gravité `warning` ou `error` et que la configuration e-mail est complète, LE SYSTÈME DOIT envoyer un résumé, au plus un par période de refroidissement globale.
2. SI Redis échoue, ALORS LE SYSTÈME NE DOIT envoyer aucun e-mail.

## Correspondance avec Roadmap §7

| Roadmap §7 | Exigences |
|------------|-----------|
| R1 | 1 |
| R2 | 2 |
| R3 | 6 |
| R4 | 3 |
| R5 | 8, 9 |
| R6 | 10.1 |
| R7 | 10.2 |
| R8 | 11 |
| R9 | 9.4, 13 |
| R10, R11, R12 | `../chimeraflow-ui/requirements.md` |
| R13 | 2.3 |
