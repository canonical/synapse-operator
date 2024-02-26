#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for Synapse on kubernetes."""

# ignoring duplicate-code with container connect check in the mjolnir observer.
# pylint: disable=R0801

import logging
import typing

import ops
from charms.nginx_ingress_integrator.v0.nginx_route import require_nginx_route
from charms.traefik_k8s.v1.ingress import IngressPerAppRequirer
from ops.charm import ActionEvent
from ops.main import main

import actions
import synapse
from admin_access_token import AdminAccessTokenService
from backup_observer import BackupObserver
from charm_state import CharmConfigInvalidError, CharmState
from database_observer import DatabaseObserver
from mjolnir import Mjolnir
from observability import Observability
from pebble import PebbleService, PebbleServiceError
from redis_observer import RedisObserver
from saml_observer import SAMLObserver
from smtp_observer import SMTPObserver
from user import User

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
        self._redis = RedisObserver(self)
        self.framework.observe(
            self.on.synapse_nginx_pebble_ready, self._on_synapse_nginx_pebble_ready
        )
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
        self.token_service = AdminAccessTokenService(app=self.app, model=self.model)
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
        if self._charm_state.synapse_config.enable_mjolnir:
            self._mjolnir = Mjolnir(
                self, charm_state=self._charm_state, token_service=self.token_service
            )
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.reset_instance_action, self._on_reset_instance_action)
        self.framework.observe(self.on.synapse_pebble_ready, self._on_synapse_pebble_ready)
        self.framework.observe(self.on.register_user_action, self._on_register_user_action)
        self.framework.observe(
            self.on.promote_user_admin_action, self._on_promote_user_admin_action
        )
        self.framework.observe(self.on.anonymize_user_action, self._on_anonymize_user_action)
        self.framework.observe(self.on.collect_unit_status, self._on_collect_status)

    def _on_collect_status(self, _: ops.CollectStatusEvent) -> None:
        """Collect status event handler."""
        container = self.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            logger.warning("Synapse Stats Exporter: Waiting for Synapse pebble")
            return
        synapse_service = container.get_services(synapse.SYNAPSE_SERVICE_NAME)
        synapse_not_active = [
            service for service in synapse_service.values() if not service.is_running()
        ]
        if not synapse_service or synapse_not_active:
            # The get_membership_room_id does a call to Synapse API in order to get the
            # membership room id. This only works if Synapse is running so that's why
            # the service status is checked here.
            logger.warning("Synapse Stats Exporter: Waiting for Synapse")
            return
        stats_service = container.get_services(synapse.STATS_EXPORTER_SERVICE_NAME)
        stats_not_active = [
            service for service in stats_service.values() if not service.is_running()
        ]
        if not stats_service or stats_not_active:
            logger.warning("Synapse Stats Exporter not running, restarting.")
            self.pebble_service.replan_stats_exporter(container, self.token_service)
        self._set_unit_status()

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
        if nginx_not_active or not nginx_service:
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

    def _on_synapse_pebble_ready(self, _: ops.HookEvent) -> None:
        """Handle synapse pebble ready event."""
        self.change_config()

    def _on_synapse_nginx_pebble_ready(self, event: ops.HookEvent) -> None:
        """Handle synapse nginx pebble ready event.

        Args:
            event: Event triggering the synapse nginx pebble ready.
        """
        container = self.unit.get_container(synapse.SYNAPSE_NGINX_CONTAINER_NAME)
        if not container.can_connect():
            logger.debug("synapse_nginx_pebble_ready failed to connect, defer")
            event.defer()
            return
        nginx_service = container.get_services(synapse.SYNAPSE_NGINX_SERVICE_NAME)
        nginx_not_active = [
            service for service in nginx_service.values() if not service.is_running()
        ]
        if nginx_not_active or not nginx_service:
            logger.debug("synapse_nginx_pebble_ready replanning nginx")
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
            admin_access_token = self.token_service.get(container)
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
            admin_access_token = self.token_service.get(container)
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
