# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The media integrator relation observer."""

# ignoring duplicate-code with container connect check in the saml observer.
# pylint: disable=R0801

import logging

import ops
from charms.data_platform_libs.v0.s3 import CredentialsChangedEvent
from ops.framework import Object

import pebble
import synapse
from backup import S3Parameters
from backup_observer import S3_INVALID_CONFIGURATION
from charm_state import CharmBaseWithState, CharmState
from lib.charms.data_platform_libs.v0.s3 import S3Requirer

logger = logging.getLogger(__name__)


class MediaObserver(Object):
    """The media relation observer."""

    _RELATION_NAME = "media"

    def __init__(self, charm: CharmBaseWithState):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
        """
        super().__init__(charm, "media-observer")
        self._charm = charm

        self._s3_client = S3Requirer(self._charm, "media")
        self.framework.observe(
            self._s3_client.on.credentials_changed, self._on_s3_credentials_changed
        )

    def get_charm(self) -> CharmBaseWithState:
        """Return the current charm.

        Returns:
           The current charm
        """
        return self._charm

    def _on_s3_credentials_changed(self, event: CredentialsChangedEvent) -> None:
        """Handle the S3 credentials changed event.

        Args:
            event: The event object
        """
        try:
            s3_parameters = S3Parameters(**self._s3_client.get_s3_connection_info())
        except ValueError:
            self._charm.unit.status = ops.BlockedStatus(S3_INVALID_CONFIGURATION)
            return

        # enable s3 media / config change
        self._enable_media(CharmState(s3_parameters=s3_parameters))
        self._charm.unit.status = ops.ActiveStatus()
        # change config homeserver


    def _enable_media(self, charm_state: CharmState) -> None:
        """Enable Media.

        Args:
            charm_state: The charm state
        """
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        try:
            pebble.enable_media(charm_state, container)
        except pebble.PebbleServiceError as exc:
            self._charm.model.unit.status = ops.BlockedStatus(f"Media integration failed: {exc}")
            return
        self._charm.unit.status = ops.ActiveStatus()
