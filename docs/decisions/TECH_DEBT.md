# Technical Debt

Issues identified but not resolved in the current cycle.
Required by AGENTS.md §15.

---

## Format

[YYYY-MM-DD] Problem description | Estimated impact (low/med/high) | Concerned file(s)

---

## Current Debt
- [2026-11-17] Alerte e-mail : le rejet définitif est détecté (`permanent_bounces`) mais seuls les compteurs de `result` sont connus par une réponse observée en production ; les rejets différés après mise en file (`queued` puis rebond) ne sont pas détectables depuis la réponse d'envoi, et la réception réelle de l'e-mail depuis `mail.linguasolution.com` reste à confirmer par le propriétaire | Med | backend/engine/alerts.py
- [2026-11-17] Relances LLM : l'enchaînement erreur passagère puis succès, le modèle de repli (`LITELLM_FALLBACK_MODEL`) et le plafond de 45 s ne sont testés qu'avec `litellm.acompletion` simulé et une horloge factice, jamais contre le vrai proxy ; les 2 relances sont partagées par toute la conversation (une relance de validation qui rencontre une panne peut manquer de relances), et le repli reste actif pour les appels suivants d'une même requête | Low | backend/engine/nl_to_rule.py, backend/engine/llm_client.py
- [2026-11-17] Parseur WhatsApp : (1) un export dont toutes les dates sont ambiguës (champs ≤ 12) est lu avec `default_date_order` (`dmy`), un export EN doit être déclaré `mdy` à la construction du connecteur, sans réglage par variable d'environnement ; (2) un message système est reconnu par l'absence d'auteur, donc un message système contenant « : » (ex. un nom de groupe) est lu comme un message ; (3) une ligne de suite qui ressemble à un en-tête (`12/11/2026 10:00 - …`) démarre un message ; (4) le fichier entier est lu à chaque appel ; (5) `attachment` n'est pas une colonne utilisable dans une règle (absente de `schemas/sources.py`) | Low | backend/mcp_servers/whatsapp_parser.py, backend/mcp_servers/whatsapp_connector.py
- [2026-11-17] `python-dateutil` repassé à 2.9.0.post0 (`< 3`) : `litellm >= 1.100.4` (correctif des alertes Dependabot 1 et 22) exige `boto3`, dont `botocore` borne `python-dateutil < 3`. Remonter la version quand botocore lèvera la borne ; `boto3`, `botocore`, `s3transfer` alourdissent l'image | Low | backend/requirements.txt
- [2026-11-17] Dans Dokploy v0.31.0, le toggle du tableau de bord, le changement de ports ou de variables et la mise à jour de version de Traefik recréent le conteneur `dokploy-traefik` : `traefik.yml` est conservé (et rétabli par `check-traefik-config.timer` en cas de dérive), mais le montage du secret DNS-01 `/run/secrets/cf_dns_api_token` est perdu et l'image passe à `traefik:v3.7.16` (`TRAEFIK_VERSION` n'est pas posée sur le service `dokploy`). Le garde-fou signale le montage manquant sans recréer le conteneur ; à ne pas utiliser, sinon recréer avec `.cloudflare-backup\r6-traefik-recreate.sh` du propriétaire | Low | ops/vps/check-traefik-config.sh
- [2026-11-16] Flux SSE et interface : course possible sur la réservation d'un emplacement de flux, plafond par IP absent (seulement 20 flux par processus), flux non suspendu dans un onglet masqué, reconnexion sans délai croissant, et l'interrogation toutes les 2 s garde la base Neon éveillée | Med | backend/api/correlation_stream.py, frontend/lib/hooks, frontend/components
- [2026-11-16] La première mise en production incrémente `version` des 5 règles prédéfinies et applique le statut du fichier (une règle désactivée à la main peut être réactivée) | Low | backend/models/seed.py
- [2026-11-16] Un nom d'un seul mot correspond à tout produit qui le contient (voir l'entrée du 2026-11-15, toujours ouverte) | Low | backend/engine/normalizer.py
- [2026-11-16] `correlations_found` peut dépasser le nombre de lignes de corrélations stockées | Low | backend/api/correlations.py
- [2026-11-16] Les règles personnalisées déjà stockées qui violent la nouvelle liste blanche de colonnes ou la règle « une seule jointure par source » échoueront à l'exécution (« Rule execution failed ») : à vérifier en production avant le déploiement | Med | backend/schemas/rule.py, backend/engine/interpreter.py
- [2026-11-16] Tests manquants relevés par la revue du 2026-11-16 (détail dans le rapport de revue) | Low | backend/tests
- [2026-11-16] Le compteur `parse_errors` des connecteurs est partagé entre les threads, et les lectures en thread des serveurs MCP n'utilisent pas `abandon_on_cancel` | Low | backend/mcp_servers/base.py, backend/mcp_servers
- [2026-11-16] Un e-mail d'alerte tombé pendant le délai global est perdu (les corrélations ne sont « nouvelles » qu'une fois) et un échec d'envoi consomme aussi le délai | Low | backend/engine/alerts.py
- [2026-11-15] L'alerte e-mail n'a jamais été envoyée à un vrai Cloudflare Email Service (transport HTTP simulé : jeton, domaine d'envoi `mail.linguasolution.com` et format de la réponse non vérifiés) ; la conversion NL→règle n'a jamais appelé le vrai proxy avec l'alias nu | Med | backend/engine/alerts.py
- [2026-11-15] Un nom d'un seul mot correspond à tout produit qui le contient (« ciment » : « Ciment 50 kg » et « Ciment 25 kg » à score égal, le départage par le temps choisit) ; « ciment colle 50 kg » (sans trait d'union) correspond à « ciment 50 kg ». Inclusion de mots volontaire, à resserrer (mot-clé seul exclu) si la démonstration montre de faux rapprochements | Low | backend/engine/normalizer.py
- [2026-11-15] `POST /api/v1/demo/reset` est ouvert à tout compte authentifié (le compte de démonstration est public et partagé) : n'importe quel visiteur connecté peut effacer les corrélations et rétablir les règles | Low | backend/api/demo.py
- [2026-11-15] Flux SSE : une interrogation de la base toutes les 2 s par flux (20 flux au plus, compteur par processus et non global), pas de LISTEN/NOTIFY ni de Redis pub/sub ; sur SQLite un `id` supprimé peut être réattribué (le curseur le manquerait, PostgreSQL n'a pas ce cas) | Low | backend/api/correlation_stream.py
- [2026-11-15] Le seed incrémente `version` des deux règles inchangées lors de la première mise à jour (la forme sérialisée du déclencheur gagne `where`) et la définition d'une règle est comparée par égalité JSON | Low | backend/models/seed.py
- [2026-11-15] L'écart calculé (`tolerance_pct`) est relatif à la valeur de `ref` : `|a − b| / |b|`, donc asymétrique selon le sens de la comparaison ; une règle qui veut l'écart relatif au tarif fournisseur doit déclencher sur Excel | Low | backend/engine/interpreter.py
- [2026-11-17] Audit navigateur (Edge headless, axe-core, API simulée) : 360 px, clavier, contraste et boîtes de dialogue vérifiés en thèmes clair et sombre, mais jamais avec un lecteur d'écran réel, ni Firefox ou Safari, ni un téléphone, ni l'API réelle ; l'audit n'est pas rejoué en CI | Low | frontend/components, frontend/app/components.css
- [2026-11-15] Le thème sombre choisi explicitement est appliqué après l'hydratation (un éclair de thème clair est possible) ; un script bloquant dans `<head>` l'éviterait | Low | frontend/components/theme-provider.tsx
- [2026-11-15] Nombre d'enregistrements par source plafonné à 500 par lecture (`/sources/all/records`) : `/sources` n'expose pas de compteur | Low | frontend/lib/services/sources-service.ts
- [2026-11-15] Pas d'éditeur de règle JSON ni de page Paramètres (budget LLM, limiteur) : l'API n'expose ni budget ni état du limiteur | Low | frontend/components/rules-view.tsx
- [2026-11-15] MCP : `.kiro/settings/mcp.json` est passé en chemins absolus et `cwd` (les quatre serveurs répondent à `tools/list` depuis n'importe quel répertoire) mais l'affichage dans le panneau MCP de Kiro n'est pas constaté ; à vérifier à la main après rechargement de la fenêtre, journal Kiro en niveau Debug | Med | .kiro/settings/mcp.json, backend/mcp_servers/kiro-mcp.json
- [2026-11-15] MCP : transport stdio seulement, aucun service compose ni HTTP streamable : « 4 serveurs MCP dans un conteneur » (AGENTS.md §18) reste une cible | Low | docker-compose.yml, backend/mcp_servers/mcp_app.py
- [2026-11-15] MCP : après un dépassement de 5 s le thread de lecture n'est pas interrompu (Python ne tue pas un thread), il se termine seul ; le verrou de sérialisation reste tenu par l'appel suivant seulement quand celui-ci attend | Low | backend/mcp_servers/mcp_app.py
- [2026-11-15] MCP : `mcp` 2.3.0 est récent et ses dépendances (httpx2, pyjwt, cryptography, pywin32 sous Windows) ne sont pas épinglées ; `ACCESS_READERS` existe dans `config.py` et dans `access_connector.py` | Low | backend/requirements.txt, backend/config.py, backend/mcp_servers/access_connector.py
- [2026-11-15] Dokploy utilise le jeton Doppler en écriture : à remplacer par un jeton de service en lecture seule pour `chimeraflow/prd` | High | docker-compose.yml, Dokploy
- [2026-11-15] Branche de production Vercel encore `main` : les déploiements de `dev` sont manuels, à basculer | Med | Vercel
- [2026-11-15] Résidus de revue non corrigés : corps de requête analysé avant l'authentification (422 avant 401), file d'attente du `CapacityLimiter` non bornée, scrypt par défaut sous la recommandation OWASP (N = 2^17) | Low | backend/api/auth.py, backend/auth/passwords.py
- [2026-11-15] Les identifiants de démonstration sont masqués derrière un bouton « Voir les identifiants » : cela évite le HTML prérendu mais pas la lecture du bundle JS | Low | frontend/components/login-form.tsx

- [2026-11-15] Authentification : un seul compte de démonstration partagé et public, pas de comptes individuels ni de rôles | Med | backend/api/auth.py, backend/config.py
- [2026-11-15] Les identifiants de démonstration sont dans le bundle JS public (`NEXT_PUBLIC_DEMO_LOGIN_*`) : un robot qui lit le bundle peut se connecter, seule la limitation par IP (`RATE_LIMIT_LOGIN_PER_IP`) le freine ; un défi anti-robot (CAPTCHA) ne serait pas une dépendance triviale | Med | frontend/lib/demo-credentials.ts, frontend/components/login-form.tsx
- [2026-11-15] Pas de révocation d'un jeton avant son expiration (1 h) ; seul le changement de `AUTH_TOKEN_SECRET` invalide toutes les sessions | Low | backend/auth/tokens.py
- [2026-11-15] Jeton conservé dans `sessionStorage` : lisible par un script injecté (XSS) ; atténué par l'échappement des textes affichés et la durée de 1 h | Low | frontend/lib/auth/token-storage.ts
- [2026-11-17] Le formulaire de connexion est testé (jsdom : bouton d'identifiants, connexion en un clic, erreur annoncée) mais le parcours complet avec l'API réelle n'est pas automatisé (ni dans la CI) | Low | frontend/components/login-form.tsx, frontend/components/auth-provider.tsx
- [2026-11-15] `anyio` importé directement (plafond de hachages simultanés), dépendance transitive de FastAPI non épinglée dans requirements.txt | Low | backend/api/auth.py, backend/requirements.txt
- [2026-11-15] `/docs` absent sauf si `BACKEND_NODE_ENV` vaut `development` ou `test`, y compris avec `docker-compose.yml` local (`production`) : pour l'utiliser en local, lancer uvicorn avec `BACKEND_NODE_ENV=development` | Low | backend/main.py, docker-compose.yml
- [2026-11-15] CI : le job `migrations-postgres` reçoit un hash factice (valide, jamais utilisé) ; la CI n'exécute pas le parcours de connexion de bout en bout | Low | .github/workflows/ci.yml
- [2026-11-17] Next.js reste en 15.5.29 (dernière 15.x) : l'avis postcss est fermé par `overrides.next.postcss` (^8.5.23), pas par une montée de version. À retirer de `package.json` quand Next passera en 16 (migration : `next lint` retiré, ESLint 9 et config plate, Node ≥ 20.9) | Low | frontend/package.json
- [2026-11-14] Tailwind v4 déclaré dans package.json mais non branché (ni `@tailwindcss/postcss` ni `postcss.config`) : le CSS du frontend est du CSS simple à tokens ; brancher Tailwind demande une dépendance à approuver | Low | frontend/package.json, frontend/app/globals.css
- [2026-11-14] `next lint` est déprécié (retiré dans Next 16) : migrer vers l'ESLint CLI (`npx @next/codemod@canary next-lint-to-eslint-cli .`) | Low | frontend/package.json, frontend/.eslintrc.json
- [2026-11-14] Le processus uvicorn hérite de `DOPPLER_TOKEN` (`doppler run` transmet l'environnement) ; un jeton de service en lecture seule limite l'exposition | Low | backend/docker-entrypoint.sh
- [2026-11-14] HEALTHCHECK de l'image et des compose en dur sur le port 8000 : `BACKEND_PORT` dans Doppler doit rester absent ou égal à 8000 | Low | backend/Dockerfile, docker-compose.prod.yml
- [2026-11-14] Image `redis:7-alpine` non figée par digest (tag mobile) et Doppler CLI épinglé à 3.77.1 sans mise à jour automatique | Low | backend/Dockerfile
- [2026-11-14] Documentation à mettre à jour (hors périmètre de cette tâche, édition en cours par un autre agent) : le build runtime exige `--build-context data=./data` hors compose, `docker-compose.prod.yml` et le démarrage Doppler ne sont décrits ni dans README.md, backend/README.md ni docs/deployment | Med | README.md, backend/README.md, docs/deployment/P0-setup.md
- [2026-11-14] Compose de production non éprouvé sur le VPS (Dokploy, Traefik, Doppler réel) : seuls des essais locaux avec un faux serveur Doppler ont été faits | Med | docker-compose.prod.yml
- [2026-11-17] CI frontend : `npm audit` ne tourne pas en CI ; le résultat est maintenant propre (0 avis, dev compris) et pourrait devenir une étape bloquante | Low | .github/workflows/ci.yml
- [2026-11-14] `@import` Google Fonts dans globals.css : requête vers un tiers (confidentialité, CSP) ; migrer vers `next/font` (auto-hébergement des polices IBM Plex) | Low | frontend/app/globals.css
- [2026-11-15] Règlement du budget LLM : si l'`INCRBY` qui remplace la réservation par le coût réel échoue, la réservation (pessimiste) reste comptée ; une requête annulée garde aussi sa réservation. Le compteur ne sous-estime jamais, mais peut s'user plus vite que le coût réel | Low | backend/engine/nl_to_rule.py
- [2026-11-14] Caractères non URL-safe de REDIS_PASSWORD non vérifiés au démarrage | Low | docker-compose.yml, backend/config.py
- [2026-11-15] Pas de service Redis dans la CI : aucun test d'intégration marqué Redis n'existe (le limiteur utilise la mémoire en `BACKEND_NODE_ENV=test`, le compteur de dépense un faux client) ; ajouter le service avec le premier test d'intégration Redis | Med | .github/workflows/ci.yml, backend/tests
- [2026-11-15] Dokploy : `autoDeploy` désactivé sur `chimeraflow-api` (branche `main`), le déploiement reste manuel ; à activer après un premier déploiement vérifié depuis `main` | Low | Dokploy, docs/deployment/PRODUCTION.md
- [2026-11-14] Des tests manipulent les internes du limiteur (`limiter.limiter.hit`, `limiter.reset`) au lieu de ne mocker que la frontière Redis | Low | backend/tests/test_rate_limit.py, backend/tests/conftest.py
- [2026-11-14] Boucles `for` dans le corps de tests (règle « pas de logique dans les tests ») | Low | backend/tests/test_rate_limit.py
- [2026-11-14] La conversion NL→règle n'a jamais appelé le vrai proxy LiteLLM (clé, URL et modèle inconnus) : `response_format` json_object, `drop_params`, la forme du nom de modèle et `completion_cost` sont non vérifiés en réel | Med | backend/engine/llm_client.py
- [2026-11-14] RedisSpendStore et le limiteur ne sont testés qu'avec un faux client Redis et le stockage mémoire (vérifiés une fois à la main sur Redis local) ; la CI n'a pas de service Redis | Med | backend/tests/test_nl_to_rule.py, backend/tests/test_rate_limit.py, .github/workflows/ci.yml
- [2026-11-14] Prix de repli (15 USD / million de tokens) quand LiteLLM ne sait pas chiffrer le modèle : constante en code, non configurable | Low | backend/engine/llm_client.py
- [2026-11-14] Le `template` généré par le modèle dérive d'un texte non fiable : le frontend doit l'échapper à l'affichage (comme les textes de sources) | Med | frontend
- [2026-11-14] `limits.errors.StorageError` importé directement depuis `limits`, dépendance transitive de slowapi non épinglée dans requirements.txt | Low | backend/api/rate_limit.py, backend/requirements.txt
- [2026-11-14] access-parser : une colonne Currency avec propriété Format renvoie une chaîne formatée, prix_achat devient None | Low | backend/mcp_servers/access_connector.py
- [2026-11-14] Équivalence des lecteurs Access vérifiée seulement là où mdbtools est installé (Docker) : à exécuter en CI | Med | backend/tests/test_access_readers.py
- [2026-11-14] Boucle for/if dans un test (règle « pas de logique dans les tests ») | Low | backend/tests/test_access_readers.py
- [2026-11-14] `access-parser` reader has no 5 s timeout (in-process, unlike `mdb-export`) | Low | backend/mcp_servers/access_connector.py
- [2026-11-13] Savepoint partial-rollback path untested: test_should_keep_previous_correlations_when_a_rule_fails raises before any DML | Low | backend/tests/test_api_correlations.py
- [2026-11-13] Seeding idempotence test counts rows but doesn't assert version == 1 after re-seed | Low | backend/tests/test_api_correlations.py
- [2026-11-13] models/seed.py change detection relies on JSON round-trip equality; a future Enum field would bump version on every restart | Low | backend/models/seed.py

### Residual review findings (not fixed, non-blocking)

- [2026-11-13] Time window is symmetric for every source, so a WhatsApp message can match a stock or price record dated after it | Low | backend/engine/interpreter.py
- [2026-11-13] Le synonyme `l` -> `litre` s'applique à tout mot `l` isolé | Low | backend/engine/normalizer.py
- [2026-11-13] Tests manquants : tests d'erreur de parsing des connecteurs (connectors.md), tests API des endpoints de règles, tests des opérateurs `eq`, `ne`, `lte`, `gte`, `contains`, `in` et des bornes exactes de fenêtre (`t ± window_seconds`) | Medium | backend/tests/
- [2026-11-13] `rules.created_by` stores the client IP address (personal data) | Medium | backend/api/rules.py, backend/models/rule.py
- [2026-11-13] Source text is not sanitized backend-side; the frontend must escape messages and payload values before display (security.md rule 2) | Medium | backend/engine/interpreter.py
- [2026-11-13] `DELETE /rules/{id}` accepts a predefined rule id; the rule comes back at the next startup (the id stays reserved for `POST /rules`) | Low | backend/api/rules.py

---

### [2026-11-13] Source timestamps without offset are treated as UTC | Low | backend/engine/interpreter.py

**Problem**: WhatsApp, Excel, Access and MoMo timestamps carry no timezone. The interpreter reads them as UTC. The demo business is in Douala (UTC+1), so the window is shifted by one hour at most.

**Impact**: Low - negligible for windows of one day or more.

**Solution**: Add a source timezone setting when windows shorter than a few hours are needed.

---

### [2026-11-13] WhatsApp parser limits | Low | backend/mcp_servers/whatsapp_connector.py

**Problem**: Product extraction uses a hardcoded keyword list (ciment, pointe, vis, tuyau, ...). (Multi-line messages and the iOS format are handled since 2026-11-17, see `whatsapp_parser.py`.)

**Impact**: Low - sufficient for the demo data, does not generalize.

**Solution**: LLM-assisted extraction once LiteLLM is available.

---

### [2026-11-13] No containerization for MCP servers yet | Medium | backend/

**Problem**: P1 focused on connector logic. Docker Compose exists but MCP server container not yet configured.

**Impact**: Medium - deployment to VPS Hetzner will need container setup.

**Solution**: P3 task (Docker integration).

---

_Add new entries at the top of this file (reverse chronological order)._

- [2026-11-17] Le service MCP hébergé limite le débit en mémoire (un compteur par processus, remis à zéro à chaque redémarrage) et n'a qu'un jeton partagé sans rotation automatique | low | backend/mcp_servers/mcp_http_app.py
- [2026-11-17] `client_ip` de l'API (`api/rate_limit.py`) et `resolve_client` du service MCP dupliquent la lecture de `X-Forwarded-For` car `config.py` n'est pas importable sans les réglages de l'API ; à extraire dans un module commun | low | backend/api/rate_limit.py, backend/mcp_servers/mcp_http_app.py
- [2026-11-17] Le jeton de service Doppler de `chimeraflow/prd` accepte l'écriture alors que PRODUCTION.md le décrit en lecture seule : le remplacer par un jeton en lecture seule pour les conteneurs | med | docs/deployment/PRODUCTION.md
