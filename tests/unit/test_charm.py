# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm unit tests."""

# pylint: disable=protected-access

import io
import json
from unittest.mock import MagicMock

import ops
import pytest
from ops.testing import Harness

import pebble
import synapse
from charm import SynapseCharm
from pebble import PebbleServiceError

from .conftest import TEST_SERVER_NAME, TEST_SERVER_NAME_CHANGED


def test_synapse_pebble_layer(harness: Harness) -> None:
    """
    arrange: charm deployed.
    act: start the Synapse charm, set Synapse container to be ready and set server_name.
    assert: Synapse charm should submit the correct Synapse pebble layer to pebble.
    """
    harness.set_leader(True)
    harness.begin_with_initial_hooks()

    pebble_plan = harness.get_container_pebble_plan(synapse.SYNAPSE_CONTAINER_NAME).to_dict()
    synapse_layer = pebble_plan["services"][synapse.SYNAPSE_SERVICE_NAME]
    assert pebble_plan["checks"]["synapse-ready"]["period"] == "2m"
    assert pebble_plan["checks"]["synapse-ready"]["threshold"] == 5
    assert pebble_plan["checks"]["synapse-ready"]["timeout"] == "20s"
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)
    assert synapse_layer == {
        "override": "replace",
        "summary": "Synapse application service",
        "command": synapse.SYNAPSE_COMMAND_PATH,
        "environment": {
            "SYNAPSE_CONFIG_DIR": synapse.SYNAPSE_CONFIG_DIR,
            "SYNAPSE_CONFIG_PATH": synapse.SYNAPSE_CONFIG_PATH,
            "SYNAPSE_DATA_DIR": synapse.SYNAPSE_DATA_DIR,
            "SYNAPSE_NO_TLS": "True",
            "SYNAPSE_REPORT_STATS": "no",
            "SYNAPSE_SERVER_NAME": TEST_SERVER_NAME,
            "LD_PRELOAD": "/usr/lib/x86_64-linux-gnu/libjemalloc.so.2",
        },
        "startup": "enabled",
    }
    container = harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME]
    root = harness.get_filesystem_root(container)
    synapse_configuration = (root / "data" / "homeserver.yaml").read_text()
    assert f"public_baseurl: https://{TEST_SERVER_NAME}" in synapse_configuration


@pytest.mark.skip(reason="harness does not reproduce checks changes")
def test_synapse_pebble_layer_change(harness: Harness) -> None:
    """
    arrange: charm deployed.
    act: change experimental_alive_check config.
    assert: Synapse charm should submit the correct Synapse pebble layer to pebble.
    """
    harness.set_leader(True)
    harness.container_pebble_ready("synapse")
    harness.begin_with_initial_hooks()
    pebble_plan = harness.get_container_pebble_plan(synapse.SYNAPSE_CONTAINER_NAME).to_dict()
    assert pebble_plan["checks"]["synapse-ready"]["period"] == "2m"
    assert pebble_plan["checks"]["synapse-ready"]["threshold"] == 5
    assert pebble_plan["checks"]["synapse-ready"]["timeout"] == "20s"

    harness.update_config({"experimental_alive_check": "1m,3,30s"})

    pebble_plan = harness.get_container_pebble_plan(synapse.SYNAPSE_CONTAINER_NAME).to_dict()
    assert pebble_plan["checks"]["synapse-ready"]["period"] == "1m"
    assert pebble_plan["checks"]["synapse-ready"]["threshold"] == 3
    assert pebble_plan["checks"]["synapse-ready"]["timeout"] == "30s"


@pytest.mark.parametrize(
    "harness",
    [
        pytest.param(1, id="harness_exit_code"),
    ],
    indirect=True,
)
def test_synapse_migrate_config_error(harness: Harness) -> None:
    """
    arrange: charm deployed.
    act: start the Synapse charm, set Synapse container to be ready and set server_name.
    assert: Synapse charm should be blocked by error on migrate_config command.
    """
    harness.set_leader(True)
    harness.begin_with_initial_hooks()

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "Migrate config failed" in str(harness.model.unit.status)


