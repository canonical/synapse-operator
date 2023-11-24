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
from database_observer import DatabaseObserver
from mjolnir import Mjolnir
from observability import Observability
from pebble import PebbleService, PebbleServiceError
from saml_observer import SAMLObserver
from user import User

JUJU_HAS_SECRETS = JujuVersion.from_environ().has_secrets
PEER_RELATION_NAME = "synapse-peers"
# Disabling it since these are not hardcoded password
SECRET_ID = "secret-id"  # nosec
SECRET_KEY = "secret-key"  # nosec

logger = logging.getLogger(__name__)


class SynapseCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args: typing.Any) -> None:
        """Construct.

        Args:
            args: class arguments.
        """
        super().__init__(*args)
        self._database = DatabaseObserver(self)
        self._saml = SAMLObserver(self)
        try:
            self._charm_state = CharmState.from_charm(
                charm=self,
                datasource=self._database.get_relation_as_datasource(),
                saml_config=self._saml.get_relation_as_saml_conf(),
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
        container = self.unit.get_container(synapse.SYNAPSE_NGINX_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for Synapse NGINX pebble")
            return
        self.pebble_service.replan_nginx(container)
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

    def _on_synapse_nginx_pebble_ready(self, _: ops.HookEvent) -> None:
        """Handle synapse nginx pebble ready event."""
        container = self.unit.get_container(synapse.SYNAPSE_NGINX_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for Synapse NGINX pebble")
            return
        self.pebble_service.replan_nginx(container)

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

    def _create_admin_user(self) -> typing.Optional[User]:
        """Create admin user.

        Returns:
            Admin user with token to be used in Synapse API requests or None if fails.
        """
        container = self.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            logger.error("Failed to connect to the container")
            return None
        # The username is random because if the user exists, register_user will try to get the
        # access_token.
        # But to do that it needs an admin user and we don't have one yet.
        # So, to be on the safe side, the user name is randomly generated and if for any reason
        # there is no access token on peer data/secret, another user will be created.
        #
        # Using 16 to create a random value but to  be secure against brute-force attacks,
        # please check the docs:
        # https://docs.python.org/3/library/secrets.html#how-many-bytes-should-tokens-use
        username = token_hex(16)
        return actions.register_user(container, username, True)

    def get_admin_access_token(self) -> typing.Optional[str]:
        """Get admin access token.

        Returns:
            admin access token or None if fails.
        """
        peer_relation = self.model.get_relation(PEER_RELATION_NAME)
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
                except ops.model.SecretNotFoundError as exc:
                    logger.exception("Failed to get secret id %s: %s", secret_id, str(exc))
                    del peer_relation.data[self.app][SECRET_ID]
                    return None
            else:
                # There is Secrets support but none was created
                # So lets create the user and store its token in the secret
                admin_user = self._create_admin_user()
                if not admin_user:
                    return None
                logger.debug("Adding secret")
                secret = self.app.add_secret({SECRET_KEY: admin_user.access_token})
                peer_relation.data[self.app].update({SECRET_ID: secret.id})
                admin_access_token = admin_user.access_token
        else:
            # There is no Secrets support and none relation data was created
            # So lets create the user and store its token in the peer relation
            secret_value = peer_relation.data[self.app].get(SECRET_KEY)
            if secret_value:
                admin_access_token = secret_value
            else:
                admin_user = self._create_admin_user()
                if not admin_user:
                    return None
                logger.debug("Adding peer data")
                peer_relation.data[self.app].update({SECRET_KEY: admin_user.access_token})
                admin_access_token = admin_user.access_token
        return admin_access_token

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
