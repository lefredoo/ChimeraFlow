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
  ├─ mcp_servers/   4 connecteurs (Excel, Access, WhatsApp, Mobile Money) → enregistrement unifié
  ├─ schemas/       modèles Pydantic : règle déclarative et réponses
  └─ models/, migrations/   SQLAlchemy 2 et Alembic (PostgreSQL en production, SQLite en tests)
Redis             compteurs du limiteur et compteur de dépense LLM
/data (lecture seule) fichiers synthétiques : 4 sources
```

Les connecteurs sont des classes Python appelées par l'API. Ils ne sont pas encore exposés
comme serveurs MCP (le protocole MCP et `.kiro/settings/mcp.json` restent à faire, voir `tasks.md`).

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

Mise en correspondance d'entités (`EntityNormalizer.match`) :

1. normalisation puis application du dictionnaire de synonymes FR/EN (`SYNONYMS`) ;
2. égalité exacte après synonymes : score 1.0 ;
3. **garde numérique** : si la liste des nombres diffère (`["50"]` contre `["40"]`), pas de correspondance, score 0.0 ;
4. sinon similarité de Levenshtein normalisée (`rapidfuzz`), correspondance si score ≥ **0.85**.

Limites connues : la comparaison porte sur la chaîne entière (un nom partiel ne correspond pas) et quelques synonymes ne peuvent jamais s'appliquer (voir TECH_DEBT).

---

## 5. Interpréteur (`engine/interpreter.py`)

Entrée : une règle (`RuleCreate`), les records du déclencheur, les records de toutes les sources.
Sortie : une liste de corrélations, sans heure de détection (P4).

Pour chaque record déclencheur de la bonne source :

1. Le record doit porter une entité du type `trigger.entity`. Sinon : pas de corrélation.
2. Fenêtre : `[t − window_seconds ; t + window_seconds]`, symétrique. Les timestamps sans fuseau sont lus en UTC.
3. Pour chaque `join`, dans l'ordre : candidats = records de la source du join qui sont dans la fenêtre, dont le champ `on.field` correspond à l'entité (normaliseur), et dont toutes les conditions `where` sont vraies.
4. Choix du meilleur candidat, par clé ordonnée : score le plus élevé, puis record situé avant ou à l'instant du déclencheur, puis distance temporelle la plus petite, puis ordre dans la source. Le dernier prix avant le message gagne donc sur les doublons.
5. Tous les joins doivent trouver un candidat (jointure interne). Sinon : pas de corrélation.
6. Le message est rendu en une seule passe (`render_template`). Un texte venu d'une source contenant `{momo.phone}` reste littéral. Un placeholder sans valeur devient une chaîne vide.
7. La provenance liste le record déclencheur puis chaque record joint (P1).

Opérateurs (liste blanche `Operator`) : `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `contains`, `in`. Une comparaison entre types incompatibles (`"n/a" < 10`) est un non-match et ne fait pas échouer la règle. Les conditions `where` ne portent que sur le record joint : il n'existe pas encore de condition sur le record déclencheur (voir TECH_DEBT, règles désactivées).

---

## 6. Règles, prédéfinies et persistance

### 6.1 Schéma de règle (`schemas/rule.py`, AGENTS.md §20)

- `id` : `^[a-z0-9_]+$`, 1 à 100 caractères.
- `natural_language` : 10 à 1000 caractères.
- `trigger` : `source` (`whatsapp`, `momo`, `excel`, `access`) et `entity`.
- `joins` : 1 à 10. Un join `access` exige `table`. Un join `excel` exige `sheet`.
- `window_seconds` : 60 à 2 592 000 (30 jours), 604 800 par défaut (7 jours).
- `emit` : `severity` (`info`, `warning`, `error`) et `template`.

Pas de code, pas d'expression libre : une règle est une donnée validée.

### 6.2 Règles prédéfinies (`data/rules/*.json`)

Une règle par fichier. Le fichier contient les champs de `RuleCreate` plus `status`.
`engine/predefined_rules.py` les charge au démarrage. Un fichier invalide, un `id` différent
du nom de fichier ou une clé inconnue arrête l'application.

| Règle | Statut initial | Raison |
|-------|----------------|--------|
| `r_low_stock` | active | alerte de stock (démo) |
| `r_high_value_order` | active | suivi des commandes à forte valeur |
| `r_payment_received` | inactive | promet un filtre sur le statut PENDING que le DSL ne sait pas exprimer |
| `r_price_comparison` | inactive | promet un écart supérieur à 10 %, non calculable par le DSL |
| `r_stock_replenish` | inactive | promet un seuil sur le record déclencheur, condition absente du DSL |

