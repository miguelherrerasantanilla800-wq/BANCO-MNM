#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ $# -gt 1 ]]; then
    printf 'Usage: %s [--no-build]\n' "${0##*/}" >&2
    exit 2
fi

case "${1:-}" in
    "")
        BUILD=true
        ;;
    --no-build)
        BUILD=false
        ;;
    --help|-h)
        printf 'Usage: %s [--no-build]\n' "${0##*/}"
        printf 'Start Banco MNM with Docker Compose; images are built by default.\n'
        exit 0
        ;;
    *)
        printf 'Unknown option: %s\nUsage: %s [--no-build]\n' "$1" "${0##*/}" >&2
        exit 2
        ;;
esac

command -v docker >/dev/null 2>&1 || {
    printf 'Docker is required. Install Docker Engine and the Compose v2 plugin.\n' >&2
    exit 1
}
command -v python3 >/dev/null 2>&1 || {
    printf 'Python 3 is required to validate the local configuration.\n' >&2
    exit 1
}
docker compose version >/dev/null

CREATED_ENV=false
if [[ ! -f .env ]]; then
    cp .env.example .env
    CREATED_ENV=true
fi

if [[ "$CREATED_ENV" == true ]]; then
    python3 - <<'PY'
import base64
import os
import secrets
from pathlib import Path

path = Path(".env")
lines = path.read_text(encoding="utf-8").splitlines()
secret_values = {
    "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
    "JWT_SECRET": secrets.token_urlsafe(48),
    "AIRFLOW_POSTGRES_PASSWORD": secrets.token_urlsafe(32),
    "AIRFLOW_FERNET_KEY": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii"),
    "AIRFLOW_WEBSERVER_SECRET_KEY": secrets.token_urlsafe(48),
    "AIRFLOW_ADMIN_PASSWORD": secrets.token_urlsafe(24),
    "GRAFANA_ADMIN_PASSWORD": secrets.token_urlsafe(24),
}
found = set()
updated = []
for line in lines:
    if "=" not in line or line.lstrip().startswith("#"):
        updated.append(line)
        continue
    key, value = line.split("=", 1)
    if key in secret_values:
        updated.append(f"{key}={secret_values[key]}")
        found.add(key)
    else:
        updated.append(line)

for key, value in secret_values.items():
    if key not in found:
        updated.append(f"{key}={value}")

temporary = path.with_suffix(".env.tmp")
temporary.write_text("\n".join(updated) + "\n", encoding="utf-8")
os.chmod(temporary, 0o600)
os.replace(temporary, path)
PY
else
    python3 - <<'PY'
import sys
from pathlib import Path

values = {}
for line in Path(".env").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.lstrip().startswith("#"):
        key, value = line.split("=", 1)
        values[key] = value

required = (
    "POSTGRES_PASSWORD",
    "JWT_SECRET",
    "AIRFLOW_POSTGRES_PASSWORD",
    "AIRFLOW_FERNET_KEY",
    "AIRFLOW_WEBSERVER_SECRET_KEY",
    "AIRFLOW_ADMIN_PASSWORD",
    "GRAFANA_ADMIN_PASSWORD",
)
placeholders = ("replace-with", "change-this", "generate-")
invalid = [
    key for key in required
    if not values.get(key) or values[key].startswith(placeholders)
]
if invalid:
    print(
        "Replace the template values in .env before starting: "
        + ", ".join(invalid),
        file=sys.stderr,
    )
    raise SystemExit(1)
PY
    chmod 600 .env
fi

compose_args=(up --detach)
if [[ "$BUILD" == true ]]; then
    compose_args+=(--build)
fi
docker compose "${compose_args[@]}"
docker compose ps
