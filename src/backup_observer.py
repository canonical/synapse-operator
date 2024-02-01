# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""S3 Backup relation observer for Synapse."""

import logging
import typing

import ops
from charms.data_platform_libs.v0.s3 import CredentialsChangedEvent, S3Requirer
from ops.charm import ActionEvent
from ops.framework import Object
from ops.pebble import APIError, ExecError

import backup
import synapse

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
        self.framework.observe(self._charm.on.create_backup_action, self._on_create_backup_action)
        self.framework.observe(self._charm.on.list_backups_action, self._on_list_backups_action)

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
            logger.exception("Error creating S3Client.")
            self._charm.unit.status = ops.BlockedStatus(S3_INVALID_CONFIGURATION)
            return

        if not s3_client.can_use_bucket():
            self._charm.unit.status = ops.BlockedStatus(S3_CANNOT_ACCESS_BUCKET)
            return

        self._charm.unit.status = ops.ActiveStatus()

    def _on_s3_credential_gone(self, _: CredentialsChangedEvent) -> None:
        """Handle s3 credentials gone. Set unit status to active."""
        self._charm.unit.status = ops.ActiveStatus()

    def _on_create_backup_action(self, event: ActionEvent) -> None:
        """Create new backup of Synapse data.

        Args:
            event: Event triggering the create backup action.
        """
        try:
            s3_parameters = backup.S3Parameters(**self._s3_client.get_s3_connection_info())
        except ValueError:
            logger.exception("Wrong S3 configuration in backup action")
            event.fail("Wrong S3 configuration on create backup action. Check S3 integration.")
            return

        backup_passphrase = self._charm.config.get("backup_passphrase")
        if not backup_passphrase:
            event.fail("Missing backup_passphrase config option.")
            return

        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)

        try:
            backup_key = backup.create_backup(container, s3_parameters, backup_passphrase)
        except (backup.BackupError, APIError, ExecError):
            logger.exception("Error Creating Backup.")
            event.fail("Error Creating Backup.")
            return

        event.set_results({"result": "correct", "backup-id": backup_key})

    def _generate_backup_list_formatted(self, backup_list: typing.List[backup.S3Backup]) -> str:
        """Generate a formatted string for the backups.

        Args:
            backup_list: List of backups to create a formatted string for

        Returns:
            The formatted string of the backups
        """
        output = [f"{'backup-id':<21s} | {'last-modified':<28s} | {'size':>15s}"]
        output.append("-" * len(output[0]))
        for cur_backup in backup_list:
            output.append(
                f"{cur_backup.backup_key:<21s}"
                f"| {cur_backup.last_modified!s:<28s}"
                f"| {cur_backup.size:>15d}"
            )
        return "\n".join(output)

    def _on_list_backups_action(self, event: ActionEvent) -> None:
        """List backups in S3 configured storage.

        Args:
            event: Event triggering the list backups action.
        """
        try:
            s3_parameters = backup.S3Parameters(**self._s3_client.get_s3_connection_info())
        except ValueError:
            logger.exception("Wrong S3 configuration in list backups action")
            event.fail("Wrong S3 configuration on list backups action. Check S3 integration.")
            return

        try:
            s3_client = backup.S3Client(s3_parameters)
            backups = s3_client.list_backups()
        except backup.S3Error:
            logger.exception("Error while trying looking for backups.")
            self._charm.unit.status = ops.BlockedStatus(S3_CANNOT_ACCESS_BUCKET)
            return

        event.set_results(
            {
                "formatted": self._generate_backup_list_formatted(backups),
                "backups": {
                    backup.backup_key: {
                        "last-modified": str(backup.last_modified),
                        "size": str(backup.size),
                    }
                    for backup in backups
                },
            }
        )
