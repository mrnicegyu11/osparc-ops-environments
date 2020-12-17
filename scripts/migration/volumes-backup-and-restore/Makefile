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


.PHONY: backup restore clean all_ssh transfer
backup: ## Backup volumes specified in the env file
	@./volume-backup-and-restore.bash backup

restore: ## Restore volumes specified in the env fike
	@./volume-backup-and-restore.bash restore

transfer: ## Transfer volumes saved in /tmp/backup to another host
	@./volume-backup-and-restore.bash transfer

all_ssh: ## Connect to a distant server in ssh, backup the volume and restore it in the local server
	@./volume-backup-and-restore.bash backup_and_restore_ssh
 
clean: ## Remove the backup in /backup
	@sudo rm -rf /backup/*