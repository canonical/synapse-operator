# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm matrix-auth integration unit tests."""

# pylint: disable=protected-access

from unittest.mock import ANY, MagicMock

import pytest
import yaml
from charms.synapse.v1.matrix_auth import MatrixAuthRequirerData
from ops.testing import Harness
from pydantic import SecretStr

import synapse

from .conftest import TEST_SERVER_NAME


def test_matrix_auth_update_success(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: start the Synapse charm.
    act: integrate via matrix-auth.
    assert: update_relation_data is called and homeserver has same value as
        server_name.
    """
    harness.update_config({"server_name": TEST_SERVER_NAME})
    harness.set_can_connect(synapse.SYNAPSE_CONTAINER_NAME, True)
    harness.set_leader(True)
    harness.begin()
    update_relation_data = MagicMock()
    monkeypatch.setattr(
        harness.charm._matrix_auth.matrix_auth, "update_relation_data", update_relation_data
    )
    monkeypatch.setattr(
        synapse, "get_registration_shared_secret", MagicMock(return_value="shared_secret")
    )

    rel_id = harness.add_relation("matrix-auth", "maubot")
    harness.add_relation_unit(rel_id, "maubot/0")
    harness.update_relation_data(rel_id, "maubot", {"foo": "foo"})

    relation = harness.charm.framework.model.get_relation("matrix-auth", rel_id)
    update_relation_data.assert_called_with(relation, ANY)

    assert update_relation_data.call_args[0][1].homeserver == f"https://{TEST_SERVER_NAME}"


def test_matrix_auth_update_public_baseurl_success(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: start the Synapse charm with public_baseurl set.
    act: integrate via matrix-auth.
    assert: update_relation_data is called and homeserver has same value as
        public_baseurl.
    """
    base_url_value = "https://new-server"
    harness.update_config({"server_name": TEST_SERVER_NAME, "public_baseurl": base_url_value})
    harness.set_can_connect(synapse.SYNAPSE_CONTAINER_NAME, True)
    harness.set_leader(True)
    harness.begin()
    update_relation_data = MagicMock()
    monkeypatch.setattr(
        harness.charm._matrix_auth.matrix_auth, "update_relation_data", update_relation_data
    )
    monkeypatch.setattr(
        synapse, "get_registration_shared_secret", MagicMock(return_value="shared_secret")
    )

    rel_id = harness.add_relation("matrix-auth", "maubot")
    harness.add_relation_unit(rel_id, "maubot/0")
    harness.update_relation_data(rel_id, "maubot", {"foo": "foo"})

    relation = harness.charm.framework.model.get_relation("matrix-auth", rel_id)
    update_relation_data.assert_called_with(relation, ANY)

    assert update_relation_data.call_args[0][1].homeserver == base_url_value


def test_matrix_auth_registration_secret_success(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: start the Synapse charm with public_base url set.
    act: integrate via matrix-auth with maubot and add registration as relation
        data.
    assert: update_relation_data is called, homeserver has same value as
        public_baseurl and app_service_config_files is set.
    """
    base_url_value = "https://new-server"
    harness.update_config({"server_name": TEST_SERVER_NAME, "public_baseurl": base_url_value})
    harness.set_can_connect(synapse.SYNAPSE_CONTAINER_NAME, True)
    harness.set_leader(True)
    harness.begin_with_initial_hooks()
    update_relation_data = MagicMock()
    monkeypatch.setattr(
        harness.charm._matrix_auth.matrix_auth, "update_relation_data", update_relation_data
    )
    aes_key = b"DXnflqjmmM8-UASxTl9oWeM7PWKQoclMFVb_bp9zLGY="
    monkeypatch.setattr(
        MatrixAuthRequirerData, "get_aes_key_secret", MagicMock(return_value=aes_key)
    )
    monkeypatch.setattr(
        synapse, "get_registration_shared_secret", MagicMock(return_value="shared_secret")
    )
    create_registration_secrets_files_mock = MagicMock()
    monkeypatch.setattr(
        synapse, "create_registration_secrets_files", create_registration_secrets_files_mock
    )

    rel_id = harness.add_relation("matrix-auth", "maubot")
    harness.add_relation_unit(rel_id, "maubot/0")
    encrypted_text = MatrixAuthRequirerData.encrypt_string(key=aes_key, plaintext=SecretStr("foo"))
    harness.update_relation_data(rel_id, "maubot", {"registration_secret": encrypted_text})

    relation = harness.charm.framework.model.get_relation("matrix-auth", rel_id)
    update_relation_data.assert_called_with(relation, ANY)
    assert update_relation_data.call_args[0][1].homeserver == base_url_value
    create_registration_secrets_files_mock.assert_called_once()
    root = harness.get_filesystem_root(synapse.SYNAPSE_CONTAINER_NAME)
    config_path = root / synapse.SYNAPSE_CONFIG_PATH[1:]
    with open(config_path, encoding="utf-8") as config_file:
        content = yaml.safe_load(config_file)
        assert "app_service_config_files" in content
        assert content["app_service_config_files"] == [
            f"/data/appservice-registration-matrix-auth-{rel_id}.yaml"
        ]


def test_matrix_auth_registration_secret_empty(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: start the Synapse charm with public_base url set.
    act: integrate via matrix-auth with maubot and add registration as relation
        data.
    assert: update_relation_data is called, homeserver has same value as
        public_baseurl and since registration is empty there are no registration
        files.
    """
    base_url_value = "https://new-server"
    harness.update_config({"server_name": TEST_SERVER_NAME, "public_baseurl": base_url_value})
    harness.set_can_connect(synapse.SYNAPSE_CONTAINER_NAME, True)
    harness.set_leader(True)
    harness.begin_with_initial_hooks()
    update_relation_data = MagicMock()
    monkeypatch.setattr(
        harness.charm._matrix_auth.matrix_auth, "update_relation_data", update_relation_data
    )
    aes_key = b"DXnflqjmmM8-UASxTl9oWeM7PWKQoclMFVb_bp9zLGY="
    monkeypatch.setattr(
        MatrixAuthRequirerData, "get_aes_key_secret", MagicMock(return_value=aes_key)
    )
    monkeypatch.setattr(
        synapse, "get_registration_shared_secret", MagicMock(return_value="shared_secret")
    )
    create_registration_secrets_files_mock = MagicMock()
    monkeypatch.setattr(
        synapse, "create_registration_secrets_files", create_registration_secrets_files_mock
    )

    rel_id = harness.add_relation("matrix-auth", "maubot")
    harness.add_relation_unit(rel_id, "maubot/0")
    relation = harness.charm.framework.model.get_relation("matrix-auth", rel_id)
    harness.charm.on["matrix-auth"].relation_changed.emit(
        relation, harness.charm.app, harness.charm.unit
    )

    update_relation_data.assert_called_with(relation, ANY)
    assert update_relation_data.call_args[0][1].homeserver == base_url_value
    create_registration_secrets_files_mock.assert_not_called()
