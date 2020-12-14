.DEFAULT_GOAL := help

APP_NAME := deployment-agent

# External VARIABLES
include ../../repo.config
# Internal VARIABLES ------------------------------------------------
# STACK_NAME defaults to name of the current directory. Should not to be changed if you follow GitOps operating procedures.
ifeq ($(PREFIX_STACK_NAME),)
STACK_NAME := $(notdir $(shell pwd))
else
STACK_NAME := $(PREFIX_STACK_NAME)-$(notdir $(shell pwd))
endif
SWARM_HOSTS = $(shell docker node ls --format={{.Hostname}} 2>/dev/null)
TEMP_COMPOSE = .stack.${STACK_NAME}.yaml
TEMP_COMPOSE-devel = .stack.${STACK_NAME}.devel.yml
TEMP_COMPOSE-aws = .stack.${STACK_NAME}.aws.yml
DEPLOYMENT_AGENT_CONFIG = deployment_config.yaml
DEPLOYMENT_AGENT_CONFIG_DEFAULT=deployment_config.default.yaml

# VCS info on current repo
CURRENT_GIT_URL=$(shell git config --get remote.origin.url)
CURRENT_GIT_BRANCH=$(shell git rev-parse --abbrev-ref HEAD)

# TARGETS --------------------------------------------------
include ../../scripts/common.Makefile

# exports
export VCS_URL:=$(shell git config --get remote.origin.url)
export VCS_REF:=$(shell git rev-parse --short HEAD)
export VCS_STATUS_CLIENT:=$(if $(shell git status -s),'modified/untracked','clean')
export BUILD_DATE:=$(shell date -u +"%Y-%m-%dT%H:%M:%SZ")

export DOCKER_REGISTRY ?= itisfoundation
export DOCKER_IMAGE_TAG ?= $(shell cat VERSION)
$(info DOCKER_REGISTRY set to ${DOCKER_REGISTRY})
$(info DOCKER_IMAGE_TAG set to ${DOCKER_IMAGE_TAG})

## docker BUILD -------------------------------
.PHONY: build build-kit build-x build-devel build-devel-kit build-devel-x
build build-kit build-x build-devel build-devel-kit build-devel-x: ## Builds $(APP_NAME) image
	@$(if $(findstring -kit,$@),export DOCKER_BUILDKIT=1;export COMPOSE_DOCKER_CLI_BUILD=1;,) \
	$(if $(findstring -x,$@),docker buildx bake, docker-compose) --file docker-compose.yml $(if $(findstring -devel,$@),--file docker-compose.devel.yaml,) $(if $(findstring -x,$@),,build)


.PHONY: up
up: .init ${DEPLOYMENT_AGENT_CONFIG} ${TEMP_COMPOSE} ## Deploys or updates current stack "$(STACK_NAME)" using replicas=X (defaults to 1)
	@docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE} $(STACK_NAME)

.PHONY: up-devel
up-devel: .init ${DEPLOYMENT_AGENT_CONFIG} ${TEMP_COMPOSE-devel} ## Deploys or updates current stack "$(STACK_NAME)" using replicas=X (defaults to 1)
	@docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE-devel} $(STACK_NAME)

.PHONY: up-dalco
up-dalco: up ## Deploys deploymentagent stack for Dalco Cluster

.PHONY: up-aws
up-aws: .init ${DEPLOYMENT_AGENT_CONFIG} ${TEMP_COMPOSE-aws} ## Deploys or updates current stack "$(STACK_NAME)" using replicas=X (defaults to 1) on aws
	@docker stack deploy --with-registry-auth --prune --compose-file ${TEMP_COMPOSE-aws} $(STACK_NAME)

.PHONY: up-master
up-master: up-dalco

.PHONY: down
down: ## Stops and remove stack from swarm
	-@docker stack rm $(STACK_NAME)
	-@docker stack rm ${SIMCORE_STACK_NAME}

