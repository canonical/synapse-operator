# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provides backup functionality for Synapse."""

import datetime
import logging
import os
import pathlib
from typing import Any, Dict, Generator, Iterable, NamedTuple, Optional

import boto3
import ops
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from botocore.exceptions import ConnectionError as BotoConnectionError
from ops.pebble import APIError, ExecError

import synapse
from s3_parameters import S3Parameters

AWS_COMMAND = "/aws/dist/aws"

# The configuration files to back up consist in the signing keys
# plus the sqlite db if it exists.
BACKUP_FILE_PATTERNS = ["*.key", "homeserver.db*"]

# For the data directory, inside the "media" directory, all directories starting
# with local_ will be backed up. The directories starting with "remote_" are from
# other server and is it not necessary to back them up.
MEDIA_LOCAL_DIR_PATTERN = "local_*"

# A smaller value will minimise memory requirements. A bigger value can make the transfer faster.
# As an alternative the option max_bandwidth could be used to limit speed.
S3_MAX_CONCURRENT_REQUESTS = 1


PASSPHRASE_FILE = os.path.join(synapse.SYNAPSE_CONFIG_DIR, ".gpg_backup_passphrase")  # nosec
BASH_COMMAND = "/usr/bin/bash"
BACKUP_ID_FORMAT = "%Y%m%d%H%M%S%f"


logger = logging.getLogger(__name__)


class BackupError(Exception):
    """Generic backup Exception."""


class S3Error(Exception):
    """Generic S3 Exception."""


class S3Backup(NamedTuple):
    """Information about a backup file from S3.

    Attributes:
        backup_id: backup id
        last_modified: last modified date in S3
        size: size in bytes
    """

    backup_id: str
    last_modified: datetime.datetime
    size: int


class S3Client:
    """S3 Client Wrapper around boto3 library."""

    # New methods will be needed to at least list, check and delete backups
    # pylint: disable=too-few-public-methods
    def __init__(self, s3_parameters: S3Parameters):
        """Initialize the S3 client.

        Args:
            s3_parameters: Parameter to configure the S3 connection.
        """
        self._s3_parameters = s3_parameters
        self._client = self._create_client()
        self._prefix = _s3_path(self._s3_parameters.path)

    def _create_client(self) -> Any:
        """Create new boto3 S3 client.

        Creating the client does not connect to the server.

        Returns:
            New instantiated boto3 S3 client.

        Raises:
            S3Error: If it was not possible to create the client.
        """
        try:
            s3_client_config = Config(
                region_name=self._s3_parameters.region,
                s3={
                    "addressing_style": self._s3_parameters.addressing_style,
                },
            )
            s3_client = boto3.client(
                "s3",
                self._s3_parameters.region,
                aws_access_key_id=self._s3_parameters.access_key,
                aws_secret_access_key=self._s3_parameters.secret_key,
                endpoint_url=self._s3_parameters.endpoint,
                config=s3_client_config,
            )
        except (TypeError, ValueError, BotoCoreError) as exc:
            raise S3Error("Error creating S3 client") from exc
        return s3_client

    def can_use_bucket(self) -> bool:
        """Check if a bucket exists and is accessible in an S3 compatible object store.

        Returns:
            True if the bucket exists and is accessible
        """
        try:
            self._client.head_bucket(Bucket=self._s3_parameters.bucket)
        except (ClientError, BotoConnectionError):
            logger.exception(
                "Bucket %s doesn't exist or you don't have access to it.",
                self._s3_parameters.bucket,
            )
            return False
        return True

    def delete_backup(self, backup_id: str) -> None:
        """Delete a backup stored in S3 in the current s3 configuration.

        Args:
            backup_id: backup id to delete.

        Raises:
            S3Error: If there was an error deleting the backup.
        """
        object_key = _s3_path(prefix=self._s3_parameters.path, object_name=backup_id)

        try:
            self._client.delete_object(Bucket=self._s3_parameters.bucket, Key=object_key)
        except ClientError as exc:
            raise S3Error(f"Cannot delete backup_id {backup_id} from bucket") from exc

    def exists_backup(self, backup_id: str) -> bool:
        """Check if a backup-id exists in S3.

        Args:
            backup_id: backup id to delete.

        Returns:
            True if the backup-id exists, False otherwise

        Raises:
            S3Error: If there was an error checking the backup.
        """
        object_key = _s3_path(prefix=self._s3_parameters.path, object_name=backup_id)
        try:
            self._client.head_object(Bucket=self._s3_parameters.bucket, Key=object_key)
        except ClientError as exc:
            if "Error" in exc.response and exc.response["Error"].get("Code") == "404":
                return False
            logger.exception("Error when checking if S3 object exists using head_object.")
            raise S3Error("Error when checking if S3 object exists using head_object.") from exc

        return True

    def list_backups(self) -> list[S3Backup]:
        """List the backups stored in S3 in the current s3 configuration.

        Returns:
            list of backups.
        """
        backups = []
        for item in self._list_s3_objects():
            s3_object_key = pathlib.Path(item["Key"])
            backup_id = s3_object_key.relative_to(self._prefix)
            backup = S3Backup(
                backup_id=str(backup_id),
                last_modified=item["LastModified"],
                size=item["Size"],
            )
            backups.append(backup)
        return backups

    def _list_s3_objects(self) -> Generator[dict, None, None]:
        """List the backups stored in S3 in the current s3 configuration.

        A paginator is used over `list_objects_v2` because there can
        be more than 1000 elements.

        Yield:
            Element from list_objects_v2.

        Raises:
            S3Error: if listing the objects in S3 fails.
        """
        paginator = self._client.get_paginator("list_objects_v2")
        page_iterator = paginator.paginate(Bucket=self._s3_parameters.bucket, Prefix=self._prefix)
        try:
            for page in page_iterator:
                if page["KeyCount"] > 0:
                    yield from page["Contents"]
        except ClientError as exc:
            raise S3Error("Error iterating over objects in bucket") from exc


