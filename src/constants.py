# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""This module defines constants used throughout the Synapse application."""

CHECK_READY_NAME = "synapse-ready"
CHECK_ALIVE_NAME = "synapse-alive"
CHECK_NGINX_READY_NAME = "synapse-nginx-ready"
CHECK_MJOLNIR_READY_NAME = "synapse-mjolnir-ready"
COMMAND_MIGRATE_CONFIG = "migrate_config"
PROMETHEUS_TARGET_PORT = "9000"
SYNAPSE_CONFIG_DIR = "/data"
SYNAPSE_CONFIG_PATH = f"{SYNAPSE_CONFIG_DIR}/homeserver.yaml"
MJOLNIR_CONFIG_PATH = f"{SYNAPSE_CONFIG_DIR}/config/production.yaml"
MJOLNIR_USER = "mjolnir"
MJOLNIR_MANAGEMENT_ROOM = "management"
SYNAPSE_COMMAND_PATH = "/start.py"
SYNAPSE_CONTAINER_NAME = "synapse"
SYNAPSE_NGINX_CONTAINER_NAME = "synapse-nginx"
SYNAPSE_PORT = 8008
SYNAPSE_NGINX_PORT = 8080
SYNAPSE_SERVICE_NAME = "synapse"
SYNAPSE_URL = "http://localhost:8008"
TEST_SERVER_NAME = "server-name-configured.synapse.com"
