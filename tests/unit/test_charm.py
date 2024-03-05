# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm unit tests."""

# pylint: disable=protected-access

import json
from unittest import skip
from unittest.mock import ANY, MagicMock

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
    harness.begin_with_initial_hooks()

    synapse_layer = harness.get_container_pebble_plan(synapse.SYNAPSE_CONTAINER_NAME).to_dict()[
        "services"
    ][synapse.SYNAPSE_SERVICE_NAME]
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
        },
        "startup": "enabled",
    }


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
    harness.begin()
    harness.set_can_connect(harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME], False)

    harness.update_config({"report_stats": True})

    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
    assert "Waiting for" in str(harness.model.unit.status)
    harness.cleanup()


def test_replan_nginx_container_down(harness: Harness) -> None:
    """
    arrange: Mock container as down.
    act: start the Synapse charm, set server_name, set NGINX Synapse container to be down
        and then try to change report_stats.
    assert: Synapse charm should submit the correct status.
    """
    harness.begin()
    harness.set_can_connect(
        harness.model.unit.containers[synapse.SYNAPSE_NGINX_CONTAINER_NAME], False
    )
    harness.update_config({"report_stats": True})
    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
    assert "Waiting for" in str(harness.model.unit.status)


def test_server_name_empty() -> None:
    """
    arrange: charm deployed.
    act: start the Synapse charm and set Synapse container to be ready.
    assert: Synapse charm waits for server_name to be set.
    """
    harness = Harness(SynapseCharm)

    harness.begin_with_initial_hooks()

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "invalid configuration: server_name" in str(harness.model.unit.status)


def test_traefik_integration(harness: Harness) -> None:
    """
    arrange: add relation with Traefik charm.
    act: update relation with expected URL.
    assert: Relation data is as expected.
    """
    harness.begin()
    harness.set_leader(True)
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
        "host": f"{app_name}-endpoints.{model_name}.svc.cluster.local",
        "model": model_name,
        "name": app_name,
        "port": str(synapse.SYNAPSE_NGINX_PORT),
        "strip-prefix": "true",
    }


def test_saml_integration_container_down(saml_configured: Harness) -> None:
    """
    arrange: start the Synapse charm, set server_name, set Synapse container to be down.
    act: emit saml_data_available.
    assert: Synapse charm should submit the correct status.
    """
    harness = saml_configured
    harness.begin()
    harness.set_can_connect(harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME], False)
    relation = harness.charm.framework.model.get_relation("saml", 0)

    harness.charm._saml.saml.on.saml_data_available.emit(relation)

    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
    assert "Waiting for" in str(harness.model.unit.status)
    harness.cleanup()


