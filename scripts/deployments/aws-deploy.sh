#!/bin/bash
#
# Deploy the stack within AWS. The script take the FQDN values (FQDN and monitoring FQDN) from the repo.config file and edit each.env files
#
#

set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

function error_exit
{
    echo
    echo -e "\e[91m${1:-"Unknown Error"}" 1>&2
    exit 1
}

function substitute_environs
{
    # NOTE: be careful that no variable with $ are in .env or they will be replaced by envsubst unless a list of variables is given
       
    envsubst < "${1:-"Missing File"}" > "${2}"
}

function call_make
{
    make --no-print-directory --directory "${1:-"Missing Directory"}" "${2:-"Missing recipe"}"
}

# Using osx support functions
declare psed # fixes shellcheck issue with not finding psed

source "$( dirname "${BASH_SOURCE[0]}" )/../portable.sh"

# Paths
this_script_dir=$(dirname "$0")
repo_basedir=$(realpath "${this_script_dir}"/../../)

# VCS info on current repo
current_git_url=$(git config --get remote.origin.url)
current_git_branch=$(git rev-parse --abbrev-ref HEAD)


# Loads configurations variables
# See https://askubuntu.com/questions/743493/best-way-to-read-a-config-file-in-bash
# shellcheck source=/dev/null
set -o allexport; source "${repo_basedir}"/repo.config; set +o allexport;

# Mails host and login/password

echo "$SMTP_HOST" | grep -Eo "([^.*.*]+)"

echo
echo -e "\e[1;33mDeploying osparc AWS-version on ${MACHINE_FQDN}\e[0m"


# -------------------------------- Simcore -------------------------------

pushd "${repo_basedir}"/services/simcore;

simcore_env=".env"
simcore_compose="docker-compose.deploy.yml"

substitute_environs ${simcore_env}

# for aws use we need http for the traefik entrypoint in simcore. Https is handled by aws
$psed --in-place --expression='s/traefik.http.routers.${PREFIX_STACK_NAME}_webserver.entrypoints=.*/traefik.http.routers.${PREFIX_STACK_NAME}_webserver.entrypoints=http/' ${simcore_compose}
$psed --in-place --expression='s/traefik.http.routers.${PREFIX_STACK_NAME}_webserver.tls=.*/traefik.http.routers.${PREFIX_STACK_NAME}_webserver.tls=false/' ${simcore_compose}

# We don't use a auto-generated root certificate for storage
$psed --in-place --expression='s/\s\s\s\ssecrets:/    #secrets:/' ${simcore_compose}
$psed --in-place --expression='s/\s\s\s\s\s\s- source: rootca.crt/      #- source: rootca.crt/' ${simcore_compose}
$psed --in-place --expression="s~\s\s\s\s\s\s\s\starget: /usr/local/share/ca-certificates/osparc.crt~        #target: /usr/local/share/ca-certificates/osparc.crt~" ${simcore_compose}
$psed --in-place --expression='s~\s\s\s\s\s\s- SSL_CERT_FILE=/usr/local/share/ca-certificates/osparc.crt~      #- SSL_CERT_FILE=/usr/local/share/ca-certificates/osparc.crt~' ${simcore_compose}

# check if changes were done, basically if there are changes in the repo
for path in ${simcore_env} ${simcore_compose}
do
    if ! git diff origin/"${current_git_branch}" --quiet --exit-code $path; then 
        error_exit "${simcore_env} is modified, please commit, push your changes and restart the script";
    fi
done
popd

# -------------------------------- PORTAINER ------------------------------
echo
echo -e "\e[1;33mstarting portainer...\e[0m"
make -C "${repo_basedir}"/services/portainer up-aws


# -------------------------------- TRAEFIK -------------------------------
echo
echo -e "\e[1;33mstarting traefik...\e[0m"
# setup configuration
call_make "${repo_basedir}"/services/traefik up-aws


# -------------------------------- REGISTRY -------------------------------
echo
echo -e "\e[1;33mstarting registry...\e[0m"
make -C "${repo_basedir}"/services/registry up-aws


# -------------------------------- Redis commander-------------------------------
echo
echo -e "\e[1;33mstarting redis commander...\e[0m"
make -C "${repo_basedir}"/services/redis-commander up-aws


# -------------------------------- MONITORING -------------------------------

echo
echo -e "\e[1;33mstarting monitoring...\e[0m"

# grafana config
service_dir="${repo_basedir}"/services/monitoring
substitute_environs "${service_dir}"/grafana/template-config.monitoring "${service_dir}"/grafana/config.monitoring
substitute_environs "${service_dir}"/grafana/provisioning/datasources/datasource.yml.template "${service_dir}"/grafana/provisioning/datasources/datasource.yml
make -C "${service_dir}" up-aws


