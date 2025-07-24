# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

variables {
  channel = "2/edge"
  # renovate: depName="synapse"
  revision = 731
}

run "basic_deploy" {
  assert {
    condition     = module.synapse.app_name == "synapse"
    error_message = "Synapse app_name did not match expected"
  }
}
