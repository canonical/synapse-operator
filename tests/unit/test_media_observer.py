# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse media unit tests."""

# pylint: disable=protected-access

from secrets import token_hex
from unittest.mock import Mock

import ops
import pytest
from ops.testing import Harness

import synapse
from charm_types import MediaConfiguration

from .conftest import TEST_SERVER_NAME


def _test_get_relation_data_to_media_conf_parameters():
    """Generate parameters for the test_get_relation_as_media_conf.

    Returns:
        The tests.
    """
    secret_key = token_hex(16)
    return [
        pytest.param(
            {
                "access-key": "access_key",
                "secret-key": secret_key,
                "region": "eu-west-1",
                "bucket": "synapse-media-bucket",
                "endpoint": "https:/example.com",
                "path": "media",
                "s3-uri-style": "path",
            },
            MediaConfiguration(
                access_key_id="access_key",
                secret_access_key=secret_key,
                bucket="synapse-media-bucket",
                region_name="eu-west-1",
                endpoint_url="https:/example.com",
                prefix="media",
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
    "relation_data, valid",
    [
        pytest.param(
            {
                "bucket": "bucket1",
                "region": "region1",
                "endpoint": "endpoint1",
                "access-key": "access_key1",
                "secret-key": token_hex(16),
                "path": "media",
            },
            True,
            id="complete media configuration",
        ),
        pytest.param(
            {
                "bucket": "bucket1",
                "access-key": "access_key1",
                "secret-key": token_hex(16),
            },
            False,
            id="incorrect media configuration",
        ),
        pytest.param(
            {
                "bucket": "bucket1",
                "region": "region1",
                "access-key": "access_key1",
                "secret-key": token_hex(16),
            },
            True,
            id="partially-complete media configuration",
        ),
    ],
)
def test_media_configurations(harness: Harness, relation_data, valid):
    """
    arrange: add relation_data from parameter.
    act: get MediaConfiguration from media observer.
    assert: expected media configuration matches returned one.
    """
    harness.add_relation("media", "s3-integrator", app_data=relation_data)
    harness.begin()

    media_conf = harness.charm._media.get_relation_as_media_conf()
    if valid:
        assert media_conf is not None
    else:
        assert media_conf is None


def test_enable_media(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: Mock the container's can_connect method to return the can_connect parameter.
    act: Call the _enable_media method.
    assert: Check if the unit's status is set to the expected_status.
    """
    relation_data = {
        "bucket": "bucket1",
        "region": "region1",
        "endpoint": "endpoint1",
        "access-key": "access_key1",
        "secret-key": token_hex(16),
        "path": "media",
    }
    harness.add_relation("media", "s3-integrator", app_data=relation_data)
    harness.begin_with_initial_hooks()
    enable_media_mock = Mock()
    monkeypatch.setattr(synapse, "enable_media", enable_media_mock)
    container: ops.Container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    container.push(
        synapse.SYNAPSE_CONFIG_PATH, f'server_name: "{TEST_SERVER_NAME}"', make_dirs=True
    )

    relation = harness.charm.framework.model.get_relation("media", 0)
    harness.charm._media._s3_client.on.credentials_changed.emit(relation)

    enable_media_mock.assert_called_once()
