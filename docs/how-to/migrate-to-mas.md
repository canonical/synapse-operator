# How to back up and restore Synapse
This document shows how to migrate a legacy synapse homeserver (`latest/edge` track) to an oidc-native homeserver (`2/edge` track).

Note: This process is only NOT possible if the legacy synapse charm is using sqlite. During the migration process, do NOT remove the integration between the existing synapse charm and the database charm.

## Prepare the new synapse charm
### Deploy 2/edge on the same model
Use the same server name as the existing synapse charm.

```
juju deploy synapse server2 --channel=2/edge \
    --config server_name=<server_name> \
    --config public_baseurl=<public_baseurl>
```
### Integrate with postgresql
Integrate with the existing postgresql charm to set up the database for MAS, or if you prefer, deploy a fresh postgresql charm instance.

```
juju integrate server2:mas-database postgresql-k8s
```

Optionally, also set up the database for synapse using the same database instance

```
juju integrate server2:database postgresql-k8s
```

### Configure OIDC
This step is optional if the legacy synapse charm database does not contain users created with SAML.

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


## Preparing for the migration
### Transfer the homeserver yaml configuration
First, transfer the homeserver configuration from the existing charm to the new charm.

```
juju scp --container synapse server/0:/data/homeserver.yaml homeserver.yaml
juju scp --container synapse ./homeserver.yaml server-mas/0:/homeserver.yaml
```

## Migrating from the existing synapse charm to MAS
### Access the new synapse charm's container

```
juju ssh --container synapse server2/0 bash
```

From this point forward it's assumed that you are running commands in the `synapse` container of the new synapse charm.

### Fetch the generated oauth provider ID
We'll install `yq` to help fetch the Oauth provider id that the synapse charm has generated in its MAS configuration file
```
apt update
apt install wget
wget https://github.com/mikefarah/yq/releases/download/v4.44.3/yq_linux_amd64 -O /usr/bin/yq && chmod +x /usr/bin/yq

export OAUTH2_PROVIDER_ID=$(yq e '.upstream_oauth2.providers[0].id' /mas/config.yaml)
```
The Oauth2 provider id is needed 

### Perform user migration to MAS database
Run the `advisir` command as well as the `migrate` command with the `--dryRun` flag to check that there are no errors.
```
npx --yes @vector-im/syn2mas \
    --command advisor \
    --synapseConfigFile /homeserver.yaml \
    --masConfigFile /mas/config.yaml \
    --upstreamProviderMapping saml:$OAUTH2_PROVIDER_ID \

npx --yes @vector-im/syn2mas \
    --command migrate \
    --synapseConfigFile /homeserver.yaml \
    --masConfigFile /mas/config.yaml \
    --upstreamProviderMapping saml:$OAUTH2_PROVIDER_ID \
    --dryRun
```

Finally, run the migration command
```
npx --yes @vector-im/syn2mas \
    --command migrate \
    --synapseConfigFile /homeserver.yaml \
    --masConfigFile /mas/config.yaml \
    --upstreamProviderMapping saml:$OAUTH2_PROVIDER_ID
```

### Migrating everything elso to the new synapse instance
Follow the `backup-and-restore` procedure.

After the migration is complete, trigger the provisioning job to keep MAS in sync with synapse
```
mas-cli -c /mas/config.yaml manage provision-all-users
```

### (Optional) Configure the OIDC subject claim
After the migration, the `external_id` of the synapse user is used as the OIDC subject in MAS. Most of the time this needs to be changed so that the local account gets recognized by MAS when authenticating with the upstread provider. 

```
PGPASSWORD=$DB_PASSWORD psql --host $DB_HOST --username $DB_USER --port $DB_PORT mas
```

Then run the appropriate SQL command to update the subject field. For example, to use the email address as the OIDC subject, we run this SQL query:
```
update upstream_oauth_links
SET subject=(select email from user_emails where upstream_oauth_links.user_id=user_emails.user_id);

\q
```

After updating the OIDC subject in the MAS database, we need to also configure the OIDC subject claim:
```
juju config server2 oidc_subject_claim=user.email
```
