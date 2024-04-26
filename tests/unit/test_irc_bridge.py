# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Tests for the irc_bridge module."""

from unittest.mock import MagicMock

import pytest
from ops.model import Container

import irc_bridge
import synapse
from charm_state import CharmState, SynapseConfig
from charm_types import DatasourcePostgreSQL
from irc_bridge import enable_irc_bridge
from synapse import ExecResult


@pytest.fixture(name="state")
def charm_state_fixture():
    """Construct a CharmState object."""

    def charm_state_with_db(with_db_config: bool) -> CharmState:
        """
        Create a CharmState object with a SynapseConfig and optional DatasourcePostgreSQL object.

        Args:
            with_db_config: Whether to include a DatasourcePostgreSQL object in the CharmState.

        Returns:
            A CharmState object.
        """
        synapse_config = SynapseConfig(  # type: ignore
            server_name="foo",
        )
        db_config = DatasourcePostgreSQL(
            user="bar",
            password="baz",  # nosec
            host="qux",
            port="quux",
            db="quuz",
        )
        if not with_db_config:
            db_config = None  # type: ignore
        return CharmState(
            synapse_config=synapse_config,
            datasource=None,
            irc_bridge_datasource=db_config,
            saml_config=None,
            smtp_config=None,
            redis_config=None,
            media_config=None,
        )

    return charm_state_with_db


@pytest.fixture(name="container_mock")
def container_fixture():
    """Construct a Container object."""
    return MagicMock(spec=Container)


def test_enable_irc_bridge_with_pebble_socket_available(state, container_mock, monkeypatch):
    """Test enabling the IRC bridge when the Pebble socket is available.
    Arrange:
    - A container mock with a Pebble socket available.
    - A charm state with a SynapseConfig and DatasourcePostgreSQL object.
    Act:
    - Enable the IRC bridge.
    Assert:
    - The irc files are pushed to the container.
    """
    container_mock.can_connect.return_value = True
    monkeypatch.setattr(
        synapse.workload,
        "_exec",
        MagicMock(return_value=ExecResult(exit_code=0, stdout="stdout", stderr="stderr")),
    )
    monkeypatch.setattr(
        irc_bridge,
        "_create_pem_file",
        MagicMock(return_value=ExecResult(exit_code=0, stdout="stdout", stderr="stderr")),
    )

    charm = state(True)
    enable_irc_bridge(charm, container_mock)

    container_mock.can_connect.assert_called_once()
    container_mock.push.assert_called_once()
    container_mock.push.assert_called_once()


def test_enable_irc_bridge_with_pebble_socket_unavailable(state, container_mock):
    """Test enabling the IRC bridge when the Pebble socket is unavailable.
    Arrange:
    - A container mock with a Pebble socket unavailable.
    - A charm state with a SynapseConfig and DatasourcePostgreSQL object.
    Act:
    - Enable the IRC bridge.
    Assert:
    - The irc files are not pushed to the container.
    """
    container_mock.can_connect.return_value = False

    enable_irc_bridge(state, container_mock)

    container_mock.can_connect.assert_called_once()
    container_mock.push.assert_not_called()


def test_enable_irc_bridge_with_no_db_connection_string(state, container_mock):
    """Test enabling the IRC bridge when there is no db connection string.
    Arrange:
    - A container mock with a Pebble socket available.
    - A charm state with a SynapseConfig and no DatasourcePostgreSQL object.
    Act:
    - Enable the IRC bridge.
    Assert:
    - The irc files are not pushed to the container.
    """
    container_mock.can_connect.return_value = True

    charm = state(False)
    enable_irc_bridge(charm, container_mock)

    container_mock.can_connect.assert_called_once()
    container_mock.push.assert_not_called()
