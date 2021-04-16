#!/bin/bash
#
# Ask for minio a JWT token that prometheus will use to access his metrics
#
#
# http://redsymbol.net/articles/unofficial-bash-strict-mode/

docker exec -it $(docker container ls  | grep 'minio' | awk '{print $1}')   
curl https://dl.min.io/client/mc/release/linux-amd64/mc --output mc; \
chmod +x mc; \
ls;\
pwd;\
./mc alias set local https://storage.${MACHINE_FQDN} ${S3_ACCESS_KEY} ${S3_SECRET_KEY}; \
./mc admin prometheus generate local;