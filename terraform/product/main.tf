# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

# Juju model

resource "juju_model" "synapse" {
  name = local.model.name

  cloud {
    name   = local.model.cloud_name
    region = local.model.cloud_region
  }

  config      = local.config_model
  constraints = local.model.constraints

  lifecycle {
    prevent_destroy = true
  }
}

# Modules

module "synapse" {
  source      = "./.."
  app_name    = local.app_names.synapse
  channel     = local.channels.synapse
  config      = local.config_synapse
  constraints = var.constraints.synapse
  model       = juju_model.synapse.name
  revision    = local.revisions.synapse
  units       = local.units.synapse
}

module "lego" {
  count    = local.enable.nginx_ingress_integrator && local.enable.lego ? 1 : 0
  model    = juju_model.synapse.name
  source   = "../modules/lego"
  channel  = local.channels.lego
  revision = local.revisions.lego
  config   = local.config_lego
}

resource "juju_secret" "lego_credentials" {
  count = local.enable.nginx_ingress_integrator && local.enable.lego ? 1 : 0
  model = local.model.name
  name  = local.lego_secret.name
  value = local.lego_secret.value
}

resource "juju_access_secret" "lego_credentials_access" {
  count = local.enable.nginx_ingress_integrator && local.enable.lego ? 1 : 0
  model = local.model.name
  applications = [
    module.lego[0].app_name
  ]
  secret_id = juju_secret.lego_credentials[0].secret_id
}

module "maubot" {
  count    = local.enable.maubot ? 1 : 0
  model    = juju_model.synapse.name
  source   = "../modules/maubot"
  channel  = local.channels.maubot
  revision = local.revisions.maubot
}

module "nginx_ingress_integrator" {
  count    = local.enable.nginx_ingress_integrator ? 1 : 0
  model    = juju_model.synapse.name
  source   = "../modules/nginx-ingress-integrator"
  app_name = local.app_names.nginx_ingress_integrator
  channel  = local.channels.nginx_ingress_integrator
  revision = local.revisions.nginx_ingress_integrator
  config   = local.config_nginx_ingress_integrator
}

module "redis_k8s" {
  count    = local.enable.redis_k8s ? 1 : 0
  model    = juju_model.synapse.name
  source   = "../modules/redis-k8s"
  app_name = local.app_names.redis_k8s
  channel  = local.channels.redis_k8s
  revision = local.revisions.redis_k8s
}

module "s3_integrator_backup" {
  count         = local.enable.s3_integrator_backup ? 1 : 0
  model         = juju_model.synapse.name
  source        = "../modules/s3-integrator"
  app_name      = local.app_names.s3_integrator_backup
  channel       = local.channels.s3_integrator_backup
  revision      = local.revisions.s3_integrator_backup
  config        = local.config_s3_integrator_backup
  s3_access_key = local.credentials.s3_access_key
  s3_secret_key = local.credentials.s3_secret_key
}

module "s3_integrator_media" {
  count         = local.enable.s3_integrator_media ? 1 : 0
  model         = juju_model.synapse.name
  source        = "../modules/s3-integrator"
  app_name      = local.app_names.s3_integrator_media
  channel       = local.channels.s3_integrator_media
  revision      = local.revisions.s3_integrator_media
  config        = local.config_s3_integrator_media
  s3_access_key = local.credentials.s3_access_key
  s3_secret_key = local.credentials.s3_secret_key
}

module "smtp_integrator" {
  count    = local.enable.smtp_integrator ? 1 : 0
  model    = juju_model.synapse.name
  source   = "../modules/smtp-integrator"
  channel  = local.channels.smtp_integrator
  revision = local.revisions.smtp_integrator
  config   = local.config_smtp_integrator
}

module "local_saml_integrator" {
  count    = local.enable.local_saml_integrator ? 1 : 0
  model    = juju_model.synapse.name
  source   = "git::https://github.com/canonical/saml-integrator-operator//terraform/charm?ref=rev104&depth=1"
  channel  = local.channels.local_saml_integrator
  revision = local.revisions.local_saml_integrator
  config   = local.config_local_saml_integrator
}

module "local_postgresql" {
  count           = local.enable.local_postgresql ? 1 : 0
  juju_model_name = juju_model.synapse.name
  source          = "git::https://github.com/canonical/postgresql-k8s-operator//terraform?ref=rev667&depth=1"
  app_name        = local.app_names.local_postgresql
  channel         = local.channels.local_postgresql
  revision        = local.revisions.local_postgresql
  config          = local.config_local_postgresql
  storage_size    = "1G"
}

# Integrations with offers

resource "juju_integration" "synapse_postgresql" {
  count = local.integrate_offers.postgresql ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.synapse.app_name
    endpoint = module.synapse.endpoints.database
  }

  application {
    offer_url = local.offer_urls.postgresql
  }
}

