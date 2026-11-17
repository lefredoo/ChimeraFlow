# Tâches : avancement par phase

Source du plan : `Roadmap.md` §5. Ce fichier ne coche que ce qui est vérifié dans le dépôt
au 2026-11-14 (branche `dev`, HEAD 137da64). Un élément hors dépôt (déploiement, compte
GitHub, Vercel, Doppler) est noté comme non vérifié, et n'est pas coché.

Légende : `[x]` fait et vérifié dans le dépôt ; `[~]` partiel (la note dit ce qui manque) ; `[ ]` à faire.

---

## P0 : Fondations (13–14 nov.) — terminée côté dépôt

- [x] Structure du dépôt : `backend/` (FastAPI), `frontend/` (Next.js), `docker-compose.yml`, `docs/`
- [x] API FastAPI avec `GET /health` (`backend/main.py`)
- [x] Page d'accueil Next.js qui appelle `/health` (`frontend/app/page.tsx`)
- [x] `docker-compose.yml` : API et Redis, `mem_limit`, volume `data` en lecture seule, health checks
- [x] Trois specs Kiro : `connectors-spec.md`, `rule-engine-spec.md` et l'interface (`../chimeraflow-ui/design.md`, ancien `ui-spec.md`) ; depuis le 2026-11-17 une spec par dossier avec `requirements.md`, `design.md` et `tasks.md`
- [x] Deux steering : `connectors.md`, `security.md`
- [x] Générateurs de données synthétiques : `scripts/generate_excel.py`, `generate_whatsapp.py`, `generate_momo.py`, `generate_access_windows.vbs`
- [x] Spike Access : `data/STOCK_ZOBO.mdb` lu par `access-parser` (`test_access_readers.py`)
- [x] Licence MIT, LinguaSolution LLC (`LICENSE`)
- [x] Hello-world en production : frontend Vercel relié à l'API en HTTPS (en ligne depuis `dev`, voir `DECISIONS_LOG.md`)
- [x] Déploiement VPS (Dokploy/Traefik) de l'API et de Redis (en ligne en HTTPS depuis `dev`, voir `DECISIONS_LOG.md`)
- [ ] Specs approuvées : approbation non tracée dans le dépôt
- [ ] Dépôt GitHub public (**non vérifié dans le dépôt**)

## P1 : Connecteurs (15–19 nov.) — terminée côté code, MCP réalisé en stdio

