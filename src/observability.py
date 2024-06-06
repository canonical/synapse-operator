# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Provide the Observability class to represent the observability stack for Synapse."""

import ops
from charms.grafana_k8s.v0.grafana_dashboard import GrafanaDashboardProvider
from charms.loki_k8s.v1.loki_push_api import LogProxyConsumer
from charms.prometheus_k8s.v0.prometheus_scrape import MetricsEndpointProvider

import synapse

CONTAINER_NAME = "synapse"
LOG_PATHS = ["/debug.log*", "/errors.log*"]
STATS_EXPORTER_PORT = "9877"


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
            jobs=[
                {
                    "static_configs": [
                        {
                            "targets": [
                                f"*:{synapse.PROMETHEUS_MAIN_TARGET_PORT}",
                                f"*:{synapse.PROMETHEUS_WORKER_TARGET_PORT}",
                                f"*:{STATS_EXPORTER_PORT}",
                            ]
                        }
                    ]
                }
            ],
        )
        self._logging = LogProxyConsumer(
            charm,
            relation_name="logging",
            logs_scheme={
                f"{CONTAINER_NAME}": {
                    "log-files": LOG_PATHS,
                },
            },
        )
