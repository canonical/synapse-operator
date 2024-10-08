# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm scaling unit tests."""

import unittest
from unittest.mock import ANY, MagicMock, call

import ops
import pytest
import yaml
from ops.testing import Harness

import pebble
import synapse

from .conftest import TEST_SERVER_NAME


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
    harness.add_relation("redis", "redis", unit_data={"hostname": "redis-host", "port": "1010"})
    harness.set_leader(False)

    rel_id = harness.add_relation(synapse.SYNAPSE_PEER_RELATION_NAME, harness.charm.app.name)
    harness.add_relation_unit(rel_id, "synapse/1")
    relation = harness.model.get_relation(synapse.SYNAPSE_PEER_RELATION_NAME, rel_id)
    harness.charm.on[synapse.SYNAPSE_PEER_RELATION_NAME].relation_changed.emit(
        relation, harness.charm.app, harness.charm.unit
    )

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
    harness.add_relation("redis", "redis", unit_data={"hostname": "redis-host", "port": "1010"})
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
    harness.add_relation("redis", "redis", unit_data={"hostname": "redis-host", "port": "1010"})
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
    harness.add_relation("redis", "redis", unit_data={"hostname": "redis-host", "port": "1010"})
    harness.set_leader(True)

    root = harness.get_filesystem_root(synapse.SYNAPSE_CONTAINER_NAME)
    config_path = root / synapse.SYNAPSE_CONFIG_PATH[1:]
    with open(config_path, encoding="utf-8") as config_file:
        content = yaml.safe_load(config_file)
        assert "instance_map" in content
        assert content["instance_map"] == {
            "main": {
                "host": "synapse-0.synapse-endpoints",
                "port": 8035,
            },
            "federationsender1": {
                "host": "synapse-0.synapse-endpoints",
                "port": 8034,
            },
            "worker1": {
                "host": "synapse-1.synapse-endpoints",
                "port": 8034,
            },
        }
    worker_config_path = root / synapse.SYNAPSE_WORKER_CONFIG_PATH[1:]
    with open(worker_config_path, encoding="utf-8") as config_file:
        content = yaml.safe_load(config_file)
        assert content["worker_name"] == "federationsender1"


def test_scaling_instance_restarts_federation_service(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: charm deployed, integrated with Redis, one more unit in peer relation
        and set as leader.
    act: emit config-changed event.
    assert: Synapse charm is configured with instance_map and the federation service is restarted.
    """
    rel_id = harness.add_relation(synapse.SYNAPSE_PEER_RELATION_NAME, "synapse")
    harness.add_relation_unit(rel_id, "synapse/1")
    harness.begin_with_initial_hooks()
    federation_container = harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME]
    harness.set_can_connect(federation_container, True)
    harness.add_relation("redis", "redis", unit_data={"hostname": "redis-host", "port": "1010"})
    harness.set_leader(True)

    restart_federation_mock = MagicMock()
    monkeypatch.setattr(pebble, "restart_federation_sender", restart_federation_mock)
    harness.update_config({"workers_ignore_list": "worker1"})
    assert restart_federation_mock.called


def test_scaling_instance_map_not_configured(harness: Harness) -> None:
    """
    arrange: charm deployed, integrated with Redis and set as leader.
    act: emit config-changed event.
    assert: Synapse charm is not configured with instance_map.
    """
    harness.begin_with_initial_hooks()
    harness.add_relation("redis", "redis", unit_data={"hostname": "redis-host", "port": "1010"})
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
    harness.add_relation("redis", "redis", unit_data={"hostname": "redis-host", "port": "1010"})
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
    arrange: charm deployed, integrated with Redis, no leader, restart_nginx is mocked.
    act: update relation data to change the main_unit_id.
    assert: Synapse NGINX is replanned with the new main unit.
    """
    peer_relation_id = harness.add_relation(
        synapse.SYNAPSE_PEER_RELATION_NAME,
        "synapse",
        app_data={"main_unit_id": "synapse/0"},
    )
    restart_nginx_mock = MagicMock()
    monkeypatch.setattr(pebble, "restart_nginx", restart_nginx_mock)
    nginx_container = harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME]
    harness.set_can_connect(nginx_container, True)
    harness.begin_with_initial_hooks()
    harness.add_relation("redis", "redis", unit_data={"hostname": "redis-host", "port": "1010"})
    harness.set_leader(False)
    restart_nginx_mock.assert_called_with(nginx_container, "synapse-0.synapse-endpoints")

    harness.update_relation_data(
        peer_relation_id, harness.charm.app.name, {"main_unit_id": "synapse/1"}
    )

    restart_nginx_mock.assert_called_with(nginx_container, "synapse-1.synapse-endpoints")


