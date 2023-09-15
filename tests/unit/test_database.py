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

import database_observer
import synapse
from charm import SynapseCharm
from charm_types import DatasourcePostgreSQL
from constants import SYNAPSE_CONTAINER_NAME, TEST_SERVER_NAME
from database_client import DatabaseClient
from exceptions import CharmDatabaseRelationNotFoundError


def test_erase_database(
    datasource_postgresql_password: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and erase database.
    assert: erase query is executed.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME})
    relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(relation_id, "postgresql/0")
    harness.update_relation_data(
        relation_id,
        "postgresql",
        {
            "endpoints": "myhost:5432",
            "username": "user",
            "password": datasource_postgresql_password,
        },
    )
    harness.begin()
    datasource = harness.charm.database.get_relation_as_datasource()
    db_client = DatabaseClient(datasource=datasource)
    conn_mock = unittest.mock.MagicMock()
    cursor_mock = conn_mock.cursor.return_value.__enter__.return_value
    cursor_mock.execute.side_effect = None
    monkeypatch.setattr(db_client, "_connect", unittest.mock.MagicMock())
    db_client._conn = conn_mock

    db_client.erase()

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
    harness.cleanup()


def test_erase_database_error(
    datasource_postgresql_password: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and erase database.
    assert: exception is raised.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME})
    relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(relation_id, "postgresql/0")
    harness.update_relation_data(
        relation_id,
        "postgresql",
        {
            "endpoints": "myhost:5432",
            "username": "user",
            "password": datasource_postgresql_password,
        },
    )
    harness.begin()
    datasource = harness.charm.database.get_relation_as_datasource()
    db_client = DatabaseClient(datasource=datasource)
    conn_mock = unittest.mock.MagicMock()
    cursor_mock = conn_mock.cursor.return_value.__enter__.return_value
    error_msg = "Invalid query"
    cursor_mock.execute.side_effect = psycopg2.Error(error_msg)
    monkeypatch.setattr(db_client, "_connect", unittest.mock.MagicMock())
    db_client._conn = conn_mock

    with pytest.raises(psycopg2.Error):
        db_client.erase()
    harness.cleanup()


def test_connect(monkeypatch: pytest.MonkeyPatch, datasource_postgresql_password: str):
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and get connection.
    assert: connection is called with correct parameters.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME})
    relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(relation_id, "postgresql/0")
    harness.update_relation_data(
        relation_id,
        "postgresql",
        {
            "endpoints": "myhost:5432",
            "username": "user",
            "password": datasource_postgresql_password,
        },
    )
    harness.begin()
    datasource = harness.charm.database.get_relation_as_datasource()
    db_client = DatabaseClient(datasource=datasource)
    mock_connection = unittest.mock.MagicMock()
    mock_connection.autocommit = True
    connect_mock = unittest.mock.MagicMock(return_value=mock_connection)
    monkeypatch.setattr("psycopg2.connect", connect_mock)

    db_client._connect()

    query = (
        "dbname='synapse' user='user' host='myhost' "
        f"password='{datasource_postgresql_password}' connect_timeout=5"
    )
    connect_mock.assert_called_once_with(query)
    harness.cleanup()


def test_connect_error(
    datasource_postgresql_password: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and get connection.
    assert: exception is raised.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME})
    relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(relation_id, "postgresql/0")
    harness.update_relation_data(
        relation_id,
        "postgresql",
        {
            "endpoints": "myhost:5432",
            "username": "user",
            "password": datasource_postgresql_password,
        },
    )
    harness.begin()
    datasource = harness.charm.database.get_relation_as_datasource()
    db_client = DatabaseClient(datasource=datasource)
    error_msg = "Invalid query"
    connect_mock = unittest.mock.MagicMock(side_effect=psycopg2.Error(error_msg))
    monkeypatch.setattr("psycopg2.connect", connect_mock)
    with pytest.raises(psycopg2.Error):
        db_client._connect()
    harness.cleanup()


def test_prepare_database(
    datasource_postgresql_password: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and prepare database.
    assert: update query is executed.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME})
    relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(relation_id, "postgresql/0")
    harness.update_relation_data(
        relation_id,
        "postgresql",
        {
            "endpoints": "myhost:5432",
            "username": "user",
            "password": datasource_postgresql_password,
        },
    )
    harness.begin()
    datasource = harness.charm.database.get_relation_as_datasource()
    db_client = DatabaseClient(datasource=datasource)
    conn_mock = unittest.mock.MagicMock()
    cursor_mock = conn_mock.cursor.return_value.__enter__.return_value
    cursor_mock.execute.side_effect = None
    monkeypatch.setattr(db_client, "_connect", unittest.mock.MagicMock())
    db_client._conn = conn_mock
    db_client.prepare()
    conn_mock.cursor.assert_called()
    cursor_mock.execute.assert_called_with(
        sql.Composed(
            [
                sql.SQL("UPDATE pg_database SET datcollate='C', datctype='C' WHERE datname = "),
                sql.Literal("synapse"),
            ]
        )
    )
    harness.cleanup()


