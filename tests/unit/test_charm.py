# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm unit tests."""

from ops.testing import Harness

from charm import SYNAPSE_CONTAINER_NAME, SynapseCharm


def test_get_charm_configuration():
    """
    arrange: set configuration and set container to be ready to connect.
    act: start the charm.
    assert: charm status is active and server_name is set as expected.
    """
    harness = Harness(SynapseCharm)
    expected_server_name = "foo"
    harness.update_config({"server_name": expected_server_name})
    harness.set_can_connect(SYNAPSE_CONTAINER_NAME, True)

    harness.begin()

    assert harness.charm.get_charm_configuration().server_name == expected_server_name
