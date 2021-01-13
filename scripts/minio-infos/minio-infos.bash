#!/bin/bash
#
# Give current usage about minio buckets in GB
#
#
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'
source ../../repo.config

docker build --tag minio_custom:0.1 .

echo "Infos for Simcore bucket :  ${S3_BUCKET}"
docker run \
-v /etc/ssl/certs:/etc/ssl/certs:ro \
--network host \
--env MC_HOST_myminio="https://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@${S3_ENDPOINT}" \
minio_custom:0.1 ls -r --json myminio/${S3_BUCKET} | awk '{ FS=","; print $4 }' | awk '{ FS=":"; n+=$2 } END{ print n }' | xargs echo "0.000000001*" | bc | awk '{print $1" GB"}'


echo "Infos for registry bucket :  ${REGISTRY_S3_BUCKET}"
docker run \
-v /etc/ssl/certs:/etc/ssl/certs:ro \
--network host \
--env MC_HOST_myminio="https://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@${S3_ENDPOINT}" \
minio_custom:0.1 ls -r --json myminio/${REGISTRY_S3_BUCKET} | awk '{ FS=","; print $4 }' | awk '{ FS=":"; n+=$2 } END{ print n }' | xargs echo "0.000000001*" | bc | awk '{print $1" GB"}'