#!/bin/bash
# Garde-fou de la config statique de Traefik (Dokploy) pour ChimeraFlow.
#
# Vérifie dans /etc/dokploy/traefik/traefik.yml :
#   - entryPoints.websecure.forwardedHeaders.trustedIPs contient les IP de la copie de référence
#     (172.18.0.1/32, passerelle Docker vue par Traefik derrière cloudflared) ;
#   - api.insecure n'est pas activé (le tableau de bord n'est pas servi sans authentification).
# En cas de dérive : sauvegarde, correction de ces deux clés seulement (le reste du fichier est
# conservé), puis `docker restart dokploy-traefik`. Sans dérive : aucune écriture, aucun redémarrage.
# Contrôle aussi le conteneur (pas d'argument --api.insecure, montage du secret DNS-01) : journalise
# une erreur et sort avec le code 3 si le conteneur a été recréé sans ces éléments.
#
# Variables (essais) : TRAEFIK_FILE, REFERENCE_FILE, STATE_DIR, BACKUP_DIR, DRY_RUN=1,
# SKIP_RESTART=1, SKIP_CONTAINER_CHECKS=1. Codes de sortie : 0 conforme ou corrigé, 1 échec du
# redémarrage, 2 configuration du garde-fou invalide, 3 conteneur non conforme, 4 dérive non corrigeable.
set -u

TRAEFIK_FILE="${TRAEFIK_FILE:-/etc/dokploy/traefik/traefik.yml}"
REFERENCE_FILE="${REFERENCE_FILE:-/etc/dokploy/traefik/traefik.yml.chimeraflow-reference}"
CONTAINER="${TRAEFIK_CONTAINER:-dokploy-traefik}"
SECRET_HOST_FILE="${SECRET_HOST_FILE:-/etc/dokploy/secrets/cf_dns_api_token}"
SECRET_MOUNT="${SECRET_MOUNT:-/run/secrets/cf_dns_api_token}"
STATE_DIR="${STATE_DIR:-/var/lib/check-traefik-config}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/check-traefik-config}"
DRY_RUN="${DRY_RUN:-0}"
SKIP_RESTART="${SKIP_RESTART:-0}"
SKIP_CONTAINER_CHECKS="${SKIP_CONTAINER_CHECKS:-0}"
FAILURE_COOLDOWN_SECONDS="${FAILURE_COOLDOWN_SECONDS:-3600}"
TAG="check-traefik-config"

umask 077
mkdir -p "$STATE_DIR" "$BACKUP_DIR"
PENDING_FLAG="$STATE_DIR/restart-pending"
FAILURE_STAMP="$STATE_DIR/last-failure"

# Sous systemd (stdout non terminal) le préfixe <N> fixe la priorité dans le journal.
# En interactif on écrit aussi dans le journal avec `logger` pour garder une trace.
log() {
  local level="$1"; shift
  local prio=6
  case "$level" in err) prio=3 ;; warning) prio=4 ;; esac
  if [ -t 1 ]; then
    echo "[$level] $*"
    logger -t "$TAG" -p "user.$level" -- "$*"
  else
    echo "<$prio>$*"
  fi
}

exec 9>"$STATE_DIR/lock"
if ! flock -n 9; then
  log info "autre exécution en cours, rien à faire"
  exit 0
fi

# Recréation du conteneur par Dokploy en cours : ne pas interférer.
if [ "$SKIP_CONTAINER_CHECKS" != "1" ] && docker inspect dokploy-traefik-previous >/dev/null 2>&1; then
  log info "dokploy-traefik-previous présent (recréation Dokploy en cours), passage ignoré"
  exit 0
fi

# --- 1. Vérification et correction du fichier (YAML) -----------------------------------------------
py_out="$(
  TRAEFIK_FILE="$TRAEFIK_FILE" REFERENCE_FILE="$REFERENCE_FILE" BACKUP_DIR="$BACKUP_DIR" DRY_RUN="$DRY_RUN" \
  python3 - <<'PY'
import ipaddress, os, re, shutil, sys, time

target = os.environ["TRAEFIK_FILE"]
reference = os.environ["REFERENCE_FILE"]
backup_dir = os.environ["BACKUP_DIR"]
dry_run = os.environ.get("DRY_RUN") == "1"

