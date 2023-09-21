# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse workload unit tests."""

# pylint: disable=protected-access


import io
from secrets import token_hex
from unittest.mock import MagicMock, Mock

import ops
import pytest
import yaml
from ops.testing import Harness

import synapse
from constants import MJOLNIR_CONFIG_PATH, SYNAPSE_CONFIG_PATH, SYNAPSE_CONTAINER_NAME
from tests.constants import TEST_SERVER_NAME


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


def test_enable_saml_success(harness_with_saml: Harness):
    """
    arrange: set mock container with file.
    act: change the configuration file.
    assert: new configuration file is pushed and SAML is enabled.
    """
    # This test was given as an example in this comment by Ben Hoyt.
    # https://github.com/canonical/synapse-operator/pull/19#discussion_r1302486670
    harness = harness_with_saml
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
    saml_relation = harness.model.relations["saml"][0]
    saml_relation_data = harness.get_relation_data(saml_relation.id, "saml-integrator")
    expected_config_content = {
        "listeners": [
            {"type": "http", "x_forwarded": True, "port": 8080, "bind_addresses": ["::"]}
        ],
        "public_baseurl": TEST_SERVER_NAME,
        "saml2_enabled": True,
        "saml2_config": {
            "sp_config": {
                "metadata": {"remote": [{"url": saml_relation_data.get("metadata_url")}]},
                "service": {
                    "sp": {
                        "entityId": TEST_SERVER_NAME,
                        "allow_unsolicited": True,
                    }
                },
                "allow_unknown_attributes": True,
                "attribute_map_dir": "/usr/local/attributemaps",
            },
            "user_mapping_provider": {
                "config": {
                    "grandfathered_mxid_source_attribute": "uid",
                    "mxid_source_attribute": "uid",
                    "mxid_mapping": "dotreplace",
                }
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
    harness.begin()
    error_message = "Error pulling file"
    path_error = ops.pebble.PathError(kind="fake", message=error_message)
    pull_mock = MagicMock(side_effect=path_error)
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "pull", pull_mock)

    with pytest.raises(synapse.WorkloadError, match=error_message):
        synapse.enable_saml(container_mock, harness.charm._charm_state)


def test_get_mjolnir_config_success():
    """
    arrange: set access token and room id parameters.
    act: call _get_mjolnir_config.
    assert: config returns as expected.
    """
    access_token = token_hex(16)
    room_id = token_hex(16)

    config = synapse.workload._get_mjolnir_config(access_token=access_token, room_id=room_id)

    assert config["accessToken"] == access_token
    assert config["managementRoom"] == room_id


def test_create_mjolnir_config_success(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set container, access token and room id parameters.
    act: call create_mjolnir_config.
    assert: file is pushed as expected.
    """
    access_token = token_hex(16)
    room_id = token_hex(16)
    push_mock = MagicMock()
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "push", push_mock)

    synapse.create_mjolnir_config(
        container=container_mock, access_token=access_token, room_id=room_id
    )

    expected_config = synapse.workload._get_mjolnir_config(
        access_token=access_token, room_id=room_id
    )
    push_mock.assert_called_once_with(
        MJOLNIR_CONFIG_PATH, yaml.safe_dump(expected_config), make_dirs=True
    )