.PHONY: push
push: ## Pushes service to the registry.
	docker push ${DOCKER_REGISTRY}/$(APP_NAME):${DOCKER_IMAGE_TAG}
	docker tag ${DOCKER_REGISTRY}/$(APP_NAME):${DOCKER_IMAGE_TAG} ${DOCKER_REGISTRY}/deployment-agent:latest
	docker push ${DOCKER_REGISTRY}/$(APP_NAME):latest

.PHONY: pull
pull: ## Pulls service from the registry.
	docker pull ${DOCKER_REGISTRY}/$(APP_NAME):${DOCKER_IMAGE_TAG}

.PHONY: config
config: ${DEPLOYMENT_AGENT_CONFIG} ## Create an initial configuration file.

.PHONY: install-dev
install-dev: ## install deployment agent dev
	pip install -r requirements/dev.txt

# Testing -------------------------------------------------
.PHONY: install-test
install-test: install-dev ## install deployment agent testing facilities
	pip install -r requirements/ci.txt

.PHONY: unit-test
unit-test: install-test ## Execute unit tests
	pytest --cov-append --color=yes --cov-report=term-missing --cov-report=xml --cov=simcore_service_deployment_agent -v tests


## PYTHON -------------------------------
.PHONY: pylint

PY_PIP = $(if $(IS_WIN),cd .venv/Scripts && pip.exe,.venv/bin/pip3)

pylint: ## Runs python linter framework's wide
	# See exit codes and command line https://pylint.readthedocs.io/en/latest/user_guide/run.html#exit-codes
	# TODO: NOT windows friendly
	/bin/bash -c "pylint --jobs=0 --rcfile=.pylintrc $(strip $(shell find services packages -iname '*.py' \
											-not -path "*egg*" \
											-not -path "*migration*" \
											-not -path "*contrib*" \
											-not -path "*-sdk/python*" \
											-not -path "*generated_code*" \
											-not -path "*datcore.py" \
											-not -path "*web/server*"))"

.PHONY: devenv devenv-all

.venv:
	python3 -m venv $@
	$@/bin/pip3 install --upgrade \
		pip \
		wheel \
		setuptools

devenv: .venv ## create a python virtual environment with dev tools (e.g. linters, etc)
	$</bin/pip3 install -r requirements.txt
	@echo "To activate the venv, execute 'source .venv/bin/activate'"

# Helpers -------------------------------------------------
.PHONY: ${DEPLOYMENT_AGENT_CONFIG}
${DEPLOYMENT_AGENT_CONFIG}:  
	@set -o allexport; \
	# Automatically update the branch - link of the repo for the ops - repo in the deployeur config to the current one in the current project. \
	current_git_url=$$(git config --get remote.origin.url); \
	current_git_branch=$$(git branch | grep \* | cut -d ' ' -f2); \
	if [[ $$current_git_url == git* ]]; then \
	    # it is a ssh style link let's get the organisation name and just replace this cause that conf only accepts https git repos \
	    current_organisation=$(echo "$$current_git_url" | cut -d":" -f2 | cut -d"/" -f1); \
	    export OPS_GIT_LINK=https://github.com/$$current_organisation/osparc-ops.git; \
	else \
	    export OPS_GIT_LINK=$$current_git_url; \
	fi; \
	export OPS_GIT_BRANCH=$$current_git_branch; \
	source $(realpath $(CURDIR)/../../repo.config); \
	set +o allexport; \
	envsubst < ${DEPLOYMENT_AGENT_CONFIG_DEFAULT} > $@


docker-compose-configs = $(wildcard docker-compose*.yml)

.PHONY: ${TEMP_COMPOSE}
${TEMP_COMPOSE}: .env $(docker-compose-configs)
	@docker-compose --file docker-compose.yml --log-level=ERROR config > $@

.PHONY: ${TEMP_COMPOSE-devel}
${TEMP_COMPOSE-devel}: .env $(docker-compose-configs)
	@docker-compose --file docker-compose.yml --file docker-compose.devel.yaml --log-level=ERROR config > $@

.PHONY: ${TEMP_COMPOSE-aws}
${TEMP_COMPOSE-aws}: .env $(docker-compose-configs)
	@docker-compose --file docker-compose.yml --file docker-compose-aws.yml --log-level=ERROR config > $@