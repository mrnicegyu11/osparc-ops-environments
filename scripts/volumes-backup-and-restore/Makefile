.DEFAULT_GOAL := help

.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help:
	@echo "usage: make [target] ..."
	@echo ""
	@echo "Targets for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""


.PHONY: backup restore clean
backup: ## Backup desired volume
	./volume-backup-and-restore.bash backup

restore: ## Restore desired volume
	./volume-backup-and-restore.bash restore
 
clean: ## Remove the backup in /tmp/backup
	@sudo rm -rf /tmp/backup/*