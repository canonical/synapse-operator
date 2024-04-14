# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse media unit tests."""

# pylint: disable=protected-access

from secrets import token_hex
from unittest.mock import Mock

import ops
import pytest
from charm_state import CharmConfigInvalidError, CharmState
from ops.testing import Harness

from charm_types import MediaConfiguration


def _test_get_relation_data_to_media_conf_parameters():
    """Generate parameters for the test_get_relation_as_media_conf.

    Returns:
        The tests.
    """
    secret_key = token_hex(16)
    return [
        pytest.param(
            {
                "bucket": "bucket1",
                "region": "region1",
                "endpoint": "endpoint1",
                "access_key": "access_key1",
                "secret_key": secret_key,
            },
            MediaConfiguration(
                bucket="bucket1",
                region_name="region1",
                endpoint_url="endpoint1",
                access_key_id="access_key1",
                secret_access_key=secret_key,
            ),
            id="media config test",
        )
    ]


@pytest.mark.parametrize(
    "relation_data, expected_config", _test_get_relation_data_to_media_conf_parameters()
)
def test_get_relation_as_media_conf(harness: Harness, relation_data, expected_config):
    """
    arrange: add relation_data from parameter.
    act: get MediaConfiguration from media observer.
    assert: expected media configuration matches returned one.
    """
    harness.add_relation("media", "s3-integrator", app_data=relation_data)
    harness.begin()

    media_configuration = harness.charm._media.get_relation_as_media_conf()

    assert media_configuration == expected_config


@pytest.mark.parametrize(
    "relation_data",
    [
        pytest.param(
            {
                "bucket": "bucket1",
                "access_key": "access_key1",
                "secret_key": token_hex(16),
            },
            id="region and endpoint are None",
        ),
    ],
)
def test_get_relation_fails_invalid_config(harness: Harness, relation_data):
    """
    arrange: add not supported invalid relation_data from parameter.
    act: get MediaConfiguration from media observer.
    assert: raises exception CharmConfigInvalidError
    """
    harness.add_relation("media", "s3-integrator", app_data=relation_data)
    harness.begin()

    with pytest.raises(CharmConfigInvalidError):
        harness.charm._media.get_relation_as_media_conf()


@pytest.mark.parametrize(
    "can_connect, expected_status",
    [
        pytest.param(True, ops.ActiveStatus(), id="Container can connect"),
        pytest.param(False, ops.MaintenanceStatus("Waiting for Synapse pebble"), id="Container cannot connect"),
    ],
)
def test_enable_media(harness: Harness, can_connect, expected_status):
    """
    arrange: Mock the container's can_connect method to return the can_connect parameter.
    act: Call the _enable_media method.
    assert: Check if the unit's status is set to the expected_status.
    """
    charm_state = CharmState()

    container = Mock()
    container.can_connect.return_value = can_connect

    harness.charm.unit.get_container.return_value = container

    harness.begin()
    harness.charm._media._enable_media(charm_state)

    assert harness.charm.unit.status == expected_status
