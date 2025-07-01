# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the Synapse module using testing."""

from unittest.mock import MagicMock

from ops import testing
from pytest import MonkeyPatch

import mjolnir
import pebble
import synapse
from charm import SynapseCharm
from user import User


def test_config_changed(base_state: dict, monkeypatch: MonkeyPatch):
    """
    arrange: prepare synapse state.
    act: run config_changed.
    assert: reconcile is called once.
    """
    state = testing.State(**base_state)
    context = testing.Context(
        charm_type=SynapseCharm,
    )
    reconcile_mock = MagicMock()
    monkeypatch.setattr("charm.SynapseCharm.reconcile", reconcile_mock)

    context.run(context.on.config_changed(), state)

    reconcile_mock.assert_called_once()


def test_config_changed_enable_mjolnir(base_state: dict, monkeypatch: MonkeyPatch):
    """
    arrange: prepare synapse state with Mjolnir enabled, mock all calls.
    act: run config_changed.
    assert: Mjolnir-related methods are called with expected values.
    """
    # Arrange
    base_state["config"]["enable_mjolnir"] = True
    state = testing.State(**base_state)
    context = testing.Context(charm_type=SynapseCharm)

    # added nosec because these are not hardcoded passwords
    admin_token = "syt_AjfVef2_L33JNpafeif_0feKJfeaf0CQpoZk"  # nosec
    membership_room_id = "!zpGCCHhtJqXSVwqinv:test.synapse"  # nosec
    room_id = "!zpGCCHhtJqXSVwqinv:test.synapse"  # nosec
    user_token = "syt_AjfVef2_L33JNpafeif_0feKJfeaf0CQpoZk"  # nosec

    user_mock = User(username="Test", admin=True)
    user_mock.access_token = user_token
    get_membership_room_id_mock = MagicMock(return_value=membership_room_id)
    create_user_mock = MagicMock(return_value=user_mock)
    get_room_id_mock = MagicMock(return_value=room_id)
    make_room_admin_mock = MagicMock()
    generate_config_mock = MagicMock()
    override_rate_limit_mock = MagicMock()
    replan_mjolnir_mock = MagicMock()

    monkeypatch.setattr("charm.SynapseCharm.manage_signing_key", MagicMock())
    monkeypatch.setattr(pebble, "reconcile", MagicMock())
    monkeypatch.setattr(mjolnir.Mjolnir, "_admin_access_token", property(lambda self: admin_token))
    monkeypatch.setattr(mjolnir.Mjolnir, "get_membership_room_id", get_membership_room_id_mock)
    monkeypatch.setattr(synapse, "create_user", create_user_mock)
    monkeypatch.setattr(synapse, "get_room_id", get_room_id_mock)
    monkeypatch.setattr(synapse, "make_room_admin", make_room_admin_mock)
    monkeypatch.setattr(synapse, "generate_mjolnir_config", generate_config_mock)
    monkeypatch.setattr(synapse, "override_rate_limit", override_rate_limit_mock)
    monkeypatch.setattr(pebble, "replan_mjolnir", replan_mjolnir_mock)

    # Act
    out = context.run(context.on.config_changed(), state)

    # Assert
    get_membership_room_id_mock.assert_called_once_with(admin_token)
    create_user_mock.assert_called_once()
    assert create_user_mock.call_args[0][3] == admin_token  # 4th positional arg is the token

    get_room_id_mock.assert_called_once()
    assert get_room_id_mock.call_args.kwargs["admin_access_token"] == admin_token

    make_room_admin_mock.assert_called_once()
    assert make_room_admin_mock.call_args.kwargs["room_id"] == room_id

    generate_config_mock.assert_called_once()
    override_rate_limit_mock.assert_called_once()
    replan_mjolnir_mock.assert_called_once()
    assert out.unit_status == testing.ActiveStatus()


def test_config_changed_multiple_units_no_redis(base_state: dict, monkeypatch: MonkeyPatch):
    """
    arrange: prepare synapse state.
    act: run config_changed.
    assert: charm is blocked.
    """
    base_state["planned_units"] = 3
    base_state["leader"] = False
    state = testing.State(**base_state)
    context = testing.Context(
        charm_type=SynapseCharm,
    )
    monkeypatch.setattr("charm.SynapseCharm.manage_signing_key", MagicMock())
    monkeypatch.setattr(pebble, "reconcile", MagicMock())

    out = context.run(context.on.config_changed(), state)

    assert out.unit_status == testing.BlockedStatus("Redis integration is required.")


def test_config_changed_multiple_units_with_redis(
    multiple_units_base_state: dict, monkeypatch: MonkeyPatch
):
    """
    arrange: prepare synapse state.
    act: run config_changed.
    assert: charm is blocked.
    """
    state = testing.State(**multiple_units_base_state)
    context = testing.Context(
        charm_type=SynapseCharm,
    )
    monkeypatch.setattr("charm.SynapseCharm.manage_signing_key", MagicMock())
    monkeypatch.setattr(pebble, "reconcile", MagicMock())

    with context(context.on.config_changed(), state) as manager:
        out = manager.run()
        assert manager.charm._instance_map() == {
            "federationsender1": {"host": "synapse-0.synapse-endpoints", "port": 8034},
            "main": {"host": "synapse-0.synapse-endpoints", "port": 8035},
            "worker1": {"host": "synapse-1.synapse-endpoints", "port": 8034},
            "worker2": {"host": "synapse-2.synapse-endpoints", "port": 8034},
        }
        assert out.unit_status == testing.ActiveStatus()
