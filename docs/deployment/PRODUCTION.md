# Production : architecture, déploiement, exploitation

Ce document décrit la production de ChimeraFlow et les gestes d'exploitation courants. Il ne contient aucun secret : les valeurs vivent dans Doppler, Dokploy et Vercel.

## Architecture

| Élément | Rôle | Où |
|---------|------|----|
| Frontend Next.js | `https://chimeraflow.linguasolution.com` | Vercel, projet `chimeraflow` (aucun secret, seules les variables `NEXT_PUBLIC_*` sont fournies au build) |
| API FastAPI | `https://api.chimeraflow.linguasolution.com` | VPS Hetzner, compose Dokploy `chimeraflow-api` (`docker-compose.prod.yml`), TLS Let's Encrypt par Traefik |
| Redis | Limitation de débit et compteur de dépense LLM | Même compose, réseau privé `internal`, volume `redis-data` |
| PostgreSQL | Règles, corrélations, exécutions | Neon (`DATABASE_URL`) |
| Configuration et secrets | Toutes les variables de l'API | Doppler, projet `chimeraflow`, config `prd` |

Le conteneur de l'API ne reçoit qu'une variable, `DOPPLER_TOKEN` (jeton de service en lecture seule). Au démarrage, `docker-entrypoint.sh` lance `doppler run`, applique les migrations (`alembic upgrade head`) puis démarre uvicorn. Si Doppler est injoignable ou le jeton invalide, le conteneur s'arrête au lieu de démarrer avec une configuration partielle.

Les noms `api.chimeraflow` et `chimeraflow` sont en DNS seul, sans proxy : le défi HTTP-01 de Let's Encrypt et l'adresse IP cliente de la limitation de débit en dépendent.

## Branches et déploiement

`main` est la production et n'accepte que des PR depuis `dev` (CI verte obligatoire : « Backend lint and tests », « Backend Docker test stage », « Alembic migrations on PostgreSQL »).

