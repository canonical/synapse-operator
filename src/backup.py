# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provides backup functionality for Synapse."""
import logging
from typing import Any, Optional

import boto3
import ops
from botocore.exceptions import BotoCoreError, ClientError
from charms.data_platform_libs.v0.s3 import CredentialsChangedEvent, S3Requirer
from ops.framework import Object
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

S3_CANNOT_ACCESS_BUCKET = "Backup: S3 Bucket does not exist or cannot be accessed"
S3_INVALID_CONFIGURATION = "Backup: S3 configuration is invalid"
BACK_UP_STATUS_MESSAGES = (S3_INVALID_CONFIGURATION, S3_CANNOT_ACCESS_BUCKET)


class S3Parameters(BaseModel):
    """Configuration for accessing S3 bucket.

    Attributes:
        access_key: AWS access key.
        secret_key: AWS secret key.
        region: The region to connect to the object storage.
        bucket: The bucket name.
        endpoint: The endpoint used to connect to the object storage.
        path: The path inside the bucket to store objects.
        s3_uri_style: The S3 protocol specific bucket path lookup type.
    """

    access_key: str = Field(alias="access-key")
    secret_key: str = Field(alias="secret-key")
    region: Optional[str] = Field(default=None)
    bucket: str
    endpoint: Optional[str]
    path: str = Field(default="")
    s3_uri_style: str = Field(alias="s3-uri-style", default="host")

    @validator("region", always=True)
    @classmethod
    def check_region_or_endpoint_set(cls, region: str, values: dict[str, Any]) -> str:
        """Validate that eather that region or endpoint are set.

        Args:
            region: region attribute
            values: all attributes in S3 configuration

        Returns:
            value of the region attribute

        Raises:
            ValueError: if the configuration is invalid.
        """
        endpoint = values.get("endpoint")
        if region is None and endpoint is None:
            raise ValueError('one of "region" or "endpoint" needs to be set')
        return region


class SynapseBackup(Object):
    """Class to manage Synapse backups over S3."""

    _S3_RELATION_NAME = "s3-backup-parameters"

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
            s3_parameters = S3Parameters(**self._s3_client.get_s3_connection_info())
        except ValueError:
            self._charm.unit.status = ops.BlockedStatus(S3_INVALID_CONFIGURATION)
            return

        if not s3_bucket_exists(s3_parameters):
            self._charm.unit.status = ops.BlockedStatus(S3_CANNOT_ACCESS_BUCKET)

    def _on_s3_credential_gone(self, _: CredentialsChangedEvent) -> None:
        """Handle s3 credentials gone to reset unit status if it is now correct."""
        if (
            isinstance(self._charm.unit.status, ops.BlockedStatus)
            and self._charm.unit.status.message in BACK_UP_STATUS_MESSAGES
        ):
            self._charm.unit.status = ops.ActiveStatus()


def s3_bucket_exists(s3_parameters: S3Parameters) -> bool:
    """Check if a bucket exists and is accessible in an S3 compatible object store.

    Args:
        s3_parameters: S3 connection parameters

    Returns:
       True if the bucket exists and is accessible
    """
    session = boto3.session.Session(
        aws_access_key_id=s3_parameters.access_key,
        aws_secret_access_key=s3_parameters.secret_key,
        region_name=s3_parameters.region,
    )
    try:
        s3 = session.resource("s3", endpoint_url=s3_parameters.endpoint)
    except BotoCoreError:
        logger.exception("Failed to create S3 session")
        return False
    bucket = s3.Bucket(s3_parameters.bucket)
    try:
        bucket.meta.client.head_bucket(Bucket=s3_parameters.bucket)
    except ClientError:
        logger.exception(
            "Bucket %s doesn't exist or you don't have access to it.", s3_parameters.bucket
        )
        return False
    return True
