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


# Set local and public ips in repo.config
MANAGER_PRIVATE_ENDPOINT_IP=$(get_this_private_ip)
MANAGER_PUBLIC_ENDPOINT_IP=$(get_this_public_ip)
$psed --in-place "s/MANAGER_PRIVATE_ENDPOINT_IP=.*/MANAGER_PRIVATE_ENDPOINT_IP=${MANAGER_PRIVATE_ENDPOINT_IP}/" "${repo_basedir}"/repo.config
$psed --in-place "s/MANAGER_PUBLIC_ENDPOINT_IP=.*/MANAGER_PUBLIC_ENDPOINT_IP=${MANAGER_PUBLIC_ENDPOINT_IP}/" "${repo_basedir}"/repo.config

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

substitute_environs template${simcore_env} ${simcore_env}

$psed --in-place --expression='s/\s\s\s\ssecrets:/    #secrets:/' ${simcore_compose}
$psed --in-place --expression='s/\s\s\s\s\s\s- source: rootca.crt/      #- source: rootca.crt/' ${simcore_compose}
$psed --in-place --expression="s~\s\s\s\s\s\s\s\starget: /usr/local/share/ca-certificates/osparc.crt~        #target: /usr/local/share/ca-certificates/osparc.crt~" ${simcore_compose}
$psed --in-place --expression='s~\s\s\s\s\s\s- SSL_CERT_FILE=/usr/local/share/ca-certificates/osparc.crt~      #- SSL_CERT_FILE=/usr/local/share/ca-certificates/osparc.crt~' ${simcore_compose}

substitute_environs template.${simcore_compose} ${simcore_compose}

# check if changes were done, basically if there are changes in the repo
for path in ${simcore_env} ${simcore_compose}
do
    if ! git diff origin/"${current_git_branch}" --quiet --exit-code $path; then 
        error_exit "${simcore_env} or ${simcore_compose}  is modified, please commit, push your changes and restart the script";
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
pushd "${repo_basedir}"/services/mail;

if [ -d "${repo_basedir}/services/mail/config" ]
then
    echo "Config already created for mail..."
else
    echo "Adding configuration for ${SMTP_USERNAME}"
    bash setup.sh email add ${SMTP_USERNAME} ${SMTP_PASSWORD}
    bash setup.sh email add root@${MACHINE_FQDN} ${SMTP_PASSWORD}
    bash setup.sh email add devops@${MACHINE_FQDN} ${SMTP_PASSWORD}
    bash setup.sh email add code-of-conduct@${MACHINE_FQDN} ${SMTP_PASSWORD}
    bash setup.sh alias add root guidon@speag.swiss
    bash setup.sh alias add support osparcio-support@speag.swiss
    bash setup.sh alias add devops osparcio-devops@speag.swiss
    bash setup.sh alias add code-of-conduct neagu@itis.swiss
fi

echo -e "\e[1;33mstarting mail server...\e[0m"
call_make "${repo_basedir}"/services/mail up-aws
popd

# -------------------------------- GRAYLOG -------------------------------
echo
echo -e "\e[1;33mstarting graylog...\e[0m"
service_dir="${repo_basedir}"/services/graylog
call_make "${service_dir}" up-aws
call_make "${service_dir}" configure-instance



# -------------------------------- DEPlOYMENT-AGENT -------------------------------
echo
echo -e "\e[1;33mstarting deployment-agent for simcore...\e[0m"
pushd "${repo_basedir}"/services/deployment-agent;
agent_compose_default="deployment_config.default.yaml"
if [[ $current_git_url == git* ]]; then
    # it is a ssh style link let's get the organisation name and just replace this cause that conf only accepts https git repos
    current_organisation=$(echo "$current_git_url" | cut -d":" -f2 | cut -d"/" -f1)
    $psed --in-place "s|https://github.com/ITISFoundation/osparc-ops.git|https://github.com/$current_organisation/osparc-ops.git|" ${agent_compose_default}
else
    $psed --in-place "/- id: simcore-ops-repo/{n;s|url:.*|url: $current_git_url|}" ${agent_compose_default}
fi
$psed --in-place "/- id: simcore-ops-repo/{n;n;s|branch:.*|branch: $current_git_branch|}" ${agent_compose_default}

# Add environment variable that will be used by the simcore stack when deployed with the deployment-agent
YAML_STRING="environment:\n        S3_ENDPOINT: ${S3_ENDPOINT}\n        S3_ACCESS_KEY: ${S3_ACCESS_KEY}\n        S3_SECRET_KEY: ${S3_SECRET_KEY}"
$psed --in-place "s~environment: {}~$YAML_STRING~" ${agent_compose_default}
# update in case there is already something in "environment: {}"
$psed --in-place "s/S3_ENDPOINT:.*/S3_ENDPOINT: ${S3_ENDPOINT}/" ${agent_compose_default}
$psed --in-place "s~S3_ACCESS_KEY:.*~S3_ACCESS_KEY: ${S3_ACCESS_KEY}~" ${agent_compose_default}
$psed --in-place "s~S3_SECRET_KEY:.*~S3_SECRET_KEY: ${S3_SECRET_KEY}~" ${agent_compose_default}
# portainer
$psed --in-place "/- url: .*portainer:9000/{n;s/username:.*/username: ${SERVICES_USER}/}" ${agent_compose_default}
$psed --in-place "/- url: .*portainer:9000/{n;n;s/password:.*/password: ${SERVICES_PASSWORD}/}" ${agent_compose_default}
# extra_hosts
$psed --in-place "s|extra_hosts: \[\]|extra_hosts:\n        - \"${MACHINE_FQDN}:${MANAGER_PRIVATE_ENDPOINT_IP}\n ${MONITORING_DOMAIN}:${MANAGER_PRIVATE_ENDPOINT_IP}\n ${REGISTRY_DOMAIN}:${MANAGER_PRIVATE_ENDPOINT_IP}\n ${API_DOMAIN}:${MANAGER_PRIVATE_ENDPOINT_IP} \"|" ${agent_compose_default}
#Update
$psed --in-place "/extra_hosts:/{n;s/- .*/- \"${MACHINE_FQDN}:${MANAGER_PRIVATE_ENDPOINT_IP}\n ${MONITORING_DOMAIN}:${MANAGER_PRIVATE_ENDPOINT_IP}\n ${REGISTRY_DOMAIN}:${MANAGER_PRIVATE_ENDPOINT_IP}\n ${API_DOMAIN}:${MANAGER_PRIVATE_ENDPOINT_IP}\"/}" ${agent_compose_default}

# We don't use Minio and postgresql with AWS
$psed --in-place "s~excluded_services:.*~excluded_services: [webclient, minio, postgres]~" ${agent_compose_default}
make down up;
popd