def test_container_down() -> None:
    """
    arrange: charm deployed.
    act: start the Synapse charm, set server_name, set Synapse container to be down
        and then try to change report_stats.
    assert: Synapse charm should submit the correct status.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME})
    harness.add_relation("mas-database", "postgresql-k8s")
    harness.begin()
    harness.set_can_connect(harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME], False)

    harness.update_config({"report_stats": True})

    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
    assert "Waiting for" in str(harness.model.unit.status)
    harness.cleanup()


def test_restart_nginx_container_down(harness: Harness) -> None:
    """
    arrange: Mock container as down.
    act: start the Synapse charm, set server_name, set NGINX Synapse container to be down
        and then try to change report_stats.
    assert: Synapse charm should submit the correct status.
    """
    harness.begin()
    harness.set_can_connect(harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME], False)
    harness.update_config({"report_stats": True})
    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
    assert "Waiting for" in str(harness.model.unit.status)


def test_server_name_empty() -> None:
    """
    arrange: charm deployed.
    act: emit config-changed event.
    assert: Synapse charm waits for server_name to be set.
    """
    harness = Harness(SynapseCharm)
    harness.begin()

    harness.charm.on.config_changed.emit()

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "invalid configuration: server_name" in str(harness.model.unit.status)


def test_traefik_integration(harness: Harness) -> None:
    """
    arrange: add relation with Traefik charm.
    act: update relation with expected URL.
    assert: Relation data is as expected.
    """
    harness.set_leader(True)
    harness.begin()
    harness.container_pebble_ready(synapse.SYNAPSE_CONTAINER_NAME)
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
        "model": f'"{model_name}"',
        "name": f'"{app_name}"',
        "port": str(synapse.SYNAPSE_NGINX_PORT),
        "strip-prefix": "true",
    }


def test_smtp_integration_container_down(smtp_configured: Harness) -> None:
    """
    arrange: start the Synapse charm, set server_name, set Synapse container to be down.
    act: emit smtp_data_available.
    assert: Synapse charm should report maintenance status and waiting for pebble.
    """
    harness = smtp_configured
    harness.begin()
    harness.set_can_connect(harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME], False)
    relation = harness.charm.framework.model.get_relation("smtp", 0)

    harness.charm._smtp.smtp.on.smtp_data_available.emit(relation)

    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
    assert "Waiting for" in str(harness.model.unit.status)


def test_smtp_relation_success(smtp_configured: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: start the Synapse charm, set server_name, mock synapse.enable_smtp.
    act: emit smtp_data_available
    assert: synapse.enable_smtp is called once.
    """
    harness = smtp_configured
    enable_smtp_mock = MagicMock()
    monkeypatch.setattr(synapse, "enable_smtp", enable_smtp_mock)
    container: ops.Container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    container.push(
        synapse.SYNAPSE_CONFIG_PATH, f'server_name: "{TEST_SERVER_NAME}"', make_dirs=True
    )

    harness.begin()

    relation = harness.charm.framework.model.get_relation("smtp", 0)
    harness.charm._smtp.smtp.on.smtp_data_available.emit(relation)

    enable_smtp_mock.assert_called_once()


