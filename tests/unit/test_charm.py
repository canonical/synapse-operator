# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the Synapse module using testing."""

from unittest.mock import MagicMock

import yaml
from ops import testing
from ops.pebble import Service
from pytest import MonkeyPatch

import mjolnir
import pebble
import signing_key
import synapse
from charm import SynapseCharm
from user import User


def serv(name, obj):
    """
    Create a Service instance with the given name and raw object.

    Args:
        name (str): The name of the service.
        obj (dict): The raw service definition.

    Returns:
        Service: A new Service instance.
    """
    return Service(name, raw=obj)


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


def test_config_changed_single_unit_main_layers(base_state: dict, monkeypatch: MonkeyPatch):
    """
    arrange: prepare synapse state.
    act: run config_changed.
    assert: synapse-federation-sender is not present.
    """
    state = testing.State(**base_state)
    context = testing.Context(
        charm_type=SynapseCharm,
    )
    monkeypatch.setattr(signing_key, "get_signing_key_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_container", MagicMock())

    out = context.run(context.on.config_changed(), state)

    assert out.unit_status == testing.ActiveStatus()
    container = out.get_container("synapse")
    assert "synapse-federation-sender" not in container.plan.services


def test_config_changed_multiple_units_main_layers(
    multiple_units_base_state: dict, monkeypatch: MonkeyPatch
):
    """
    arrange: prepare synapse state.
    act: run config_changed.
    assert: synapse-federation-sender is present.
    """
    state = testing.State(**multiple_units_base_state)
    context = testing.Context(
        charm_type=SynapseCharm,
    )
    monkeypatch.setattr(signing_key, "get_signing_key_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_container", MagicMock())

    out = context.run(context.on.config_changed(), state)

    assert out.unit_status == testing.ActiveStatus()
    container = out.get_container("synapse")
    assert "synapse-federation-sender" in container.plan.services


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

    monkeypatch.setattr(signing_key, "get_signing_key_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_container", MagicMock())
    monkeypatch.setattr(pebble, "reconcile", MagicMock())
    monkeypatch.setattr(mjolnir.Mjolnir, "_admin_access_token", property(lambda self: admin_token))
    monkeypatch.setattr(mjolnir.Mjolnir, "get_membership_room_id", get_membership_room_id_mock)
    monkeypatch.setattr(synapse, "create_user", create_user_mock)
    monkeypatch.setattr(synapse, "get_room_id", get_room_id_mock)
    monkeypatch.setattr(synapse, "make_room_admin", make_room_admin_mock)
    monkeypatch.setattr(synapse, "generate_mjolnir_config", generate_config_mock)
    monkeypatch.setattr(synapse, "override_rate_limit", override_rate_limit_mock)

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
    assert out.unit_status == testing.ActiveStatus()
    container = out.get_container("synapse")
    assert "mjolnir" in container.plan.services
    assert container.plan.services["mjolnir"] == serv(
        "mjolnir",
        (
            {
                "summary": "Mjolnir service",
                "startup": "enabled",
                "override": "replace",
                "command": (
                    "/mjolnir-entrypoint.sh bot " "--mjolnir-config /data/config/production.yaml"
                ),
            }
        ),
    )


def test_config_changed_enable_mjolnir_failed(base_state: dict, monkeypatch: MonkeyPatch):
    """
    arrange: prepare synapse state with Mjolnir enabled, mock all calls.
    act: run config_changed.
    assert: Mjolnir-related methods are called with expected values.
    """
    base_state["config"]["enable_mjolnir"] = True
    state = testing.State(**base_state)
    context = testing.Context(charm_type=SynapseCharm)
    # added nosec because these are not hardcoded passwords
    admin_token = "syt_AjfVef2_L33JNpafeif_0feKJfeaf0CQpoZk"  # nosec
    user_token = "syt_AjfVef2_L33JNpafeif_0feKJfeaf0CQpoZk"  # nosec
    user_mock = User(username="Test", admin=True)
    user_mock.access_token = user_token
    get_membership_room_id_mock = MagicMock(return_value=None)
    monkeypatch.setattr(signing_key, "get_signing_key_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_container", MagicMock())
    monkeypatch.setattr(pebble, "reconcile", MagicMock())
    monkeypatch.setattr(mjolnir.Mjolnir, "_admin_access_token", property(lambda self: admin_token))
    monkeypatch.setattr(mjolnir.Mjolnir, "get_membership_room_id", get_membership_room_id_mock)

    out = context.run(context.on.config_changed(), state)

    get_membership_room_id_mock.assert_called_once_with(admin_token)
    assert out.unit_status == testing.BlockedStatus("moderators not found. Disable Mjolnir.")


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
    monkeypatch.setattr(signing_key, "get_signing_key_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_container", MagicMock())
    monkeypatch.setattr(pebble, "reconcile", MagicMock())

    out = context.run(context.on.config_changed(), state)

    assert out.unit_status == testing.BlockedStatus("Redis integration is required.")


