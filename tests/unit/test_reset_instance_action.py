# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Reset instance action unit tests."""

# pylint: disable=protected-access

import io
import unittest.mock

import ops
import pytest
from ops.testing import Harness

import synapse

from .conftest import TEST_SERVER_NAME


def test_reset_instance_action(harness: Harness) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: run reset-instance action.
    assert: Synapse charm should reset the instance.
    """
    harness.begin()
    harness.set_leader(True)
    event = unittest.mock.Mock()

    # Calling to test the action since is not possible calling via harness
    harness.charm._on_reset_instance_action(event)

    # Disable no-member to allow tests on generated mock attributes
    # pylint: disable=no-member
    assert event.set_results.call_count == 1
    event.set_results.assert_called_with({"reset-instance": True})
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


def test_reset_instance_action_container_down(harness: Harness) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: run reset-instance action.
    assert: Synapse charm should reset the instance.
    """
    harness.begin()
    harness.set_leader(True)
    harness.set_can_connect(harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME], False)
    event = unittest.mock.Mock()

    # Calling to test the action since is not possible calling via harness
    harness.charm._on_reset_instance_action(event)

    assert event.set_results.call_count == 0
    assert event.fail.call_count == 1
    assert "Failed to connect to container" == event.fail.call_args[0][0]


@pytest.mark.parametrize(
    "harness",
    [
        pytest.param(1, id="harness_exit_code"),
    ],
    indirect=True,
)
def test_reset_instance_action_failed(harness: Harness) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change server_name and run reset-instance action.
    assert: Synapse charm should be blocked by error on migrate_config command.
    """
    harness.begin()
    harness.set_leader(True)
    event = unittest.mock.Mock()

    # Calling to test the action since is not possible calling via harness
    harness.charm._on_reset_instance_action(event)

    assert event.set_results.call_count == 0
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "Migrate config failed" in str(harness.model.unit.status)


def test_reset_instance_action_path_error_blocked(
    container_with_path_error_blocked: unittest.mock.MagicMock,
    harness: Harness,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change server_name and run reset-instance action.
    assert: Synapse charm should be blocked by error on remove_path.
    """
    harness.begin()
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


def test_reset_instance_action_path_error_pass(
    container_with_path_error_pass: unittest.mock.MagicMock,
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
    erase_database_mocked: unittest.mock.MagicMock,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change server_name and run reset-instance action.
    assert: Synapse charm should reset the instance.
    """
    harness.begin()
    harness.set_leader(True)
    harness.charm._database = erase_database_mocked
    content = io.StringIO(f'server_name: "{TEST_SERVER_NAME}"')
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


def test_reset_instance_action_no_leader(
    harness: Harness,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change server_name and run reset-instance action.
    assert: Synapse charm should take no action if no leader.
    """
    harness.begin()
    harness.set_leader(False)

    event = unittest.mock.MagicMock()
    # Calling to test the action since is not possible calling via harness
    harness.charm._on_reset_instance_action(event)

    # Disable no-member to allow tests on generated mock attributes
    # pylint: disable=no-member
    assert event.fail.call_count == 1
    assert "Only the juju leader unit can run reset instance action" == event.fail.call_args[0][0]
