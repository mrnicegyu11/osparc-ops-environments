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
# Parse the different FQDNS in repo.config and convert them into traefik typo
MACHINE_FQDNS_TRAEFIK=$(shell set -o allexport; \
	source $(realpath $(CURDIR)/../../repo.config); \
	if [ -z "$${MACHINE_FQDNS}" ]; then \
		MACHINE_FQDNS_TRAEFIK="Host(\`$$MACHINE_FQDN\`)"; \
	else \
		IFS=', ' read -r -a hosts <<< "$${MACHINE_FQDNS}"; \
		MACHINE_FQDNS_TRAEFIK="Host(\`$$MACHINE_FQDN\`)"; \
		count=0; \
		for element in "$${hosts[@]}"; \
		do \
			if (( count > 0 )); then \
				MACHINE_FQDNS_TRAEFIK="$$MACHINE_FQDNS_TRAEFIK || Host(\`$$element\`)"; \
			fi; \
		count=$$((count+1)); \
		done; \
		MACHINE_FQDNS_TRAEFIK="$$MACHINE_FQDNS_TRAEFIK"; \
	fi; \
	echo $$MACHINE_FQDNS_TRAEFIK; \
	set +o allexport; )
# Host machine IP
MACHINE_IP = $(shell source $(realpath $(CURDIR)/../../scripts/portable.sh) && get_this_private_ip)
# TARGETS --------------------------------------------------
include ../../scripts/common.Makefile

.PHONY: configure 
configure: .env-simcore ${TEMP_COMPOSE} ## Update the configuration from the template and repo.config file

.PHONY: compose-local 
compose-local: .env-simcore ${TEMP_COMPOSE}-local ## Create docker-compose.deploy for local deployment

.PHONY: compose-letsencrypt-http 
compose-letsencrypt-http: .env-simcore ${TEMP_COMPOSE}-letsencrypt-http ## Create docker-compose.deploy for letsencrypt with http challenge deployment

.PHONY: compose-letsencrypt-dns 
compose-letsencrypt-dns: .env-simcore ${TEMP_COMPOSE}-letsencrypt-http ## Create docker-compose.deploy for letsencrypt with http dns deployment

.PHONY: compose-dalco 
compose-dalco: .env-simcore ${TEMP_COMPOSE}-dalco ## Create docker-compose.deploy for Daclo cluster

.PHONY: compose-aws 
compose-aws: .env-simcore ${TEMP_COMPOSE}-aws ## Create docker-compose.deploy for AWS


.PHONY: ${TEMP_COMPOSE}-local
${TEMP_COMPOSE}-local: docker-compose.yml docker-compose.deploy.local.yml
	@$(_yq) merge --append  docker-compose.yml docker-compose.deploy.local.yml > ${TEMP_COMPOSE}

.PHONY: ${TEMP_COMPOSE}-letsencrypt-http
${TEMP_COMPOSE}-letsencrypt-http: docker-compose.yml docker-compose.deploy.letsencrypt.http.yml
	@$(_yq) merge --append  docker-compose.yml docker-compose.deploy.letsencrypt.http.yml > ${TEMP_COMPOSE}

.PHONY: ${TEMP_COMPOSE}-letsencrypt-dns
${TEMP_COMPOSE}-letsencrypt-dns: docker-compose.yml docker-compose.deploy.letsencrypt.dns.yml
	@$(_yq) merge --append  docker-compose.yml docker-compose.deploy.letsencrypt.dns.yml > ${TEMP_COMPOSE}	

.PHONY: ${TEMP_COMPOSE}-aws
${TEMP_COMPOSE}-aws: 
	@$(_yq) merge --append docker-compose.yml docker-compose.deploy.aws.yml docker-compose.deploy.letsencrypt.dns.yml > ${TEMP_COMPOSE}

.PHONY: ${TEMP_COMPOSE}-dalco
${TEMP_COMPOSE}-dalco: docker-compose.yml docker-compose.deploy.dalco.yml docker-compose.deploy.letsencrypt.dns.yml
	@$(_yq) merge --append docker-compose.yml docker-compose.deploy.dalco.yml docker-compose.deploy.letsencrypt.dns.yml > ${TEMP_COMPOSE}

.PHONY: .env-simcore
.env-simcore: template.env ../../repo.config
	@set -o allexport; \
	source $(realpath $(CURDIR)/../../repo.config); \
	export MACHINE_FQDNS_TRAEFIK='${MACHINE_FQDNS_TRAEFIK}'; \
	set +o allexport; \
	envsubst < $< >.env
