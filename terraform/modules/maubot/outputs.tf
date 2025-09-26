# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "Name of the deployed application."
  value       = juju_application.maubot.name
}

output "requires" {
  value = {
    ingress     = "ingress"
    logging     = "logging"
    matrix_auth = "matrix-auth"
    postgresql  = "postgresql"
  }
}

output "provides" {
  value = {
    grafana_dashboard = "grafana-dashboard"
    metrics_endpoint  = "metrics-endpoint"
  }
}

output "endpoints" {
  value = {
    grafana_dashboard = "grafana-dashboard"
    ingress           = "ingress"
    logging           = "logging"
    matrix_auth       = "matrix-auth"
    metrics_endpoint  = "metrics-endpoint"
    postgresql        = "postgresql"
  }
}
