# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse media unit tests."""

# pylint: disable=protected-access

from secrets import token_hex
from unittest.mock import Mock

import ops
import pytest
from ops.testing import Harness

from charm_state import CharmState, SynapseConfig
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
                "access-key": "access_key",
                "secret-key": secret_key,
                "region": "eu-west-1",
                "bucket": "synapse-media-bucket",
                "endpoint": "https:/example.com",
                "path": "/synapse-media",
                "s3-uri-style": "path",
            },
            MediaConfiguration(
                access_key_id="access_key",
                secret_access_key=secret_key,
                bucket="synapse-media-bucket",
                region_name="eu-west-1",
                endpoint_url="https:/example.com",
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

    assert (harness.charm._media.get_relation_as_media_conf() is None) == (not valid)


@pytest.mark.parametrize(
    "relation_data, expected_status, can_connect",
    [
        pytest.param(
            {
                "bucket": "bucket1",
                "region": "region1",
                "endpoint": "endpoint1",
                "access-key": "access_key1",
                "secret-key": token_hex(16),
            },
            ops.ActiveStatus(),
            True,
            id="correct media configuration",
        ),
        pytest.param(
            {
                "bucket": "bucket1",
                "access-key": "access_key1",
                "secret-key": token_hex(16),
            },
            ops.BlockedStatus(
                "Media integration failed: Media Configuration not found. "
                "Please verify the integration between Media and Synapse."
            ),
            False,
            id="correct media configuration",
        ),
    ],
)
def test_enable_media(harness: Harness, relation_data, expected_status, can_connect):
    """
    arrange: Mock the container's can_connect method to return the can_connect parameter.
    act: Call the _enable_media method.
    assert: Check if the unit's status is set to the expected_status.
    """
    harness.add_relation("media", "s3-integrator", app_data=relation_data)
    harness.begin_with_initial_hooks()

    container = Mock()
    container.can_connect.return_value = can_connect

    charm_state = CharmState(
        synapse_config=SynapseConfig(
            server_name="example.com",
            public_baseurl="https://example.com",
            irc_bridge_admins=None,
            federation_domain_whitelist=None,
            ip_range_whitelist=None,
            report_stats=None,
            notif_from=None,
            trusted_key_servers=None,
        ),
        datasource=None,
        irc_bridge_datasource=None,
        saml_config=None,
        smtp_config=None,
        media_config=harness.charm._media.get_relation_as_media_conf(),
        redis_config=None,
    )
    harness.charm._media._enable_media(charm_state)
    assert harness.charm.unit.status == expected_status
