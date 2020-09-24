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
	@docker stack deploy --compose-file ${TEMP_COMPOSE} ${STACK_NAME}

.PHONY: up-letsencrypt-http
up-letsencrypt-http: .init .env ${TEMP_COMPOSE}-letsencrypt-http  ## Deploys graylog stack using let's encrypt http challenge
	@docker stack deploy --compose-file ${TEMP_COMPOSE}-letsencrypt-http ${STACK_NAME}

.PHONY: up-letsencrypt-dns
up-letsencrypt-dns: .init .env ${TEMP_COMPOSE}-letsencrypt-dns  ## Deploys graylog stack using let's encrypt dns challenge
	@docker stack deploy --compose-file ${TEMP_COMPOSE}-letsencrypt-dns ${STACK_NAME}

.PHONY: up-dalco ## Deploys graylog stack for Dalco Cluster
up-dalco: up-letsencrypt-dns

.PHONY: up-aws
up-aws: .init .env ${TEMP_COMPOSE}-aws  ## Deploys graylog stack using let's encrypt
	@docker stack deploy --compose-file ${TEMP_COMPOSE}-aws ${STACK_NAME}

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

.PHONY: ${TEMP_COMPOSE}-aws
${TEMP_COMPOSE}-aws: docker-compose.yml docker-compose.letsencrypt.http.yml docker-compose.aws.yml
	@docker-compose -f $< -f docker-compose.aws.yml -f docker-compose.letsencrypt.http.yml --log-level=ERROR config > $@

.PHONY: .env
.env: template.env ../../repo.config
	@set -o allexport; \
	source $(realpath $(CURDIR)/../../repo.config); \
	GRAYLOG_ROOT_PASSWORD_SHA2=$$(echo -n "$${GRAYLOG_ROOT_PASSWORD}" | sha256sum | cut -d ' ' -f1);\
	export GRAYLOG_ROOT_PASSWORD_SHA2;\
	set +o allexport; \
	envsubst < $< > $@

.PHONY: configure-instance
configure-instance: ../../repo.config
	# waiting for graylog to run...
	@set -o allexport; source ../../repo.config; set +o allexport; \
	while [ ! "$$(curl -s -o /dev/null -I -w "%{http_code}" --max-time 10  -H "Accept: application/json" -H "Content-Type: application/json" -X GET https://"$$MONITORING_DOMAIN"/graylog/api/users)" = 401 ]; do\
		echo "waiting for graylog to run...";\
		sleep 5s;\
	done;\
	json_data="{\
		\"title\": \"standard GELF UDP input\",\
		\"type\": \"org.graylog2.inputs.gelf.udp.GELFUDPInput\",\
		\"global\": \"true\",\
		\"configuration\": {\
			\"bind_address\": \"0.0.0.0\",\
			\"port\":12201\
		}\
	}";\
	curl -u "$$TRAEFIK_USER":"$$TRAEFIK_PASSWORD" --header "Content-Type: application/json" \
		--header "X-Requested-By: cli" -X POST \
		--data "$$json_data" https://"$$MONITORING_DOMAIN"/graylog/api/system/inputs