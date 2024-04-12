# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse backup unit tests."""

# pylint: disable=protected-access

import datetime
import os
import pathlib
from secrets import token_hex
from unittest.mock import MagicMock

import pytest
import yaml
from botocore.exceptions import ClientError
from dateutil.tz import tzutc  # type: ignore
from ops.testing import Harness

from s3_parameters import S3Parameters
import synapse


def test_s3_relation_validation_fails_when_region_and_endpoint_not_set():
    """
    arrange: Create s3 relation data without region nor endpoint.
    act: Create S3Parameters pydantic BaseModel from relation data.
    assert: Raises ValueError as one of those two fields should be set.
    """
    s3_relation_data = {
        "access-key": token_hex(16),
        "secret-key": token_hex(16),
        "bucket": "backup-bucket",
        "path": "/synapse-backups",
        "s3-uri-style": "path",
    }

    with pytest.raises(ValueError):
        S3Parameters(**s3_relation_data)
