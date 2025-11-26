#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Charm for Synapse on kubernetes."""


import logging
import typing
from typing import Optional

import ops
from charms.data_platform_libs.v0.s3 import CredentialsChangedEvent, S3Requirer
from charms.nginx_ingress_integrator.v0.nginx_route import require_nginx_route
from charms.redis_k8s.v0.redis import RedisRelationCharmEvents, RedisRequires
from charms.saml_integrator.v0.saml import SamlRequires
from charms.smtp_integrator.v0.smtp import (
    AuthType,
    SmtpRelationData,
    SmtpRequires,
    TransportSecurity,
)
from charms.traefik_k8s.v2.ingress import IngressPerAppRequirer
from ops import main
from ops.charm import ActionEvent, RelationBrokenEvent
from pydantic.v1 import ValidationError

import macaroon_key
import pebble
import signing_key
import synapse
from admin_access_token import AdminAccessTokenService
from backup_observer import BackupObserver
from charm_state import (
    MAIN_UNIT_ID,
    CharmBaseWithState,
    CharmConfigInvalidError,
    CharmState,
    inject_charm_state,
)
from charm_types import (
    MediaConfiguration,
    RedisConfiguration,
    SAMLConfiguration,
    SMTPConfiguration,
)
from database_observer import DatabaseObserver
from matrix_auth_observer import MatrixAuthObserver
from mjolnir import (
    Mjolnir,
    MjolnirEnableError,
    MjolnirModeratorsNotFoundError,
)
from observability import Observability
from s3_parameters import S3Parameters
from user import User

logger = logging.getLogger(__name__)

