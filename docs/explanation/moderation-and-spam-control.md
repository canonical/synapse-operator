# Moderation and spam control

Moderation and spam control are critical to maintaining the health and security
of any communication platform, and Synapse is no exception. As a Matrix
homeserver, Synapse enables decentralized communication, which brings challenges
in combating abuse and ensuring user safety. This document
explores charm configurations and tools (Synapse Invite Checker Module and Mjolnir)
that can help set moderation and spam control in Synapse.

---

## Charm configurations

Synapse charm provide administrators with configuration options to fine-tune
moderation and spam control. Below are some key settings:

#### [`rc_joins_remote_burst_count`](https://charmhub.io/synapse/configurations#rc_joins_remote_burst_count)

Limits the number of remote rooms a user can join before being throttled.

- Default: `10`

#### [`rc_joins_remote_per_second`](https://charmhub.io/synapse/configurations#rc_joins_remote_per_second)

Defines the rate limit for how many remote rooms a user can join per second.

- Default: `0.01`

Refer to [Ratelimiting](https://element-hq.github.io/synapse/latest/usage/configuration/config_documentation.html#ratelimiting) in Synapse configuration documentation for more details.

#### [`block_non_admin_invites`](https://charmhub.io/synapse/configurations#block_non_admin_invites)
When enabled, this configuration blocks room invites to users on the server,
except for those sent by local server admins.
- Default: `false`

Refer to [block_non_admin_invites](https://element-hq.github.io/synapse/latest/usage/configuration/config_documentation.html#block_non_admin_invites) in Synapse configuration documentation for more details.

---

## Synapse Invite Checker Module

The **Synapse Invite Checker** module provides additional flexibility in
controlling spam and abuse by monitoring and filtering room invites. This tool
leverages allowlists and blocklists to ensure that only trusted sources can
send invites.

### Configurations

#### [`invite_checker_blocklist_allowlist_url`](https://charmhub.io/synapse/configurations#invite_checker_blocklist_allowlist_url)
URL to fetch a JSON file containing the allowlist and blocklist.

#### [`invite_checker_policy_rooms`](https://charmhub.io/synapse/configurations#invite_checker_policy_rooms)
A comma-separated list of rooms used by the invite checker module to enforce
policies.

### More Information
For details and implementation, visit the module’s repository: [Synapse Invite Checker](https://git.buechner.me/nbuechner/synapse-invite-checker).

---

## Mjolnir

Synapse charm also has Mjolnir in place. Mjolnir is an all-in-one moderation
tool designed to protect Synapse server from malicious invites, spam messages,
and other unwanted activities.

### Key Features

- Bans and Redactions: Quickly remove malicious users and their messages from
rooms.
- Anti-Spam: Automatically detect and mitigate spam activity.
- Server ACLs: Manage and enforce access control lists at the server level.
- Room Directory Changes and Alias Transfers: Adjust room visibility and manage
aliases efficiently.
- Account Deactivation: Disable abusive or compromised accounts.
- Room Shutdown: Close problematic rooms completely.

### More Information

For more details and implementation guidance, refer to the [Mjolnir GitHub repository](https://github.com/matrix-org/mjolnir).

