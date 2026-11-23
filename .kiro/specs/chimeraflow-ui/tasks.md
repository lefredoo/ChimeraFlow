# Tâches : interface ChimeraFlow
Exigences : `requirements.md`. Conception : `design.md`. Plan général et autres phases : `../chimeraflow-backend/tasks.md`.
Légende : `[x]` fait et vérifié dans le dépôt ; `[~]` partiel ; `[ ]` à faire.
---
## P3 : Interface (25–29 nov.) — interface livrée (Crew abandonné)

- [x] Tableau de bord mobile-first : état des 4 sources, statistiques, bouton « Exécuter les règles », dernières corrélations (`frontend/components/dashboard.tsx`)
- [x] Composeur de règles en langage naturel, avec aperçu du brouillon et repli sur les règles prédéfinies (`rule-composer.tsx`)
- [x] Liste des règles avec détail JSON et suppression confirmée (`rules-view.tsx`)
- [x] Cartes de corrélation avec badges par source et tiroir de provenance (R10)
- [x] Assainissement des textes de source avant affichage (R12) : rendu en texte React seulement, jamais de HTML ; testé (`correlation-card.test.tsx`)
- [x] État dégradé quand une source est absente (R8) : bandeau et fil coupé sur le tableau de bord
- [x] Mise en page utilisable à 360 px et au clavier, contraste WCAG AA (R11) : mesurée le 2026-11-17 dans Edge (axe-core, 0 violation, aucun débordement horizontal à 360 px, clavier et boîtes de dialogue vérifiés, thèmes clair et sombre) ; lecteur d'écran réel, Firefox, Safari et téléphone non couverts (voir `design.md` et TECH_DEBT)
- [x] Bascule FR/EN mémorisée et thème sombre (système par défaut, choix mémorisé)
- [x] Vue « pourquoi ça correspond » (affichée seulement quand la corrélation a une `explanation`), bac à sable de normalisation (`/sandbox`), corrélations en temps réel (flux SSE, sinon actualisation toutes les 15 s)
- [x] Corrections issues de l'audit navigateur du 2026-11-17 et test du formulaire de connexion (jsdom : identifiants, connexion en un clic, erreur annoncée) (`login-form.test.tsx`)
- [x] Connecteur n°4 (Mobile Money) : écrit avec Kiro IDE et Kiro CLI, sans Crew (voir `DECISIONS_LOG.md`)
- [ ] Hook `rule-validate` : déjà présent (`.kiro/hooks/rule-validate.json`, cible `data/rules/*.json`) ; l'agent qu'il lance reste à valider en session
