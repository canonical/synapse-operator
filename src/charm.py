#!/usr/bin/env python3
# Copyright 2023 Mariyan Dimitrov
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

https://discourse.charmhub.io/t/4208
"""

import collections
import logging
import os
import psycopg2
from psycopg2 import sql

import ops.lib
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseCreatedEvent,
    DatabaseRequires,
)
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, WaitingStatus

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)

DATABASE_NAME = "synapse-db"

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]


class MatrixOperatorCharm(CharmBase):
    """Charm the service."""

    _CONTAINER_NAME = "synapse"
    _SYNAPSE_CONFIG_PATH = "/data/homeserver.yaml"

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.start, self._on_install)
        self.framework.observe(self.on.synapse_pebble_ready, self._on_config_changed)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.register_user_action, self._register_user)
        self._stored.set_default(
            db_name=None,
            db_user=None,
            db_password=None,
            db_host=None,
            db_port=None,
        )

        self.database = DatabaseRequires(
            self, relation_name="database", database_name="unused", extra_user_roles="CREATEDB"
        )
        self.framework.observe(self.database.on.database_created, self._on_database_created)
        self.framework.observe(self.database.on.endpoints_changed, self._on_database_created)

    def _create_database(self, event: DatabaseCreatedEvent) -> None:
        """Creates a new database and grant privileges to a user on it.
        Args:
            database: database to be created.
            user: user that will have access to the database.
        """
        try:
            host = event.endpoints.split(":")[0]
            database = DATABASE_NAME
            user = event.username
            connection = psycopg2.connect(
                f"dbname='unused' user='{event.username}' host='{host}'"
                f"password='{event.password}' connect_timeout=1"
            )
            connection.autocommit = True
            cursor = connection.cursor()
            cursor.execute(f"SELECT datname FROM pg_database WHERE datname='{database}';")
            if cursor.fetchone() is None:
                cursor.execute(sql.SQL("CREATE DATABASE {} WITH LC_CTYPE = 'C' LC_COLLATE='C' TEMPLATE='template0';").format(sql.Identifier(database)))
            cursor.execute(
                sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {};").format(
                    sql.Identifier(database), sql.Identifier(user)
                )
            )
            with self._connect_to_database(database=database) as conn:
                with conn.cursor() as curs:
                    statements = []
                    curs.execute(
                        "SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT LIKE 'pg_%' and schema_name <> 'information_schema';"
                    )
                    for row in curs:
                        schema = sql.Identifier(row[0])
                        statements.append(
                            sql.SQL(
                                "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA {} TO {};"
                            ).format(schema, sql.Identifier(user))
                        )
                        statements.append(
                            sql.SQL(
                                "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA {} TO {};"
                            ).format(schema, sql.Identifier(user))
                        )
                        statements.append(
                            sql.SQL(
                                "GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA {} TO {};"
                            ).format(schema, sql.Identifier(user))
                        )
                    for statement in statements:
                        curs.execute(statement)
        except psycopg2.Error as e:
            logger.error(f"Failed to create database: {e}")
            raise

    def _on_database_created(self, event: DatabaseCreatedEvent) -> None:
        """Handle database created.

        Args:
            event: Event triggering the database created handler.
        """
        self._create_database(event)
        self._stored.db_name = DATABASE_NAME
        self._stored.db_user = event.username
        self._stored.db_password = event.password
        # expected endpoint postgresql-k8s-primary:5432
        self._stored.db_host = event.endpoints.split(":")[0]
        self._stored.db_port = event.endpoints.split(":")[1]

        self._on_config_changed(event)

    def _on_install(self, _):
        """Generate a config template to be rendered later."""
        logger.debug("Generating synapse config")
        self._run_generate_synapse()

    @property
    def _external_hostname(self):
        """Return the external hostname passed to ingress via the relation."""
        # It is recommended to default to `self.app.name` so that the external
        # hostname will correspond to the deployed application name in the
        # model, but allow it to be set to something specific via config.
        return self.config["server_name"] or self.app.name

    def _container(self):
        """Get the Synapse workload container.

        Returns:
            The pebble instance of the Synapse container.
        """
        return self.unit.get_container(self._CONTAINER_NAME)

    def _populate_synapse_env_settings(self):
        """Populate env settings to pass around."""
        if os.getenv("SYNAPSE_SERVER_NAME") is None:
            os.environ["SYNAPSE_SERVER_NAME"] = self.config["server_name"]
        if os.getenv("SYNAPSE_REPORT_STATS") is None:
            os.environ["SYNAPSE_REPORT_STATS"] = self.config["report_stats"]
        pod_config = {
            "SYNAPSE_SERVER_NAME": os.getenv("SYNAPSE_SERVER_NAME"),
            "SYNAPSE_REPORT_STATS": os.getenv("SYNAPSE_REPORT_STATS"),
            "SYNAPSE_NO_TLS": "True",
            "POSTGRES_DB": self._stored.db_name,
            "POSTGRES_HOST": self._stored.db_host,
            "POSTGRES_PORT": self._stored.db_port,
            "POSTGRES_USER": self._stored.db_user,
            "POSTGRES_PASSWORD": self._stored.db_password,
        }
        return pod_config

    def _register_user(self, event):
        """Registers a user for usage with Synapse."""
        Result = collections.namedtuple("CommandExecResult", "return_code stdout stderr")

        user = event.params["username"]
        password = event.params["password"]
        admin = event.params["admin"]
        admin_switch = "--admin" if admin == "yes" else "--no-admin"

        cmd = [
            "register_new_matrix_user",
            "-u",
            user,
            "-p",
            password,
            admin_switch,
            "-c",
            self._SYNAPSE_CONFIG_PATH,
            "http://localhost:8008",
        ]
        process = self._container().exec(
            cmd,
            working_dir="/data",
            environment=self._populate_synapse_env_settings(),
        )
        try:
            stdout, stderr = process.wait_output()
            result = Result(return_code=0, stdout=stdout, stderr=stderr)
        except ops.pebble.ExecError as error:
            result = Result(error.exit_code, error.stdout, error.stderr)
        return_code = result.return_code
        logger.debug(
            "Run command: %s, return code %s\nstdout: %s\nstderr:%s",
            cmd,
            return_code,
            result.stdout,
            result.stderr,
        )

    def _run_generate_synapse(self):
        """Runs the generate command for synapse."""
        Result = collections.namedtuple("CommandExecResult", "return_code stdout stderr")

        cmd = ["/start.py", "generate"]
        process = self._container().exec(
            cmd,
            working_dir="/data",
            environment=self._populate_synapse_env_settings(),
        )
        try:
            stdout, stderr = process.wait_output()
            result = Result(return_code=0, stdout=stdout, stderr=stderr)
        except ops.pebble.ExecError as error:
            result = Result(error.exit_code, error.stdout, error.stderr)
        return_code = result.return_code
        logger.debug(
            "Run command: %s, return code %s\nstdout: %s\nstderr:%s",
            cmd,
            return_code,
            result.stdout,
            result.stderr,
        )

    def _run_migrate_synapse(self):
        """Runs the migrate command for synapse."""
        Result = collections.namedtuple("CommandExecResult", "return_code stdout stderr")
        cmd = ["/start.py", "migrate_config"]
        process = self._container().exec(
            cmd,
            working_dir="/data",
            environment=self._populate_synapse_env_settings(),
        )
        try:
            stdout, stderr = process.wait_output()
            result = Result(return_code=0, stdout=stdout, stderr=stderr)
        except ops.pebble.ExecError as error:
            result = Result(error.exit_code, error.stdout, error.stderr)
        return_code = result.return_code
        logger.debug(
            "Run command: %s, return code %s\nstdout: %s\nstderr:%s",
            cmd,
            return_code,
            result.stdout,
            result.stderr,
        )

    def _current_synapse_config(self):
        """Retrieve the current version of /data/homeserver.yaml from server.

        return None if not exists.

        Returns:
        The content of the current homeserver.yaml file, str.
        """
        synapse_config_path = self._SYNAPSE_CONFIG_PATH
        container = self._container()
        if container.exists(synapse_config_path):
            return self._container().pull(synapse_config_path).read()
        return None

    def _on_config_changed(self, event):
        """Handle changed configuration.

        Change this example to suit your needs.
        If you don't need to handle config, you can remove
        this method.

        Learn more about config at https://juju.is/docs/sdk/config
        """
        # Fetch the new config value
        log_level = self.model.config["log-level"].lower()

        # Do some validation of the configuration option
        if self._stored.db_password is not None:
            self._run_migrate_synapse()
            # The config is good, so update the configuration of the workload
            container = self.unit.get_container(self._CONTAINER_NAME)
            # Verify that we can connect to the Pebble API
            # in the workload container
            if container.can_connect():
                # Push an updated layer with the new config
                container.add_layer(self._CONTAINER_NAME, self._pebble_layer, combine=True)
                container.replan()

                logger.debug("Log level for synapse changed to '%s'", log_level)
                self.unit.status = ActiveStatus()
            else:
                # We were unable to connect to the Pebble API,
                # so we defer this event
                event.defer()
                self.unit.status = WaitingStatus("waiting for Pebble API")
        else:
            # In this case, the config option is bad,
            # so block the charm and notify the operator.
            # generate files in /data if not presents
            event.defer()
            self.unit.status = WaitingStatus("waiting for db")

    @property
    def _pebble_layer(self):
        """Return a dictionary representing a Pebble layer."""
        return {
            "summary": "matrix synapse layer",
            "description": "pebble config layer for matrix synapse",
            "services": {
                "synapse": {
                    "override": "replace",
                    "summary": "matrix synapse",
                    "command": "/start.py",
                    "startup": "enabled",
                    "environment": self._populate_synapse_env_settings(),
                }
            },
            "checks": {
                "synapse-ready": {
                    "override": "replace",
                    "level": "alive",
                    "http": {
                        "url": "http://localhost:8008/health",
                    },
                },
            },
        }


if __name__ == "__main__":  # pragma: nocover
    main(MatrixOperatorCharm)
