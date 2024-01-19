# Integrations

### db

_Interface_: pgsql
_Supported charms_: [postgresql-k8s](https://charmhub.io/postgresql-k8s),
[postgresql](https://charmhub.io/postgresql)

Database integration is a required relation for the Synapse charm to supply
structured data
storage for Synapse.

Example db integrate command: `juju integrate synapse postgresql-k8s:db`

### grafana-dashboard

_Interface_: grafana-dashboard
_Supported charms_: [grafana-k8s](https://charmhub.io/grafana-k8s)

Grafana-dashboard relation enables quick dashboard access already tailored to
fit the needs of operators to monitor the charm. The template for the Grafana
dashboard for Synapse charm can
be found at `/src/grafana_dashboards/synapse.json`. It was extracted from
[matrix/synapse repository](https://github.com/matrix-org/synapse/blob/master/contrib/grafana/synapse.json). In Grafana UI, it can be
found as “Synapse Operator” under the General section of the dashboard browser
(`/dashboards`). Modifications to the dashboard can be made but will not be
persisted upon restart/redeployment of the charm.

Grafana-Prometheus integrate command:
```
juju integrate grafana-k8s:grafana-source prometheus-k8s:grafana-source
```
Grafana-dashboard integrate command:
```
juju integrate synapse grafana-dashboard`
```

### ingress

_Interface_: ingress
_Supported charms_: [nginx-ingress-integrator](https://charmhub.io/nginx-ingress-integrator),
[traefik](https://charmhub.io/traefik-k8s)

Ingress manages external http/https access to services in a kubernetes cluster.
Note that the kubernetes cluster must already have an nginx ingress controller
already deployed. Documentation to enable ingress in MicroK8s can be found in
[Addon: Ingress](https://microk8s.io/docs/addon-ingress).

Example ingress integrate command: `juju integrate synapse nginx-ingress-integrator`

### metrics-endpoint

_Interface_: [prometheus_scrape](https://charmhub.io/interfaces/prometheus_scrape-v0)
_Supported charms_: [prometheus-k8s](https://charmhub.io/prometheus-k8s)

Metrics-endpoint relation allows scraping the `/metrics` endpoint provided by
Synapse. The metrics are exposed in the [open metrics format](https://github.com/OpenObservability/OpenMetrics/blob/main/specification/OpenMetrics.md#data-model) and will only be scraped by Prometheus once the
relation becomes active. For more information about the metrics exposed, refer to ["How to monitor Synapse metrics using Prometheus"](https://github.com/matrix-org/synapse/blob/master/docs/metrics-howto.md).

Metrics-endpoint integrate command: `juju integrate synapse prometheus-k8s`

### saml

_Interface_: saml
_Supported charms_: [saml-integrator](https://charmhub.io/saml-integrator/)

Integrating Synapse with SAML Integrator provides SAML configuration details so
users can be authenticated in via a SAML server.

Example saml integrate command: `juju integrate synapse saml-integrator:saml`

Note that `public_baseurl` configuration set the public-facing base URL that
clients use to access this Homeserver. It's used as `entity_id` if set instead of
https://server_name.

See more information in [Charm Architecture](https://charmhub.io/synapse/docs/explanation-charm-architecture).


### smtp

_Interface_: smtp
_Supported charms_: [smtp-integrator](https://charmhub.io/smtp-integrator/)

Integrating Synapse with SMTP Integrator provides SMTP configuration details so
a smtp server can be used in Synapse.

Example smtp integrate command: `juju integrate synapse smtp-integrator:smtp`

Note that the smtp-integrator provides two interfaces, `smtp` and `smtp-legacy`. 
Only use the first one if the Juju version used supports secrets. The "From" email
is set with the Synapse configuration option `notif_from`.

For the smtp-integrator, insecure configurations with `transport_security=none` or not
authenticated connections with `auth_type=none` are not supported.

See more information in [Charm Architecture](https://charmhub.io/synapse/docs/explanation-charm-architecture).


### backup

_Interface_: s3
_Supported charms_: [s3-integrator](https://charmhub.io/s3-integrator/)

In order to perform backups, Synapse has to be integrated with the s3-integrator charm using the
endpoint backup. Backups will be stored, listed and recovered from the location
indicated in the S3 compatible object storage provider configuration provided by the integration.
The Synapse charm will back up the media files, signing keys and sqlite database file if applicable.
If Synapse database integration is used, the Synapse charm will not back up the related database.

Example backup integrate command: `juju integrate synapse:backup s3-integrator`