def test_config_changed_multiple_units_with_redis(
    multiple_units_base_state: dict, monkeypatch: MonkeyPatch
):
    """
    arrange: prepare synapse state.
    act: run config_changed.
    assert: instance_map_config is correct.
    """
    state = testing.State(**multiple_units_base_state)
    context = testing.Context(
        charm_type=SynapseCharm,
    )
    monkeypatch.setattr(signing_key, "get_signing_key_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_container", MagicMock())
    monkeypatch.setattr(pebble, "reconcile", MagicMock())

    with context(context.on.config_changed(), state) as manager:
        out = manager.run()
        assert manager.charm.build_charm_state().instance_map_config == {
            "federationsender1": {"host": "synapse-0.synapse-endpoints", "port": 8034},
            "main": {"host": "synapse-0.synapse-endpoints", "port": 8035},
            "worker1": {"host": "synapse-1.synapse-endpoints", "port": 8034},
            "worker2": {"host": "synapse-2.synapse-endpoints", "port": 8034},
        }
        assert out.unit_status == testing.ActiveStatus()


def test_config_changed_workers_ignore_list(
    multiple_units_base_state: dict, monkeypatch: MonkeyPatch
):
    """
    arrange: prepare synapse state and set workers_ignore_list.
    act: run config_changed.
    assert: instance_map_config is correct without worker in workers_ignore_list.
    """
    multiple_units_base_state["config"]["workers_ignore_list"] = "worker1"
    state = testing.State(**multiple_units_base_state)
    context = testing.Context(
        charm_type=SynapseCharm,
    )
    monkeypatch.setattr(signing_key, "get_signing_key_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_container", MagicMock())

    with context(context.on.config_changed(), state) as manager:
        out = manager.run()
        assert manager.charm.build_charm_state().instance_map_config == {
            "federationsender1": {"host": "synapse-0.synapse-endpoints", "port": 8034},
            "main": {"host": "synapse-0.synapse-endpoints", "port": 8035},
            "worker2": {"host": "synapse-2.synapse-endpoints", "port": 8034},
        }
        container = out.get_container("synapse")
        file = container.get_filesystem(context) / "data" / "homeserver.yaml"
        with file.open() as f:
            content = yaml.safe_load(f)
            assert content.get("instance_map") == {
                "federationsender1": {"host": "synapse-0.synapse-endpoints", "port": 8034},
                "main": {"host": "synapse-0.synapse-endpoints", "port": 8035},
                "worker2": {"host": "synapse-2.synapse-endpoints", "port": 8034},
            }
        assert out.unit_status == testing.ActiveStatus()


def test_config_changed_experimental_extract_background_tasks(
    multiple_units_base_state: dict, monkeypatch: MonkeyPatch
):
    """
    arrange: prepare synapse state and set workers_ignore_list.
    act: run config_changed.
    assert: instance_map_config is correct without worker in workers_ignore_list.
    """
    multiple_units_base_state["config"]["experimental_extract_background_tasks"] = True
    state = testing.State(**multiple_units_base_state)
    context = testing.Context(
        charm_type=SynapseCharm,
    )
    monkeypatch.setattr(signing_key, "get_signing_key_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_secret", MagicMock())
    monkeypatch.setattr(signing_key, "write_to_container", MagicMock())

    out = context.run(context.on.config_changed(), state)

    container = out.get_container("synapse")
    file = container.get_filesystem(context) / "data" / "homeserver.yaml"
    assert "run_background_tasks_on: worker1" in file.read_text()
    assert out.unit_status == testing.ActiveStatus()
