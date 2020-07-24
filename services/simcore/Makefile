.DEFAULT_GOAL := help
SECRET=$(shell cat << EndOfMessage \
	secrets: \
      - source: rootca.crt \
        target: /usr/local/share/ca-certificates/osparc.crt"\
		EndOfMessage)


# Internal VARIABLES ------------------------------------------------
# STACK_NAME defaults to name of the current directory. Should not to be changed if you follow GitOps operating procedures.
STACK_NAME = $(notdir $(shell pwd))
SWARM_HOSTS = $(shell docker node ls --format={{.Hostname}} 2>/dev/null)
TEMP_COMPOSE=docker-compose.deploy.yml
# Host machine IP
MACHINE_IP = $(shell source $(realpath $(CURDIR)/../../scripts/portable.sh) && get_this_private_ip)
# TARGETS --------------------------------------------------
include ../../scripts/common.Makefile

.PHONY: configure # Update the configuration from the template and repo.config file
configure: .env ${TEMP_COMPOSE}


# Helpers -------------------------------------------------


.PHONY: ${TEMP_COMPOSE}
${TEMP_COMPOSE}: template.docker-compose.deploy.yml
	set -o allexport; \
	export SECRET="$$SECRET"
	set +o allexport; \
	envsubst < $< > $@