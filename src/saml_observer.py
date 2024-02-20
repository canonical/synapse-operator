# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The SAML integrator relation observer."""

# ignoring duplicate-code with container connect check in the database observer.
# pylint: disable=R0801

import logging
import typing

import ops
from charms.saml_integrator.v0.saml import SamlDataAvailableEvent, SamlRequires
from ops.framework import Object

import pebble
import synapse
from charm_state import CharmBaseWithState, CharmState, inject_charm_state
from charm_types import SAMLConfiguration

logger = logging.getLogger(__name__)


class SAMLObserver(Object):
    """The SAML Integrator relation observer."""

    _RELATION_NAME = "saml"

    def __init__(self, charm: CharmBaseWithState):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
        """
        super().__init__(charm, "saml-observer")
        self._charm = charm
        self.saml = SamlRequires(self._charm)
        self.framework.observe(self.saml.on.saml_data_available, self._on_saml_data_available)

    def _enable_saml(self, charm_state: CharmState) -> None:
        """Enable  SAML.

        Args:
            charm_state: Instance of CharmState
        """
        container = self._charm.unit.get_container(synapse.SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for Synapse pebble")
            return
        try:
            pebble.enable_saml(charm_state, container)
        except pebble.PebbleServiceError as exc:
            self._charm.model.unit.status = ops.BlockedStatus(f"SAML integration failed: {exc}")
            return
        self._charm.unit.status = ops.ActiveStatus()

    @inject_charm_state
    def _on_saml_data_available(self, _: SamlDataAvailableEvent, charm_state: CharmState) -> None:
        """Handle SAML data available.

        Args:
            charm_state: The charm state.
        """
        self.model.unit.status = ops.MaintenanceStatus("Preparing the SAML integration")
        logger.debug("_on_saml_data_available: Enabling SAML")

        self._enable_saml(charm_state)

    def get_relation_as_saml_conf(self) -> typing.Optional[SAMLConfiguration]:
        """Get SAML data from relation.

        Returns:
            Dict: Information needed for setting environment variables.
        """
        if self.model.get_relation(self._RELATION_NAME) is None:
            return None

        relation_data = {}
        relations = list(self._charm.model.relations[self._RELATION_NAME])
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