def test_server_name_change(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change to a different server_name.
    assert: Synapse charm should prevent the change with a BlockStatus.
    """
    harness.set_leader(True)
    harness.begin_with_initial_hooks()
    container: ops.Container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    container.push(
        synapse.SYNAPSE_CONFIG_PATH, f'server_name: "{TEST_SERVER_NAME}"', make_dirs=True
    )
    charm_state_mock = MagicMock()
    charm_state_mock.server_name = TEST_SERVER_NAME_CHANGED
    monkeypatch.setattr(
        harness.charm, "build_charm_state", MagicMock(return_value=charm_state_mock)
    )

    harness.update_config({"server_name": TEST_SERVER_NAME_CHANGED})

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "server_name modification is not allowed" in str(harness.model.unit.status)


def test_enable_federation_domain_whitelist_is_called(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready,
        set server_name and federation_domain_whitelist.
    act: call pebble reconcile.
    assert: enable_federation_domain_whitelist is called.
    """
    config_content = """  # pylint: disable=duplicate-code
    listeners:
        - type: http
          port: 8080
          bind_addresses:
            - "::"
    """
    config = io.StringIO(config_content)
    harness.update_config({"federation_domain_whitelist": "foo"})
    harness.begin()
    monkeypatch.setattr(synapse, "set_public_baseurl", MagicMock())
    monkeypatch.setattr(synapse, "execute_migrate_config", MagicMock())
    monkeypatch.setattr(synapse, "enable_metrics", MagicMock())
    monkeypatch.setattr(synapse, "enable_rc_joins_remote_rate", MagicMock())
    monkeypatch.setattr(synapse, "enable_replication", MagicMock())
    monkeypatch.setattr(synapse, "enable_forgotten_room_retention", MagicMock())
    monkeypatch.setattr(synapse, "enable_serve_server_wellknown", MagicMock())
    monkeypatch.setattr(synapse, "enable_instance_map", MagicMock())
    monkeypatch.setattr(synapse, "enable_media_retention", MagicMock())
    monkeypatch.setattr(synapse, "enable_stale_devices_deletion", MagicMock())
    monkeypatch.setattr(synapse, "validate_config", MagicMock())
    enable_federation_mock = MagicMock()
    monkeypatch.setattr(synapse, "enable_federation_domain_whitelist", enable_federation_mock)

    charm_state = harness.charm.build_charm_state()
    container = MagicMock()
    monkeypatch.setattr(container, "push", MagicMock())
    monkeypatch.setattr(container, "pull", MagicMock(return_value=config))
    pebble.reconcile(charm_state, container=container)

    enable_federation_mock.assert_called_once()


def test_disable_password_config_is_called(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready,
        set server_name and enable_password_config.
    act: call pebble reconcile.
    assert: disable_password_config is called.
    """
    harness.update_config({"enable_password_config": False})
    harness.begin()
    monkeypatch.setattr(synapse, "set_public_baseurl", MagicMock())
    monkeypatch.setattr(synapse, "execute_migrate_config", MagicMock())
    monkeypatch.setattr(synapse, "enable_metrics", MagicMock())
    monkeypatch.setattr(synapse, "enable_rc_joins_remote_rate", MagicMock())
    monkeypatch.setattr(synapse, "enable_replication", MagicMock())
    monkeypatch.setattr(synapse, "enable_forgotten_room_retention", MagicMock())
    monkeypatch.setattr(synapse, "enable_serve_server_wellknown", MagicMock())
    monkeypatch.setattr(synapse, "enable_instance_map", MagicMock())
    monkeypatch.setattr(synapse, "enable_media_retention", MagicMock())
    monkeypatch.setattr(synapse, "enable_stale_devices_deletion", MagicMock())
    monkeypatch.setattr(synapse, "validate_config", MagicMock())
    disable_password_config_mock = MagicMock()
    monkeypatch.setattr(synapse, "disable_password_config", disable_password_config_mock)

    charm_state = harness.charm.build_charm_state()
    container = MagicMock()
    monkeypatch.setattr(container, "push", MagicMock())
    monkeypatch.setattr(container, "pull", MagicMock(return_value=io.StringIO("{}")))
    pebble.reconcile(charm_state, container=container)

    disable_password_config_mock.assert_called_once()


def test_nginx_replan(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, mock restart_nginx call.
    act: fire that NGINX container is ready.
    assert: Pebble Service replan NGINX is called.
    """
    harness.begin()
    restart_nginx_mock = MagicMock()
    monkeypatch.setattr(pebble, "restart_nginx", restart_nginx_mock)

    harness.container_pebble_ready(synapse.SYNAPSE_CONTAINER_NAME)

    restart_nginx_mock.assert_called_once()


def test_nginx_replan_failure(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, mock restart_nginx call and set the NGINX container as down.
    act: fire that NGINX container is ready.
    assert: Pebble Service replan NGINX is not called.
    """
    harness.begin()
    restart_nginx_mock = MagicMock()
    monkeypatch.setattr(pebble, "restart_nginx", restart_nginx_mock)

    container = harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME]
    harness.set_can_connect(container, False)
    # harness.container_pebble_ready cannot be used as it sets the set_can_connect to True
    harness.charm.on[synapse.SYNAPSE_CONTAINER_NAME].pebble_ready.emit(container)

    restart_nginx_mock.assert_not_called()
    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)


def test_nginx_replan_sets_status_to_active(harness: Harness) -> None:
    """
    arrange: start Synapse charm with Synapse container and with pebble service ready.
    act: Fire that Pebble ready and then NGINX container ready.
    assert: Pebble Service replan NGINX is called and sets unit to Active.
    """
    harness.begin()
    harness.container_pebble_ready(synapse.SYNAPSE_CONTAINER_NAME)

    assert harness.model.unit.status == ops.ActiveStatus()


def test_redis_relation_success(redis_configured: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: start the Synapse charm, set server_name, mock synapse.enable_redis.
    act: emit redis_relation_updated
    assert: synapse.enable_redis is called once.
    """
    harness = redis_configured
    enable_redis_mock = MagicMock()
    monkeypatch.setattr(synapse, "enable_redis", enable_redis_mock)
    container: ops.Container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    container.push(
        synapse.SYNAPSE_CONFIG_PATH, f'server_name: "{TEST_SERVER_NAME}"', make_dirs=True
    )
    harness.begin()

    harness.charm.on.redis_relation_updated.emit()

    enable_redis_mock.assert_called_once()


def test_redis_configuration_success(redis_configured: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: start the Synapse charm, set server_name, mock synapse.enable_redis.
    act: emit redis_relation_updated.
    assert: get_relation_as_redis_conf works as expected.
    """
    harness = redis_configured
    enable_redis_mock = MagicMock()
    monkeypatch.setattr(synapse, "enable_redis", enable_redis_mock)

    harness.begin()

    redis_config = harness.charm._redis.get_relation_as_redis_conf()
    assert "redis-host" == redis_config["host"]
    assert "1010" == str(redis_config["port"])


def test_smtp_enabled_reconcile_pebble_error(
    smtp_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock pebble to give an error.
    act: emit smtp_data_available.
    assert: Synapse charm should submit the correct status.
    """
    harness = smtp_configured
    harness.begin()
    error_message = "Fail"
    reconcile_mock = MagicMock(side_effect=PebbleServiceError(error_message))
    monkeypatch.setattr(pebble, "reconcile", reconcile_mock)

    relation = harness.charm.framework.model.get_relation("smtp", 0)
    harness.charm._smtp.smtp.on.smtp_data_available.emit(relation)

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert error_message in str(harness.model.unit.status)


def test_redis_enabled_reconcile_pebble_error(
    redis_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock pebble to give an error.
    act: emit redis_relation_updated.
    assert: Synapse charm should submit the correct status.
    """
    harness = redis_configured
    harness.begin()
    error_message = "Fail"
    reconcile_mock = MagicMock(side_effect=PebbleServiceError(error_message))
    monkeypatch.setattr(pebble, "reconcile", reconcile_mock)

    harness.charm.on.redis_relation_updated.emit()

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert error_message in str(harness.model.unit.status)
