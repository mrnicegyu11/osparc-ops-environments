.DEFAULT_GOAL := help



# STACK_NAME defaults to name of the current directory. Should not to be changed if you follow GitOps operating procedures.
STACK_NAME = $(notdir $(CURDIR))
SWARM_HOSTS = $(shell docker node ls --format={{.Hostname}} 2>/dev/null)
TEMP_COMPOSE=.stack.${STACK_NAME}.yaml


# TARGETS --------------------------------------------------
include ../../scripts/common.Makefile

.PHONY: up
up: .init .env config.prometheus  datasource.yml ${TEMP_COMPOSE} ## Deploys or updates current stack "$(STACK_NAME)". If MONITORED_NETWORK is not specified, it will create an attachable network
	@docker stack deploy --compose-file ${TEMP_COMPOSE} $(STACK_NAME)

.PHONY: up-letsencrypt-http
up-letsencrypt-http: .init .env config.prometheus datasource.yml ${TEMP_COMPOSE}-letsencrypt-http   ## Deploys or updates current stack "$(STACK_NAME)" using let's encrypt http challenge
	@docker stack deploy --compose-file ${TEMP_COMPOSE}-letsencrypt-http ${STACK_NAME}

.PHONY: up-letsencrypt-dns
up-letsencrypt-dns: .init .env config.prometheus  datasource.yml ${TEMP_COMPOSE}-letsencrypt-dns   ## Deploys or updates current stack "$(STACK_NAME)" using let's encrypt dns challenge
	@docker stack deploy --compose-file ${TEMP_COMPOSE}-letsencrypt-dns ${STACK_NAME}

.PHONY: up-dalco
up-dalco: .init .env datasource.dalco.yml config.prometheus.minio ${TEMP_COMPOSE}-dalco ## Deploys monitoring stack for Dalco Cluster
	@docker stack deploy --compose-file ${TEMP_COMPOSE}-dalco ${STACK_NAME}

.PHONY: up-aws
up-aws: .init .env datasource.aws.yml config.monitoring config.prometheus.aws ${TEMP_COMPOSE}-aws   ## Deploys or updates current stack "$(STACK_NAME)" in AWS
	@docker stack deploy --compose-file ${TEMP_COMPOSE}-aws ${STACK_NAME}


.PHONY: ${TEMP_COMPOSE}
${TEMP_COMPOSE}: docker-compose.yml
	@docker-compose -f $< --log-level=ERROR config > $@

.PHONY: ${TEMP_COMPOSE}-letsencrypt-http
${TEMP_COMPOSE}-letsencrypt-http: docker-compose.yml docker-compose.letsencrypt.http.yml
	@docker-compose -f $< -f docker-compose.letsencrypt.http.yml --log-level=ERROR config > $@

.PHONY: ${TEMP_COMPOSE}-letsencrypt-dns
${TEMP_COMPOSE}-letsencrypt-dns: docker-compose.yml docker-compose.letsencrypt.dns.yml
	@docker-compose -f $< -f docker-compose.letsencrypt.dns.yml --log-level=ERROR config > $@

.PHONY: ${TEMP_COMPOSE}-dalco
${TEMP_COMPOSE}-dalco: docker-compose.yml docker-compose.dalco.yml docker-compose.letsencrypt.dns.yml
	@docker-compose -f $< -f docker-compose.letsencrypt.dns.yml -f docker-compose.dalco.yml --log-level=ERROR config > $@

.PHONY: ${TEMP_COMPOSE}-aws
${TEMP_COMPOSE}-aws: docker-compose.yml docker-compose.aws.yml docker-compose.letsencrypt.dns.yml
	@docker-compose -f $< -f docker-compose.aws.yml -f docker-compose.letsencrypt.dns.yml --log-level=ERROR config > $@


.PHONY: config.monitoring
config.monitoring: grafana/template-config.monitoring ../../repo.config
	@set -o allexport; \
	source $(realpath $(CURDIR)/../../repo.config); \
	set +o allexport; \
	envsubst < $< > grafana/$@

.PHONY: config.prometheus.minio
config.prometheus.minio: ../../repo.config
	@set -o allexport; \
	source $(realpath $(CURDIR)/../../repo.config); \
	set +o allexport; \
	@$(_yq) merge --append prometheus/prometheus-base.yml prometheus/prometheus-dalco.yml > prometheus/prometheus.yml; \
	envsubst < prometheus/prometheus.yml > prometheus/prometheus.temp.yml; \
	mv prometheus/prometheus.temp.yml prometheus/prometheus.yml

.PHONY: config.prometheus.aws
config.prometheus.aws: ../../repo.config
	@set -o allexport; \
	source $(realpath $(CURDIR)/../../repo.config); \
	set +o allexport; \
	@$(_yq) merge --append prometheus/prometheus-base.yml prometheus/prometheus-aws.yml > prometheus/prometheus.yml; \
	envsubst < prometheus/prometheus.yml > prometheus/prometheus.temp.yml; \
	mv prometheus/prometheus.temp.yml prometheus/prometheus.yml

.PHONY: config.prometheus
config.prometheus: ../../repo.config
	@cp prometheus/prometheus-base.yml prometheus/prometheus.yml


.PHONY: datasource.aws.yml
datasource.aws.yml: grafana/provisioning/datasources/datasource.yml.template grafana/provisioning/datasources/datasource.aws.yml.template ../../repo.config
	@set -o allexport; \
	source $(realpath $(CURDIR)/../../repo.config); \
	set +o allexport; \
	@$(_yq) merge --append $< grafana/provisioning/datasources/datasource.aws.yml.template > grafana/provisioning/datasources/datasource.yml; \
	envsubst < grafana/provisioning/datasources/datasource.yml > grafana/provisioning/datasources/temp.datasource.yml; \
	mv  grafana/provisioning/datasources/temp.datasource.yml grafana/provisioning/datasources/datasource.yml

.PHONY: datasource.dalco.yml
datasource.dalco.yml: grafana/provisioning/datasources/datasource.yml.template grafana/provisioning/datasources/datasource.dalco.yml.template ../../repo.config
	@set -o allexport; \
	source $(realpath $(CURDIR)/../../repo.config); \
	set +o allexport; \
	@$(_yq) merge --append $< grafana/provisioning/datasources/datasource.dalco.yml.template > grafana/provisioning/datasources/datasource.yml; \
	envsubst < grafana/provisioning/datasources/datasource.yml > grafana/provisioning/datasources/temp.datasource.yml; \
	mv  grafana/provisioning/datasources/temp.datasource.yml grafana/provisioning/datasources/datasource.yml
