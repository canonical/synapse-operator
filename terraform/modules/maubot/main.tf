# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

resource "juju_application" "maubot" {
  name       = var.app_name
  model_uuid = var.model_uuid

  charm {
    name     = "maubot"
    base     = var.base
    channel  = var.channel
    revision = var.revision
  }

  config = var.config
  units  = var.units
}
