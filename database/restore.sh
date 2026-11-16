#!/bin/sh
set -eu

set -- /backups/auth_db-*.dump
[ -f "$1" ] || { echo "No auth_db backup found in /backups" >&2; exit 1; }
auth_backup=$(ls -1t "$@" | head -n 1)

set -- /backups/banco_db-*.dump
[ -f "$1" ] || { echo "No banco_db backup found in /backups" >&2; exit 1; }
bank_backup=$(ls -1t "$@" | head -n 1)

pg_restore --clean --if-exists --no-owner --dbname=auth_db "$auth_backup"
pg_restore --clean --if-exists --no-owner --dbname=banco_db "$bank_backup"
echo "Restored auth_db and banco_db from the latest validated backups"
