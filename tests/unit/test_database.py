# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Database unit tests."""

# pylint: disable=protected-access

import unittest.mock
from secrets import token_hex

import ops
import psycopg2
import pytest
from ops.testing import Harness
from psycopg2 import sql

import database_observer
import pebble
import synapse
from charm_types import DatasourcePostgreSQL
from database_client import DatabaseClient


@pytest.fixture(autouse=True)
def postgresql_relation_data_fixture(harness: Harness) -> None:
    """Configure postgres relation for base harness"""
    postgresql_relation_data = {
        "endpoints": "myhost:5432",
        "username": "user",
    }
    harness.add_relation("database", "postgresql", app_data=postgresql_relation_data)


def test_erase_database(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and erase database.
    assert: erase query is executed.
    """
    harness.begin()
    datasource = harness.charm._database.get_relation_as_datasource()
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


def test_erase_database_error(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and erase database.
    assert: exception is raised.
    """
    harness.begin()
    datasource = harness.charm._database.get_relation_as_datasource()
    db_client = DatabaseClient(datasource=datasource)
    conn_mock = unittest.mock.MagicMock()
    cursor_mock = conn_mock.cursor.return_value.__enter__.return_value
    error_msg = "Invalid query"
    cursor_mock.execute.side_effect = psycopg2.Error(error_msg)
    monkeypatch.setattr(db_client, "_connect", unittest.mock.MagicMock())
    db_client._conn = conn_mock

    with pytest.raises(psycopg2.Error):
        db_client.erase()


def test_connect(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and get connection.
    assert: connection is called with correct parameters.
    """
    postgresql_relation = harness.model.relations["database"][0]
    harness.update_relation_data(postgresql_relation.id, "postgresql", {"password": token_hex(16)})
    harness.begin()
    datasource = harness.charm._database.get_relation_as_datasource()
    db_client = DatabaseClient(datasource=datasource)
    mock_connection = unittest.mock.MagicMock()
    mock_connection.autocommit = True
    connect_mock = unittest.mock.MagicMock(return_value=mock_connection)
    monkeypatch.setattr("psycopg2.connect", connect_mock)

    db_client._connect()

    postgresql_relation_data = harness.get_relation_data(postgresql_relation.id, "postgresql")
    relation_database_password = str(postgresql_relation_data.get("password"))
    query = (
        "dbname='synapse' user='user' host='myhost' "
        f"password='{relation_database_password}' connect_timeout=5"
    )
    connect_mock.assert_called_once_with(query)


def test_connect_error(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and get connection.
    assert: exception is raised.
    """
    harness.begin()
    datasource = harness.charm._database.get_relation_as_datasource()
    db_client = DatabaseClient(datasource=datasource)
    error_msg = "Invalid query"
    connect_mock = unittest.mock.MagicMock(side_effect=psycopg2.Error(error_msg))
    monkeypatch.setattr("psycopg2.connect", connect_mock)
    with pytest.raises(psycopg2.Error):
        db_client._connect()


def test_prepare_database(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and prepare database.
    assert: update query is executed.
    """
    harness.begin()
    datasource = harness.charm._database.get_relation_as_datasource()
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


def test_prepare_database_error(harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation and prepare database.
    assert: exception is raised.
    """
    harness.begin()
    datasource = harness.charm._database.get_relation_as_datasource()
    db_client = DatabaseClient(datasource=datasource)
    conn_mock = unittest.mock.MagicMock()
    cursor_mock = conn_mock.cursor.return_value.__enter__.return_value
    error_msg = "Invalid query"
    cursor_mock.execute.side_effect = psycopg2.Error(error_msg)
    monkeypatch.setattr(db_client, "_connect", unittest.mock.MagicMock())
    db_client._conn = conn_mock

    with pytest.raises(psycopg2.Error):
        db_client.prepare()


def test_relation_as_datasource(
    harness: Harness,
) -> None:
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add database relation.
    assert: database data and synapse environment should be the same as relation data.
    """
    postgresql_relation = harness.model.relations["database"][0]
    harness.update_relation_data(postgresql_relation.id, "postgresql", {"password": token_hex(16)})

    harness.begin()

    postgresql_relation_data = harness.get_relation_data(postgresql_relation.id, "postgresql")
    relation_database_password = str(postgresql_relation_data.get("password"))
    expected = DatasourcePostgreSQL(
        host="myhost",
        db=harness.charm.app.name,
        password=relation_database_password,
        port="5432",
        user="user",
    )
    assert expected == harness.charm._database.get_relation_as_datasource()
    synapse_env = synapse.get_environment(harness.charm.build_charm_state())
    assert synapse_env["POSTGRES_DB"] == expected["db"]
    assert synapse_env["POSTGRES_HOST"] == expected["host"]
    assert synapse_env["POSTGRES_PORT"] == expected["port"]
    assert synapse_env["POSTGRES_USER"] == expected["user"]
    assert synapse_env["POSTGRES_PASSWORD"] == expected["password"]


def test_change_config(harness: Harness):
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and trigger change config.
    assert: charm status is active.
    """
    harness.begin()

    charm_state = harness.charm.build_charm_state()
    harness.charm._database._change_config(charm_state)

    assert isinstance(harness.model.unit.status, ops.ActiveStatus)


def test_change_config_error(
    harness: Harness,
):
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and trigger change config.
    assert: charm status is active.
    """
    harness.begin()
    harness.set_can_connect(harness.model.unit.containers[synapse.SYNAPSE_CONTAINER_NAME], False)

    charm_state = harness.charm.build_charm_state()
    harness.charm._database._change_config(charm_state)

    assert isinstance(harness.model.unit.status, ops.MaintenanceStatus)


def test_on_database_created(harness: Harness, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: start the Synapse charm, set Synapse container to be ready and set server_name.
    act: add relation and trigger _on_database_created.
    assert: charm status is active.
    """
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

    harness.charm._database._on_database_created(unittest.mock.MagicMock())

    db_client_mock.prepare.assert_called_once()


def test_synapse_stats_exporter_pebble_layer(harness: Harness) -> None:
    """
    arrange: charm deployed.
    act: get synapse layer data.
    assert: Synapse charm should submit the correct Synapse Stats Exporter pebble layer to pebble.
    """
    harness.begin_with_initial_hooks()

    synapse_layer = harness.get_container_pebble_plan(synapse.SYNAPSE_CONTAINER_NAME).to_dict()[
        "services"
    ][pebble.STATS_EXPORTER_SERVICE_NAME]
    assert isinstance(harness.model.unit.status, ops.ActiveStatus)
    synapse_env = synapse.get_environment(harness.charm.build_charm_state())
    assert synapse_layer == {
        "override": "replace",
        "summary": "Synapse Stats Exporter service",
        "command": "synapse-stats-exporter",
        "startup": "disabled",
        "environment": {
            "PROM_SYNAPSE_USER": synapse_env["POSTGRES_USER"],
            "PROM_SYNAPSE_PASSWORD": synapse_env["POSTGRES_PASSWORD"],
            "PROM_SYNAPSE_HOST": synapse_env["POSTGRES_HOST"],
            "PROM_SYNAPSE_PORT": synapse_env["POSTGRES_PORT"],
            "PROM_SYNAPSE_DATABASE": synapse_env["POSTGRES_DB"],
        },
        "on-failure": "ignore",
    }