Le seed (`models/seed.py`) est idempotent : il insère ou met à jour les règles au démarrage,
sans écraser le statut choisi par un opérateur. Un identifiant prédéfini reste réservé
(`POST /rules` renvoie 409, même si la ligne a été supprimée).

### 6.3 Tables (migrations Alembic)

- `rules` : définition (JSON pour `trigger`, `joins`, `emit`), `status`, `version`, dates UTC.
- `rule_executions` : durée, nombre de correspondances, nombre de records lus, erreur générique.
- `correlations` : message, `severity`, provenance (JSON), fenêtre, `detected_at`.
- `correlations` et `rule_executions` référencent `rules.id` avec `ON DELETE CASCADE`. Les clés étrangères sont aussi actives sur SQLite (tests).
- Migrations : `0001_initial_schema`, puis `0002_drop_rules_created_by` qui supprime la colonne `created_by`. L'adresse IP du client n'est donc plus stockée (contrôlé par `test_migrations.py`).

### 6.4 Exécution (`POST /api/v1/correlations/execute`)

- Seules les règles `active` sont exécutées (ou celles de `rule_ids`, 20 au maximum).
- Chaque exécution **remplace** les corrélations précédentes de la règle. Deux exécutions identiques donnent la même liste.
- Chaque règle tourne dans son propre savepoint. Une règle en échec n'écrit rien, garde ses corrélations précédentes, et enregistre `Rule execution failed` (le détail part dans les journaux).
- Chaque source lit au plus 1000 records.

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

**État réel** : le pipeline est testé avec `litellm.acompletion` simulé. Aucun appel à un vrai proxy LiteLLM n'a été fait (clé, URL et nom de modèle non configurés). Le format `openai/<alias>` et `completion_cost` ne sont donc pas vérifiés en réel (TECH_DEBT).

---

## 10. Budget LLM (`engine/nl_budget.py`)

- Compteur global dans Redis, clé `chimeraflow:nl:spent_microusd` (micro-dollars), **sans expiration**. Supprimer la clé remet le budget à zéro.
- Avant chaque tentative : si la dépense atteint `LITELLM_BUDGET_USD`, refus (503) sans appel au modèle.
- Coût après chaque appel : `litellm.completion_cost` si le modèle est chiffré. Sinon estimation par tokens à 15 USD par million (constante volontairement pénalisante). En cas d'échec de l'appel, un coût d'entrée pessimiste (caractères ÷ 4) est enregistré.
- Redis injoignable ou compteur illisible : refus (`nl_budget_unavailable`). Le budget n'est jamais supposé.
- Limite connue : contrôle puis ajout du coût. Des appels concurrents peuvent dépasser le plafond (TECH_DEBT).

---

## 11. Sécurité (règles de `AGENTS.md` §1 et §9)

