# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The media integrator relation observer."""

# ignoring duplicate-code with container connect check in the saml observer.
# pylint: disable=R0801

import logging
from typing import Optional

import ops
from charms.data_platform_libs.v0.s3 import CredentialsChangedEvent, S3Requirer
from ops.framework import Object

import pebble
import synapse
from backup_observer import S3_INVALID_CONFIGURATION
from charm_state import CharmBaseWithState, CharmState
from charm_types import MediaConfiguration
from s3_parameters import S3Parameters

logger = logging.getLogger(__name__)

S3_CANNOT_ACCESS_BUCKET = "Media: S3 bucket does not exist or cannot be accessed"
S3_INVALID_CONFIGURATION = "Media: S3 configuration is invalid"

class MediaObserver(Object):
    """The media relation observer."""

    _S3_RELATION_NAME = "media"

    def __init__(self, charm: CharmBaseWithState):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
        """
        super().__init__(charm, "media-observer")

        self._charm = charm
        self._s3_client = S3Requirer(self._charm, self._S3_RELATION_NAME)
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
            _ = S3Parameters(**self._s3_client.get_s3_connection_info())
        except ValueError:
            self._charm.unit.status = ops.BlockedStatus(S3_INVALID_CONFIGURATION)
            return

        self.model.unit.status = ops.MaintenanceStatus("Preparing the Media integration")
        self._enable_media(self._charm.state)

    def get_relation_as_media_conf(self) -> Optional[MediaConfiguration]:
        """Get Media data from relation.

        Returns:
            Dict: Information needed for setting environment variables.

        Raises:
            CharmConfigInvalidError: If the Media configurations is not supported.
        """
        try:
            relation_data: Optional[S3Parameters] = self._s3_client.get_s3_connection_info()
        except ValueError:
            logger.info("Media databag is empty. Media information will be set in the next event.")
            return None
        
        if relation_data is None:
            return None
        
        return MediaConfiguration(
            access_key=relation_data.access_key,
            secret_key=relation_data.secret_key,
            region=relation_data.region,
            bucket=relation_data.bucket,
            endpoint=relation_data.endpoint,
            path=relation_data.path,
            s3_uri_style=relation_data.s3_uri_style,
        )

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
