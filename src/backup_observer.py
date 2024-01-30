# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""S3 Backup relation observer for Synapse."""

import logging

import ops
from charms.data_platform_libs.v0.s3 import CredentialsChangedEvent, S3Requirer
from ops.framework import Object

import backup

logger = logging.getLogger(__name__)

S3_CANNOT_ACCESS_BUCKET = "Backup: S3 bucket does not exist or cannot be accessed"
S3_INVALID_CONFIGURATION = "Backup: S3 configuration is invalid"


class BackupObserver(Object):
    """The S3 backup relation observer."""

    _S3_RELATION_NAME = "backup"

    def __init__(self, charm: ops.CharmBase):
        """Initialize the backup object.

        Args:
            charm: The parent charm the backups are made for.
        """
        super().__init__(charm, "backup")

        self._charm = charm
        self._s3_client = S3Requirer(self._charm, self._S3_RELATION_NAME)
        self.framework.observe(
            self._s3_client.on.credentials_changed, self._on_s3_credential_changed
        )
        self.framework.observe(self._s3_client.on.credentials_gone, self._on_s3_credential_gone)

    def _on_s3_credential_changed(self, _: CredentialsChangedEvent) -> None:
        """Check new S3 credentials set the unit to blocked if they are wrong."""
        try:
            s3_parameters = backup.S3Parameters(**self._s3_client.get_s3_connection_info())
        except ValueError:
            self._charm.unit.status = ops.BlockedStatus(S3_INVALID_CONFIGURATION)
            return

        try:
            s3_client = backup.S3Client(s3_parameters)
        except backup.S3Error:
            self._charm.unit.status = ops.BlockedStatus(S3_INVALID_CONFIGURATION)
            return

        if not s3_client.can_use_bucket():
            self._charm.unit.status = ops.BlockedStatus(S3_CANNOT_ACCESS_BUCKET)
            return

        self._charm.unit.status = ops.ActiveStatus()

    def _on_s3_credential_gone(self, _: CredentialsChangedEvent) -> None:
        """Handle s3 credentials gone. Set unit status to active."""
        self._charm.unit.status = ops.ActiveStatus()
