# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""This module defines constants used throughout the Synapse application."""

CHECK_ALIVE_NAME = "synapse-alive"
CHECK_MJOLNIR_READY_NAME = "synapse-mjolnir-ready"
CHECK_NGINX_READY_NAME = "synapse-nginx-ready"
CHECK_READY_NAME = "synapse-ready"
COMMAND_MIGRATE_CONFIG = "migrate_config"
SYNAPSE_CONFIG_DIR = "/data"
MJOLNIR_CONFIG_PATH = f"{SYNAPSE_CONFIG_DIR}/config/production.yaml"
MJOLNIR_HEALTH_PORT = 7777
MJOLNIR_MANAGEMENT_ROOM = "management"
MJOLNIR_MEMBERSHIP_ROOM = "moderators"
MJOLNIR_SERVICE_NAME = "mjolnir"
PEER_RELATION_NAME = "synapse-peers"
PROMETHEUS_TARGET_PORT = "9000"
# Disabling it since these are not hardcoded password
SECRET_ID = "secret-id"  # nosec
SECRET_KEY = "secret-key"  # nosec
SYNAPSE_COMMAND_PATH = "/start.py"
SYNAPSE_CONFIG_PATH = f"{SYNAPSE_CONFIG_DIR}/homeserver.yaml"
SYNAPSE_CONTAINER_NAME = "synapse"
SYNAPSE_NGINX_CONTAINER_NAME = "synapse-nginx"
SYNAPSE_NGINX_PORT = 8080
SYNAPSE_PORT = 8008
SYNAPSE_SERVICE_NAME = "synapse"
SYNAPSE_URL = "http://localhost:8008"
TEST_SERVER_NAME = "server-name-configured.synapse.com"
WELL_KNOW_FILE_PATH = "/var/www/html/.well-known/matrix/server"
