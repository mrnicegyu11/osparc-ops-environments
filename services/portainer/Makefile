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
	@docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE} ${STACK_NAME}

.PHONY: up-letsencrypt-http
up-letsencrypt-http: .init .env .secrets ${TEMP_COMPOSE}-letsencrypt-http  ## Deploys portainer stack using let's encrypt http challenge
	@docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE}-letsencrypt-http ${STACK_NAME}

.PHONY: up-letsencrypt-dns
up-letsencrypt-dns: .init .env .secrets ${TEMP_COMPOSE}-letsencrypt-dns ## Deploys portainer stack using let's encrypt dns challenge
	@docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE}-letsencrypt-dns ${STACK_NAME}

.PHONY: up-dalco ## Deploys portainer stack for Dalco Cluster
up-dalco: up-letsencrypt-dns

.PHONY: up-aws ## Deploys portainer stack for AWS
up-aws: .init .env .secrets ${TEMP_COMPOSE}-aws  ## Deploys portainer stack in aws
	@docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE}-aws ${STACK_NAME}

.PHONY: up-master
up-master: up-dalco

.PHONY: configure-registry
configure-registry:  ## Add if necessary dockerhub registry configuration to portainer.
	@set -o allexport; source ../../repo.config; set +o allexport; \
	while [ "$$(curl -s -o /dev/null -I -w "%{http_code}" --max-time 10  -H "Accept: application/json" -H "Content-Type: application/json" -X GET https://"$$MONITORING_DOMAIN"/portainer/#/auth)" != 200 ]; do\
		echo "waiting for portainer to run...";\
		sleep 5s;\
	done;\
	echo "Updating docker-hub config";\
	authentificationToken=$$(curl -o /dev/null -X POST "https://"$$MONITORING_DOMAIN"/portainer/api/auth" -H  "Content-Type: application/json" -d "{  \"Username\": \"admin\",  \"Password\": \"dev\"}"); \
	authentificationToken=$$(echo "$$authentificationToken" | jq --raw-output '.jwt'); \
	update_hub=$$(curl -o /dev/null -X PUT "https://"$$MONITORING_DOMAIN"/portainer/api/dockerhub" -H  "accept: application/json" -H \
	"Authorization: Bearer $${authentificationToken}" -H  "Content-Type: application/json" \
	-d "{  \"Authentication\": true,  \"Username\": \"$$DOCKER_HUB_LOGIN\",  \"Password\": \"$$DOCKER_HUB_PASSWORD\"}"); \


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
