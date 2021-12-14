.DEFAULT_GOAL := help


# Internal VARIABLES ------------------------------------------------
# STACK_NAME defaults to name of the current directory. Should not to be changed if you follow GitOps operating procedures.
STACK_NAME = $(notdir $(shell pwd))
SWARM_HOSTS = $(shell docker node ls --format={{.Hostname}} 2>/dev/null)
TEMP_COMPOSE=.stack.${STACK_NAME}.yaml


# Makefile including function used by every services
include ../../scripts/common.Makefile

.PHONY: up
up: .env ${TEMP_COMPOSE}  ## Deploys maintenance page stack
	docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE} ${STACK_NAME}

.PHONY: up-dalco 
up-dalco: up ## Deploys maintenance page stack for Dalco Cluster

.PHONY: up-aws
up-aws: up ## Deploys maintenance page stack for aws Cluster

.PHONY: up-master 
up-master: up ## Deploys maintenance page stack for Master Cluster

# Helpers -------------------------------------------------

.PHONY: ${TEMP_COMPOSE}
${TEMP_COMPOSE}: docker-compose.yml
	@docker-compose -f $< --log-level=ERROR config > $@


# Parse the different FQDNS in repo.config and convert them into traefik typo and add the service rule
MACHINE_FQDNS_TRAEFIK=$(shell set -o allexport; \
	source $(realpath $(CURDIR)/../../repo.config); \
	if [ -z "$${MACHINE_FQDNS}" ]; then \
		MACHINE_FQDNS_TRAEFIK="Host(\`$$MACHINE_FQDN\`) || HostRegexp(\`services.$$MACHINE_FQDN\`,\`{subhost:[a-zA-Z0-9-]+}.services.$$MACHINE_FQDN\`)"; \
	else \
		IFS=', ' read -r -a hosts <<< "$${MACHINE_FQDNS}"; \
		MACHINE_FQDNS_TRAEFIK="Host(\`$$MACHINE_FQDN\`)"; \
		count=0; \
		for element in "$${hosts[@]}"; \
		do \
			if (( count > 0 )); then \
				MACHINE_FQDNS_TRAEFIK="$$MACHINE_FQDNS_TRAEFIK || Host(\`$$element\`) || HostRegexp(\`services.$$element\`,\`{subhost:[a-zA-Z0-9-]+}.services.$$element\`)";\
			else\
				MACHINE_FQDNS_TRAEFIK="$$MACHINE_FQDNS_TRAEFIK || HostRegexp(\`services.$$element\`,\`{subhost:[a-zA-Z0-9-]+}.services.$$element\`)";\
			fi; \
		count=$$((count+1)); \
		done; \
		MACHINE_FQDNS_TRAEFIK="$$MACHINE_FQDNS_TRAEFIK"; \
	fi; \
	echo $$MACHINE_FQDNS_TRAEFIK; \
	set +o allexport; )

.PHONY: .env
.env: template.env ../../repo.config
	@set -o allexport; \
	source $(realpath $(CURDIR)/../../repo.config); \
	export MACHINE_FQDNS_TRAEFIK='${MACHINE_FQDNS_TRAEFIK}'; \
	set +o allexport; \
	envsubst < $< >.env