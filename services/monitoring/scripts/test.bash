#!/bin/bash

HOST='https://monitoring.osparc-master.speag.com/grafana'
DASH_DIR=./../grafana/provisioning2

# Declare a list with the api keys using as a prefix the organization name plus "_" character
declare -a StringArray=("MAIN_eyJrIjoiVXY0dk9Kemdvb0ppa3RxMDRCeXZER0ozdEY5Z0VFTTEiLCJuIjoidGVzdCIsImlkIjoxfQ==")

# Clean previous files
sudo rm -rf "$DASH_DIR"

# Iterate through api keys:
for API_KEY in "${StringArray[@]}"; do
    ORG=$(echo $API_KEY | cut -d "_" -f1) # Name of the organization based on the prefix
    KEY=$(echo $API_KEY | cut -d "_" -f2) # API Key for that organization after removing the prefix

    # Iterate through dashboards using the current API Key
    for dashboard_uid in $(curl -sS -H "Authorization: Bearer eyJrIjoiVXY0dk9Kemdvb0ppa3RxMDRCeXZER0ozdEY5Z0VFTTEiLCJuIjoidGVzdCIsImlkIjoxfQ==" $HOST/api/search\?query\=\& | jq -r '.[] | select( .type | contains("dash-db")) | .uid'); do
        url=`echo $HOST/api/dashboards/uid/$dashboard_uid | tr -d '\r'`
        dashboard_json=$(curl -sS -H "Authorization: Bearer $KEY" $url)
        dashboard_title=$(echo $dashboard_json | jq -r '.dashboard | .title' | sed -r 's/[ \/]+/_/g' )
        dashboard_version=$(echo $dashboard_json | jq -r '.dashboard | .version')
        folder_title="$(echo $dashboard_json | jq -r '.meta | .folderTitle')"

        # You can export the files like this to keep them organized by organization:
        mkdir -p "$DASH_DIR/dashboards/$folder_title/"
        echo $dashboard_json | jq -r {meta:.meta}+.dashboard  > $DASH_DIR/dashboards/$folder_title/${dashboard_version}.json
    done
done


fetch_fields() {
    curl -sSL -f -k -H "Authorization: Bearer eyJrIjoiVXY0dk9Kemdvb0ppa3RxMDRCeXZER0ozdEY5Z0VFTTEiLCJuIjoidGVzdCIsImlkIjoxfQ==" "${HOST}/api/${2}" | jq -r "if type==\"array\" then .[] else . end| .${3}"
}

ORG="MAIN"
KEY="eyJrIjoiVXY0dk9Kemdvb0ppa3RxMDRCeXZER0ozdEY5Z0VFTTEiLCJuIjoidGVzdCIsImlkIjoxfQ=="
DIR="$DASH_DIR"
mkdir -p "$DASH_DIR/datasources"
mkdir -p "$DASH_DIR/alert-notifications"

for id in $(fetch_fields $KEY 'datasources' 'id'); do
    DS=$(echo $(fetch_fields $KEY "datasources/${id}" 'name')|sed 's/ /-/g').json
    echo $DS
    curl -f -k -H "Authorization: Bearer ${KEY}" "${HOST}/api/datasources/${id}" | jq '' > "$DASH_DIR/datasources/${id}.json"
done
for id in $(fetch_fields $KEY 'alert-notifications' 'id'); do
    FILENAME=${id}.json
    echo $FILENAME
    curl -f -k -H "Authorization: Bearer ${KEY}" "${HOST}/api/alert-notifications/${id}" | jq 'del(.created,.updated)' > "$DASH_DIR/alert-notifications/$FILENAME"
done