def test_scaling_stream_writers_not_configured(harness: Harness) -> None:
    """
    arrange: charm deployed, integrated with Redis and set as leader.
    act: emit config-changed event.
    assert: Synapse charm is not configured with stream_writer.
    """
    harness.begin_with_initial_hooks()
    harness.add_relation("redis", "redis", unit_data={"hostname": "redis-host", "port": "1010"})
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
    harness.add_relation("redis", "redis", unit_data={"hostname": "redis-host", "port": "1010"})
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
    harness.add_relation("redis", "redis", unit_data={"hostname": "redis-host", "port": "1010"})
    harness.set_leader(False)
    harness.charm.unit.name = "synapse/1"
    reconcile_mock = MagicMock()
    monkeypatch.setattr(harness.charm, "reconcile", reconcile_mock)

    harness.remove_relation_unit(rel_id, "synapse/2")

    reconcile_mock.assert_called()


def test_scaling_signing_key_pushed_worker(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: charm deployed, integrated with Redis, one more unit in peer relation
        and set as no leader.
    act: emit config changed.
    assert: Signing key is copied from the secret and pushed to the container.
    """
    rel_id = harness.add_relation(synapse.SYNAPSE_PEER_RELATION_NAME, "synapse")
    harness.add_relation_unit(rel_id, "synapse/1")
    harness.begin_with_initial_hooks()
    harness.add_relation("redis", "redis", unit_data={"hostname": "redis-host", "port": "1010"})
    harness.set_leader(False)
    harness.charm.unit.name = "synapse/1"
    signing_key = "ed25519 a_ONyE 5YwXqh43qXKrwQa/9Vcjog66xYliBUzotClQ5SUt9tk"
    monkeypatch.setattr(harness.charm, "get_signing_key", MagicMock(return_value=signing_key))
    container = harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME]
    push_mock = MagicMock()
    monkeypatch.setattr(container, "push", push_mock)

    harness.charm.on.config_changed.emit()

    push_mock.assert_has_calls(
        [
            call(
                f"/data/{TEST_SERVER_NAME}.signing.key",
                signing_key,
                make_dirs=True,
                encoding="utf-8",
            ),
            call(ANY, ANY),
        ],
        any_order=True,
    )


def test_scaling_signing_key_found(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: charm deployed, integrated with Redis and set as main.
    act: emit config changed.
    assert: Signing key secret is found and content is pushed.
    """
    harness.begin_with_initial_hooks()
    signing_key = "ed25519 a_ONyE 5YwXqh43qXKrwQa/9Vcjog66xYliBUzotClQ5SUt9tk"
    get_signing_key_mock = MagicMock(return_value=signing_key)
    monkeypatch.setattr(harness.charm, "get_signing_key", get_signing_key_mock)
    container = harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME]
    push_mock = MagicMock()
    monkeypatch.setattr(container, "push", push_mock)
    monkeypatch.setattr(pebble, "reconcile", MagicMock())

    harness.charm.on.config_changed.emit()

    push_mock.assert_has_calls(
        [
            call(
                f"/data/{TEST_SERVER_NAME}.signing.key",
                signing_key,
                make_dirs=True,
                encoding="utf-8",
            )
        ]
    )


