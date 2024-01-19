# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse backup unit tests."""

from secrets import token_hex
from unittest.mock import MagicMock

import boto3
import pytest
from botocore.exceptions import BotoCoreError, ClientError

import backup


def test_s3_relation_validation_fails_when_region_and_endpoint_not_set():
    """
    arrange: Create s3 relation data without region nor endpoint.
    act: Create S3Parameters pydantic BaseModel from relation data.
    assert: Raises ValueError as one of those two fields should be set.
    """
    s3_relation_data = {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
        "bucket": "synapse-backup-bucket",
        "path": "/synapse-backups",
        "s3-uri-style": "path",
    }

    with pytest.raises(ValueError):
        backup.S3Parameters(**s3_relation_data)


def test_can_use_bucket_wrong_boto3_resource(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Create S3Parameters and mock boto3 library so it raises on accessing S3 resource.
    act: Run can_use_bucket.
    assert: Check that the function returns False.
    """
    s3_parameters = backup.S3Parameters(
        **{
            "access-key": token_hex(16),
            "secret-key": token_hex(16),
            "region": "eu-west-1",
            "bucket": "bucket_name",
        }
    )
    session = MagicMock()
    session.resource = MagicMock(side_effect=BotoCoreError())
    monkeypatch.setattr(boto3.session, "Session", MagicMock(return_value=session))

    assert not backup.can_use_bucket(s3_parameters)


def test_can_use_bucket_bucket_error_checking_bucket(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Create S3Parameters and mock boto3 library so it fails when checking the bucket.
    act: Run can_use_bucket.
    assert: Check that the function returns False.
    """
    s3_parameters = backup.S3Parameters(
        **{
            "access-key": token_hex(16),
            "secret-key": token_hex(16),
            "region": "eu-west-1",
            "bucket": "bucket_name",
        }
    )
    session = MagicMock()
    session.resource().Bucket().meta.client.head_bucket.side_effect = ClientError({}, "HeadBucket")
    monkeypatch.setattr(boto3.session, "Session", MagicMock(return_value=session))

    assert not backup.can_use_bucket(s3_parameters)
