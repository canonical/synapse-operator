#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for Synapse on kubernetes."""


import logging
import typing

import ops
from charms.nginx_ingress_integrator.v0.nginx_route import require_nginx_route
from charms.redis_k8s.v0.redis import RedisRelationCharmEvents
from charms.traefik_k8s.v2.ingress import IngressPerAppRequirer
from ops import main
from ops.charm import ActionEvent, RelationDepartedEvent

import actions
import pebble
import synapse
from admin_access_token import AdminAccessTokenService
from backup_observer import BackupObserver
from charm_state import CharmBaseWithState, CharmState, inject_charm_state
from database_observer import DatabaseObserver
from matrix_auth_observer import MatrixAuthObserver
from media_observer import MediaObserver
from mjolnir import Mjolnir
from observability import Observability
from redis_observer import RedisObserver
from saml_observer import SAMLObserver
from smtp_observer import SMTPObserver
from user import User

logger = logging.getLogger(__name__)

INGRESS_INTEGRATION_NAME = "ingress"
MAIN_UNIT_ID = 0
SYNAPSE_VERSION = "1.132.0"


class SynapseCharm(CharmBaseWithState):
    """Charm the service.

    Attrs:
        on: listen to Redis events.
    """

    # This class has several instance attributes like observers and libraries.
    # Consider refactoring if more attributes are added.
    # pylint: disable=too-many-instance-attributes
    on = RedisRelationCharmEvents()

    def __init__(self, *args: typing.Any) -> None:
        """Construct.

        Args:
            args: class arguments.
        """
        super().__init__(*args)
        self.unit.set_workload_version(SYNAPSE_VERSION)
        self._backup = BackupObserver(self)
        self._matrix_auth = MatrixAuthObserver(self)
        self._media = MediaObserver(self)
        self._database = DatabaseObserver(self, relation_name=synapse.SYNAPSE_DB_RELATION_NAME)
        self._saml = SAMLObserver(self)
        self._smtp = SMTPObserver(self)
        self._redis = RedisObserver(self)
        self.token_service = AdminAccessTokenService(app=self.app, model=self.model)
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
            charm=self,
            relation_name=INGRESS_INTEGRATION_NAME,
            port=synapse.SYNAPSE_NGINX_PORT,
        )
        self._observability = Observability(self)
        self._mjolnir = Mjolnir(self, token_service=self.token_service)
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(self.on.upgrade_charm, self._on_config_changed)
        self.framework.observe(
            self.on[synapse.SYNAPSE_PEER_RELATION_NAME].relation_departed,
            self._on_relation_departed,
        )
        self.framework.observe(
            self.on[synapse.SYNAPSE_PEER_RELATION_NAME].relation_changed, self._on_relation_changed
        )
        self.framework.observe(self.on.synapse_pebble_ready, self._on_synapse_pebble_ready)
        self.framework.observe(self.on.register_user_action, self._on_register_user_action)
        self.framework.observe(
            self.on.promote_user_admin_action, self._on_promote_user_admin_action
        )
        self.framework.observe(self.on.anonymize_user_action, self._on_anonymize_user_action)

    def build_charm_state(self) -> CharmState:
        """Build charm state.

        Returns:
            The current charm state.
        """
        return CharmState.from_charm(
            charm=self,
            datasource=self._database.get_relation_as_datasource(),
            saml_config=self._saml.get_relation_as_saml_conf(),
            smtp_config=self._smtp.get_relation_as_smtp_conf(),
            media_config=self._media.get_relation_as_media_conf(),
            redis_config=self._redis.get_relation_as_redis_conf(),
            registration_secrets=self._matrix_auth.get_requirer_registration_secrets(),
            instance_map_config=self._instance_map(),
        )

    @inject_charm_state
    def _on_config_changed(self, _: ops.HookEvent, charm_state: CharmState) -> None:
        """Handle changed configuration.

        Args:
            charm_state: The charm state.
        """
        self.reconcile(charm_state)

    @inject_charm_state
    def _on_synapse_pebble_ready(self, _: ops.HookEvent, charm_state: CharmState) -> None:
        """Handle synapse pebble ready event.

        Args:
            charm_state: The charm state.
        """
        self.reconcile(charm_state)

    @inject_charm_state
    def _on_relation_departed(self, event: RelationDepartedEvent, charm_state: CharmState) -> None:
        """Handle Synapse peer relation departed event.

        Args:
            event: relation departed event.
            charm_state: The charm state.
        """
        if event.departing_unit == self.unit:
            return
        self.reconcile(charm_state)

    @inject_charm_state
    def _on_relation_changed(self, _: ops.HookEvent, charm_state: CharmState) -> None:
        """Handle Synapse peer relation changed event.

        Args:
            charm_state: The charm state.
        """
        self.reconcile(charm_state)

    def reconcile(self, charm_state: CharmState) -> None:
        """Reconcile Synapse configuration with charm state.

        This is the main entry for changes that require a restart.

        Args:
            charm_state: Instance of CharmState
        """
        container = self.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        if self._is_redis_required(charm_state):
            self.unit.status = ops.BlockedStatus("Redis integration is required.")
            return
        self.model.unit.status = ops.MaintenanceStatus("Configuring Synapse")
        try:
            self._configure_and_start_services(charm_state, container)
        except (pebble.PebbleServiceError, FileNotFoundError) as exc:
            self.model.unit.status = ops.BlockedStatus(str(exc))
            return
        if self.unit.is_leader():
            self._matrix_auth.update_matrix_auth_integration(charm_state)
        self._set_unit_status()

    def _signing_key_path(self, charm_state: CharmState) -> str:
        """Get signing key path.

        Args:
            charm_state: charm state.
        """
        return f"/data/{charm_state.synapse_config.server_name}.signing.key"

    def _get_signing_key_secret_content(self) -> typing.Optional[str]:
        """Get signing key secret content.

        Returns:
            Content as string.
        """
        content = None
        peer_relation = self._peers()
        if not peer_relation:
            logger.error(
                "Failed to get signing key: no peer relation %s found",
                synapse.SYNAPSE_PEER_RELATION_NAME,
            )
            return content
        secret_id = peer_relation.data[self.app].get("secret-signing-id")
        if secret_id:
            try:
                secret = self.model.get_secret(id=secret_id)
                logging.debug(secret.get_content().get("secret-signing-key"))
                content = secret.get_content().get("secret-signing-key")
            except (ops.model.SecretNotFoundError, ValueError, TypeError) as exc:
                logger.exception("Failed to get secret id %s: %s", secret_id, str(exc))
                del peer_relation.data[self.app]["secret-signing-id"]
        return content

    def write_signing_key_to_container(
        self, charm_state: CharmState, container: ops.Container
    ) -> None:
        """Get signing key from secret.

        Args:
            charm_state: charm state.
            container: container.
        """
        content = self._get_signing_key_secret_content()
        if content:
            container.push(
                self._signing_key_path(charm_state),
                content,
                make_dirs=True,
                encoding="utf-8",
            )

    def set_signing_key_from_container(
        self, charm_state: CharmState, container: ops.Container
    ) -> None:
        """Create secret with signing key content.

        Args:
            charm_state: charm state.
            container: container.
        """
        peer_relation = self._peers()
        if not peer_relation:
            logger.error(
                "Failed to set signing key: no peer relation %s found",
                synapse.SYNAPSE_PEER_RELATION_NAME,
            )
            return
        signing_key = ""
        with container.pull(self._signing_key_path(charm_state)) as f:
            signing_key = f.read()
            signing_key = signing_key.rstrip()
        if signing_key == self._get_signing_key_secret_content():
            logger.info("Received signing key but there is no change, skipping")
            return
        if self.unit.is_leader():
            logger.debug("Adding signing key to secret: %s", signing_key)
            secret = self.app.add_secret({"secret-signing-key": signing_key})
            peer_relation.data[self.app].update({"secret-signing-id": typing.cast(str, secret.id)})

    def _configure_and_start_services(
        self, charm_state: CharmState, container: ops.Container
    ) -> None:
        """Configure and start pebble layers."""
        self.write_signing_key_to_container(charm_state, container)
        pebble.reconcile(
            charm_state, container, is_main=self._is_main(), unit_number=self._get_unit_number()
        )
        if self._is_main() and charm_state.synapse_config.enable_mjolnir:
            self._mjolnir.enable(charm_state)
        pebble.restart_nginx(container, self._get_unit_address(MAIN_UNIT_ID))
        self.set_signing_key_from_container(charm_state, container)

    def _is_redis_required(self, charm_state: CharmState) -> bool:
        """Check if Redis configuration should be required.

        Return:
            True if more than 1 unit is found.
        """
        return charm_state.redis_config is None and self.app.planned_units() > 1

    def _peers(self) -> typing.Optional[ops.Relation]:
        """Get peer relation.

        Returns:
            Synapse peer relation.
        """
        return self.model.get_relation(synapse.SYNAPSE_PEER_RELATION_NAME)

    def _is_main(self) -> bool:
        """Verify if this unit is the main.

        Returns:
            bool: true if is the main unit.
        """
        return f"/{MAIN_UNIT_ID}" in self.unit.name

    def _get_unit_address(self, unit_id: int) -> str:
        """Get unit address.

        Args:
            unit_id: number as 0 in synapse/0.

        Returns:
            unit address as unit-0.synapse-endpoints.
        """
        return f"{self.app.name}-{unit_id}.{self.app.name}-endpoints"

    def _get_unit_number(self) -> str:
        """Get unit number.

        Returns:
            unit number as 0 in synapse/0.
        """
        return self.unit.name.split("/")[1]

    def _instance_map(self) -> typing.Optional[typing.Dict]:
        """Create instance_map configuration.

        Returns:
            Instance map configuration as a dict or None if there is only one unit.
        """
        peer_relation = self._peers()
        if not peer_relation or len(peer_relation.units) <= 1:
            logger.debug("One unit in peer relation, skipping instance_map configuration")
            return None
        instance_map = {}
        for unit_id in range(len(peer_relation.units)):
            if unit_id == MAIN_UNIT_ID:
                instance_map["main"] = {
                    "host": self._get_unit_address(MAIN_UNIT_ID),
                    "port": 8035,
                }
                instance_map["federationsender1"] = {
                    "host": self._get_unit_address(MAIN_UNIT_ID),
                    "port": 8034,
                }
                continue

            instance_name = f"worker{unit_id}"
            address = self._get_unit_address(unit_id)
            instance_map[instance_name] = {
                "host": address,
                "port": 8034,
            }
        return instance_map

    def _set_unit_status(self) -> None:
        """Set unit status depending on Synapse and NGINX state."""
        if isinstance(self.unit.status, ops.BlockedStatus):
            # Preserve error state set elsewhere
            return

        container = self.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return

        if not self._is_service_running(container, synapse.SYNAPSE_SERVICE_NAME):
            self.unit.status = ops.MaintenanceStatus("Waiting for Synapse")
            return

        if not self._is_service_running(container, synapse.SYNAPSE_NGINX_SERVICE_NAME):
            self.unit.status = ops.MaintenanceStatus("Waiting for NGINX")
            return

        self.unit.status = ops.ActiveStatus()

    def _is_service_running(self, container: ops.Container, service_name: str) -> bool:
        """Check if all instances of a service are running.

        Returns:
            True if all services are running.
        """
        services = container.get_services(service_name)
        return bool(services) and all(service.is_running() for service in services.values())

    def _on_register_user_action(self, event: ActionEvent) -> None:
        """Register user and report action result.

        Args:
            event: Event triggering the register user instance action.
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

    @inject_charm_state
    def _on_promote_user_admin_action(self, event: ActionEvent, charm_state: CharmState) -> None:
        """Promote user admin and report action result.

        Args:
            event: Event triggering the promote user admin action.
            charm_state: The charm state.
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
            server = charm_state.synapse_config.server_name
            user = User(username=username, admin=True)
            synapse.promote_user_admin(
                user=user, server=server, admin_access_token=admin_access_token
            )
            results["promote-user-admin"] = True
        except synapse.APIError as exc:
            event.fail(str(exc))
            return
        event.set_results(results)

    @inject_charm_state
    def _on_anonymize_user_action(self, event: ActionEvent, charm_state: CharmState) -> None:
        """Anonymize user and report action result.

        Args:
            event: Event triggering the anonymize user action.
            charm_state: The charm state.
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
            server = charm_state.synapse_config.server_name
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
