# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

resource "juju_application" "smtp_integrator" {
  name  = var.app_name
  model = var.model

  charm {
    name     = "smtp-integrator"
    base     = var.base
    channel  = var.channel
    revision = var.revision
  }

  config = var.config
  units  = var.units
}
