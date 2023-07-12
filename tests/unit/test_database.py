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

from constants import SYNAPSE_CONTAINER_NAME
from exceptions import CharmDatabaseRelationNotFoundError


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_erase_database(harness_with_postgresql: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and erase database.
    assert: erase query is executed.
    """
    harness = harness_with_postgresql
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
def test_erase_database_error(
    harness_with_postgresql: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and erase database.
    assert: exception is raised.
    """
    harness = harness_with_postgresql
    conn_mock = unittest.mock.MagicMock()
    cursor_mock = conn_mock.cursor.return_value.__enter__.return_value
    error_msg = "Invalid query"
    cursor_mock.execute.side_effect = psycopg2.Error(error_msg)
    conn_func_mock = unittest.mock.MagicMock(return_value=conn_mock)
    monkeypatch.setattr(harness.charm.database, "get_conn", conn_func_mock)
    with pytest.raises(psycopg2.Error):
        harness.charm.database.erase_database()


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_get_conn(
    harness_with_postgresql: Harness,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and get connection.
    assert: connection is called with correct parameters.
    """
    harness = harness_with_postgresql
    mock_connection = unittest.mock.MagicMock()
    mock_connection.autocommit = True
    connect_mock = unittest.mock.MagicMock(return_value=mock_connection)
    monkeypatch.setattr("psycopg2.connect", connect_mock)
    harness.charm.database.get_conn()
    connect_mock.assert_called_once_with(
        "dbname='synapse' user='user' host='myhost' password='password' connect_timeout=1"
    )


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_get_conn_error(
    harness_with_postgresql: Harness,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and get connection.
    assert: exception is raised.
    """
    harness = harness_with_postgresql
    error_msg = "Invalid query"
    connect_mock = unittest.mock.MagicMock(side_effect=psycopg2.Error(error_msg))
    monkeypatch.setattr("psycopg2.connect", connect_mock)
    with pytest.raises(psycopg2.Error):
        harness.charm.database.get_conn()


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_on_database_created(
    harness_with_postgresql: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and trigger on_database_created.
    assert: update query is executed.
    """
    harness = harness_with_postgresql
    conn_mock = unittest.mock.MagicMock()
    cursor_mock = conn_mock.cursor.return_value.__enter__.return_value
    cursor_mock.execute.side_effect = None
    conn_func_mock = unittest.mock.MagicMock(return_value=conn_mock)
    change_config_mock = unittest.mock.MagicMock(return_value=None)
    monkeypatch.setattr(harness.charm.database, "get_conn", conn_func_mock)
    monkeypatch.setattr(harness.charm.database, "_change_config", change_config_mock)
    harness.charm.database._on_database_created(unittest.mock.Mock())
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
def test_prepare_database_error(
    harness_with_postgresql: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and prepare database.
    assert: exception is raised.
    """
    harness = harness_with_postgresql
    conn_mock = unittest.mock.MagicMock()
    cursor_mock = conn_mock.cursor.return_value.__enter__.return_value
    error_msg = "Invalid query"
    cursor_mock.execute.side_effect = psycopg2.Error(error_msg)
    conn_func_mock = unittest.mock.MagicMock(return_value=conn_mock)
    monkeypatch.setattr(harness.charm.database, "get_conn", conn_func_mock)
    with pytest.raises(psycopg2.Error):
        harness.charm.database.prepare_database()


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_relation_data(
    harness_with_postgresql: Harness,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation.
    assert: database data and synapse environment should be the same as relation data.
    """
    harness = harness_with_postgresql
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


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_relation_data_error(
    harness_with_postgresql: Harness,
):
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and trigger change config.
    assert: charm status is active.
    """
    harness = harness_with_postgresql
    harness.charm.database.connection_params = None
    with pytest.raises(CharmDatabaseRelationNotFoundError):
        harness.charm.database.get_database_name()


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_change_config(
    harness_with_postgresql: Harness,
):
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and trigger change config.
    assert: charm status is active.
    """
    harness = harness_with_postgresql
    harness.charm.database._change_config(unittest.mock.MagicMock())
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


@pytest.mark.parametrize("harness", [0], indirect=True)
def test_change_config_error(
    harness_with_postgresql: Harness,
):
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and trigger change config.
    assert: charm status is active.
    """
    harness = harness_with_postgresql
    harness.set_can_connect(harness.model.unit.containers[SYNAPSE_CONTAINER_NAME], False)
    harness.charm.database._change_config(unittest.mock.MagicMock())
    assert isinstance(harness.model.unit.status, ops.WaitingStatus)
