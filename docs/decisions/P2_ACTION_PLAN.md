# CHIMERAFLOW — PLAN D'ACTION P1 → P2
Généré le : 13/11/2026 21:35:50

============================================================

## 1. RÉSOLUTION BLOQUEURS P1

- [x] IMMÉDIAT : pip install -r backend/requirements.txt
  Puis lancer : python -m pytest backend/tests/ -v

- [x] IMMÉDIAT : python scripts/generate_excel.py
  Vérifie que data/tarifs_fournisseurs.xlsx est créé

- [x] Access : créer manuellement sur Windows


## 2. CONFIGURATION P2

- [ ] Base de données : PostgreSQL sur Neon
  1. Créer DB sur neon.tech
  2. Ajouter DATABASE_URL dans Doppler
  3. Configurer SQLAlchemy + Alembic

Stratégie NL→JSON :
  - [ ] Implémenter conversion LiteLLM
  - [ ] Validation Pydantic stricte
  - [ ] 2 retries max
  - [ ] Fallback règles prédéfinies

Normalisation : approche hybride (règles + fuzzy + synonymes)


## 3. SCOPE P2 (20h)

Features incluses :
  - [x] Interpréteur de règles JSON
  - [x] Corrélation multi-sources
  - [x] Fenêtre temporelle
  - [x] 5 règles prédéfinies (3 inactives en attente d'une décision DSL, voir TECH_DEBT.md)
  - [x] API REST (/rules, /correlations)
  - [ ] Rate limiting


## 4. GIT & DÉPLOIEMENT

- [ ] Ouvrir PR dev → main immédiatement

- [ ] Déployer backend maintenant (Vercel + Hetzner)


## 5. PRIORITÉS IMMÉDIATES

1. Installer dépendances + tests
2. Générer Excel et Access
3. Configurer base de données
4. Démarrer interpréteur P2
5. Déployer backend P1
6. Ouvrir PR dev → main
