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


usage()
{
    echo "usage: db-backup.sh [-n --network]"
    echo "-n --network : Add the network monitored_network to be able to connect to the pgsql service (When the pgsql server is in a swarm)"
}

network="--network=""bridge"""

for var in "$@"
do
    if [ "$var" = "-n" ] || [ "$var" = "--network" ]; then
        network="--network=""monitored_network"""
    else
        usage
        exit
    fi
done

echo "Making a backup of the current database in tmp/mydump.sql..."
docker run \
-v /tmp:/var/pgdata \
--env PGPASSWORD=${POSTGRES_ORIGIN_PASSWORD} \
"${network}" \
-it --rm --entrypoint pg_dump jbergknoff/postgresql-client \
--host=${POSTGRES_ORIGIN_HOST} --username=${POSTGRES_ORIGIN_USER} \
--file=/var/pgdata/mydump.sql ${POSTGRES_ORIGIN_DB} --no-owner