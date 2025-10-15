output "applications" {
  description = "Applications deployed by the product."
  value = {
    lego                     = local.enable.lego ? module.lego : null
    nginx_ingress_integrator = local.enable.nginx_ingress_integrator ? module.nginx_ingress_integrator : null
    redis_k8s                = local.enable.redis_k8s ? module.redis_k8s : null
    s3_integrator_backup     = local.enable.s3_integrator_backup ? module.s3_integrator_backup: null
    s3_integrator_media      = local.enable.s3_integrator_media ? module.s3_integrator_media : null
    smtp_integrator          = local.enable.smtp_integrator ? module.smtp_integrator : null
    local_saml_integrator    = local.enable.local_saml_integrator ? module.local_saml_integrator : null
    local_postgresql         = local.enable.local_postgresql ? module.local_postgresql: null
    synapse                  = module.synapse
    maubot                   = module.maubot
  }
}
