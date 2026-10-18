#!/usr/bin/env bash
# Sobe só o backend do OrbiBots e o Postgres deste compose.
# Não para outros projetos, não faz prune e não recarrega o Nginx.
set -euo pipefail

case "${ORBIBOTS_ENV:-}" in
  staging)
    deploy_dir=/opt/orbibots-backend/staging
    port=3220
    project=orbibots-api-staging
    ;;
  production)
    deploy_dir=/opt/orbibots-backend/production
    port=3221
    project=orbibots-api-production
    ;;
  *)
    echo "Ambiente recusado: ${ORBIBOTS_ENV:-vazio}" >&2
    exit 1
    ;;
esac

case "${ORBIBOTS_IMAGE:-}" in
  ghcr.io/heinrick7/orbibots-backend:*) ;;
  *)
    echo "Imagem recusada: ${ORBIBOTS_IMAGE:-vazia}" >&2
    exit 1
    ;;
esac

cd "$deploy_dir"
test -f .env
export ORBIBOTS_PORT="$port"
export COMPOSE_PROJECT_NAME="$project"
export DOCKER_CONFIG=/opt/orbibots-backend/.docker
set -a
# shellcheck disable=SC1091
source .env
set +a

docker compose -p "$project" -f docker-compose.yml config --quiet

container_id="$(docker compose -p "$project" -f docker-compose.yml ps -q api 2>/dev/null || true)"
previous_image=""
if [[ -n "$container_id" ]]; then
  previous_image="$(docker inspect "$container_id" --format '{{.Config.Image}}')"
fi

docker compose -p "$project" -f docker-compose.yml pull api
if ! docker compose -p "$project" -f docker-compose.yml up -d --wait; then
  echo "A nova versão não ficou saudável." >&2
  if [[ -n "$previous_image" ]]; then
    echo "Restaurando ${previous_image}" >&2
    ORBIBOTS_IMAGE="$previous_image" docker compose -p "$project" -f docker-compose.yml up -d --wait --no-deps api || true
  fi
  exit 1
fi

docker compose -p "$project" -f docker-compose.yml ps
