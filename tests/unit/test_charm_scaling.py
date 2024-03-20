# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm scaling unit tests."""

import unittest

import ops
from ops.testing import Harness

import synapse


def test_scaling_redis_required(harness: Harness) -> None:
    """
    arrange: charm deployed.
    act: scale charm to more than 1 unit and emit synapse pebble ready event;
    assert: Synapse charm is in BlockedStatus due lacking of Redis integration.
    """
    harness.begin()
    harness.set_leader(True)

    rel_id = harness.add_relation(synapse.SYNAPSE_PEER_RELATION_NAME, harness.charm.app.name)
    harness.add_relation_unit(rel_id, "synapse/1")

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
    rel_id = harness.add_relation(synapse.SYNAPSE_PEER_RELATION_NAME, harness.charm.app.name)
    harness.add_relation_unit(rel_id, "synapse/1")
    harness.charm.on.synapse_pebble_ready.emit(unittest.mock.MagicMock())
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)

    harness.remove_relation_unit(rel_id, "synapse/1")
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
    harness.begin_with_initial_hooks()
    relation = harness.charm.framework.model.get_relation("redis", 0)
    # We need to bypass protected access to inject the relation data
    # pylint: disable=protected-access
    harness.charm._redis._stored.redis_relation = {
        relation.id: ({"hostname": "redis-host", "port": 1010})
    }
    harness.set_leader(True)

    harness.add_relation(synapse.SYNAPSE_PEER_RELATION_NAME, harness.charm.app.name)

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
        app_data={"main_unit_id": "foo"},
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
    unit.name = "foo"
    harness.charm.on[synapse.SYNAPSE_PEER_RELATION_NAME].relation_departed.emit(
        relation=relation, app=harness.charm.app, unit=unit
    )

    synapse_layer = harness.get_container_pebble_plan(synapse.SYNAPSE_CONTAINER_NAME).to_dict()[
        "services"
    ][synapse.SYNAPSE_SERVICE_NAME]
    assert "/start.py" == synapse_layer["command"]
