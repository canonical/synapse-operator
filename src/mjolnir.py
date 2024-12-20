# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the Mjolnir class to represent the Mjolnir plugin for Synapse."""

# disabling due the fact that collect status does many checks
# pylint: disable=too-many-return-statements

import logging
import typing

import ops

import pebble
import synapse
from state.charm_state import CharmState
from state.mas import MASConfiguration
from state.mjolnir import (
    CharmContainerNotReadyError,
    MjolnirConfiguration,
    MjolnirNotMainUnitError,
)
from state.validation import CharmBaseWithState, validate_charm_state
from user import User

logger = logging.getLogger(__name__)

MJOLNIR_SERVICE_NAME = "mjolnir"
USERNAME = "moderator"
MJOLNIR_CONTEXT_SECRET_LABEL = "mjolnir.context"
MJOLNIR_CONTEXT_KEY_ACCESS_TOKEN = "key.access.token"


class MjolnirContextNotSetError(Exception):
    """Exception raised when the mjolnir context is not set by the leader."""


class Mjolnir(ops.Object):
    """A class representing the Mjolnir plugin for Synapse application.

    Mjolnir is a moderation tool for Matrix to be used to protect your server from malicious
    invites, spam messages etc.
    See https://github.com/matrix-org/mjolnir/ for more details about it.
    """

    def __init__(self, charm: CharmBaseWithState):
        """Initialize a new instance of the Mjolnir class.

        Args:
            charm: The charm object that the Mjolnir instance belongs to.
        """
        super().__init__(charm, "mjolnir")
        self._charm = charm
        self._application = self._charm.app
        self.framework.observe(charm.on.collect_unit_status, self._on_collect_status)

    def get_charm(self) -> CharmBaseWithState:
        """Return the current charm.

        Returns:
           The current charm
        """
        return self._charm

    # Ignoring complexity warning for now
    @validate_charm_state
    def _on_collect_status(self, event: ops.CollectStatusEvent) -> None:  # noqa: C901
        """Collect status event handler.

        Args:
            event: Collect status event.
        """
        charm = self.get_charm()
        charm_state = charm.build_charm_state()
        MASConfiguration.validate(charm)
        if not charm_state.synapse_config.enable_mjolnir:
            return

        try:
            mjolnir_configuration = MjolnirConfiguration.from_charm(
                charm, charm_state.synapse_config
            )
        except MjolnirNotMainUnitError:
            logger.debug("Not main unit, stopping mjolnir and exiting.")
            # At this point, container is guaranteed to be ready as CharmContainerNotReadyError
            # would have been thrown first otherwise.
            container = charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
            if container.get_services(MJOLNIR_SERVICE_NAME):
                container.stop(MJOLNIR_SERVICE_NAME)
            return
        except CharmContainerNotReadyError:
            logger.exception("Charm container not ready.")
            charm.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return

        container = charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        # This check is the same done in get_main_unit. It should be refactored
        # to a place where both Charm and Mjolnir can get it.
        if mjolnir_service := container.get_services(MJOLNIR_SERVICE_NAME):
            mjolnir_not_active = [
                service for service in mjolnir_service.values() if not service.is_running()
            ]
            if mjolnir_not_active:
                logger.debug(
                    "%s service already exists but is not running, restarting",
                    MJOLNIR_SERVICE_NAME,
                )
                container.restart(MJOLNIR_SERVICE_NAME)
            logger.debug("%s service already exists and running, skipping", MJOLNIR_SERVICE_NAME)
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
            if self.get_membership_room_id(mjolnir_configuration.admin_access_token) is None:
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
        self.enable_mjolnir(container, mjolnir_configuration, charm_state)
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

    def enable_mjolnir(
        self,
        container: ops.model.Container,
        mjolnir_configuration: MjolnirConfiguration,
        charm_state: CharmState,
    ) -> None:
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
            container: The charm's container.
            mjolnir_configuration: mjolnir configuration state component.
            charm_state: Instance of CharmState.
        """
        admin_access_token = mjolnir_configuration.admin_access_token
        self._charm.model.unit.status = ops.MaintenanceStatus("Configuring Mjolnir")
        mjolnir_user = User(mjolnir_configuration.username, admin=True)
        room_id = synapse.get_room_id(
            room_name=synapse.MJOLNIR_MANAGEMENT_ROOM, admin_access_token=admin_access_token
        )
        if room_id is None:
            logger.info("Room %s not found, creating", synapse.MJOLNIR_MANAGEMENT_ROOM)
            room_id = synapse.create_management_room(admin_access_token=admin_access_token)
        # Add the Mjolnir user to the management room
        synapse.make_room_admin(
            user=mjolnir_user,
            server=str(charm_state.synapse_config.server_name),
            admin_access_token=admin_access_token,
            room_id=room_id,
        )
        synapse.generate_mjolnir_config(
            container=container, access_token=admin_access_token, room_id=room_id
        )
        synapse.override_rate_limit(
            user=mjolnir_user,
            admin_access_token=admin_access_token,
            charm_state=charm_state,
        )
        pebble.replan_mjolnir(container)
        self._charm.model.unit.status = ops.ActiveStatus()