1. Fusionner la PR `dev` → `main` (squash).
2. **Frontend** : Vercel déploie `main` en production (branche de production du projet). Vérifier dans Vercel, onglet Deployments, que le déploiement est « Ready ».
3. **API** : le compose Dokploy `chimeraflow-api` suit la branche `main`. Dokploy → projet ChimeraFlow → `chimeraflow-api` → **Deploy** (reconstruit l'image depuis `main` et redémarre). Le déploiement automatique (`autoDeploy`) est désactivé : il serait à activer après un premier déploiement vérifié depuis `main`, via le webhook de l'application GitHub liée à Dokploy (onglet Deployments du compose).
4. Contrôler avec le test de fumée (voir plus bas).

Avant une fusion qui ajoute une variable obligatoire à `backend/config.py`, la créer d'abord dans Doppler (`chimeraflow/prd`) : l'API ne démarre pas si une variable obligatoire manque.

## Tests de fumée

Le script `scripts/ops/smoke-prod.sh` (Linux, macOS, WSL ; exige `curl` et `jq`) et `scripts/ops/smoke-prod.ps1` (PowerShell 7 et Windows PowerShell 5.1) vérifient la production avec le compte de démonstration public : santé, `/docs` absent (404), `/api/v1/sources` refusé sans jeton (401), connexion, `/auth/me`, quatre sources en bon état, cinq règles prédéfinies, exécution des corrélations sans règle en échec, liste des corrélations, préflight CORS accepté pour le frontend et refusé pour une autre origine. Le jeton n'est jamais affiché ; le code de sortie est non nul au premier échec constaté.

Les identifiants sont lus dans l'environnement (`SMOKE_EMAIL`, `SMOKE_PASSWORD`), jamais écrits dans le dépôt. Ils sont publics par construction : ce sont les valeurs `NEXT_PUBLIC_DEMO_LOGIN_*` de Doppler.

```powershell
$env:SMOKE_EMAIL = '<email de démonstration>'
$env:SMOKE_PASSWORD = '<mot de passe de démonstration>'
./scripts/ops/smoke-prod.ps1
```

Depuis GitHub : Actions → **Production smoke** → Run workflow. Le workflow lit les secrets de dépôt `SMOKE_EMAIL` et `SMOKE_PASSWORD`. Pour les recréer : lire les deux valeurs dans Doppler (`doppler secrets get NEXT_PUBLIC_DEMO_LOGIN_EMAIL NEXT_PUBLIC_DEMO_LOGIN_PASSWORD --plain`) puis `gh secret set SMOKE_EMAIL` et `gh secret set SMOKE_PASSWORD`.

L'exécution des corrélations remplace celles des règles actives : lancer le test de fumée est sans effet durable sur les données.

## Surveillance de disponibilité

Le workflow `.github/workflows/uptime.yml` s'exécute toutes les 30 minutes (et à la demande) : `GET /health` de l'API (HTTP 200 et `status` égal à `ok`) et `GET /login` du frontend (HTTP 200), avec trois essais espacés de 10 secondes pour ignorer une coupure brève.

- En cas d'échec, un unique ticket GitHub « Production is down », étiqueté `uptime`, est ouvert. Tant que la panne dure, chaque exécution y ajoute un commentaire au lieu d'ouvrir un nouveau ticket.
- Au retour à la normale, le ticket est commenté puis fermé.
- Les exécutions planifiées ne se lancent que depuis la branche par défaut (`dev`). GitHub désactive les workflows planifiés après 60 jours sans activité dans un dépôt : un `workflow_dispatch` ou un commit les réactive.

Pour être prévenu, activer les notifications GitHub du dépôt pour les tickets.

## Renouveler le jeton Doppler

Le jeton de service de l'API est en lecture seule sur `chimeraflow/prd`. Renouveler après toute fuite supposée, et régulièrement.

1. Créer un nouveau jeton de service en lecture seule : tableau de bord Doppler, projet `chimeraflow`, config `prd`, Access, Service Tokens (ou `doppler configs tokens create`, avec l'accès `read`). Le copier une seule fois.
2. Dokploy → `chimeraflow-api` → onglet Environment : remplacer `DOPPLER_TOKEN`, enregistrer, puis **Deploy**. Le service Redis lit son mot de passe via le même jeton : les deux conteneurs sont recréés par le déploiement.
3. Lancer le test de fumée.
4. Révoquer l'ancien jeton dans Doppler (Service Tokens, Revoke), seulement après la vérification.
5. Mettre à jour la copie locale dans `.env` à la racine (jamais versionné) si elle sert à l'administration.

Changer `AUTH_TOKEN_SECRET` dans Doppler est un autre geste : il invalide toutes les sessions ouvertes (les utilisateurs se reconnectent).

## Retour arrière

**API.** Le compose se reconstruit depuis la branche `main` : il n'y a pas d'image précédente à rappeler. Le retour arrière passe par git.

1. Sur `dev`, `git revert <commit fautif>` (jamais de réécriture d'historique), pousser, ouvrir ou mettre à jour la PR `dev` → `main`, attendre la CI verte, fusionner.
2. Redéployer le compose dans Dokploy.
3. Lancer le test de fumée.

Les migrations Alembic s'appliquent au démarrage mais ne sont pas annulées automatiquement. Si le commit fautif ajoutait une migration, écrire d'abord une migration inverse (ou lancer `alembic downgrade -1` dans le conteneur de l'API, après une copie de sauvegarde Neon) avant de redéployer l'ancien code.

**Frontend.** Vercel → projet `chimeraflow` → Deployments → ouvrir le dernier déploiement sain → menu `…` → **Promote to Production** (ou `vercel promote <url du déploiement>`). C'est immédiat et ne demande aucun commit.

## Anomalies fréquentes

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| Le ticket `uptime` s'ouvre, `/health` répond 502 ou 504 | Conteneur arrêté ou en redémarrage (variable obligatoire manquante, Doppler injoignable) | Dokploy → Logs du service `api` ; corriger la variable dans Doppler, redéployer |
| `/health` répond 200 mais le test de fumée échoue à la connexion (401) | `DEMO_LOGIN_*` modifiés dans Doppler sans mettre à jour `NEXT_PUBLIC_DEMO_LOGIN_*` ni les secrets `SMOKE_*` | Réaligner les valeurs, redéployer le frontend |
| Le test de fumée échoue sur le CORS | `CORS_ORIGINS` de Doppler ne contient pas l'origine du frontend | Corriger dans Doppler, redéployer l'API |
| Le test de fumée échoue sur 429 | Limitation de débit atteinte depuis cette IP | Attendre la fin de la fenêtre (`RATE_LIMIT_WINDOW_SECONDS`) |
