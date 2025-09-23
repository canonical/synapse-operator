variable "app_names" {
  description = "Partial overrides for application names."
  type        = map(string)
  default     = {}

  validation {
    condition = length(
      setsubtract(keys(var.integrate_offers), [
        "synapse",
        "s3_integrator_backup",
        "s3_integrator_media",
      ])
    ) == 0

    error_message = "The keys in var.app_names must be one or more of: synapse, s3_integrator_backup, s3_integrator_media."
  }
}

variable "channels" {
  description = "Partial overrides for charm channels. Keys follow same name as the variable enable."
  type        = map(string)
  default     = {}
}

variable "config_lego" {
  description = "Configuration for the Lego charm."
  type        = map(string)

  default = {
    "email" : "is-admin@canonical.com",
    "plugin" : "httpreq",
  }
}

variable "config_model" {
  description = "Configuration for the juju model."
  type        = map(string)
  default = {
    juju-http-proxy  = "" # override or set via locals
    juju-https-proxy = "" # override or set via locals
    juju-no-proxy    = "127.0.0.1,localhost,::1,10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,.canonical.com,.launchpad.net,.internal,.jujucharms.com,.ubuntu.com"
  }
}

variable "config_nginx_ingress_integrator" {
  description = "Configuration for the nginx ingress integrator charm."
  type        = map(string)
  default = {
    max-body-size    = "21"
    service-hostname = "" # override or set via locals
  }
}

variable "config_s3_integrator_backup" {
  description = "Configuration for the s3 integrator backup charm."
  type        = map(string)
  default = {
    bucket       = "prod-synapse-k8s-live-backup"
    endpoint     = "https://radosgw.ps6.canonical.com"
    path         = "synapse-backup"
    region       = "prodstack6"
    s3-uri-style = "path"
  }
}

variable "config_s3_integrator_media" {
  description = "Configuration for the s3 integrator media charm."
  type        = map(string)
  default = {
    bucket       = "prod-synapse-k8s-live-media"
    endpoint     = "https://radosgw.ps6.canonical.com"
    path         = "synapse-media"
    region       = "prodstack6"
    s3-uri-style = "path"
  }
}

variable "config_local_saml_integrator" {
  description = "Configuration for the local saml integrator charm."
  type        = map(string)
  default     = {}
}

variable "config_local_postgresql" {
  description = "Configuration for the local postgresql charm."
  type        = map(string)
  default     = {}
}

variable "config_smtp_integrator" {
  description = "Configuration for the smtp integrator charm."
  type        = map(string)
  default = {
    auth_type          = "plain"
    transport_security = "tls"
    host               = "smtp-services.canonical.com"
    port               = "465"
    user               = ""
    password           = "" # override or set via locals
  }
}

variable "config_synapse" {
  description = "Configuration for the Synapse charm."
  type        = map(string)

  default = {
    allow_public_rooms_over_federation     = true
    enable_mjolnir                         = true
    experimental_alive_check               = "2m,5,21s"
    federation_domain_whitelist            = ""
    invite_checker_blocklist_allowlist_url = "https://cloud.haxxors.com/s/HP4D8ZDqrxymYDY/download"
    invite_checker_policy_rooms            = "fTjMjIzNKEsFlUIiru:neko.dev,zMUcYneBjSXhdJBGmb:ubuntu.com"
    public_baseurl                         = ""
    limit_remote_rooms_complexity          = 10.0
    notif_from                             = "noreply+chat@ubuntu.com"
    report_stats                           = false
    server_name                            = "chat-server-live.ubuntu.com"
  }
}

variable "constraints" {
  description = "Constraints for each application."
  type        = map(string)
  default = {
    synapse = "arch=amd64"
  }
}

variable "credentials" {
  description = "Static credentials map for various services."
  type        = map(string)
  default = {
    s3_access_key         = ""
    s3_secret_key         = ""
    lego_httpreq_username = ""
    lego_httpreq_password = ""
  }
  validation {
    condition = length(
      setsubtract(keys(var.enable), [
        "s3_access_key",
        "s3_secret_key",
        "lego_httpreq_username",
        "lego_httpreq_password",
      ])
    ) == 0

    error_message = "The keys in var.credentials must be one or more of: s3_access_key, s3_secret_key, lego_httpreq_username, lego_httpreq_password."
  }
}

variable "enable" {
  description = "A map to enable or disable various components."
  type        = map(bool)
  default     = {}
  validation {
    condition = length(
      setsubtract(keys(var.enable), [
        "lego",
        "nginx_ingress_integrator",
        "local_postgresql",
        "local_saml_integrator",
        "maubot",
        "redis_k8s",
        "s3_integrator_backup",
        "s3_integrator_media",
        "smtp_integrator"
      ])
    ) == 0

    error_message = "The keys in var.enable must be one or more of: lego, nginx_ingress_integrator, local_postgresql, local_saml_integrator, maubot, redis_k8s, s3_integrator_backup, s3_integrator_media, smtp_integrator."
  }
}

variable "hostname" {
  description = "Matrix server URL."
  type        = string
  default     = "chat-server-live.ubuntu.com"
}

variable "integrate_offers" {
  description = "Partial overrides for integrating specific offers."
  type        = map(bool)
  default     = {}
}

variable "lego_secret" {
  description = "Lego secret config."
  type = object({
    name  = string
    value = map(any)
  })

  default = {
    name = "synapse-lego-credentials"
    value = {
      httpreq-endpoint            = "https://lego-certs.canonical.com"
      httpreq-username            = ""
      httpreq-password            = ""
      httpreq-propagation-timeout = 600
    }
  }
}

variable "model" {
  description = "Partial overrides for the model configuration."
  type        = map(string)
  default     = {}
}

variable "offer_urls" {
  description = "Partial overrides for external offer URLs."
  type        = map(string)
  default     = {}
  validation {
    condition = length(
      setsubtract(keys(var.integrate_offers), [
        "postgresql",
        "prometheus",
        "grafana",
        "saml_integrator"
      ])
    ) == 0

    error_message = "The keys in var.integrate_offers must be one or more of: postgresql, prometheus, grafana, saml_integrator."
  }

  validation {
    condition = !(
      (contains(keys(var.enable), "local_postgresql") && contains(keys(var.integrate_offers), "postgresql"))
      ||
      (contains(keys(var.enable), "local_saml_integrator") && contains(keys(var.integrate_offers), "saml_integrator"))
    )

    error_message = <<EOT
If var.enable contains "local_postgresql", you cannot set "postgresql" in var.integrate_offers.
If var.enable contains "local_saml_integrator", you cannot set "saml_integrator" in var.integrate_offers.
EOT
  }
}

variable "revisions" {
  description = "Partial overrides for charm revisions. Keys follow same name as the variable enable."
  type        = map(number)
  default     = {}
}

variable "units" {
  description = "Partial overrides for unit counts. Only synapse for now."
  type        = map(number)
  default     = {}
}
