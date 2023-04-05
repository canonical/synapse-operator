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

import ops.lib
from charms.nginx_ingress_integrator.v0.nginx_route import require_nginx_route
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, WaitingStatus

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)

pgsql = ops.lib.use("pgsql", 1, "postgresql-charmers@lists.launchpad.net")
DATABASE_NAME = "synapse"

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]


class MatrixOperatorCharm(CharmBase):
    """Charm the service."""

    _CONTAINER_NAME = "synapse"
    _SYNAPSE_CONFIG_PATH = "/data/homeserver.yaml"

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self.framework.observe(self.on.install, self._on_install)
        self.framework.observe(self.on.start, self._on_install)
        self.framework.observe(
                self.on.synapse_pebble_ready,
                self._on_config_changed
        )
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.register_user_action, self._register_user)
        require_nginx_route(
            charm=self,
            service_hostname=self._external_hostname,
            service_name=self.app.name,
            service_port=8008,
        )
        self._stored.set_default(
            db_name=None,
            db_user=None,
            db_password=None,
            db_host=None,
            db_port=None,
        )

        self.db = pgsql.PostgreSQLClient(self, "db")  # pylint: disable=C0103
        self.framework.observe(
              self.db.on.database_relation_joined,
              self._on_database_relation_joined
          )
        self.framework.observe(
              self.db.on.master_changed,
              self._on_master_changed
          )

    def _on_database_relation_joined(
         self, event: pgsql.DatabaseRelationJoinedEvent  # type: ignore
    ) -> None:
        """Handle db-relation-joined.

        Args:
            event: Event triggering the database relation joined handler.
        """
        if self.model.unit.is_leader():
            # Provide requirements to the PostgreSQL server.
            event.database = DATABASE_NAME
            event.extensions = ["hstore:public", "pg_trgm:public"]
        elif event.database != DATABASE_NAME:
            # Leader has not yet set requirements. Defer, in case this unit
            # becomes leader and needs to perform that operation.
            event.defer()

    # pgsql.MasterChangedEvent is actually defined
    def _on_master_changed(self, event: pgsql.MasterChangedEvent) -> None:
        """Handle changes in the primary database unit.

        Args:
            event: Event triggering the database master changed handler.
        """
        if event.master is None:
            self._stored.db_name = None
            self._stored.db_user = None
            self._stored.db_password = None
            self._stored.db_host = None
            self._stored.db_port = None
        else:
            self._stored.db_name = event.master.dbname
            self._stored.db_user = event.master.user
            self._stored.db_password = event.master.password
            self._stored.db_host = event.master.host
            self._stored.db_port = event.master.port

        self._on_config_changed(event)

    def _on_install(self, _):
        """Generate a config template to be rendered later."""
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

    def _run_synapse_command(self, synapse_cmd):
        """Runs a synapse command such as generate or migrate
        for configs and register_new_matrix_user for creating users."""
        Result = collections.namedtuple(
                "CommandExecResult", "return_code stdout stderr")

        cmd = synapse_cmd
        process = self._container().exec(
            cmd,
            working_dir="/data",
            environment=self._populate_synapse_env_settings(),
        )
        try:
            stdout, stderr = process.wait_output()
            result = Result(
                    return_code=0, stdout=stdout, stderr=stderr)
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

    def _register_user(self, event):
        """Registers a user for usage with Synapse."""
        user = event.params["username"]
        password = event.params["password"]
        admin = event.params["admin"]
        admin_switch = "--admin" if admin == "yes" else "--no-admin"

        cmd = ["register_new_matrix_user",
               "-u", user, "-p", password,
               admin_switch, "-c", self._SYNAPSE_CONFIG_PATH,
               "http://localhost:8008"]
        self._run_synapse_command(cmd)

    def _run_generate_synapse(self):
        """Runs the generate command for synapse"""
        cmd = ["/start.py", "generate"]
        self._run_synapse_command(cmd)

    def _run_migrate_synapse(self):
        """Runs the migrate command for synapse"""
        cmd = ["/start.py", "migrate_config"]
        self._run_synapse_command(cmd)

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
            if self._current_synapse_config() is None:
                self._run_migrate_synapse()
            # The config is good, so update the configuration of the workload
            container = self.unit.get_container(self._CONTAINER_NAME)
            # Verify that we can connect to the Pebble API
            # in the workload container
            if container.can_connect():
                # Push an updated layer with the new config
                container.add_layer(
                        self._CONTAINER_NAME, self._pebble_layer, combine=True)
                container.replan()

                logger.debug(
                        "Log level for synapse changed to '%s'", log_level
                        )
                self.unit.status = ActiveStatus()
            else:
                # We were unable to connect to the Pebble API,
                # so we defer this event
                event.defer()
                self.unit.status = WaitingStatus("waiting for Pebble API")
        else:
            # In this case, the config option is bad,
            # so block the charm and notify the operator.
            # generate files in /data if not present
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
