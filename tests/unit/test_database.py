# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Database unit tests."""

# pylint: disable=protected-access

import unittest.mock

import ops
import psycopg2
import pytest
from ops.testing import Harness
from psycopg2 import sql


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
    assert not harness.charm._database.get_conn()
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
    assert harness.charm.app.name == harness.charm._database.get_database_name()
    synapse_env = harness.charm._synapse.synapse_environment()
    assert all(key in synapse_env and synapse_env[key] == value for key, value in expected.items())


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_get_database_name(harness_server_name_configured: Harness) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: get database name.
    assert: database name is empty.
    """
    harness = harness_server_name_configured
    assert not harness.charm._database.get_database_name()


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
    conn_mock = unittest.mock.MagicMock()
    cursor_mock = conn_mock.cursor.return_value.__enter__.return_value
    cursor_mock.execute.side_effect = None
    conn_func_mock = unittest.mock.MagicMock(return_value=conn_mock)
    monkeypatch.setattr(harness.charm._database, "get_conn", conn_func_mock)
    harness.charm._database.prepare_database()
    conn_mock.cursor.assert_called_once()
    cursor_mock.execute.assert_called_once_with(
        sql.Composed(
            [
                sql.SQL("UPDATE pg_database SET datcollate='C', datctype='C' WHERE datname = "),
                sql.Literal("synapse"),
            ]
        )
    )


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
    conn_mock = unittest.mock.MagicMock()
    cursor_mock = conn_mock.cursor.return_value.__enter__.return_value
    cursor_mock.execute.side_effect = None
    conn_func_mock = unittest.mock.MagicMock(return_value=conn_mock)
    monkeypatch.setattr(harness.charm._database, "get_conn", conn_func_mock)
    harness.charm._database.erase_database()
    conn_mock.cursor.assert_called_once()
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
def test_erase_database_conn_error(
    harness_server_name_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and erase database.
    assert: conn is none, no action is taken.
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
    conn_func_mock = unittest.mock.MagicMock(return_value=None)
    monkeypatch.setattr(harness.charm._database, "get_conn", conn_func_mock)
    harness.charm._database.erase_database()
    conn_func_mock.assert_called_once()


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_prepare_database_conn_error(
    harness_server_name_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and prepare database.
    assert: conn is none, no action is taken.
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
    conn_func_mock = unittest.mock.MagicMock(return_value=None)
    monkeypatch.setattr(harness.charm._database, "get_conn", conn_func_mock)
    harness.charm._database.prepare_database()
    conn_func_mock.assert_called_once()


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_prepare_database_error(
    harness_server_name_configured: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and prepare database.
    assert: charm is blocked if error happens while preparing database.
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


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_erase_database_error(
    harness_server_name_configured: Harness,
    monkeypatch: pytest.MonkeyPatch,
    erase_database_mocked: unittest.mock.MagicMock,
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
    harness.charm._synapse = unittest.mock.MagicMock()
    harness.set_leader(True)
    harness.charm._database = erase_database_mocked
    harness.charm._on_reset_instance_action(unittest.mock.MagicMock())
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)
    harness.disable_hooks()
    harness._framework = ops.framework.Framework(
        harness._storage, harness._charm_dir, harness._meta, harness._model
    )
    harness._charm = None
    harness.enable_hooks()
    harness.begin_with_initial_hooks()
    harness.set_leader(True)
    error_msg = "Invalid query"
    erase_database_mock = unittest.mock.MagicMock(side_effect=psycopg2.Error(error_msg))
    monkeypatch.setattr(erase_database_mocked, "erase_database", erase_database_mock)
    harness.charm._database = erase_database_mocked
    harness.charm._on_reset_instance_action(unittest.mock.MagicMock())
    assert isinstance(harness.model.unit.status, ops.BlockedStatus)
    assert error_msg in str(harness.model.unit.status)
