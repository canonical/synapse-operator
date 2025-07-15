
variable "channel" {
  description = "The channel to use when deploying a charm."
  type        = string
  default     = "2/edge"
}

variable "revision" {
  description = "Revision number of the charm."
  type        = number
  default     = null
}

terraform {
  required_providers {
    juju = {
      version = "~> 0.20.0"
      source  = "juju/juju"
    }
  }
}

provider "juju" {}

module "synapse" {
  source   = "./.."
  app_name = "synapse"
  channel  = var.channel
  config = {
    server_name = "test"
  }
  model       = "test"
  revision    = var.revision
  constraints = "arch=amd64"
}
