.DEFAULT_GOAL := help


# Internal VARIABLES ------------------------------------------------
# STACK_NAME defaults to name of the current directory. Should not to be changed if you follow GitOps operating procedures.
STACK_NAME = $(notdir $(shell pwd))
SWARM_HOSTS = $(shell docker node ls --format={{.Hostname}} 2>/dev/null)
TEMP_COMPOSE=.stack.${STACK_NAME}.yaml

# TARGETS --------------------------------------------------
include ../../scripts/common.Makefile

.PHONY: up
up: .init .env ${TEMP_COMPOSE}  ## Deploys graylog stack
	@docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE} ${STACK_NAME}

.PHONY: up-letsencrypt-http
up-letsencrypt-http: .init .env ${TEMP_COMPOSE}-letsencrypt-http  ## Deploys graylog stack using let's encrypt http challenge
	@docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE}-letsencrypt-http ${STACK_NAME}

.PHONY: up-letsencrypt-dns
up-letsencrypt-dns: .init .env ${TEMP_COMPOSE}-letsencrypt-dns  ## Deploys graylog stack using let's encrypt dns challenge
	@docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE}-letsencrypt-dns ${STACK_NAME}

.PHONY: up-dalco ## Deploys graylog stack for Dalco Cluster
up-dalco: .init .env ${TEMP_COMPOSE}-letsencrypt-dalco
	@docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE}-letsencrypt-dalco ${STACK_NAME}

.PHONY: up-aws
up-aws: .init .env ${TEMP_COMPOSE}-aws  ## Deploys graylog stack using let's encrypt
	@docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE}-aws ${STACK_NAME}

.PHONY: up-master
up-master: up-letsencrypt-dns

# Helpers -------------------------------------------------

.PHONY: ${TEMP_COMPOSE}
${TEMP_COMPOSE}: docker-compose.yml
	@docker-compose -f $< --log-level=ERROR config > $@

.PHONY: ${TEMP_COMPOSE}-letsencrypt-http
${TEMP_COMPOSE}-letsencrypt-http: docker-compose.yml docker-compose.letsencrypt.http.yml
	@docker-compose -f $< -f docker-compose.letsencrypt.http.yml --log-level=ERROR config > $@

.PHONY: ${TEMP_COMPOSE}-letsencrypt-dns
${TEMP_COMPOSE}-letsencrypt-dns: docker-compose.yml docker-compose.letsencrypt.dns.yml
	@docker-compose -f $< -f docker-compose.letsencrypt.dns.yml --log-level=ERROR config > $@

.PHONY: ${TEMP_COMPOSE}-letsencrypt-dalco
${TEMP_COMPOSE}-letsencrypt-dalco: docker-compose.yml docker-compose.dalco.yml docker-compose.letsencrypt.dns.yml
	@docker-compose -f $< -f docker-compose.dalco.yml -f docker-compose.letsencrypt.dns.yml --log-level=ERROR config > $@

.PHONY: ${TEMP_COMPOSE}-aws
${TEMP_COMPOSE}-aws: docker-compose.yml docker-compose.letsencrypt.dns.yml docker-compose.aws.yml
	@docker-compose -f $< -f docker-compose.aws.yml -f docker-compose.letsencrypt.dns.yml --log-level=ERROR config > $@

.PHONY: .env
.env: template.env ../../repo.config
	@set -o allexport; \
	source $(realpath $(CURDIR)/../../repo.config); \
	GRAYLOG_ROOT_PASSWORD_SHA2=$$(echo -n "$${GRAYLOG_ROOT_PASSWORD}" | sha256sum | cut -d ' ' -f1);\
	export GRAYLOG_ROOT_PASSWORD_SHA2;\
	set +o allexport; \
	envsubst < $< > $@


.PHONY: configure
configure: ## Test is Graylog is online and configure Graylog inputs
	@cd scripts;\
	if [ ! -d "venv" ]; \
	then\
		python3 -m venv venv;\
	fi;\
	source venv/bin/activate;\
	pip install -r requirements.txt > /dev/null 2>&1;\
	python configure.py;