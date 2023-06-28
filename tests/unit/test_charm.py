# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm unit tests."""

# pylint: disable=protected-access

import io
import json
import unittest.mock

import ops
import pytest
from ops.testing import Harness

from constants import (
    SYNAPSE_COMMAND_PATH,
    SYNAPSE_CONTAINER_NAME,
    SYNAPSE_PORT,
    SYNAPSE_SERVICE_NAME,
    TEST_SERVER_NAME,
)


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_synapse_pebble_layer(harness_server_name_configured: Harness) -> None:
    """
    arrange: none
    act: start the Synapse charm, set Synapse container to be ready and set server_name.
    assert: Synapse charm should submit the correct Synapse pebble layer to pebble.
    """
    harness = harness_server_name_configured
    synapse_layer = harness.get_container_pebble_plan(SYNAPSE_CONTAINER_NAME).to_dict()[
        "services"
    ][SYNAPSE_SERVICE_NAME]
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)
    assert synapse_layer == {
        "override": "replace",
        "summary": "Synapse application service",
        "command": SYNAPSE_COMMAND_PATH,
        "environment": {
            "SYNAPSE_NO_TLS": "True",
            "SYNAPSE_REPORT_STATS": "no",
            "SYNAPSE_SERVER_NAME": TEST_SERVER_NAME,
        },
        "startup": "enabled",
    }


@pytest.mark.parametrize("harness", [1], indirect=True)
def test_synapse_migrate_config_error(harness_server_name_configured: Harness) -> None:
    """
    arrange: none
    act: start the Synapse charm, set Synapse container to be ready and set server_name.
    assert: Synapse charm should be blocked by error on migrate_config command.
    """
    harness = harness_server_name_configured
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "Migrate config failed" in str(harness.model.unit.status)


def test_container_down(harness_server_name_configured: Harness) -> None:
    """
    arrange: none
    act: start the Synapse charm, set server_name, set Synapse container to be down
        and then try to change report_stats.
    assert: Synapse charm should submit the correct status.
    """
    harness = harness_server_name_configured
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


def test_traefik_integration(harness_server_name_configured: Harness) -> None:
    """
    arrange: add relation with Traefik charm.
    act: update relation with expected URL.
    assert: Relation data is as expected.
    """
    harness = harness_server_name_configured
    harness.set_leader(True)
    harness.container_pebble_ready(SYNAPSE_CONTAINER_NAME)
    relation_id = harness.add_relation("ingress", "traefik")
    harness.add_relation_unit(relation_id, "traefik/0")
    app_name = harness.charm.app.name
    model_name = harness.model.name
    url = f"http://ingress:80/{model_name}-{app_name}"
    harness.update_relation_data(
        relation_id,
        "traefik",
        {"ingress": json.dumps({"url": url})},
    )
    app_data = harness.get_relation_data(relation_id, app_name)
    assert app_data == {
        "host": f"{app_name}-endpoints.{model_name}.svc.cluster.local",
        "model": model_name,
        "name": app_name,
        "port": str(SYNAPSE_PORT),
        "strip-prefix": "true",
    }


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_server_name_change(harness_server_name_configured: Harness) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change to a different server_name.
    assert: Synapse charm should prevent the change with a BlockStatus.
    """
    harness = harness_server_name_configured
    server_name_changed = "pebble-layer-1.synapse.com"
    harness.update_config({"server_name": server_name_changed})
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "server_name modification is not allowed" in str(harness.model.unit.status)


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_reset_instance_action(harness_server_name_configured: Harness) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: run reset-instance action.
    assert: Synapse charm should reset the instance.
    """
    harness = harness_server_name_configured
    harness.set_leader(True)
    server_name_changed = "pebble-layer-1.synapse.com"
    harness.update_config({"server_name": server_name_changed})
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "server_name modification is not allowed" in str(harness.model.unit.status)
    event = unittest.mock.Mock()
    # Calling to test the action since is not possible calling via harness
    harness.charm._on_reset_instance_action(event)
    assert event.set_results.call_count == 1
    event.set_results.assert_called_with({"reset-instance": True})
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


@pytest.mark.parametrize("harness", [1], indirect=True)
def test_reset_instance_action_failed(harness_server_name_configured: Harness) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change server_name and run reset-instance action.
    assert: Synapse charm should be blocked by error on migrate_config command.
    """
    harness = harness_server_name_configured
    harness.set_leader(True)
    server_name_changed = "pebble-layer-1.synapse.com"
    harness.update_config({"server_name": server_name_changed})
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "server_name modification is not allowed" in str(harness.model.unit.status)
    event = unittest.mock.Mock()
    # Calling to test the action since is not possible calling via harness
    harness.charm._on_reset_instance_action(event)
    assert event.set_results.call_count == 0
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "Migrate config failed" in str(harness.model.unit.status)


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_reset_instance_action_path_error_blocked(
    container_with_path_error_blocked: unittest.mock.MagicMock,
    harness_server_name_configured: Harness,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change server_name and run reset-instance action.
    assert: Synapse charm should be blocked by error on remove_path.
    """
    harness = harness_server_name_configured
    harness.set_leader(True)
    server_name_changed = "pebble-layer-1.synapse.com"
    harness.update_config({"server_name": server_name_changed})
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "server_name modification is not allowed" in str(harness.model.unit.status)
    harness.charm.unit.get_container = unittest.mock.MagicMock(
        return_value=container_with_path_error_blocked
    )
    event = unittest.mock.MagicMock()
    # Calling to test the action since is not possible calling via harness
    harness.charm._on_reset_instance_action(event)
    assert container_with_path_error_blocked.remove_path.call_count == 1
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "Error erasing" in str(harness.model.unit.status)


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_reset_instance_action_path_error_pass(
    container_with_path_error_pass: unittest.mock.MagicMock,
    harness_server_name_configured: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change server_name and run reset-instance action.
    assert: Synapse charm should reset the instance.
    """
    harness = harness_server_name_configured
    harness.set_leader(True)
    server_name_changed = "pebble-layer-1.synapse.com"
    harness.update_config({"server_name": server_name_changed})
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "server_name modification is not allowed" in str(harness.model.unit.status)
    content = io.StringIO(f'server_name: "{server_name_changed}"')
    pull_mock = unittest.mock.MagicMock(return_value=content)
    monkeypatch.setattr(container_with_path_error_pass, "pull", pull_mock)
    harness.charm.unit.get_container = unittest.mock.MagicMock(
        return_value=container_with_path_error_pass
    )
    event = unittest.mock.MagicMock()
    # Calling to test the action since is not possible calling via harness
    harness.charm._on_reset_instance_action(event)
    assert container_with_path_error_pass.remove_path.call_count == 1
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_reset_instance_action_no_leader(
    harness_server_name_configured: Harness,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change server_name and run reset-instance action.
    assert: Synapse charm should take no action if no leader.
    """
    harness = harness_server_name_configured
    harness.set_leader(True)
    server_name_changed = "pebble-layer-1.synapse.com"
    harness.update_config({"server_name": server_name_changed})
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "server_name modification is not allowed" in str(harness.model.unit.status)
    harness.set_leader(False)
    event = unittest.mock.MagicMock()
    # Calling to test the action since is not possible calling via harness
    harness.charm._on_reset_instance_action(event)
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
