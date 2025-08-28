# Security

This document outlines common risks and possible best practices specifically for the Synapse charm. It
focuses on configurations and protections available through the charm itself.

For details regarding upstream Synapse configuration and broader security considerations, please
refer to the [official Synapse documentation](https://element-hq.github.io/synapse/latest/welcome_and_overview.html).

## Risks

The following items include descriptions of the risks, their corresponding best practices for mitigation, as well as links to related documentation and configuration guidelines.

### Loss of data

Synapse configuration files or the database might be destroyed, corrupted, or become inaccessible.

#### Best practices

- Set up regular backups:

  Follow the [charm documentation](https://charmhub.io/synapse/docs/how-to-backup-and-restore) for guidance on creating backups.

  Synapse uses a file to store its [signing key](https://element-hq.github.io/synapse/latest/usage/administration/backups.html#server-signing-key). If this file is lost, Synapse will generate
  a new one on startup. However, events signed with the old key will no longer be considered valid
  by other homeservers, so it's critical to have a backup of the charm.

- Avoid manual media deletion:

  Manually deleting media files will cause Synapse to lose track of them. Always use Synapse's API
  for [media removal](https://element-hq.github.io/synapse/latest/admin_api/media_admin_api.html#purge-remote-media-api) to ensure consistency.

### Data breach

Sensitive data, such as backups containing the signing key or moderation tool access tokens, could
be accessed or stolen by unauthorized individuals.

#### Best practices

- Secure your backup passphrase:

  Store your [`backup_passphrase`](https://charmhub.io/synapse/configurations#backup_passphrase) securely and do not share it.

- Protect your moderation access token secret:

  The [`moderation_access_token_secret_id`](https://charmhub.io/synapse/configurations#moderation_access_token_secret_id) Juju secret contains a token used by the moderation tool. This token
  grants high power-level access to multiple rooms. Treat it as sensitive and avoid sharing it.

### Unexpected downtime

Synapse may become unavailable, preventing users from accessing the service.

#### Best practices

- Keep clients updated:

  Synapse performance can be degraded by certain client behaviors, as noted in [Element issue #27867](https://github.com/vector-im/element-web/issues/27867). For example, some clients continuously query `/keys/query` for inactive users, leading to
  performance issues. Keeping clients updated helps avoid known performance problems.

- Ensure sufficient resources:

  - Plan for adequate storage and database capacity (e.g., media storage and PostgreSQL).
  If the directory used by Synapse becomes full, the service will stop.
  - Consider integrating Synapse with S3 and enabling [`enable_media_sync_cleanup`](https://charmhub.io/synapse/configurations#enable_media_sync_cleanup) to manage media
  storage more efficiently.

<!-- vale Canonical.007-Headings-sentence-case = NO -->
### Denial-of-Service (DoS) attacks
<!-- vale Canonical.007-Headings-sentence-case = YES -->

A denial-of-service attack could overwhelm Synapse with traffic, preventing legitimate users from accessing the service.

#### Best practices

- Rate-limit remote room joins:

  The Synapse charm provides two configuration options:
  - [`rc_joins_remote_burst_count`](https://charmhub.io/synapse/configurations#rc_joins_remote_burst_count)
  - [`rc_joins_remote_per_second`](https://charmhub.io/synapse/configurations#rc_joins_remote_per_second)

  These configurations control the rate at which users can join remote rooms. Refer to the [official documentation](https://matrix-org.github.io/synapse/latest/usage/configuration/config_documentation.html#rc_joins) for details on how to configure these values.

- Restrict invites and federation sources:

  The Synapse charm provides the following configuration options that can help with restricting access:

  - [`block_non_admin_invites`](https://charmhub.io/synapse/configurations#block_non_admin_invites): Blocks invites from non-admin users.
  - [`federation_domain_whitelist`](https://charmhub.io/synapse/configurations#federation_domain_whitelist): Comma-separated list of allowed federation domains.
  - [`invite_checker_blocklist_allowlist_url`](https://charmhub.io/synapse/configurations#invite_checker_blocklist_allowlist_url): Configure allowed and blocked lists for invite sources.
  - [`ip_range_whitelist`](https://charmhub.io/synapse/configurations#ip_range_whitelist): Comma-separated list of allowed IP address ranges (CIDR).
  - [`limit_remote_rooms_complexity`](https://charmhub.io/synapse/configurations#limit_remote_rooms_complexity): Limits the complexity of remote rooms; if a room exceeds this complexity, users will be prevented from joining.

### Security vulnerabilities

Running Synapse with one or more weakness that can be exploited by attackers.

#### Best practices

  - Keep the Juju and the charm updated. See more about Juju updates in the [documentation](https://documentation.ubuntu.com/juju/latest/explanation/juju-security/index.html#regular-updates-and-patches).

### Unencrypted traffic

When HTTPS is not enabled, data exchanged between Synapse and its clients — including authentication tokens, registration secrets, and personal information — is transmitted in plain text. This leaves the communication vulnerable to interception, tampering, and impersonation by malicious actors.

#### Best practices

- Always enable HTTPS:

  Configure Synapse to use HTTPS for all clients communication. The Synapse charm supports ingress integration, allowing HTTPS to be enabled when integrating with charms such as [nginx-ingress-integrator](https://charmhub.io/nginx-ingress-integrator) and [traefik-k8s](https://charmhub.io/traefik-k8s).
