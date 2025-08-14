# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

output "app_name" {
  description = "Name of the deployed application."
  value       = juju_application.synapse.name
}

output "endpoints" {
  value = {
    backup            = "backup"
    database          = "database"
    grafana_dashboard = "grafana-dashboard"
    ingress           = "ingress"
    logging           = "logging"
    mas_database      = "mas-database"
    matrix_auth       = "matrix-auth"
    media             = "media"
    metrics_endpoint  = "metrics-endpoint"
    nginx_route       = "nginx-route"
    oauth             = "oauth"
    redis             = "redis"
    saml              = "saml"
    smtp              = "smtp"
  }
}
