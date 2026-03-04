# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# Charm Workflow - Generic logic, managed centrally.
# ==============================================================================

CHARMCRAFT_PACK_CMD 	:= charmcraft pack --bases-index=$(CHARM_BASE_INDEX)

##@ Charm
.PHONY: build-charm deploy-charm clean-charm .check-charmcraft

.check-charmcraft:
	@command -v charmcraft >/dev/null 2>&1 || \
		( $(call errmsg,"charmcraft not found. Install with: snap install charmcraft --classic") )

build-charm: .check-charmcraft $(PROJECT_ROOT)/$(CHARM_DYNAMIC_ARTIFACT) ## Build the charm if it's out of date.

$(PROJECT_ROOT)/$(CHARM_DYNAMIC_ARTIFACT):
	@$(call msg,"--> Building Charm artifact: $(CHARM_DYNAMIC_ARTIFACT)...")
	@echo "$(CHARM_VERSION)" > $(PROJECT_ROOT)/version
	@cd $(PROJECT_ROOT) && $(CHARMCRAFT_PACK_CMD)
	@rm -f $(PROJECT_ROOT)/version
	@mv $(PROJECT_ROOT)/$(CHARM_STATIC_ARTIFACT) $(PROJECT_ROOT)/$(CHARM_DYNAMIC_ARTIFACT)

deploy-charm: setup-juju-model $(PROJECT_ROOT)/$(CHARM_DYNAMIC_ARTIFACT) publish-rock deploy-charm-pre ## Build & publish artifacts, then deploy.
	@$(call msg,"--> Deploying Charm: $(CHARM_NAME)")
	@juju deploy -m $(JUJU_MODEL_NAME) $(PROJECT_ROOT)/$(CHARM_DYNAMIC_ARTIFACT) --resource $(OCI_RESOURCE_NAME)=$(ROCK_IMAGE)
	@$(MAKE) -f $(firstword $(MAKEFILE_LIST)) deploy-charm-post

clean-charm: ## Remove charm artifacts.
	@$(call msg,"--> Cleaning charm artifacts...")
	@rm -f $(PROJECT_ROOT)/*.charm $(PROJECT_ROOT)/$(CHARM_OVERRIDE_FILE)
