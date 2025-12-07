.PHONY: help
help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

VAGRANT_DIR := .vagrant

test: ## run unit tests (no VM required)
	cd .. && pytest tests/ -v -m "not integration"

test-vm: ## run single-host integration tests
	cd .. && pytest tests/tests/ -v -m "integration and not multihost"

test-multihost: ## run multi-host integration tests
	cd .. && pytest tests/tests/ -v -m "integration and multihost"

test-all: ## run all tests (unit + integration)
	cd .. && pytest tests/ -v

vstatus: ## show vagrant status
	vagrant status

vdestroy: ## destroy box and local state
	vagrant destroy -f || true
	rm -rf $(VAGRANT_DIR)

vdestroy-libvirt: ## destroy libvirt VMs
	@for vf in Vagrantfile.libvirt Vagrantfile.multihost; do \
		if [ -f "$$vf" ]; then \
			VAGRANT_VAGRANTFILE=$$vf vagrant destroy -f 2>/dev/null || true; \
		fi; \
	done
	vagrant destroy -f 2>/dev/null || true
	rm -rf $(VAGRANT_DIR)

vdestroy-all: ## destroy ALL vagrant envs from global-status (danger)
	@vagrant global-status --prune \
	  | awk 'NR>2 && $$1 ~ /^[0-9a-f]+$$/ {print $$1}' \
	  | xargs -r -n1 vagrant destroy -f

vprune: ## prune vagrant cache (cleans stale global-status entries)
	vagrant global-status --prune

clean: vdestroy ## clean up vagrant and test artifacts
	rm -rf tests/.pytest_cache tests/__pycache__ .pytest_cache __pycache__
