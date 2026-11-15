# Documentation ChimeraFlow

Bienvenue dans le centre de documentation de ChimeraFlow.

---

## 📚 Structure

### [decisions/](./decisions/)
Décisions d'architecture et dette technique.

- **[DECISIONS_LOG.md](./decisions/DECISIONS_LOG.md)** : journal chronologique des décisions techniques et d'architecture (les plus récentes en haut)
- **[TECH_DEBT.md](./decisions/TECH_DEBT.md)** : dette technique identifiée, avec impact et fichiers concernés
- **[P2_ACTION_PLAN.md](./decisions/P2_ACTION_PLAN.md)** : plan pour clore la P1 et démarrer la P2
- **[p1-completion-qcm.html](./decisions/p1-completion-qcm.html)** : questionnaire interactif de clôture de la P1
- **[p2-decisions-qcm.html](./decisions/p2-decisions-qcm.html)** : questionnaire de décisions P2
- **[chimeraflow-decisions-qcm.html](./decisions/chimeraflow-decisions-qcm.html)** : questionnaire de décisions du projet
- **[build-log.md](./build-log.md)** : journal de bord quotidien

### [deployment/](./deployment/)
- **[P0-setup.md](./deployment/P0-setup.md)** : installation locale, Docker Compose et vérifications de la phase P0

### [specs/](./specs/)
Vide pour l'instant (`.gitkeep`). Les spécifications Kiro sont dans **[`../.kiro/specs/`](../.kiro/specs/)** :
- `connectors-spec.md`, `rule-engine-spec.md`, `ui-spec.md` : specs des phases P0 et P1
- `api-spec.md` : endpoints de l'API FastAPI
- `design.md` : architecture implémentée et propriétés de correction P1 à P6
- `tasks.md` : avancement par phase

### [design/](./design/)
Documents de design, maquettes et éléments visuels. Vide pour l'instant (`.gitkeep`) : le système de design est dans [`../DESIGN.md`](../DESIGN.md).

### [architecture/](./architecture/)
Diagrammes et documents d'architecture système. Vide pour l'instant (`.gitkeep`). L'architecture implémentée est décrite dans [`../.kiro/specs/design.md`](../.kiro/specs/design.md).

### [reference/](./reference/)
Références techniques et bonnes pratiques. Vide pour l'instant (`.gitkeep`).

---

## 🚀 Liens rapides

- **[README principal](../README.md)** : présentation et démarrage rapide
- **[AGENTS.md](../AGENTS.md)** : règles de développement pour les agents IA
- **[DESIGN.md](../DESIGN.md)** : système de design
- **[Roadmap.md](../Roadmap.md)** : plan produit

---

## 📝 Contribuer à la documentation

Pour ajouter un document :

1. Le ranger dans le dossier qui correspond à son sujet
2. Ajouter un lien dans ce fichier
3. Écrire en français clair et concis (la documentation utilisateur est en français, AGENTS.md §6)
4. Inclure des exemples quand ils aident
5. Garder un Markdown cohérent

---

_Dernière mise à jour : 2026-11-14_
