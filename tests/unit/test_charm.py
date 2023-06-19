# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm unit tests."""

import ops
import pytest
from ops.testing import Harness

from constants import SYNAPSE_CONTAINER_NAME, SYNAPSE_SERVICE_NAME
from synapse import COMMAND_PATH


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_synapse_pebble_layer(harness: Harness) -> None:
    """
    arrange: none
    act: start the Synapse charm, set Synapse container to be ready and set server_name.
    assert: Synapse charm should submit the correct Synapse pebble layer to pebble.
    """
    harness.disable_hooks()
    server_name = "pebble-layer.synapse.com"
    harness.update_config({"server_name": server_name})
    harness.enable_hooks()
    harness.begin_with_initial_hooks()
    harness.set_can_connect(harness.model.unit.containers[SYNAPSE_CONTAINER_NAME], True)
    harness.framework.reemit()
    synapse_layer = harness.get_container_pebble_plan(SYNAPSE_CONTAINER_NAME).to_dict()[
        "services"
    ][SYNAPSE_SERVICE_NAME]
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)
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


@pytest.mark.parametrize("harness", [1], indirect=True)
def test_synapse_migrate_config_error(harness: Harness) -> None:
    """
    arrange: none
    act: start the Synapse charm, set Synapse container to be ready and set server_name.
    assert: Synapse charm should be blocked by error on migrate_config command.
    """
    harness.disable_hooks()
    server_name = "migrate-config-error.synapse.com"
    harness.update_config({"server_name": server_name})
    harness.enable_hooks()
    harness.begin_with_initial_hooks()
    harness.set_can_connect(harness.model.unit.containers[SYNAPSE_CONTAINER_NAME], True)
    harness.framework.reemit()
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "Migrate config failed" in str(harness.model.unit.status)


def test_container_down(harness: Harness) -> None:
    """
    arrange: none
    act: start the Synapse charm, set server_name, set Synapse container to be down
        and then try to change report_stats.
    assert: Synapse charm should submit the correct status.
    """
    harness.disable_hooks()
    server_name = "container-down.synapse.com"
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
