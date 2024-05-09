# External access

Synapse charm requires external access depending on configuration options or Federation required.

## Configuration options

There are two configurations that changes Synapse behavior regarding external access:
- [trusted_key_servers](https://matrix-org.github.io/synapse/latest/usage/configuration/config_documentation.html#trusted_key_servers): comma separated list of trusted servers to download signing keys from.
Synapse configuration sets default to matrix.org.
- [report_stats](https://matrix-org.github.io/synapse/latest/usage/configuration/config_documentation.html#report_stats): configures whether to report statistics. See [Reporting Homeserver Usage Statistics](https://matrix-org.github.io/synapse/latest/usage/administration/monitoring/reporting_homeserver_usage_statistics.html) in Matrix documentation for information on what data is reported.
- enable_irc_bridge: configures whether to enable IRC bridging for Matrix.

## Federation required

Federation is the process by which users on different servers can participate in the same room.
For this to work, the server communicate with each other via HTTPS port 8448 or a different port
depending how the server is configured. See ["Setting up federation"](https://matrix-org.github.io/synapse/latest/federate.html)
in Matrix documentation for reference.