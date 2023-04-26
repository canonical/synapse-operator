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
import socket
from typing import Dict, Optional

import ops.lib
import psycopg2
import yaml
from charms.data_platform_libs.v0.data_interfaces import (
    DatabaseCreatedEvent,
    DatabaseRequires,
)
from charms.redis_k8s.v0.redis import RedisRelationCharmEvents, RedisRequires
from charms.traefik_k8s.v1.ingress import IngressPerAppRequirer
from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, Relation, WaitingStatus
from psycopg2 import sql

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)

DATABASE_NAME = "synapse-db"

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]


class MatrixOperatorCharm(CharmBase):
    """Charm the service."""

    _CONTAINER_NAME = "synapse"
    _SYNAPSE_MAIN_CONFIG_PATH = "/data/homeserver.yaml"
    _SYNAPSE_WORKER_CONFIG_PATH = "/data/worker.yaml"
    _SYNAPSE_PORT = 8008
    _SYNAPSE_REPLICATION_PORT = 9093

    _stored = StoredState()
    on = RedisRelationCharmEvents()

    @property
    def _address(self) -> str:
        """Unit's hostname."""
        return socket.getfqdn()

    @property
    def _leader_address(self) -> str:
        """Get leader address from relation data.

        Returns:
            Leader address
        """
        if self.unit.is_leader():
            return self._address

        peer_relation = self.model.get_relation("synapse-peers")
        assert peer_relation is not None  # nosec
        return peer_relation.data[self.app].get("leader-address")

    @property
    def _external_hostname(self):
        """Return the external hostname passed to ingress via the relation."""
        # It is recommended to default to `self.app.name` so that the external
        # hostname will correspond to the deployed application name in the
        # model, but allow it to be set to something specific via config.
        return self.config["server_name"] or self.app.name

    @property
    def _pebble_layer(self):
        """Return a dictionary representing a Pebble layer."""
        command = "/start.py"
        env_vars = self._populate_synapse_env_settings()
        if not self.unit.is_leader():
            logging.debug("starting a worker")
            command = f"/start.py run --config-path={self._SYNAPSE_MAIN_CONFIG_PATH} --config-path={self._SYNAPSE_WORKER_CONFIG_PATH}"
            env_vars["SYNAPSE_WORKER"] = "synapse.app.generic_worker"
        return {
            "summary": "matrix synapse layer",
            "description": "pebble config layer for matrix synapse",
            "services": {
                "synapse": {
                    "override": "replace",
                    "summary": "matrix synapse",
                    "command": command,
                    "startup": "enabled",
                    "environment": env_vars,
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

    def __init__(self, *args):
        super().__init__(*args)

        self._stored.set_default(
            db_name=None,
            db_user=None,
            db_password=None,
            db_host=None,
            db_port=None,
            redis_relation={},
        )

        self.redis = RedisRequires(self, self._stored)

        self.database = DatabaseRequires(
            self, relation_name="database", database_name="unused", extra_user_roles="CREATEDB"
        )

        self.ingress = IngressPerAppRequirer(
            self,
            port=self._SYNAPSE_PORT,
            # We're forced to use the app's service endpoint
            # as the ingress per app interface currently always routes to the leader.
            # https://github.com/canonical/traefik-k8s-operator/issues/159
            host=f"{self.app.name}-endpoints.{self.model.name}.svc.cluster.local",
            strip_prefix=True,
        )
        # TODO port for federation?

        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.register_user_action, self._register_user)
        self.framework.observe(self.database.on.database_created, self._on_database_created)
        self.framework.observe(self.database.on.endpoints_changed, self._on_database_created)
        self.framework.observe(self.on.redis_relation_changed, self._on_config_changed)
        self.framework.observe(self.on.leader_elected, self._on_config_changed)

    def _get_redis_rel(self) -> Optional[Relation]:
        """Get Redis relation.

        Returns:
            Relation between synapse and redis. If not found, returns None.
        """
        return next(
            (rel for rel in self.model.relations["redis"]),
            None,
        )

    def _get_redis_backend(self) -> Dict:
        """Generate Redis Backend URL formed by Redis host and port for the relation.

        Returns:
            Redis Backend URL as expected by Synapse.
        """
        redis_host = ""
        redis_port = "0"

        if (redis_rel := self._get_redis_rel()) is not None:
            logger.debug(redis_rel.data)
            redis_unit = next(unit for unit in redis_rel.data if unit.name.startswith("redis"))
            redis_host = redis_rel.data[redis_unit].get("hostname", "")
            redis_port = redis_rel.data[redis_unit].get("port", "0")

        enabled = True
        if not redis_host:
            logger.debug("Redis is not ready")
            enabled = False

        return {"enabled": enabled, "host": redis_host, "port": int(redis_port)}

    def _create_database(self, event: DatabaseCreatedEvent) -> None:
        """Create a new database and grant privileges to a user on it.

        Args:
            event: DatabaseCreated event
        """
        try:
            host = event.endpoints.split(":")[0]
            database = DATABASE_NAME
            user = event.username
            conn = psycopg2.connect(
                f"dbname='unused' user='{event.username}' host='{host}'"
                f"password='{event.password}' connect_timeout=1"
            )
            conn.autocommit = True
            cursor = conn.cursor()
            with conn.cursor() as curs:
                cursor.execute(f"SELECT datname FROM pg_database WHERE datname='{database}';")
                if cursor.fetchone() is None:
                    cursor.execute(
                        sql.SQL(
                            "CREATE DATABASE {} WITH LC_CTYPE = 'C' LC_COLLATE='C' TEMPLATE='template0';"
                        ).format(sql.Identifier(database))
                    )
                    # Bug: if you recreate the relation, the new user won't be able to access the database
                    # created by the previous relation user.
                cursor.execute(
                    sql.SQL("GRANT ALL PRIVILEGES ON DATABASE {} TO {};").format(
                        sql.Identifier(database), sql.Identifier(user)
                    )
                )
                statements = []
                curs.execute(
                    "SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT LIKE 'pg_%' and schema_name <> 'information_schema';"
                )
                for row in curs:
                    schema = sql.Identifier(row[0])
                    statements.append(
                        sql.SQL("GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA {} TO {};").format(
                            schema, sql.Identifier(user)
                        )
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
                statements.append(
                    sql.SQL("GRANT ALL PRIVILEGES ON SCHEMA PUBLIC TO {};").format(
                        sql.Identifier(user)
                    )
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
        logger.debug("on.database.created handled")
        if self.unit.is_leader():
            logger.debug("Leader elected creating database")
            self._create_database(event)
        self._stored.db_name = DATABASE_NAME
        self._stored.db_user = event.username
        self._stored.db_password = event.password
        # expected endpoint postgresql-k8s-primary:5432
        self._stored.db_host = event.endpoints.split(":")[0]
        self._stored.db_port = event.endpoints.split(":")[1]

        self._on_config_changed(event)

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
            # TODO server name and report stats will be received via configurator
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

    def _run_generate_synapse(self):
        """Run the generate command for synapse."""
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
        """Run the migrate command for synapse."""
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
        # Add Replication and Redis config
        config = self._current_synapse_main_config()
        if config is not None:
            current_yaml = yaml.safe_load(config)
            replication = {
                "port": self._SYNAPSE_REPLICATION_PORT,
                "type": "http",
                "resources": [{"names": ["replication"]}],
            }
            current_yaml["listeners"].append(replication)
            current_yaml["redis"] = self._get_redis_backend()
            self._container().push(self._SYNAPSE_MAIN_CONFIG_PATH, yaml.safe_dump(current_yaml))

            # Push worker config
            self._container().push(
                self._SYNAPSE_WORKER_CONFIG_PATH, self._worker_config(current_yaml)
            )

    def _worker_config(self, current_yaml: Dict):
        """Generate worker config.

        Returns:
            Yaml stream to push to the container
        """
        unit = os.environ["JUJU_UNIT_NAME"]
        unit_name = unit.split("/")[0]
        unit_id = unit.split("/")[1]
        config = {
            "worker_app": "synapse.app.generic_worker",
            "worker_listeners": [
                {
                    "port": self._SYNAPSE_PORT,
                    "resources": [{"names": ["client", "federation"]}],
                    "type": "http",
                    "x_forwarded": True,
                }
            ],
            "worker_name": f"generic_worker_{unit_name}_{unit_id}",
            "worker_replication_host": self._leader_address,
            "worker_replication_http_port": self._SYNAPSE_REPLICATION_PORT,
            "redis": current_yaml.get("redis"),
            "database": current_yaml.get("database"),
        }
        return yaml.safe_dump(config)

    def _current_synapse_main_config(self):
        """Retrieve the current version of /data/homeserver.yaml from server.

        return None if not exists.

        Returns:
        The content of the current homeserver.yaml file, str.
        """
        synapse_config_path = self._SYNAPSE_MAIN_CONFIG_PATH
        container = self._container()
        if container.exists(synapse_config_path):
            return self._container().pull(synapse_config_path).read()
        return None

    def _get_synapse_nginx_pebble_config(self) -> Dict:
        """Generate pebble config for the synapse-nginx container.

        Returns:
            The pebble configuration for the container.
        """
        return {
            "summary": "Synapse nginx layer",
            "description": "Synapse nginx layer",
            "services": {
                "synapse-nginx": {
                    "override": "replace",
                    "summary": "Nginx service",
                    "command": "/usr/sbin/nginx",
                    "startup": "enabled",
                    "environment": {"LEADER_ADDRESS": self._leader_address},
                },
            },
            "checks": {
                "nginx-ready": {
                    "override": "replace",
                    "level": "alive",
                    "http": {"url": "http://localhost:8080/health"},
                },
            },
        }

    def _on_install(self, _):
        """Generate a config template to be rendered later."""
        logger.debug("Generating synapse config")
        self._run_generate_synapse()
        self._on_config_changed()

    def _on_leader_elected(self, _) -> None:
        """Handle leader-elected event."""
        peer_relation = self.model.get_relation("synapse-peers")
        if peer_relation and not peer_relation.data[self.app].get("leader-address"):
            peer_relation.data[self.app].update({"leader-address": self._address})

    def _on_config_changed(self, event):
        """Handle changed configuration."""
        # TODO Handle configurator event

        # Fetch the new config value
        log_level = self.model.config["log-level"].lower()

        if self._get_redis_rel() is None:
            event.defer()
            self.unit.status = WaitingStatus("waiting for redis")
            return

        if not self._stored.db_password:
            event.defer()
            self.unit.status = WaitingStatus("waiting for db")
            return

        # The config is good, so update the configuration of the workload
        container = self.unit.get_container(self._CONTAINER_NAME)
        # Verify that we can connect to the Pebble API
        # in the workload container
        if container.can_connect():
            self._run_migrate_synapse()
            # Push an updated layer with the new config
            container.add_layer(self._CONTAINER_NAME, self._pebble_layer, combine=True)
            container.add_layer(
                "synapse-nginx", self._get_synapse_nginx_pebble_config(), combine=True
            )
            container.replan()
            self._create_main_nginx_conf()
            logger.debug("Log level for synapse changed to '%s'", log_level)
            self.unit.status = ActiveStatus()
        else:
            # We were unable to connect to the Pebble API,
            # so we defer this event
            event.defer()
            self.unit.status = WaitingStatus("waiting for Pebble API")

    def _execute_command_nginx(self,cmd: list) -> None:
        container = self.unit.get_container("synapse-nginx")

        if container.can_connect():
            Result = collections.namedtuple("CommandExecResult", "return_code stdout stderr")

            process = container.exec(
                cmd,
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

    def _create_main_nginx_conf(self):
        """Create main nginx conf"""
        cmd = [
            "envsubst",
            "<",
            "/etc/nginx/conf/main_location.conf.template",
            ">",
            "/etc/nginx/conf/main_location.conf",
        ]
        self._execute_command_nginx(cmd)
        self._execute_command_nginx(["/usr/sbin/nginx","reload"])

    def _register_user(self, event):
        """Register a user for usage with Synapse."""
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
            self._SYNAPSE_MAIN_CONFIG_PATH,
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


if __name__ == "__main__":  # pragma: nocover
    main(MatrixOperatorCharm)
