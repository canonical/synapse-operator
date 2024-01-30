# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse backup observer unit tests."""

from secrets import token_hex
from typing import Type
from unittest.mock import MagicMock

import ops
import pytest
from ops.testing import Harness

import backup


@pytest.mark.parametrize(
    "relation_data, can_use_bucket, expected_status_cls, expected_str_in_status",
    [
        pytest.param(
            {
                "access-key": token_hex(16),
                "secret-key": token_hex(16),
                "region": "eu-west-1",
                "bucket": "synapse-backup-bucket",
                "endpoint": "https:/example.com",
                "path": "/synapse-backups",
                "s3-uri-style": "path",
            },
            True,
            ops.BlockedStatus,
            "configuration is invalid",
            id="Correct S3 configuration",
        ),
        pytest.param(
            {
                "access-key": token_hex(16),
                "secret-key": token_hex(16),
                "region": "eu-west-1",
                "bucket": "synapse-backup-bucket",
                "endpoint": "https://example.com",
                "path": "/synapse-backups",
                "s3-uri-style": "path",
            },
            True,
            ops.ActiveStatus,
            "",
            id="Invalid S3 endoint",
        ),        
        pytest.param(
            {
                "access-key": token_hex(16),
                "secret-key": token_hex(16),
            },
            True,
            ops.BlockedStatus,
            "S3 configuration is invalid",
            id="Invalid S3 configuration",
        ),
        pytest.param(
            {
                "access-key": token_hex(16),
                "secret-key": token_hex(16),
                "region": "eu-west-1",
                "bucket": "synapse-backup-bucket",
                "s3-uri-style": "path",
            },
            False,
            ops.BlockedStatus,
            "bucket does not exist",
            id="Bucket does not exist or not accessible",
        ),
    ],
)
def test_on_s3_credentials_changed(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    relation_data: dict,
    can_use_bucket: bool,
    expected_status_cls: Type,
    expected_str_in_status: str,
):
    """
    arrange: start the Synapse charm. Mock function can_use_bucket as the pytest param.
    act: Add integration with s3-integrator.
    assert: The unit should be in the expected state with the expected message.
    """
    # pylint: disable=too-many-arguments
    monkeypatch.setattr(backup.S3Client, "can_use_bucket", MagicMock(return_value=can_use_bucket))
    harness.begin_with_initial_hooks()

    harness.add_relation("backup", "s3-integrator", app_data=relation_data)

    assert isinstance(harness.model.unit.status, expected_status_cls)
    assert expected_str_in_status in str(harness.model.unit.status)


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
    relation_id = harness.add_relation("backup", "s3-integrator", app_data=s3_relation_data)
    harness.begin_with_initial_hooks()

    harness.remove_relation(relation_id)

    assert harness.model.unit.status == ops.ActiveStatus()
