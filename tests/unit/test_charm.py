# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm unit tests."""

from secrets import token_hex

import ops
from ops.testing import Harness

from constants import SYNAPSE_CONTAINER_NAME, SYNAPSE_SERVICE_NAME
from synapse import COMMAND_PATH


def test_synapse_pebble_layer(harness: Harness) -> None:
    """
    arrange: none
    act: start the Synapse charm, set Synapse container to be ready and set server_name.
    assert: Synapse charm should submit the correct Synapse pebble layer to pebble.
    """
    harness.disable_hooks()
    server_name = token_hex(16)
    harness.update_config({"server_name": server_name})
    harness.enable_hooks()
    harness.begin_with_initial_hooks()
    harness.set_can_connect(harness.model.unit.containers[SYNAPSE_CONTAINER_NAME], True)
    harness.framework.reemit()
    synapse_layer = harness.get_container_pebble_plan(SYNAPSE_CONTAINER_NAME).to_dict()[
        "services"
    ][SYNAPSE_SERVICE_NAME]
    assert synapse_layer == {
        "override": "replace",
        "summary": "Synapse application service",
        "command": COMMAND_PATH,
        "environment": {
            "SYNAPSE_NO_TLS": "True",
            "SYNAPSE_REPORT_STATS": "no",
            "SYNAPSE_SERVER_NAME": server_name,
        },
        "startup": "enabled",
    }


def test_container_down(harness: Harness) -> None:
    """
    arrange: none
    act: start the Synapse charm, set server_name, set Synapse container to be down
        and then try to change report_stats.
    assert: Synapse charm should submit the correct status.
    """
    harness.disable_hooks()
    server_name = token_hex(16)
    harness.update_config({"server_name": server_name})
    harness.enable_hooks()
    harness.begin_with_initial_hooks()
    harness.set_can_connect(harness.model.unit.containers[SYNAPSE_CONTAINER_NAME], True)
    harness.framework.reemit()
    harness.set_can_connect(harness.model.unit.containers[SYNAPSE_CONTAINER_NAME], False)
    harness.update_config({"report_stats": True})
    assert isinstance(harness.model.unit.status, ops.WaitingStatus)
    assert "Waiting for" in str(harness.model.unit.status)


def test_server_name_empty(harness: Harness) -> None:
    """
    arrange: none
    act: start the Synapse charm and set Synapse container to be ready.
    assert: Synapse charm waits for server_name to be set.
    """
    harness.begin()
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "invalid configuration: server_name" in str(harness.model.unit.status)
