# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse backup unit tests."""

from secrets import token_hex
from unittest.mock import MagicMock

import boto3
import ops
import pytest
from botocore.exceptions import BotoCoreError, ClientError
from ops.testing import Harness

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


def test_on_s3_credentials_changed_correct(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: start the Synapse charm.
    act: Add integration with s3-integrator with correct data.
    assert: The unit should be in active status.
    """
    monkeypatch.setattr(backup, "can_use_bucket", MagicMock(return_value=True))
    s3_relation_data = {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
        "region": "eu-west-1",
        "bucket": "synapse-backup-bucket",
        "endpoint": "https://example.com",
        "path": "/synapse-backups",
        "s3-uri-style": "path",
    }
    harness.begin_with_initial_hooks()

    harness.add_relation("s3-backup", "s3-integrator", app_data=s3_relation_data)

    assert harness.model.unit.status == ops.ActiveStatus()


def test_on_s3_credentials_changed_wrong_s3_parameters(harness: Harness):
    """
    arrange: start the Synapse charm.
    act: Add integration with s3-integrator with missing fields.
    assert: The unit should be blocked because of S3 invalid configuration.
    """
    s3_relation_data = {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
    }
    harness.begin_with_initial_hooks()

    harness.add_relation("s3-backup", "s3-integrator", app_data=s3_relation_data)

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "S3 configuration is invalid" in str(harness.model.unit.status)


def test_on_s3_credentials_changed_cannot_access_bucket(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: start the Synapse charm. Mock function can_use_bucket as if bucket does not exist.
    act: Add integration with s3-integrator.
    assert: The unit should be blocked because of bucket does not exist.
    """
    monkeypatch.setattr(backup, "can_use_bucket", MagicMock(return_value=False))
    s3_relation_data = {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
        "region": "eu-west-1",
        "bucket": "synapse-backup-bucket",
        "endpoint": "https://example.com",
        "path": "/synapse-backups",
        "s3-uri-style": "path",
    }
    harness.begin_with_initial_hooks()

    harness.add_relation("s3-backup", "s3-integrator", app_data=s3_relation_data)

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "bucket does not exist" in str(harness.model.unit.status)


def test_on_s3_credentials_gone_set_active(harness: Harness):
    """
    arrange: start the Synapse charm. Integrate with s3-integrator with missing data,
       so the charm is in blocked status.
    act: Remove the s3-integratior integration
    assert: The unit should be active.
    """
    s3_relation_data = {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
    }
    relation_id = harness.add_relation("s3-backup", "s3-integrator", app_data=s3_relation_data)
    harness.begin_with_initial_hooks()

    harness.remove_relation(relation_id)

    assert harness.model.unit.status == ops.ActiveStatus()


def test_can_use_bucket_correct(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Create S3Parameters and mock boto3 library so it does not fail.
    act: Run can_use_bucket.
    assert: Check that the function returns True.
    """
    s3_parameters = backup.S3Parameters(
        **{
            "access-key": token_hex(16),
            "secret-key": token_hex(16),
            "region": "eu-west-1",
            "bucket": "bucket_name",
        }
    )
    monkeypatch.setattr(boto3.session, "Session", MagicMock())

    assert backup.can_use_bucket(s3_parameters) is True


def test_can_use_bucket_wrong_boto3_resource(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Create S3Parameters and mock boto3 library so raises on accessing S3 resource.
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

    assert backup.can_use_bucket(s3_parameters) is False


def test_can_use_bucket_bucket_error_checking_bucket(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Create S3Parameters and mock boto3 library so fails when checking the bucket.
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

    assert backup.can_use_bucket(s3_parameters) is False
