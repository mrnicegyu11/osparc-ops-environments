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

echo "migrating S3 data.."
docker build --tag minio_custom:0.1 .

echo "migrating data from ${S3_OLD_BUCKET_REGISTRY} to ${S3_BUCKET_REGISTRY}"
docker run \
-v /etc/ssl/certs:/etc/ssl/certs:ro \
--network host \
--env MC_HOST_local="https://${S3_OLD_ACCESS_KEY}:${S3_OLD_SECRET_KEY}@${S3_OLD_ENDPOINT}" \
--env MC_HOST_aws="https://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@${S3_ENDPOINT}" \
minio_custom:0.1 cp --recursive  local/${S3_OLD_BUCKET_REGISTRY}/ aws/${S3_BUCKET_REGISTRY} || true