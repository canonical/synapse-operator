#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module to interact with Reset Instance action."""

import logging
import typing

import ops
import psycopg2

import synapse
from charm_state import CharmState
from database_client import DatabaseClient, DatasourcePostgreSQL

logger = logging.getLogger(__name__)


class ResetInstanceError(Exception):
    """Exception raised when something fails while running reset-instance.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the ResetInstanceError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


def reset_instance(
    container: ops.Container,
    charm_state: CharmState,
    datasource: typing.Optional[DatasourcePostgreSQL],
) -> None:
    """Run reset instance action.

    Args:
        container: Container of the charm.
        charm_state: charm state from the charm.
        datasource: datasource to interact with the database.

    Raises:
        ResetInstanceError: if something goes wrong while resetting the instance.
    """
    try:
        if datasource is not None:
            logger.info("Erase Synapse database")
            # Connecting to template1 to make it possible to erase the database.
            # Otherwise PostgreSQL will prevent it if there are open connections.
            db_client = DatabaseClient(datasource=datasource, alternative_database="template1")
            db_client.erase()
        synapse.execute_migrate_config(container=container, charm_state=charm_state)
    except (psycopg2.Error, synapse.WorkloadError) as exc:
        raise ResetInstanceError(str(exc)) from exc
