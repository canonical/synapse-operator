# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the Mjolnir class to represent the Mjolnir plugin for Synapse."""

# disabling due the fact that collect status does many checks
# pylint: disable=too-many-return-statements

import logging
import typing

import ops

import actions
import synapse
from actions import RegisterUserError
from charm_state import CharmState

logger = logging.getLogger(__name__)

MJOLNIR_SERVICE_NAME = "mjolnir"
USERNAME = "moderator"


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

    @property
    def _admin_access_token(self) -> typing.Optional[str]:
        """Get admin access token.

        Returns:
            admin access token or None if fails.
        """
        get_admin_access_token = getattr(self._charm, "get_admin_access_token", None)
        if not get_admin_access_token:
            logging.error("Failed to get method get_admin_access_token.")
            return None
        return get_admin_access_token()

    def _on_collect_status(self, event: ops.CollectStatusEvent) -> None:
        """Collect status event handler.

        Args:
            event: Collect status event.
        """
        if not self._charm_state.synapse_config.enable_mjolnir:
            return
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        mjolnir_service = container.get_services(MJOLNIR_SERVICE_NAME)
        if mjolnir_service:
            logger.debug("%s service already exists, skipping", MJOLNIR_SERVICE_NAME)
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
        try:
            admin_access_token = self._admin_access_token
        except RegisterUserError:
            logger.exception("Failed to get admin access token.")
            admin_access_token = None

        if not admin_access_token:
            self._charm.unit.status = ops.MaintenanceStatus(
                "Failed to get admin access token. Please, check the logs."
            )
            return

        try:
            if self.get_membership_room_id(self._admin_access_token) is None:
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
        except synapse.APIError as exc:
            logger.exception(
                "Failed to check for membership_room. Mjolnir will not be configured: %r",
                exc,
            )
            return
        self.enable_mjolnir(self._admin_access_token)
        event.add_status(ops.ActiveStatus())

    def get_membership_room_id(self, admin_access_token: str) -> typing.Optional[str]:
        """Check if membership room exists.

        Args:
            admin_access_token: not empty admin access token.

        Returns:
            The room id or None if is not found.
        """
        return synapse.get_room_id(
            room_name=synapse.MJOLNIR_MEMBERSHIP_ROOM, admin_access_token=admin_access_token
        )

    def enable_mjolnir(self, admin_access_token: str) -> None:
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
            admin_access_token: not empty admin access token.
        """
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        self._charm.model.unit.status = ops.MaintenanceStatus("Configuring Mjolnir")
        mjolnir_user = actions.register_user(
            container,
            USERNAME,
            True,
            admin_access_token,
            str(self._charm_state.synapse_config.server_name),
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
            server=str(self._charm_state.synapse_config.server_name),
            admin_access_token=admin_access_token,
            room_id=room_id,
        )
        synapse.create_mjolnir_config(
            container=container, access_token=mjolnir_access_token, room_id=room_id
        )
        synapse.override_rate_limit(
            user=mjolnir_user,
            admin_access_token=admin_access_token,
            charm_state=self._charm_state,
        )
        self._pebble_service.replan_mjolnir(container)
        self._charm.model.unit.status = ops.ActiveStatus()
