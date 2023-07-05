# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Database unit tests."""

# pylint: disable=protected-access

import unittest.mock

import ops
import psycopg2
import pytest
from ops.testing import Harness


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_relation_data(
    harness_server_name_configured: Harness,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation.
    assert: database data and synapse environment should be the same as relation data.
    """
    harness = harness_server_name_configured
    assert not harness.charm._database.get_relation_data()
    # reinitialize the charm as would happen in real environment
    harness.disable_hooks()
    harness._framework = ops.framework.Framework(
        harness._storage, harness._charm_dir, harness._meta, harness._model
    )
    harness._charm = None
    relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(relation_id, "postgresql/0")
    harness.update_relation_data(
        relation_id,
        "postgresql",
        {
            "endpoints": "myhost:5432",
            "username": "user",
            "password": "password",
        },
    )
    harness.begin_with_initial_hooks()
    expected = {
        "POSTGRES_DB": harness.charm.app.name,
        "POSTGRES_HOST": "myhost",
        "POSTGRES_PASSWORD": "password",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "user",
    }
    assert expected == harness.charm._database.get_relation_data()
    synapse_env = harness.charm._synapse.synapse_environment()
    assert all(key in synapse_env and synapse_env[key] == value for key, value in expected.items())


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_prepare_database_error(
    harness_server_name_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation.
    assert: database data and synapse environment should be the same as relation data.
    """
    harness = harness_server_name_configured
    relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(relation_id, "postgresql/0")
    harness.update_relation_data(
        relation_id,
        "postgresql",
        {
            "endpoints": "myhost:5432",
            "username": "user",
            "password": "password",
        },
    )
    database_mocked = unittest.mock.MagicMock()
    prepare_database_mock = unittest.mock.MagicMock(side_effect=None)
    monkeypatch.setattr(database_mocked, "prepare_database", prepare_database_mock)
    harness.charm._database = database_mocked
    harness.charm._on_database_created(unittest.mock.MagicMock())
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)
    error_msg = "Invalid query"
    prepare_database_mock = unittest.mock.MagicMock(side_effect=psycopg2.Error(error_msg))
    monkeypatch.setattr(database_mocked, "prepare_database", prepare_database_mock)
    harness.charm._database = database_mocked
    harness.charm._on_database_created(unittest.mock.MagicMock())
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert error_msg in str(harness.model.unit.status)
