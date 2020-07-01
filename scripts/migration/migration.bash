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

echo "Making a backup of the current database in tmp/mydump.dump..."
docker run \
-v /tmp:/var/pgdata \
--env PGPASSWORD=${POSTGRES_ORIGIN_PASSWORD} \
--network monitored_network \
-it --rm --entrypoint pg_dump jbergknoff/postgresql-client \
--host=${POSTGRES_ORIGIN_HOST} --username=${POSTGRES_ORIGIN_USER} \
--format=c --data-only \
--file=/var/pgdata/mydump.dump ${POSTGRES_ORIGIN_DB}	

echo "Droping and recreating the database in the destination host"
source ../../repo.config
docker run -it --rm \
jbergknoff/postgresql-client postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:5432/postgres \
 -c "DROP DATABASE simcoredb;" -c "CREATE DATABASE simcoredb;"


echo "Making the migrations to the destination host"
git clone https://github.com/ITISFoundation/osparc-simcore.git
python3 -m venv venv
source venv/bin/activate
pip install osparc-simcore/packages/postgres-database/.[migration]
sc-pg discover --user ${POSTGRES_USER} --password ${POSTGRES_PASSWORD} \
--host ${POSTGRES_HOST} --database ${POSTGRES_DB}
sc-pg upgrade
rm -rf osparc-simcore

echo "Restoring the data into the destination host"
docker run \
-v /tmp:/var/pgdata \
--env PGPASSWORD=${POSTGRES_PASSWORD} \
--network monitored_network \
-it --rm --entrypoint pg_restore jbergknoff/postgresql-client \
--host=${POSTGRES_HOST} --username=${POSTGRES_USER} \
--no-owner --dbname=${POSTGRES_DB} /var/pgdata/mydump.dump


echo "migrating S3 data.." 
docker build --tag minio_custom:0.1 .
docker run \
-v /etc/ssl/certs:/etc/ssl/certs:ro \
--network host \
--env MC_HOST_local="https://${S3_OLD_ACCESS_KEY}:${S3_OLD_SECRET_KEY}@${S3_OLD_ENDPOINT}" \
--env MC_HOST_aws="https://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@${S3_ENDPOINT}" \
minio_custom:0.1 rb --force --dangerous aws/${S3_BUCKET} || true

docker run \
-v /etc/ssl/certs:/etc/ssl/certs:ro \
--network host \
--env MC_HOST_local="https://${S3_OLD_ACCESS_KEY}:${S3_OLD_SECRET_KEY}@${S3_OLD_ENDPOINT}" \
--env MC_HOST_aws="https://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@${S3_ENDPOINT}" \
minio_custom:0.1 rb --force --dangerous aws/${S3_BUCKET_REGISTRY} || true

docker run \
-v /etc/ssl/certs:/etc/ssl/certs:ro \
--network host \
--env MC_HOST_local="https://${S3_OLD_ACCESS_KEY}:${S3_OLD_SECRET_KEY}@${S3_OLD_ENDPOINT}" \
--env MC_HOST_aws="https://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@${S3_ENDPOINT}" \
minio_custom:0.1 mb aws/${S3_BUCKET} 

docker run \
-v /etc/ssl/certs:/etc/ssl/certs:ro \
--network host \
--env MC_HOST_local="https://${S3_OLD_ACCESS_KEY}:${S3_OLD_SECRET_KEY}@${S3_OLD_ENDPOINT}" \
--env MC_HOST_aws="https://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@${S3_ENDPOINT}" \
minio_custom:0.1 mb aws/${S3_BUCKET_REGISTRY} 

docker run \
-v /etc/ssl/certs:/etc/ssl/certs:ro \
--network host \
--env MC_HOST_local="https://${S3_OLD_ACCESS_KEY}:${S3_OLD_SECRET_KEY}@${S3_OLD_ENDPOINT}" \
--env MC_HOST_aws="https://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@${S3_ENDPOINT}" \
minio_custom:0.1 cp --recursive  local/${S3_OLD_BUCKET}/ aws/${S3_BUCKET}

docker run \
-v /etc/ssl/certs:/etc/ssl/certs:ro \
--network host \
--env MC_HOST_local="https://${S3_OLD_ACCESS_KEY}:${S3_OLD_SECRET_KEY}@${S3_OLD_ENDPOINT}" \
--env MC_HOST_aws="https://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@${S3_ENDPOINT}" \
minio_custom:0.1 cp --recursive  local/${S3_OLD_BUCKET_REGISTRY}/ aws/${S3_BUCKET}