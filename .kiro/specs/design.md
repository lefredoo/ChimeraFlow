# Design : architecture implémentée et propriétés de correction

Document de référence du backend ChimeraFlow, tel qu'il est codé sur la branche `dev`
(état du 2026-11-14). Il décrit ce qui existe dans le dépôt, pas l'intention. Les
propriétés P1 à P6 viennent de `Roadmap.md` §7. Leur statut vient de l'audit des tests
dans `backend/tests/` effectué le 2026-11-14.

Sources : `backend/` (code), `data/rules/*.json` (règles prédéfinies), `docker-compose.yml`.
Les endpoints sont décrits dans `api-spec.md`. L'avancement est dans `tasks.md`. Les
écarts connus sont dans `docs/decisions/TECH_DEBT.md`.

---

## 1. Vue d'ensemble

```
Frontend Next.js (frontend/app : page d'accueil qui appelle /health)
        │ HTTP, CORS (liste blanche)
FastAPI (backend/main.py)
  ├─ api/           routeurs sources, rules, correlations ; limitation par IP ; erreurs stables
  ├─ engine/        normaliseur, interpréteur, règles prédéfinies, NL→règle, budget LLM
  ├─ mcp_servers/   4 connecteurs (Excel, Access, WhatsApp, Mobile Money) → enregistrement unifié,
  │                 et leurs 4 serveurs MCP stdio (mcp_app.py, lancés par mcp_main.py)
  ├─ schemas/       modèles Pydantic : règle déclarative et réponses
  └─ models/, migrations/   SQLAlchemy 2 et Alembic (PostgreSQL en production, SQLite en tests)
Redis             compteurs du limiteur et compteur de dépense LLM
/data (lecture seule) fichiers synthétiques : 4 sources
```

Les connecteurs sont des classes Python appelées par l'API. Ils sont aussi exposés comme
serveurs MCP stdio (un processus par source, SDK `mcp`), que Kiro lance via
`.kiro/settings/mcp.json`. Les serveurs MCP lisent les mêmes fichiers que l'API mais
n'importent pas `config.py` : ils ne dépendent que de `DATA_DIR` et `ACCESS_READER`.
Le transport HTTP n'est pas exposé et les fichiers compose ne démarrent pas de serveur MCP.

---

## 2. Connecteurs

Contrat commun (`mcp_servers/base.py`, `BaseConnector`) :

- `fetch_records(limit)` renvoie une liste d'`UnifiedRecord`. La limite est bornée à 1000.
- `health_check()` renvoie `status`, `source`, `message`, `last_fetch`. Le résultat est mis en cache 30 secondes par instance.
- Une exception de lecture est transformée en statut `error` dans `health_check()` au lieu de faire tomber le processus.
- `CONNECTOR_ERRORS` regroupe les exceptions attendues : `OSError`, `ValueError`, `KeyError`, `RuntimeError`, `subprocess.SubprocessError`.

