# Garde-fou de la config Traefik (VPS)

Copies des fichiers installés sur le VPS `hetzner-1` pour que la config statique de Traefik (`/etc/dokploy/traefik/traefik.yml`, partagée avec les autres applications du propriétaire) garde deux réglages demandés par ChimeraFlow :

- `entryPoints.websecure.forwardedHeaders.trustedIPs` contient `172.18.0.1/32` (Traefik conserve alors l'IP du visiteur dans `X-Forwarded-For`) ;
- `api.insecure` n'est pas activé (le tableau de bord de Traefik n'est pas servi sans authentification).

## Ce que Dokploy v0.31.0 fait (lu dans le code, tag `v0.31.0`)

| Action | Effet | Code |
|---|---|---|
| Settings → Web Server → Traefik → **Reload** (`settings.reloadTraefik`) | `docker restart dokploy-traefik` seulement. Fichier et conteneur inchangés | `apps/dokploy/server/api/routers/settings.ts` (`reloadTraefik`), `packages/server/src/services/settings.ts` (`reloadDockerResource`) |
| Démarrage ou mise à jour de Dokploy | `createDefaultTraefikConfig()` ne crée le fichier que s'il est absent (ou s'il est un dossier). Un fichier existant n'est jamais réécrit | `packages/server/src/setup/traefik-setup.ts`, appelé par `apps/dokploy/server/server.ts` |
| Éditeur de la config principale (`settings.updateTraefikConfig`) | Écrit tel quel le texte enregistré. Dokploy ne garde rien en base : le fichier est l'unique source (`readTraefikConfig` le relit) | `routers/settings.ts`, `packages/server/src/utils/traefik/web-server.ts` (`writeMainConfig`) |
| `settings.toggleRequests`, changement de l'e-mail Let's Encrypt | Lit puis réécrit le YAML (clés conservées, commentaires perdus) | `routers/settings.ts`, `web-server.ts` (`updateLetsEncryptEmail`) |
| **Toggle dashboard**, **ports** (`updateTraefikPorts`), **variables d'environnement** (`writeTraefikEnv`), **mise à jour de version** (`updateTraefik`) | **Recréent le conteneur** (`writeTraefikSetup` → `initializeStandaloneTraefik`). `traefik.yml` n'est pas touché, mais le conteneur est recréé avec seulement 3 montages : le montage du secret DNS-01 est perdu et l'image devient `traefik:v${TRAEFIK_VERSION}` (3.7.16 par défaut, la variable n'est pas posée sur le service `dokploy`) | `routers/settings.ts`, `traefik-setup.ts` (`recreateStandaloneTraefik`) |
| Toggle dashboard | Ne modifie pas `api.insecure` : il publie seulement le port 8080 de l'hôte | `routers/settings.ts` (`toggleDashboard`) |
| Installation / configuration d'un serveur distant | Concerne les serveurs ajoutés à Dokploy, pas ce VPS. Ne réécrit pas un fichier existant | `packages/server/src/setup/server-setup.ts` |

Conclusion : un **Reload** ne perd rien. Le fichier n'est réécrit que par une édition manuelle (éditeur, `toggleRequests`, e-mail Let's Encrypt) ou s'il disparaît. Une **recréation** du conteneur garde le fichier mais perd le montage du secret DNS-01 (le garde-fou le signale sans le réparer). Le toggle du tableau de bord reste à ne pas utiliser.

## Ce que fait le garde-fou

`check-traefik-config.sh` tourne toutes les 5 minutes (`check-traefik-config.timer`, unité `check-traefik-config.service`).

1. Lit le fichier et la copie de référence `/etc/dokploy/traefik/traefik.yml.chimeraflow-reference` avec PyYAML (sans PyYAML : détection seule par expressions régulières, aucune correction).
2. Sans dérive : aucune écriture, aucun redémarrage.
3. Avec dérive : sauvegarde dans `/var/backups/check-traefik-config/` (20 dernières), ajout des IP manquantes à `trustedIPs` (les autres IP sont conservées) et `api.insecure: false`, le reste du fichier est conservé (les commentaires sont perdus). Écriture sur place (même inode, mêmes droits), puis `docker restart dokploy-traefik` et vérification que le conteneur reste démarré. Si le redémarrage échoue, une nouvelle tentative n'a lieu qu'après 1 h.
4. Ne fait rien si Dokploy est en train de recréer le conteneur (`dokploy-traefik-previous` présent).
5. Contrôle le conteneur : aucun argument `--api*`, montage `/run/secrets/cf_dns_api_token` présent. Sinon, erreur dans le journal et code de sortie 3 (l'unité apparaît en échec). Il ne recrée jamais le conteneur : voir `.cloudflare-backup\r6-traefik-recreate.sh` dans les notes du VPS.

Fichier illisible ou invalide : aucune écriture, code de sortie 4.

## Installation

Sur le VPS, en root, depuis ce dossier :

```
install -m 755 check-traefik-config.sh /usr/local/sbin/check-traefik-config.sh
install -m 644 check-traefik-config.service check-traefik-config.timer /etc/systemd/system/
cp -p /etc/dokploy/traefik/traefik.yml /etc/dokploy/traefik/traefik.yml.chimeraflow-reference
systemctl daemon-reload && systemctl enable --now check-traefik-config.timer
```

La copie de référence doit être faite quand `traefik.yml` est correct. Si les IP de confiance changent un jour, mettre la référence à jour (le garde-fou ne retire jamais d'IP).

## Vérification

```
DRY_RUN=1 /usr/local/sbin/check-traefik-config.sh          # affiche la dérive éventuelle, n'écrit rien
systemctl start check-traefik-config.service
journalctl -t check-traefik-config -n 20 --no-pager -o cat
systemctl list-timers check-traefik-config.timer
```

Essai sans toucher à la production, sur une copie : `TRAEFIK_FILE=/tmp/t.yml STATE_DIR=/tmp/s BACKUP_DIR=/tmp/b SKIP_RESTART=1 SKIP_CONTAINER_CHECKS=1 /usr/local/sbin/check-traefik-config.sh`.

Après toute opération Traefik : `https://chimeraflow-api.linguasolution.com/health` renvoie 200 et `X-Forwarded-For` commence par l'IP du visiteur (voir `docs/deployment/PRODUCTION.md`).

## Retrait

```
systemctl disable --now check-traefik-config.timer
rm /etc/systemd/system/check-traefik-config.{service,timer} /usr/local/sbin/check-traefik-config.sh
rm -r /var/lib/check-traefik-config
systemctl daemon-reload
```

La copie de référence et les sauvegardes (`/var/backups/check-traefik-config/`) peuvent être gardées ou supprimées. Retour à l'état d'avant les réglages : copier `/etc/dokploy/traefik/traefik.yml.bak-chimeraflow-20261116200929` sur `traefik.yml`, puis `docker restart dokploy-traefik`.
