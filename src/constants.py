# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""This module defines constants used throughout the Synapse application."""

CHECK_READY_NAME = "synapse-ready"
CHECK_ALIVE_NAME = "synapse-alive"
COMMAND_MIGRATE_CONFIG = "migrate_config"
PROMETHEUS_TARGET_PORT = "9000"
SYNAPSE_CONFIG_DIR = "/data"
SYNAPSE_CONFIG_PATH = f"{SYNAPSE_CONFIG_DIR}/homeserver.yaml"
SYNAPSE_COMMAND_PATH = "/start.py"
SYNAPSE_CONTAINER_NAME = "synapse"
SYNAPSE_NGINX_CONTAINER_NAME = "synapse-nginx"
SYNAPSE_PORT = 8008
SYNAPSE_NGINX_PORT = 8080
SYNAPSE_SERVICE_NAME = "synapse"
TEST_SERVER_NAME = "server-name-configured.synapse.com"
TEST_SERVER_NAME_CHANGED = "pebble-layer-1.synapse.com"
