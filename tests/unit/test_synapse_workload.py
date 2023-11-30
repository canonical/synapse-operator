# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse workload unit tests."""

# pylint: disable=protected-access


import io
import typing
from secrets import token_hex
from unittest.mock import MagicMock, Mock

import ops
import pytest
import yaml
from ops.testing import Harness

import synapse
from charm import SynapseCharm

from .conftest import TEST_SERVER_NAME


def test_enable_ip_range_whitelist_success(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: update ip_range_whitelist config and call enable_ip_range_whitelist.
    assert: new configuration file is pushed and ip_range_whitelist is enabled.
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

    expected_first_domain = "foo1"
    expected_second_domain = "foo2"
    harness.update_config(
        {"ip_range_whitelist": f"{expected_first_domain},{expected_second_domain}"}
    )
    harness.begin()
    synapse.enable_ip_range_whitelist(container_mock, harness.charm._charm_state)

    assert pull_mock.call_args[0][0] == synapse.SYNAPSE_CONFIG_PATH
    assert push_mock.call_args[0][0] == synapse.SYNAPSE_CONFIG_PATH
    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "ip_range_whitelist": [expected_first_domain, expected_second_domain],
    }
    assert push_mock.call_args[0][1] == yaml.safe_dump(expected_config_content)


def test_enable_ip_range_whitelist_error(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: update ip_range_whitelist config and call enable_smtp.
    assert: raise WorkloadError in case of error.
    """
    error_message = "Error pulling file"
    path_error = ops.pebble.PathError(kind="fake", message=error_message)
    pull_mock = MagicMock(side_effect=path_error)
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "pull", pull_mock)

    with pytest.raises(synapse.WorkloadError, match=error_message):
        expected_first_domain = "foo1"
        expected_second_domain = "foo2"
        harness.update_config(
            {"ip_range_whitelist": f"{expected_first_domain},{expected_second_domain}"}
        )
        harness.begin()
        synapse.enable_ip_range_whitelist(container_mock, harness.charm._charm_state)


def test_enable_federation_domain_whitelist_success(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: set mock container with file.
    act: update federation_domain_whitelist config and call enable_federation_domain_whitelist.
    assert: new configuration file is pushed and federation_domain_whitelist is enabled.
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

    expected_first_domain = "foo1"
    expected_second_domain = "foo2"
    harness.update_config(
        {"federation_domain_whitelist": f"{expected_first_domain},{expected_second_domain}"}
    )
    harness.begin()
    synapse.enable_federation_domain_whitelist(container_mock, harness.charm._charm_state)

    assert pull_mock.call_args[0][0] == synapse.SYNAPSE_CONFIG_PATH
    assert push_mock.call_args[0][0] == synapse.SYNAPSE_CONFIG_PATH
    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "federation_domain_whitelist": [expected_first_domain, expected_second_domain],
    }
    assert push_mock.call_args[0][1] == yaml.safe_dump(expected_config_content)


def test_enable_federation_domain_whitelist_error(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: set mock container with file.
    act: update federation_domain_whitelist config and call enable_smtp.
    assert: raise WorkloadError in case of error.
    """
    error_message = "Error pulling file"
    path_error = ops.pebble.PathError(kind="fake", message=error_message)
    pull_mock = MagicMock(side_effect=path_error)
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "pull", pull_mock)

    with pytest.raises(synapse.WorkloadError, match=error_message):
        expected_first_domain = "foo1"
        expected_second_domain = "foo2"
        harness.update_config(
            {"federation_domain_whitelist": f"{expected_first_domain},{expected_second_domain}"}
        )
        harness.begin()
        synapse.enable_federation_domain_whitelist(container_mock, harness.charm._charm_state)


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

    assert pull_mock.call_args[0][0] == synapse.SYNAPSE_CONFIG_PATH
    assert push_mock.call_args[0][0] == synapse.SYNAPSE_CONFIG_PATH
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
    harness.set_can_connect(synapse.SYNAPSE_CONTAINER_NAME, True)
    harness.begin()
    root = harness.get_filesystem_root(synapse.SYNAPSE_CONTAINER_NAME)
    config_path = root / synapse.SYNAPSE_CONFIG_PATH[1:]
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
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    synapse.enable_saml(container, harness.charm._charm_state)

    # Assert: ensure config file was written correctly
    expected_config_content = {
        "listeners": [
            {"type": "http", "x_forwarded": True, "port": 8080, "bind_addresses": ["::"]}
        ],
        "public_baseurl": TEST_SERVER_NAME,
        "saml2_enabled": True,
        "saml2_config": {
            "sp_config": {
                "metadata": {"remote": [{"url": metadata_url}]},
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


def test_enable_saml_success_no_ubuntu_url():
    """
    arrange: set configuration and saml-integrator relation without ubuntu.com
        in metadata_url.
    act: enable saml.
    assert: SAML configuration is created as expected.
    """
    # Arrange: set up harness and container filesystem
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME, "public_baseurl": TEST_SERVER_NAME})
    relation_id = harness.add_relation("saml", "saml-integrator")
    harness.add_relation_unit(relation_id, "saml-integrator/0")
    metadata_url = "https://login.staging.com/saml/metadata"
    harness.update_relation_data(
        relation_id,
        "saml-integrator",
        {
            "entity_id": "https://login.staging.com",
            "metadata_url": metadata_url,
        },
    )
    harness.set_can_connect(synapse.SYNAPSE_CONTAINER_NAME, True)
    harness.begin()
    root = harness.get_filesystem_root(synapse.SYNAPSE_CONTAINER_NAME)
    config_path = root / synapse.SYNAPSE_CONFIG_PATH[1:]
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
    container = harness.model.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
    synapse.enable_saml(container, harness.charm._charm_state)

    # Assert: ensure config file was written correctly
    expected_config_content = {
        "listeners": [
            {"type": "http", "x_forwarded": True, "port": 8080, "bind_addresses": ["::"]}
        ],
        "public_baseurl": TEST_SERVER_NAME,
        "saml2_enabled": True,
        "saml2_config": {
            "sp_config": {
                "metadata": {"remote": [{"url": metadata_url}]},
                "service": {
                    "sp": {
                        "entityId": TEST_SERVER_NAME,
                        "allow_unsolicited": True,
                    }
                },
                "allow_unknown_attributes": True,
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


def test_enable_saml_error(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: change the configuration file.
    assert: raise WorkloadError in case of error.
    """
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
        synapse.MJOLNIR_CONFIG_PATH, yaml.safe_dump(expected_config), make_dirs=True
    )


def test_enable_smtp_success(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: update smtp_host config and call enable_smtp.
    assert: new configuration file is pushed and SMTP is enabled.
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

    expected_smtp_host = "127.0.0.1"
    harness.update_config({"smtp_host": expected_smtp_host})
    harness.begin()
    synapse.enable_smtp(container_mock, harness.charm._charm_state)

    assert pull_mock.call_args[0][0] == synapse.SYNAPSE_CONFIG_PATH
    assert push_mock.call_args[0][0] == synapse.SYNAPSE_CONFIG_PATH
    server_name = harness.charm._charm_state.synapse_config.server_name
    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "email": {"notif_from": server_name, "smtp_host": expected_smtp_host, "smtp_port": 25},
    }
    assert push_mock.call_args[0][1] == yaml.safe_dump(expected_config_content)


def test_enable_smtp_error(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: update smtp_host config and call enable_smtp.
    assert: raise WorkloadError in case of error.
    """
    error_message = "Error pulling file"
    path_error = ops.pebble.PathError(kind="fake", message=error_message)
    pull_mock = MagicMock(side_effect=path_error)
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "pull", pull_mock)

    with pytest.raises(synapse.WorkloadError, match=error_message):
        expected_smtp_host = "127.0.0.1"
        harness.update_config({"smtp_host": expected_smtp_host})
        harness.begin()
        synapse.enable_smtp(container_mock, harness.charm._charm_state)


def test_enable_serve_server_wellknown_success(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: update smtp_host config and call enable_serve_server_wellknown.
    assert: new configuration file is pushed and serve_server_wellknown is enabled.
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

    synapse.enable_serve_server_wellknown(container_mock)

    assert pull_mock.call_args[0][0] == synapse.SYNAPSE_CONFIG_PATH
    assert push_mock.call_args[0][0] == synapse.SYNAPSE_CONFIG_PATH
    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "serve_server_wellknown": True,
    }
    assert push_mock.call_args[0][1] == yaml.safe_dump(expected_config_content)


def test_enable_serve_server_wellknown_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: call enable_serve_server_wellknown.
    assert: raise WorkloadError.
    """
    error_message = "Error pulling file"
    path_error = ops.pebble.PathError(kind="fake", message=error_message)
    pull_mock = MagicMock(side_effect=path_error)
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "pull", pull_mock)

    with pytest.raises(synapse.WorkloadError, match=error_message):
        synapse.enable_serve_server_wellknown(container_mock)


def test_disable_password_config_success(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: call disable_password_config.
    assert: new configuration file is pushed and password_config is disabled.
    """
    config_content = """
    password_config:
        enabled: true
    """
    text_io_mock = io.StringIO(config_content)
    pull_mock = Mock(return_value=text_io_mock)
    push_mock = MagicMock()
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "pull", pull_mock)
    monkeypatch.setattr(container_mock, "push", push_mock)

    synapse.disable_password_config(container_mock)

    assert pull_mock.call_args[0][0] == synapse.SYNAPSE_CONFIG_PATH
    assert push_mock.call_args[0][0] == synapse.SYNAPSE_CONFIG_PATH
    expected_config_content = {
        "password_config": {
            "enabled": False,
        },
    }
    assert push_mock.call_args[0][1] == yaml.safe_dump(expected_config_content)


def test_disable_password_config_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: call disable_password_config.
    assert: raise WorkloadError.
    """
    error_message = "Error pulling file"
    path_error = ops.pebble.PathError(kind="fake", message=error_message)
    pull_mock = MagicMock(side_effect=path_error)
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "pull", pull_mock)

    with pytest.raises(synapse.WorkloadError, match=error_message):
        synapse.disable_password_config(container_mock)


def test_get_registration_shared_secret_success(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: call get_registration_shared_secret.
    assert: registration_shared_secret is returned.
    """
    expected_secret = token_hex(16)
    config_content = f"registration_shared_secret: {expected_secret}"
    text_io_mock = io.StringIO(config_content)
    pull_mock = Mock(return_value=text_io_mock)
    push_mock = MagicMock()
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "pull", pull_mock)
    monkeypatch.setattr(container_mock, "push", push_mock)

    received_secret = synapse.get_registration_shared_secret(container_mock)

    assert pull_mock.call_args[0][0] == synapse.SYNAPSE_CONFIG_PATH
    assert received_secret == expected_secret


def test_get_registration_shared_secret_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: call get_registration_shared_secret.
    assert: raise WorkloadError.
    """
    error_message = "Error pulling file"
    path_error = ops.pebble.PathError(kind="fake", message=error_message)
    pull_mock = MagicMock(side_effect=path_error)
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "pull", pull_mock)

    with pytest.raises(ops.pebble.PathError, match=error_message):
        synapse.get_registration_shared_secret(container_mock)


HTTP_PROXY_TEST_PARAMS = [
    pytest.param({}, {}, id="no_env"),
    pytest.param({"JUJU_CHARM_NO_PROXY": "127.0.0.1"}, {"no_proxy": "127.0.0.1"}, id="no_proxy"),
    pytest.param(
        {"JUJU_CHARM_HTTP_PROXY": "http://proxy.test"},
        {"http_proxy": "http://proxy.test"},
        id="http_proxy",
    ),
    pytest.param(
        {"JUJU_CHARM_HTTPS_PROXY": "http://proxy.test"},
        {"https_proxy": "http://proxy.test"},
        id="https_proxy",
    ),
    pytest.param(
        {
            "JUJU_CHARM_HTTP_PROXY": "http://proxy.test",
            "JUJU_CHARM_HTTPS_PROXY": "http://proxy.test",
        },
        {"http_proxy": "http://proxy.test", "https_proxy": "http://proxy.test"},
        id="http_https_proxy",
    ),
]


@pytest.mark.parametrize(
    "set_env, expected",
    HTTP_PROXY_TEST_PARAMS,
)
def test_http_proxy(
    set_env: typing.Dict[str, str],
    expected: typing.Dict[str, str],
    monkeypatch,
    harness: Harness,
):
    """
    arrange: set juju charm http proxy related environment variables.
    act: generate a Synapse environment.
    assert: environment generated should contain proper proxy environment variables.
    """
    for set_env_name, set_env_value in set_env.items():
        monkeypatch.setenv(set_env_name, set_env_value)

    harness.begin()
    env = synapse.get_environment(harness.charm._charm_state)

    expected_env: typing.Dict[str, typing.Optional[str]] = {
        "http_proxy": None,
        "https_proxy": None,
        "no_proxy": None,
    }
    expected_env.update(expected)
    for env_name, env_value in expected_env.items():
        assert env.get(env_name) == env.get(env_name.upper()) == env_value
