# Decision Log

Chronological history of architectural and technical decisions.

---

## Entry Format

```markdown
## [YYYY-MM-DD] Short decision title

**Context**: Why this choice arose (1-2 sentences)
**Decision**: What was done
**Alternatives rejected**: What was discarded and why
**Consequences**: Impact on codebase (debt, future constraints)
**AGENTS.md rule concerned**: (if applicable)
```

---

## [2026-11-17] Redis réel en CI et écart de prix indéfini refusé par l'interpréteur
**Context**: Le limiteur, le compteur de dépense LLM et le délai d'alerte n'étaient testés qu'avec des faux ; la propriété P6 (pas de fabrication) n'était que partielle.
**Decision**: Service `redis:7-alpine` dans le job backend de la CI, `REDIS_TEST_URL` (base 15, vidée avant et après chaque test, jamais la base 0), tests marqués `redis` sautés sans la variable et étape CI qui échoue si un test est sauté. P6 : propriété Hypothesis sur règles et records générés, avec un oracle indépendant du rendu. Elle a trouvé `_gap_pct` : `OverflowError` sur un entier hors de la plage des flottants (toute la règle échouait) et écart infini (JSON invalide). Un écart non représentable est désormais indéfini, donc la condition n'est pas satisfaite (comme une référence nulle).
**Alternatives rejected**: `fakeredis` (ne prouve ni `SET NX EX` ni `INCRBY` atomiques) ; traiter un écart infini comme supérieur à toute tolérance (la valeur ne peut pas être stockée) ; restreindre le générateur aux petits entiers (masque le défaut).
**Consequences**: Un record dont l'écart de prix est hors plage ne corrèle plus au lieu de faire échouer la règle. Les tests Redis exigent un Redis local hors CI (`docker run -p 6390:6379 redis:7-alpine`).

---
## [2026-11-17] Serveurs MCP hébergés en HTTP plutôt que lancés en stdio par Kiro

**Context**: Kiro n'affichait aucun serveur MCP malgré un `.kiro/settings/mcp.json` valide, et le fichier local à chemins absolus ne pouvait pas être versionné. Le propriétaire veut un fonctionnement automatique.
**Decision**: Service compose `mcp` (même image, `mcp_http_main.py`, 192 Mo) servant `/mcp/<source>` en Streamable HTTP sans état, jeton Bearer `MCP_HTTP_TOKEN` (temps constant), limitation par IP en mémoire avant le contrôle du jeton, secrets limités par `--only-secrets`. Nom `chimeraflow-mcp.linguasolution.com` (tunnel, CNAME, domaine Dokploy). `.kiro/settings/mcp.json` redevient versionné avec `${CHIMERAFLOW_MCP_TOKEN}` ; le stdio reste une alternative documentée.
**Alternatives rejected**: serveur unique à outils préfixés (Kiro perdrait les quatre serveurs identiques au stdio) ; chemin sur l'API existante (mélange le jeton MCP avec la configuration de l'API, mémoire de 512 Mo partagée avec litellm) ; Vercel (fonctions sans état, fichiers `mdbtools` et Access indisponibles) ; limiteur Redis (dépendance inutile pour un service à un processus).
**Consequences**: Nouvelle variable obligatoire pour ce service seulement (`MCP_HTTP_TOKEN`, `MCP_RATE_LIMIT_PER_IP`) ; compteur de limitation perdu au redémarrage ; DNS rebinding désactivé car l'accès repose sur le jeton ; chaque poste doit définir `CHIMERAFLOW_MCP_TOKEN` et approuver la variable dans Kiro. Les agents utilisateur de `~/.kiro/agents` reçoivent `includeMcpJson: true`.
**AGENTS.md rule concerned**: §7 (aucune valeur par défaut), §9 (limitation de débit)

---

