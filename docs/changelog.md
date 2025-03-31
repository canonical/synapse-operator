# Changelog

### 2025-03-27

- Add a new configuration, enable_media_sync_cleanup. When enabled, and if S3
integration for media is configured, the charm will run [s3_media_upload](https://github.com/matrix-org/synapse-s3-storage-provider#regular-cleanup-job) after a successful backup to
upload local media to S3 and then clean it up locally.

### 2025-03-10

- Add Draupnir as moderation tool. See [Draupnir documentation](https://the-draupnir-project.github.io/draupnir-documentation/) for more information about the project.

### 2025-02-24

- Add Synapse Service Health Grafana dashboard.

### 2025-02-21

- Refactor Synapse Grafana dashboard.

### 2025-01-09

- Add changelog for tracking user-relevant changes.
