#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for Synapse on kubernetes."""

import logging
import typing

import ops
from charms.nginx_ingress_integrator.v0.nginx_route import require_nginx_route
from charms.traefik_k8s.v1.ingress import IngressPerAppRequirer
from ops.charm import ActionEvent
from ops.jujuversion import JujuVersion
from ops.main import main

import actions
import synapse
from backup_observer import BackupObserver
from charm_state import CharmConfigInvalidError, CharmState
from database_observer import DatabaseObserver
from mjolnir import Mjolnir
from observability import Observability
from pebble import PebbleService, PebbleServiceError
from saml_observer import SAMLObserver
from smtp_observer import SMTPObserver
from user import User

JUJU_HAS_SECRETS = JujuVersion.from_environ().has_secrets
PEER_RELATION_NAME = "synapse-peers"
# Disabling it since these are not hardcoded password
SECRET_ID = "secret-id"  # nosec
SECRET_KEY = "secret-key"  # nosec

logger = logging.getLogger(__name__)


class SynapseCharm(ops.CharmBase):
    """Charm the service."""

    # This class has several instance attributes like observers, libraries and state.
    # Consider refactoring if more attributes are added.
    # pylint: disable=too-many-instance-attributes

    def __init__(self, *args: typing.Any) -> None:
        """Construct.

        Args:
            args: class arguments.
        """
        super().__init__(*args)
        self._backup = BackupObserver(self)
        self._database = DatabaseObserver(self)
        self._saml = SAMLObserver(self)
        self._smtp = SMTPObserver(self)
        try:
            self._charm_state = CharmState.from_charm(
                charm=self,
                datasource=self._database.get_relation_as_datasource(),
                saml_config=self._saml.get_relation_as_saml_conf(),
                smtp_config=self._smtp.get_relation_as_smtp_conf(),
            )
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
            service_port=synapse.SYNAPSE_NGINX_PORT,
        )
        self._ingress = IngressPerAppRequirer(
            self,
            port=synapse.SYNAPSE_NGINX_PORT,
            # We're forced to use the app's service endpoint
            # as the ingress per app interface currently always routes to the leader.
            # https://github.com/canonical/traefik-k8s-operator/issues/159
            host=f"{self.app.name}-endpoints.{self.model.name}.svc.cluster.local",
            strip_prefix=True,
        )
        self._observability = Observability(self)
        # Mjolnir is a moderation tool for Matrix.
        # See https://github.com/matrix-org/mjolnir/ for more details about it.
        if self._charm_state.synapse_config.enable_mjolnir:
            self._mjolnir = Mjolnir(self, charm_state=self._charm_state)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.reset_instance_action, self._on_reset_instance_action)
        self.framework.observe(self.on.synapse_pebble_ready, self._on_synapse_pebble_ready)
        self.framework.observe(
            self.on.synapse_nginx_pebble_ready, self._on_synapse_nginx_pebble_ready
        )
        self.framework.observe(self.on.register_user_action, self._on_register_user_action)
        self.framework.observe(
            self.on.promote_user_admin_action, self._on_promote_user_admin_action
        )
        self.framework.observe(self.on.anonymize_user_action, self._on_anonymize_user_action)

    def change_config(self) -> None:
        """Change configuration."""
        container = self.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        self.model.unit.status = ops.MaintenanceStatus("Configuring Synapse")
        try:
            self.pebble_service.change_config(container)
        except PebbleServiceError as exc:
            self.model.unit.status = ops.BlockedStatus(str(exc))
            return
        self._set_unit_status()

    def _set_unit_status(self) -> None:
        """Set unit status depending on Synapse and NGINX state."""
        # This method contains a similar check that the one in mjolnir.py for Synapse
        # container and service. Until a refactoring is done for a different way of checking
        # and setting the unit status in a hollistic way, both checks will be in place.
        # pylint: disable=R0801

        # If the unit is in a blocked state, do not change it, as it
        # was set by a problem or error with the configuration
        if isinstance(self.unit.status, ops.BlockedStatus):
            return
        # Synapse checks
        container = self.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        synapse_service = container.get_services(synapse.SYNAPSE_SERVICE_NAME)
        synapse_not_active = [
            service for service in synapse_service.values() if not service.is_running()
        ]
        if not synapse_service or synapse_not_active:
            self.unit.status = ops.MaintenanceStatus("Waiting for Synapse")
            return
        # NGINX checks
        container = self.unit.get_container(synapse.SYNAPSE_NGINX_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for Synapse NGINX pebble")
            return
        nginx_service = container.get_services(synapse.SYNAPSE_NGINX_SERVICE_NAME)
        nginx_not_active = [
            service for service in nginx_service.values() if not service.is_running()
        ]
        if not nginx_service or nginx_not_active:
            self.unit.status = ops.MaintenanceStatus("Waiting for NGINX")
            return
        # All checks passed, the unit is active
        self.model.unit.status = ops.ActiveStatus()

    def _set_workload_version(self) -> None:
        """Set workload version with Synapse version."""
        container = self.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        try:
            synapse_version = synapse.get_version()
            self.unit.set_workload_version(synapse_version)
        except synapse.APIError as exc:
            logger.debug("Cannot set workload version at this time: %s", exc)

    def _on_config_changed(self, _: ops.HookEvent) -> None:
        """Handle changed configuration."""
        self.change_config()
        self._set_workload_version()

    def _get_peer_relation(self) -> typing.Optional[ops.Relation]:
        """Get peer relation.

        Returns:
            Relation or not if is not found.
        """
        return self.model.get_relation(PEER_RELATION_NAME)

    def get_admin_access_token(self) -> typing.Optional[str]:
        """Get admin access token.

        Returns:
            admin access token or None if fails.
        """
        peer_relation = self._get_peer_relation()
        if not peer_relation:
            logger.error(
                "Failed to get admin access token: no peer relation %s found", PEER_RELATION_NAME
            )
            return None
        admin_access_token = None
        if JUJU_HAS_SECRETS:
            secret_id = peer_relation.data[self.app].get(SECRET_ID)
            if secret_id:
                try:
                    secret = self.model.get_secret(id=secret_id)
                    admin_access_token = secret.get_content().get(SECRET_KEY)
                    return admin_access_token
                except ops.model.SecretNotFoundError as exc:
                    logger.exception("Failed to get secret id %s: %s", secret_id, str(exc))
                    del peer_relation.data[self.app][SECRET_ID]
                    return None
        else:
            # There is no Secrets support and none relation data was created
            # So lets create the user and store its token in the peer relation
            secret_value = peer_relation.data[self.app].get(SECRET_KEY)
            if secret_value:
                return secret_value
        return None

    def _start_synapse_stats_exporter(self) -> None:
        """Start Synapse Stats Exporter in Synapse container."""
        container = self.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            logger.error("Failed to connect to container while starting Synapse Stats Exporter")
            return
        self.pebble_service.replan_stats_exporter(container)

    def _set_admin_access_token(self, access_token: str) -> None:
        """Set admin access token.

        Args:
            access_token: token to save in the secret.
        """
        peer_relation = self._get_peer_relation()
        if not peer_relation:
            logger.error(
                "Failed to get admin access token: no peer relation %s found", PEER_RELATION_NAME
            )
            return
        if JUJU_HAS_SECRETS:
            logger.debug("Adding secret")
            secret = self.app.add_secret({SECRET_KEY: access_token})
            peer_relation.data[self.app].update({SECRET_ID: secret.id})
        else:
            logger.debug("Adding peer data")
            peer_relation.data[self.app].update({SECRET_KEY: access_token})

    def _on_synapse_pebble_ready(self, _: ops.HookEvent) -> None:
        """Handle synapse pebble ready event."""
        self.change_config()
        if self.get_admin_access_token():
            self._start_synapse_stats_exporter()
            return
        # Since Synapse is ready, the charm can create the admin access token
        container = self.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        admin_user = synapse.create_admin_user(container)
        if not admin_user:
            logger.error("Failed to create admin user.")
            return
        self._set_admin_access_token(admin_user.access_token)
        self._charm_state.synapse_config.admin_access_token = admin_user.access_token
        # Stats exporter needs access token so the charm will start it here
        self._start_synapse_stats_exporter()

    def _on_synapse_nginx_pebble_ready(self, _: ops.HookEvent) -> None:
        """Handle synapse nginx pebble ready event."""
        container = self.unit.get_container(synapse.SYNAPSE_NGINX_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for Synapse NGINX pebble")
            return
        self.pebble_service.replan_nginx(container)
        self._set_unit_status()

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
        container = self.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            event.fail("Failed to connect to the container")
            return
        try:
            self.model.unit.status = ops.MaintenanceStatus("Resetting Synapse instance")
            self.pebble_service.reset_instance(container)
            datasource = self._database.get_relation_as_datasource()
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
        container = self.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            event.fail("Failed to connect to the container")
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

    def _on_promote_user_admin_action(self, event: ActionEvent) -> None:
        """Promote user admin and report action result.

        Args:
            event: Event triggering the promote user admin action.
        """
        results = {
            "promote-user-admin": False,
        }
        container = self.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            event.fail("Failed to connect to the container")
            return
        try:
            admin_access_token = self.get_admin_access_token()
            if not admin_access_token:
                event.fail("Failed to get admin access token")
                return
            username = event.params["username"]
            server = self._charm_state.synapse_config.server_name
            user = User(username=username, admin=True)
            synapse.promote_user_admin(
                user=user, server=server, admin_access_token=admin_access_token
            )
            results["promote-user-admin"] = True
        except synapse.APIError as exc:
            event.fail(str(exc))
            return
        event.set_results(results)

    def _on_anonymize_user_action(self, event: ActionEvent) -> None:
        """Anonymize user and report action result.

        Args:
            event: Event triggering the anonymize user action.
        """
        results = {
            "anonymize-user": False,
        }
        container = self.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            event.fail("Container not yet ready. Try again later")
            return
        try:
            admin_access_token = self.get_admin_access_token()
            if not admin_access_token:
                event.fail("Failed to get admin access token")
                return
            username = event.params["username"]
            server = self._charm_state.synapse_config.server_name
            user = User(username=username, admin=False)
            synapse.deactivate_user(
                user=user, server=server, admin_access_token=admin_access_token
            )
            results["anonymize-user"] = True
        except synapse.APIError:
            event.fail("Failed to anonymize the user. Check if the user is created and active.")
            return
        event.set_results(results)


if __name__ == "__main__":  # pragma: nocover
    main(SynapseCharm)
