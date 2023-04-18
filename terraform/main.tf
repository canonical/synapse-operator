terraform {
  required_providers {
    juju = {
      source  = "juju/juju"
      version = "~> 0.6.0"
    }
  }
}

provider "juju" {}

resource "juju_model" "synapse" {
  name = var.model_name
}

resource "juju_application" "synapse" {
  name  = "synapse"
  model = juju_model.synapse.name
  charm {
    name    = "matrix-operator"
    channel = "edge"
    series  = "jammy"
  }
  depends_on = [
    juju_application.db
  ]
}

resource "juju_application" "db" {
  name  = "db"
  model = juju_model.synapse.name
  charm {
    name = "postgresql-k8s"
    channel = "14"
  }
}
