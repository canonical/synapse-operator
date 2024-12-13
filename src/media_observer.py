# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The media integrator relation observer."""

import logging
from typing import Optional

import ops
from charms.data_platform_libs.v0.s3 import CredentialsChangedEvent, S3Requirer
from ops.framework import Object

from backup_observer import S3_INVALID_CONFIGURATION
from charm_types import MediaConfiguration
from s3_parameters import S3Parameters
from state.mas import MASConfiguration
from state.validation import CharmBaseWithState, validate_charm_state

logger = logging.getLogger(__name__)

S3_CANNOT_ACCESS_BUCKET = "Media: S3 bucket does not exist or cannot be accessed"


class MediaObserver(Object):
    """The media relation observer."""

    _S3_RELATION_NAME = "media"

    def __init__(self, charm: CharmBaseWithState):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
        """
        super().__init__(charm, "media")

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

    @validate_charm_state
    def _on_s3_credentials_changed(self, _: CredentialsChangedEvent) -> None:
        """Handle the S3 credentials changed event."""
        charm = self.get_charm()
        charm_state = charm.build_charm_state()
        mas_configuration = MASConfiguration.from_charm(charm)

        try:
            _ = S3Parameters(**self._s3_client.get_s3_connection_info())
        except ValueError:
            self._charm.unit.status = ops.BlockedStatus(S3_INVALID_CONFIGURATION)
            return

        self.model.unit.status = ops.MaintenanceStatus("Preparing the Media integration")
        logger.debug("_on_s3_credentials_changed emitting reconcile")
        charm.reconcile(charm_state, mas_configuration)

    def get_relation_as_media_conf(self) -> Optional[MediaConfiguration]:
        """Get Media data from relation.

        Returns:
            Dict: Information needed for setting environment variables.
        """
        try:
            relation_data = S3Parameters(**self._s3_client.get_s3_connection_info())
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
