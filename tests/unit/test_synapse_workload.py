# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse workload unit tests."""

# pylint: disable=protected-access

import io
from unittest.mock import MagicMock, Mock

import ops
import pytest
import yaml
from ops.testing import Harness

import synapse
from charm import SynapseCharm
from constants import SYNAPSE_CONFIG_PATH, SYNAPSE_CONTAINER_NAME, TEST_SERVER_NAME


def test_enable_metrics_success(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: change the configuration file.
    assert: new configuration file is pushed and metrics are enabled.
    """
    config_content = """
    listeners:
        - type: http
          port: 8080
          bind_addresses:
            - "::"
    """
    text_io_mock = io.StringIO(config_content)
    pull_mock = Mock(return_value=text_io_mock)
    push_mock = MagicMock()
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "pull", pull_mock)
    monkeypatch.setattr(container_mock, "push", push_mock)

    synapse.enable_metrics(container_mock)

    assert pull_mock.call_args[0][0] == SYNAPSE_CONFIG_PATH
    assert push_mock.call_args[0][0] == SYNAPSE_CONFIG_PATH
    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
            {"port": 9000, "type": "metrics", "bind_addresses": ["::"]},
        ],
        "enable_metrics": True,
    }
    assert push_mock.call_args[0][1] == yaml.safe_dump(expected_config_content)


def test_enable_metrics_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: change the configuration file.
    assert: raise WorkloadError in case of error.
    """
    error_message = "Error pulling file"
    path_error = ops.pebble.PathError(kind="fake", message=error_message)
    pull_mock = MagicMock(side_effect=path_error)
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "pull", pull_mock)

    with pytest.raises(synapse.WorkloadError, match=error_message):
        synapse.enable_metrics(container_mock)


def test_enable_saml_success():
    """
    arrange: set mock container with file.
    act: change the configuration file.
    assert: new configuration file is pushed and SAML is enabled.
    """
    # This test was given as an example in this comment by Ben Hoyt.
    # https://github.com/canonical/synapse-operator/pull/19#discussion_r1302486670
    # Arrange: set up harness and container filesystem
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME})
    relation_id = harness.add_relation("saml", "saml-integrator")
    harness.add_relation_unit(relation_id, "saml-integrator/0")
    harness.update_relation_data(
        relation_id,
        "saml-integrator",
        {
            "entity_id": "https://login.staging.ubuntu.com",
            "metadata_url": "https://login.staging.ubuntu.com/saml/metadata",
        },
    )
    harness.set_can_connect(SYNAPSE_CONTAINER_NAME, True)
    harness.begin()
    root = harness.get_filesystem_root(SYNAPSE_CONTAINER_NAME)
    config_path = root / SYNAPSE_CONFIG_PATH[1:]
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        """
listeners:
    - type: http
      port: 8080
      bind_addresses:
        - "::"
      x_forwarded: false
"""
    )

    # Act: write the Synapse config file with SAML enabled
    container = harness.model.unit.get_container(SYNAPSE_CONTAINER_NAME)
    synapse.enable_saml(container, harness.charm._charm_state)

    # Assert: ensure config file was written correctly
    expected_config_content = {
        "listeners": [
            {"type": "http", "x_forwarded": True, "port": 8080, "bind_addresses": ["::"]}
        ],
        "saml2_enabled": True,
        "saml2_config": {
            "sp_config": {
                "metadata": {
                    "remote": [{"url": "https://login.staging.ubuntu.com/saml/metadata"}]
                },
                "service": {"sp": {"entityId": "https://server-name-configured.synapse.com"}},
                "name": ["https://login.staging.ubuntu.com", "en"],
            },
            "user_mapping_provider": {
                "config": {"mxid_source_attribute": "username", "mxid_mapping": "dotreplace"}
            },
        },
    }
    assert config_path.read_text() == yaml.safe_dump(expected_config_content)


def test_enable_saml_error(harness_with_saml: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: change the configuration file.
    assert: raise WorkloadError in case of error.
    """
    harness = harness_with_saml
    error_message = "Error pulling file"
    path_error = ops.pebble.PathError(kind="fake", message=error_message)
    pull_mock = MagicMock(side_effect=path_error)
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "pull", pull_mock)

    with pytest.raises(synapse.WorkloadError, match=error_message):
        synapse.enable_saml(container_mock, harness.charm._charm_state)
