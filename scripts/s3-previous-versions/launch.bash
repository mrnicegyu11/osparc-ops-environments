#!/bin/bash
# This script restore S3 objects to a previous versionnized state
# 

set -o nounset
set -o pipefail
IFS=$'\n\t'

set -o allexport
source .env
set +o allexport
git clone https://github.com/angeloc/s3-pit-restore
cd s3-pit-restore
s3-pit-restore $@
cd ..
rm -rf s3-pit-restore