output "app_name" {
  description = "Name of the deployed applications."
  value = {
    lego                     = local.enable.lego ? module.lego.app_name : null
    nginx_ingress_integrator = local.enable.nginx_ingress_integrator ? module.nginx_ingress_integrator.app_name : null
    redis_k8s                = local.enable.redis_k8s ? module.redis_k8s.app_name : null
    s3_integrator_backup     = local.enable.s3_integrator_backup ? module.s3_integrator_backup.app_name : null
    s3_integrator_media      = local.enable.s3_integrator_media ? module.s3_integrator_media.app_name : null
    smtp_integrator          = local.enable.smtp_integrator ? module.smtp_integrator.app_name : null
    local_saml_integrator    = local.enable.local_saml_integrator ? module.local_saml_integrator[0].app_name : null
    local_postgresql         = local.enable.local_postgresql ? module.local_postgresql.application_name : null
    synapse                  = module.synapse.app_name
  }
}