# -------------------------------- JAEGER -------------------------------
echo
echo -e "\e[1;33mstarting jaeger...\e[0m"
service_dir="${repo_basedir}"/services/jaeger
call_make "${service_dir}" up-aws

# -------------------------------- Adminer -------------------------------
echo
echo -e "\e[1;33mstarting adminer...\e[0m"
service_dir="${repo_basedir}"/services/adminer
call_make "${service_dir}" up-aws

# -------------------------------- Mail -------------------------------
echo
echo -e "\e[1;33mstarting mail server...\e[0m"
service_dir="${repo_basedir}"/services/mail
call_make "${service_dir}" up-aws
#./setup.sh email add support@simcore.io alexamdre

# -------------------------------- GRAYLOG -------------------------------
echo
echo -e "\e[1;33mstarting graylog...\e[0m"

service_dir="${repo_basedir}"/services/graylog
GRAYLOG_ROOT_PASSWORD_SHA2=$(echo -n "$GRAYLOG_ROOT_PASSWORD" | sha256sum | cut -d ' ' -f1)
export GRAYLOG_ROOT_PASSWORD_SHA2
substitute_environs "${service_dir}"/template.env "${service_dir}"/.env
make -C "${service_dir}" up-aws

# Wait for Graylog to start, then send a request configuring one INPUT to allow graylogs to receive logs transmitted by LOGSPOUT
echo
echo "waiting for graylog to run..."
while [ ! $(curl -s -o /dev/null -I -w "%{http_code}" --max-time 10 -H "Accept: application/json" -H "Content-Type: application/json" -X GET https://$MONITORING_DOMAIN/graylog/api/users) = 401 ]; do
    echo "waiting for graylog to run..."
    sleep 5s
done
json_data=$(cat <<EOF
{
"title": "standard GELF UDP input",
    "type": "org.graylog2.inputs.gelf.udp.GELFUDPInput",
    "global": "true",
    "configuration": {
        "bind_address": "0.0.0.0",
        "port":12201
    }
}
EOF
)
curl -u $GRAYLOG_LOGIN:$GRAYLOG_ROOT_PASSWORD --header "Content-Type: application/json" \
    --header "X-Requested-By: cli" -X POST \
    --data "$json_data" https://$MONITORING_DOMAIN/graylog/api/system/inputs
popd



# -------------------------------- DEPlOYMENT-AGENT -------------------------------
echo
echo -e "\e[1;33mstarting deployment-agent for simcore...\e[0m"
pushd "${repo_basedir}"/services/deployment-agent;
if [[ $current_git_url == git* ]]; then
    # it is a ssh style link let's get the organisation name and just replace this cause that conf only accepts https git repos
    current_organisation=$(echo "$current_git_url" | cut -d":" -f2 | cut -d"/" -f1)
    $psed --in-place "s|https://github.com/ITISFoundation/osparc-ops.git|https://github.com/$current_organisation/osparc-ops.git|" deployment_config.default.yaml
else
    $psed --in-place "/- id: simcore-ops-repo/{n;s|url:.*|url: $current_git_url|}" deployment_config.default.yaml
fi
$psed --in-place "/- id: simcore-ops-repo/{n;n;s|branch:.*|branch: $current_git_branch|}" deployment_config.default.yaml

# Add environment variable that will be used by the simcore stack when deployed with the deployment-agent
YAML_STRING="environment:\n        S3_ENDPOINT: ${S3_ENDPOINT}\n        S3_ACCESS_KEY: ${ACCESS_KEY_ID}\n        S3_SECRET_KEY: ${SECRET_ACCESS_KEY}"
$psed --in-place "s~environment: {}~$YAML_STRING~" deployment_config.default.yaml
# update in case there is already something in "environment: {}"
$psed --in-place "s/S3_ENDPOINT:.*/S3_ENDPOINT: ${S3_ENDPOINT}/" deployment_config.default.yaml
$psed --in-place "s~S3_ACCESS_KEY:.*~S3_ACCESS_KEY: ${ACCESS_KEY_ID}~" deployment_config.default.yaml
$psed --in-place "s~S3_SECRET_KEY:.*~S3_SECRET_KEY: ${SECRET_ACCESS_KEY}~" deployment_config.default.yaml

# We don't use Minio and postgresql with AWS
$psed --in-place "s~excluded_services:.*~excluded_services: [webclient, minio, postgres]~" deployment_config.default.yaml
make down up;
popd