| Connecteur | Fichier source | Lecture | Particularités |
|------------|----------------|---------|----------------|
| `excel` | `data/tarifs_fournisseurs.xlsx` | pandas + openpyxl, feuille `Tarifs` | colonnes d'origine conservées dans le payload |
| `access` | `data/STOCK_ZOBO.mdb`, table `Articles` | `ACCESS_READER` : `mdbtools` (CLI `mdb-export`) ou `access-parser` (Python pur) | pas de repli automatique d'un lecteur vers l'autre |
| `whatsapp` | `data/commandes_clients.txt` | expression régulière | ne lit que le format Android `[JJ/MM/AAAA, HH:MM:SS] Auteur: Message` ; les autres lignes (format iOS, suite d'un message sur plusieurs lignes) sont comptées comme erreurs |
| `momo` | `data/momo_transactions.csv` | module `csv` | entités `payment` et `product` (tiré de `reference`) |

Serveur MCP (`mcp_servers/mcp_app.py`, réglages dans `mcp_servers/mcp_settings.py`) :

- Outils `fetch_records(limit)` (1 à 1000, validé par le schéma de l'outil) et `health_check()`, en lecture seule. Une ressource `chimeraflow://source/<source>` décrit la source.
- Chaque appel au connecteur s'exécute dans un thread de travail, avec 5 secondes maximum et 2 tentatives (attente 0,2 s puis 0,4 s). Les appels sont sérialisés par un verrou : le compteur `parse_errors` est un état partagé et le premier import de pandas/openpyxl n'est pas sûr depuis deux threads.
- Une erreur de lecture devient une erreur d'outil sans chemin de fichier. `DATA_DIR` absent ou invalide, ou `ACCESS_READER` absent ou inconnu (source `access`), arrête le processus (code 2).
- Journaux JSON sur stderr (stdout porte le protocole) : `connector`, `operation`, `records_count`, `errors_count`, `duration_ms`, `status`.

Règles de parsing communes :

- Une ligne invalide est ignorée, journalisée et comptée dans `parse_errors`. Aucune valeur n'est inventée (P6).
- Le fichier est lu à chaque appel. Si un fichier de source manque, `_fetch_all_records` (dans `api/correlations.py`) le saute : c'est le comportement dégradé demandé par R8.

---

## 3. Enregistrement unifié

Schéma (AGENTS.md §19, `UnifiedRecord`) :

| Champ | Contenu |
|-------|---------|
| `id` | identifiant du record dans la source |
| `source` | `excel`, `access`, `whatsapp` ou `momo` |
| `source_ref` | fichier et ligne ou ligne de tableau (`#L412`, `#row`) |
| `timestamp` | ISO 8601, souvent sans fuseau horaire |
| `lang` | `fr` ou `en` |
| `entities` | liste de `{type, raw, norm}` (`type` = `product`, `payment`) |
| `payload` | champs de la source, **avec les noms de colonnes d'origine** |

Le payload garde les noms d'origine (`Produit`, `Prix_Unitaire`, `qty_stock`, etc.) pour
que `field` et les placeholders `{source.champ}` des règles renvoient à ce que l'utilisateur voit.

---

## 4. Normaliseur (`engine/normalizer.py`)

`normalize_text()` est l'implémentation unique. `BaseConnector.normalize_text()` l'appelle.
Étapes, dans l'ordre :

1. minuscules ;
2. suppression des accents (NFD, marques `Mn` retirées) ;
3. décimal ou fraction entre deux chiffres (`2.5`, `1/2`) : séparateur converti en tiret, le nombre reste un seul jeton (`2-5`) ;
4. suppression de la ponctuation (tirets conservés) ;
5. séparation lettres et chiffres (`50kg` devient `50 kg`) ;
6. réduction des espaces, en dernier, pour l'idempotence (P2).

Mise en correspondance d'entités (`EntityNormalizer.match_detail`, qui renvoie `(matches, score, method)` ; `match` en renvoie le couple `(matches, score)`) :

1. normalisation puis application du dictionnaire de synonymes FR/EN (`SYNONYMS`) ; les formes préparées sont mises en cache par instance ;
2. égalité exacte après synonymes : score 1.0, méthode `exact` (même texte normalisé) ou `synonym` ;
3. **mêmes nombres des deux côtés** : similarité de Levenshtein normalisée (`rapidfuzz`) ≥ **0.85** avec le même nombre de mots, chaque paire de mots étant égale ou deux orthographes proches (similarité ≥ 0.75) d'un mot d'au moins 5 lettres : méthode `fuzzy` (fautes de frappe). « tuyau PVC 32mm » et « tuyau PPR 32mm » (0.87 en chaîne entière) sont donc deux produits ;
4. **nom partiel (`token`)** : un nom est contenu dans l'autre, mot pour mot (inclusion d'ensembles de mots : « ciment-colle » n'est pas « ciment »). Le nom le plus court doit porter au moins un vrai mot (3 lettres ou plus, pas un nombre : « kg » ou « 50 » seuls ne correspondent à rien), et ses nombres doivent figurer parmi ceux du nom le plus long. Score de 0.85 à 0.99 selon la part du nom long couverte (`rapidfuzz.fuzz.ratio` sur les mots triés) : à égalité de temps, le candidat le plus complet gagne, et jamais devant une correspondance exacte (1.0) ;
5. **garde numérique** : si les nombres diffèrent, il n'y a correspondance que par inclusion (étape 4), donc seulement si les nombres du nom court sont tous dans le nom long. « ciment 50 kg » et « ciment 40 kg » ne correspondent jamais, ni « ciment 50 kg » et « Ciment-colle 25 kg » ; « tuyau PVC » (sans nombre) correspond à « Tuyau PVC Ø 32mm (barre 6m) ».

Choix : le `token_set_ratio` de rapidfuzz vaut 100 pour une inclusion, mais il note aussi 0.9 deux noms qui se recouvrent seulement (« tuyau pvc 32mm » et « tuyau ppr 32mm »). L'inclusion est donc testée exactement avec des ensembles, et rapidfuzz ne sert qu'à noter la couverture.

Limites connues : une inclusion est permissive pour un nom d'un seul mot (« ciment » correspond à tout produit dont le nom contient `ciment` comme mot) : à égalité de score, le départage de l'interpréteur choisit. « ciment 50 kg » et « ciment colle 50 kg » (sans trait d'union) correspondent par inclusion. Quelques synonymes ne peuvent jamais s'appliquer (`l` pour tout mot `l`, voir TECH_DEBT).

---

## 5. Interpréteur (`engine/interpreter.py`)

Entrée : une règle (`RuleCreate`), les records du déclencheur, les records de toutes les sources.
Sortie : une liste de corrélations, sans heure de détection (P4).

Pour chaque record déclencheur de la bonne source :

1. Les conditions `trigger.where` doivent être vraies pour le payload du record (valeurs littérales). Sinon : pas de corrélation.
2. Le record doit porter au moins une entité du type `trigger.entity`. **Chaque entité de ce type est corrélée** : un message qui demande deux produits donne deux corrélations. Deux mentions qui se normalisent pareil (« ciment 50kg » et « Ciment 50 kg ») ne comptent que pour une, la première. L'ordre est celui des entités du record.
3. Fenêtre : `[t − window_seconds ; t + window_seconds]`, symétrique. Les timestamps sans fuseau sont lus en UTC.
4. Pour chaque `join`, dans l'ordre : candidats = records de la source du join qui sont dans la fenêtre, dont le champ `on.field` correspond à l'entité (normaliseur), et dont toutes les conditions `where` sont vraies. Avec `on.field = "entities"`, le nom comparé est chaque entité de type `on.entity` du record joint (le meilleur score est retenu pour le record). Une condition `ref` lit le payload du déclencheur ou d'un join précédent ; avec `tolerance_pct` elle compare l'écart relatif (arrondi à 6 décimales) à la tolérance.
5. Choix du meilleur candidat, par clé ordonnée : score le plus élevé, puis record situé avant ou à l'instant du déclencheur, puis distance temporelle la plus petite, puis ordre dans la source. Le dernier prix avant le message gagne donc sur les doublons.
6. Tous les joins doivent trouver un candidat (jointure interne). Sinon : pas de corrélation.
7. Le message est rendu en une seule passe (`render_template`). Les valeurs viennent du payload du déclencheur (sous le nom de sa source) et de chaque record joint. Un texte venu d'une source contenant `{momo.phone}` reste littéral. Un placeholder sans valeur devient une chaîne vide.
8. La provenance liste le record déclencheur puis chaque record joint (P1).
9. `explanation` (voir api-spec.md §1.3) : entité du déclencheur (brut et normalisé), conditions du déclencheur avec leurs valeurs, et pour chaque join le record, le nom comparé, le score, la méthode, le nombre de candidats et les conditions avec `expected`, `actual`, `gap_pct`.

Opérateurs (liste blanche `Operator`) : `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `contains`, `in`. Une comparaison entre types incompatibles (`"n/a" < 10`) est un non-match et ne fait pas échouer la règle. Une valeur absente (`None`) ou une référence nulle est un non-match.

Vocabulaire fermé de comparaison calculée : `ref` (`<source>.<colonne>`, limité au déclencheur et aux joins précédents, validé à la création) et `tolerance_pct` (0 à 1000, opérateurs d'ordre seulement). Aucune expression libre, aucun code : l'écart `|a − b| / |b|` est la seule formule du moteur.

---

## 6. Règles, prédéfinies et persistance

### 6.1 Schéma de règle (`schemas/rule.py`, AGENTS.md §20)

- `id` : `^[a-z0-9_]+$`, 1 à 100 caractères.
- `natural_language` : 10 à 1000 caractères.
- `trigger` : `source` (`whatsapp`, `momo`, `excel`, `access`), `entity` et `where` (conditions sur le record déclencheur, valeurs littérales, 10 au plus).
- `joins` : 1 à 10. Un join `access` exige `table`. Un join `excel` exige `sheet`. `on` exige `entity` et `field` (une colonne, ou `entities`, voir §5). `where` : 10 conditions au plus.
- Condition : `field`, `op`, et `value` ou `ref` (+ `tolerance_pct`). Clés inconnues refusées. `value` : scalaire de 200 caractères au plus ou liste de 50 scalaires au plus.
- `window_seconds` : 60 à 2 592 000 (30 jours), 604 800 par défaut (7 jours).
- `emit` : `severity` (`info`, `warning`, `error`) et `template` (500 caractères au plus).
- Validation croisée (`validate_references`) : toute colonne citée existe dans sa source (`schemas/sources.py`), un `ref` vise le déclencheur ou un join précédent (jamais dans `trigger.where`), un placeholder du `template` est `{product}` ou `{source.colonne}` d'une source de la règle, jamais `momo.phone` ni `momo.customer_name` (données personnelles). Un brouillon du modèle de langage qui invente une colonne est refusé et relancé avec l'erreur.

Pas de code, pas d'expression libre : une règle est une donnée validée.

### 6.2 Règles prédéfinies (`data/rules/*.json`)

Une règle par fichier. Le fichier contient les champs de `RuleCreate` plus `status`.
`engine/predefined_rules.py` les charge au démarrage. Un fichier invalide, un `id` différent
du nom de fichier ou une clé inconnue arrête l'application.

| Règle | Statut initial | Raison |
|-------|----------------|--------|
| `r_low_stock` | active | alerte de stock (démo) |
| `r_high_value_order` | active | suivi des commandes à forte valeur |
| `r_payment_received` | active | `trigger.where` statut `SUCCESS`, jointure WhatsApp sur `entities` (fenêtre 24 h) |
| `r_price_comparison` | active | jointure Excel avec `ref: access.prix_achat` et `tolerance_pct: 10` (écart > 10 %) |
| `r_stock_replenish` | active | `trigger.where` stock Access < 15, commande WhatsApp récente (3 jours) et prix Excel |

Le seed (`models/seed.py`) est idempotent : il insère ou met à jour les règles au démarrage.
Une règle dont la définition livrée a changé reçoit la nouvelle définition, `version + 1` **et le statut
de son fichier** (c'est ainsi qu'une version réactive les trois règles corrigées). Une règle inchangée garde son statut
stocké, donc un choix d'opérateur en base survit à un redémarrage. Aucun endpoint ne modifie le statut. La première
version qui introduit `trigger.where` incrémente aussi la version des deux autres règles (la forme sérialisée du déclencheur change).
`POST /api/v1/demo/reset` rétablit toutes les règles prédéfinies à l'état de leur fichier. Un identifiant prédéfini reste réservé
(`POST /rules` renvoie 409, même si la ligne a été supprimée).

### 6.3 Tables (migrations Alembic)

- `rules` : définition (JSON pour `trigger`, `joins`, `emit`), `status`, `version`, dates UTC.
- `rule_executions` : durée, nombre de correspondances, nombre de records lus, erreur générique.
- `correlations` : message, `severity`, provenance (JSON), `explanation` (JSON, nullable), fenêtre, `detected_at`.
- `correlations` et `rule_executions` référencent `rules.id` avec `ON DELETE CASCADE`. Les clés étrangères sont aussi actives sur SQLite (tests).
- Migrations : `0001_initial_schema`, `0002_drop_rules_created_by` qui supprime la colonne `created_by` (l'adresse IP du client n'est plus stockée), puis `0003_add_correlation_explanation` qui ajoute `correlations.explanation` (JSON nullable ; les lignes antérieures restent à `null`). `test_migrations.py` contrôle `upgrade head`, `downgrade -1`, `upgrade head` et l'égalité avec les modèles.

### 6.4 Exécution (`POST /api/v1/correlations/execute`)

- Seules les règles `active` sont exécutées (ou celles de `rule_ids`, 20 au maximum).
- Les corrélations stockées d'une règle exécutée deviennent exactement celles qui viennent d'être trouvées. L'identité d'une corrélation est `(message, ids des records de la provenance)` : une corrélation retrouvée garde sa ligne, son `id` et son `detected_at` (son explication et sa fenêtre sont rafraîchies), une corrélation disparue est supprimée, une nouvelle est insérée avec l'heure de la règle. Deux exécutions identiques donnent la même liste. Les clients (flux, `since`, e-mail) voient donc seulement le nouveau.
- Chaque règle tourne dans son propre savepoint. Une règle en échec n'écrit rien, garde ses corrélations précédentes, et enregistre `Rule execution failed` (le détail part dans les journaux).
- Chaque source lit au plus 1000 records. La lecture des connecteurs et le travail sur la base se font dans des threads (`anyio.to_thread`, `run_in_threadpool`) : ils ne bloquent pas la boucle d'événements. Les handlers de lecture et d'écriture de `rules.py` sont des fonctions synchrones (FastAPI les exécute dans son pool).
- Alerte e-mail (`engine/alerts.py`) : les nouvelles corrélations `warning` et `error` d'une exécution partent dans **un** e-mail récapitulatif (Cloudflare Email Service, API REST via `httpx` ; succès = HTTP 2xx et `success: true`), envoyé après la réponse (`BackgroundTasks`). Fonction active seulement si `CF_EMAIL_ACCOUNT_ID`, `CF_EMAIL_API_TOKEN`, `ALERT_EMAIL_FROM` et `ALERT_EMAIL_TO` (1 à 5 adresses, séparées par des virgules) sont définies. 2 essais, 5 s chacun, nouvel essai sur 5xx et 429 seulement. Ni destinataire, ni jeton, ni contenu dans les journaux (seuls les codes d'erreur de Cloudflare). Les messages (texte de sources non fiable) perdent leurs caractères de contrôle, sont bornés à 300 caractères (50 lignes au plus) et la partie HTML est échappée. Un échec d'envoi n'affecte jamais la réponse.

### 6.5 Flux temps réel, bac à sable et réinitialisation

- `GET /api/v1/correlations/stream` (`api/correlation_stream.py`) : SSE lu avec `fetch` et l'en-tête Bearer (l'`EventSource` ne sait pas envoyer d'en-tête ; pas de jeton de flux, donc aucun jeton dans une URL). Interrogation de la base toutes les 2 s : elle fonctionne avec plusieurs processus. Curseur : id de corrélation (`Last-Event-ID`). Fermeture après 300 s (`end`), 20 flux au plus.
- `POST /api/v1/normalize` (`api/normalize.py`) : mêmes formes préparées et même `match_detail` que le moteur. Sans limite par IP (sans état, borné, authentifié), voir DECISIONS_LOG.
- `POST /api/v1/demo/reset` (`api/demo.py`) : supprime corrélations et exécutions, rétablit les règles prédéfinies, garde les règles créées par l'API.

---

## 7. API

Les endpoints, leurs corps, leurs réponses et leurs codes d'erreur sont dans `api-spec.md`.
Le principe de réponse d'erreur est dans `backend/api/errors.py` :
`{"detail": {"code": "<code stable>", "message": "<texte court en anglais>"}}`.

---

## 8. Limitation de débit (`api/rate_limit.py`)

- slowapi, un compteur par endpoint (`key_style="endpoint"`), stocké dans Redis (`REDIS_URL`). Le stockage mémoire n'est utilisé que si `BACKEND_NODE_ENV=test`.
- Endpoints limités : `POST /rules`, `DELETE /rules/{id}`, `POST /correlations/execute` (`RATE_LIMIT_PER_IP` par `RATE_LIMIT_WINDOW_SECONDS`) et `POST /rules/from-text` (`RATE_LIMIT_NL_PER_IP`, plus strict). Les lectures ne sont pas limitées.
- Dépassement : `429 rate_limit_exceeded` avec `Retry-After`.
- Redis du limiteur injoignable : `503 rate_limit_unavailable`. La mutation est refusée, jamais laissée sans limite.
- IP du client : adresse du pair TCP. `X-Forwarded-For` n'est lu que si le pair est dans `TRUSTED_PROXIES`, de droite à gauche. Une IPv4 mappée en IPv6 compte comme IPv4. Un client IPv6 est compté par `/64`.

---

## 9. Conversion NL→règle (`engine/nl_to_rule.py`, `engine/llm_client.py`)

Pipeline de `POST /api/v1/rules/from-text` :

1. Le texte (20 à 1000 caractères après `strip`) est transmis comme donnée, pas comme instruction. Le message système porte les règles de format et la liste des colonnes. Le message utilisateur porte un objet JSON `{description, language}` entre les marqueurs `<<<USER_DATA` et `USER_DATA>>>`. Les suites de trois `<` ou `>` sont réduites à deux.
2. Appel LiteLLM (`acompletion`) : `base_url` et `model` depuis la configuration, `temperature=0`, `max_tokens=1500`, `response_format=json_object`, `timeout=20 s`, sans retry interne de LiteLLM (`num_retries=0`).
3. La réponse doit être un objet JSON (une clôture markdown est tolérée). Seules les clés `trigger`, `joins`, `window_seconds`, `emit` sont admises. `id` et `natural_language` sont fixés par le serveur. La réponse est validée par `RuleCreate`.
4. En cas d'échec, le modèle reçoit son propre message (au plus 2000 caractères) et les erreurs de validation, sans les valeurs rejetées. **2 relances au plus, soit 3 appels.**
5. Le brouillon est renvoyé (`id` généré `r_nl_<12 hex>`, `natural_language` = texte de l'utilisateur). **Rien n'est stocké** : le client doit appeler `POST /api/v1/rules`.

Erreurs : `nl_feature_disabled` (503), `nl_budget_exceeded` (503), `nl_budget_unavailable` (503), `nl_provider_error` (502), `nl_conversion_failed` (422). Les erreurs `nl_*` contiennent `fallback_rules` : les règles prédéfinies.

**État réel** : le pipeline est testé avec `litellm.acompletion` simulé. Aucun appel à un vrai proxy LiteLLM n'a été fait (clé, URL et nom de modèle non configurés). L'alias nu (`LITELLM_MODEL`, envoyé avec `custom_llm_provider="openai"`) et `completion_cost` ne sont donc pas vérifiés en réel (TECH_DEBT).

---

## 10. Budget LLM (`engine/nl_budget.py`)

- Compteur global dans Redis, clé `chimeraflow:nl:spent_microusd` (micro-dollars), **sans expiration**. Supprimer la clé remet le budget à zéro.
- **Réservation** avant chaque tentative : le coût estimé (prompt + 1500 tokens de réponse, à 15 USD par million) est ajouté au compteur par `INCRBY`, qui renvoie le total. Si la dépense d'avant cet appel (total − réservation, en micro-dollars entiers) atteint `LITELLM_BUDGET_USD`, la réservation est rendue et l'appel refusé (503) sans appel au modèle. Des appels simultanés voient les réservations les uns des autres : le plafond n'est dépassé que d'un appel au plus.
- **Règlement** après l'appel : la réservation est remplacée par le coût réel (`INCRBY` de la différence, négative si besoin). `litellm.completion_cost` si le modèle est chiffré, sinon estimation par tokens à 15 USD par million (constante volontairement pénalisante). En cas d'échec de l'appel, un coût d'entrée pessimiste (caractères ÷ 4) est conservé. Si le règlement échoue (Redis), la réservation reste comptée : le compteur ne sous-estime jamais.
- Redis injoignable ou compteur illisible : refus (`nl_budget_unavailable`). Le budget n'est jamais supposé.
- Limite connue : une requête annulée (client coupé) laisse sa réservation comptée jusqu'à une remise à zéro de la clé.

---

## 11. Sécurité (règles de `AGENTS.md` §1 et §9)

- Aucune exécution de code généré : la règle est du JSON validé, interprété avec une liste blanche d'opérateurs.
- Entrées validées côté serveur par Pydantic (corps et bornes). Les clés inconnues renvoyées par le modèle sont refusées par la conversion et déclenchent une relance (`test_should_retry_when_the_answer_has_an_unexpected_key`).
- Texte utilisateur séparé des instructions dans le prompt. Réponse du modèle validée, jamais suivie.
- Erreurs : codes stables, sans écho des valeurs rejetées ni du texte.
- Journaux : pas de texte utilisateur, pas de réponse du modèle, pas de clé API, pas d'IP (une seule ligne par conversion : issue, tentatives, coût, durée).
- CORS : liste blanche (`CORS_ORIGINS`).
- Authentification : tous les endpoints `/api/v1` exigent un jeton Bearer (dépendance `require_auth` posée à l'inclusion des routeurs dans `main.py`). Un compte de démonstration unique et public ; mot de passe haché en scrypt (`hashlib`), jeton HMAC-SHA256 de 1 h, comparaisons à temps constant, même réponse 401 pour un email inconnu et un mot de passe faux, login limité par IP (`RATE_LIMIT_LOGIN_PER_IP`) et deux hachages simultanés au plus. Aucune dépendance ajoutée. Ni jeton, ni mot de passe, ni email dans les journaux ; les réponses 422 n'échoient pas la valeur rejetée. `/docs`, `/redoc` et `/openapi.json` servis seulement en `development` et `test`. Décision et alternatives : DECISIONS_LOG, entrée du 2026-11-15.
- Frontend : jeton en mémoire et `sessionStorage` (jamais `localStorage` ni cookie), un 401 renvoie à `/login`. La page `/login` affiche les identifiants de démonstration publics (`NEXT_PUBLIC_DEMO_LOGIN_*`) après un clic sur « Voir les identifiants » : ils ne figurent pas dans le HTML prérendu.
- **Non implémenté** : assainissement des textes de source avant affichage (travail frontend, R12) ; révocation d'un jeton avant son expiration ; comptes individuels.

---

## 12. Propriétés de correction (P1 à P6)

Statuts : **couverte** (test automatisé du comportement énoncé), **partielle** (test qui ne couvre qu'une partie de l'énoncé), **non couverte** (aucun test du comportement).

### P1 : conservation de la provenance

**Énoncé** : chaque corrélation émise ne liste que des records présents dans les entrées.

**Tests** :
- `backend/tests/test_interpreter.py::test_should_list_every_contributing_record_when_correlation_is_emitted` : la provenance contient le record déclencheur et le record joint.
- `backend/tests/test_properties.py::TestProvenance::test_source_ref_present` : chaque record connecteur a un `source_ref` avec `#`.
- `backend/tests/test_api_correlations.py::test_should_persist_correlations_when_executing_a_predefined_rule` : la corrélation enregistrée référence `r_low_stock`.

**Tests ajoutés** : `backend/tests/test_interpreter_properties.py::test_should_cite_only_input_records_when_a_correlation_is_emitted` (Hypothesis : chaque `(source, record_id, source_ref)` cité existe dans les entrées).

**Statut : couverte pour l'interpréteur.** Le test de `source_ref` des connecteurs ne porte que sur WhatsApp.

### P2 : idempotence de la normalisation

**Énoncé** : `norm(norm(x)) == norm(x)`.

**Tests** :
- `backend/tests/test_properties.py::TestNormalizationProperties::test_normalization_idempotent` (Hypothesis, texte arbitraire).
- `backend/tests/test_normalizer.py::test_should_be_idempotent_when_normalizing_any_text` (Hypothesis).
- `backend/tests/test_normalizer.py::test_should_be_idempotent_when_text_contains_decimals_or_fractions` (cas `Câble 2.5mm`, `tuyau 1/2 pouce`, etc.).

**Statut : couverte.** Le test Hypothesis a trouvé un cas réel (caractère U+2110 sans minuscule), corrigé dans le normaliseur.

### P3 : aller-retour du parseur

**Énoncé** : `parse(export(messages)) == messages` pour les formats Android et iOS, FR et EN.

**Mise en œuvre** : `export_messages(messages, format)` (`backend/mcp_servers/whatsapp_parser.py`) écrit cinq formats (`android_fr`, `android_nobracket_fr`, `ios_fr`, `ios_en`, `android_en`) ; `parse_export` les relit. Deux formats n'ont pas de secondes : l'export refuse alors un message dont la seconde n'est pas nulle. Les formats EN sont mois d'abord : l'aller-retour se fait avec `default_date_order="mdy"` (règle de l'ordre jour/mois dans `backend/README.md`). Messages générés : texte sur 1 à 3 lignes (lignes vides et caractères Unicode quelconques compris, sauf contrôles, séparateurs de ligne et marques invisibles), auteur sans `:`, espaces réservés de pièces jointes FR et EN, dates de 2000 à 2099.

**Tests** (Hypothesis, `backend/tests/test_properties.py::TestParserRoundTrip`) :
- `test_should_parse_back_the_exported_messages_when_exporting_in_any_format` : `parse_export(export_messages(m, f)) == m` (horodatage, auteur, texte, drapeau de pièce jointe), sans erreur ni message système.
- `test_should_number_each_message_by_its_first_line_when_exporting_in_any_format` : le numéro de ligne de chaque message est celui de sa première ligne.
- `test_should_return_the_exported_messages_when_the_connector_reads_the_file` : même propriété à travers un fichier et `WhatsAppConnector.fetch_records` (payload `author`, `text`, `attachment`).
- Cas d'exemple dans `backend/tests/test_whatsapp_parser.py` (formats, ordre des dates, multi-lignes, pièces jointes, messages système, erreurs).
- `test_whatsapp_parse_lossless` (même classe `TestRoundTrip`) reste un test de lecture des données livrées, il ne porte pas la propriété.

**Statut : couverte.** Limite : le round-trip ne génère que des messages dont aucune ligne de suite ne ressemble à un en-tête (sinon la ligne serait un nouveau message, par construction du format), et les messages système ne sont pas exportés.

### P4 : déterminisme

**Énoncé** : mêmes entrées et même règle, même sortie.

**Tests** :
- `backend/tests/test_interpreter.py::test_should_return_identical_correlations_when_executed_twice_with_same_inputs`
- `backend/tests/test_interpreter.py::test_should_return_identical_messages_when_executed_twice`
- `backend/tests/test_interpreter.py::test_should_not_set_detection_time_when_engine_emits_a_correlation`
- `backend/tests/test_properties.py::TestDeterminism::test_normalization_deterministic`
- `backend/tests/test_api_correlations.py::test_should_return_same_correlation_count_when_executing_twice`

**Test ajouté** : `backend/tests/test_interpreter_properties.py::test_should_return_identical_correlations_when_the_same_inputs_are_run_twice` (Hypothesis, entrées générées).

**Statut : couverte.** Le départage des candidats est couvert par des tests dédiés (`test_should_pick_latest_price_at_or_before_trigger_when_duplicates_exist`, `test_should_keep_source_order_when_candidates_are_identical_in_score_and_time`).

### P5 : monotonie de la fenêtre

**Énoncé** : élargir la fenêtre ne retire aucune corrélation.

**Précision** : « corrélation » désigne ici le couple (record déclencheur, entité) qui a trouvé tous ses joins. Le record choisi peut changer quand la fenêtre grandit (un candidat meilleur entre dedans), mais un couple corrélé le reste, parce que l'ensemble des candidats d'une fenêtre est inclus dans celui d'une fenêtre plus large (même chemin de code, la fenêtre est le seul paramètre qui change).

**Tests** :
- `backend/tests/test_interpreter_properties.py::test_should_keep_every_correlation_when_the_window_is_widened` (Hypothesis : deux fenêtres tirées entre 60 s et 30 jours, messages et prix à des décalages aléatoires, plusieurs produits par message).
- `backend/tests/test_interpreter_properties.py::test_should_keep_every_correlation_when_the_window_is_widened_and_a_condition_filters_candidates` (même propriété avec une condition `where` sur les candidats).
- `backend/tests/test_interpreter.py::test_should_not_emit_correlation_when_joined_record_is_outside_window` : exclusion hors fenêtre.

**Statut : couverte.** Les tests de bornes exactes de fenêtre (record à `t ± window_seconds`) restent à écrire (TECH_DEBT).

### P6 : absence de fabrication

**Énoncé** : aucune valeur émise n'est absente des records sources.

**Tests** :
- `backend/tests/test_properties.py::TestNoFabrication::test_entities_from_payload` : sur WhatsApp uniquement, vérifie qu'au moins un mot de plus de deux lettres de l'entité apparaît dans le payload.
- `backend/tests/test_connector_payloads.py::test_should_emit_product_entity_when_reading_momo_reference` : l'entité vient de la colonne `reference` du CSV.
- `backend/tests/test_interpreter.py::test_should_not_expand_braces_when_source_text_contains_a_placeholder` : un texte source n'est pas réinterprété comme placeholder.
- `backend/tests/test_interpreter.py::test_should_render_empty_text_when_placeholder_field_is_missing` : un champ absent donne une chaîne vide.

**Test ajouté** : `backend/tests/test_interpreter_properties.py::test_should_only_render_prices_found_in_the_sources_when_a_correlation_is_emitted` (Hypothesis : le prix rendu dans un message est un prix présent dans les records Excel d'entrée).

**Statut : partielle.** La vérification de l'entité des connecteurs est faible (un seul mot suffit) et ne porte que sur WhatsApp ; le test de l'interpréteur ne couvre que le champ `Prix_Unitaire` du message.

### Synthèse

| Propriété | Statut | Tests principaux |
|-----------|--------|------------------|
| P1 Provenance | couverte (interpréteur) | `test_interpreter_properties.py`, `test_interpreter.py`, `test_properties.py::TestProvenance` |
| P2 Idempotence | couverte | `test_properties.py`, `test_normalizer.py` (Hypothesis) |
| P3 Aller-retour | couverte | `test_properties.py::TestParserRoundTrip` (Hypothesis), `test_whatsapp_parser.py` |
| P4 Déterminisme | couverte | `test_interpreter_properties.py`, `test_interpreter.py`, `test_api_correlations.py` |
| P5 Monotonie | couverte | `test_interpreter_properties.py` (Hypothesis) |
| P6 Pas de fabrication | partielle | `test_interpreter_properties.py`, `test_properties.py::TestNoFabrication`, `test_interpreter.py` |

Propriétés du comparateur de noms (`test_normalizer.py`, Hypothesis) : symétrie, score entre 0 et 1, un nom se compare exactement à lui-même, mêmes résultats avant et après normalisation.

---

## 13. Écarts connus

Détail et priorités dans `docs/decisions/TECH_DEBT.md`. Principaux : pas de service Redis
ni de vrai proxy LiteLLM en CI ; fenêtre symétrique (une note WhatsApp peut corréler un prix
postérieur) ; un nom d'un seul mot correspond à tout produit qui le contient ; alerte e-mail
jamais envoyée à un vrai Cloudflare Email Service ; propriété P6 incomplète.