def create_backup(
    container: ops.Container,
    s3_parameters: S3Parameters,
    passphrase: str,
) -> str:
    """Create a backup for Synapse running it in the workload.

    Args:
        container: Synapse Container
        s3_parameters: S3 parameters for the backup.
        passphrase: Passphrase use to encrypt the backup.

    Returns:
       The backup key used for the backup.

    Raises:
       BackupError: If there was an error creating the backup.
    """
    backup_id = "backup-" + datetime.datetime.now().strftime(BACKUP_ID_FORMAT)

    _prepare_container(container, s3_parameters, passphrase)
    paths_to_backup = _get_paths_to_backup(container)
    logger.info("Paths to back up: %s.", list(paths_to_backup))
    if not paths_to_backup:
        raise BackupError("Backup Failed. No paths to back up.")

    expected_size = _calculate_size(container, paths_to_backup)
    backup_command = _build_backup_command(
        s3_parameters, backup_id, paths_to_backup, PASSPHRASE_FILE, expected_size
    )

    logger.info("Backup command: %s", backup_command)
    environment = _get_environment(s3_parameters)
    try:
        exec_process = container.exec(
            backup_command,
            environment=environment,
            user=synapse.SYNAPSE_USER,
            group=synapse.SYNAPSE_GROUP,
        )
        stdout, stderr = exec_process.wait_output()
    except (APIError, ExecError) as exc:
        raise BackupError("Backup Command Failed.") from exc

    logger.info("Backup command output: %s. %s.", stdout, stderr)
    return backup_id


