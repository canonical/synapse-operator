# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm unit tests."""

# pylint: disable=protected-access

import json
from unittest.mock import MagicMock

import ops
import pytest
from ops.testing import Harness
import synapse
from charm import SynapseCharm

from constants import (
    SYNAPSE_COMMAND_PATH,
    SYNAPSE_CONTAINER_NAME,
    SYNAPSE_NGINX_CONTAINER_NAME,
    SYNAPSE_NGINX_PORT,
    SYNAPSE_SERVICE_NAME,
    TEST_SERVER_NAME,
    TEST_SERVER_NAME_CHANGED,
    SYNAPSE_CONFIG_PATH,
)
from pebble import PebbleServiceError


def test_synapse_pebble_layer(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: charm deployed.
    act: start the Synapse charm, set Synapse container to be ready and set server_name.
    assert: Synapse charm should submit the correct Synapse pebble layer to pebble.
    """
    monkeypatch.setattr(synapse, "get_version", lambda *_args, **_kwargs: "")
    harness.update_config({"server_name": TEST_SERVER_NAME})

    harness.begin_with_initial_hooks()

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


@pytest.mark.parametrize(
    "harness",
    [
        pytest.param(1, id="harness_exit_code"),
    ],
    indirect=True,
)
def test_synapse_migrate_config_error(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: charm deployed.
    act: start the Synapse charm, set Synapse container to be ready and set server_name.
    assert: Synapse charm should be blocked by error on migrate_config command.
    """
    monkeypatch.setattr(synapse, "get_version", lambda *_args, **_kwargs: "")
    harness.update_config({"server_name": TEST_SERVER_NAME})

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
    harness.set_can_connect(harness.model.unit.containers[SYNAPSE_CONTAINER_NAME], False)

    harness.update_config({"report_stats": True})

    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
    assert "Waiting for" in str(harness.model.unit.status)
    harness.cleanup()


def test_replan_nginx_container_down(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: Mock container as down.
    act: start the Synapse charm, set server_name, set NGINX Synapse container to be down
        and then try to change report_stats.
    assert: Synapse charm should submit the correct status.
    """
    monkeypatch.setattr(synapse, "get_version", lambda *_args, **_kwargs: "")
    harness.update_config({"server_name": TEST_SERVER_NAME})
    harness.begin()
    harness.set_can_connect(harness.model.unit.containers[SYNAPSE_NGINX_CONTAINER_NAME], False)
    harness.update_config({"report_stats": True})
    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
    assert "Waiting for" in str(harness.model.unit.status)


def test_server_name_empty(harness: Harness) -> None:
    """
    arrange: charm deployed.
    act: start the Synapse charm and set Synapse container to be ready.
    assert: Synapse charm waits for server_name to be set.
    """
    harness.begin()
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "invalid configuration: server_name" in str(harness.model.unit.status)


def test_traefik_integration(harness: Harness) -> None:
    """
    arrange: add relation with Traefik charm.
    act: update relation with expected URL.
    assert: Relation data is as expected.
    """
    harness.update_config({"server_name": TEST_SERVER_NAME})
    harness.begin()
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
        "port": str(SYNAPSE_NGINX_PORT),
        "strip-prefix": "true",
    }


def test_saml_integration_container_restart(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock container and enable_saml.
    act: enable saml via pebble_service as the observer does.
    assert: The container is restarted.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME})
    harness.begin()
    monkeypatch.setattr("synapse.enable_saml", MagicMock)
    container = MagicMock()
    container_restart = MagicMock()
    monkeypatch.setattr(container, "restart", container_restart)

    harness.charm.pebble_service.enable_saml(container)

    container_restart.assert_called_once()
    harness.cleanup()


def test_saml_integration_container_down() -> None:
    """
    arrange: start the Synapse charm, set server_name, set Synapse container to be down.
    act: emit saml_data_available.
    assert: Synapse charm should submit the correct status.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME, "public_baseurl": TEST_SERVER_NAME})
    relation_id = harness.add_relation("saml", "saml-integrator")
    harness.add_relation_unit(relation_id, "saml-integrator/0")
    metadata_url = "https://login.staging.ubuntu.com/saml/metadata"
    harness.update_relation_data(
        relation_id,
        "saml-integrator",
        {
            "entity_id": "https://login.staging.ubuntu.com",
            "metadata_url": metadata_url,
        },
    )
    harness.set_can_connect(SYNAPSE_CONTAINER_NAME, True)
    harness.begin()
    harness.set_leader(True)
    harness.set_can_connect(harness.model.unit.containers[SYNAPSE_CONTAINER_NAME], False)
    relation = harness.charm.framework.model.get_relation("saml", 0)

    harness.charm.saml.saml.on.saml_data_available.emit(relation)

    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
    assert "Waiting for" in str(harness.model.unit.status)
    harness.cleanup()


def test_saml_integration_pebble_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set server_name, mock pebble to give an error.
    act: emit saml_data_available.
    assert: Synapse charm should submit the correct status.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME, "public_baseurl": TEST_SERVER_NAME})
    relation_id = harness.add_relation("saml", "saml-integrator")
    harness.add_relation_unit(relation_id, "saml-integrator/0")
    metadata_url = "https://login.staging.ubuntu.com/saml/metadata"
    harness.update_relation_data(
        relation_id,
        "saml-integrator",
        {
            "entity_id": "https://login.staging.ubuntu.com",
            "metadata_url": metadata_url,
        },
    )
    harness.set_can_connect(SYNAPSE_CONTAINER_NAME, True)
    harness.begin()
    harness.set_leader(True)
    relation = harness.charm.framework.model.get_relation("saml", 0)
    enable_saml_mock = MagicMock(side_effect=PebbleServiceError("fail"))
    monkeypatch.setattr(harness.charm.saml._pebble_service, "enable_saml", enable_saml_mock)

    harness.charm.saml.saml.on.saml_data_available.emit(relation)

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "SAML integration failed" in str(harness.model.unit.status)
    harness.cleanup()


def test_server_name_change(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: change to a different server_name.
    assert: Synapse charm should prevent the change with a BlockStatus.
    """
    monkeypatch.setattr(synapse, "get_version", lambda *_args, **_kwargs: "")
    harness.update_config({"server_name": TEST_SERVER_NAME})
    harness.begin()
    container: ops.Container = harness.model.unit.get_container(SYNAPSE_CONTAINER_NAME)
    container.push(SYNAPSE_CONFIG_PATH, f'server_name: "{TEST_SERVER_NAME}"', make_dirs=True)
    charm_state_mock = MagicMock()
    charm_state_mock.server_name = TEST_SERVER_NAME_CHANGED
    monkeypatch.setattr(harness.charm.pebble_service, "_charm_state", charm_state_mock)

    harness.update_config({"server_name": TEST_SERVER_NAME})

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert "server_name modification is not allowed" in str(harness.model.unit.status)
