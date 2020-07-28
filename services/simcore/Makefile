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


.PHONY: up-local
up-local: .env ${TEMP_COMPOSE}-local

.PHONY: up-aws
up-aws: .env ${TEMP_COMPOSE}-aws  


.PHONY: ${TEMP_COMPOSE}-local
${TEMP_COMPOSE}-local: install-snap docker-compose.yml docker-compose.deploy.local.yml
	@yq m $< docker-compose.deploy.local.yml > ${TEMP_COMPOSE}		

.PHONY: ${TEMP_COMPOSE}-aws
${TEMP_COMPOSE}-aws: install-snap docker-compose.yml
	@cp docker-compose.yml ${TEMP_COMPOSE}

.PHONY: install-snap
install-snap:
	@sudo snap list | grep yq > /dev/null 2>&1;\
	testSnap=$$?;\
	[ "$$testSnap" -eq 0 ] || sudo snap install yq