INGRESS_INTEGRATION_NAME = "ingress"
# This constant is updated by Renovate.
SYNAPSE_VERSION = "1.142.1"
S3_CANNOT_ACCESS_BUCKET = "Media: S3 bucket does not exist or cannot be accessed"
S3_INVALID_CONFIGURATION = "Media: S3 configuration is invalid"


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
        self._media = S3Requirer(self, relation_name="media")
        self._database = DatabaseObserver(self, relation_name=synapse.SYNAPSE_DB_RELATION_NAME)
        self._saml = SamlRequires(self)
        self._smtp = SmtpRequires(self, relation_name="smtp")
        self._redis = RedisRequires(self)
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
        self.framework.observe(self.on.redis_relation_updated, self._trigger_reconcile)
        self.framework.observe(self.on.smtp_data_available, self._trigger_reconcile)
        self.framework.observe(
            self._media.on.credentials_changed, self._on_media_credentials_changed
        )
        self.framework.observe(self._saml.on.saml_data_available, self._trigger_reconcile)
        self.framework.observe(
            self.on[self._saml.relation_name].relation_broken, self._on_saml_relation_broken
        )

    def build_charm_state(self) -> CharmState:
        """Build charm state.

        Returns:
            The current charm state.
        """
        return CharmState.from_charm(
            charm=self,
            datasource=self._database.get_relation_as_datasource(),
            saml_config=self.get_relation_as_saml_conf(),
            smtp_config=self.get_relation_as_smtp_conf(),
            media_config=self.get_relation_as_media_conf(),
            redis_config=self.get_relation_as_redis_conf(),
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
                macaroon_key.write_to_container(self.peer_relation, self, charm_state, container)
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
            macaroon_key.write_to_secret(self.peer_relation, self, charm_state, container)

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

    # Integrations
    def get_relation_as_redis_conf(self) -> Optional[RedisConfiguration]:
        """Get the hostname and port from the redis relation data.

        Returns:
            RedisConfiguration instance with the hostname and port of the related redis or None
            if not found.
        """
        redis_config = None
        try:
            if self._redis.relation_data:
                redis_hostname = str(self._redis.relation_data.get("hostname"))
                redis_port = int(self._redis.relation_data.get("port", "6379"))
                logger.debug(
                    "Got redis connection details from relation %s:%s", redis_hostname, redis_port
                )
                redis_config = RedisConfiguration(host=redis_hostname, port=redis_port)
        except (KeyError, ValueError, TypeError) as exc:
            # the relation databag is empty at that point.
            logger.exception("Failed to get Redis relation data: %s", str(exc))
            return None

        if not redis_config:
            logger.info("Redis databag is empty.")
        return redis_config

    @inject_charm_state
    def _on_media_credentials_changed(
        self, _: CredentialsChangedEvent, charm_state: CharmState
    ) -> None:
        """Handle the S3 credentials changed event.

        Args:
            charm_state: The charm state.
        """
        try:
            _ = S3Parameters(**self._media.get_s3_connection_info())
        except ValueError:
            self.unit.status = ops.BlockedStatus(S3_INVALID_CONFIGURATION)
            return

        logger.debug("_on_media_credentials_changed emitting reconcile")
        self.reconcile(charm_state, "Preparing the Media integration")

    def get_relation_as_media_conf(self) -> Optional[MediaConfiguration]:
        """Get Media data from relation.

        Returns:
            Dict: Information needed for setting environment variables.
        """
        try:
            relation_data = S3Parameters(**self._media.get_s3_connection_info())
        except ValueError:
            logger.info("Relation data for S3 Media is not valid S3 Parameters.")
            return None

        if relation_data is None:
            return None

        rel_region = relation_data.region or ""
        rel_endpoint = relation_data.endpoint or ""

        return MediaConfiguration(
            bucket=relation_data.bucket,
            region_name=rel_region,
            endpoint_url=rel_endpoint,
            access_key_id=relation_data.access_key,
            secret_access_key=relation_data.secret_key,
            prefix=relation_data.path,
        )

    @inject_charm_state
    def _on_saml_relation_broken(self, _: RelationBrokenEvent, charm_state: CharmState) -> None:
        """Handle SAML relation broken.

        Args:
            charm_state: The charm state.
        """
        logger.debug("_on_saml_relation_broken emitting reconcile")
        self.reconcile(charm_state, "Reloading SAML configuration")

    def get_relation_as_saml_conf(self) -> Optional[SAMLConfiguration]:
        """Get SAML data from relation.

        Returns:
            Dict: Information needed for setting environment variables.
        """
        if not self.model.relations.get("saml"):
            return None

        relation_data = {}
        relations = list(self.model.relations["saml"])
        relation_id = relations[0].id
        for relation in relations:
            relation_data[relation.id] = (
                {key: value for key, value in relation.data[relation.app].items() if key != "data"}
                if relation.app
                else {}
            )

        return SAMLConfiguration(
            entity_id=relation_data[relation_id].get("entity_id", ""),
            metadata_url=relation_data[relation_id].get("metadata_url", ""),
        )

    def get_relation_as_smtp_conf(self) -> Optional[SMTPConfiguration]:
        """Get SMTP data from relation.

        Returns:
            Dict: Information needed for setting environment variables.

        Raises:
            CharmConfigInvalidError: If the SMTP configurations is not supported.
        """
        if not self.model.relations.get("smtp"):
            return None
        try:
            relation_data: Optional[SmtpRelationData] = self._smtp.get_relation_data()
        except (ValidationError, ValueError):
            # ValidationError happens in the smtp(_legacy)relation_created event, as
            # the relation databag is empty at that point.
            logger.info("SMTP databag is empty. SMTP information will be set in the next event.")
            return None

        if relation_data is None:
            return None

        if relation_data.transport_security == TransportSecurity.NONE:
            raise CharmConfigInvalidError("Transport security NONE is not supported for SMTP")

        if relation_data.auth_type != AuthType.PLAIN:
            raise CharmConfigInvalidError("Only PLAIN auth type is supported for SMTP")

        user = relation_data.user
        password = self._get_password_from_relation_data(relation_data)

        # Not all combinations for the next variables are correct. See:
        # https://github.com/matrix-org/synapse/blob/develop/synapse/config/emailconfig.py
        force_tls = False
        enable_tls = False
        require_transport_security = False
        if relation_data.transport_security == TransportSecurity.STARTTLS:
            enable_tls = True
            require_transport_security = True
        elif relation_data.transport_security == TransportSecurity.TLS:
            force_tls = True
            enable_tls = True
            require_transport_security = True

        return SMTPConfiguration(
            enable_tls=enable_tls,
            force_tls=force_tls,
            require_transport_security=require_transport_security,
            host=relation_data.host,
            port=relation_data.port,
            user=user,
            password=password,
        )

    def _get_password_from_relation_data(self, relation_data: SmtpRelationData) -> Optional[str]:
        """Get smtp password from relation data.

        Arguments:
            relation_data: The relation data from where to extract the password

        Returns:
            the password or None if no password found
        """
        # If the relation data password_id exists, that means that
        # Juju version is >= 3.0 and secrets are used for the password.
        # Otherwise, use the field password as a fallback
        if relation_data.password_id:
            secret = self.model.get_secret(id=relation_data.password_id)
            content = secret.get_content()
            return content["password"]
        return relation_data.password

    # Actions
    class RegisterUserError(Exception):
        """Exception raised when something fails while running register-user.

        Attrs:
            msg (str): Explanation of the error.
        """

        def __init__(self, msg: str):
            """Initialize a new instance of the RegisterUserError exception.

            Args:
                msg (str): Explanation of the error.
            """
            self.msg = msg

    def _register_user(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        container: ops.Container,
        username: str,
        admin: bool,
        admin_access_token: Optional[str] = None,
        server: str = "",
    ) -> "User":
        """Run register user action.

        Args:
            container: Container of the charm.
            username: username to be registered.
            admin: if user is admin.
            server: to be used to create the user id.
            admin_access_token: server admin access token to get user's access token if it exists.

        Raises:
            RegisterUserError: if something goes wrong while registering the user.

        Returns:
            User with password registered.
        """
        try:
            registration_shared_secret = synapse.get_registration_shared_secret(
                container=container
            )
            if registration_shared_secret is None:
                raise self.RegisterUserError(
                    "registration_shared_secret was not found, please check the logs"
                )
            user = User(username=username, admin=admin)
            access_token = synapse.register_user(
                registration_shared_secret=registration_shared_secret,
                user=user,
                admin_access_token=admin_access_token,
                server=server,
            )
            user.access_token = access_token
            return user
        except (ValidationError, synapse.APIError) as exc:
            raise self.RegisterUserError(str(exc)) from exc

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
            user = self._register_user(
                container=container, username=event.params["username"], admin=event.params["admin"]
            )
        except self.RegisterUserError as exc:
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
