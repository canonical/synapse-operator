# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Database unit tests."""

# pylint: disable=protected-access

import unittest.mock

import ops
import pytest
from ops.testing import Harness
from psycopg2 import sql


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_erase_database(
    harness_server_name_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and erase database.
    assert: erase query is executed.
    """
    harness = harness_server_name_configured
    harness.disable_hooks()
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
    harness._framework = ops.framework.Framework(
        harness._storage, harness._charm_dir, harness._meta, harness._model
    )
    harness._charm = None
    harness.enable_hooks()
    harness.begin()
    harness.set_leader(True)
    conn_mock = unittest.mock.MagicMock()
    cursor_mock = conn_mock.cursor.return_value.__enter__.return_value
    cursor_mock.execute.side_effect = None
    conn_func_mock = unittest.mock.MagicMock(return_value=conn_mock)
    monkeypatch.setattr(harness.charm.database, "get_conn", conn_func_mock)
    harness.charm.database.erase_database()
    conn_mock.cursor.assert_called()
    calls = [
        unittest.mock.call(sql.Composed([sql.SQL("DROP DATABASE "), sql.Identifier("synapse")])),
        unittest.mock.call(
            sql.Composed(
                [
                    sql.SQL("CREATE DATABASE "),
                    sql.Identifier("synapse"),
                    sql.SQL(" WITH LC_CTYPE = 'C' LC_COLLATE='C' TEMPLATE='template0';"),
                ]
            )
        ),
    ]
    cursor_mock.execute.assert_has_calls(calls)


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_get_conn(
    harness_server_name_configured: Harness,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and get connection.
    assert: connection is called with correct parameters.
    """
    harness = harness_server_name_configured
    harness.disable_hooks()
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
    harness._framework = ops.framework.Framework(
        harness._storage, harness._charm_dir, harness._meta, harness._model
    )
    harness._charm = None
    harness.enable_hooks()
    harness.begin()
    harness.set_leader(True)
    mock_connection = unittest.mock.MagicMock()
    mock_connection.autocommit = True
    connect_mock = unittest.mock.MagicMock(return_value=mock_connection)
    monkeypatch.setattr("psycopg2.connect", connect_mock)
    harness.charm.database.get_conn()

    connect_mock.assert_called_once_with(
        "dbname='synapse' user='user' host='myhost' password='password' connect_timeout=1"
    )


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_prepare_database(
    harness_server_name_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and prepare database.
    assert: update query is executed.
    """
    harness = harness_server_name_configured
    harness.disable_hooks()
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
    harness._framework = ops.framework.Framework(
        harness._storage, harness._charm_dir, harness._meta, harness._model
    )
    harness._charm = None
    harness.enable_hooks()
    harness.begin()
    harness.set_leader(True)
    conn_mock = unittest.mock.MagicMock()
    cursor_mock = conn_mock.cursor.return_value.__enter__.return_value
    cursor_mock.execute.side_effect = None
    conn_func_mock = unittest.mock.MagicMock(return_value=conn_mock)
    monkeypatch.setattr(harness.charm.database, "get_conn", conn_func_mock)
    harness.charm.database.prepare_database()
    conn_mock.cursor.assert_called()
    cursor_mock.execute.assert_called_with(
        sql.Composed(
            [
                sql.SQL("UPDATE pg_database SET datcollate='C', datctype='C' WHERE datname = "),
                sql.Literal("synapse"),
            ]
        )
    )


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
    # reinitialize the charm as would happen in real environment
    harness.disable_hooks()
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
    harness._framework = ops.framework.Framework(
        harness._storage, harness._charm_dir, harness._meta, harness._model
    )
    harness._charm = None
    harness.begin()
    expected = {
        "POSTGRES_DB": harness.charm.app.name,
        "POSTGRES_HOST": "myhost",
        "POSTGRES_PASSWORD": "password",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "user",
    }
    assert expected == harness.charm.database.get_relation_data()
    assert harness.charm.app.name == harness.charm.database.get_database_name()
    synapse_env = harness.charm._synapse.synapse_environment()
    assert all(key in synapse_env and synapse_env[key] == value for key, value in expected.items())
