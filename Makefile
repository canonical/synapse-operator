# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# ==============================================================================
# Project: Synapse K8s Operator
# This file contains ONLY project-specific configuration.
# ==============================================================================

CHARM_NAME        := synapse
ROCK_NAME         := synapse
OCI_RESOURCE_NAME := synapse-image
ROCK_DIR          ?= synapse_rock
LINT_TARGETS      := tox-lint

# Override the default lint to exclude docs-check until vale/lychee are configured.
lint: tox-lint

# Synapse-specific post-deploy setup (PostgreSQL relation, server_name, etc.)
deploy-charm-post:
	@$(call msg,"--> Configuring Synapse post-deploy...")
	# Add charm-specific juju config/relate commands here

# ==============================================================================
# Makefile common logic
# ==============================================================================

MAKE_DIR := charm-workspace/make
include $(MAKE_DIR)/common.mk
