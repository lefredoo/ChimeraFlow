# ChimeraFlow

> Relier Excel, Access, WhatsApp et Mobile Money en une seule vue corrélée, avec des règles écrites en français ou en anglais.

**Projet du Kiroween 2026 Hackathon** | Catégorie : Frankenstein | Projet solo | Licence MIT

**Démonstration en ligne : https://chimeraflow.linguasolution.com**

---

## Sommaire

- [Qu'est-ce que ChimeraFlow ?](#quest-ce-que-chimeraflow-)
- [Essayer la démonstration](#essayer-la-démonstration)
- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Usage de Kiro](#usage-de-kiro)
- [Démarrage rapide en local](#démarrage-rapide-en-local)
- [Tests et intégration continue](#tests-et-intégration-continue)
- [Sécurité](#sécurité)
- [Avancement](#avancement)
- [Structure du dépôt](#structure-du-dépôt)
- [Documentation](#documentation)
- [Contribuer, licence, contact](#contribuer)

---

## Qu'est-ce que ChimeraFlow ?

Les petites entreprises ne travaillent pas avec des API. Elles travaillent avec des **tableurs Excel**, des **bases Access** et des **groupes WhatsApp**. ChimeraFlow lit ces sources, ramène chaque ligne à un même format, puis applique des règles de corrélation (« quand un client demande un produit sur WhatsApp, montre son stock et son prix »).

**Scénario de démonstration :** une quincaillerie fictive, ZOBO (Douala, Cameroun). Toutes les données sont synthétiques.

| Source | Fichier | Contenu |
|--------|---------|---------|
| Access | `data/STOCK_ZOBO.mdb` | Stock hérité, table `Articles` |
| Excel | `data/tarifs_fournisseurs.xlsx` | Tarifs fournisseurs, feuille `Tarifs`, mise en forme imparfaite, accents manquants |
| WhatsApp | `data/commandes_clients.txt` | Groupe de commandes, mélange de français et d'anglais, abréviations |
| Mobile Money | `data/momo_transactions.csv` | Confirmations de paiement |

**Le point difficile :** un même produit s'écrit de plusieurs façons (`ciment 50 kg`, `Ciment50kg`, `cimént 50kg`, `ciment (50kg)`). La normalisation les ramène à la même clé (`ciment 50 kg`) sans jamais corriger les nombres : `ciment 50 kg` ne correspond pas à `ciment 40 kg`.

---

## Essayer la démonstration

| | Adresse |
|---|---------|
| Application | https://chimeraflow.linguasolution.com |
| API | https://chimeraflow-api.linguasolution.com (`/health` est public ; `/docs` n'est pas servi en production) |

1. Ouvrir l'application : elle redirige vers la page de connexion.
2. Cliquer sur **« Entrer dans la démo »** (connexion en un clic). Le bouton **« Voir les identifiants »** affiche le compte de démonstration, qui est public et ne donne accès qu'à des données synthétiques.
3. Sur le tableau de bord, cliquer sur **« Exécuter les règles »** : les corrélations apparaissent sous forme de cartes, avec leur provenance et la vue « Pourquoi ça correspond ».
4. Essayer le bac à sable de normalisation (`/sandbox`) et le composeur de règles (`/rules/new`).

Le bouton de réinitialisation du tableau de bord remet les données de démonstration dans leur état initial.

---

## Fonctionnalités

**Sources et enregistrement unifié**
- Quatre connecteurs : Excel (pandas, openpyxl), Access (`mdbtools` en Docker, `access-parser` en Python pur sous Windows), WhatsApp (export Android), Mobile Money (CSV).
- Chaque ligne devient un enregistrement unifié (`source`, `source_ref`, `timestamp`, `lang`, `entities`, `payload`). Une ligne illisible est ignorée et comptée, jamais inventée.

**Normalisation**
- Casse, accents, ponctuation et espaces ; nombres conservés ; synonymes FR/EN.
- Correspondance par distance de Levenshtein (seuil 0,85) et par inclusion de mots pour les noms partiels (« tuyau PVC » dans « Tuyau PVC Ø 32mm (barre 6m) »). Une garde numérique empêche de rapprocher deux quantités différentes.

**Règles déclaratives**
- Règles en JSON validé par Pydantic. Aucun code n'est exécuté, ni écrit par le modèle, ni stocké.
- Opérateurs en liste blanche : `eq`, `ne`, `lt`, `lte`, `gt`, `gte`, `contains`, `in`.
- Conditions sur le déclencheur (`trigger.where`) et comparaisons calculées (`ref` avec `tolerance_pct`, par exemple « prix fournisseur supérieur de plus de 10 % au prix d'achat »).
- Cinq règles prédéfinies (`data/rules/`), toutes actives. Chacune produit au moins une corrélation sur les données livrées (testé dans `test_scenario_data.py`).

| Règle | Déclencheur | Objet |
|-------|-------------|-------|
| `r_low_stock` | WhatsApp | Montrer le stock Access et le prix Excel d'un produit demandé, alerter si le stock est inférieur à 10 |
| `r_high_value_order` | WhatsApp | Alerter quand une commande concerne un produit dont le prix dépasse 10 000 FCFA |
| `r_payment_received` | Mobile Money | Rapprocher un paiement `SUCCESS` d'une commande WhatsApp récente |
| `r_price_comparison` | Access | Détecter un écart de plus de 10 % entre prix d'achat et tarif fournisseur |
| `r_stock_replenish` | Access | Recommander un réapprovisionnement quand le stock est inférieur à 15 et qu'il y a des commandes récentes |

**Explication et provenance**
- Chaque corrélation liste les enregistrements source qui l'ont produite.
- La vue « Pourquoi ça correspond » détaille le nom comparé, le score, la méthode et les valeurs des conditions.
- Les textes venus des sources sont affichés en texte seul, jamais en HTML.

**Règle en langage naturel**
- `POST /api/v1/rules/from-text` convertit une phrase en **brouillon** de règle via un proxy LiteLLM : prompt qui sépare instructions et texte utilisateur, validation stricte, 2 relances au plus, budget plafonné suivi dans Redis, repli sur les règles prédéfinies si la conversion échoue. Le brouillon n'est pas stocké avant validation par l'utilisateur.
- **État réel :** le pipeline est testé avec un LiteLLM simulé. Le modèle de production est en cours de changement : la conversion n'est pas à considérer comme fonctionnelle sur la démonstration en ligne.

**Interface**
- Tableau de bord, liste des règles, composeur, cartes de corrélation, bac à sable de normalisation.
- Corrélations en temps réel (flux SSE, avec actualisation périodique en repli).
- Alerte par e-mail (Cloudflare Email Service) : un récapitulatif des nouvelles corrélations `warning` et `error` par exécution, avec un délai minimal entre deux e-mails. Elle n'est active que si sa configuration est complète.
- Interface en français et en anglais, thème sombre, éléments accessibles au clavier, mise en page pensée pour 360 px.

---

## Architecture

```
Navigateur ──► Frontend Next.js 15 (Vercel)
                    │  HTTPS, jeton Bearer
                    ▼
        Tunnel Cloudflare ──► Traefik ──► API FastAPI (VPS Hetzner, Dokploy)
                                              │        │
                                              │        └──► Redis (limitation par IP, budget LLM, délai des alertes)
                                              ├──► PostgreSQL (Neon) : règles, corrélations, exécutions
                                              ├──► Fichiers de données synthétiques (lecture seule)
                                              ├──► Proxy LiteLLM : conversion langage naturel → règle
                                              └──► Cloudflare Email Service : alertes
```

| Élément | Technologie | Hébergement |
|---------|-------------|-------------|
| Frontend | Next.js 15 (App Router), TypeScript strict | Vercel |
| API | FastAPI, SQLAlchemy, Alembic, Python 3.13 | VPS Hetzner, Dokploy (`docker-compose.prod.yml` : API et Redis) |
| Base de données | PostgreSQL | Neon |
| Cache et compteurs | Redis | Même compose que l'API, réseau privé |
| Secrets | Doppler | Les conteneurs ne reçoivent que `DOPPLER_TOKEN` |
| Accès à l'API | Tunnel Cloudflare puis Traefik | Les ports 80 et 443 du VPS restent fermés |

Détail de l'exploitation (déploiement, retour arrière, surveillance) : [docs/deployment/PRODUCTION.md](./docs/deployment/PRODUCTION.md). Architecture du backend : [.kiro/specs/design.md](./.kiro/specs/design.md).

---

## Usage de Kiro

Ce que le dépôt contient de la configuration Kiro :

- **Specs** (`.kiro/specs/`) : `connectors-spec.md`, `rule-engine-spec.md`, `ui-spec.md`, `api-spec.md`, `design.md` (architecture réelle et propriétés de correction P1 à P6) et `tasks.md` (avancement par phase).
- **Steering** (`.kiro/steering/`) : `connectors.md` (conventions des connecteurs) et `security.md` (règles de sécurité).
- **Hooks** (`.kiro/hooks/`) : `parser-test` (tests de contrat et tests de propriétés à la sauvegarde d'un connecteur), `rule-validate` (validation des fichiers de `data/rules/`), `spec-update-reminder` (rappel de mise à jour de `tasks.md`).
- **Serveurs MCP** : chaque source est exposée en serveur MCP stdio (`chimeraflow-excel`, `chimeraflow-access`, `chimeraflow-whatsapp`, `chimeraflow-momo`), déclarés dans `.kiro/settings/mcp.json`. Outils en lecture seule : `fetch_records(limit)` et `health_check()`. Dans Kiro, demander par exemple « appelle `health_check` du serveur chimeraflow-excel ».
- **Tests basés sur les propriétés** (Hypothesis), statuts d'après `.kiro/specs/design.md` §12 :

| Propriété | Énoncé | Statut |
|-----------|--------|--------|
| P1 Provenance | Une corrélation ne cite que des enregistrements d'entrée | couverte (interpréteur) |
| P2 Idempotence | `norm(norm(x)) == norm(x)` | couverte |
| P3 Aller-retour | `parse(export(m)) == m` | non couverte |
| P4 Déterminisme | Mêmes entrées, même sortie | couverte |
| P5 Monotonie | Élargir la fenêtre ne retire aucune corrélation | couverte |
| P6 Pas de fabrication | Aucune valeur émise absente des sources | partielle |

- **Outils Kiro utilisés** : Kiro IDE et Kiro CLI. Kiro Crew n'est pas utilisé.

---

## Démarrage rapide en local

### Prérequis
- Python 3.13 et [uv](https://docs.astral.sh/uv/)
- Node.js 18.18 ou plus récent (la CI utilise Node 22)
- Docker (suite de tests complète avec mdbtools, Redis)
- Doppler CLI (facultatif)

### 1. Cloner

```powershell
git clone https://github.com/lefredoo/ChimeraFlow.git
cd ChimeraFlow
```

Les quatre fichiers de données sont déjà dans `data/`. Pour les régénérer :

```powershell
python scripts/generate_excel.py          # requiert pandas et openpyxl
python scripts/generate_whatsapp.py
python scripts/generate_momo.py           # déterministe : même sortie à chaque exécution
cscript //Nologo scripts/generate_access_windows.vbs   # Windows avec Access uniquement
```

### 2. Installer le backend

```powershell
cd backend
uv venv --python 3.13 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-dev.txt
```

### 3. Configurer l'environnement

Il n'existe **pas de `.env.example`**. Le backend lit uniquement des variables d'environnement. La liste complète, obligatoires et facultatives, est dans [AGENTS.md §22](./AGENTS.md) et dans [backend/README.md](./backend/README.md). Une variable obligatoire absente arrête l'application au démarrage, c'est voulu.

En local, exporter les variables dans le shell, par exemple :

```powershell
$env:DATABASE_URL = "postgresql://user:pass@host/dbname"
$env:CORS_ORIGINS = "http://localhost:3000"
$env:DATA_DIR = "../data"
$env:ACCESS_READER = "access-parser"              # Windows : pas de mdbtools
$env:REDIS_URL = "redis://localhost:6379/0"
$env:RATE_LIMIT_PER_IP = "10"
$env:RATE_LIMIT_WINDOW_SECONDS = "60"
$env:AUTH_TOKEN_SECRET = "<au moins 32 caractères aléatoires>"
$env:DEMO_LOGIN_EMAIL = "demo@example.com"
$env:DEMO_LOGIN_PASSWORD_HASH = "<sortie de : python -m auth.hash_password>"
```

La conversion en langage naturel et l'alerte e-mail restent désactivées tant que leurs variables ne sont pas toutes définies.

### 4. Créer le schéma et lancer l'API

```powershell
cd backend
.venv\Scripts\python.exe -m alembic upgrade head
$env:BACKEND_NODE_ENV = "development"      # nécessaire pour servir /docs
.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000
```

- Documentation interactive : http://localhost:8000/docs (seulement hors production)
- Santé : http://localhost:8000/health

Tous les endpoints `/api/v1` exigent un jeton Bearer, obtenu par `POST /api/v1/auth/login`.

### 5. Lancer le frontend

```powershell
cd frontend
npm install
npm run dev     # http://localhost:3000
```

Le frontend exige `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_DEMO_LOGIN_EMAIL` et `NEXT_PUBLIC_DEMO_LOGIN_PASSWORD` au build. Le compte de démonstration est public par construction : la page `/login` l'affiche.

### Docker Compose (local)

```powershell
docker compose up -d
```

`docker-compose.yml` démarre l'API (port 8000) et Redis (sans port publié). Il exige notamment `DATABASE_URL`, `REDIS_PASSWORD`, `AUTH_TOKEN_SECRET`, `DEMO_LOGIN_EMAIL` et `DEMO_LOGIN_PASSWORD_HASH` (liste complète dans `backend/README.md`). L'API applique les migrations avant de servir les requêtes.

### Utiliser les serveurs MCP dans Kiro

Ouvrir le dépôt dans Kiro après l'étape 2 : `.kiro/settings/mcp.json` lance `backend/mcp_main.py --source <nom>` avec le Python du venv Windows (`backend/.venv/Scripts/python.exe`). Sous Linux ou macOS, adapter le chemin vers `backend/.venv/bin/python`. Détail : section « Serveurs MCP » de [backend/README.md](./backend/README.md).

---

## Tests et intégration continue

Depuis `backend/` :

```powershell
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe -m ruff check .
```

Depuis `frontend/` : `npx tsc --noEmit`, `npm run lint`, `npm test`, `npm run build`.

Suite complète avec mdbtools, depuis la racine du dépôt :

```powershell
docker build --target test -t chimeraflow-backend-test backend; docker run --rm -v "${PWD}/data:/data:ro" chimeraflow-backend-test
```

**Derniers résultats vérifiés :**

| Suite | Résultat |
|-------|----------|
| Backend, en local sous Windows | environ 603 tests, dont 3 sautés sans mdbtools |
| Backend, étage Docker de test | aucun test sauté |
| Frontend (Vitest) | 178 tests |

**CI GitHub Actions** (`.github/workflows/ci.yml`), cinq jobs : lint et tests du backend ; étage Docker de test ; migrations Alembic sur PostgreSQL (montée, vérification de dérive, descente) ; lint, tests et build du frontend ; scan de secrets (gitleaks) sur tout l'historique.

**Exploitation :**
- `uptime.yml` : contrôle de `/health` et de `/login` toutes les 30 minutes une fois activé (variable de dépôt `UPTIME_SCHEDULE_ENABLED`), avec ticket GitHub en cas de panne.
- `smoke-prod.yml` : test de fumée de la production, lancé à la demande (scripts dans `scripts/ops/`).

Détail des tests : [backend/tests/README.md](./backend/tests/README.md).

---

## Sécurité

- Authentification par jeton Bearer sur tous les endpoints `/api/v1`, sauf la connexion. Le jeton expire après 1 heure.
- Limitation de débit par IP sur les mutations, la connexion et la conversion en langage naturel (Redis).
- Aucun code généré n'est exécuté : les règles sont du JSON validé par un schéma strict, avec une liste blanche d'opérateurs et de colonnes.
- Texte des sources traité comme non fiable : séparation instructions et données dans le prompt, sortie du modèle validée, affichage en texte seul.
- Données 100 % synthétiques, montées en lecture seule.
- Secrets uniquement dans Doppler, jamais dans le code. Scan de secrets (gitleaks) à chaque exécution de la CI.
- `/docs` n'est pas servi en production. CORS en liste blanche.

Limites connues, avec leur impact : [docs/decisions/TECH_DEBT.md](./docs/decisions/TECH_DEBT.md). Parmi elles : un seul compte de démonstration partagé et public, un parseur WhatsApp limité au format Android, et une alerte e-mail jamais envoyée à un vrai Cloudflare Email Service.

---

## Avancement

État au 2026-11-17. Détail case par case : [.kiro/specs/tasks.md](./.kiro/specs/tasks.md).

| Phase | Statut | Contenu |
|-------|--------|---------|
| P0 Fondations | terminée | Structure, specs, steering, données synthétiques, déploiement Vercel et VPS |
| P1 Connecteurs | terminée | Quatre connecteurs, enregistrement unifié, tests de contrat, serveurs MCP stdio |
| P2 Moteur de règles | terminée, sauf conversion en réel | Normaliseur, interpréteur avec provenance, cinq règles actives, API, migrations, limitation par IP, budget LLM. Reste : brancher et mesurer un vrai modèle LiteLLM |
| P3 Interface | interface livrée | Tableau de bord, composeur, corrélations, bac à sable, temps réel, FR/EN, thème sombre |
| P4 Durcissement | en grande partie faite | Authentification, tests de fumée, surveillance, scan de secrets, documentation. Reste : mesures d'accessibilité dans un navigateur, gel du code |
| P5 Soumission | à faire | Vidéo, write-up, blog, formulaire Devpost |

**Vidéo de démonstration :** à publier en P5.

---

## Structure du dépôt

```
.
├── backend/                  # API FastAPI (Python 3.13)
│   ├── main.py               # application FastAPI
│   ├── config.py             # variables d'environnement (échec au démarrage si absentes)
│   ├── api/                  # routeurs : auth, sources, rules, correlations, flux SSE, normalize, demo
│   ├── auth/                 # hachage scrypt et jetons signés
│   ├── engine/               # normaliseur, interpréteur, règles prédéfinies, NL→règle, budget, alertes
│   ├── mcp_servers/          # connecteurs et serveurs MCP (Excel, Access, WhatsApp, Mobile Money)
│   ├── models/               # modèles SQLAlchemy et seed des règles
│   ├── schemas/              # schémas Pydantic
│   ├── migrations/           # migrations Alembic
│   ├── tests/                # suite de tests
│   └── Dockerfile            # cibles base, test et runtime
├── frontend/                 # Next.js 15 (App Router)
│   ├── app/                  # pages : connexion, tableau de bord, règles, corrélations, bac à sable
│   ├── components/, hooks/, lib/
│   └── messages/             # textes FR et EN
├── data/                     # données synthétiques et règles prédéfinies (rules/)
├── scripts/                  # générateurs de données ; ops/ : tests de fumée de la production
├── ops/vps/                  # garde-fou de configuration Traefik sur le VPS
├── docs/                     # décisions, dette technique, déploiement, journal
├── .kiro/                    # specs, steering, hooks, settings/mcp.json
├── .github/workflows/        # ci.yml, uptime.yml, smoke-prod.yml
├── docker-compose.yml        # local : API et Redis
├── docker-compose.prod.yml   # production (Dokploy) : API et Redis
├── AGENTS.md                 # règles de développement pour les agents IA
├── DESIGN.md                 # système de design
├── Roadmap.md                # plan produit
└── LICENSE                   # MIT, LinguaSolution LLC
```

---

## Documentation

- [AGENTS.md](./AGENTS.md) : règles de développement et variables d'environnement (en anglais)
- [backend/README.md](./backend/README.md) : endpoints, configuration, authentification, serveurs MCP
- [.kiro/specs/](./.kiro/specs/) : specs, conception (P1 à P6), plan par phase
- [docs/deployment/PRODUCTION.md](./docs/deployment/PRODUCTION.md) : production, déploiement, exploitation
- [ops/vps/README.md](./ops/vps/README.md) : garde-fou Traefik
- [docs/decisions/DECISIONS_LOG.md](./docs/decisions/DECISIONS_LOG.md) : décisions d'architecture
- [docs/decisions/TECH_DEBT.md](./docs/decisions/TECH_DEBT.md) : dette technique
- [DESIGN.md](./DESIGN.md) : système de design (effet verre, bleu `#2563eb`, IBM Plex)
- [Roadmap.md](./Roadmap.md) : plan produit

---

## À propos de LinguaSolution LLC

ChimeraFlow est développé par LinguaSolution LLC, à partir de son expertise en normalisation linguistique et en traitement du langage naturel sur des données multilingues et non structurées. Les mêmes techniques servent ici à corréler des données d'entreprise désordonnées.

---

## Contribuer

Ce projet a été réalisé pour le Kiroween 2026 Hackathon. Les contributions pendant la période de jugement (jusqu'au 29 janvier 2027) peuvent affecter l'éligibilité.

1. Travailler sur la branche `dev`, jamais directement sur `main`.
2. Suivre les [Conventional Commits](https://www.conventionalcommits.org/) (messages en anglais).
3. Lire `AGENTS.md` pour les conventions de code.
4. Noter les décisions dans `docs/decisions/DECISIONS_LOG.md`.

---

## Licence

Licence MIT, voir le fichier [LICENSE](./LICENSE).

Copyright (c) 2026 LinguaSolution LLC

---

## Contact

**Fondateur :** Fredy Zobo
**Organisation :** LinguaSolution LLC
**GitHub :** [@lefredoo](https://github.com/lefredoo)
**Hackathon :** Kiroween 2026

---

**Construit à Yaoundé, Cameroun | Propulsé par Kiro**
