# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the Observability class to represent the observability stack for Synapse."""

import ops
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider

from constants import PROMETHEUS_TARGET_PORT


class Observability:  # pylint: disable=too-few-public-methods
    """A class representing the observability stack for Synapse application."""

    def __init__(self, charm: ops.CharmBase):
        """Initialize a new instance of the Observability class.

        Args:
            charm: The charm object that the Observability instance belongs to.
        """
        self._grafana_dashboards = GrafanaDashboardProvider(
            charm, relation_name="grafana-dashboard"
        )
        self._metrics_endpoint = MetricsEndpointProvider(
            charm,
            relation_name="metrics-endpoint",
            jobs=[{"static_configs": [{"targets": [f"*:{PROMETHEUS_TARGET_PORT}"]}]}],
        )
