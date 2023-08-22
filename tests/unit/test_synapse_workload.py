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
from constants import SYNAPSE_CONFIG_PATH


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


def test_enable_saml_success(harness_with_saml: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: change the configuration file.
    assert: new configuration file is pushed and SAML is enabled.
    """
    harness = harness_with_saml
    config_content = """
    listeners:
        - type: http
          port: 8080
          bind_addresses:
            - "::"
          x_forwarded: false
    """
    text_io_mock = io.StringIO(config_content)
    pull_mock = Mock(return_value=text_io_mock)
    push_mock = MagicMock()
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "pull", pull_mock)
    monkeypatch.setattr(container_mock, "push", push_mock)

    synapse.enable_saml(container_mock, harness.charm._charm_state)

    assert pull_mock.call_args[0][0] == SYNAPSE_CONFIG_PATH
    assert push_mock.call_args[0][0] == SYNAPSE_CONFIG_PATH
    saml_relation = harness.model.get_relation("saml")
    assert saml_relation
    saml_relation_data = harness.get_relation_data(saml_relation.id, "saml-integrator")
    assert saml_relation_data
    entity_id = saml_relation_data.get("entity_id")
    metadata_url = saml_relation_data.get("metadata_url")
    expected_config_content = {
        "listeners": [
            {"type": "http", "x_forwarded": True, "port": 8080, "bind_addresses": ["::"]}
        ],
        "saml2_enabled": True,
        "saml2_config": {
            "sp_config": {
                "metadata": {"remote": [{"url": metadata_url}]},
                "service": {"sp": {"entityId": "https://server-name-configured.synapse.com"}},
                "name": [entity_id, "en"],
            },
            "user_mapping_provider": {
                "config": {"mxid_source_attribute": "username", "mxid_mapping": "dotreplace"}
            },
        },
    }
    assert push_mock.call_args[0][1] == yaml.safe_dump(expected_config_content)


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