resource "juju_integration" "synapse_prometheus" {
  count = local.integrate_offers.prometheus ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.synapse.app_name
    endpoint = module.synapse.endpoints.metrics_endpoint
  }

  application {
    offer_url = local.offer_urls.prometheus
  }
}

resource "juju_integration" "synapse_grafana" {
  count = local.integrate_offers.grafana ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.synapse.app_name
    endpoint = module.synapse.endpoints.grafana_dashboard
  }

  application {
    offer_url = local.offer_urls.grafana
  }
}

resource "juju_integration" "synapse_saml" {
  count = local.integrate_offers.saml_integrator ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.synapse.app_name
    endpoint = module.synapse.endpoints.saml
  }

  application {
    offer_url = local.offer_urls.saml_integrator
  }
}

resource "juju_integration" "maubot_postgresql" {
  count = local.enable.maubot && local.integrate_offers.postgresql ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.maubot[0].app_name
    endpoint = module.maubot[0].endpoints.postgresql
  }

  application {
    offer_url = local.offer_urls.postgresql
  }
}

resource "juju_integration" "maubot_prometheus" {
  count = local.enable.maubot && local.integrate_offers.prometheus ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.maubot[0].app_name
    endpoint = module.maubot[0].endpoints.metrics_endpoint
  }

  application {
    offer_url = local.offer_urls.prometheus
  }
}

resource "juju_integration" "maubot_grafana" {
  count = local.enable.maubot && local.integrate_offers.grafana ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.maubot[0].app_name
    endpoint = module.maubot[0].endpoints.grafana_dashboard
  }

  application {
    offer_url = local.offer_urls.grafana
  }
}

# Integrations between modules

resource "juju_integration" "synapse_maubot" {
  count = local.enable.maubot ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.synapse.app_name
    endpoint = module.synapse.endpoints.matrix_auth
  }

  application {
    name     = module.maubot[0].app_name
    endpoint = module.synapse.endpoints.matrix_auth
  }
}

resource "juju_integration" "synapse_nginx_ingress_integrator" {
  count = local.enable.nginx_ingress_integrator ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.synapse.app_name
    endpoint = module.synapse.endpoints.nginx_route
  }

  application {
    name     = module.nginx_ingress_integrator[0].app_name
    endpoint = module.nginx_ingress_integrator[0].endpoints.nginx_route
  }
}

resource "juju_integration" "synapse_s3_integrator_backup" {
  count = local.enable.s3_integrator_backup ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.synapse.app_name
    endpoint = module.synapse.endpoints.backup
  }

  application {
    name     = module.s3_integrator_backup[0].app_name
    endpoint = module.s3_integrator_backup[0].endpoints.s3_credentials
  }
}

resource "juju_integration" "synapse_s3_integrator_media" {
  count = local.enable.s3_integrator_media ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.synapse.app_name
    endpoint = module.synapse.endpoints.media
  }

  application {
    name     = module.s3_integrator_media[0].app_name
    endpoint = module.s3_integrator_media[0].endpoints.s3_credentials
  }
}

resource "juju_integration" "synapse_smtp_integrator" {
  count = local.enable.smtp_integrator ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.synapse.app_name
    endpoint = module.synapse.endpoints.smtp
  }

  application {
    name     = module.smtp_integrator[0].app_name
    endpoint = module.smtp_integrator[0].endpoints.smtp
  }
}

resource "juju_integration" "synapse_local_saml_integrator" {
  count = local.enable.local_saml_integrator ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.synapse.app_name
    endpoint = module.synapse.endpoints.saml
  }

  application {
    name     = module.local_saml_integrator[0].app_name
    endpoint = module.local_saml_integrator[0].provides.saml
  }
}

resource "juju_integration" "synapse_redis" {
  count = local.enable.redis_k8s ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.synapse.app_name
    endpoint = module.synapse.endpoints.redis
  }

  application {
    name     = module.redis_k8s[0].app_name
    endpoint = module.redis_k8s[0].endpoints.redis
  }
}

resource "juju_integration" "nginx_lego" {
  count = local.enable.lego && local.enable.nginx_ingress_integrator ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.nginx_ingress_integrator[0].app_name
    endpoint = module.nginx_ingress_integrator[0].endpoints.certificates
  }

  application {
    name     = module.lego[0].app_name
    endpoint = module.lego[0].endpoints.certificates
  }
}

resource "juju_integration" "maubot_local_postgresql" {
  count = local.enable.maubot && local.enable.local_postgresql ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.maubot[0].app_name
    endpoint = module.maubot[0].endpoints.postgresql
  }

  application {
    name     = module.local_postgresql[0].application_name
    endpoint = module.local_postgresql[0].provides.database
  }
}

resource "juju_integration" "synapse_local_postgresql" {
  count = local.enable.local_postgresql ? 1 : 0
  model = juju_model.synapse.name

  application {
    name     = module.synapse.app_name
    endpoint = module.synapse.endpoints.database
  }

  application {
    name     = module.local_postgresql[0].application_name
    endpoint = module.local_postgresql[0].provides.database
  }
}