def test_prepare_database_error(
    datasource_postgresql_password: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and prepare database.
    assert: exception is raised.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME})
    relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(relation_id, "postgresql/0")
    harness.update_relation_data(
        relation_id,
        "postgresql",
        {
            "endpoints": "myhost:5432",
            "username": "user",
            "password": datasource_postgresql_password,
        },
    )
    harness.begin()
    datasource = harness.charm.database.get_relation_as_datasource()
    db_client = DatabaseClient(datasource=datasource)
    conn_mock = unittest.mock.MagicMock()
    cursor_mock = conn_mock.cursor.return_value.__enter__.return_value
    error_msg = "Invalid query"
    cursor_mock.execute.side_effect = psycopg2.Error(error_msg)
    monkeypatch.setattr(db_client, "_connect", unittest.mock.MagicMock())
    db_client._conn = conn_mock

    with pytest.raises(psycopg2.Error):
        db_client.prepare()
    harness.cleanup()


def test_relation_as_datasource(datasource_postgresql_password: str) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation.
    assert: database data and synapse environment should be the same as relation data.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME})
    relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(relation_id, "postgresql/0")
    harness.update_relation_data(
        relation_id,
        "postgresql",
        {
            "endpoints": "myhost:5432",
            "username": "user",
            "password": datasource_postgresql_password,
        },
    )

    harness.begin()

    expected = DatasourcePostgreSQL(
        host="myhost",
        db=harness.charm.app.name,
        password=datasource_postgresql_password,
        port="5432",
        user="user",
    )
    assert expected == harness.charm.database.get_relation_as_datasource()
    assert harness.charm.app.name == harness.charm.database.get_database_name()
    synapse_env = synapse.get_environment(harness.charm._charm_state)
    assert synapse_env["POSTGRES_DB"] == expected["db"]
    assert synapse_env["POSTGRES_HOST"] == expected["host"]
    assert synapse_env["POSTGRES_PORT"] == expected["port"]
    assert synapse_env["POSTGRES_USER"] == expected["user"]
    assert synapse_env["POSTGRES_PASSWORD"] == expected["password"]
    harness.cleanup()


def test_relation_as_datasource_error(
    datasource_postgresql_password: str, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and trigger change config.
    assert: charm status is active.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME})
    relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(relation_id, "postgresql/0")
    harness.update_relation_data(
        relation_id,
        "postgresql",
        {
            "endpoints": "myhost:5432",
            "username": "user",
            "password": datasource_postgresql_password,
        },
    )

    harness.begin()

    get_relation_as_datasource_mock = unittest.mock.MagicMock(return_value=None)
    monkeypatch.setattr(
        harness.charm.database, "get_relation_as_datasource", get_relation_as_datasource_mock
    )
    with pytest.raises(CharmDatabaseRelationNotFoundError):
        harness.charm.database.get_database_name()
    harness.cleanup()


def test_change_config(
    harness: Harness, datasource_postgresql_password: str, monkeypatch: pytest.MonkeyPatch
):
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and trigger change config.
    assert: charm status is active.
    """
    monkeypatch.setattr(synapse, "get_version", lambda *_args, **_kwargs: "")
    harness.update_config({"server_name": TEST_SERVER_NAME})
    relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(relation_id, "postgresql/0")
    harness.update_relation_data(
        relation_id,
        "postgresql",
        {
            "endpoints": "myhost:5432",
            "username": "user",
            "password": datasource_postgresql_password,
        },
    )
    harness.begin()

    harness.charm.database._change_config()

    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


def test_change_config_error(
    datasource_postgresql_password: str,
):
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and trigger change config.
    assert: charm status is active.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME})
    relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(relation_id, "postgresql/0")
    harness.update_relation_data(
        relation_id,
        "postgresql",
        {
            "endpoints": "myhost:5432",
            "username": "user",
            "password": datasource_postgresql_password,
        },
    )
    harness.begin()
    harness.set_can_connect(harness.model.unit.containers[SYNAPSE_CONTAINER_NAME], False)

    harness.charm.database._change_config()

    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)
    harness.cleanup()


def test_on_database_created(datasource_postgresql_password: str, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and trigger _on_database_created.
    assert: charm status is active.
    """
    harness = Harness(SynapseCharm)
    harness.update_config({"server_name": TEST_SERVER_NAME})
    relation_id = harness.add_relation("database", "postgresql")
    harness.add_relation_unit(relation_id, "postgresql/0")
    harness.update_relation_data(
        relation_id,
        "postgresql",
        {
            "endpoints": "myhost:5432",
            "username": "user",
            "password": datasource_postgresql_password,
        },
    )
    harness.begin()
    db_client_mock = unittest.mock.MagicMock()
    conn_mock = unittest.mock.MagicMock()
    cursor_mock = conn_mock.cursor.return_value.__enter__.return_value
    cursor_mock.execute.side_effect = None
    monkeypatch.setattr(db_client_mock, "_connect", unittest.mock.MagicMock())
    db_client_mock._conn = conn_mock
    monkeypatch.setattr(
        database_observer, "DatabaseClient", unittest.mock.MagicMock(return_value=db_client_mock)
    )

    harness.charm.database._on_database_created(unittest.mock.MagicMock())

    db_client_mock.prepare.assert_called_once()
    harness.cleanup()
