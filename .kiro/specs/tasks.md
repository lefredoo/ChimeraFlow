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
- [x] Trois specs Kiro : `connectors-spec.md`, `rule-engine-spec.md`, `ui-spec.md`
- [x] Deux steering : `connectors.md`, `security.md`
- [x] Générateurs de données synthétiques : `scripts/generate_excel.py`, `generate_whatsapp.py`, `generate_momo.py`, `generate_access_windows.vbs`
- [x] Spike Access : `data/STOCK_ZOBO.mdb` lu par `access-parser` (`test_access_readers.py`)
- [x] Licence MIT, LinguaSolution LLC (`LICENSE`)
- [ ] Hello-world en production : frontend Vercel relié à l'API en HTTPS (**non vérifié dans le dépôt**)
- [ ] Déploiement VPS (Dokploy/Traefik) de l'API et de Redis (**non vérifié dans le dépôt**)
- [ ] Specs approuvées : approbation non tracée dans le dépôt
- [ ] Dépôt GitHub public (**non vérifié dans le dépôt**)

## P1 : Connecteurs (15–19 nov.) — terminée côté code, MCP non réalisé

- [x] Connecteurs Excel, Access, WhatsApp, Mobile Money (`backend/mcp_servers/`)
- [x] Enregistrement unifié (`mcp_servers/base.py`, AGENTS.md §19)
- [x] Tests de contrat R1 à R4 (`backend/tests/test_connectors.py`)
- [x] Hook `parser-test` (`.kiro/hooks/parser-test.json`)
- [x] Hook `spec-update-reminder` (`.kiro/hooks/spec-update-reminder.json`)
- [~] Propriétés de parseur (PBT) : P2 couverte ; P1 et P6 partielles ; P3 non couverte (`design.md` §12)
- [~] Parseur WhatsApp : format Android seulement ; le format iOS et les messages sur plusieurs lignes sont comptés comme erreurs (`TECH_DEBT.md`)
- [ ] Trois connecteurs servis en serveurs MCP et enregistrés dans `.kiro/settings/mcp.json` (**fichier absent**, pas de serveur MCP)
- [ ] Les quatre serveurs MCP dans un conteneur (AGENTS.md §18, cible d'architecture)

## P2 : Moteur de règles (20–24 nov.) — en cours

- [x] Normalisation d'entités avec `lang`, synonymes FR/EN, garde numérique, Levenshtein 0.85 (`engine/normalizer.py`)
- [x] DSL JSON et interpréteur avec provenance (`engine/interpreter.py`, `schemas/rule.py`)
- [x] Validation de schéma : Pydantic, liste blanche d'opérateurs
- [x] Cinq règles prédéfinies dans `data/rules/*.json`, validées au démarrage et par `python -m engine.validate_rules`
- [~] Trois règles prédéfinies sur cinq sont `inactive` (`r_payment_received`, `r_price_comparison`, `r_stock_replenish`) : le critère « 3 règles correctes sur le jeu de données » n'est pas atteint
- [x] API règles et corrélations, idempotence de l'exécution (`backend/api/`)
- [x] Migrations Alembic `0001` et `0002`, vérification modèles/migrations (`test_migrations.py`)
- [x] Limitation par IP (slowapi, Redis) sur les mutations, `429` et `Retry-After`
- [x] Conversion NL→règle : prompt séparé, validation, 2 relances, brouillon non stocké (`engine/nl_to_rule.py`)
- [x] Budget LLM : compteur Redis, plafond `LITELLM_BUDGET_USD`, repli sur les règles prédéfinies
- [~] Conversion NL→règle en réel : pipeline testé avec LiteLLM simulé ; **aucun proxy LiteLLM réel connecté** (clé, URL et modèle à fournir)
- [~] Cible « ≥ 8/10 phrases FR/EN converties en règle valide » : non mesurée
- [~] Budget et limiteur : Redis testé seulement avec un faux client et le stockage mémoire ; la CI n'a pas de service Redis
- [~] Propriétés de corrélation : P1, P4, P6 partielles ; P5 non couverte (`design.md` §12)
- [ ] Doppler : configuration de développement et secrets (`doppler.yaml` présent, configuration non vérifiée)
- [ ] Neon : branche de développement de la base PostgreSQL
- [ ] CI verte sur GitHub Actions : **bloquée par la facturation du compte** (run 43569157569, voir `TECH_DEBT.md`)
- [ ] Déploiement du backend sur le VPS avec migrations au démarrage
- [ ] Pull request `dev` → `main` ouverte et fusionnée (squash, CI verte, une revue)

## P3 : Interface et Crew (25–29 nov.) — non commencée

- [ ] Tableau de bord mobile-first (le frontend actuel est une page d'accueil de test)
- [ ] Composeur de règles en langage naturel, avec aperçu du brouillon et repli sur les règles prédéfinies
- [ ] Cartes de corrélation avec badges par source et tiroir de provenance (R10)
- [ ] Assainissement des textes de source avant affichage (R12) : côté frontend, aucun code aujourd'hui
- [ ] État dégradé quand une source est absente (R8)
- [ ] Mise en page utilisable à 360 px et au clavier, contraste WCAG AA (R11)
- [ ] Connecteur n°4 généré par Crew en session enregistrée (`.kiro/agents/` absent)
- [ ] Hook `rule-validate` : déjà présent (`.kiro/hooks/rule-validate.json`, cible `data/rules/*.json`) ; l'agent qu'il lance reste à valider en session

## P4 : Durcissement (30 nov. – 1er déc.) — non commencée

- [x] Licence vérifiée : MIT, LinguaSolution LLC, présente à la racine
- [x] Pas de `.env.example` ; un seul `.env` racine (en production, seul `DOPPLER_TOKEN` est local)
- [~] README et documentation : traduction française et mise à jour des faits en cours (2026-11-14)
- [ ] Tests de fumée en production
- [ ] Bouton de réinitialisation des données de démo
- [ ] Scan de secrets du dépôt et de l'historique
- [ ] Revue du `.kiro` et du `.gitignore`
- [ ] Gel du code le 1er décembre au soir

## P5 : Soumission (2–3 déc.) — non commencée

- [ ] Vidéo de moins de 3 minutes (2 prises), publiée sur YouTube
- [ ] Write-up Kiro
- [ ] Article de blog mentionnant Kiroween 2026
- [ ] Publication sur les réseaux (`#KiroweenHackathon26`)
- [ ] Site et profil LinkedIn finalisés
- [ ] Formulaire Devpost soumis avant le 3 décembre, 18 h (Yaoundé)

---

## Hors plan : dette à traiter

- [ ] Sécurité : authentification des endpoints sensibles (`api-spec.md` §6)
- [ ] Voir `docs/decisions/TECH_DEBT.md` pour la liste complète, avec impact et fichiers
