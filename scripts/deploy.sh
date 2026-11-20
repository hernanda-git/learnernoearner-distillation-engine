#!/usr/bin/env bash
# Deploy Project Proteus to the production VPS.
#
# Usage:
#   scripts/deploy.sh              # push main, reset the host to origin/main, restart
#   scripts/deploy.sh --no-push    # deploy the current local HEAD (already pushed)
#
# Overrides: PROTEUS_DEPLOY_HOST, PROTEUS_DEPLOY_DIR, PROTEUS_DEPLOY_BRANCH,
#            PROTEUS_DEPLOY_SERVICES.
set -euo pipefail

HOST="${PROTEUS_DEPLOY_HOST:-valarion@46.202.155.192}"
APP_DIR="${PROTEUS_DEPLOY_DIR:-/home/valarion/apps/learnernoearner-distillation-engine}"
BRANCH="${PROTEUS_DEPLOY_BRANCH:-main}"
SERVICES="${PROTEUS_DEPLOY_SERVICES:-proteus-paper-daemon proteus-web}"
PUBLIC_URL="${PROTEUS_DEPLOY_URL:-https://engine.warga-digital.com}"

cd "$(git rev-parse --show-toplevel)"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "refusing to deploy: working tree is dirty" >&2
  exit 1
fi

if [[ "${1:-}" != "--no-push" ]]; then
  git push origin "$BRANCH"
fi

echo "deploying $(git rev-parse --short HEAD) to $HOST:$APP_DIR"
# shellcheck disable=SC2086  # SERVICES is an intentional word list
ssh "$HOST" bash -s -- "$APP_DIR" "$BRANCH" $SERVICES <<'REMOTE'
set -euo pipefail
app_dir="$1"
branch="$2"
shift 2

cd "$app_dir"
git fetch --quiet origin "$branch"
git reset --hard "origin/$branch"
sudo -n systemctl restart "$@"
for attempt in 1 2 3 4 5; do
  sleep 2
  if systemctl is-active --quiet "$@"; then
    systemctl is-active "$@"
    exit 0
  fi
done
echo "services failed to become active:" >&2
systemctl status "$@" --no-pager >&2 || true
exit 1
REMOTE

curl -fsS --max-time 20 "$PUBLIC_URL/api/v1/alpha" >/dev/null
echo "live: $PUBLIC_URL/api/v1/alpha ok"
