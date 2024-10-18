# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The Matrix Auth relation observer."""

import logging
from collections import namedtuple
from pathlib import Path
from typing import List, Optional

import ops
from charms.synapse.v0.matrix_auth import (
    MatrixAuthProviderData,
    MatrixAuthProvides,
    MatrixAuthRequirerData,
)
from ops.framework import Object

import synapse
from charm_state import CharmBaseWithState, CharmState, inject_charm_state

logger = logging.getLogger(__name__)


class MatrixAuthObserver(Object):
    """The Matrix Auth relation observer."""

    def __init__(self, charm: CharmBaseWithState):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
        """
        super().__init__(charm, "matrix-auth-observer")
        self._charm = charm
        self.matrix_auth = MatrixAuthProvides(self._charm)
        # matrix_auth_request_received conflicts with on defined by Redis...
        self.framework.observe(
            self._charm.on["matrix-auth"].relation_changed, self._on_matrix_auth_relation_changed
        )
        self.framework.observe(
            self._charm.on["matrix-auth"].relation_departed, self._on_matrix_auth_relation_departed
        )

    def get_charm(self) -> CharmBaseWithState:
        """Return the current charm.

        Returns:
           The current charm
        """
        return self._charm

    def update_matrix_auth_integration(self, charm_state: CharmState) -> None:
        """Update matrix auth integration relation data.

        Args:
            charm_state: The charm state.
        """
        for relation in list(self._charm.model.relations["matrix-auth"]):
            if not relation.units:
                return
            provider_data = self._get_matrix_auth_provider_data(charm_state)
            if self._matrix_auth_relation_updated(relation, provider_data):
                return
            self.matrix_auth.update_relation_data(relation, provider_data)

    def get_requirer_registration_secrets(self) -> Optional[List]:
        """Get requirers registration secrets (application services).

        Returns:
            dict with filepath and content for creating the secret files.
        """
        registration_secrets = []
        RegistrationSecret = namedtuple("RegistrationSecret", ["file_path", "registration_secret"])
        for relation in list(self._charm.model.relations["matrix-auth"]):
            requirer_data = MatrixAuthRequirerData.from_relation(self._charm.model, relation)
            if requirer_data and requirer_data.registration_secret_id:
                registration_juju_secret = requirer_data.get_registration(
                    self._charm.model, requirer_data.registration_secret_id
                )
                filename = f"{relation.name}-{relation.id}"
                file_path = (
                    Path(synapse.SYNAPSE_CONFIG_DIR) / f"appservice-registration-{filename}.yaml"
                )
                registration_secrets.append(
                    RegistrationSecret(file_path, registration_juju_secret.get_secret_value())
                )
        return registration_secrets

    def _get_matrix_auth_provider_data(
        self, charm_state: CharmState
    ) -> Optional[MatrixAuthProviderData]:
        """Get Synapse configuration as expected by the matrix auth relation.

        The integration will share homeserver URL and registration shared secret.

        Args:
            charm_state: The charm state.

        Returns:
            MatrixAuthConfiguration instance.
        """
        # future refactor victim: this is repeated with saml
        homeserver = (
            charm_state.synapse_config.public_baseurl
            if charm_state.synapse_config.public_baseurl is not None
            else f"https://{charm_state.synapse_config.server_name}"
        )
        # assuming that shared secret is always found
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        shared_secret = synapse.get_registration_shared_secret(container=container)
        return MatrixAuthProviderData(homeserver=homeserver, shared_secret=shared_secret)

    def _matrix_auth_relation_updated(
        self, relation: ops.Relation, provider_data: MatrixAuthProviderData
    ) -> bool:
        """Compare current information with the one in the relation.

        This check is done to prevent triggering relation-changed.

        Args:
            relation: The matrix-auth relation.
            provider_data: current Synapse configuration as MatrixAuthProviderData.

        Returns:
            True if current configuration and relation data are the same.
        """
        relation_homeserver = relation.data[self._charm.app].get("homeserver", "")
        relation_shared_secret = relation.data[self._charm.app].get("shared_secret", "")
        if (
            provider_data.homeserver != relation_homeserver
            or provider_data.shared_secret != relation_shared_secret
        ):
            logger.info("matrix-auth relation ID %s is outdated and will be updated", relation.id)
            return False
        return True

    @inject_charm_state
    def _on_matrix_auth_relation_changed(self, _: ops.EventBase, charm_state: CharmState) -> None:
        """Handle matrix-auth request received event.

        Args:
            charm_state: The charm state.
        """
        logger.debug("_on_matrix_auth_relation_changed emitting reconcile")
        self._charm.reconcile(charm_state)

    @inject_charm_state
    def _on_matrix_auth_relation_departed(self, _: ops.EventBase, charm_state: CharmState) -> None:
        """Handle matrix-auth relation departed event.

        Args:
            charm_state: The charm state.
        """
        logger.debug("_on_matrix_auth_relation_departed emitting reconcile")
        self._charm.reconcile(charm_state)