def test_scaling_signing_not_found(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: charm deployed, integrated with Redis and set as main.
    act: emit config changed.
    assert: Signing key is pulled and secret is created.
    """
    harness.begin_with_initial_hooks()
    signing_key = "ed25519 a_ONyE 5YwXqh43qXKrwQa/9Vcjog66xYliBUzotClQ5SUt9tk"
    get_signing_key_mock = MagicMock(return_value=signing_key)
    monkeypatch.setattr(harness.charm, "get_signing_key", get_signing_key_mock)
    container = harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME]
    push_mock = MagicMock()
    monkeypatch.setattr(container, "push", push_mock)
    monkeypatch.setattr(pebble, "reconcile", MagicMock())

    harness.charm.on.config_changed.emit()

    push_mock.assert_has_calls(
        [
            call(
                f"/data/{TEST_SERVER_NAME}.signing.key",
                signing_key,
                make_dirs=True,
                encoding="utf-8",
            )
        ]
    )


@pytest.mark.parametrize(
    "workers_ignore_list,instance_map_content",
    [
        (
            "worker1, worker2",
            {
                "main": {
                    "host": "synapse-0.synapse-endpoints",
                    "port": 8035,
                },
                "federationsender1": {
                    "host": "synapse-0.synapse-endpoints",
                    "port": 8034,
                },
                "worker3": {
                    "host": "synapse-3.synapse-endpoints",
                    "port": 8034,
                },
                "worker4": {
                    "host": "synapse-4.synapse-endpoints",
                    "port": 8034,
                },
            },
        ),
        (
            "worker1 ,worker2",
            {
                "main": {
                    "host": "synapse-0.synapse-endpoints",
                    "port": 8035,
                },
                "federationsender1": {
                    "host": "synapse-0.synapse-endpoints",
                    "port": 8034,
                },
                "worker3": {
                    "host": "synapse-3.synapse-endpoints",
                    "port": 8034,
                },
                "worker4": {
                    "host": "synapse-4.synapse-endpoints",
                    "port": 8034,
                },
            },
        ),
        (
            " worker1,worker3 ",
            {
                "main": {
                    "host": "synapse-0.synapse-endpoints",
                    "port": 8035,
                },
                "federationsender1": {
                    "host": "synapse-0.synapse-endpoints",
                    "port": 8034,
                },
                "worker2": {
                    "host": "synapse-2.synapse-endpoints",
                    "port": 8034,
                },
                "worker4": {
                    "host": "synapse-4.synapse-endpoints",
                    "port": 8034,
                },
            },
        ),
        (
            "worker4",
            {
                "main": {
                    "host": "synapse-0.synapse-endpoints",
                    "port": 8035,
                },
                "federationsender1": {
                    "host": "synapse-0.synapse-endpoints",
                    "port": 8034,
                },
                "worker1": {
                    "host": "synapse-1.synapse-endpoints",
                    "port": 8034,
                },
                "worker2": {
                    "host": "synapse-2.synapse-endpoints",
                    "port": 8034,
                },
                "worker3": {
                    "host": "synapse-3.synapse-endpoints",
                    "port": 8034,
                },
            },
        ),
        (
            "workerfake",
            {
                "main": {
                    "host": "synapse-0.synapse-endpoints",
                    "port": 8035,
                },
                "federationsender1": {
                    "host": "synapse-0.synapse-endpoints",
                    "port": 8034,
                },
                "worker1": {
                    "host": "synapse-1.synapse-endpoints",
                    "port": 8034,
                },
                "worker2": {
                    "host": "synapse-2.synapse-endpoints",
                    "port": 8034,
                },
                "worker3": {
                    "host": "synapse-3.synapse-endpoints",
                    "port": 8034,
                },
                "worker4": {
                    "host": "synapse-4.synapse-endpoints",
                    "port": 8034,
                },
            },
        ),
    ],
)
def test_scaling_instance_map_configured_ignoring_workers(
    harness: Harness, workers_ignore_list, instance_map_content
) -> None:
    """
    arrange: charm deployed, integrated with Redis, one more unit in peer relation
        and set as leader.
    act: emit config-changed event.
    assert: Synapse charm is configured with instance_map.
    """
    rel_id = harness.add_relation(synapse.SYNAPSE_PEER_RELATION_NAME, "synapse")
    harness.add_relation_unit(rel_id, "synapse/1")
    harness.add_relation_unit(rel_id, "synapse/2")
    harness.add_relation_unit(rel_id, "synapse/3")
    harness.add_relation_unit(rel_id, "synapse/4")
    harness.begin_with_initial_hooks()
    harness.add_relation("redis", "redis", unit_data={"hostname": "redis-host", "port": "1010"})
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
                "port": 8035,
            },
            "federationsender1": {
                "host": "synapse-0.synapse-endpoints",
                "port": 8034,
            },
            "worker1": {
                "host": "synapse-1.synapse-endpoints",
                "port": 8034,
            },
            "worker2": {
                "host": "synapse-2.synapse-endpoints",
                "port": 8034,
            },
            "worker3": {
                "host": "synapse-3.synapse-endpoints",
                "port": 8034,
            },
            "worker4": {
                "host": "synapse-4.synapse-endpoints",
                "port": 8034,
            },
        }

    harness.update_config({"workers_ignore_list": workers_ignore_list})

    root = harness.get_filesystem_root(synapse.SYNAPSE_CONTAINER_NAME)
    config_path = root / synapse.SYNAPSE_CONFIG_PATH[1:]
    with open(config_path, encoding="utf-8") as config_file:
        content = yaml.safe_load(config_file)
        assert "instance_map" in content
        assert content["instance_map"] == instance_map_content
