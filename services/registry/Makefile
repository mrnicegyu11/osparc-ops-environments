.DEFAULT_GOAL := help



# Internal VARIABLES ------------------------------------------------
# STACK_NAME defaults to name of the current directory. Should not to be changed if you follow GitOps operating procedures.
STACK_NAME = $(notdir $(shell pwd))
SWARM_HOSTS = $(shell docker node ls --format={{.Hostname}} 2>/dev/null)
TEMP_COMPOSE=.stack.${STACK_NAME}.yaml

# TARGETS --------------------------------------------------
include ../../scripts/common.Makefile

define create-s3-bucket
	# ensure bucket is available in S3...
	@set -o allexport; \
	source .env; \
	set +o allexport; \
	./../../scripts/create-s3-bucket.bash "$${S3_BUCKET}"; \
	# bucket is available in S3
endef

.PHONY: up
up: .init .env ${TEMP_COMPOSE}  ## Deploys registry stack
	@$(create-s3-bucket)
	docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE} ${STACK_NAME}

.PHONY: up-letsencrypt-http
up-letsencrypt-http: .init .env ${TEMP_COMPOSE}-letsencrypt-http  ## Deploys registry stack using let's encrypt http challenge
	docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE}-letsencrypt-http ${STACK_NAME}

.PHONY: up-letsencrypt-dns
up-letsencrypt-dns: .init .env ${TEMP_COMPOSE}-letsencrypt-dns  ## Deploys registry stack using let's encrypt dns challenge
	docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE}-letsencrypt-dns ${STACK_NAME}

.PHONY: up-dalco ## Deploys registry stack for Dalco Cluster
up-dalco: up-letsencrypt-dns

.PHONY: up-aws
up-aws: .env ${TEMP_COMPOSE}-aws  ## Deploys registry on AWS
	@docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE}-aws ${STACK_NAME}

.PHONY: up-master
up-master: up-dalco

# Helpers -------------------------------------------------

.PHONY: ${TEMP_COMPOSE}
${TEMP_COMPOSE}: docker-compose.yml docker-compose.self-signed.yml
	docker-compose -f $< -f docker-compose.self-signed.yml --log-level=ERROR config > $@

.PHONY: ${TEMP_COMPOSE}-letsencrypt-http
${TEMP_COMPOSE}-letsencrypt-http: docker-compose.yml docker-compose.letsencrypt.http.yml
	docker-compose -f $< -f docker-compose.letsencrypt.http.yml --log-level=ERROR config > $@

.PHONY: ${TEMP_COMPOSE}-letsencrypt-dns
${TEMP_COMPOSE}-letsencrypt-dns: docker-compose.yml docker-compose.letsencrypt.dns.yml
	docker-compose -f $< -f docker-compose.letsencrypt.dns.yml --log-level=ERROR config > $@

.PHONY: ${TEMP_COMPOSE}-aws
${TEMP_COMPOSE}-aws: docker-compose.yml docker-compose.aws.yml docker-compose.letsencrypt.dns.yml
	docker-compose -f $< -f docker-compose.aws.yml -f docker-compose.letsencrypt.dns.yml --log-level=ERROR config > $@
