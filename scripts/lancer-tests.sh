#!/usr/bin/env bash
# Lance tous les tests dans Docker (PostgreSQL 14 + Python 3.11), comme la CI. Rien n'est installé sur la machine.
#   ./scripts/lancer-tests.sh             tous les tests
#   ./scripts/lancer-tests.sh collecte    un seul service (utilisateurs, etablissements, collecte, analyses, infra, function)
set -euo pipefail
cd "$(dirname "$0")/.."

RESEAU=beacom-tests
PG=beacom-tests-pg
docker network inspect "$RESEAU" >/dev/null 2>&1 || docker network create "$RESEAU" >/dev/null
if ! docker ps --format '{{.Names}}' | grep -qx "$PG"; then
  docker rm -f "$PG" >/dev/null 2>&1 || true
  docker run -d --rm --name "$PG" --network "$RESEAU" \
    -e POSTGRES_USER=beacom -e POSTGRES_PASSWORD=beacom postgres:14-alpine >/dev/null
fi
until docker exec "$PG" pg_isready -U beacom >/dev/null 2>&1; do sleep 1; done

docker run --rm --network "$RESEAU" -v "$PWD":/src:ro -v beacom-pip-cache:/root/.cache/pip \
  -e TEST_PG_ADMIN_URL="postgresql://beacom:beacom@$PG:5432/postgres" \
  -e PYTHONDONTWRITEBYTECODE=1 -e CIBLE="${1:-}" \
  python:3.11-slim bash -c '
    set -euo pipefail
    cp -r /src /tmp/depot && cd /tmp/depot
    pip install -q --root-user-action=ignore --disable-pip-version-check -r requirements-dev.txt \
      -r service-utilisateurs/requirements.txt -r service-collecte/requirements.txt \
      -r function-nlp/requirements.txt
    statut=0
    for cible in utilisateurs etablissements collecte analyses infra function; do
      [ -n "$CIBLE" ] && [ "$CIBLE" != "$cible" ] && continue
      case $cible in
        infra) dossier=infra ;;
        function) dossier=function-nlp ;;
        *) dossier=service-$cible ;;
      esac
      [ -d "$dossier/tests" ] || continue
      echo "=== $dossier"
      (cd "$dossier" && python -m pytest -q -p no:cacheprovider tests) || statut=1
    done
    exit $statut
  '
