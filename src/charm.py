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
from ops.charm import ActionEvent

import actions
import pebble
import signing_key
import synapse
from admin_access_token import AdminAccessTokenService
from backup_observer import BackupObserver
from charm_state import (
    MAIN_UNIT_ID,
    CharmBaseWithState,
    CharmState,
    inject_charm_state,
)
from database_observer import DatabaseObserver
from matrix_auth_observer import MatrixAuthObserver
from media_observer import MediaObserver
from mjolnir import (
    Mjolnir,
    MjolnirEnableError,
    MjolnirModeratorsNotFoundError,
)
from observability import Observability
from redis_observer import RedisObserver
from saml_observer import SAMLObserver
from smtp_observer import SMTPObserver
from user import User

logger = logging.getLogger(__name__)

INGRESS_INTEGRATION_NAME = "ingress"
# This constant is updated by Renovate.
SYNAPSE_VERSION = "1.137.0"


class SynapseCharm(CharmBaseWithState):
    """Charm the service.

    Attrs:
        on: listen to Redis events.
        peer_relation: charm peer relation.
        is_main: if is main unit or not.
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
        self.framework.observe(self.on.config_changed, self._trigger_reconcile)
        self.framework.observe(self.on.upgrade_charm, self._trigger_reconcile)
        self.framework.observe(
            self.on[synapse.SYNAPSE_PEER_RELATION_NAME].relation_departed,
            self._trigger_reconcile,
        )
        self.framework.observe(
            self.on[synapse.SYNAPSE_PEER_RELATION_NAME].relation_changed, self._trigger_reconcile
        )
        self.framework.observe(self.on.synapse_pebble_ready, self._trigger_reconcile)
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
            instance_map_config=self.create_instance_map(),
        )

    @property
    def peer_relation(self) -> typing.Optional[ops.Relation]:
        """Get peer relation.

        Args:
            charm: charm instance.

        Returns:
            Synapse peer relation.
        """
        peer_relations = self.model.relations[synapse.SYNAPSE_PEER_RELATION_NAME]
        if not peer_relations:
            return None
        return peer_relations[0]

    @property
    def is_main(self) -> bool:
        """Check if this is the main unit.

        Returns:
            True if is main unit.
        """
        return f"/{MAIN_UNIT_ID}" in self.unit.name

    @inject_charm_state
    def _trigger_reconcile(self, event: ops.HookEvent, charm_state: CharmState) -> None:
        """Trigger or not reconcile based on events observed by the charm.

        Args:
            event: event triggers reconcile.
            charm_state: charm state.
        """
        if isinstance(event, ops.RelationDepartedEvent) and event.departing_unit == self.unit:
            return
        self.reconcile(charm_state)

    def reconcile(
        self, charm_state: CharmState, maintenance_status: str = "Configuring Synapse"
    ) -> None:
        """Reconcile Synapse configuration with charm state.

        This is the main entry for changes that require a restart.

        Args:
            charm_state: Instance of CharmState.
            maintenance_status: message to display during the reconcile.
        """
        self.unit.set_workload_version(SYNAPSE_VERSION)

        container = self.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for container")
            return

        if charm_state.redis_required:
            self.unit.status = ops.BlockedStatus("Redis integration is required.")
            return

        self.model.unit.status = ops.MaintenanceStatus(maintenance_status)

        self.configure_and_start_services(charm_state, container)

        if self.unit.is_leader():
            self._matrix_auth.update_matrix_auth_integration(charm_state)

        if charm_state.mjolnir_enabled:
            try:
                self._mjolnir.enable(charm_state)
            except MjolnirEnableError as e:
                self.model.unit.status = ops.MaintenanceStatus(str(e))
            except MjolnirModeratorsNotFoundError as e:
                self.unit.status = ops.BlockedStatus(str(e))

        self._set_unit_with_service_status(charm_state)

    def configure_and_start_services(
        self, charm_state: CharmState, container: ops.Container
    ) -> None:
        """Configure and start pebble layers.

        Args:
            charm_state: charm state.
            container: charm container.
        """
        if self.peer_relation:
            try:
                signing_key.write_to_container(self.peer_relation, self, charm_state, container)
            except signing_key.SigningKeyWriteError:
                # only changes the status instead of letting the charm in error
                # since the secret might be created in next events/steps
                self.model.unit.status = ops.MaintenanceStatus(
                    "Signing key secret not found, check the logs"
                )
        unit_number = self.unit.name.split("/")[1]
        pebble.reconcile(charm_state, container, is_main=self.is_main, unit_number=unit_number)
        pebble.restart_nginx(container, self._get_unit_address(MAIN_UNIT_ID))
        if self.peer_relation:
            signing_key.write_to_secret(self.peer_relation, self, charm_state, container)

    def _get_unit_address(self, unit_id: int) -> str:
        """Get unit address.

        Args:
            unit_id: number as 0 in synapse/0.

        Returns:
            unit address as unit-0.synapse-endpoints.
        """
        return f"{self.app.name}-{unit_id}.{self.app.name}-endpoints"

    def create_instance_map(self) -> typing.Optional[typing.Dict]:
        """Create instance_map configuration.

        Returns:
            Instance map configuration as a dict or None if there is only one unit.
        """
        planned_units = self.app.planned_units()
        if planned_units == 1:
            logger.debug("Only one unit is planned; skipping instance_map configuration.")
            return None

        instance_map = {
            "main": {
                "host": self._get_unit_address(MAIN_UNIT_ID),
                "port": 8035,
            },
            "federationsender1": {
                "host": self._get_unit_address(MAIN_UNIT_ID),
                "port": 8034,
            },
        }

        for unit_id in range(planned_units):
            if unit_id == MAIN_UNIT_ID:
                continue
            instance_name = f"worker{unit_id}"
            instance_map[instance_name] = {
                "host": self._get_unit_address(unit_id),
                "port": 8034,
            }

        return instance_map

    def _set_unit_with_service_status(self, charm_state: CharmState) -> None:
        """Set unit status message after checking services.

        Args:
            charm_state: charm state.
        """
        container = self.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return

        if isinstance(self.unit.status, ops.BlockedStatus):
            # Preserve BlockedStatus from backup/media observers (e.g., S3 config errors).
            # This should be refactored.
            return

        if self.peer_relation and not signing_key.is_secret_container_equal(
            self.peer_relation, self, charm_state, container
        ):
            self.unit.status = ops.MaintenanceStatus(
                "Signing key secret content is different from the file"
            )
            return

        try:
            service = container.get_service(synapse.MJOLNIR_SERVICE_NAME)
            if service and not service.is_running():
                self.unit.status = ops.MaintenanceStatus("Waiting for Mjolnir")
        except ops.ModelError:
            # ModelError is raised if service not found
            logger.info("mjolnir not found, skipping")

        self.unit.status = ops.ActiveStatus()

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
