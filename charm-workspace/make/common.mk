# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# Common Makefile - Generic logic, managed centrally.
# ==============================================================================

MAKE_DIR ?= .
PROJECT_ROOT ?= $(PWD)

# Shared defaults used by derived values below.
ROCK_DIR ?= rock
CONTAINER_REGISTRY ?= localhost:32000
ROCK_PLATFORM ?= amd64
CHARM_VERSION ?= $(shell git -C $(PROJECT_ROOT) describe --tags --always --dirty 2>/dev/null || echo unknown)
CHARM_PLATFORM ?= amd64
# The index of the base in charmcraft.yaml to build.
CHARM_BASE_INDEX ?= 0

# Shared derived variables.
HAS_YQ := $(shell command -v yq)
ifndef HAS_YQ
	$(error yq is required. Install with: snap install yq)
endif

ROCK_DIR_PATH := $(if $(filter /%,$(ROCK_DIR)),$(ROCK_DIR),$(PROJECT_ROOT)/$(ROCK_DIR))
CHARMCRAFT_FILE ?= charmcraft.yaml
CHARMCRAFT_FILE_PATH := $(if $(filter /%,$(CHARMCRAFT_FILE)),$(CHARMCRAFT_FILE),$(PROJECT_ROOT)/$(CHARMCRAFT_FILE))

ROCK_VERSION_BASE := $(shell yq '.version // "1.0"' $(ROCK_DIR_PATH)/rockcraft.yaml)
ROCK_CONTENT_HASH := $(shell find $(ROCK_DIR_PATH) -type f -not -name '*.rock' -print0 | sort -z | xargs -0 cat | sha1sum | cut -c1-7)
ROCK_IMAGE_TAG ?= $(ROCK_VERSION_BASE)-$(ROCK_CONTENT_HASH)
ROCK_STATIC_ARTIFACT := $(ROCK_NAME)_$(ROCK_VERSION_BASE)_$(ROCK_PLATFORM).rock
ROCK_DYNAMIC_ARTIFACT := $(ROCK_NAME)_$(ROCK_IMAGE_TAG)_$(ROCK_PLATFORM).rock
ROCK_IMAGE := $(CONTAINER_REGISTRY)/$(ROCK_NAME):$(ROCK_IMAGE_TAG)

CHARM_BASE_NAME := $(shell yq ".bases[$(CHARM_BASE_INDEX)].run-on[0].name" $(CHARMCRAFT_FILE_PATH))
CHARM_BASE_CHANNEL := $(shell yq ".bases[$(CHARM_BASE_INDEX)].run-on[0].channel" $(CHARMCRAFT_FILE_PATH))
CHARM_BASE_STRING := $(CHARM_BASE_NAME)-$(CHARM_BASE_CHANNEL)
JUJU_DEPLOY_BASE := $(shell echo $(CHARM_BASE_STRING) | sed 's/-/@/')
CHARM_STATIC_ARTIFACT := $(CHARM_NAME)_$(CHARM_BASE_STRING)-$(CHARM_PLATFORM).charm
CHARM_DYNAMIC_ARTIFACT := $(CHARM_NAME)_$(CHARM_VERSION)_$(CHARM_BASE_STRING)_$(CHARM_PLATFORM).charm

# --- Includes ---
# Include all the modular workflow files.
include $(MAKE_DIR)/help.mk
include $(MAKE_DIR)/rock.mk
include $(MAKE_DIR)/charm.mk
include $(MAKE_DIR)/juju.mk
include $(MAKE_DIR)/tox.mk
include $(MAKE_DIR)/docs.mk

# Default target when 'make' is called without arguments.
all: help

.PHONY: all build publish deploy clean test lint unit integration docs

##@ General
LINT_TARGETS ?= tox-lint docs-check
build: build-rock build-charm         		## Build all artifacts (ROCK and Charm).
publish: publish-rock                 		## Publish all artifacts.
deploy: deploy-charm                  		## Deploy the charm for local testing (runs pre/post hooks).
clean: clean-rock clean-charm clean-docs    ## Clean up all build artifacts.
test: tox-unit								## Run unit tests.
lint: $(LINT_TARGETS)					## Run all linters and documentation checks.
unit: tox-unit                    			## Run unit tests.
integration: build-charm publish-rock tox-integration	## Deploy the charm, then run integration tests.
