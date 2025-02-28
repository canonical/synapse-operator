# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the Draupnir class to represent the Draupnir plugin for Synapse."""

# disabling due the fact that collect status does many checks
# pylint: disable=too-many-return-statements

import logging
import typing

import ops

import pebble
import synapse
from admin_access_token import AdminAccessTokenService
from charm_state import CharmBaseWithState, CharmState, inject_charm_state

logger = logging.getLogger(__name__)

DRAUPNIR_SERVICE_NAME = "draupnir"
USERNAME = "moderator"


class Draupnir(ops.Object):  # pylint: disable=too-few-public-methods
    """A class representing the Draupnir plugin for Synapse application.

    Draupnir is a moderation tool for Matrix to be used to protect your server from malicious
    invites, spam messages etc.
    See https://github.com/the-draupnir-project/draupnir/ for more details about it.
    """

    def __init__(self, charm: CharmBaseWithState, token_service: AdminAccessTokenService):
        """Initialize a new instance of the Draupnir class.

        Args:
            charm: The charm object that the Draupnir instance belongs to.
            token_service: Instance of Admin Access Token Service.
        """
        super().__init__(charm, "draupnir")
        self._charm = charm
        self._token_service = token_service
        self.framework.observe(charm.on.collect_unit_status, self._on_collect_status)

    def get_charm(self) -> CharmBaseWithState:
        """Return the current charm.

        Returns:
           The current charm
        """
        return self._charm

    @property
    def _admin_access_token(self) -> typing.Optional[str]:
        """Get admin access token.

        Returns:
            admin access token or None if fails.
        """
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            logger.exception("Failed to connect to Synapse")
            return None
        access_token = self._token_service.get(container)
        if not access_token:
            logging.error("Admin Access Token was not found, please check the logs.")
            return None
        return access_token

    # Ignoring complexity warning for now
    @inject_charm_state
    def _on_collect_status(  # noqa: C901
        self, event: ops.CollectStatusEvent, charm_state: CharmState
    ) -> None:
        """Collect status event handler.

        Args:
            event: Collect status event.
            charm_state: The charm state.
        """
        if not charm_state.synapse_config.enable_draupnir:
            return
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        draupnir_service = container.get_services(DRAUPNIR_SERVICE_NAME)
        # This check is the same done in get_main_unit. It should be refactored
        # to a place where both Charm and Draupnir can get it.
        peer_relation = self._charm.model.relations[synapse.SYNAPSE_PEER_RELATION_NAME]
        if peer_relation:
            logger.debug(
                "Peer relation found, checking if is main unit before configuring Draupnir"
            )
            # The default is self._charm.unit.name to make tests that use Harness.begin() work.
            # When not using begin_with_initial_hooks, the peer relation data is not created.
            main_unit_id = (
                peer_relation[0].data[self._charm.app].get("main_unit_id", self._charm.unit.name)
            )
            if not self._charm.unit.name == main_unit_id:
                if draupnir_service:
                    logger.info("This is not the main unit, stopping Draupnir")
                    container.stop(DRAUPNIR_SERVICE_NAME)
                else:
                    logger.info("This is not the main unit, skipping Draupnir configuration")
                return
        if draupnir_service:
            draupnir_not_active = [
                service for service in draupnir_service.values() if not service.is_running()
            ]
            if draupnir_not_active:
                logger.debug(
                    "%s service already exists but is not running, restarting",
                    DRAUPNIR_SERVICE_NAME,
                )
                container.restart(DRAUPNIR_SERVICE_NAME)
            logger.debug("%s service already exists and running, skipping", DRAUPNIR_SERVICE_NAME)
            return
        synapse_service = container.get_services(synapse.SYNAPSE_SERVICE_NAME)
        synapse_not_active = [
            service for service in synapse_service.values() if not service.is_running()
        ]
        if not synapse_service or synapse_not_active:
            # The get_membership_room_id does a call to Synapse API in order to get the
            # membership room id. This only works if Synapse is running so that's why
            # the service status is checked here.
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for Synapse")
            return
        if not self._admin_access_token:
            self._charm.unit.status = ops.MaintenanceStatus(
                "Failed to get admin access token. Please, check the logs."
            )
            return
        try:
            if self.get_membership_room_id(self._admin_access_token) is None:
                status = ops.BlockedStatus(
                    f"{synapse.DRAUPNIR_MEMBERSHIP_ROOM} not found and "
                    "is required by Draupnir. Please, check the logs."
                )
                interval = self._charm.model.config.get("update-status-hook-interval", "")
                logger.error(
                    "The Draupnir configuration will be done in %s after the room %s is created."
                    "This interval is set in update-status-hook-interval model config.",
                    interval,
                    synapse.DRAUPNIR_MEMBERSHIP_ROOM,
                )
                event.add_status(status)
                return
        except synapse.APIError as exc:
            logger.exception(
                "Failed to check for membership_room. Draupnir will not be configured: %r",
                exc,
            )
            return
        self.enable_draupnir(charm_state, self._admin_access_token)
        event.add_status(ops.ActiveStatus())

    def get_membership_room_id(self, admin_access_token: str) -> typing.Optional[str]:
        """Check if membership room exists.

        Args:
            admin_access_token: not empty admin access token.

        Returns:
            The room id or None if is not found.
        """
        return synapse.get_room_id(
            room_name=synapse.DRAUPNIR_MEMBERSHIP_ROOM, admin_access_token=admin_access_token
        )

    def enable_draupnir(self, charm_state: CharmState, admin_access_token: str) -> None:
        """Enable draupnir service.

        The required steps to enable Draupnir are:
         - Get an admin access token.
         - Check if the DRAUPNIR_MEMBERSHIP_ROOM room is created.
         -- Only users from there will be allowed to join the management room.
         - Create Draupnir user or get its access token if already exists.
         - Create the management room or get its room id if already exists.
         -- The management room will allow only members of
         DRAUPNIR_MEMBERSHIP_ROOM room to join it.
         - Make the Draupnir user admin of this room.
         - Create the Draupnir configuration file.
         - Override Draupnir user rate limit.
         - Finally, add Draupnir pebble layer.

        Args:
            charm_state: Instance of CharmState.
            admin_access_token: not empty admin access token.
        """
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        self._charm.model.unit.status = ops.MaintenanceStatus("Configuring Draupnir")
        draupnir_user = synapse.create_user(
            container,
            USERNAME,
            True,
            admin_access_token,
            str(charm_state.synapse_config.server_name),
        )
        if draupnir_user is None:
            logger.error("Failed to create Draupnir user. Draupnir will not be configured")
            return
        draupnir_access_token = draupnir_user.access_token
        room_id = synapse.get_room_id(
            room_name=synapse.DRAUPNIR_MANAGEMENT_ROOM, admin_access_token=admin_access_token
        )
        if room_id is None:
            logger.info("Room %s not found, creating", synapse.DRAUPNIR_MANAGEMENT_ROOM)
            room_id = synapse.create_management_room(admin_access_token=admin_access_token)
        # Add the Draupnir user to the management room
        synapse.make_room_admin(
            user=draupnir_user,
            server=str(charm_state.synapse_config.server_name),
            admin_access_token=admin_access_token,
            room_id=room_id,
        )
        synapse.generate_draupnir_config(
            container=container, access_token=draupnir_access_token, room_id=room_id
        )
        synapse.override_rate_limit(
            user=draupnir_user,
            admin_access_token=admin_access_token,
            charm_state=charm_state,
        )
        pebble.replan_draupnir(container)
        self._charm.model.unit.status = ops.ActiveStatus()
