# How to back up and restore Synapse
This document shows how to migrate a legacy synapse homeserver (`latest/edge` track) to an oidc-native homeserver (`2/edge` track).

## Initial deployment setup 
This document will cover the migration path for a synapse charm on the `latest\edge` track, using the `saml-integrator` charm to provide authentication users via SAML.
```

```

## Prepare the new synapse charm
### Deploy the 2/edge channel on the same model
We will use the same configuration as the existing synapse charm.

```
juju deploy synapse server-mas --channel=2/edge \
    --config server_name=<server_name> \
    --config public_baseurl=<public_baseurl>
```

### Integrate with postgresql
Integrate with the existing postgresql charm to set up the database for the new charm.

```
juju integrate server-mas:mas-database postgresql-k8s
juju integrate server-mas:database postgresql-k8s
```

### Configure OIDC
We will config
```
juju deploy oauth-external-idp-integrator oidc --channel=latest/edge
juju config oidc \
  issuer_url=<issuer_url> \
  authorization_endpoint=<authorization_endpoint> \
  userinfo_endpoint=<userinfo_endpoint> \
  token_endpoint=<token_endpoint> \
  introspection_endpoint=<introspection_endpoint> \
  jwks_endpoint=<jwks_endpoint> \
  client_id=<client_id> \
  client_secret=<client_secret>
```

## Synapse database migration
### Stop all services on the new and the existing synapse charm
```
juju ssh --container synapse server-mas/0 "pebble stop synapse; pebble stop synapse-mas; pebble stop stats-exporter"
juju ssh --container synapse server/0 "pebble stop synapse; pebble stop stats-exporter"
```

### Connect to the database
```
juju ssh --container synapse server-mas/0 bash
```

The following commands assume that you are in the `synapse` container of the `server-mas` application.
```
apt update
apt install wget postgresql-client -y
wget https://github.com/mikefarah/yq/releases/download/v4.44.3/yq_linux_amd64 -O /usr/bin/yq && chmod +x /usr/bin/yq
```

Copy the original synapse database
```
DB_HOST=$(yq e '.database.args.host' /data/homeserver.yaml)
DB_PORT=$(yq e '.database.args.port' /data/homeserver.yaml)
DB_PASSWORD=$(yq e '.database.args.password' /data/homeserver.yaml)
DB_USER=$(yq e '.database.args.user' /data/homeserver.yaml)
PGPASSWORD=$DB_PASSWORD psql --host $DB_HOST --username $DB_USER --port $DB_PORT postgres -c 'drop database "server-mas";'
PGPASSWORD=$DB_PASSWORD psql --host $DB_HOST --username $DB_USER --port $DB_PORT postgres -c "create database \"server-mas\" with template server owner $DB_USER;"
```

In case where postgres gives you an error saying "", drop all connections from the database
```
PGPASSWORD=$DB_PASSWORD psql --host $DB_HOST --username $DB_USER --port $DB_PORT postgres -c SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = "server" AND pid <> pg_backend_pid();
```

## Migrating users to MAS
### Perform user migration to MAS database
Run the `advisir` command as well as the `migrate` command with the `--dryRun` flag to check that there are no errors.
```
npx --yes @vector-im/syn2mas \
    --command advisor \
    --synapseConfigFile /data/homeserver.yaml

OAUTH2_PROVIDER_ID=$(yq e '.upstream_oauth2.providers[0].id' /mas/config.yaml)
npx --yes @vector-im/syn2mas \
    --command migrate \
    --synapseConfigFile /data/homeserver.yaml \
    --masConfigFile /mas/config.yaml \
    --upstreamProviderMapping saml:$OAUTH2_PROVIDER_ID \
    --dryRun
```

Finally, run the migration command
```
npx --yes @vector-im/syn2mas \
    --command migrate \
    --synapseConfigFile /data/homeserver.yaml \
    --masConfigFile /mas/config.yaml \
    --upstreamProviderMapping saml:$OAUTH2_PROVIDER_ID
```

### Configure the OIDC subject claim
After the migration, the `external_id` of the synapse user is used as the OIDC subject in MAS. Most of the time this needs to be changed so that the local account gets recognized by MAS when authenticating with the upstream provider. 

```
psql $(yq e '.database.uri' /mas/config.yaml)
```

Then run the appropriate SQL command to update the subject field. For example, to use the email address as the OIDC subject, we run this SQL query:
```
update upstream_oauth_links
SET subject=(select email from user_emails where upstream_oauth_links.user_id=user_emails.user_id);

\q
```

After updating the OIDC subject in the MAS database, we need to also configure the OIDC subject claim:
```
juju config server-mas oidc_subject_claim=user.email
```