- [x] Connecteurs Excel, Access, WhatsApp, Mobile Money (`backend/mcp_servers/`)
- [x] Enregistrement unifié (`mcp_servers/base.py`, AGENTS.md §19)
- [x] Tests de contrat R1 à R4 (`backend/tests/test_connectors.py`)
- [x] Hook `parser-test` (`.kiro/hooks/parser-test.json`)
- [x] Hook `spec-update-reminder` (`.kiro/hooks/spec-update-reminder.json`)
- [~] Propriétés de parseur (PBT) : P2 et P3 couvertes ; P1 et P6 partielles (`design.md` §12)
- [x] Parseur WhatsApp : Android et iOS, dates FR et EN (ordre jour/mois décidé par fichier), messages sur plusieurs lignes, pièces jointes signalées, messages système comptés à part (`backend/mcp_servers/whatsapp_parser.py`, `backend/tests/test_whatsapp_parser.py`)
- [x] Les quatre connecteurs servis en serveurs MCP stdio (`backend/mcp_servers/mcp_app.py`, lanceur `backend/mcp_main.py`, tests `backend/tests/test_mcp_servers.py`)
- [~] Enregistrement dans Kiro : `.kiro/settings/mcp.json` (local, chemins absolus, généré depuis le modèle `backend/mcp_servers/kiro-mcp.json`, testé ; démarrage des quatre serveurs vérifié depuis deux répertoires) ; reste à constater les quatre serveurs au vert dans le panneau MCP de Kiro
- [ ] Les quatre serveurs MCP dans un conteneur (AGENTS.md §18, cible d'architecture) : l'image runtime contient le lanceur, mais aucun service compose ne le démarre (stdio uniquement)

## P2 : Moteur de règles (20–24 nov.) — en cours

- [x] Normalisation d'entités avec `lang`, synonymes FR/EN, garde numérique, Levenshtein 0.85 (`engine/normalizer.py`)
- [x] Noms partiels : inclusion de mots (« tuyau PVC » dans « Tuyau PVC Ø 32mm (barre 6m) »), méthodes `exact`/`synonym`/`fuzzy`/`token` (`design.md` §4)
- [x] DSL JSON et interpréteur avec provenance (`engine/interpreter.py`, `schemas/rule.py`)
- [x] Extension du DSL : conditions sur le déclencheur (`trigger.where`), comparaison calculée (`ref`, `tolerance_pct`), jointure sur `entities`, bornes et colonnes autorisées
- [x] Plusieurs produits par message : une corrélation par produit
- [x] `explanation` par corrélation (colonne `correlations.explanation`, migration `0003`)
- [x] Validation de schéma : Pydantic, liste blanche d'opérateurs
- [x] Cinq règles prédéfinies dans `data/rules/*.json`, validées au démarrage et par `python -m engine.validate_rules`
- [x] Les cinq règles prédéfinies sont actives et chacune produit au moins une corrélation sur les données livrées (`test_scenario_data.py`)
- [x] Flux temps réel `GET /correlations/stream` (SSE, Bearer), paramètre `since`, bac à sable `POST /normalize`, `POST /demo/reset`
- [x] Alerte e-mail Cloudflare Email Service (nouvelles corrélations `warning` et `error`, un récapitulatif par exécution, testée avec le transport HTTP simulé ; jamais envoyée à un vrai Cloudflare Email Service)
- [x] API règles et corrélations, idempotence de l'exécution (`backend/api/`)
- [x] Migrations Alembic `0001` à `0003`, vérification modèles/migrations (`test_migrations.py`)
- [x] Limitation par IP (slowapi, Redis) sur les mutations, `429` et `Retry-After`
- [x] Conversion NL→règle : prompt séparé, validation, 2 relances, brouillon non stocké (`engine/nl_to_rule.py`)
- [x] Budget LLM : compteur Redis, plafond `LITELLM_BUDGET_USD`, réservation avant l'appel puis règlement, repli sur les règles prédéfinies
- [~] Conversion NL→règle en réel : pipeline testé avec LiteLLM simulé ; **aucun proxy LiteLLM réel connecté** (clé, URL et modèle à fournir)
- [~] Cible « ≥ 8/10 phrases FR/EN converties en règle valide » : non mesurée
- [~] Budget et limiteur : Redis testé seulement avec un faux client et le stockage mémoire ; la CI n'a pas de service Redis
- [~] Propriétés de corrélation : P1, P4, P5 couvertes par Hypothesis sur l'interpréteur ; P6 partielle (`design.md` §12)
- [ ] Doppler : configuration de développement et secrets (`doppler.yaml` présent, configuration non vérifiée)
- [ ] Neon : branche de développement de la base PostgreSQL
- [ ] CI verte sur GitHub Actions : **bloquée par la facturation du compte** (run 43569157569, voir `TECH_DEBT.md`)
- [x] Déploiement du backend sur le VPS avec migrations au démarrage (API en ligne en HTTPS)
- [ ] Pull request `dev` → `main` ouverte et fusionnée (squash, CI verte, une revue)

## P3 : Interface (25–29 nov.) — interface livrée (Crew abandonné)
Le détail des tâches de cette phase est dans `../chimeraflow-ui/tasks.md` (spec de l'interface).

## P4 : Durcissement (30 nov. – 1er déc.) — non commencée

- [x] Licence vérifiée : MIT, LinguaSolution LLC, présente à la racine
- [x] Pas de `.env.example` ; un seul `.env` racine (en production, seul `DOPPLER_TOKEN` est local)
- [~] README et documentation : traduction française et mise à jour des faits en cours (2026-11-14)
- [ ] Tests de fumée en production
- [~] Bouton de réinitialisation des données de démo : bouton et confirmation livrés sur le tableau de bord ; il appelle `POST /api/v1/demo/reset` (livré côté backend)
- [ ] Scan de secrets du dépôt et de l'historique
- [ ] Revue du `.kiro` et du `.gitignore`
- [ ] Gel du code le 1er décembre au soir

## P5 : Soumission (2–3 déc.) — non commencée

Rappel : Passer le dépôt GitHub en public avant la soumission (3 déc.)

- [ ] Vidéo de moins de 3 minutes (2 prises), publiée sur YouTube
- [ ] Write-up Kiro
- [ ] Article de blog mentionnant Kiroween 2026
- [ ] Publication sur les réseaux (`#KiroweenHackathon26`)
- [ ] Site et profil LinkedIn finalisés
- [ ] Formulaire Devpost soumis avant le 3 décembre, 18 h (Yaoundé)

---

## Hors plan : dette à traiter

- [x] Sécurité : authentification de tous les endpoints `/api/v1` (jeton Bearer, compte de démonstration) et page `/login` (`api-spec.md` §2.1 et §6, résidus dans TECH_DEBT)
- [ ] Voir `docs/decisions/TECH_DEBT.md` pour la liste complète, avec impact et fichiers
