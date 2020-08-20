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


.PHONY: compose-local ## Create docker-compose.deploy for local deployment
compose-local: .env ${TEMP_COMPOSE}-local

.PHONY: compose-letsencrypt-http ## Create docker-compose.deploy for letsencrypt with http challenge deployment
compose-letsencrypt-http: .env ${TEMP_COMPOSE}-letsencrypt-http  

.PHONY: compose-letsencrypt-dns ## Create docker-compose.deploy for letsencrypt with http dns deployment
compose-letsencrypt-dns: .env ${TEMP_COMPOSE}-letsencrypt-http 

.PHONY: compose-dalco ## Create docker-compose.deploy for Daclo cluster
compose-dalco: .env ${TEMP_COMPOSE}-dalco 

.PHONY: ${TEMP_COMPOSE}-local
${TEMP_COMPOSE}-local: install-yq docker-compose.yml docker-compose.deploy.local.yml
	@yq m  docker-compose.yml docker-compose.deploy.local.yml > ${TEMP_COMPOSE}

.PHONY: ${TEMP_COMPOSE}-letsencrypt-http
${TEMP_COMPOSE}-letsencrypt-http: install-yq docker-compose.yml docker-compose.deploy.letsencrypt.http.yml
	@yq m  docker-compose.yml docker-compose.deploy.letsencrypt.http.yml > ${TEMP_COMPOSE}

.PHONY: ${TEMP_COMPOSE}-letsencrypt-dns
${TEMP_COMPOSE}-letsencrypt-dns: install-yq docker-compose.yml docker-compose.deploy.letsencrypt.dns.yml
	@yq m  docker-compose.yml docker-compose.deploy.letsencrypt.dns.yml > ${TEMP_COMPOSE}	

.PHONY: ${TEMP_COMPOSE}-aws
${TEMP_COMPOSE}-aws: install-yq docker-compose.yml
	@cp docker-compose.yml ${TEMP_COMPOSE}

.PHONY: ${TEMP_COMPOSE}-dalco
${TEMP_COMPOSE}-dalco: install-yq docker-compose.yml docker-compose.deploy.dalco.yml docker-compose.deploy.letsencrypt.dns.yml
	@yq merge docker-compose.yml docker-compose.deploy.dalco.yml docker-compose.deploy.letsencrypt.dns.yml > ${TEMP_COMPOSE}		

.PHONY: install-yq
install-yq:
	@dpkg -s yq > /dev/null 2>&1;\
	testYqInstalled=$$?;\
	[ "$$testYqInstalled" -eq 0 ] || ( sudo apt-key adv --keyserver keyserver.ubuntu.com --recv-keys CC86BB64 \
	&& sudo add-apt-repository -y ppa:rmescandon/yq \
	&& sudo apt update; sudo apt install -y yq );