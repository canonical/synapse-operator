# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm scaling unit tests."""

import unittest
from unittest.mock import MagicMock

import ops
import pytest
import yaml
from ops.testing import Harness

import pebble
import synapse


def test_scaling_redis_required(harness: Harness) -> None:
    """
    arrange: charm deployed.
    act: scale charm to more than 1 unit and emit synapse pebble ready event;
    assert: Synapse charm is in BlockedStatus due lacking of Redis integration.
    """
    harness.begin()
    harness.set_leader(True)
    harness.set_planned_units(2)

    harness.charm.on.synapse_pebble_ready.emit(unittest.mock.MagicMock())

    assert isinstance(harness.charm.unit.status, ops.BlockedStatus)


def test_scaling_redis_not_required(harness: Harness) -> None:
    """
    arrange: charm deployed, scaled to more than 1 unit and synapse pebble ready event is emitted.
    act: scale down and emit synapse pebble ready event.
    assert: Synapse charm is not Blocked.
    """
    harness.begin()
    harness.set_leader(True)
    harness.set_planned_units(1)

    harness.charm.on.synapse_pebble_ready.emit(unittest.mock.MagicMock())

    assert not isinstance(harness.model.unit.status, ops.BlockedStatus)


def test_scaling_worker_configured(harness: Harness) -> None:
    """
    arrange: charm deployed, integrated with Redis and set as no leader.
    act: scale charm to more than 1 unit.
    assert: Synapse charm is configured as worker.
    """
    harness.begin_with_initial_hooks()
    relation = harness.charm.framework.model.get_relation("redis", 0)
    # We need to bypass protected access to inject the relation data
    # pylint: disable=protected-access
    harness.charm._redis._stored.redis_relation = {
        relation.id: ({"hostname": "redis-host", "port": 1010})
    }
    harness.set_leader(False)

    rel_id = harness.add_relation(synapse.SYNAPSE_PEER_RELATION_NAME, harness.charm.app.name)
    harness.add_relation_unit(rel_id, "synapse/1")

    synapse_layer = harness.get_container_pebble_plan(synapse.SYNAPSE_CONTAINER_NAME).to_dict()[
        "services"
    ][synapse.SYNAPSE_SERVICE_NAME]
    command = (
        f"/start.py run -m synapse.app.generic_worker "
        f"--config-path {synapse.SYNAPSE_CONFIG_PATH} "
        f"--config-path {synapse.SYNAPSE_WORKER_CONFIG_PATH}"
    )
    assert command == synapse_layer["command"]


def test_scaling_main_configured(harness: Harness) -> None:
    """
    arrange: charm deployed, integrated with Redis and set as a leader.
    act: create peer relation.
    assert: Synapse charm is configured as main.
    """
    harness.begin()
    harness.add_relation(
        synapse.SYNAPSE_PEER_RELATION_NAME,
        harness.charm.app.name,
        app_data={"main_unit_id": "synapse/0"},
    )
    relation = harness.charm.framework.model.get_relation("redis", 0)
    # We need to bypass protected access to inject the relation data
    # pylint: disable=protected-access
    harness.charm._redis._stored.redis_relation = {
        relation.id: ({"hostname": "redis-host", "port": 1010})
    }
    harness.set_leader(True)

    harness.charm.on.config_changed.emit()

    synapse_layer = harness.get_container_pebble_plan(synapse.SYNAPSE_CONTAINER_NAME).to_dict()[
        "services"
    ][synapse.SYNAPSE_SERVICE_NAME]
    assert "/start.py" == synapse_layer["command"]


def test_scaling_main_unit_departed(harness: Harness) -> None:
    """
    arrange: charm deployed, integrated with Redis and set as a no leader.
    act: set as a leader and emit relation departed for the previous main_unit.
    assert: Synapse charm is re-configured as the main unit.
    """
    harness.begin_with_initial_hooks()
    relation = harness.charm.framework.model.get_relation("redis", 0)
    # We need to bypass protected access to inject the relation data
    # pylint: disable=protected-access
    harness.charm._redis._stored.redis_relation = {
        relation.id: ({"hostname": "redis-host", "port": 1010})
    }
    harness.set_leader(False)
    harness.add_relation(
        synapse.SYNAPSE_PEER_RELATION_NAME,
        harness.charm.app.name,
        app_data={"main_unit_id": "synapse/0"},
    )
    relation = harness.model.relations[synapse.SYNAPSE_PEER_RELATION_NAME][0]
    synapse_layer = harness.get_container_pebble_plan(synapse.SYNAPSE_CONTAINER_NAME).to_dict()[
        "services"
    ][synapse.SYNAPSE_SERVICE_NAME]
    command = (
        f"/start.py run -m synapse.app.generic_worker "
        f"--config-path {synapse.SYNAPSE_CONFIG_PATH} "
        f"--config-path {synapse.SYNAPSE_WORKER_CONFIG_PATH}"
    )
    assert command == synapse_layer["command"]

    harness.set_leader(True)
    unit = harness.charm.unit
    unit.name = "synapse/0"
    harness.charm.on[synapse.SYNAPSE_PEER_RELATION_NAME].relation_departed.emit(
        relation=relation, app=harness.charm.app, unit=unit
    )

    synapse_layer = harness.get_container_pebble_plan(synapse.SYNAPSE_CONTAINER_NAME).to_dict()[
        "services"
    ][synapse.SYNAPSE_SERVICE_NAME]
    assert "/start.py" == synapse_layer["command"]


