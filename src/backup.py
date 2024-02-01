# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provides backup functionality for Synapse."""

import logging
from typing import Any, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from botocore.exceptions import ConnectionError as BotoConnectionError
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


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
