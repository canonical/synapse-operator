#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""State of the Charm."""
import ops

SYNAPSE_CONTAINER_NAME = "synapse"
SYNAPSE_PORT = 8008


class CharmState:
    """State of the Charm.

    Attrs:
        server_name: server_name config.
        report_stats: report_stats config.
    """

    def __init__(self, charm: ops.CharmBase) -> None:
        """Construct.

        Args:
            charm: Synapse charm
        """
        self._charm = charm

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
