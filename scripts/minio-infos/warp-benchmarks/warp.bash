#!/bin/bash
#
# Execute mixed test on minio and put then in a file
#
#
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'
source ../../repo.config



results=$(docker run \
-v /etc/ssl/certs:/etc/ssl/certs:ro \
--network public-network \
--env WARP_HOST="minio{1...4}:9000" \
--env WARP_ACCESS_KEY="gfhfgh765gjtyjtj" \
--env WARP_SECRET_KEY="fjghjgjdsdg345" \
minio/warp mixed --analyze.v)


if [ -f "warp_results" ]
then 
    rm "warp_results" && touch "warp_results"
fi

echo "$results" > "warp_results"