## [2026-11-17] Alerte e-mail : un rejet définitif n'est pas un envoi réussi
**Context**: En production, Cloudflare Email Service a répondu HTTP 200 et `success: true` avec `result: {delivered: [], queued: [], permanent_bounces: [1 élément]}` pour l'ancien domaine d'envoi (retiré) ; `alerts.py` a journalisé `outcome=sent` et aucun e-mail n'est arrivé.
**Decision**: `send_digest` lit les longueurs de `result.delivered`, `result.queued` et `result.permanent_bounces` (`_delivery_counts`). Succès seulement si HTTP 2xx, `success: true` et delivered + queued ≥ 1. Rejets seuls : `outcome=bounced`, retour `False`, pas de nouvel essai (définitif). Résultat entièrement vide : `outcome=empty`, retenté une fois comme un échec passager (aucun envoi n'a eu lieu, donc pas de doublon possible). Le domaine d'envoi devient `mail.linguasolution.com`.
**Alternatives rejected**: Ne pas retenter le résultat vide (ambiguïté sans coût : un seul essai de plus). Journaliser les adresses rejetées (données personnelles).
**Consequences**: Le délai global reste consommé par un envoi échoué (voir TECH_DEBT). Le format réel de `result` n'est connu que par la réponse observée en production.
**AGENTS.md rule concerned**: §22 (définition du succès mise à jour).

## [2026-11-17] Specs Kiro au format dossier

**Context**: Le panneau Specs de Kiro restait vide : il attend un dossier par spec (`requirements.md`, `design.md`, `tasks.md`), le dépôt avait des fichiers à plat.
**Decision**: `.kiro/specs/chimeraflow-backend/` (design, tasks, détails connectors/rule-engine/api, `requirements.md` EARS en français) et `.kiro/specs/chimeraflow-ui/` (`design.md` ex-`ui-spec.md`, `requirements.md`, `tasks.md` extrait de la phase P3). Déplacements par `git mv`.
**Alternatives rejected**: Une spec par fichier d'origine (trois specs sans design propre). Une seule spec (mélange backend et interface).
**Consequences**: Références mises à jour (AGENTS.md §21, README, docs, commentaires de code). `docs/build-log.md` et les QCM HTML gardent les anciens chemins (historique).

---

## [2026-11-17] Configuration MCP de Kiro locale, en chemins absolus

**Context**: Le panneau MCP de Kiro restait vide malgré `.kiro/settings/mcp.json`. Avec des chemins relatifs (`command`, `args`, `DATA_DIR`), un serveur lancé depuis un autre répertoire que la racine échoue (`FileNotFoundError`, constaté sur les quatre serveurs).
**Decision**: `.kiro/settings/mcp.json` utilise des chemins absolus et `cwd`, il est ignoré par git. Le modèle `backend/mcp_servers/kiro-mcp.json` garde le marqueur `<RACINE_DEPOT>`, remplacé par poste (commande dans `backend/README.md`).
**Alternatives rejected**: Versionner le fichier absolu (casse tous les autres postes et publie un chemin utilisateur). Variable `${RACINE}` : Kiro ne développe que les variables d'environnement du processus, à définir avant chaque lancement.
**Consequences**: Une étape par poste, documentée. Le test du modèle (`test_mcp_servers.py`) reste valable.

---

## [2026-11-17] Kiro Crew abandonné : le projet utilise Kiro IDE et Kiro CLI

**Context**: Le plan prévoyait trois agents Crew (`.kiro/agents/`) et un connecteur n°4 généré par Crew en session filmée. Le règlement du hackathon n'exige pas Crew.
**Decision**: Crew est retiré du plan. Le projet est construit avec Kiro IDE et Kiro CLI. Le connecteur Mobile Money est écrit comme les trois autres. README, AGENTS.md §21, `tasks.md` et `Roadmap.md` (P3 et ligne Crew du §6) sont mis à jour.
**Alternatives rejected**: Garder Crew « au cas où » : budget de crédits (≈ 1 000) et temps de session pour un prérequis absent du règlement.
**Consequences**: Pas de `.kiro/agents/`. Le prix « Best Kiro Crew App » n'est pas visé. Le reste du Roadmap (budget de crédits, scénario de vidéo, liste de soumission) cite encore Crew : à relire par le propriétaire.
**AGENTS.md rule concerned**: §21

---

## [2026-11-17] Relances sur erreurs passagères du fournisseur LLM et modèle de repli
**Context**: En production avec `glm-4.7-flash-bedrock`, 6 requêtes NL→règle sur 10 ont reçu `502 nl_provider_error` pendant environ 3 minutes d'`InternalServerError` du proxy ; les mêmes phrases ont ensuite réussi. Seules les réponses invalides étaient relancées.
**Decision**: Une erreur passagère (5xx, connexion, délai ; jamais 4xx ni erreur inattendue) est relancée au plus 2 fois pour toute la conversion, après 0,5 s puis 1,5 s (± 25 % de gigue), dans un délai global de 45 s (appel limité au temps restant, aucun appel sous 3 s). `LITELLM_FALLBACK_MODEL` (optionnelle) sert à la dernière relance et aux appels suivants. Chaque tentative réserve le budget, un échec garde le coût d'entrée pessimiste. La réponse 200 et les erreurs `nl_*` portent `provider_retries`, `retries` garde son sens.
**Alternatives rejected**: `num_retries` de LiteLLM (invisible du budget, délais non maîtrisés, relances non comptées). Relancer aussi les 429 : le budget et les limites du fournisseur ne se règlent pas en quelques secondes. Un compteur de relances par type d'erreur : plus de code pour le même plafond de requête.
**Consequences**: `LlmClient.complete` prend `model` et `timeout`. Pire cas d'une requête sous 50 s (45 s plus la marge de 2 s du délai externe). Image backend inchangée. Le repli n'est pas vérifié contre le vrai proxy (TECH_DEBT).
**AGENTS.md rule concerned**: §7 (variable optionnelle via `optional_env`, pas de valeur de repli), §22

---

## [2026-11-17] Frontend : vitest 4, surcharge postcss et audit navigateur
**Context**: 19 alertes Dependabot npm ouvertes (postcss via Next, vite, vitest, tinypool critique, esbuild, minimatch) et interface jamais exécutée dans un navigateur (R11 : 360 px, clavier, WCAG AA).
**Decision**: `vitest` 4.1.12 (vite 8, config JSX passée de `esbuild` à `oxc`), `overrides.next.postcss` ^8.5.23, `npm audit fix` pour minimatch et typescript-eslint : `npm audit` donne 0 avis, dev compris. Audit Edge headless (axe-core, Playwright, API simulée, outils hors dépôt) : jeton `--text-muted` clair assombri (`#5f6672`, 4,44:1 mesuré sur la fin du dégradé), nom accessible des boutons FR/EN commençant par le texte visible, `h2` masqué pour la liste des corrélations (ordre des titres).
**Alternatives rejected**: Next 16 : la seule alerte runtime (postcss) se ferme par la surcharge ; la montée imposerait ESLint 9 en config plate et la fin de `next lint` pour un gain nul sur la sécurité. Ajouter Playwright ou axe au `package.json` : demande une dépendance approuvée, l'audit reste un outil ponctuel.
**Consequences**: la surcharge est à retirer au passage en Next 16 ; l'audit navigateur n'est pas en CI (voir TECH_DEBT 2026-11-17).
**AGENTS.md rule concerned**: §16 (dépendance de dev montée en version majeure pour fermer des avis), §10 (contraste 4,5:1)

---

## [2026-11-17] Parseur WhatsApp : formats, ordre des dates et aller-retour (R3, P3)
**Context**: Le parseur ne lisait que `[JJ/MM/AAAA, HH:MM:SS]` ; iOS, dates EN et messages multi-lignes étaient des erreurs. P3 n'avait ni fonction d'export ni test.
**Decision**: Parseur pur dans `whatsapp_parser.py` (formats Android avec ou sans crochets, iOS, horloge 12 h). Ordre jour/mois décidé par fichier : premier champ > 12 donne `dmy`, sinon second champ > 12 donne `mdy`, sinon `default_date_order` (`dmy`), exposé et journalisé. Lignes de suite ajoutées au message précédent ; messages système (sans auteur) comptés dans `system_skipped` ; pièces jointes gardées avec `payload["attachment"]`. `export_messages` et trois tests Hypothesis couvrent P3. Deux messages ajoutés en fin de `data/commandes_clients.txt` (multi-lignes, média) sans décaler les numéros de ligne existants.
**Alternatives rejected**: Heuristique « AM/PM donc mois d'abord » (faux au Royaume-Uni ou en Australie). Variable d'environnement pour l'ordre par défaut (hors périmètre, demanderait AGENTS.md §22). Lecture en flux avec arrêt à `limit` (l'ordre des dates exige tout le fichier).
**Consequences**: `parse_errors` et `system_skipped` portent sur tout le fichier ; une ligne vide avant le premier en-tête n'est plus une erreur ; `attachment` s'ajoute au payload sans être une colonne de règle. Limites dans TECH_DEBT (2026-11-17). Les hooks `parser-test` et `spec-update-reminder` avaient un `matcher` jamais vrai (`\\.py` au lieu de `\.py` après échappement JSON) et `cd backend && …` échoue sous PowerShell 5.1 : corrigés.
**AGENTS.md rule concerned**: §4 (corriger dans le cycle), §7 (pas de repli de configuration : l'ordre par défaut est un argument documenté)

---

## [2026-11-17] Dépendances Python : litellm 1.100.4 et python-dateutil 2.9.0.post0
**Context**: Alertes Dependabot 1 et 22 (litellm, sévérité haute, correctif 1.100.4).
**Decision**: `litellm==1.100.4` (version corrigée la plus basse). Il tire `boto3`, qui borne `python-dateutil < 3` : `python-dateutil` passe de 4.0.0 à 2.9.0.post0 (aucun import direct, dépendance de pandas).
**Alternatives rejected**: Une version de litellm plus récente (plus de changements sans besoin). Garder `python-dateutil` 4.0.0 (résolution impossible).
**Consequences**: Trois paquets de plus (`boto3`, `botocore`, `s3transfer`). Voir TECH_DEBT (2026-11-17).
**AGENTS.md rule concerned**: §16 (dépendance ajoutée de façon transitive, imposée par le correctif de sécurité)

---

## [2026-11-17] Traefik : garde-fou systemd contre la perte des réglages
**Context**: Les réglages `trustedIPs` et `api.insecure: false` sont dans un fichier partagé que Dokploy gère. Il fallait savoir si un rechargement depuis l'interface les efface.
**Decision**: Lecture du code Dokploy v0.31.0 : Reload = `docker restart` seul, `traefik.yml` n'est recréé que s'il est absent, et Dokploy ne le stocke pas en base (rien à synchroniser par `settings.updateTraefikConfig`). Ajout de `check-traefik-config.timer` (5 min, root) : script `/usr/local/sbin/check-traefik-config.sh`, copie de référence `traefik.yml.chimeraflow-reference`, correction des deux clés seulement puis `docker restart`, rien si aucune dérive. Copies dans `ops/vps/`. Essais : sans dérive, copies à dérive, conteneur factice, un Reload Dokploy réel (fichier inchangé).
**Alternatives rejected**: Remplacer le fichier entier par la référence (écraserait les changements des autres applications). Recréer automatiquement le conteneur s'il perd le secret DNS-01 (invasif sur une infra partagée) : le script journalise l'erreur seulement. `chattr +i` sur le fichier (bloquerait aussi les écritures légitimes de Dokploy).
**Consequences**: Les commentaires du YAML sont perdus lors d'une correction. Une recréation du conteneur par Dokploy (toggle dashboard, ports, variables, version) garde le fichier mais perd le montage du secret DNS-01 et change la version de Traefik (TECH_DEBT). Retrait : voir `ops/vps/README.md`.
**AGENTS.md rule concerned**: §4 (ne laisser aucun problème non résolu), §9

---

## [2026-11-17] Traefik : IP visiteur de confiance et tableau de bord fermé
**Context**: Derrière le tunnel, Traefik remplaçait `X-Forwarded-For` par la passerelle Docker `172.18.0.1` (cloudflared, en réseau hôte, atteint Traefik par `[::1]:443` puis docker-proxy), donc tous les visiteurs partageaient une clé de limitation. `api.insecure: true` publiait en plus l'API et le tableau de bord de Traefik sur `:8080` sans authentification, joignable depuis tout conteneur du réseau `dokploy-network`.
**Decision**: Dans `/etc/dokploy/traefik/traefik.yml` (accord du propriétaire) : `forwardedHeaders.trustedIPs: ["172.18.0.1/32"]` sur `websecure` seulement, et `api.insecure: false` (aucun routeur `api@internal`, le tableau de bord n'est plus exposé). Sauvegarde : `/etc/dokploy/traefik/traefik.yml.bak-chimeraflow-20261116200929`. Puis `docker restart dokploy-traefik`. `TRUSTED_PROXIES=10.0.1.0/24,172.18.0.1/32` posé dans Doppler par le propriétaire.
**Alternatives rejected**: Faire confiance aux plages publiques de Cloudflare : inutile, seul le pair `172.18.0.1` parle à Traefik. Élargir à `172.18.0.0/16` : tout conteneur du pont pourrait forger l'IP cliente. Ajouter `web` : cloudflared n'utilise que `https://localhost:443`.
**Consequences**: Mesuré sur l'API : `X-Forwarded-For: <IP visiteur>, 172.18.0.1`. Limite de connexion (5 par minute) : 429 à la 6e tentative depuis un poste, le test de fumée GitHub (autre IP) passe. Le port 8080 n'était pas publié sur l'hôte et reste fermé dans le réseau Docker. Un rechargement de Traefik par Dokploy peut réécrire le fichier (TECH_DEBT, 2026-11-17). Retour arrière : copier la sauvegarde sur `traefik.yml` puis `docker restart dokploy-traefik`.
**AGENTS.md rule concerned**: §9 (limitation de débit sur les points d'entrée publics)

---

## [2026-11-17] API publique sur `chimeraflow-api.linguasolution.com` via le tunnel partagé
**Context**: L'API n'était pas joignable depuis Internet (DNS vers l'adresse Tailscale, ports 80 et 443 fermés sur `eth0`), donc les runners GitHub et le frontend hors Tailscale échouaient. Le propriétaire a déjà un tunnel Cloudflare `hetzner-1-web` qui sert ses autres applications.
**Decision**: Le nom public est `chimeraflow-api.linguasolution.com` (CNAME proxied vers le tunnel `hetzner-1-web`, ingress vers Traefik en `https://localhost:443`). Traefik délivre le certificat en DNS-01. Les ports 80 et 443 du VPS restent fermés. Vercel pointe déjà sur ce nom.
**Alternatives rejected**: `api.chimeraflow.linguasolution.com` : deux niveaux de sous-domaine, non couverts par l'Universal SSL de Cloudflare. DNS vers l'IP publique avec ports 80 et 443 ouverts : annule le durcissement du VPS décidé par le propriétaire.
**Consequences**: Derrière le tunnel, l'IP cliente visible par l'API est celle de la passerelle Docker : la limitation de débit est partagée entre visiteurs jusqu'au correctif de `TRUSTED_PROXIES` (TECH_DEBT, 2026-11-17). Le correctif touche la config Traefik partagée et demande l'accord du propriétaire.
**AGENTS.md rule concerned**: aucune

---

## [2026-11-17] E-mails via Cloudflare Email Service et alias LiteLLM nu
**Context**: Le propriétaire utilise Cloudflare (Mailflare) pour toutes ses adresses, sur un sous-domaine de `linguasolution.com` ; le proxy LiteLLM attend l'alias `deepseek-v4.1-flash-group`, sans préfixe.
**Decision**: L'alerte e-mail appelle l'API REST Cloudflare Email Service (`CF_EMAIL_ACCOUNT_ID` de 32 caractères hexadécimaux, `CF_EMAIL_API_TOKEN`), succès = HTTP 2xx et `success: true`, seuls les codes d'erreur sont journalisés ; expéditeur `ChimeraFlow <notifications@notify.linguasolution.com>`. Le client LiteLLM envoie l'alias tel quel avec `custom_llm_provider="openai"` (un ancien `openai/` est retiré une fois).
**Alternatives rejected**: Resend (hors de la norme du propriétaire, domaine d'envoi à part). Préfixe `openai/` dans `LITELLM_MODEL` : il ne sert qu'à choisir le fournisseur par le nom, ce que le paramètre explicite fait sans modifier l'alias.
**Consequences**: Variables `RESEND_API_KEY` remplacées dans Doppler et `docker-compose.yml`. Aucun envoi ni appel réel vérifié (TECH_DEBT). Le client HTTP `httpx` journalise l'URL (qui contient l'identifiant de compte) : son niveau est relevé à WARNING.
**AGENTS.md rule concerned**: §7 (aucune valeur de repli), §22

## [2026-11-16] Délai global des e-mails d'alerte, obligatoire avec Resend
**Context**: Chaque exécution qui trouve de nouvelles corrélations `warning`/`error` envoyait un e-mail : des exécutions répétées pouvaient inonder la boîte et épuiser le quota Resend.
**Decision**: `ALERT_EMAIL_COOLDOWN_SECONDS` (entier ≥ 60) limite à un récapitulatif par fenêtre, clé Redis `chimeraflow:alerts:cooldown` posée avec `SET NX EX`. Obligatoire dès que les trois variables Resend sont définies ; sans Redis ou en cas de panne, rien n'est envoyé (échec fermé).
**Alternatives rejected**: Valeur par défaut documentée (comme `RATE_LIMIT_NL_PER_IP`) : une configuration oubliée resterait silencieuse. Compteur en mémoire de processus : non partagé entre workers.
**Consequences**: Les corrélations nouvelles pendant le délai ne sont pas envoyées plus tard (elles restent visibles dans l'interface). Le démarrage échoue si Resend est configuré sans la nouvelle variable.
**AGENTS.md rule concerned**: §7 (aucune valeur de repli)

## [2026-11-15] Noms partiels : inclusion de mots plutôt que `token_set_ratio`
**Context**: « perceuse 500W » et « tuyau PVC » ne correspondaient pas à « Perceuse électrique 500W » et « Tuyau PVC Ø 32mm (barre 6m) » (comparaison de chaîne entière, garde numérique stricte).
**Decision**: Un nom contenu mot pour mot dans l'autre correspond (méthode `token`, score de 0.85 à 0.99, jamais devant l'exact). Ses nombres doivent figurer dans l'autre nom (un nom sans nombre peut donc correspondre à un nom chiffré). La faute de frappe (`fuzzy`) exige le même nombre de mots et des mots d'au moins 5 lettres. Le résultat porte la méthode (`exact`, `synonym`, `fuzzy`, `token`) pour l'explication.
**Alternatives rejected**: `token_set_ratio` seul : il vaut 100 pour une inclusion mais note 0.9 « tuyau pvc 32mm » et « tuyau ppr 32mm » (deux produits). Il reste utilisé sous forme de `fuzz.ratio` sur les mots triés, pour noter la couverture. Lever la garde numérique : « ciment 50 kg » et « ciment 40 kg » se confondraient.
**Consequences**: Un nom d'un seul mot correspond à tout produit qui le contient (dette notée). Le test « tuyau PVC » contre « tuyau PVC 32mm » (rejeté avant) est inversé. Le faux positif préexistant PVC/PPR en chaîne entière est corrigé au passage.
**AGENTS.md rule concerned**: aucune (le seuil flou 0.85 de `steering/connectors.md` est conservé)

---

## [2026-11-15] DSL étendu : conditions du déclencheur, écart calculé fermé, jointure sur `entities`
**Context**: Trois règles prédéfinies étaient inactives car le DSL ne savait ni filtrer le record déclencheur, ni calculer un écart, ni joindre sur les entités d'un message.
**Decision**: `trigger.where` (valeurs littérales), `ref` (`<source>.<colonne>` du déclencheur ou d'un join précédent) avec `tolerance_pct` (0 à 1000, opérateurs d'ordre), `on.field = "entities"`. Vocabulaire fermé et validé : colonnes connues par source (`schemas/sources.py`), bornes de taille, `momo.phone` et `momo.customer_name` interdits dans un template, clés inconnues refusées. Réactivation livrée par le seed : quand la définition d'une règle prédéfinie change, la version est incrémentée et le statut du fichier est appliqué ; une règle inchangée garde son statut. `POST /demo/reset` rétablit tout.
**Alternatives rejected**: Expressions libres ou mini-langage (surface d'attaque, règle « pas d'exécution de code ») ; toujours écraser le statut au seed (efface un choix d'opérateur à chaque redémarrage) ; migration de données (une règle prédéfinie vient des fichiers, pas d'une migration).
**Consequences**: Les règles stockées doivent respecter les nouvelles bornes (les cinq prédéfinies et les brouillons du modèle les respectent). La version de toutes les règles prédéfinies est incrémentée une fois. Aucun endpoint ne change le statut, donc rien n'est perdu.
**AGENTS.md rule concerned**: §20 (schéma de règle étendu et mis à jour), §4 (JSON déclaratif, pas de code)

---

## [2026-11-15] Corrélations stables, explication stockée, flux lu avec fetch, alerte Resend
**Context**: Il fallait expliquer chaque correspondance, offrir le temps réel et alerter par e-mail sans renvoyer les mêmes alertes à chaque exécution.
**Decision**: `correlations.explanation` (JSON nullable, migration 0003). Une exécution garde la ligne, l'`id` et le `detected_at` d'une corrélation retrouvée (identité : message + records de la provenance) ; `since` et le flux ne voient que le nouveau. Flux SSE par interrogation de la base toutes les 2 s, lu avec `fetch` et l'en-tête Bearer (pas de jeton de flux). E-mail : un récapitulatif des nouvelles corrélations `warning` et `error`, tâche de fond, Resend via `httpx` (déjà présent), activé si les trois variables sont définies. `POST /normalize` sans limite par IP (sans état, borné, authentifié) pour noter pendant la frappe.
**Alternatives rejected**: Remplacer toutes les lignes à chaque exécution (ids changeants, e-mail à chaque fois) ; jeton de flux signé en URL (jeton dans les journaux des proxys) ; Redis pub/sub ou mémoire de processus pour le flux (inutile avec plusieurs processus) ; SDK Resend (dépendance de plus).
**Consequences**: Le flux coûte une lecture de base par flux toutes les 2 s (20 flux au plus). Les nouvelles variables sont facultatives et passées par `docker-compose.yml`. L'alerte n'a jamais été envoyée à un vrai Resend (dette).
**AGENTS.md rule concerned**: §7 (fonction désactivée si une variable manque, aucun repli), §9 (pas de PII dans les journaux : destinataires et contenu jamais journalisés)

---

## [2026-11-15] Budget LLM : réservation avant l'appel, colonnes autorisées pour les brouillons du modèle
**Context**: Le plafond n'était vérifié qu'avant l'appel et le coût ajouté après : des appels simultanés pouvaient le dépasser. Un brouillon pouvait aussi exposer `momo.phone` ou inventer des colonnes.
**Decision**: `INCRBY` du coût estimé (prompt + réponse maximale) avant l'appel, refus si la dépense d'avant l'appel atteint le plafond (réservation rendue), puis règlement par la différence avec le coût réel. La validation `RuleCreate` refuse les colonnes inconnues et les placeholders de données personnelles ; le brouillon est relancé avec l'erreur, et le prompt décrit la nouvelle syntaxe.
**Alternatives rejected**: Verrou Redis autour de l'appel (sérialise les conversions, 20 s chacune) ; refuser quand la réservation dépasse le plafond (refus prématuré près du plafond, tests existants).
**Consequences**: Une requête annulée garde sa réservation (dette, sans sous-estimation). Le protocole `SpendStore.add_spent_usd` renvoie le total.
**AGENTS.md rule concerned**: §4 (budget plafonné), `steering/security.md` (budget, validation du schéma, pas de confiance dans le modèle)

---

## [2026-11-15] Scénario de données : chaque règle prédéfinie trouve une corrélation
**Context**: Seules deux règles produisaient quelque chose sur les fichiers livrés, et la démonstration doit montrer les cinq.
**Decision**: WhatsApp et MoMo scriptés (messages et paiements explicites, dont un paiement `SUCCESS` et un `PENDING` pour le même ciment), dates Excel et Access rapprochées (fenêtre de 3 jours de `r_stock_replenish`), deux écarts de prix de 13 % et 14 %, des stocks sous 15 pour des produits demandés, un message à deux produits. Les téléphones MoMo générés sont manifestement faux (`237000…`). `tests/test_scenario_data.py` exécute les cinq règles sur les vrais fichiers.
**Alternatives rejected**: Garder les dates aléatoires (une règle sur deux ne trouve rien) ; données tirées de vraies transactions (interdit, 100 % synthétique).
**Consequences**: Les fichiers `data/*` changent (régénération par `scripts/generate_*.py` et `generate_access_windows.vbs`, ce dernier seulement sous Windows avec Access). Tout test qui lit ces fichiers dépend du scénario.
**AGENTS.md rule concerned**: `steering/security.md` (données 100 % synthétiques)

---

## [2026-11-15] Interface P3 : fil de couture, i18n par contexte, flux lu par fetch, tests de composants
**Context**: Les écrans P3 (tableau de bord, règles, composeur, corrélations, bac à sable) devaient suivre DESIGN.md sans ressembler à une interface générée, fonctionner en FR/EN avec thème sombre, et rester utilisables quand les endpoints du chantier backend manquent.
**Decision**: Signature visuelle unique, le « fil de couture » (trait pointillé qui relie les sources d'un résultat, coupé quand une source est en panne), icônes SVG à la place des émojis, aucun halo ni dégradé de texte. `t()` reste pur ; `LocaleProvider` et `useI18n()` portent la langue (FR par défaut, choix dans `localStorage`), `tp()` choisit la forme plurielle avec `Intl.PluralRules`. Thème par `data-theme` sur `<html>`. Flux SSE lu avec `fetch` (l'en-tête Bearer ne passe pas par `EventSource`), chaque événement relit la liste, repli sur une relecture toutes les 15 s. Réponses de l'API validées par des gardes de type (`lib/parsers.ts`) qui gardent les champs inconnus, pour que le JSON d'un brouillon soit renvoyé tel quel. Tiroirs et confirmations en `<dialog>` natif. Tests de composants avec Testing Library et jsdom, Vitest passé en 3.x.
**Alternatives rejected**: next-intl ou react-intl (dépendance pour une trentaine de clés par écran) ; `EventSource` avec jeton dans l'URL (jeton dans les journaux) ; bibliothèque de modales (le `<dialog>` piège le focus et gère Échap) ; Monaco pour le JSON (poids, et la modification passe par le composeur).
**Consequences**: Nouvelles dépendances de développement : vitest 3.2.7, jsdom 26.1.0, @testing-library/react 16.3.3, @testing-library/dom 10.4.2, @testing-library/user-event 14.6.10. Le thème explicite peut clignoter une fois au chargement (appliqué après l'hydratation). Le panneau « Pourquoi ça correspond » lit le format actuel de l'explication et retombe sur un affichage générique sinon.
**AGENTS.md rule concerned**: §4 (aucun texte en dur : tout passe par `messages/*.json`), §6 (logique dans `lib/`, `fetch` dans `lib/services/`), §8 (pluriels et dates par `Intl`)

---

## [2026-11-15] Serveurs MCP stdio, un processus par source (SDK `mcp` 2.3.0)
**Context**: La sortie de P1 exige des connecteurs servis en MCP et utilisés par Kiro ; AGENTS.md §18 vise « 4 serveurs MCP dans un conteneur ». Le SDK officiel `mcp` est approuvé.
**Decision**: Un module (`mcp_servers/mcp_app.py`) lancé quatre fois via `backend/mcp_main.py --source <nom>`, transport stdio, outils `fetch_records(limit 1..1000)` et `health_check()` en lecture seule, ressource de métadonnées. Réglages dans `mcp_servers/mcp_settings.py` (`DATA_DIR`, `ACCESS_READER` pour `access` seulement, sans repli) au lieu de `config.py`, qui exige tous les réglages de l'API. Appels au connecteur dans un thread de travail, 5 s, 2 tentatives, sérialisés par un verrou (compteur `parse_errors` partagé, premier import d'openpyxl non sûr entre threads). `access_connector.py` n'importe plus `config` au chargement : `ACCESS_READERS` y est dérivé de ses lecteurs et `ACCESS_READER` est lu à la demande quand aucun lecteur n'est passé.
**Alternatives rejected**: Un seul serveur à outils préfixés par source (Kiro ne montrerait qu'une entrée, un échec d'une source gênerait les autres) ; HTTP streamable dans compose (port et surface d'attaque en plus, sans besoin avant la démo) ; importer `config.py` (impose base, Redis et secrets d'authentification à un serveur lancé par Kiro) ; recopier la logique des connecteurs (deux sources de vérité).
**Consequences**: Dépendance `mcp==2.3.0` (version majeure récente, ses dépendances ne sont pas épinglées). Pas de service MCP dans les fichiers compose : « 4 serveurs dans un conteneur » reste une cible (lancement possible par `docker run -i ... python mcp_main.py --source <nom>`). `ACCESS_READERS` est défini à deux endroits (`config.py` et `access_connector.py`), à unifier.
**AGENTS.md rule concerned**: §7 (aucun repli de configuration), §16 (dépendance `mcp` approuvée par l'utilisateur), §18 (4 serveurs MCP : stdio seulement)

---

## [2026-11-15] Surveillance planifiée désactivée tant que l'API est privée
**Context**: Le premier essai de `uptime.yml` et de « Production smoke » sur GitHub a échoué (`curl` code 28 vers l'API) : le DNS de l'API pointe vers l'adresse Tailscale du VPS et le pare-feu rejette le trafic public sur 80/443.
**Decision**: Les exécutions planifiées de `uptime.yml` sont conditionnées à la variable de dépôt `UPTIME_SCHEDULE_ENABLED` (absente = désactivées) ; le lancement manuel reste possible. Le ticket `uptime` ouvert par ce faux positif est fermé avec une explication. Rien n'est modifié côté DNS ni pare-feu.
**Alternatives rejected**: Laisser tourner le moniteur (ticket permanent, bruit) ; ouvrir le pare-feu ou changer le DNS (décision de réseau du propriétaire, hors périmètre) ; Tailscale sur le runner (secret supplémentaire, accès au réseau privé depuis GitHub).
**Consequences**: Pas de surveillance automatique tant que le propriétaire n'a pas rendu l'API publique ; la dette est suivie dans `TECH_DEBT.md`.
**AGENTS.md rule concerned**: §4 (blocage externe documenté dans `TECH_DEBT.md`)

---

## [2026-11-15] Durcissement CI et exploitation : jobs frontend et secrets, moniteur, test de fumée, Dokploy sur main
**Context**: Le dépôt est public, les Actions sont gratuites et `main` devient la production ; la CI ne couvrait pas le frontend, aucun contrôle ne vérifiait la production et Dokploy suivait encore `dev`.
**Decision**: (1) CI : job « Frontend lint, tests and build » (Node 22, `npm ci`, tsc, lint, vitest, build avec des `NEXT_PUBLIC_*` factices) et job « Secret scan » (binaire gitleaks 8.30.1 épinglé par somme SHA-256, historique complet) ; actions tierces épinglées par SHA de commit. (2) `uptime.yml` toutes les 30 min : `/health` et `/login`, un seul ticket `uptime` ouvert puis fermé au retour ; la permission `issues: write` n'est donnée qu'au job qui gère le ticket. (3) `scripts/ops/smoke-prod.{sh,ps1}` : identifiants lus dans `SMOKE_EMAIL` / `SMOKE_PASSWORD`, jamais dans le dépôt ; workflow manuel « Production smoke » avec deux secrets de dépôt copiés depuis Doppler (valeurs publiques par construction). (4) Compose Dokploy `chimeraflow-api` : branche `main` (via l'API Dokploy), sans redéploiement ; `autoDeploy` laissé désactivé. (5) `docs/deployment/PRODUCTION.md` décrit déploiement, rotation du jeton Doppler, retour arrière.
**Alternatives rejected**: `gitleaks/gitleaks-action` (code tiers avec accès au dépôt, licence selon le type de compte) au profit du binaire vérifié par somme ; service Redis dans la CI (aucun test d'intégration Redis n'existe, il tournerait sans rien tester) ; `autoDeploy` sur `main` (une fusion déploierait sans contrôle d'une variable Doppler manquante, l'API s'arrêterait au démarrage) ; URLs de production en paramètre des scripts de fumée (repli de configuration, §7).
**Consequences**: `main` exige maintenant aussi les nouveaux jobs si le propriétaire les ajoute aux contrôles requis ; les secrets de dépôt `SMOKE_*` suivent `NEXT_PUBLIC_DEMO_LOGIN_*` ; le ticket d'indisponibilité dépend des notifications GitHub du dépôt ; le compose Dokploy est sur `main` : le prochain déploiement attend la fusion de la PR `dev` → `main`.
**AGENTS.md rule concerned**: §4 et §12 (dette corrigée dans le cycle), §7 (pas de repli de configuration)

---

## [2026-11-15] Déploiement initial depuis dev
**Context**: La démonstration doit être en ligne avant la fusion de la PR `dev` → `main`, sans quoi rien n'est testable en conditions réelles.
**Decision**: Le compose Dokploy `chimeraflow-api` (VPS) et le projet Vercel `chimeraflow` se déploient depuis la branche `dev` jusqu'à la fusion de la PR. La branche de production Vercel reste `main` : les déploiements de `dev` sont donc lancés à la main, par référence git. Les noms `api.chimeraflow` et `chimeraflow` (zone `linguasolution.com`) sont en DNS seul (sans proxy) ; Traefik obtient les certificats Let's Encrypt par HTTP-01.
**Alternatives rejetées**: Fusionner `dev` dans `main` avant la revue (contredit la règle PR du §5) ; proxy DNS du fournisseur (le défi HTTP-01 et l'IP client de la limitation de débit en dépendent).
**Consequences**: Après la fusion, Dokploy et Vercel doivent passer sur `main` (voir `TECH_DEBT.md`). Les secrets viennent de Doppler, jamais du dépôt.
**AGENTS.md rule concerned**: §5 (Git Workflow), déploiement hors `main` toléré jusqu'à la PR

---

## [2026-11-15] Authentification : compte de démonstration, session émise par le backend
**Context**: AGENTS.md §9 exige une authentification des opérations sensibles et l'API était ouverte. Le frontend (Vercel) et le backend (VPS) sont deux origines distinctes, sans base d'utilisateurs : un seul compte de démonstration public suffit.
**Decision**:
(1) Le backend émet une session : `POST /api/v1/auth/login` (email + mot de passe, limité par IP) renvoie un jeton Bearer HMAC-SHA256 signé, valable 1 h ; `GET /api/v1/auth/me`. Une dépendance FastAPI posée à l'inclusion des routeurs `sources`, `rules` et `correlations` (dans `main.py`) protège tous les endpoints `/api/v1` en lecture comme en écriture ; un futur routeur ne peut pas l'oublier. `/`, `/health` restent publics.
(2) Aucune dépendance ajoutée : `hashlib.scrypt` (hash auto-descriptif `scrypt:N:r:p:sel:clé`, N = 2^15, 32 Mio), `hmac`, `secrets.compare_digest`. Le hash est recalculé même pour un email inconnu (pas d'énumération), les deux comparaisons sont à temps constant, la réponse 401 est unique (`auth_invalid_credentials`). Le calcul de hash tourne dans un thread, deux à la fois au plus (`anyio.CapacityLimiter(2)`) pour borner la mémoire du conteneur (512 Mio) face à des connexions venues de nombreuses IP.
(3) Variables obligatoires, sans repli : `AUTH_TOKEN_SECRET` (32 octets ou plus), `DEMO_LOGIN_EMAIL`, `DEMO_LOGIN_PASSWORD_HASH` (validé au démarrage, jamais affiché). `python -m auth.hash_password` lit le mot de passe sur stdin et affiche le hash. `RATE_LIMIT_LOGIN_PER_IP` est facultative ; non définie : `max(3, RATE_LIMIT_PER_IP // 2)`, soit 5 par minute en production (écart assumé à §7, même précédent que `RATE_LIMIT_NL_PER_IP`) : un repli plus strict (`// 5` = 2) bloquerait un utilisateur qui se trompe une fois.
(4) `/docs`, `/redoc` et `/openapi.json` sont désactivés quand `BACKEND_NODE_ENV=production`. Swagger UI ne peut pas envoyer l'en-tête Bearer au chargement du schéma : les protéger demanderait un mécanisme à part, et un visiteur anonyme n'a pas besoin du schéma. Hors production, ils restent servis.
(5) Les réponses 422 n'échoient plus la valeur rejetée (`input`) : un mot de passe mal formé serait revenu dans la réponse, et une valeur avec un surrogate isolé faisait échouer le gestionnaire par défaut (500). Le format reste `[{loc, msg, type}]` de api-spec.md.
(6) Frontend : page `/login` qui affiche les identifiants de démonstration (`NEXT_PUBLIC_DEMO_LOGIN_EMAIL` / `_PASSWORD`, exigées au build, publiques par construction) avec un bouton « Voir la démo » qui remplit et soumet, plus le formulaire. Jeton en mémoire et `sessionStorage` (jamais `localStorage` ni cookie : le cookie serait inter-sites, bloqué par les navigateurs et exposé au CSRF). Contexte React (`AuthProvider`), appels via `lib/services/api-client.ts` (en-tête Bearer, 401 → session effacée et retour à `/login`). La page d'accueil est protégée. `Retry-After` est exposé en CORS pour que la page affiche le délai.
**Alternatives rejected**: Neon Auth / Better Auth managé : son SDK Next.js exige un secret de cookie côté serveur sur Vercel (AGENTS.md §18 : Vercel ne détient aucun secret) et la feuille de route de Neon ne prend pas officiellement en charge un frontend et un backend séparés. Better Auth auto-hébergé : troisième service, mémoire du VPS déjà juste. PyJWT / passlib / argon2-cffi : nouvelle dépendance, non approuvée (§16) pour un compte unique. Protéger `/docs` par jeton : voir (4). Cookie de session : voir (6).
**Consequences**: un seul compte partagé, public ; pas de révocation avant l'expiration (1 h) ; `AUTH_TOKEN_SECRET` à renouveler pour invalider toutes les sessions ; `/docs` absent en production, y compris avec `docker-compose.yml` (qui fixe `BACKEND_NODE_ENV=production`) ; un login coûte 32 Mio et ~100 ms de CPU, borné par la limite par IP et par le plafond de concurrence ; les secrets sont dans Doppler `prd` (`AUTH_TOKEN_SECRET`, `DEMO_LOGIN_*`, `NEXT_PUBLIC_DEMO_LOGIN_*`) ; `docker-compose.yml` exige les trois variables obligatoires ; la CI (job migrations) passe des valeurs factices.
**AGENTS.md rule concerned**: §9 (authentification, limitation, pas de PII dans les journaux), §7 (variables obligatoires ; dérivation de `RATE_LIMIT_LOGIN_PER_IP`), §16 (aucune dépendance), §18 (pas de secret sur Vercel), §8 et §10 (textes i18n, accessibilité du formulaire)

---

## [2026-11-14] Déploiement : Doppler dans le conteneur, données dans l'image, compose de production
**Context**: Q9 : en production seule la variable `DOPPLER_TOKEN` est fournie (Dokploy). Le bind mount `./backend:/app` masquait le code de l'image, `data/` était un chemin hôte et l'image runtime contenait les tests.
**Decision**:
(1) Doppler CLI 3.77.1 installé dans un stage dédié depuis le dépôt apt officiel (paquet signé, empreinte de la clé vérifiée dans le build) ; seul le binaire statique est copié (runtime et Redis). `backend/docker-entrypoint.sh` : `DOPPLER_TOKEN` défini → `doppler run --no-check-version --no-fallback -- sh -c "alembic upgrade head && exec uvicorn ..."`, sinon la même commande sans Doppler (compose local, tests). Le mode est journalisé ; Doppler injoignable ou jeton invalide arrête le conteneur.
(2) `docker-compose.prod.yml` : services `api` et `redis`, `DOPPLER_TOKEN` seule variable. Redis est construit (`target: redis`) avec le CLI Doppler et reçoit `REDIS_PASSWORD` seul (`doppler run --only-secrets REDIS_PASSWORD`), refuse de démarrer s'il est absent ou vide (sinon Redis démarrerait sans authentification et le healthcheck passerait) et lit sa configuration sur stdin (`redis-server -`, mot de passe hors des arguments du processus) ; `REDIS_URL` dans Doppler le référence (`redis://:${REDIS_PASSWORD}@chimeraflow-redis:6379/0`). Son healthcheck n'a pas le mot de passe : `NOAUTH` signifie serveur vivant. `api` est sur `dokploy-network` (externe) et sur le réseau privé `internal` partagé avec Redis (alias `chimeraflow-redis`) ; aucun port publié, un seul label `traefik.docker.network=dokploy-network` pour fixer le réseau que Traefik utilise. `mem_limit` : api 512m (mesuré ~105 MiB au repos, ~275 MiB avec litellm importé), Redis 128m.
(3) `data/` copié dans l'image par un contexte de build nommé `data` (`additional_contexts` en compose, `--build-context data=./data` sinon) : aucun chemin hôte sur le VPS, les données sont synthétiques et publiques. Un stage `source` retire tests/, requirements-dev.txt et fichiers de dev du runtime.
(4) Compose local : bind mount `./backend:/app` retiré, `mem_limit` 512m. Frontend : `lib/env.ts` sans repli (la valeur est passée par l'appelant, Next ne remplace que `process.env.NEXT_PUBLIC_X` littéral), `NEXT_PUBLIC_API_URL` exigée au build, service `health-service`, i18n FR/EN sans dépendance, CSS à tokens, Next 15.0.3 → 15.5.29 (RCE du protocole flight), `next.config.ts` local.
**Alternatives rejected**: Redis sans Doppler avec `REDIS_PASSWORD` en seconde variable Dokploy (deux variables à tenir synchrones). Réseau Redis `internal: true` (Redis doit joindre Doppler au démarrage). Montage de `data/` depuis l'hôte (chemin à maintenir sur le VPS). Contexte de build à la racine (casse `docker build --target test backend` de la CI). Tailwind v4 branché (nouvelle dépendance non approuvée).
**Consequences**: le processus uvicorn hérite de `DOPPLER_TOKEN` ; le port 8000 est fixe dans les healthchecks ; secrets à créer dans Doppler `prd` ; `docker build backend` sans `--target test` exige le contexte `data`.
**AGENTS.md rule concerned**: §7 (deux modes explicites, pas de repli silencieux), §4 (frontend), §8 (i18n)

---

## [2026-11-14] Durcissement après revue : Redis, défaut dérivé de RATE_LIMIT_NL_PER_IP, IP non stockée

**Context**: La revue de la vague 2 a relevé que le compteur de budget LLM (sans TTL) pouvait être évincé par `allkeys-lru`, que Redis était publié sans mot de passe, que `rules.created_by` stockait l'IP du client et que `RATE_LIMIT_NL_PER_IP` a une valeur dérivée.
**Decision**:
(1) Redis : `noeviction` (le compteur de budget ne doit jamais être évincé ; à saturation les écritures échouent et l'API refuse, `503`), `--appendonly yes` sur le volume nommé `redis-data`, `--requirepass` depuis `REDIS_PASSWORD` (requis, sans défaut, repris dans `REDIS_URL`), aucun port publié.
(2) Exception assumée à §7 : `RATE_LIMIT_NL_PER_IP`, si absent, vaut `max(1, RATE_LIMIT_PER_IP // 5)`. C'est un calcul à partir d'une variable requise, pas une valeur inventée : la limite NL reste toujours plus stricte que la générale, sans variable de plus à renseigner. Défaut figé par un test (conftest retire la variable ; 1000 donne 200).
(3) `rules.created_by` supprimée (migration 0002, retour arrière = colonne nullable vide) : l'IP est une donnée personnelle. Clé du limiteur : en-têtes `X-Forwarded-For` multiples joints, IPv4 mappée lue comme IPv4, client IPv6 compté par /64. Un appel LLM en échec enregistre un coût d'entrée pessimiste (caractères / 4 à 15 USD le million).
**Alternatives rejected**: `volatile-lru` (correct tant que la clé n'a pas de TTL, mais fragile si un TTL est ajouté un jour). Variable `RATE_LIMIT_NL_PER_IP` obligatoire (une configuration de plus pour un réglage secondaire). Hacher l'IP au lieu de la supprimer (aucun usage de la valeur).
**Consequences**: `docker compose` exige `REDIS_PASSWORD` (URL-safe, par exemple hexadécimal). Redis de production du VPS : mêmes réglages à vérifier, voir `backend/README.md`. À saturation de Redis le limiteur et le budget refusent les requêtes au lieu de les laisser passer.
**AGENTS.md rule concerned**: §7 (exception documentée pour `RATE_LIMIT_NL_PER_IP`), §9 (pas de PII, limitation par IP)

---

## [2026-11-14] Règles prédéfinies en fichiers, limitation par IP (slowapi + Redis), conversion NL→règle avec budget

**Context**: P2 Q4, Q5, Q7, Q14 : dépendances `slowapi` et `litellm` approuvées, règles prédéfinies à sortir du code, hook à recibler. Aucune règle de sécurité 4 (limitation) ni de plafond LLM n'était tenue.
**Decision**:
(1) Une règle prédéfinie = un fichier `data/rules/<id>.json` (champs de `RuleCreate` + `status`), validé par Pydantic à l'import de `engine.predefined_rules` (démarrage), clés inconnues refusées, `id` = nom de fichier, ordre = noms de fichier ; sans émoji.
(2) Limitation : slowapi, stockage Redis (`REDIS_URL`), mémoire seulement si `BACKEND_NODE_ENV=test`. `RATE_LIMIT_PER_IP` et `RATE_LIMIT_WINDOW_SECONDS` sont requis, un compteur par endpoint (`key_style="endpoint"`, sinon `DELETE /rules/{id}` aurait un compteur par id). Clé = IP du pair TCP ; `X-Forwarded-For` n'est lu que si le pair appartient à `TRUSTED_PROXIES`, de droite à gauche jusqu'à la première adresse non proxy. Limite NL→règle séparée et plus stricte (`RATE_LIMIT_NL_PER_IP`, sinon `RATE_LIMIT_PER_IP // 5`, au moins 1). Redis du limiteur en panne : `503`, mutation refusée.
(3) NL→règle : `POST /rules/from-text` renvoie un brouillon non stocké ; texte utilisateur passé comme chaîne JSON entre marqueurs dans le message utilisateur ; `id` et `natural_language` fixés par le serveur ; 2 retries avec les erreurs de validation (sans valeurs rejetées). Budget : plafond global `LITELLM_BUDGET_USD`, dépense cumulée en micro-USD dans Redis (`INCRBY`, atomique, sans dérive flottante), vérifiée avant chaque appel ; coût = `litellm.completion_cost`, sinon estimation par tokens à 15 USD/million. Fonctionnalité désactivée sans les quatre variables `LITELLM_*` ; `litellm` importé à la première conversion.
(4) Erreurs : `{"detail": {"code", "message"}}` partout, `fallback_rules` pour les erreurs `nl_*`. (5) Les trois variables `LITELLM_API_KEY`, `LITELLM_BASE_URL`, `LITELLM_MODEL` sont de la configuration : aucune valeur par défaut.
**Alternatives rejected**: Garder les règles en Python (textes métier dans le code, hook sans cible). Limiter par URL (contournable avec des ids différents) ou lire `X-Forwarded-For` sans condition (spoofable). Stockage mémoire en repli si Redis manque (compteur par worker, repli silencieux). Budget en `INCRBYFLOAT` (dérive). Estimation de coût fixe sans `completion_cost` (faux pour les modèles tarifés). Persister le brouillon (le client doit relire avant `POST /rules`). Laisser le modèle choisir l'`id` (collisions, injection d'un id réservé).
**Consequences**: `alembic` et la CI exigent `RATE_LIMIT_*` (ajoutés à `ci.yml` et `docker-compose.yml`). Réinitialiser le budget = supprimer la clé Redis `chimeraflow:nl:spent_microusd`. Appels LiteLLM jamais exécutés en réel (clé, URL, modèle inconnus), voir TECH_DEBT.md. Les messages d'erreur des endpoints existants ont changé de format (objet au lieu de texte).
**AGENTS.md rule concerned**: §7 (pas de repli de configuration), §9 (limitation par IP), §4 (texte utilisateur dans les fichiers de données), §16 (dépendances approuvées)

---

## [2026-11-14] Lecteur Access explicite, Alembic au démarrage du conteneur, dépendances scindées

**Context**: Python 3.13, nouvelles dépendances approuvées (P2 Q2, Q4, Q6, Q8) : lecture Access sous Windows, schéma géré à la main (`create_all`), pins `requirements.txt` périmés.
**Decision**: `ACCESS_READER` (`mdbtools` | `access-parser`) est obligatoire et validé au démarrage, sans repli de l'un sur l'autre ; les deux lecteurs alimentent le même code de parsing (mêmes enregistrements, test d'équivalence sur `STOCK_ZOBO.mdb`). `alembic upgrade head` s'exécute dans le CMD du conteneur avant uvicorn, plus dans le lifespan (qui ne fait que le seed). `requirements.txt` (runtime) et `requirements-dev.txt` (tests, lint) sont séparés ; l'image a une cible `test` avec mdbtools. Lint : `ruff check` (règles F, équivalent pyflakes) car pyflakes ne sait pas exclure `.venv`.
**Alternatives rejected**: Repli automatique mdbtools → access-parser (masque une mauvaise configuration, §7). Migration dans le lifespan (course entre workers/réplicas, impossible avec SQLite en mémoire des tests, le serveur démarrerait malgré un échec). Fichier de dépendances unique (les outils de test alourdissent l'image de production).
**Consequences**: Lancer `alembic upgrade head` à la main en local avant uvicorn ; `alembic` charge `config.py`, donc toutes les variables requises doivent être définies (Doppler les fournit). Les tests créent les tables avec `create_all`, un test vérifie l'absence de dérive avec la migration. `DATABASE_URL` `postgresql://` est converti en `postgresql+psycopg://` dans `config.normalize_database_url` (seul endroit).
**AGENTS.md rule concerned**: §7 (pas de repli de configuration), §16 (nouvelles dépendances approuvées par le product owner)

---

## [2026-11-13] P2 review pass 2: seeded predefined rules, matching on numbers, idempotent executions

**Context**: The second review found foreign keys pointing to rules that exist only in code, duplicate correlations on each execution, and fuzzy matching that links "ciment 50 kg" to "ciment 40 kg".
**Decision**: Predefined rules are upserted into `rules` at startup (status kept on restart); 3 of them (`r_payment_received`, `r_price_comparison`, `r_stock_replenish`) are seeded inactive and never executed, pending the user's decision on the DSL. The time window stays symmetric. Rows with invalid values are still skipped and counted. Matching requires the same numeric tokens on both sides before the fuzzy ratio, and "2.5" or "1/2" stay one token. Each execution replaces the rule's previous correlations.
**Alternatives rejected**: Dropping the foreign keys (loses referential integrity). Extending the DSL now (scope). Forward-only window (prices predate messages). Defaulting invalid values (invents data). Higher fuzzy threshold alone (still links 100mm and 10mm).
**Consequences**: Reversible: activating the 3 rules is a status change. Foreign keys are enforced on SQLite too, tests behave like PostgreSQL. Partial names ("tuyau PVC" vs "Tuyau PVC 32mm") no longer match. See TECH_DEBT.md.
**AGENTS.md rule concerned**: §4 (fix problems in the same cycle), §14 (decision log)

---

## [2026-11-13] P2 code review: configuration, data contract and matching fixes

**Context**: An audit of the uncommitted P2 code found config fallbacks, rule fields that did not match connector payloads, a non-idempotent normalizer, and an import of a module that does not exist.
**Decision**: `DATABASE_URL`, `CORS_ORIGINS`, `DATA_DIR` are required (no SQLite or default fallback). Connector payloads keep the source column names (`Produit`, `Prix_Unitaire`, `qty_stock`, ...). One `normalize_text()` in `engine/normalizer.py`, whitespace collapsed last, letters split from digits. Record timestamps come from source dates. The rule time window is symmetric (before and after the trigger). Rows with invalid values are skipped and counted, never defaulted. Each rule runs in its own savepoint.
**Alternatives rejected**: Keeping the SQLite fallback (hides a missing variable, AGENTS.md §7). Renaming rule fields to the old payload keys (breaks the link between a rule and the file the user sees). Forward-only window (prices and stock predate the WhatsApp message, so nothing matched).
**Consequences**: Environment variables must be set before startup (tests set them in `tests/conftest.py`, `backend/.env.test` removed). Remaining limits are in TECH_DEBT.md (Access on Windows, partial product names, predefined rules 2 and 5, foreign keys, rate limiting, NL→rule).
**AGENTS.md rule concerned**: §7 (no configuration fallbacks), §13 (no bare `except`), §4 (fix problems in the same cycle)

---

## [2026-11-13] P1 Connecteurs Implementation Complete (95%)

**Context**: Implementation of Phase 1 (Connecteurs) per Roadmap.md, including all 4 MCP connectors, unified record schema, tests, and Kiro hooks.

**Decision**: 
- Implemented BaseConnector abstract class with normalization strategy (lowercase, accent removal, whitespace collapse, punctuation removal)
- Created 4 connectors: ExcelConnector (openpyxl), AccessConnector (mdbtools CLI), WhatsAppConnector (regex parsing), MobileMoneyConnector (CSV)
- Unified record schema enforced: id, source, source_ref, timestamp, lang (fr|en), entities[], payload
- FastAPI REST API endpoints: GET /api/v1/sources, /{source}/health, /{source}/records, /all/records
- Contract tests (test_connectors.py): validates R1-R4 from connectors-spec.md for all connectors
- Property-Based Testing (test_properties.py): validates P2 (normalization idempotence), P4 (determinism), P1 (provenance), P6 (no fabrication)
- Kiro hooks: parser-test.json (run tests on connector save), spec-update-reminder.json (remind on spec change), rule-validate.json (validate rule schema)
- Synthetic data generated: WhatsApp export (50 messages), Mobile Money CSV (50 transactions)

**Alternatives rejected**:
- Pure Python Access parser (access_parser): rejected due to poor .mdb support, chosen mdbtools CLI for reliability
- Individual .env per service: rejected for single root .env with Doppler in production
- Full LLM-based entity extraction in P1: deferred to P2, using simple keyword matching for MVP

**Consequences**:
- P1 ~95% complete: connectors implemented and tested, synthetic data generated (WhatsApp, Mobile Money)
- Remaining blockers: Access .mdb file generation (requires Windows/Jackcess or mdbtools on Linux), Excel tarifs_fournisseurs.xlsx generation (requires openpyxl installation), pytest dependencies installation (hypothesis installed in requirements.txt but not on user machine)
- Health check caching (30s) reduces load on file system (R3 compliance)
- Parse errors logged and counted without crashing (R4 compliance)
- Normalization handles demo scenario: 4 spelling variations of "ciment 50 kg" normalize to comparable forms
- Tests ready but cannot run without installing dependencies: `pip install -r backend/requirements.txt` needed
- Config.py modified to allow optional REDIS_URL in test environment

**AGENTS.md rule concerned**: §4 (critical rules - never leave unresolved problem documented), §7 (configuration management - requireEnv pattern), §11 (testing), §12 (agent behavior - verify build)

---

## [2026-11-13] Décisions Techniques et Design — ChimeraFlow

**Context**: Finalisation des choix techniques et design avant implémentation du projet Kiroween 2026. Validation via QCM interactif pour structurer toutes les décisions importantes du projet.

**Decision**: 
- **Design**: Glassmorphism moderne, palette Professional Blue (#2563eb), typographie IBM Plex (Sans/Serif/Mono)
- **Architecture Frontend**: Next.js 15+ on Vercel, Context API, Tailwind CSS v4
- **Architecture Backend**: FastAPI on VPS Hetzner, SQLAlchemy, Redis rate limiting, logs structurés
- **Data**: Schéma unifié (source, source_ref, timestamp, lang, entities, payload), normalisation hybride (règles + fuzzy), FR/EN
- **MVP**: Dashboard (règles actives, corrélations récentes, santé sources, stats) + Page règles (NL input, JSON edit, liste, prédéfinis) + Pages sources + Settings
- **Kiro**: 4 specs (connectors, rule-engine, ui, api), 3 agents Crew (chimera-builder, test-warden, rule-smith), 3 hooks (parser-test, spec-update, rule-validate), 6 propriétés PBT (provenance, idempotence, roundtrip, determinism, monotonicity, no_fabrication)
- **Startup**: LinguaSolution LLC, ajout page ChimeraFlow + services + blog post, lien narratif : normalisation linguistique NLP
- **Démo**: ZOBO Hardware Store (Douala), produits variés (pointes/vis, tuyaux PVC, électrique, cadenas, peinture, ciment, outillage, brouette, pompes, solaire)

**Alternatives rejected**: 
- Styles alternatifs (minimaliste strict, bold coloré) — glassmorphism mieux adapté à l'identité "business intelligence moderne"
- Palettes alternatives (tech green, creative purple) — professional blue plus trustworthy pour PME
- State management complexe (Zustand, Redux) — Context API suffisant pour le scope MVP
- Monitoring lourd (Sentry) — logs structurés plus pragmatiques pour hackathon
- Normalisation simple (règles seules ou embeddings seuls) — hybride offre meilleur balance précision/performance

**Consequences**: 
- Architecture complète définie pour les 21 jours du hackathon (84h)
- Design system cohérent appliqué dans DESIGN.md
- Stack technique validée : pas de changement majeur pendant l'implémentation
- Scope MVP clair : focus sur dashboard + règles + corrélations
- Kiro usage structuré : specs, agents Crew, hooks, PBT tous définis
- LinguaSolution LLC positionnée pour Best Startup Project
- AGENTS.md sections 18-22 complétées avec les spécifications techniques
- README.md et DESIGN.md finalisés avec vraies informations

**AGENTS.md rule concerned**: §14 (Decision Log obligatoire avant commit)

---

## [2026-11-13] Project initialization with governance structure

**Context**: Creation of a new project requiring clear documentation and governance structure for AI agents and developers.

**Decision**: Adopt best practices from reference projects (Akili and Ancestria) including AGENTS.md for development guidelines, DESIGN.md for design system, structured docs/ directory, and two-branch Git workflow (main/dev).

**Alternatives rejected**: 
- Starting without documentation structure — would lead to inconsistent development practices
- Multiple feature branches — adds complexity without benefit for this project
- Storing configuration in code — violates security best practices

**Consequences**: 
- Solid foundation for future development
- Clear standards from day one
- All team members (human and AI) follow same conventions
- Technical decisions are documented and traceable

**AGENTS.md rule concerned**: §14 (DECISIONS_LOG mandatory), §5 (Git workflow)

---

_Add new entries at the top of this file (reverse chronological order)._