def restore_backup(
    container: ops.Container,
    s3_parameters: S3Parameters,
    passphrase: str,
    backup_id: str,
) -> None:
    """Restore a backup for Synapse overwriting the current data.

    Args:
        container: Synapse Container
        s3_parameters: S3 parameters for the backup.
        passphrase: Passphrase use to decrypt the backup.
        backup_id: Name of the object in the backup.

    Raises:
       BackupError: If there was an error restoring the backup.
    """
    _prepare_container(container, s3_parameters, passphrase)
    container.stop(synapse.SYNAPSE_SERVICE_NAME)

    # Delete the media directory.
    # Other files to back up will be just overwritten.
    media_dir = synapse.get_media_store_path(container)
    container.remove_path(media_dir, recursive=True)

    restore_command = _build_restore_command(s3_parameters, backup_id, PASSPHRASE_FILE)
    logger.info("Restore command: %s", restore_command)
    environment = _get_environment(s3_parameters)
    try:
        exec_process = container.exec(
            restore_command,
            environment=environment,
            user=synapse.SYNAPSE_USER,
            group=synapse.SYNAPSE_GROUP,
        )
        stdout, stderr = exec_process.wait_output()
    except (APIError, ExecError) as exc:
        raise BackupError("Backup restore failed.") from exc
    logger.info("Backup command output: %s. %s.", stdout, stderr)

    container.start(synapse.SYNAPSE_SERVICE_NAME)


def _prepare_container(
    container: ops.Container, s3_parameters: S3Parameters, passphrase: str
) -> None:
    """Prepare container for create or restore backup.

    This means configuring the aws client and the gpg passphrase file.

    Args:
        container: Synapse Container.
        s3_parameters: S3 parameters for the backup.
        passphrase: Passphrase for the backup (used for gpg).

    Raises:
       BackupError: if there was an error preparing the configuration.
    """
    aws_set_addressing_style = [
        AWS_COMMAND,
        "configure",
        "set",
        "default.s3.addressing_style",
        s3_parameters.addressing_style,
    ]

    aws_set_concurrent_requests = [
        AWS_COMMAND,
        "configure",
        "set",
        "default.s3.max_concurrent_requests",
        str(S3_MAX_CONCURRENT_REQUESTS),
    ]

    try:
        process = container.exec(
            aws_set_addressing_style,
            user=synapse.SYNAPSE_USER,
            group=synapse.SYNAPSE_GROUP,
        )
        process.wait()
        process = container.exec(
            aws_set_concurrent_requests,
            user=synapse.SYNAPSE_USER,
            group=synapse.SYNAPSE_GROUP,
        )
        process.wait()
    except (APIError, ExecError) as exc:
        raise BackupError("Backup Failed. Error configuring AWS.") from exc

    try:
        container.push(
            PASSPHRASE_FILE,
            passphrase,
            user=synapse.SYNAPSE_USER,
            group=synapse.SYNAPSE_GROUP,
        )
    except ops.pebble.PathError as exc:
        raise BackupError("Backup Failed. Error configuring GPG passphrase.") from exc


def _build_restore_command(
    s3_parameters: S3Parameters,
    backup_id: str,
    passphrase_file: str,
) -> list[str]:
    """Build the command to execute the backup restore.

    Args:
        s3_parameters: S3 parameters.
        backup_id: The name of the object to back up.
        passphrase_file: Passphrase to use to encrypt the backup file.

    Returns:
        The restore command to execute.
    """
    bash_strict_command = "set -euxo pipefail; "
    s3_url = _s3_path(
        prefix=s3_parameters.path, object_name=backup_id, bucket=s3_parameters.bucket
    )
    aws_command = f"{AWS_COMMAND} s3 cp '{s3_url}' -"
    gpg_command = f"gpg --batch --no-symkey-cache --decrypt --passphrase-file '{passphrase_file}'"
    # restoring with "-C /" is something to review.
    tar_command = "tar -x -C /"
    full_command = bash_strict_command + " | ".join((aws_command, gpg_command, tar_command))
    return [BASH_COMMAND, "-c", full_command]


def _get_paths_to_backup(container: ops.Container) -> Iterable[str]:
    """Get the list of paths that should be in a backup for Synapse.

    Args:
       container: Synapse Container.

    Returns:
       Iterable with the list of paths to backup.
    """
    paths = []
    for pattern in BACKUP_FILE_PATTERNS:
        paths += container.list_files(synapse.SYNAPSE_CONFIG_DIR, pattern=pattern)
    # Local media if it exists
    media_dir = synapse.get_media_store_path(container)
    paths += container.list_files(media_dir, pattern=MEDIA_LOCAL_DIR_PATTERN)
    return [path.path for path in paths]


