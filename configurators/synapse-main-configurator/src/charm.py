#!/usr/bin/env python3
# Copyright 2023 Mariyan Dimitrov
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following post for a quick-start guide that will help you
develop a new k8s charm using the Operator Framework:

https://discourse.charmhub.io/t/4208
"""

import logging

from ops.charm import CharmBase
from ops.framework import StoredState
from ops.main import main
from ops.model import ActiveStatus, WaitingStatus

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)

VALID_LOG_LEVELS = ["info", "debug", "warning", "error", "critical"]
DEFAULT_RELATION_NAME = "synapse_server_configurator"


class SynapseMainConfiguratorCharm(CharmBase):
    """Charm the Synapse configurator service.

    Save configuration for the Synapse main application
    and serve it over a relation to the (Synapse) app charm.
    """

    _stored = StoredState()

    def __init__(self, *args):
        super().__init__(*args)
        self._relation_name = DEFAULT_RELATION_NAME
        self.framework.observe(self.on.config_changed, self._on_config_changed)
        self.framework.observe(
            self.on.synapse_server_configurator_relation_created,
            self._on_synapse_server_configurator_relation_created,
        )
        self._stored.set_default(
            relation=False,
        )

    def _values_from_config(self):
        return {
            "server_name": self.config["server_name"],
            "report_stats": self.config["report_stats"],
        }

    def _on_synapse_server_configurator_relation_created(self, event):
        self._stored.relation = True
        event.relation.data[self.unit].update(self._values_from_config())

    def _on_config_changed(self, _event):
        """Handle changes in Synapse configuration.

        Currently this is a noop until we emit changes via a custom event
        to the Synapse application charm and let it handle the changes.
        """
        self.unit.status = WaitingStatus("Reconfiguring")
        if self._stored.relation:
            for relation in self.model.relations[self._relation_name]:
                relation.data[self.unit].update(self._values_from_config())
        self.unit.status = ActiveStatus()


if __name__ == "__main__":  # pragma: nocover
    main(SynapseMainConfiguratorCharm)
