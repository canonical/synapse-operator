# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# Tox Workflow - Generic logic, managed centrally.
# ==============================================================================

VENV_DIR ?= $(PROJECT_ROOT)/.venv
VENV_PYTHON := $(VENV_DIR)/bin/python
TOX := $(VENV_DIR)/bin/tox

# Default empty ARGS variables for each explicit tox target.
# These can be overridden in the root Makefile.
TOX_LINT_ARGS ?=
TOX_UNIT_ARGS ?=
TOX_INTEGRATION_PROJECT_ARGS ?=
TOX_INTEGRATION_FILTER ?=
TOX_INTEGRATION_EXTRA_ARGS ?=
TOX_INTEGRATION_FILTER_ARGS := $(if $(strip $(TOX_INTEGRATION_FILTER)),-k "$(TOX_INTEGRATION_FILTER)",)
TOX_INTEGRATION_ARGS ?= $(strip $(TOX_INTEGRATION_PROJECT_ARGS) $(TOX_INTEGRATION_FILTER_ARGS) $(TOX_INTEGRATION_EXTRA_ARGS))

INTEGRATION_TEST_ENV ?= \
	CHARM_FILE=$(PROJECT_ROOT)/$(CHARM_DYNAMIC_ARTIFACT) \
	ROCK_IMAGE=$(ROCK_IMAGE) \
	OCI_RESOURCE_NAME=$(OCI_RESOURCE_NAME) \
	JUJU_DEPLOY_BASE=$(JUJU_DEPLOY_BASE)

$(VENV_DIR):
	@$(call msg,"--> Creating Python virtual environment in $(VENV_DIR)...")
	@python3 -m venv $(VENV_DIR)

$(TOX): $(VENV_DIR)
	@$(call msg,"--> Installing tox in virtual environment...")
	@$(VENV_PYTHON) -m pip install tox

##@ Testing
.PHONY: tox-lint tox-unit tox-integration

tox-lint: $(TOX) ## Run linters using tox.
	@$(call msg,"--> Running tox environment: lint")
	@cd $(PROJECT_ROOT) && $(TOX) -e lint -- $(TOX_LINT_ARGS)

tox-unit: $(TOX) ## Run unit tests using tox.
	@$(call msg,"--> Running tox environment: unit")
	@cd $(PROJECT_ROOT) && $(TOX) -e unit -- $(TOX_UNIT_ARGS)

tox-integration: $(TOX) ## Run integration tests using tox.
	@$(call msg,"--> Running tox environment: integration")
	@$(call msg,"    ROCK_IMAGE:'$(ROCK_IMAGE)'  CHARM_FILE:'$(CHARM_DYNAMIC_ARTIFACT)'")
	@cd $(PROJECT_ROOT) && $(INTEGRATION_TEST_ENV) $(TOX) -e integration -- $(TOX_INTEGRATION_ARGS)

# This pattern rule allows running any other tox environment.
# Example: 'make tox-fmt' will run 'tox -e fmt'.
.PHONY: tox-%
tox-%: $(TOX)
	$(eval ENV_UPPER := $(shell echo $* | tr 'a-z-' 'A-Z_'))
	@$(call msg,"--> Running tox environment: $* $($(ENV_UPPER)_ARGS)")
	@$(if $($(ENV_UPPER)_ARGS),$(call msg, "    using args from TOX_$(ENV_UPPER)_ARGS: '$($(ENV_UPPER)_ARGS)')")
	@cd $(PROJECT_ROOT) && $(TOX) -e $* -- $($(ENV_UPPER)_ARGS)
