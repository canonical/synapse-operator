# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

resource "juju_application" "synapse" {
  name       = var.app_name
  model_uuid = var.model_uuid

  charm {
    name     = "synapse"
    base     = var.base
    channel  = var.channel
    revision = var.revision
  }

  config             = var.config
  constraints        = var.constraints
  units              = var.units
  storage_directives = var.storage
}