def test_saml_integration_pebble_success(
    saml_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock synapse.enable_saml.
    act: call enable_saml from pebble_service.
    assert: synapse.enable_saml is called once.
    """
    harness = saml_configured
    harness.begin()
    container = harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME]
    enable_saml_mock = MagicMock()
    monkeypatch.setattr(synapse, "enable_saml", enable_saml_mock)

    charm_state = harness.charm.build_charm_state()
    pebble.enable_saml(charm_state, container=container)

    enable_saml_mock.assert_called_once_with(
        container=container, charm_state=harness.charm.build_charm_state()
    )


def test_saml_integration_pebble_error(
    saml_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock pebble to give an error.
    act: emit saml_data_available.
    assert: Synapse charm should submit the correct status.
    """
    harness = saml_configured
    harness.begin()

    relation = harness.charm.framework.model.get_relation("saml", 0)
    enable_saml_mock = MagicMock(side_effect=PebbleServiceError("fail"))
    monkeypatch.setattr(pebble, "enable_saml", enable_saml_mock)

    harness.charm._saml.saml.on.saml_data_available.emit(relation)

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "SAML integration failed" in str(harness.model.unit.status)
    harness.cleanup()


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


def test_smtp_relation_pebble_success(smtp_configured: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: start the Synapse charm, set server_name, mock synapse.enable_smtp.
    act: emit smtp_data_available
    assert: synapse.enable_smtp is called once and unit is active.
    """
    harness = smtp_configured
    enable_smtp_mock = MagicMock()
    container = harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME]
    monkeypatch.setattr(synapse, "enable_smtp", enable_smtp_mock)

    harness.begin()

    relation = harness.charm.framework.model.get_relation("smtp", 0)
    harness.charm._smtp.smtp.on.smtp_data_available.emit(relation)

    enable_smtp_mock.assert_called_once_with(
        container=container, charm_state=harness.charm.build_charm_state()
    )
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


def test_smtp_relation_pebble_error(smtp_configured: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: start the Synapse charm, set server_name, mock pebble to give an error.
    act: emit smtp_data_available.
    assert: Synapse charm should submit the correct status (blocked).
    """
    harness = smtp_configured
    harness.begin()

    enable_smtp_mock = MagicMock(side_effect=PebbleServiceError("fail"))
    monkeypatch.setattr(pebble, "enable_smtp", enable_smtp_mock)

    relation = harness.charm.framework.model.get_relation("smtp", 0)
    harness.charm._smtp.smtp.on.smtp_data_available.emit(relation)

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "SMTP integration failed" in str(harness.model.unit.status)


def test_server_name_change(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change to a different server_name.
    assert: Synapse charm should prevent the change with a BlockStatus.
    """
    harness.begin()
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
    act: call pebble change_config.
    assert: enable_federation_domain_whitelist is called.
    """
    harness.update_config({"federation_domain_whitelist": "foo"})
    harness.begin()
    harness.set_leader(True)
    monkeypatch.setattr(synapse, "execute_migrate_config", MagicMock())
    monkeypatch.setattr(synapse, "enable_metrics", MagicMock())
    monkeypatch.setattr(synapse, "enable_forgotten_room_retention", MagicMock())
    monkeypatch.setattr(synapse, "enable_serve_server_wellknown", MagicMock())
    monkeypatch.setattr(synapse, "validate_config", MagicMock())
    enable_federation_mock = MagicMock()
    monkeypatch.setattr(synapse, "enable_federation_domain_whitelist", enable_federation_mock)

    charm_state = harness.charm.build_charm_state()
    pebble.change_config(charm_state, container=MagicMock())

    enable_federation_mock.assert_called_once()


def test_disable_password_config_is_called(
    harness: Harness,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready,
        set server_name and enable_password_config.
    act: call pebble change_config.
    assert: disable_password_config is called.
    """
    harness.update_config({"enable_password_config": False})
    harness.begin()
    harness.set_leader(True)
    monkeypatch.setattr(synapse, "execute_migrate_config", MagicMock())
    monkeypatch.setattr(synapse, "enable_metrics", MagicMock())
    monkeypatch.setattr(synapse, "enable_forgotten_room_retention", MagicMock())
    monkeypatch.setattr(synapse, "enable_serve_server_wellknown", MagicMock())
    monkeypatch.setattr(synapse, "validate_config", MagicMock())
    disable_password_config_mock = MagicMock()
    monkeypatch.setattr(synapse, "disable_password_config", disable_password_config_mock)

    charm_state = harness.charm.build_charm_state()
    pebble.change_config(charm_state, container=MagicMock())

    disable_password_config_mock.assert_called_once()


def test_nginx_replan(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, mock replan_nginx call.
    act: fire that NGINX container is ready.
    assert: Pebble Service replan NGINX is called.
    """
    harness.begin()
    replan_nginx_mock = MagicMock()
    monkeypatch.setattr(pebble, "replan_nginx", replan_nginx_mock)

    harness.container_pebble_ready(synapse.SYNAPSE_CONTAINER_NAME)
    harness.container_pebble_ready(synapse.SYNAPSE_NGINX_CONTAINER_NAME)

    replan_nginx_mock.assert_called_once()


def test_nginx_replan_failure(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, mock replan_nginx call and set the NGINX container as down.
    act: fire that NGINX container is ready.
    assert: Pebble Service replan NGINX is not called.
    """
    harness.begin()
    replan_nginx_mock = MagicMock()
    monkeypatch.setattr(pebble, "replan_nginx", replan_nginx_mock)

    container = harness.model.unit.containers[synapse.SYNAPSE_NGINX_CONTAINER_NAME]
    harness.set_can_connect(container, False)
    # harness.container_pebble_ready cannot be used as it sets the set_can_connect to True
    harness.charm.on[synapse.SYNAPSE_NGINX_CONTAINER_NAME].pebble_ready.emit(container)

    replan_nginx_mock.assert_not_called()
    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)


def test_nginx_replan_sets_status_to_active(harness: Harness) -> None:
    """
    arrange: start Synapse charm with Synapse container and with pebble service ready.
    act: Fire that Pebble ready and then NGINX container ready.
    assert: Pebble Service replan NGINX is called and sets unit to Active.
    """
    harness.begin()
    harness.container_pebble_ready(synapse.SYNAPSE_CONTAINER_NAME)

    harness.container_pebble_ready(synapse.SYNAPSE_NGINX_CONTAINER_NAME)

    assert harness.model.unit.status == ops.ActiveStatus()


def test_nginx_replan_with_synapse_container_down(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start Synapse charm with Synapse container as down, and mock replan_nginx.
    act: Fire that NGINX container is ready.
    assert: Pebble Service replan NGINX is called but unit is in maintenance
        waiting for Synapse pebble.
    """
    harness.begin()
    replan_nginx_mock = MagicMock()
    monkeypatch.setattr(pebble, "replan_nginx", replan_nginx_mock)

    container = harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME]
    harness.set_can_connect(container, False)

    harness.container_pebble_ready(synapse.SYNAPSE_NGINX_CONTAINER_NAME)

    replan_nginx_mock.assert_called_once()
    assert harness.model.unit.status == ops.MaintenanceStatus("Waiting for Synapse pebble")


def test_nginx_replan_with_synapse_service_not_existing(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start Synapse charm with Synapse container but without synapse service,
        and mock replan_nginx.
    act: Fire that NGINX container is ready.
    assert: Pebble Service replan NGINX is called but unit is in maintenance waiting for Synapse.
    """
    harness.begin()
    replan_nginx_mock = MagicMock()
    monkeypatch.setattr(pebble, "replan_nginx", replan_nginx_mock)

    harness.container_pebble_ready(synapse.SYNAPSE_NGINX_CONTAINER_NAME)

    replan_nginx_mock.assert_called_once()
    assert harness.model.unit.status == ops.MaintenanceStatus("Waiting for Synapse")

@skip
def test_synapse_stats_exporter_pebble_layer(harness: Harness) -> None:
    """
    arrange: charm deployed.
    act: emit update status event.
    assert: Synapse charm should submit the correct Synapse Stats Exporter pebble layer to pebble.
    """
    harness.begin_with_initial_hooks()

    harness.charm.on.update_status.emit()

    synapse_layer = harness.get_container_pebble_plan(synapse.SYNAPSE_CONTAINER_NAME).to_dict()[
        "services"
    ][synapse.STATS_EXPORTER_SERVICE_NAME]
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)
    assert synapse_layer == {
        "override": "replace",
        "summary": "Synapse Stats Exporter service",
        "command": "synapse-stats-exporter",
        "startup": "enabled",
        "environment": {
            "PROM_SYNAPSE_ADMIN_TOKEN": ANY,
            "PROM_SYNAPSE_BASE_URL": "http://localhost:8008/",
        },
        "on-failure": "ignore",
    }


def test_redis_relation_pebble_success(redis_configured: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: start the Synapse charm, set server_name, mock synapse.enable_redis.
    act: emit redis_relation_updated
    assert: synapse.enable_redis is called once and unit is active.
    """
    harness = redis_configured
    enable_redis_mock = MagicMock()
    monkeypatch.setattr(synapse, "enable_redis", enable_redis_mock)
    harness.begin()

    harness.charm.on.redis_relation_updated.emit()

    enable_redis_mock.assert_called_once()
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


def test_redis_relation_pebble_error(redis_configured: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: start the Synapse charm, set server_name, mock pebble to give an error.
    act: emit redis_relation_updated.
    assert: Synapse charm should submit the correct status (blocked).
    """
    harness = redis_configured
    harness.begin()

    enable_redis_mock = MagicMock(side_effect=PebbleServiceError("fail"))
    monkeypatch.setattr(pebble, "enable_redis", enable_redis_mock)

    harness.charm.on.redis_relation_updated.emit()

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "Redis integration failed" in str(harness.model.unit.status)


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
    relation = harness.charm.framework.model.get_relation("redis", 0)
    # We need to bypass protected access to inject the relation data
    # pylint: disable=protected-access
    harness.charm._redis._stored.redis_relation = {
        relation.id: ({"hostname": "redis-host", "port": 1010})
    }

    redis_config = harness.charm._redis.get_relation_as_redis_conf()
    assert relation.data[relation.app]["hostname"] == redis_config["host"]
    assert relation.data[relation.app]["port"] == str(redis_config["port"])
