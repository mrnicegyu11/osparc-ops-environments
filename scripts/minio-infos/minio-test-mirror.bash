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


echo "Infos for Simcore bucket :  ${S3_BUCKET}"
docker run \
-v /etc/ssl/certs:/etc/ssl/certs:ro \
--network host \
--env MC_HOST_myminioMaster="https://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@${S3_ENDPOINT}" \
--env MC_HOST_myminioDalco="https://gfhfgh765gjtyjtj:fjghjgjdsdg345@storage.osparc.speag.com" \
minio/mc mirror myminioMaster/${S3_BUCKET} myminioDalco/${S3_BUCKET} --watch