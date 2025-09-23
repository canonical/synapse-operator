terraform {
  required_version = ">= 1.6.6"
  required_providers {
    vault = {
      source  = "hashicorp/vault"
      version = "~> 5.0.0"
    }
    juju = {
      source  = "juju/juju"
      version = "~> 0.20.0"
    }
  }
}
