.DEFAULT_GOAL := help



# Internal VARIABLES ------------------------------------------------
# STACK_NAME defaults to name of the current directory. Should not to be changed if you follow GitOps operating procedures.
STACK_NAME = $(notdir $(shell pwd))
SWARM_HOSTS = $(shell docker node ls --format={{.Hostname}} 2>/dev/null)
DOCKER_PORTAINER_ADMIN_PASSWORD_SECRET = $(shell docker secret inspect --format {{.Spec.Name}} portainer_admin_password 2>/dev/null)
TEMP_COMPOSE=.stack.${STACK_NAME}.yaml

# TARGETS --------------------------------------------------
include ../../scripts/common.Makefile

.PHONY: up
up: .init .env .secrets ${TEMP_COMPOSE}  ## Deploys portainer stack
	@docker stack deploy --compose-file ${TEMP_COMPOSE} ${STACK_NAME}

.PHONY: up-letsencrypt-http
up-letsencrypt-http: .init .env .secrets ${TEMP_COMPOSE}-letsencrypt-http  ## Deploys portainer stack using let's encrypt http challenge
	@docker stack deploy --compose-file ${TEMP_COMPOSE}-letsencrypt-http ${STACK_NAME}

.PHONY: up-letsencrypt-dns
up-letsencrypt-dns: .init .env .secrets ${TEMP_COMPOSE}-letsencrypt-dns ## Deploys portainer stack using let's encrypt dns challenge
	@docker stack deploy --compose-file ${TEMP_COMPOSE}-letsencrypt-dns ${STACK_NAME}

.PHONY: up-aws
up-aws: .init .env .secrets ${TEMP_COMPOSE}-aws  ## Deploys portainer stack in aws
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
${TEMP_COMPOSE}-aws: docker-compose.yml docker-compose.aws.yml docker-compose.letsencrypt.dns.yml
	@docker-compose -f $< -f docker-compose.aws.yml -f docker-compose.letsencrypt.dns.yml --log-level=ERROR config > $@

.PHONY: .secrets
.secrets: .env
	@$(if $(DOCKER_PORTAINER_ADMIN_PASSWORD_SECRET), \
		docker secret rm portainer_admin_password;  set -o allexport; source .env; set +o allexport; echo -n "$${PORTAINER_ADMIN_PWD}" | docker secret create portainer_admin_password -  2>/dev/null;  , \
		set -o allexport; source .env; set +o allexport; echo -n "$${PORTAINER_ADMIN_PWD}" | docker secret create portainer_admin_password -  2>/dev/null;\
	)
