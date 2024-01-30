# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provides backup functionality for Synapse."""

import logging
import os
from typing import Any, Dict, Iterable, List, Optional

import boto3
import ops
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from botocore.exceptions import ConnectionError as BotoConnectionError
from ops.pebble import ExecError
from pydantic import BaseModel, Field, validator

import synapse

# It looks stage-snaps is broken, as it
# does put /usb/bin/aws but it points to ../aws/dist/aws
# which does not exists. Check again and
# open issue if appropriate
AWS_COMMAND = "/aws/dist/aws"
BACKUP_FILE_PATTERNS = ["*.key", "homeserver.db*"]
LOCAL_DIR_PATTERN = "local_*"
S3_MAX_CONCURRENT_REQUESTS = 1
MEDIA_DIR = "media"
PASSPHRASE_FILE = "/root/.gpg_passphrase"  # nosec
BASH_COMMAND = "bash"

logger = logging.getLogger(__name__)


class BackupError(Exception):
    """Generic backup Exception."""


class S3Error(Exception):
    """Generic S3 Exception."""


class S3Parameters(BaseModel):
    """Configuration for accessing S3 bucket.

    Attributes:
        access_key: AWS access key.
        secret_key: AWS secret key.
        region: The region to connect to the object storage.
        bucket: The bucket name.
        endpoint: The endpoint used to connect to the object storage.
        path: The path inside the bucket to store objects.
        s3_uri_style: The S3 protocol specific bucket path lookup type. Can be "path" or "host".
        addressing_style: S3 protocol addressing style, can be "path" or "virtual".
    """

    access_key: str = Field(alias="access-key")
    secret_key: str = Field(alias="secret-key")
    region: Optional[str]
    bucket: str
    endpoint: Optional[str]
    path: str = Field(default="")
    s3_uri_style: str = Field(alias="s3-uri-style", default="host")

    @validator("endpoint", always=True)
    @classmethod
    def check_endpoint_or_region_set(cls, endpoint: str, values: dict[str, Any]) -> str:
        """Validate that either region or endpoint is set.

        Args:
            endpoint: endpoint attribute
            values: all attributes in S3 configuration

        Returns:
            value of the endpoint attribute

        Raises:
            ValueError: if the configuration is invalid.
        """
        region = values.get("region")
        if not region and not endpoint:
            raise ValueError('one of "region" or "endpoint" needs to be set')
        return endpoint

    @property
    def addressing_style(self) -> str:
        """Translates s3_uri_style to AWS addressing_style."""
        if self.s3_uri_style == "path":
            return "path"
        return "virtual"


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
            logger.exception("Error creating S3 client")
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


def get_paths_to_backup(container: ops.Container) -> Iterable[str]:
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
    media_dir = os.path.join(synapse.SYNAPSE_DATA_DIR, MEDIA_DIR)
    if container.exists(media_dir):
        paths += container.list_files(media_dir, pattern=LOCAL_DIR_PATTERN)
    return [path.path for path in paths]


def build_backup_command(
    s3_parameters: S3Parameters,
    backup_key: str,
    backup_paths: Iterable[str],
    passphrase_file: str,
    expected_size: int = int(1e10),
) -> List[str]:
    """Build the command to execute the backup.

    Args:
        s3_parameters: S3 parameters.
        backup_key: The name of the object to back up.
        backup_paths: List of paths to back up.
        passphrase_file: Passphrase to use to encrypt the backup file.
        expected_size: expected size of the backup, so AWS S3 Client can calculate
            a reasonable size for the upload parts.

    Returns:
        The backup command to execute.
    """
    bash_strict_command = "set -euxo pipefail; "
    paths = " ".join(backup_paths)
    tar_command = f"tar -c {paths}"
    gpg_command = f"gpg --batch --no-symkey-cache --passphrase-file {passphrase_file} --symmetric"
    aws_command = f"{AWS_COMMAND} s3 cp --expected-size={expected_size} - "
    aws_command += f"'s3://{s3_parameters.bucket}/{s3_parameters.path}/{backup_key}'"
    full_command = bash_strict_command + " | ".join((tar_command, gpg_command, aws_command))
    # sh does not accept "set -o pipefail". Better use bash.
    return [BASH_COMMAND, "-c", full_command]


def calculate_size(container: ops.Container, paths: Iterable[str]) -> int:
    """Return the combined size of all the paths given.

    Args:
        container: Container where to check the size of the paths.
        paths: Paths to check.

    Returns:
        Total size in bytes.
    """
    command = "set -euxo pipefail; du -bsc " + " ".join(paths) + " | tail -n1 | cut -f 1"
    exec_process = container.exec([BASH_COMMAND, "-c", command])
    stdout, stderr = exec_process.wait_output()
    logger.info(
        "Calculating size of paths. Command: %s. stdout: %s. stderr: %s", command, stdout, stderr
    )
    return int(stdout)


def prepare_container(
    container: ops.Container, s3_parameters: S3Parameters, passphrase: str
) -> None:
    """Prepare container for create or restore backup.

    This means preparing the required aws configuration and gpg passphrase file.

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

    # To minimise memory comsupmtion. A bigger value could increase speed.
    aws_set_concurrent_requests = [
        AWS_COMMAND,
        "configure",
        "set",
        "default.s3.max_concurrent_requests",
        str(S3_MAX_CONCURRENT_REQUESTS),
    ]

    try:
        process = container.exec(aws_set_addressing_style)
        process.wait()
        process = container.exec(aws_set_concurrent_requests)
        process.wait()
    except ExecError as exc:
        logger.exception(exc)
        raise BackupError("Backup Failed. Error configuring AWS.") from exc

    container.push(PASSPHRASE_FILE, passphrase)


def create_backup(
    container: ops.Container,
    s3_parameters: S3Parameters,
    backup_key: str,
    passphrase: str,
) -> None:
    """Create a backup for Synapse running it in the workload.

    Args:
        container: Synapse Container
        s3_parameters: S3 parameters for the backup.
        backup_key: Name of the object in the backup.
        passphrase: Passphrase use to encrypt the backup.

    Raises:
       BackupError: If there was an error creating the backup.
    """
    prepare_container(container, s3_parameters, passphrase)
    paths_to_backup = get_paths_to_backup(container)
    logger.info("paths to backup: %s", list(paths_to_backup))
    if not paths_to_backup:
        raise BackupError("Backup Failed. No files to back up")

    expected_size = calculate_size(container, paths_to_backup)
    backup_command = build_backup_command(
        s3_parameters, backup_key, paths_to_backup, PASSPHRASE_FILE, expected_size
    )

    logger.info("backup command: %s", backup_command)
    environment = get_environment(s3_parameters)
    try:
        exec_process = container.exec(backup_command, environment=environment)
        stdout, stderr = exec_process.wait_output()
    except ExecError as exc:
        logger.exception(exc)
        raise BackupError("Backup Command Failed") from exc

    logger.info("Backup command output: %s. %s.", stdout, stderr)


def get_environment(s3_parameters: S3Parameters) -> Dict[str, str]:
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
