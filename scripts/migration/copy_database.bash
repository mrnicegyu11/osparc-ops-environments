#!/bin/bash
#
# Deploys in local host
#
#
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'
source .env

docker run \
-v /tmp:/var/pgdata -it --rm --entrypoint pg_dump \   
jbergknoff/postgresql-client -h ${POSTGRES_ORIGIN_HOST} -U ${POSTGRES_ORIGIN_USER} -p ${POSTGRES_ORIGIN_PASSWORD} \
-f /var/pgdata/mydump.sql ${POSTGRES_ORIGIN_DB}


