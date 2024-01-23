# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provides backup functionality for Synapse."""

import logging
from typing import Any, Optional

from boto3 import client
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from botocore.exceptions import ConnectionError as BotoConnectionError
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)


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


def can_use_bucket(s3_parameters: S3Parameters) -> bool:
    """Check if a bucket exists and is accessible in an S3 compatible object store.

    Args:
        s3_parameters: S3 connection parameters

    Returns:
       True if the bucket exists and is accessible
    """
    try:
        s3_client_config = Config(
            region_name=s3_parameters.region,
            s3={
                "addressing_style": s3_parameters.addressing_style,
            },
        )
        s3_client = client(
            "s3",
            s3_parameters.region,
            aws_access_key_id=s3_parameters.access_key,
            aws_secret_access_key=s3_parameters.secret_key,
            endpoint_url=s3_parameters.endpoint,
            config=s3_client_config,
        )
    except (TypeError, BotoCoreError):
        logger.exception("Failed to create S3 client")
        return False

    try:
        s3_client.head_bucket(Bucket=s3_parameters.bucket)
    except (ClientError, BotoConnectionError):
        logger.exception(
            "Bucket %s doesn't exist or you don't have access to it.", s3_parameters.bucket
        )
        return False
    return True
