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
}

resource "juju_application" "ingress" {
  name  = "ingress"
  model = juju_model.synapse.name
  charm {
    name = "nginx-ingress-integrator"
  }
}

resource "juju_application" "db" {
  name  = "db"
  model = juju_model.synapse.name
  charm {
    name = "postgresql-k8s"
  }
}

resource "juju_integration" "ingress" {
  model = juju_model.synapse.name

  application {
    name = juju_application.synapse.name
  }

  application {
    name = juju_application.ingress.name
  }
}

resource "juju_integration" "db" {
  model = juju_model.synapse.name

  application {
    name     = juju_application.db.name
    endpoint = "db"
  }

  application {
    name = juju_application.synapse.name
  }
}
