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
    echo "usage: s3-data-migration.bash [--rm ] [--create] [--copy]"
    echo "--rm : Delete the destination bucket"
    echo "--create : Create the destination bucket"
    echo "--cp : Copy data from the old bucket to the destination one"
}

rm=false
create=false
cp=false

for var in "$@"
do
    if [ "$var" = "--rm" ]; then
        rm=true
    elif [ "$var" = "--create" ]; then
        create=true
    elif [ "$var" = "--cp" ]; then
        cp=true
    else
        usage
        exit
    fi
done

base_docker_run="docker run \
        -v /etc/ssl/certs:/etc/ssl/certs:ro \
        --network host \
        --env MC_HOST_old=""https://${S3_OLD_ACCESS_KEY}:${S3_OLD_SECRET_KEY}@${S3_OLD_ENDPOINT}"" \
        --env MC_HOST_new=""https://${S3_ACCESS_KEY}:${S3_SECRET_KEY}@${S3_ENDPOINT}"" \
        minio_custom:0.1"

if [ "$rm" = true ]; then
    read -p "Are you sure ? You are going to delete ${S3_ENDPOINT} / ${S3_BUCKET_DATA} (y/n)? " yn
    if [ "$yn" = "y" ]; then
        echo "Deleting bucket from  ${S3_ENDPOINT} / ${S3_BUCKET_DATA}"
        "$base_docker_run" rb --force new/${S3_BUCKET_DATA}
    fi
fi

if [ "$create" = true ]; then
    echo "Creating  ${S3_ENDPOINT} / ${S3_BUCKET_DATA} bucket"
    docker build --tag minio_custom:0.1 .
    "$base_docker_run" mb new/${S3_BUCKET_DATA}
fi


if [ "$cp" = true ]; then
    echo "migrating data from ${S3_OLD_ENDPOINT} / ${S3_OLD_BUCKET_DATA} to ${S3_ENDPOINT} / ${S3_BUCKET_DATA}"
    docker build --tag minio_custom:0.1 .
    "$base_docker_run" cp --recursive  old/${S3_OLD_BUCKET_DATA}/ new/${S3_BUCKET_DATA} || true
fi

