#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for Synapse on kubernetes."""

import logging
import typing
from secrets import token_hex

import ops
from charms.nginx_ingress_integrator.v0.nginx_route import require_nginx_route
from charms.traefik_k8s.v1.ingress import IngressPerAppRequirer
from ops.charm import ActionEvent
from ops.jujuversion import JujuVersion
from ops.main import main

import actions
import synapse
from charm_state import CharmConfigInvalidError, CharmState
from constants import (
    MJOLNIR_MANAGEMENT_ROOM,
    MJOLNIR_MEMBERSHIP_ROOM,
    MJOLNIR_USER,
    SYNAPSE_CONTAINER_NAME,
    SYNAPSE_NGINX_CONTAINER_NAME,
    SYNAPSE_NGINX_PORT,
)
from database_observer import DatabaseObserver
from observability import Observability
from pebble import PebbleService, PebbleServiceError
from saml_observer import SAMLObserver

logger = logging.getLogger(__name__)

SECRET_KEY = "secret-key"  # nosec
SECRET_ID = "secret-id"  # nosec
PEER_RELATION_NAME = "synapse-peers"


class SynapseCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: typing.Any) -> None:
        """Construct.

        Args:
            args: class arguments.
        """
        super().__init__(*args)
        self.database = DatabaseObserver(self)
        self.saml = SAMLObserver(self)
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
            service_port=SYNAPSE_NGINX_PORT,
        )
        self._ingress = IngressPerAppRequirer(
            self,
            port=SYNAPSE_NGINX_PORT,
            # We're forced to use the app's service endpoint
            # as the ingress per app interface currently always routes to the leader.
            # https://github.com/canonical/traefik-k8s-operator/issues/159
            host=f"{self.app.name}-endpoints.{self.model.name}.svc.cluster.local",
            strip_prefix=True,
        )
        self._observability = Observability(self)
        self.framework.observe(self.on.leader_elected, self._on_leader_elected)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.reset_instance_action, self._on_reset_instance_action)
        self.framework.observe(self.on.synapse_pebble_ready, self._on_pebble_ready)
        self.framework.observe(self.on.register_user_action, self._on_register_user_action)

    def replan_nginx(self) -> None:
        """Replan NGINX."""
        container = self.unit.get_container(SYNAPSE_NGINX_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for pebble")
            return
        self.model.unit.status = ops.MaintenanceStatus("Configuring Synapse NGINX")
        self.pebble_service.replan_nginx(container)
        self.model.unit.status = ops.ActiveStatus()

    def change_config(self) -> None:
        """Change configuration."""
        container = self.unit.get_container(SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for pebble")
            return
        self.model.unit.status = ops.MaintenanceStatus("Configuring Synapse")
        try:
            self.pebble_service.change_config(container)
        except PebbleServiceError as exc:
            self.model.unit.status = ops.BlockedStatus(str(exc))
            return
        self.replan_nginx()

    def _set_workload_version(self) -> None:
        """Set workload version with Synapse version."""
        container = self.unit.get_container(SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for pebble")
            return
        try:
            synapse_version = synapse.get_version()
            self.unit.set_workload_version(synapse_version)
        except synapse.APIError as exc:
            logger.debug("Cannot set workload version at this time: %s", exc)

    def _on_config_changed(self, event: ops.HookEvent) -> None:
        """Handle changed configuration.

        Args:
            event: Event triggering after config is changed.
        """
        self.change_config()
        self._set_workload_version()
        if self._charm_state.enable_mjolnir:
            self._enable_mjolnir(event)

    def _has_secrets(self) -> bool:
        """Check if current Juju version supports secrets.

        Returns:
            If secrets are supported or not.
        """
        juju_version = JujuVersion.from_environ()
        # Because we're only using secrets in a peer relation we don't need to
        # check if the other end of a relation also supports secrets.
        return juju_version.has_secrets

    def _on_leader_elected(self, _: ops.LeaderElectedEvent) -> None:
        """Handle leader-elected event."""
        logger.debug("Leader elected event.")
        container = self.unit.get_container(SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for pebble")
            return
        # Using 16 to create a random value but to  be secure against brute-force attacks, please
        # check the docs:
        # https://docs.python.org/3/library/secrets.html#how-many-bytes-should-tokens-use
        username = token_hex(16)
        admin_user = actions.register_user(container, username, True)
        # If there is no secret, we use peer relation data
        # If there is secret, then we update the secret and add the secret id to peer data
        peer_relation = self.model.get_relation(PEER_RELATION_NAME)
        if (
            peer_relation
            and not self._has_secrets()
            and not peer_relation.data[self.app].get(SECRET_KEY)
        ):
            logger.debug("Updating peer relation data")
            peer_relation.data[self.app].update({SECRET_KEY: admin_user.access_token})
        elif (
            peer_relation
            and self._has_secrets()
            and not peer_relation.data[self.app].get(SECRET_ID)
        ):
            logger.debug("Adding secret")
            secret = self.app.add_secret({SECRET_KEY: admin_user.access_token})
            peer_relation.data[self.app].update({SECRET_ID: secret.id})

    def _get_admin_access_token(self) -> str:
        """Get admin access token.

        Returns:
            admin access token.
        """
        peer_relation = self.model.get_relation(PEER_RELATION_NAME)
        assert peer_relation is not None  # nosec
        if not self._has_secrets():
            secret_value = peer_relation.data[self.app].get(SECRET_KEY)
        else:
            secret_id = peer_relation.data[self.app].get(SECRET_ID)
            if secret_id:
                secret = self.model.get_secret(id=secret_id)
                secret_value = secret.get_content().get(SECRET_KEY)
        return secret_value

    def _enable_mjolnir(self, event: ops.HookEvent) -> None:
        """Enable mjolnir service.

        The required steps to enable Mjolnir are:
         - Get an admin access token.
         - Check if the MJOLNIR_MEMBERSHIP_ROOM room is created.
         -- Only users from there will be allowed to join the management room.
         - Create Mjolnir user or get its access token if already exists.
         - Create the management room or get its room id if already exists.
         -- The management room will allow only members of MJOLNIR_MEMBERSHIP_ROOM room to join it.
         - Make the Mjolnir user admin of this room.
         - Create the Mjolnir configuration file.
         - Override Mjolnir user rate limit.
         - Finally, add Mjolnir pebble layer.

        Args:
            event: Event triggering after config is changed.
        """
        container = self.unit.get_container(SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for pebble")
            return
        # Not checking if the pebble service is enabled to skip this
        # in case there is a charm update that changes Mjolnir configuration
        self.model.unit.status = ops.MaintenanceStatus("Configuring Mjolnir")
        admin_access_token = self._get_admin_access_token()
        try:
            synapse.get_room_id(
                room_name=MJOLNIR_MEMBERSHIP_ROOM, admin_access_token=admin_access_token
            )
        except synapse.RoomNotFoundError:
            logger.info("Room %s not found, waiting for user action", MJOLNIR_MEMBERSHIP_ROOM)
            self.model.unit.status = ops.BlockedStatus(
                f"{MJOLNIR_MEMBERSHIP_ROOM} not found and "
                "is required by Mjolnir. Please, create it."
            )
            event.defer()
            return
        mjolnir_user = actions.register_user(
            container,
            MJOLNIR_USER,
            True,
            str(self._charm_state.server_name),
            admin_access_token,
        )
        mjolnir_access_token = mjolnir_user.access_token
        try:
            # Considering that the management room exists
            room_id = synapse.get_room_id(
                room_name=MJOLNIR_MANAGEMENT_ROOM, admin_access_token=admin_access_token
            )
        except synapse.RoomNotFoundError:
            logger.info("Room %s not found, creating", MJOLNIR_MANAGEMENT_ROOM)
            room_id = synapse.create_management_room(admin_access_token=admin_access_token)
        # Add the Mjolnir user to the management room
        synapse.make_room_admin(
            user=mjolnir_user,
            server=str(self._charm_state.server_name),
            admin_access_token=admin_access_token,
            room_id=room_id,
        )
        synapse.create_mjolnir_config(
            container=container, access_token=mjolnir_access_token, room_id=room_id
        )
        synapse.override_rate_limit(
            user=mjolnir_user, admin_access_token=admin_access_token, charm_state=self._charm_state
        )
        self.pebble_service.replan_mjolnir(container)
        self.model.unit.status = ops.ActiveStatus()

    def _on_pebble_ready(self, _: ops.HookEvent) -> None:
        """Handle pebble ready event."""
        self.change_config()

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
            actions.reset_instance(
                container=container, charm_state=self._charm_state, datasource=datasource
            )
            logger.info("Start Synapse")
            self.pebble_service.restart_synapse(container)
            results["reset-instance"] = True
        except (PebbleServiceError, actions.ResetInstanceError) as exc:
            self.model.unit.status = ops.BlockedStatus(str(exc))
            event.fail(str(exc))
            return
        event.set_results(results)
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
        try:
            user = actions.register_user(
                container=container, username=event.params["username"], admin=event.params["admin"]
            )
        except actions.RegisterUserError as exc:
            event.fail(str(exc))
            return
        results = {"register-user": True, "user-password": user.password}
        event.set_results(results)


if __name__ == "__main__":  # pragma: nocover
    main(SynapseCharm)
