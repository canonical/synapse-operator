# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""The SAML integrator relation observer."""

import logging
import typing

import ops
from charms.saml_integrator.v0.saml import SamlDataAvailableEvent, SamlRequires
from ops.framework import Object

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

    def get_charm(self) -> CharmBaseWithState:
        """Return the current charm.

        Returns:
           The current charm
        """
        return self._charm

    @inject_charm_state
    def _on_saml_data_available(self, _: SamlDataAvailableEvent, charm_state: CharmState) -> None:
        """Handle SAML data available.

        Args:
            charm_state: The charm state.
        """
        self.model.unit.status = ops.MaintenanceStatus("Preparing the SAML integration")
        logger.debug("_on_saml_data_available emitting reconcile")
        self.get_charm().reconcile(charm_state)

    def get_relation_as_saml_conf(self) -> typing.Optional[SAMLConfiguration]:
        """Get SAML data from relation.

        Returns:
            Dict: Information needed for setting environment variables.
        """
        if not self.model.relations.get(self._RELATION_NAME):
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
