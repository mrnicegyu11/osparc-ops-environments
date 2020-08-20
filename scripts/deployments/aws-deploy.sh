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
    make --no-print-directory --directory "${1:-"Missing Directory"}" "${@:2:$#}"
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

# Generate WEBSERVER_SESSION_SECRET_KEY if the key is empty in repo.config
if [[ -z "${WEBSERVER_SESSION_SECRET_KEY}" ]]; then
    echo "Creation of a new webserver session key..."
    WEBSERVER_SESSION_SECRET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key())")
    # TODO 
    #$WEBSERVER_SESSION_SECRET_KEY = ${${WEBSERVER_SESSION_SECRET_KEY}//\'/\'} # Espace ' characters
    $psed --in-place "s/WEBSERVER_SESSION_SECRET_KEY=.*/WEBSERVER_SESSION_SECRET_KEY=${WEBSERVER_SESSION_SECRET_KEY}/" "${repo_basedir}"/repo.config
    set -o allexport; source "${repo_basedir}"/repo.config; set +o allexport;
fi

echo
echo -e "\e[1;33mDeploying osparc AWS-version on ${MACHINE_FQDN}\e[0m"


# -------------------------------- Simcore -------------------------------
echo
echo -e "Updating if necessary docker-compose-deploy and .env in Sincore..."
pushd "${repo_basedir}"/services/simcore;
make -C "${repo_basedir}"/services/simcore compose-dalco

simcore_env=.env
simcore_compose=docker-compose.deploy.yml
# check if changes were done, basically if there are changes in the repo
for path in ${simcore_env} ${simcore_compose}
do
    if ! git diff origin/"${current_git_branch}" --quiet --exit-code $path; then 
        error_exit "${simcore_env} or ${simcore_compose}  is modified, please commit, push your changes and restart the script";
    fi
done
popd

# TODO Configure for different stacks and not only dalco
if [ $1 != "--simcore_only" ]; then

    # -------------------------------- PORTAINER ------------------------------
    echo
    echo -e "\e[1;33mstarting portainer...\e[0m"
    make -C "${repo_basedir}"/services/portainer up-letsencrypt-dns

    # -------------------------------- TRAEFIK -------------------------------
    echo
    echo -e "\e[1;33mstarting traefik...\e[0m"
    # setup configuration
    call_make "${repo_basedir}"/services/traefik up-dalco

    # -------------------------------- Redis commander-------------------------------
    echo
    echo -e "\e[1;33mstarting redis commander...\e[0m"
    make -C "${repo_basedir}"/services/redis-commander up-letsencrypt-dns

    # -------------------------------- MONITORING -------------------------------

    echo
    echo -e "\e[1;33mstarting monitoring...\e[0m"
    # grafana config
    service_dir="${repo_basedir}"/services/monitoring
    make -C "${service_dir}" up-letsencrypt-dns

    # -------------------------------- JAEGER -------------------------------
    echo
    echo -e "\e[1;33mstarting jaeger...\e[0m"
    service_dir="${repo_basedir}"/services/jaeger
    call_make "${service_dir}" up-letsencrypt-dns

    # -------------------------------- Adminer -------------------------------
    echo
    echo -e "\e[1;33mstarting adminer...\e[0m"
    service_dir="${repo_basedir}"/services/adminer
    call_make "${service_dir}" up-letsencrypt-dns

    # -------------------------------- REGISTRY -------------------------------
    echo
    echo -e "\e[1;33mstarting registry...\e[0m"
    make -C "${repo_basedir}"/services/registry up-letsencrypt-dns

    # -------------------------------- Minio -------------------------------
    # In the .env, MINIO_NUM_MINIOS and MINIO_NUM_PARTITIONS need to be set at 1 to work without labelling the nodes with minioX=true

    echo
    echo -e "\e[1;33mstarting minio...\e[0m"
    service_dir="${repo_basedir}"/services/minio
    call_make "${repo_basedir}"/services/minio up-letsencrypt-dns

    echo "waiting for minio to run...don't worry..."
    while [ ! "$(curl -s -o /dev/null -I -w "%{http_code}" --max-time 10 https://"${STORAGE_DOMAIN}"/minio/health/ready)" = 200 ]; do
        echo "waiting for minio to run..."
        sleep 5s
    done

    # -------------------------------- Mail -------------------------------
    echo
    echo -e "\e[1;33mstarting mail server...\e[0m"
    call_make "${repo_basedir}"/services/mail up

    # -------------------------------- GRAYLOG -------------------------------
    echo
    echo -e "\e[1;33mstarting graylog...\e[0m"
    service_dir="${repo_basedir}"/services/graylog
    call_make "${service_dir}" up-letsencrypt-dns configure-instance
fi



# -------------------------------- DEPlOYMENT-AGENT -------------------------------
echo
echo -e "\e[1;33mstarting deployment-agent for simcore...\e[0m"
pushd "${repo_basedir}"/services/deployment-agent;
make down up;
popd