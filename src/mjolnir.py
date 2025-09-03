# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the Mjolnir class to represent the Mjolnir plugin for Synapse."""

# disabling due the fact that collect status does many checks
# pylint: disable=too-many-return-statements

import logging
import typing

import ops

import pebble
import synapse
from admin_access_token import AdminAccessTokenService
from charm_state import CharmBaseWithState, CharmState

logger = logging.getLogger(__name__)

MJOLNIR_SERVICE_NAME = "mjolnir"
USERNAME = "moderator"


class MjolnirEnableError(Exception):
    """Exception when enabling Mjolnir fails."""


class MjolnirModeratorsNotFoundError(Exception):
    """Exception when the moderators room is not found or cannot be verified."""


class Mjolnir(ops.Object):  # pylint: disable=too-few-public-methods
    """A class representing the Mjolnir plugin for Synapse application.

    Mjolnir is a moderation tool for Matrix to be used to protect your server from malicious
    invites, spam messages etc.
    See https://github.com/matrix-org/mjolnir/ for more details about it.
    """

    def __init__(self, charm: CharmBaseWithState, token_service: AdminAccessTokenService):
        """Initialize a new instance of the Mjolnir class.

        Args:
            charm: The charm object that the Mjolnir instance belongs to.
            token_service: Instance of Admin Access Token Service.
        """
        super().__init__(charm, "mjolnir")
        self._charm = charm
        self._token_service = token_service

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

    def enable(self, charm_state: CharmState) -> None:
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
            charm_state: Instance of CharmState.

        Raises:
            MjolnirEnableError: Mjolnir or requirements fail.
            MjolnirModeratorsNotFoundError: moderators room is not found or cannot be verified.
        """
        if not self._admin_access_token:
            raise MjolnirEnableError(
                "Mjolnir: failed to get admin access token. Please, check the logs."
            )
        try:
            if self.get_membership_room_id(self._admin_access_token) is None:
                raise MjolnirModeratorsNotFoundError(
                    f"{synapse.MJOLNIR_MEMBERSHIP_ROOM} not found. Disable Mjolnir."
                )
        except synapse.APIError as exc:
            logger.exception(
                "Failed to check for membership_room. Mjolnir will not be configured: %r",
                exc,
            )
            raise MjolnirModeratorsNotFoundError(
                f"Failed to find {synapse.MJOLNIR_MEMBERSHIP_ROOM}. Disable Mjolnir."
            ) from exc
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            raise MjolnirEnableError("Mjolnir: waiting for Synapse pebble")
        mjolnir_user = synapse.create_user(
            container,
            USERNAME,
            True,
            self._admin_access_token,
            str(charm_state.synapse_config.server_name),
        )
        if mjolnir_user is None:
            logger.error("Failed to create Mjolnir user. Mjolnir will not be configured")
            return
        mjolnir_access_token = mjolnir_user.access_token
        room_id = synapse.get_room_id(
            room_name=synapse.MJOLNIR_MANAGEMENT_ROOM, admin_access_token=self._admin_access_token
        )
        if room_id is None:
            logger.info("Room %s not found, creating", synapse.MJOLNIR_MANAGEMENT_ROOM)
            room_id = synapse.create_management_room(admin_access_token=self._admin_access_token)
        # Add the Mjolnir user to the management room
        synapse.make_room_admin(
            user=mjolnir_user,
            server=str(charm_state.synapse_config.server_name),
            admin_access_token=self._admin_access_token,
            room_id=room_id,
        )
        synapse.generate_mjolnir_config(
            container=container, access_token=mjolnir_access_token, room_id=room_id
        )
        synapse.override_rate_limit(
            user=mjolnir_user,
            admin_access_token=self._admin_access_token,
            charm_state=charm_state,
        )
        pebble.replan_mjolnir(container)
