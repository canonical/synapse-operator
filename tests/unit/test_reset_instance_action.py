# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Reset instance action unit tests."""

# pylint: disable=protected-access

import io
import unittest.mock

import ops
import pytest
from ops.testing import Harness


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_reset_instance_action(harness_server_name_changed: Harness) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: run reset-instance action.
    assert: Synapse charm should reset the instance.
    """
    harness = harness_server_name_changed
    harness.set_leader(True)
    event = unittest.mock.Mock()
    # Calling to test the action since is not possible calling via harness
    harness.charm._on_reset_instance_action(event)
    assert event.set_results.call_count == 1
    event.set_results.assert_called_with({"reset-instance": True})
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


@pytest.mark.parametrize("harness", [1], indirect=True)
def test_reset_instance_action_failed(harness_server_name_changed: Harness) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change server_name and run reset-instance action.
    assert: Synapse charm should be blocked by error on migrate_config command.
    """
    harness = harness_server_name_changed
    harness.set_leader(True)
    event = unittest.mock.Mock()
    # Calling to test the action since is not possible calling via harness
    harness.charm._on_reset_instance_action(event)
    assert event.set_results.call_count == 0
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "Migrate config failed" in str(harness.model.unit.status)


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_reset_instance_action_path_error_blocked(
    container_with_path_error_blocked: unittest.mock.MagicMock,
    harness_server_name_changed: Harness,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change server_name and run reset-instance action.
    assert: Synapse charm should be blocked by error on remove_path.
    """
    harness = harness_server_name_changed
    harness.set_leader(True)
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
    harness_server_name_changed: Harness,
    monkeypatch: pytest.MonkeyPatch,
    erase_database_mocked: unittest.mock.MagicMock,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change server_name and run reset-instance action.
    assert: Synapse charm should reset the instance.
    """
    harness = harness_server_name_changed
    harness.set_leader(True)
    harness.charm._database = erase_database_mocked
    server_name_changed = "pebble-layer-1.synapse.com"
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
    harness_server_name_changed: Harness,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change server_name and run reset-instance action.
    assert: Synapse charm should take no action if no leader.
    """
    harness = harness_server_name_changed
    harness.set_leader(False)
    event = unittest.mock.MagicMock()
    # Calling to test the action since is not possible calling via harness
    harness.charm._on_reset_instance_action(event)
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
