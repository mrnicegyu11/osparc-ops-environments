.DEFAULT_GOAL := help


# Internal VARIABLES ------------------------------------------------
# STACK_NAME defaults to name of the current directory. Should not to be changed if you follow GitOps operating procedures.
STACK_NAME = $(notdir $(shell pwd))
SWARM_HOSTS = $(shell docker node ls --format={{.Hostname}} 2>/dev/null)
TEMP_COMPOSE=.stack.${STACK_NAME}.yaml


# Makefile including function used by every services
include ../../scripts/common.Makefile

.PHONY: up
up: .env configure ${TEMP_COMPOSE}  ## Deploys mail stack
	docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE} ${STACK_NAME}

.PHONY: up-dalco ## Deploys mail stack for Dalco Cluster
up-dalco: up

.PHONY: up-aws
up-aws: .env configure ${TEMP_COMPOSE}-aws  ## Deploys mail stack in aws
	docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE}-aws ${STACK_NAME}

.PHONY: up-master ## Deploys mail stack for Master Cluster
up-master: up-dalco

# Helpers -------------------------------------------------

.PHONY: ${TEMP_COMPOSE}
${TEMP_COMPOSE}: docker-compose.yml
	@docker-compose -f $< --log-level=ERROR config > $@

.PHONY: ${TEMP_COMPOSE}-aws
${TEMP_COMPOSE}-aws: docker-compose.yml docker-compose-aws.yml
	@docker-compose -f $< -f docker-compose-aws.yml --log-level=ERROR config > $@


.PHONY : configure
configure: ## If it does not exist, add the configuration (create mails and alias, and add amavis config) to the mail service
	@if [ -f "config/postfix-accounts.cf" ] ; then \
		echo "Config already created for mail..."; \
	else \
		set -o allexport; \
		source $(realpath $(CURDIR)/../../repo.config); \
		set +o allexport; \
		echo "Adding configuration for $${SMTP_USERNAME}"; \
		bash setup.sh email add $${SMTP_USERNAME} $${SMTP_PASSWORD}; \
		bash setup.sh email add root@$${MACHINE_FQDN} $${SMTP_PASSWORD}; \
		bash setup.sh email add devops@$${MACHINE_FQDN} $${SMTP_PASSWORD}; \
		bash setup.sh email add code-of-conduct@$${MACHINE_FQDN} $${SMTP_PASSWORD}; \
		bash setup.sh email add e2e@$${MACHINE_FQDN} $${SMTP_PASSWORD}; \
		bash setup.sh alias add root@$${MACHINE_FQDN} guidon@speag.swiss; \
		bash setup.sh alias add support@$${MACHINE_FQDN} osparcio-support@speag.swiss; \
		bash setup.sh alias add devops@$${MACHINE_FQDN} osparcio-devops@speag.swiss; \
		bash setup.sh alias add code-of-conduct@$${MACHINE_FQDN} neagu@itis.swiss; \
		bash setup.sh alias add e2e@$${MACHINE_FQDN} test-osparc@itis.swiss; \
		touch amavis.cf; \
		echo '$$final_bad_header_destiny = D_PASS;' >> amavis.cf; \
		echo '$$bad_header_quarantine_to = undef;' >> amavis.cf; \
		sudo mv amavis.cf config/amavis.cf; \
	fi;