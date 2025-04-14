# Security

This document outlines common risks and possible mitigations specifically for the Synapse charm. It
focuses on configurations and protections available through the charm itself.

For details regarding upstream Synapse configuration and broader security considerations, please
refer to the [official Synapse documentation](https://element-hq.github.io/synapse/latest/welcome_and_overview.html).

## Risk: Loss of Data

Synapse configuration files or the database might be destroyed, corrupted, or become inaccessible.

### Mitigations

- Set up regular backups

  Follow the [charm documentation](https://charmhub.io/synapse/docs/how-to-backup-and-restore) for guidance on creating backups.

  Synapse uses a file to store its [signing key](https://element-hq.github.io/synapse/latest/usage/administration/backups.html#server-signing-key). If this file is lost, Synapse will generate
  a new one on startup. However, events signed with the old key will no longer be considered valid
  by other homeservers. So, it's critical having a backup of the charm.

- Avoid manual media deletion
  Manually deleting media files will cause Synapse to lose track of them. Always use Synapse's API
  for [media removal](https://element-hq.github.io/synapse/latest/admin_api/media_admin_api.html#purge-remote-media-api) to ensure consistency.

## Risk: Data Breach

Sensitive data, such as backups containing the signing key or moderation tool access tokens, could
be accessed or stolen by unauthorized individuals.

### Mitigations

- Secure your backup passphrase
  Store your [backup_passphrase](https://charmhub.io/synapse/configurations#backup_passphrase) securely and do not share it.

- Protect your moderation access token secret
  The [moderation_access_token_secret_id](https://charmhub.io/synapse/configurations#moderation_access_token_secret_id) Juju secret contains a token used by Moderation tool. This token
  grants high power-level access to multiple rooms. Treat it as sensitive and avoid sharing it.

## Risk: Unexpected Downtime

Synapse may become unavailable, preventing users from accessing the service.

### Mitigations

- Keep clients updated
  Synapse performance can be degraded by certain client behaviors, as noted in [Element issue #27867](https://github.com/vector-im/element-web/issues/27867). For example, some clients continuously query `/keys/query` for inactive users, leading to
  performance issues. Keeping clients updated helps avoid known performance problems.

- Ensure sufficient resources
  - Plan for adequate storage and database capacity (e.g., media storage and PostgreSQL).
  If the directory used by Synapse becomes full, the service will stop.
  - Consider integrating Synapse with S3 and enabling [enable_media_sync_cleanup](https://charmhub.io/synapse/configurations#enable_media_sync_cleanup) to manage media
  storage more efficiently.

## Risk: Denial-of-Service (DoS) Attacks

A denial-of-service attack could overwhelm Synapse with traffic, preventing legitimate users from accessing the service.

### Mitigations

- Rate-limit remote room joins
  The Synapse charm provides two configuration options:
  - [rc_joins_remote_burst_count](https://charmhub.io/synapse/configurations#rc_joins_remote_burst_count)
  - [rc_joins_remote_per_second](https://charmhub.io/synapse/configurations#rc_joins_remote_per_second)

  These settings control the rate at which users can join remote rooms. Refer to the [official documentation](https://matrix-org.github.io/synapse/latest/usage/configuration/config_documentation.html#rc_joins) for details on how to configure these values.

- Restrict invites and federation sources
  - `block_non_admin_invites`: Blocks invites from non-admin users.
  - `federation_domain_whitelist`: Comma-separated list of allowed federation domains.
  - `invite_checker_blocklist_allowlist_url`: Configure allowed and blocked lists for invite sources.
  - `ip_range_whitelist`: Comma-separated list of allowed IP address ranges (CIDR).
  - `limit_remote_rooms_complexity`: Limits the complexity of remote rooms; if a room exceeds this complexity, users will be prevented from joining.

## Risk: Security vulnerabilities

Running Synapse with one or more weakness that can be exploited by attackers.

### Mitigations

  - Keep the Juju and the charm updated. See more about Juju updates in the [documentation](https://documentation.ubuntu.com/juju/latest/explanation/juju-security/index.html#regular-updates-and-patches).
