# Spécification de l'interface

Interface mobile-first en verre dépoli (glassmorphism), en français par défaut, en anglais au choix.
Code dans `frontend/` (Next.js 15, App Router, TypeScript strict). Jetons de design dans
`frontend/app/globals.css` (voir `DESIGN.md`), classes d'écran dans `frontend/app/components.css`.

## Exigences

- **R1 Tableau de bord** : état des 4 sources, statistiques, exécution des règles, dernières corrélations.
- **R2 Règles** : liste, détail JSON, suppression, composeur en langage naturel.
- **R3 Corrélations** : cartes avec badges par source, tiroir de provenance, horodatage et gravité.
- **R6 Accessibilité** : contraste WCAG AA, clavier, focus visible, rôles ARIA.
- **R7 Responsive** : 360 px minimum, 768 px, 1024 px et plus.
- **R8 État dégradé** : une source absente est signalée, les autres règles continuent.
- **R10 Provenance** : chaque corrélation montre source, référence dans la source et identifiant de l'enregistrement.
- **R12 Texte de source non fiable** : tout texte venu d'un fichier ou d'une conversation (message de corrélation, gabarit de règle, valeurs d'explication) est affiché comme texte React. Aucun `dangerouslySetInnerHTML`, aucun HTML interprété.

## Écrans implémentés (P3)

Toutes les pages, sauf `/login`, sont derrière `RequireAuth` et partagent la coque `AppPage` (lien d'évitement, navigation, langue, thème, compte).

| Route | Composant | Contenu |
|-------|-----------|---------|
| `/login` | `login-view.tsx`, `login-form.tsx` | Connexion, compte de démonstration, langue et thème |
| `/` | `dashboard.tsx` | Fil des sources (un fil coupé pour une source en panne), bandeau de mode dégradé, 4 cartes de santé (statut, nombre d'enregistrements, dernière lecture), statistiques, bouton « Exécuter les règles » avec résumé (règles exécutées et en échec, corrélations trouvées, durée), 5 dernières corrélations, réinitialisation de la démo, état de l'API |
| `/rules` | `rules-view.tsx` | Liste (badges actif/inactif/brouillon, prédéfinie/personnalisée, texte, sources rapprochées), tiroir de détail (description en clair et JSON en police mono), suppression avec confirmation |
| `/rules/new` | `rule-composer.tsx` | Zone de texte de 20 à 1000 caractères avec compteur, langue, brouillon (description en clair, JSON, nombre de relances), enregistrement, règles prédéfinies proposées quand la conversion est indisponible |
| `/correlations` | `correlations-view.tsx` | Cartes, filtres par gravité et par règle, indicateur de mise à jour en direct, tiroir de provenance, panneau « Pourquoi ça correspond » |
| `/sandbox` | `sandbox-view.tsx` | Normalisation d'un texte et score de correspondance avec d'autres noms, exemples (4 écritures du ciment, 50 kg contre 40 kg) |

### Carte de corrélation

Gravité (icône et texte), identifiant de règle, temps relatif (`Intl.RelativeTimeFormat`, date complète dans l'infobulle), message, fil de couture reliant les sources contributrices (badges Excel, Access, WhatsApp, Mobile Money : icône, couleur et nom), boutons « Provenance » et « Pourquoi ça correspond » (celui-ci seulement si la corrélation a une `explanation`).

### Pourquoi ça correspond

Quand `explanation` suit le format du moteur (`trigger` puis `joins`), le panneau l'écrit en phrases : entité du déclencheur et clé normalisée, candidat retenu pour chaque jointure avec la méthode (identique, synonyme, proche, mots communs) et le score, résultat de chaque condition (attendu, valeur trouvée, respectée ou non, écart relatif avec tolérance). Tout autre format est affiché en listes génériques.

### Temps réel

`GET /api/v1/correlations/stream` est lu avec `fetch` (l'en-tête Bearer ne passe pas par `EventSource`). Les événements `correlation` et `execution` déclenchent une relecture de la liste (une seule pour une rafale). Un flux qui se ferme est rouvert. Si le flux est absent (404, mauvais type de contenu, trop de flux ouverts), la liste est relue toutes les 15 s, onglet visible.

### Préférences

- Langue FR/EN : `localStorage` (`chimeraflow.locale`), `<html lang>` mis à jour. Les messages sont dans `frontend/messages/{fr,en}.json` ; pluriels par `Intl.PluralRules` (clés `.one` et `.other`), dates et nombres par `Intl`.
- Thème clair/sombre : `localStorage` (`chimeraflow.theme`), système par défaut, appliqué par `data-theme` sur `<html>`.
- Le jeton d'accès n'est jamais dans `localStorage` (voir `token-storage.ts`).

### Erreurs

Le client traduit le `code` stable de l'API (jamais son `message`) : `nl_feature_disabled`, `nl_budget_exceeded`, `nl_budget_unavailable`, `nl_provider_error`, `nl_conversion_failed`, `rate_limit_exceeded` (avec `Retry-After`), `rate_limit_unavailable`, `rule_already_exists`, `rule_not_found`, erreurs d'authentification. Réseau coupé et réponse inattendue ont leur message. Une réponse 401 renvoie à la page de connexion.

### Accessibilité

- Lien d'évitement, un seul `h1` par page, navigation avec `aria-current`.
- Tiroirs et confirmations : élément natif `<dialog>` (focus piégé, Échap, retour du focus).
- Zones `aria-live` pour les résultats asynchrones (exécution, brouillon, bac à sable, réinitialisation) et `role="alert"` pour les erreurs.
- Rien ne repose sur la couleur seule : badges de source (icône, couleur, nom), gravité (icône, texte), statuts (icône, texte).
- `prefers-reduced-motion` respecté, boutons activés par `aria-disabled` (focus conservé).

## Dépendances sur le backend

| Fonction de l'interface | Endpoint | Si absent |
|-------------------------|----------|-----------|
| Santé des sources | `GET /api/v1/sources`, `GET /api/v1/sources/all/records` | Erreur avec bouton Réessayer |
| Règles | `GET/POST/DELETE /api/v1/rules`, `GET /api/v1/rules/predefined` | Erreur avec bouton Réessayer |
| Composeur | `POST /api/v1/rules/from-text` | 503 `nl_feature_disabled` : message et règles prédéfinies proposées |
| Exécution et corrélations | `POST /api/v1/correlations/execute`, `GET /api/v1/correlations` | Erreur affichée |
| Pourquoi ça correspond | champ `explanation` des corrélations | Bouton absent |
| Bac à sable | `POST /api/v1/normalize` (`text`, `compare_with`) | 404 : état « indisponible » |
| Temps réel | `GET /api/v1/correlations/stream` | Relecture toutes les 15 s |
| Réinitialisation de la démo | `POST /api/v1/demo/reset` | 404 : message « pas encore disponible » |

## Tests

Logique pure testée avec Vitest (`frontend/lib/**/*.test.ts` : formats, pluriels, préférences, analyse des réponses, correspondance codes d'erreur et messages, filtres, résumés de règles, flux SSE, explication). Tests de composants avec Testing Library et jsdom : échappement du texte de source, panneau d'explication, tiroir de provenance, bac à sable, formulaire de connexion (identifiants masqués puis révélés avec `aria-expanded`, connexion en un clic, erreur annoncée dans la région `role="alert"`).

## Audit navigateur (2026-11-17)

Edge headless, axe-core (WCAG 2 A/AA, 2.1, 2.2 AA et bonnes pratiques) et Playwright, outils hors dépôt, API simulée par interception des requêtes. Pages : `/login` (y compris identifiants révélés et erreur), `/`, `/rules` (détail, suppression), `/rules/new` (brouillon), `/correlations` (tiroir, « Pourquoi ça correspond »), `/sandbox`, en thèmes clair et sombre, à 1280 px et 360 px.

- Aucune violation axe après correction. Corrigées : nom accessible des boutons FR/EN (le texte visible `FR` n'y figurait pas), ordre des titres de la liste des corrélations, `--text-muted` clair à 4,44:1 sur la fin du dégradé.
- Contraste vérifié aussi par calcul sur chaque texte (axe ignore les fonds en dégradé) : aucun texte sous 4,5:1 (3:1 pour le grand texte).
- 360 px : `scrollWidth` égal à 360 sur toutes les pages, boîtes de dialogue et brouillon compris.
- Clavier : tous les contrôles de `/login` et de `/rules` atteints dans l'ordre visuel, focus visible partout ; les boîtes de dialogue reçoivent le focus, le gardent, se ferment avec Échap et rendent le focus au bouton d'origine.
- Non couvert : lecteur d'écran réel, Firefox, Safari, appareil tactile.

## Hors périmètre

La page « Paramètres » de la première version de cette spécification (limites, budget LLM, intervalle d'actualisation) n'est pas implémentée : l'API n'expose ni budget ni état du limiteur. L'éditeur JSON (Monaco) n'est pas ajouté : le JSON est affiché en lecture seule, la modification passe par le composeur.