def test_scaling_instance_map_configured(harness: Harness) -> None:
    """
    arrange: charm deployed, integrated with Redis, one more unit in peer relation
        and set as leader.
    act: emit config-changed event.
    assert: Synapse charm is configured with instance_map.
    """
    rel_id = harness.add_relation(synapse.SYNAPSE_PEER_RELATION_NAME, "synapse")
    harness.add_relation_unit(rel_id, "synapse/1")
    harness.begin_with_initial_hooks()
    relation = harness.charm.framework.model.get_relation("redis", 0)
    # We need to bypass protected access to inject the relation data
    # pylint: disable=protected-access
    harness.charm._redis._stored.redis_relation = {
        relation.id: ({"hostname": "redis-host", "port": 1010})
    }
    harness.set_leader(True)

    harness.charm.on.config_changed.emit()

    root = harness.get_filesystem_root(synapse.SYNAPSE_CONTAINER_NAME)
    config_path = root / synapse.SYNAPSE_CONFIG_PATH[1:]
    with open(config_path, encoding="utf-8") as config_file:
        content = yaml.safe_load(config_file)
        assert "instance_map" in content
        assert content["instance_map"] == {
            "main": {
                "host": "synapse-0.synapse-endpoints",
                "port": 8034,
            },
            "worker1": {
                "host": "synapse-1.synapse-endpoints",
                "port": 8034,
            },
        }


def test_scaling_instance_map_not_configured(harness: Harness) -> None:
    """
    arrange: charm deployed, integrated with Redis and set as leader.
    act: emit config-changed event.
    assert: Synapse charm is not configured with instance_map.
    """
    harness.begin_with_initial_hooks()
    relation = harness.charm.framework.model.get_relation("redis", 0)
    # We need to bypass protected access to inject the relation data
    # pylint: disable=protected-access
    harness.charm._redis._stored.redis_relation = {
        relation.id: ({"hostname": "redis-host", "port": 1010})
    }
    harness.set_leader(True)

    harness.charm.on.config_changed.emit()

    root = harness.get_filesystem_root(synapse.SYNAPSE_CONTAINER_NAME)
    config_path = root / synapse.SYNAPSE_CONFIG_PATH[1:]
    with open(config_path, encoding="utf-8") as config_file:
        content = yaml.safe_load(config_file)
        assert "instance_map" not in content


def test_scaling_stream_writers_configured(harness: Harness) -> None:
    """
    arrange: charm deployed, integrated with Redis, two more units in peer relation
        and set as leader.
    act: emit config-changed event.
    assert: Synapse charm is configured with stream_writer.
    """
    rel_id = harness.add_relation(synapse.SYNAPSE_PEER_RELATION_NAME, "synapse")
    harness.add_relation_unit(rel_id, "synapse/1")
    harness.add_relation_unit(rel_id, "synapse/2")
    harness.begin_with_initial_hooks()
    relation = harness.charm.framework.model.get_relation("redis", 0)
    # We need to bypass protected access to inject the relation data
    # pylint: disable=protected-access
    harness.charm._redis._stored.redis_relation = {
        relation.id: ({"hostname": "redis-host", "port": 1010})
    }
    harness.set_leader(True)

    harness.charm.on.config_changed.emit()

    root = harness.get_filesystem_root(synapse.SYNAPSE_CONTAINER_NAME)
    config_path = root / synapse.SYNAPSE_CONFIG_PATH[1:]
    with open(config_path, encoding="utf-8") as config_file:
        content = yaml.safe_load(config_file)
        assert "stream_writers" in content
        expected_events = ["worker1", "worker2"]
        actual_events = content["stream_writers"]["events"]
        assert sorted(actual_events) == sorted(expected_events)