- Aucune exécution de code généré : la règle est du JSON validé, interprété avec une liste blanche d'opérateurs.
- Entrées validées côté serveur par Pydantic (corps et bornes). Les clés inconnues renvoyées par le modèle sont refusées par la conversion et déclenchent une relance (`test_should_retry_when_the_answer_has_an_unexpected_key`).
- Texte utilisateur séparé des instructions dans le prompt. Réponse du modèle validée, jamais suivie.
- Erreurs : codes stables, sans écho des valeurs rejetées ni du texte.
- Journaux : pas de texte utilisateur, pas de réponse du modèle, pas de clé API, pas d'IP (une seule ligne par conversion : issue, tentatives, coût, durée).
- CORS : liste blanche (`CORS_ORIGINS`).
- **Non implémenté** : authentification (aucun endpoint n'est protégé, la limitation par IP est la seule barrière) ; assainissement des textes de source avant affichage (travail frontend, R12).

---

## 12. Propriétés de correction (P1 à P6)

Statuts : **couverte** (test automatisé du comportement énoncé), **partielle** (test qui ne couvre qu'une partie de l'énoncé), **non couverte** (aucun test du comportement).

### P1 : conservation de la provenance

**Énoncé** : chaque corrélation émise ne liste que des records présents dans les entrées.

**Tests** :
- `backend/tests/test_interpreter.py::test_should_list_every_contributing_record_when_correlation_is_emitted` : la provenance contient le record déclencheur et le record joint.
- `backend/tests/test_properties.py::TestProvenance::test_source_ref_present` : chaque record connecteur a un `source_ref` avec `#`.
- `backend/tests/test_api_correlations.py::test_should_persist_correlations_when_executing_a_predefined_rule` : la corrélation enregistrée référence `r_low_stock`.

**Statut : partielle.** Aucun test ne vérifie sur des entrées générées que chaque `record_id` de la provenance existe dans les entrées. Le test de `source_ref` ne porte que sur WhatsApp.

### P2 : idempotence de la normalisation

**Énoncé** : `norm(norm(x)) == norm(x)`.

**Tests** :
- `backend/tests/test_properties.py::TestNormalizationProperties::test_normalization_idempotent` (Hypothesis, texte arbitraire).
- `backend/tests/test_normalizer.py::test_should_be_idempotent_when_normalizing_any_text` (Hypothesis).
- `backend/tests/test_normalizer.py::test_should_be_idempotent_when_text_contains_decimals_or_fractions` (cas `Câble 2.5mm`, `tuyau 1/2 pouce`, etc.).

**Statut : couverte.** Le test Hypothesis a trouvé un cas réel (caractère U+2110 sans minuscule), corrigé dans le normaliseur.

### P3 : aller-retour du parseur

**Énoncé** : `parse(export(messages)) == messages` pour les formats Android et iOS, FR et EN.

**Tests** : `backend/tests/test_properties.py::TestRoundTrip::test_whatsapp_parse_lossless` ne vérifie que la présence non vide de `author` et `text`. Aucune fonction d'export n'existe. Le format iOS n'est pas lu (il est compté comme erreur).

**Statut : non couverte.** Le test porte un autre nom que la propriété. À corriger si P3 est retenue.

### P4 : déterminisme

**Énoncé** : mêmes entrées et même règle, même sortie.

**Tests** :
- `backend/tests/test_interpreter.py::test_should_return_identical_correlations_when_executed_twice_with_same_inputs`
- `backend/tests/test_interpreter.py::test_should_return_identical_messages_when_executed_twice`
- `backend/tests/test_interpreter.py::test_should_not_set_detection_time_when_engine_emits_a_correlation`
- `backend/tests/test_properties.py::TestDeterminism::test_normalization_deterministic`
- `backend/tests/test_api_correlations.py::test_should_return_same_correlation_count_when_executing_twice`

**Statut : partielle.** Les tests vérifient des exemples fixes, sans générateur Hypothesis sur l'interpréteur. Le départage des candidats est couvert par des tests dédiés (`test_should_pick_latest_price_at_or_before_trigger_when_duplicates_exist`, `test_should_keep_source_order_when_candidates_are_identical_in_score_and_time`).

### P5 : monotonie de la fenêtre

**Énoncé** : élargir la fenêtre ne retire aucune corrélation.

**Tests** : `backend/tests/test_interpreter.py::test_should_not_emit_correlation_when_joined_record_is_outside_window` vérifie seulement l'exclusion hors fenêtre. Aucun test ne compare deux fenêtres.

**Statut : non couverte.** La propriété tient en principe, car l'ensemble des candidats ne fait que grandir avec la fenêtre, mais rien ne le vérifie. Les tests de bornes de fenêtre manquent aussi (TECH_DEBT).

### P6 : absence de fabrication

**Énoncé** : aucune valeur émise n'est absente des records sources.

**Tests** :
- `backend/tests/test_properties.py::TestNoFabrication::test_entities_from_payload` : sur WhatsApp uniquement, vérifie qu'au moins un mot de plus de deux lettres de l'entité apparaît dans le payload.
- `backend/tests/test_connector_payloads.py::test_should_emit_product_entity_when_reading_momo_reference` : l'entité vient de la colonne `reference` du CSV.
- `backend/tests/test_interpreter.py::test_should_not_expand_braces_when_source_text_contains_a_placeholder` : un texte source n'est pas réinterprété comme placeholder.
- `backend/tests/test_interpreter.py::test_should_render_empty_text_when_placeholder_field_is_missing` : un champ absent donne une chaîne vide.

**Statut : partielle.** La vérification de l'entité est faible (un seul mot suffit), elle ne porte que sur WhatsApp, et la valeur des corrélations n'est pas comparée aux sources.

### Synthèse

| Propriété | Statut | Tests principaux |
|-----------|--------|------------------|
| P1 Provenance | partielle | `test_interpreter.py`, `test_properties.py::TestProvenance` |
| P2 Idempotence | couverte | `test_properties.py`, `test_normalizer.py` (Hypothesis) |
| P3 Aller-retour | non couverte | `test_properties.py::TestRoundTrip` (ne teste pas la propriété) |
| P4 Déterminisme | partielle | `test_interpreter.py`, `test_api_correlations.py` |
| P5 Monotonie | non couverte | aucun |
| P6 Pas de fabrication | partielle | `test_properties.py::TestNoFabrication`, `test_interpreter.py` |

---

## 13. Écarts connus

Détail et priorités dans `docs/decisions/TECH_DEBT.md`. Principaux : pas de service Redis
ni de vrai proxy LiteLLM en CI ; une seule entité par message ; fenêtre symétrique (une
note WhatsApp peut corréler un prix postérieur) ; comparaison de noms entiers ; tests de
propriétés incomplets (P3, P5 absentes, P1, P4, P6 partielles).
