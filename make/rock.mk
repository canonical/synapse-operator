# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# ROCK Workflow - Generic logic, managed centrally.
# ==============================================================================

ROCKCRAFT_PACK_CMD 	:= rockcraft pack
SKOPEO_ARGS 		?= --insecure-policy copy --dest-tls-verify=false
SKOPEO_COPY_CMD 	:= skopeo $(SKOPEO_ARGS)
K8S_BACKEND ?= microk8s

##@ ROCK
.PHONY: build-rock publish-rock publish-rock-force clean-rock .check-rockcraft

.check-rockcraft:
	@command -v rockcraft >/dev/null 2>&1 || \
		$(call errmsg,"rockcraft not found. Install with: snap install rockcraft --classic")

build-rock: .check-rockcraft $(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT) ## Build the ROCK OCI image.

$(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT):
	@$(call msg,"--> Building ROCK artifact: $(ROCK_DYNAMIC_ARTIFACT)...")
	@cd $(ROCK_DIR) && $(ROCKCRAFT_PACK_CMD)
	@mv $(ROCK_DIR)/$(ROCK_STATIC_ARTIFACT) $(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT)

publish-rock: $(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT) check-microk8s-registry ## Push the ROCK OCI image to the registry, if not already present.
	@$(call msg,"--> Publishing ROCK: $(ROCK_IMAGE)")
	@{ \
		if skopeo --insecure-policy inspect --tls-verify=false docker://$(ROCK_IMAGE) >/dev/null 2>&1; then \
			$(call warnmsg, Image $(ROCK_IMAGE) already exists in registry, skipping upload); \
			exit 0; \
		fi; \
		$(SKOPEO_COPY_CMD) oci-archive:$(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT) docker://$(ROCK_IMAGE); \
	}

publish-rock-force: $(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT) check-microk8s-registry ## Force push the ROCK OCI image to the registry.
	@$(call msg,"--> Force Publishing ROCK: $(ROCK_IMAGE)")
	$(K8S_BACKEND) ctr images rm $(ROCK_IMAGE) || true
	$(SKOPEO_COPY_CMD) oci-archive:$(ROCK_DIR)/$(ROCK_DYNAMIC_ARTIFACT) docker://$(ROCK_IMAGE)

clean-rock: ## Remove ROCK artifacts.
	@$(call msg,"--> Cleaning ROCK artifacts...")
	@rm -f $(ROCK_DIR)/*.rock
