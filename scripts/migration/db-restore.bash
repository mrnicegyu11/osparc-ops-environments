#!/bin/bash
#
# Extract the database from the current host and copy it in a new host
#
#
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'
source .env

echo "Droping and recreating the database in the destination host"
docker run -it --rm \
-v /tmp:/var/pgdata \
jbergknoff/postgresql-client postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:5432/postgres \
-c "DROP DATABASE simcoredb;" -c "CREATE DATABASE simcoredb;" \
-c "CREATE ROLE grafanareader with LOGIN ENCRYPTED PASSWORD '${POSTGRES_GRAFANA_PASSWORD}';" \
-c "\connect simcoredb" -f "/var/pgdata/mydump.sql"
rm /tmp/mydump.sql