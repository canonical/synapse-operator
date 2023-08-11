# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""The SAML integrator relation observer."""

# ignoring duplicate-code with container connect check in the database observer.
# pylint: disable=R0801

import logging
import typing

import ops
from charms.saml_integrator.v0.saml import SamlDataAvailableEvent, SamlRequires
from ops.charm import CharmBase
from ops.framework import Object

from charm_types import SAMLConfiguration
from constants import SYNAPSE_CONTAINER_NAME

logger = logging.getLogger(__name__)


class SAMLObserver(Object):
    """The SAML Integrator relation observer.

    Attrs:
        _pebble_service: instance of pebble service.
    """

    _RELATION_NAME = "saml"

    def __init__(self, charm: CharmBase):
        """Initialize the observer and register event handlers.

        Args:
            charm: The parent charm to attach the observer to.
        """
        super().__init__(charm, "saml-observer")
        self._charm = charm
        self.saml = SamlRequires(self._charm)
        self.framework.observe(self.saml.on.saml_data_available, self._on_saml_data_available)

    @property
    def _pebble_service(self) -> typing.Any:
        """Return instance of pebble service.

        Returns:
            instance of pebble service or none.
        """
        return getattr(self._charm, "pebble_service", None)

    def _enable_saml(self) -> None:
        """Enable  SAML."""
        container = self._charm.unit.get_container(SYNAPSE_CONTAINER_NAME)
        if not container.can_connect() or self._pebble_service is None:
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for pebble")
            return
        try:
            self._pebble_service.enable_saml(container)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._charm.model.unit.status = ops.BlockedStatus(f"SAML integration failed: {exc}")
            return
        self._charm.unit.status = ops.ActiveStatus()

    def _on_saml_data_available(self, _: SamlDataAvailableEvent) -> None:
        """Handle SAML data available."""
        self.model.unit.status = ops.MaintenanceStatus("Preparing the SAML integration")
        self._enable_saml()

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
