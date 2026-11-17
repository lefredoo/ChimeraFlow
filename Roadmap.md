# ChimeraFlow — Roadmap v2 (Kiroween 2026)

Fredy · v2 · 13 nov. 2026 · Catégorie Frankenstein · Bonus visés : Best Startup Project, Blog, Social

Deadline officielle : **vendredi 4 déc. 2026, 14:00 PT = 22:00 UTC = 23:00 à Yaoundé**. Cible interne : soumission le **jeudi 3 déc.** (le 4 est une marge d'urgence, pas un plan).

## 1. Décisions et hypothèses

| Sujet | Décision / hypothèse |
| --- | --- |
| Capacité | Solo, ≥ 4 h/jour ≈ 84 h sur 21 jours |
| Catégorie | Frankenstein (angle PME africaine : Excel + Access + WhatsApp) |
| Bonus | Best Startup Project via LinguaSolution LLC, plus Blog et Social |
| Hébergement | Front Next.js sur Vercel ; backend sur le VPS Hetzner (Dokploy/Traefik déjà en place) |
| Données | Hypothèse : 100 % synthétiques (repo et démo publics : aucun vrai message ni numéro) |
| LLM runtime | Hypothèse : LiteLLM existant, clé virtuelle dédiée avec budget plafonné |
| Langue | Soumission 100 % en anglais ; les règles peuvent être saisies en français |
| Crédits Kiro | Acquis ; vérifier kiro.dev/account/usage chaque semaine |

**À trancher avant le 20 nov. :** candidater en individuel ou comme Organization (LinguaSolution LLC). La ligne de copyright du LICENSE, le propriétaire de l'IP et l'Entrant Devpost doivent désigner la même entité. Le versement du prix et les formulaires W-8 en dépendent : à faire valider par ton comptable.

## 2. Pitch et scénario de démo

**One-liner :** ChimeraFlow stitches the Excel sheets, Access databases and WhatsApp groups that small businesses actually run on into one correlated view. Rules are written in plain French or English.

Scénario fictif : une quincaillerie de Douala (nom inventé). Trois « organes » au départ :

- **Access** `STOCK.mdb` (legacy) : tables Articles et Mouvements.
- **Excel** tarifs fournisseur, volontairement imparfait (en-têtes fusionnés, accents manquants).
- **Export WhatsApp** du groupe « Commandes clients » (français, un peu d'anglais, abréviations).
- **4e organe, généré par Kiro Crew pendant la démo** : export CSV de SMS Mobile Money.

Règle de démo : « Quand un client demande un produit sur WhatsApp, montre son stock Access et son prix Excel, et alerte-moi si le stock est inférieur à 10. »

Cas piège volontaire : le même produit écrit de quatre façons (`ciment 50 kg`, `Ciment50kg`, `cimént 50kg`, `ciment (50kg)`). La normalisation doit les unifier, sinon la corrélation est fausse. C'est la démonstration concrète du lien avec le savoir-faire linguistique de LinguaSolution (champ `lang`, normalisation FR/EN), sans rien inventer.

## 3. Architecture v2

```
Vercel (Next.js, aucun secret)
   │ HTTPS + CORS allowlist
VPS Hetzner (Dokploy / Traefik, TLS)
   ├─ api   : FastAPI (règles, corrélation, SSE ou polling)
   ├─ mcp   : 4 serveurs MCP légers dans un seul conteneur
   ├─ LiteLLM existant (clé virtuelle dédiée + budget)
   └─ Redis existant (rate limiting)
Volume /data en lecture seule : STOCK_ZOBO.mdb, tarifs_fournisseurs.xlsx, commandes_clients.txt, momo_transactions.csv
```

Règles d'architecture :

- `mem_limit` sur chaque conteneur (hypothèse de départ : 384 Mo, 0,5 CPU). Mesurer avec `docker stats` à la fin de P1 pour ne pas surcharger le VPS.
- **Aucune exécution de code généré.** Le LLM produit une règle JSON validée ; l'interpréteur n'accepte qu'une liste blanche d'opérateurs.
- Budget LLM plafonné (hypothèse : 5 $ ≈ 3 300 FCFA, à ajuster) ; au-delà, repli sur les règles prédéfinies.
- Rate limit par IP sur la création de règles.
- Pas d'upload de fichiers utilisateur en démo publique (surface d'attaque) ; à mentionner comme suite possible.
- Tout texte issu d'une source est assaini avant affichage (XSS) et traité comme non fiable dans les prompts (prompt injection).
- Secrets via Doppler ; `.kiro/settings/mcp.json` ne contient que des références à des variables d'environnement.

## 4. Schémas

**Record unifié** (toutes les sources) :

```json
{"id":"wa-0412","source":"whatsapp","source_ref":"chat.txt#L412","timestamp":"2026-11-02T09:14:00+01:00","lang":"fr","entities":[{"type":"product","raw":"ciment 50 kg","norm":"ciment-50kg"}],"payload":{"author":"Client A","text":"..."}}
```

**Règle déclarative** (aucun code, aucune expression libre) :

```json
{"id":"r_low_stock","version":1,"natural_language":"...","trigger":{"source":"whatsapp","entity":"product"},"joins":[{"source":"access","table":"Articles","on":{"entity":"product","field":"designation"},"where":[{"field":"qty","op":"lt","value":10}]},{"source":"excel","sheet":"Tarifs","on":{"entity":"product","field":"Produit"}}],"window_seconds":604800,"emit":{"severity":"warning","template":"{product}: stock {access.qty}, prix {excel.prix} FCFA"}}
```

Opérateurs autorisés : `eq, ne, lt, lte, gt, gte, contains, in`.

## 5. Calendrier (84 h)

| Phase | Dates | Heures | Livrables | Critère de sortie |
| --- | --- | --- | --- | --- |
| P0 Fondations | ven 13 – sam 14 nov | 8 | Repo public (MIT, `.kiro` committé), compose + déploiement Dokploy, front Vercel « hello » relié à l'API en HTTPS, 3 specs rédigées avec Kiro, steering, générateurs de données synthétiques, **spike Access** | Hello-world bout en bout en prod ; lecture d'un `.mdb` prouvée ; spec connectors approuvée |
| P1 Connecteurs | dim 15 – jeu 19 nov | 20 | Excel, Access, WhatsApp en MCP ; schéma unifié ; tests de contrat ; PBT des parsers ; hook de test | 3 connecteurs servis en MCP sur le VPS, enregistrés dans mcp.json ; hook déclenché |
| P2 Moteur de règles | ven 20 – mar 24 nov | 20 | Normalisation d'entités + `lang`, DSL JSON + interpréteur, NL→règle (LiteLLM, validation de schéma, 2 retries), rate limit + budget, 5 règles prédéfinies, PBT corrélation | 3 règles correctes sur le jeu de données, cas piège inclus ; cible : ≥ 8/10 phrases FR/EN converties en règle valide |
| P3 UI + Crew | mer 25 – dim 29 nov | 20 | Dashboard mobile-first, composeur de règles, cartes de corrélation avec tiroir de provenance, état dégradé, ~~connecteur n°4 généré par Crew (session enregistrée)~~ (abandonné : Crew non requis par le règlement ; projet construit avec Kiro IDE et Kiro CLI), passe accessibilité | Parcours complet cliquable en prod ; connecteur n°4 mergé |
| P4 Durcissement | lun 30 nov – mar 1 déc | 8 | Tests de fumée en prod, bouton reset des données de démo, README, scan de secrets, vérif licence et `.kiro` | **Gel du code le 1er déc. au soir** |
| P5 Soumission | mer 2 – jeu 3 déc | 8 | Vidéo (2 prises), YouTube public, write-up, blog, post social, site et LinkedIn finalisés, formulaire Devpost | Soumis le 3 déc. avant 18:00 (Yaoundé) |

Spike Access (jour 1, risque n°1) : lire un `.mdb` avec `access_parser` (Python pur). Générer le fichier synthétique une seule fois avec Jackcess (petit script Java, fichier committé) ou sur une machine Windows avec Access. Si `access_parser` échoue sur certains types, repli sur `mdbtools` en CLI dans le conteneur. Ne commence pas P1 sans avoir tranché.

Déployer dès P0 : un bug d'intégration Vercel/VPS découvert le 2 déc. est fatal, découvert le 14 nov. est anodin.

## 6. Usage de Kiro (chaque ligne doit laisser une preuve dans le repo)

| Fonction | Usage prévu | Preuve |
| --- | --- | --- |
| Specs | 3 specs distinctes (connectors, rule-engine, ui) plutôt qu'un monolithe ; les propriétés de correction sont dans `.kiro/specs/design.md` | `.kiro/specs/*` |
| Steering | Conventions de connecteur, règles de sécurité (jamais d'exécution de code généré), ton des textes UI | `.kiro/steering/*` |
| Hooks | À la sauvegarde d'un connecteur ou parser : test de contrat + PBT. À la modification d'une spec : rappel de mettre à jour `tasks.md`. (Pas de hook Prettier : trop trivial.) | `.kiro/hooks/*` |
| MCP | Tes 4 serveurs enregistrés dans Kiro et utilisés par l'app | `.kiro/settings/mcp.json`, `backend/mcp_servers/` |
| PBT | Voir propriétés P1 à P6 ci-dessous ; documenter ce qui est réellement trouvé, sans en promettre | `backend/tests/` |
| Crew | Abandonné : Crew non requis par le règlement ; projet construit avec Kiro IDE et Kiro CLI | sans objet |

Bonus « Best Kiro Crew App » : les règles parlent d'un dépôt séparé pour une app Crew. **Pose la question sur le Discord (#kiroween-hackathon) avant de cocher cette case.**

Deux habitudes qui sauvent le write-up et la vidéo :

1. **Journal de bord** `docs/build-log.md` : chaque jour 3 lignes (décision de spec, ce qu'un hook ou un PBT a trouvé, crédits consommés).
2. **Enregistrer l'écran en continu** pendant les sessions Kiro : les extraits réels sont irremplaçables pour la vidéo.

Budget de crédits (hypothèse) : 4 000 crédits sur 21 jours ≈ 190/jour ; réserver ≈ 1 000 à Crew, qui consomme plus que le CLI seul. Ne laisse jamais une session Crew tourner à vide.

## 7. Spec de départ (`requirements.md`, à raffiner avec Kiro)

- **R1** The system shall expose each data source through an MCP server implementing `fetch_records(limit)` and `health_check()`.
- **R2** WHEN a source returns records, the system shall normalize them to the unified record schema (`source`, `source_ref`, `timestamp`, `lang`, `entities`, `payload`).
- **R3** WHEN parsing a WhatsApp export, the system shall support Android and iOS formats, French and English date formats, multi-line messages and attachment placeholders.
- **R4** IF a line cannot be parsed, THEN the system shall skip it, count it and report the count without crashing.
- **R5** WHEN the user submits a natural-language rule, the system shall return a rule conforming to the Rule JSON Schema or a validation error; the system shall never execute generated code.
- **R6** The rule interpreter shall be deterministic: identical records and rule produce identical correlations.
- **R7** Every correlation shall retain the provenance (`source`, `source_ref`) of each contributing record.
- **R8** WHERE a source is unavailable, the system shall return partial results and flag the missing source.
- **R9** The system shall rate-limit rule creation per IP and enforce a global LLM budget; when exceeded, it shall fall back to predefined rules.
- **R10** The UI shall display each correlation with per-source badges and a provenance drawer.
- **R11** The UI shall be usable at a 360 px viewport width and by keyboard, with WCAG AA contrast.
- **R12** The system shall sanitize all source-originated text before rendering.
- **R13** Entity normalization shall be idempotent (case, accents, whitespace, FR/EN synonyms).

**Propriétés pour `.kiro/specs/design.md` (PBT, Hypothesis) :**

- **P1** Provenance conservation: every emitted correlation lists only records that exist in the inputs.
- **P2** Normalization idempotence: `norm(norm(x)) == norm(x)`.
- **P3** Parser round-trip: `parse(export(messages)) == messages` across Android/iOS and FR/EN formats.
- **P4** Determinism: same inputs and rule give the same output.
- **P5** Window monotonicity: widening the time window never removes a correlation.
- **P6** No fabrication: no emitted field value is absent from the source records.

## 8. Script vidéo (cible 2:50, plafond 3:00)

| Temps | Contenu |
| --- | --- |
| 0:00–0:20 | Accroche : « Small businesses don't run on APIs. They run on Excel, Access and WhatsApp. » Les trois sources brutes côte à côte. |
| 0:20–1:15 | Live : règle tapée en français ; JSON lisible généré ; exécution ; cartes de corrélation avec lignes de couture ; clic sur un badge, provenance. Cas piège résolu. |
| 1:15–1:30 | Une source coupée : l'UI se dégrade proprement, rien ne casse. |
| 1:30–2:30 | Kiro : spec → tâches (10 s), steering (10 s), hook qui se déclenche (10 s), PBT (15 s, **seulement s'il a trouvé un vrai bug**), Crew qui construit le connecteur n°4 en accéléré (20 s). |
| 2:30–2:50 | Clôture : à qui ça sert, pourquoi ça compte, dépôt et URL. Construit à Yaoundé. |

Pas de musique sous copyright. Vidéo publique sur YouTube. Montrer l'app sur l'appareil visé (navigateur + mobile).

## 9. Checklist de soumission (corrigée)

- [ ] Dépôt GitHub public (pas GitLab), licence MIT visible dans la section About
- [ ] `/.kiro/` à la racine, absent du `.gitignore`
- [ ] README : installation, architecture, usage de Kiro, données synthétiques déclarées
- [ ] URL de l'app fonctionnelle, de préférence **sans login** (sinon identifiants dans le champ réservé aux juges)
- [ ] App disponible gratuitement jusqu'à la fin du judging (29 janv. 2027)
- [ ] Vidéo YouTube publique, < 3 min
- [ ] Write-up Kiro (IDE/CLI/Web/Crew, agents, hooks, specs, steering, MCP, PBT, powers)
- [ ] Catégorie Frankenstein ; code préexistant éventuel déclaré
- [ ] Startup : confirmation fondateur + LinkedIn + site web de la startup
- [ ] **Blog** : publié pendant la période, mentionne qu'il est écrit pour Kiroween 2026
- [ ] **Post social** : commence par `#KiroweenHackathon26`, publié pendant la période, rédigé par toi (l'originalité est jugée)
- [ ] Noms et profils cohérents entre Devpost, GitHub, LinkedIn et site (les profils incohérents peuvent être disqualifiés)

## 10. Risques

| Risque | Mitigation |
| --- | --- |
| Lecture Access impossible | Spike jour 1 ; repli `mdbtools` |
| Formats WhatsApp variés | PBT round-trip ; compteur de lignes ignorées |
| JSON invalide du LLM | Validation de schéma, 2 retries, repli sur règles prédéfinies |
| VPS surchargé ou indisponible | `mem_limit`, redémarrage automatique, moniteur d'uptime, état dégradé dans l'UI |
| Crédits Kiro épuisés | Suivi hebdomadaire ; Crew limité à ≈ 1 000 crédits |
| Bonus startup jugé inéligible | Lien honnête avec LinguaSolution ; le projet reste en lice pour les prix principaux |
| Écart licence / entrant / propriétaire IP | Trancher avant le 20 nov. |
| Vidéo trop longue | Viser 2:50 ; couper la partie Kiro avant le produit |

## 11. Ordre de sacrifice si retard

1. Normalisation bilingue avancée (garder accents, casse, fuzzy matching).
2. Connecteur n°4 : le garder très simple.
3. NL→règle en direct : garder les règles prédéfinies et l'édition du JSON.
4. Finitions mobiles.

**Jamais sacrifiés :** tests, déploiement public, `.kiro`, vidéo, soumission le 3 déc.
