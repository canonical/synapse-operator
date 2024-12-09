# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse charm matrix-auth integration unit tests."""

# pylint: disable=protected-access

from unittest.mock import ANY, MagicMock

import pytest
from ops.testing import Harness

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