def say(level, message):
    print(f"{level}|{message}")

try:
    import yaml
except ImportError:
    yaml = None

def dig(node, *keys):
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node

def norm(value):
    try:
        return str(ipaddress.ip_network(str(value), strict=False))
    except ValueError:
        return None

if yaml is None:
    # Repli sans PyYAML : détection stricte par expressions régulières, aucune correction.
    try:
        text = open(target, encoding="utf-8").read()
        ref_text = open(reference, encoding="utf-8").read()
    except OSError as exc:
        say("err", f"lecture impossible : {exc.strerror}")
        sys.exit(2)
    insecure_on = re.search(r"^api:\s*\n(?:[ \t]+.*\n)*?[ \t]+insecure:\s*true\b", text, re.M) is not None
    has_ip = "172.18.0.1/32" in text
    if insecure_on or (not has_ip and "172.18.0.1/32" in ref_text):
        say("err", "dérive détectée mais PyYAML absent : correction manuelle requise")
        sys.exit(4)
    say("info", "conforme (contrôle par expressions régulières, PyYAML absent)")
    sys.exit(0)

def load(path):
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError("document YAML racine invalide")
    return data

try:
    ref = load(reference)
except (OSError, ValueError, yaml.YAMLError) as exc:
    say("err", f"copie de référence illisible ({type(exc).__name__}) : {reference}")
    sys.exit(2)

wanted = dig(ref, "entryPoints", "websecure", "forwardedHeaders", "trustedIPs")
wanted_norm = [norm(ip) for ip in wanted] if isinstance(wanted, list) else []
if not wanted_norm or None in wanted_norm:
    say("err", "la référence doit définir entryPoints.websecure.forwardedHeaders.trustedIPs (IP/CIDR valides)")
    sys.exit(2)
if dig(ref, "api", "insecure") is not False:
    say("err", "la référence doit définir api.insecure: false")
    sys.exit(2)

try:
    cfg = load(target)
except (OSError, ValueError, yaml.YAMLError) as exc:
    # Fichier absent ou invalide : ne rien écraser, laisser un humain décider.
    say("err", f"{target} illisible ou invalide ({type(exc).__name__}), aucune correction automatique")
    sys.exit(4)

def drift(config):
    problems = []
    current = dig(config, "entryPoints", "websecure", "forwardedHeaders", "trustedIPs")
    current_norm = {norm(ip) for ip in current} if isinstance(current, list) else set()
    missing = [ip for ip in wanted_norm if ip not in current_norm]
    if missing:
        problems.append("trustedIPs manquant(s) sous websecure : " + ", ".join(missing))
    insecure = dig(config, "api", "insecure")
    if insecure not in (None, False):
        problems.append(f"api.insecure vaut {insecure!r}")
    return problems

problems = drift(cfg)
if not problems:
    say("info", "conforme : trustedIPs et api.insecure corrects")
    sys.exit(0)

for problem in problems:
    say("warning", "dérive : " + problem)
if dry_run:
    say("info", "DRY_RUN : aucune écriture")
    sys.exit(12)

# Correction minimale des deux clés, le reste de la structure est conservé.
entry_points = cfg.setdefault("entryPoints", {}) if isinstance(cfg.get("entryPoints", {}), dict) else None
websecure = entry_points.setdefault("websecure", {}) if entry_points is not None and isinstance(entry_points.get("websecure", {}), dict) else None
if websecure is None:
    say("err", "entryPoints.websecure n'est pas un mapping : correction manuelle requise")
    sys.exit(4)
forwarded = websecure.get("forwardedHeaders")
if not isinstance(forwarded, dict):
    forwarded = websecure["forwardedHeaders"] = {}
ips = forwarded.get("trustedIPs")
if not isinstance(ips, list):
    ips = forwarded["trustedIPs"] = []
present = {norm(ip) for ip in ips}
for raw in wanted:
    if norm(raw) not in present:
        ips.append(str(raw))
        present.add(norm(raw))
api = cfg.get("api")
if isinstance(api, dict) and api.get("insecure") not in (None, False):
    api["insecure"] = False
elif not isinstance(api, dict) and api is not None:
    cfg["api"] = {"insecure": False}

