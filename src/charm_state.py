#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""State of the Charm."""
from ops.charm import CharmBase


class CharmState:
    """State of the Charm.

    Attrs:
        container_name: Synapse container name.
        server_name: server_name config.
        report_stats: report_stats config.
        synapse_port: port to expose Synapse.
    """

    def __init__(self, charm: CharmBase) -> None:
        """Construct.

        Args:
            charm: Synapse charm
        """
        self._charm = charm

    @property
    def container_name(self) -> str:
        """Return the Synapse container name.

        Returns:
            str: container name.
        """
        return "synapse"

    @property
    def server_name(self) -> str:
        """Return server_name config.

        Returns:
            str: server_name config.
        """
        return self._charm.config["server_name"]

    @property
    def report_stats(self) -> str:
        """Return report_stats config.

        Returns:
            str: report_stats config.
        """
        return self._charm.config["report_stats"]

    @property
    def synapse_port(self) -> int:
        """Return the port to expose Synapse.

        Returns:
            int: port number.
        """
        return 8008
