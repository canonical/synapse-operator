# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse backup unit tests."""

# pylint: disable=protected-access
from secrets import token_hex

import ops
import pytest

# from s3_parameters import S3Parameters
from ops.testing import Harness


def test_enable_media(s3_relation_data_media, harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """Test enabling media with valid S3 configuration."""
    s3_relation_data_media["access-key"] = token_hex(16)
    s3_relation_data_media["secret-key"] = token_hex(16)
    s3_relation_data_media["bucket"] = "test-bucket"
    s3_relation_data_media["region"] = "us-east-1"
    s3_relation_data_media["endpoint"] = "https://s3.us-east-1.amazonaws.com"
    s3_relation_data_media["path"] = "test-path"
    s3_relation_data_media["s3-uri-style"] = "host"
    s3_relation_data_media["addressing-style"] = "virtual"

    monkeypatch.setattr("media_observer.S3_INVALID_CONFIGURATION", "Invalid S3 configuration")

    harness.update_relation_data(0, "media", s3_relation_data_media)

    harness.begin_with_initial_hooks()

    assert harness.charm.unit.status == ops.ActiveStatus()
    assert harness.charm.unit.status.message == "Invalid S3 configuration"

    harness.update_relation_data(0, "media", {})

    harness.begin_with_initial_hooks()

    assert harness.charm.unit.status == ops.BlockedStatus("S3 configuration is invalid")
    assert (
        harness.charm.unit.status.message
        == "Media: S3 bucket does not exist or cannot be accessed"
    )
