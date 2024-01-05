# How to integrate with SMTP for sending notifications

This document shows how to integrate Synapse with SMTP for sending
emails. Synapse should be deployed beforehand.

## Deploy smtp-integrator charm

For synapse to use SMTP, it uses the smtp-integrator charm. Replace the configuration options with your specific configuration.
```
juju deploy smtp-integrator --channel edge
juju config smtp-integrator host=<smtp host> port=<smtp port> user=<smtp auth user> password=<smtp auth password> auth_type=plain transport_security=tls
```

## Configure email to use in `From`

Configure the "From" mail for Synapse with:
```
juju config synapse notif_from=<email to use in the "From" address>
```

## Integrate with Synapse

You can run it with the legacy integration `smtp-legacy` or with
the new integration using secrets `smtp`. A Juju version
with secrets is required for the `smtp` integration.

With the old integration without using secrets, run:
```
juju integrate smtp-integrator:smtp-legacy synapse:smtp
```
For the new integration with secrets, run:
```
juju integrate smtp-integrator:smtp synapse:smtp
```