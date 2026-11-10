#!/bin/sh
# Points the API at an image tag that was already built locally, then checks /health.
# Example: ops/rollback.sh local
set -eu
tag=${1:?usage: ops/rollback.sh <image-tag>}
cd "$(dirname "$0")/.."

if ! docker image inspect "bus-booking-api:${tag}" >/dev/null 2>&1; then
    echo "Image bus-booking-api:${tag} is not present locally. Build it before rolling back." >&2
    exit 1
fi

IMAGE_TAG="$tag" docker compose up -d --no-build api
echo "Waiting for the API healthcheck"
i=0
until docker compose exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready')" >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -gt 30 ]; then
        echo "API did not become ready on tag ${tag}" >&2
        docker compose logs --tail=50 api >&2
        exit 1
    fi
    sleep 2
done
docker compose exec -T api python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
echo "api is serving bus-booking-api:${tag}"