text = yaml.safe_dump(cfg, sort_keys=False, default_flow_style=False, allow_unicode=True, width=1000)
if drift(yaml.safe_load(text)):
    say("err", "la correction ne produit pas un fichier conforme, abandon")
    sys.exit(4)

stamp = time.strftime("%Y%m%d%H%M%S")
saved = os.path.join(backup_dir, f"traefik.yml.{stamp}-{os.getpid()}")
shutil.copy2(target, saved)
backups = sorted(f for f in os.listdir(backup_dir) if f.startswith("traefik.yml."))
for old in backups[:-20]:
    os.remove(os.path.join(backup_dir, old))

# Écriture sur place : même inode, mêmes droits (le fichier est monté tel quel dans le conteneur).
with open(target, "r+", encoding="utf-8") as handle:
    handle.seek(0)
    handle.write(text)
    handle.truncate()
    handle.flush()
    os.fsync(handle.fileno())
say("warning", f"fichier corrigé (sauvegarde : {saved})")
sys.exit(10)
PY
)"
py_rc=$?
while IFS='|' read -r level message; do
  [ -n "${level:-}" ] && log "$level" "$message"
done <<< "$py_out"

exit_code=0
case "$py_rc" in
  0) ;;
  10) [ "$SKIP_RESTART" = "1" ] || touch "$PENDING_FLAG" ;;
  12) exit 0 ;;
  *) exit "$py_rc" ;;
esac

# --- 2. Redémarrage si le fichier a été corrigé (ou si un redémarrage précédent a échoué) ----------
if [ -f "$PENDING_FLAG" ] && [ "$SKIP_RESTART" != "1" ]; then
  if [ -f "$FAILURE_STAMP" ] && [ $(( $(date +%s) - $(cat "$FAILURE_STAMP") )) -lt "$FAILURE_COOLDOWN_SECONDS" ]; then
    log err "redémarrage échoué récemment, nouvelle tentative après le délai de repos"
    exit 1
  fi
  if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
    log err "conteneur $CONTAINER introuvable, redémarrage impossible"
    exit 1
  fi
  before="$(docker inspect -f '{{.State.StartedAt}}' "$CONTAINER")"
  timeout 90 docker restart "$CONTAINER" >/dev/null 2>&1
  sleep 6
  after="$(docker inspect -f '{{.State.StartedAt}}' "$CONTAINER")"
  running="$(docker inspect -f '{{.State.Running}}' "$CONTAINER")"
  sleep 4
  stable="$(docker inspect -f '{{.State.StartedAt}}' "$CONTAINER")"
  if [ "$running" = "true" ] && [ "$after" != "$before" ] && [ "$after" = "$stable" ]; then
    rm -f "$PENDING_FLAG" "$FAILURE_STAMP"
    log warning "$CONTAINER redémarré, configuration appliquée"
  else
    date +%s > "$FAILURE_STAMP"
    log err "$CONTAINER ne reste pas démarré après le redémarrage : restaurer la sauvegarde de $BACKUP_DIR"
    exit 1
  fi
fi

# --- 3. Contrôles du conteneur (journalisation seule, aucune recréation automatique) ---------------
if [ "$SKIP_CONTAINER_CHECKS" != "1" ]; then
  if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
    log err "conteneur $CONTAINER introuvable"
    exit 3
  fi
  cmdline="$(docker inspect -f '{{.Path}} {{range .Args}}{{.}} {{end}}{{range .Config.Cmd}}{{.}} {{end}}' "$CONTAINER")"
  if printf '%s' "$cmdline" | grep -Eq -- '--api(\.|=|[[:space:]]|$)'; then
    log err "arguments du conteneur contenant --api* (tableau de bord possiblement réactivé)"
    exit_code=3
  fi
  if [ -f "$SECRET_HOST_FILE" ] && ! docker inspect -f '{{range .Mounts}}{{.Destination}} {{end}}' "$CONTAINER" | grep -qF -- "$SECRET_MOUNT"; then
    log err "montage $SECRET_MOUNT absent : conteneur recréé sans le secret DNS-01, renouvellements de certificats en danger (voir ops/vps/README.md)"
    exit_code=3
  fi
fi

exit "$exit_code"