def _calculate_size(container: ops.Container, paths: Iterable[str]) -> int:
    """Return the combined size of all the paths given.

    Args:
        container: Container where to check the size of the paths.
        paths: Paths to check.

    Returns:
        Total size in bytes.

    Raises:
        BackupError: If there was a problem calculating the size.
    """
    command = "set -euxo pipefail; du -bsc " + _paths_to_args(paths) + " | tail -n1 | cut -f 1"
    try:
        exec_process = container.exec(
            [BASH_COMMAND, "-c", command],
            user=synapse.SYNAPSE_USER,
            group=synapse.SYNAPSE_GROUP,
        )
        stdout, stderr = exec_process.wait_output()
    except (APIError, ExecError) as exc:
        raise BackupError("Cannot calculate size of paths. du failed.") from exc

    logger.info(
        "Calculating size of paths. Command: %s. stdout: %s. stderr: %s", command, stdout, stderr
    )

    return int(stdout)


def _build_backup_command(
    s3_parameters: S3Parameters,
    backup_id: str,
    backup_paths: Iterable[str],
    passphrase_file: str,
    expected_size: int,
) -> list[str]:
    """Build the command to execute the backup.

    Args:
        s3_parameters: S3 parameters.
        backup_id: The name of the object to back up.
        backup_paths: List of paths to back up.
        passphrase_file: Passphrase to use to encrypt the backup file.
        expected_size: expected size of the backup, so AWS S3 Client can calculate
            a reasonable size for the upload parts.

    Returns:
        The backup command to execute.
    """
    bash_strict_command = "set -euxo pipefail; "
    paths = _paths_to_args(backup_paths)
    tar_command = f"tar -c {paths}"
    gpg_command = (
        f"gpg --batch --no-symkey-cache " f"--passphrase-file '{passphrase_file}' " f"--symmetric"
    )

    s3_url = _s3_path(
        prefix=s3_parameters.path, object_name=backup_id, bucket=s3_parameters.bucket
    )
    aws_command = f"{AWS_COMMAND} s3 cp --expected-size={expected_size} - '{s3_url}'"
    full_command = bash_strict_command + " | ".join((tar_command, gpg_command, aws_command))
    return [BASH_COMMAND, "-c", full_command]


def _get_environment(s3_parameters: S3Parameters) -> Dict[str, str]:
    """Get the environment variables for backup that configure aws S3 cli.

    Args:
        s3_parameters: S3 parameters.

    Returns:
        A dictionary with aws s3 configuration variables.
    """
    environment = {
        "AWS_ACCESS_KEY_ID": s3_parameters.access_key,
        "AWS_SECRET_ACCESS_KEY": s3_parameters.secret_key,
    }
    if s3_parameters.endpoint:
        environment["AWS_ENDPOINT_URL"] = s3_parameters.endpoint
    if s3_parameters.region:
        environment["AWS_DEFAULT_REGION"] = s3_parameters.region
    return environment


def _s3_path(prefix: str, object_name: Optional[str] = None, bucket: Optional[str] = None) -> str:
    """Create a S3 paths compatible with S3 and Minio for backup purposes.

    Args:
        prefix: prefix for the path.
        object_name: final part of the name of the object.
        bucket: name of the bucket.

    Returns:
       a S3 path, only including the protocol if the bucket is included.
    """
    # Removing the root slash in path makes this code compatible with
    # MinIO. MinIO looks like it does not have a slash as the first element,
    # and if the file was uploaded with one, it gets removed.
    path = prefix.strip("/")
    if object_name:
        # Use pathlib to remove possible extra slashes in paths, as MinIO may work
        # incorrectly. See https://github.com/minio/minio/issues/5958
        path = str(pathlib.Path(f"{path}/{object_name}"))
    if bucket:
        path = f"s3://{bucket}/{path}"
    return path


def _paths_to_args(paths: Iterable[str]) -> str:
    """Given a list of paths, quote and concatenate them for use as cli arguments.

    Args:
        paths: List of paths

    Returns:
        paths concatenated and quoted
    """
    return " ".join(f"'{path}'" for path in paths)
