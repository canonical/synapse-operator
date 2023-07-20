#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for Synapse on kubernetes."""

import logging
import typing

import ops
import psycopg2
from charms.nginx_ingress_integrator.v0.nginx_route import require_nginx_route
from charms.traefik_k8s.v1.ingress import IngressPerAppRequirer
from ops.charm import ActionEvent
from ops.main import main

# pydantic is causing this no-name-in-module problem
from pydantic import ValidationError  # pylint: disable=no-name-in-module,import-error

import synapse
from charm_state import CharmConfigInvalidError, CharmState
from constants import SYNAPSE_CONTAINER_NAME, SYNAPSE_PORT
from database_client import DatabaseClient
from database_observer import DatabaseObserver
from pebble import PebbleService
from user import User

logger = logging.getLogger(__name__)


class SynapseCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: typing.Any) -> None:
        """Construct.

        Args:
            args: class arguments.
        """
        super().__init__(*args)
        self.database = DatabaseObserver(self)
        try:
            self._charm_state = CharmState.from_charm(charm=self)
        except CharmConfigInvalidError as exc:
            self.model.unit.status = ops.BlockedStatus(exc.msg)
            return
        self.pebble_service = PebbleService(charm_state=self._charm_state)
        # service-hostname is a required field so we're hardcoding to the same
        # value as service-name. service-hostname should be set via Nginx
        # Ingress Integrator charm config.
        require_nginx_route(
            charm=self,
            service_hostname=self.app.name,
            service_name=self.app.name,
            service_port=SYNAPSE_PORT,
        )
        self._ingress = IngressPerAppRequirer(
            self,
            port=SYNAPSE_PORT,
            # We're forced to use the app's service endpoint
            # as the ingress per app interface currently always routes to the leader.
            # https://github.com/canonical/traefik-k8s-operator/issues/159
            host=f"{self.app.name}-endpoints.{self.model.name}.svc.cluster.local",
            strip_prefix=True,
        )
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.reset_instance_action, self._on_reset_instance_action)
        self.framework.observe(self.on.synapse_pebble_ready, self._on_pebble_ready)
        self.framework.observe(self.on.register_user_action, self._on_register_user_action)

    def change_config(self, _: ops.HookEvent) -> None:
        """Change configuration."""
        container = self.unit.get_container(SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for pebble")
            return
        self.model.unit.status = ops.MaintenanceStatus("Configuring Synapse")
        try:
            self.pebble_service.change_config(container)
        except (
            CharmConfigInvalidError,
            synapse.CommandMigrateConfigError,
            ops.pebble.PathError,
            synapse.ServerNameModifiedError,
        ) as exc:
            self.model.unit.status = ops.BlockedStatus(str(exc))
            return
        self.model.unit.status = ops.ActiveStatus()

    def _on_config_changed(self, event: ops.HookEvent) -> None:
        """Handle changed configuration.

        Args:
            event: Event triggering after config is changed.
        """
        self.change_config(event)

    def _on_pebble_ready(self, event: ops.HookEvent) -> None:
        """Handle pebble ready event.

        Args:
            event: Event triggering after pebble is ready.
        """
        self.change_config(event)

    def _on_reset_instance_action(self, event: ActionEvent) -> None:
        """Reset instance and report action result.

        Args:
            event: Event triggering the reset instance action.
        """
        results = {
            "reset-instance": False,
        }
        if not self.model.unit.is_leader():
            event.fail("Only the juju leader unit can run reset instance action")
            return
        container = self.unit.get_container(SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            event.fail("Failed to connect to container")
            return
        try:
            self.model.unit.status = ops.MaintenanceStatus("Resetting Synapse instance")
            self.pebble_service.reset_instance(container)
            datasource = self.database.get_relation_as_datasource()
            if datasource is not None:
                logger.info("Erase Synapse database")
                # Connecting to template1 to make it possible to erase the database.
                # Otherwise PostgreSQL will prevent it if there are open connections.
                db_client = DatabaseClient(datasource=datasource, alternative_database="template1")
                db_client.erase()
            synapse.execute_migrate_config(container=container, charm_state=self._charm_state)
            logger.info("Start Synapse database")
            self.pebble_service.replan(container)
            results["reset-instance"] = True
        except (psycopg2.Error, ops.pebble.PathError, synapse.CommandMigrateConfigError) as exc:
            self.model.unit.status = ops.BlockedStatus(str(exc))
            event.fail(str(exc))
            return
        # results is a dict and set_results expects _SerializedData
        event.set_results(results)  # type: ignore[arg-type]
        self.model.unit.status = ops.ActiveStatus()

    def _on_register_user_action(self, event: ActionEvent) -> None:
        """Reset instance and report action result.

        Args:
            event: Event triggering the reset instance action.
        """
        container = self.unit.get_container(SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for pebble")
            return
        registration_shared_secret = synapse.get_registration_shared_secret(container=container)
        if registration_shared_secret is None:
            event.fail("registration_shared_secret was not found, please check the logs")
            return
        user_data = {
            "username": event.params["username"],
            "admin": event.params["admin"],
        }
        try:
            user = User(**user_data)
            synapse.register_user(registration_shared_secret=registration_shared_secret, user=user)
        except (ValidationError, synapse.SynapseAPIError) as exc:
            event.fail(str(exc))
            return
        results = {"register-user": True, "user-password": user.password}
        # results is a dict and set_results expects _SerializedData
        event.set_results(results)  # type: ignore[arg-type]


if __name__ == "__main__":  # pragma: nocover
    main(SynapseCharm)