def test_scaling_main_unit_changed_nginx_reconfigured(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: charm deployed, integrated with Redis, no leader, replan_nginx is mocked.
    act: update relation data to change the main_unit_id.
    assert: Synapse NGINX is replanned with the new main unit.
    """
    peer_relation_id = harness.add_relation(
        synapse.SYNAPSE_PEER_RELATION_NAME,
        "synapse",
        app_data={"main_unit_id": "synapse/0"},
    )
    harness.begin_with_initial_hooks()
    nginx_container = harness.model.unit.containers[synapse.SYNAPSE_NGINX_CONTAINER_NAME]
    harness.set_can_connect(nginx_container, True)
    redis_relation = harness.charm.framework.model.get_relation("redis", 0)
    # We need to bypass protected access to inject the relation data
    # pylint: disable=protected-access
    harness.charm._redis._stored.redis_relation = {
        redis_relation.id: ({"hostname": "redis-host", "port": 1010})
    }
    harness.set_leader(False)
    # emit nginx ready
    # assert was called with synapse/0
    replan_nginx_mock = MagicMock()
    monkeypatch.setattr(pebble, "replan_nginx", replan_nginx_mock)
    harness.charm.on.synapse_nginx_pebble_ready.emit(MagicMock())
    replan_nginx_mock.assert_called_with(nginx_container, "synapse-0.synapse-endpoints")

    harness.update_relation_data(
        peer_relation_id, harness.charm.app.name, {"main_unit_id": "synapse/1"}
    )

    replan_nginx_mock.assert_called_with(nginx_container, "synapse-1.synapse-endpoints")


def test_scaling_stream_writers_not_configured(harness: Harness) -> None:
    """
    arrange: charm deployed, integrated with Redis and set as leader.
    act: emit config-changed event.
    assert: Synapse charm is not configured with stream_writer.
    """
    harness.begin_with_initial_hooks()
    relation = harness.charm.framework.model.get_relation("redis", 0)
    # We need to bypass protected access to inject the relation data
    # pylint: disable=protected-access
    harness.charm._redis._stored.redis_relation = {
        relation.id: ({"hostname": "redis-host", "port": 1010})
    }
    harness.set_leader(True)

    harness.charm.on.config_changed.emit()

    root = harness.get_filesystem_root(synapse.SYNAPSE_CONTAINER_NAME)
    config_path = root / synapse.SYNAPSE_CONFIG_PATH[1:]
    with open(config_path, encoding="utf-8") as config_file:
        content = yaml.safe_load(config_file)
        assert "stream_writers" not in content


def test_scaling_worker_name_configured(harness: Harness) -> None:
    """
    arrange: charm deployed, integrated with Redis, not set as leader and unit
        name is worker1.
    act: emit config-changed event.
    assert: Worker configuration is configured with expected worker name.
    """
    rel_id = harness.add_relation(synapse.SYNAPSE_PEER_RELATION_NAME, "synapse")
    harness.add_relation_unit(rel_id, "synapse/1")
    harness.begin_with_initial_hooks()
    relation = harness.charm.framework.model.get_relation("redis", 0)
    # We need to bypass protected access to inject the relation data
    # pylint: disable=protected-access
    harness.charm._redis._stored.redis_relation = {
        relation.id: ({"hostname": "redis-host", "port": 1010})
    }
    harness.set_leader(False)
    harness.charm.unit.name = "synapse/1"

    harness.charm.on.config_changed.emit()

    root = harness.get_filesystem_root(synapse.SYNAPSE_CONTAINER_NAME)
    config_path = root / synapse.SYNAPSE_WORKER_CONFIG_PATH[1:]
    with open(config_path, encoding="utf-8") as config_file:
        content = yaml.safe_load(config_file)
        assert "worker_name" in content
        assert content["worker_name"] == "worker1"


def test_scaling_relation_departed(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: charm deployed, integrated with Redis, two more units in peer relation
        and set as no leader.
    act: remove unit from relation.
    assert: Synapse charm is re-configured.
    """
    rel_id = harness.add_relation(synapse.SYNAPSE_PEER_RELATION_NAME, "synapse")
    harness.add_relation_unit(rel_id, "synapse/1")
    harness.add_relation_unit(rel_id, "synapse/2")
    harness.begin_with_initial_hooks()
    relation = harness.charm.framework.model.get_relation("redis", 0)
    # We need to bypass protected access to inject the relation data
    # pylint: disable=protected-access
    harness.charm._redis._stored.redis_relation = {
        relation.id: ({"hostname": "redis-host", "port": 1010})
    }
    harness.set_leader(False)
    harness.charm.unit.name = "synapse/1"
    change_config_mock = MagicMock()
    monkeypatch.setattr(harness.charm, "change_config", change_config_mock)

    harness.remove_relation_unit(rel_id, "synapse/2")

    change_config_mock.assert_called()
