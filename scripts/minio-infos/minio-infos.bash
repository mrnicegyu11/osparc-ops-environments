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

# List of buckets

list_bucket=$(docker run \
-v /etc/ssl/certs:/etc/ssl/certs:ro \
--network host \
--env MC_HOST_myminio="https://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@${S3_ENDPOINT}" \
minio/mc ls myminio)

buckets=$(echo "$list_bucket" | awk '{ FS=" "; print $5 }')

# Thanks to https://stackoverflow.com/questions/24628076/convert-multiline-string-to-array
SAVEIFS=$IFS   # Save current IFS
IFS=$'\n'      # Change IFS to new line
buckets=($buckets) # split to array $names
IFS=$SAVEIFS   # Restore IFS

for (( i=0; i<${#buckets[@]}; i++ ))
do
    echo "Infos for bucket ${buckets[$i]} : "
    docker run \
    -v /etc/ssl/certs:/etc/ssl/certs:ro \
    --network host \
    --env MC_HOST_myminio="https://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@${S3_ENDPOINT}" \
    minio/mc ls -r --json myminio/${buckets[$i]} | awk '{ FS=","; print $4 }' | awk '{ FS=":"; n+=$2 } END{ print n }' | xargs echo "0.000000001*" | bc | awk '{print $1" GB"}'
done