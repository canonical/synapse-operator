# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the Mjolnir class to represent the Mjolnir plugin for Synapse."""

import logging
import typing
from secrets import token_hex

import ops
from ops.jujuversion import JujuVersion

import actions
import synapse
from charm_state import CharmState
from user import User

logger = logging.getLogger(__name__)

MJOLNIR_SERVICE_NAME = "mjolnir"
PEER_RELATION_NAME = "synapse-peers"
# Disabling it since these are not hardcoded password
SECRET_ID = "secret-id"  # nosec
SECRET_KEY = "secret-key"  # nosec
USERNAME = "mjolnir"


class Mjolnir(ops.Object):  # pylint: disable=too-few-public-methods
    """A class representing the Mjolnir plugin for Synapse application.

    Mjolnir is a moderation tool for Matrix to be used to protect your server from malicious
    invites, spam messages etc.
    See https://github.com/matrix-org/mjolnir/ for more details about it.
    """

    def __init__(self, charm: ops.CharmBase, charm_state: CharmState):
        """Initialize a new instance of the Mjolnir class.

        Args:
            charm: The charm object that the Mjolnir instance belongs to.
            charm_state: Instance of CharmState.
        """
        super().__init__(charm, "mjolnir")
        self._charm = charm
        self._charm_state = charm_state
        self.framework.observe(charm.on.collect_unit_status, self._on_collect_status)

    @property
    def _pebble_service(self) -> typing.Any:
        """Return instance of pebble service.

        Returns:
            instance of pebble service or none.
        """
        return getattr(self._charm, "pebble_service", None)

    def _update_peer_data(self, container: ops.model.Container) -> None:
        """Update peer data if needed.

        Args:
            container: Synapse container.
        """
        # If there is no secret, we use peer relation data
        # If there is secret, then we update the secret and add the secret id to peer data
        peer_relation = self._charm.model.get_relation(PEER_RELATION_NAME)
        if not peer_relation:
            # there is no peer relation so nothing to be done
            return

        if JujuVersion.from_environ().has_secrets and not peer_relation.data[self._charm.app].get(
            SECRET_ID
        ):
            # we can create secrets and the one that we need was not created yet
            logger.debug("Adding secret")
            admin_user = self.create_admin_user(container)
            secret = self._charm.app.add_secret({SECRET_KEY: admin_user.access_token})
            peer_relation.data[self._charm.app].update({SECRET_ID: secret.id})
            return

        if not JujuVersion.from_environ().has_secrets and not peer_relation.data[
            self._charm.app
        ].get(SECRET_KEY):
            # we can't create secrets and peer data is empty
            logger.debug("Updating peer relation data")
            admin_user = self.create_admin_user(container)
            peer_relation.data[self._charm.app].update({SECRET_KEY: admin_user.access_token})

    def create_admin_user(self, container: ops.model.Container) -> User:
        """Create an admin user.

        Args:
            container: Synapse container.

        Returns:
            User: admin user that was created.
        """
        # The username is random because if the user exists, register_user will try to get the
        # access_token.
        # But to do that it needs an admin user and we don't have one yet.
        # So, to be on the safe side, the user name is randomly generated and if for any reason
        # there is no access token on peer data/secret, another user will be created.
        #
        # Using 16 to create a random value but to  be secure against brute-force attacks, please
        # check the docs:
        # https://docs.python.org/3/library/secrets.html#how-many-bytes-should-tokens-use
        username = token_hex(16)
        return actions.register_user(container, username, True)

    def _on_collect_status(self, event: ops.CollectStatusEvent) -> None:
        """Collect status event handler.

        Args:
            event: Collect status event.
        """
        if not self._charm_state.enable_mjolnir:
            return
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for pebble")
            return
        mjolnir_service = container.get_services(MJOLNIR_SERVICE_NAME)
        if mjolnir_service:
            logger.debug("%s service already exists, skipping", MJOLNIR_SERVICE_NAME)
            return
        current_services = container.get_services()
        all_svcs_running = all(svc.is_running() for svc in current_services.values())
        if not all_svcs_running or not current_services:
            # The get_membership_room_id does a call to Synapse API in order to get the
            # membership room id. This only works if Synapse and NGINX are running so that's why
            # the services are being checked here.
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for Synapse")
            return
        self._update_peer_data(container)
        if self.get_membership_room_id() is None:
            status = ops.BlockedStatus(
                f"{synapse.MJOLNIR_MEMBERSHIP_ROOM} not found and "
                "is required by Mjolnir. Please, check the logs."
            )
            interval = self._charm.model.config.get("update-status-hook-interval", "")
            logger.error(
                "The Mjolnir configuration will be done in %s after the room %s is created."
                "This interval is set in update-status-hook-interval model config.",
                interval,
                synapse.MJOLNIR_MEMBERSHIP_ROOM,
            )
            event.add_status(status)
            return
        self.enable_mjolnir()
        event.add_status(ops.ActiveStatus())

    def get_membership_room_id(self) -> typing.Optional[str]:
        """Check if membership room exists.

        Returns:
            The room id or None if is not found.
        """
        admin_access_token = self.get_admin_access_token()
        return synapse.get_room_id(
            room_name=synapse.MJOLNIR_MEMBERSHIP_ROOM, admin_access_token=admin_access_token
        )

    def get_admin_access_token(self) -> str:
        """Get admin access token.

        Returns:
            admin access token.
        """
        peer_relation = self._charm.model.get_relation(PEER_RELATION_NAME)
        assert peer_relation  # nosec
        if JujuVersion.from_environ().has_secrets:
            secret_id = peer_relation.data[self._charm.app].get(SECRET_ID)
            if secret_id:
                secret = self._charm.model.get_secret(id=secret_id)
                secret_value = secret.get_content().get(SECRET_KEY)
        else:
            secret_value = peer_relation.data[self._charm.app].get(SECRET_KEY)
        assert secret_value  # nosec
        return secret_value

    def enable_mjolnir(self) -> None:
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
        """
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for pebble")
            return
        self._charm.model.unit.status = ops.MaintenanceStatus("Configuring Mjolnir")
        admin_access_token = self.get_admin_access_token()
        mjolnir_user = actions.register_user(
            container,
            USERNAME,
            True,
            str(self._charm_state.server_name),
            admin_access_token,
        )
        mjolnir_access_token = mjolnir_user.access_token
        room_id = synapse.get_room_id(
            room_name=synapse.MJOLNIR_MANAGEMENT_ROOM, admin_access_token=admin_access_token
        )
        if room_id is None:
            logger.info("Room %s not found, creating", synapse.MJOLNIR_MANAGEMENT_ROOM)
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
        self._pebble_service.replan_mjolnir(container)
        self._charm.model.unit.status = ops.ActiveStatus()
