# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""This module defines constants used throughout the Synapse application."""

CHECK_READY_NAME = "synapse-ready"
COMMAND_MIGRATE_CONFIG = "migrate_config"
COMMAND_REGISTER_NEW_MATRIX_USER = "register_new_matrix_user"
SYNAPSE_CONFIG_DIR = "/data"
SYNAPSE_CONFIG_PATH = f"{SYNAPSE_CONFIG_DIR}/homeserver.yaml"
SYNAPSE_COMMAND_PATH = "/start.py"
SYNAPSE_CONTAINER_NAME = "synapse"
SYNAPSE_PORT = 8008
SYNAPSE_SERVICE_NAME = "synapse"
TEST_SERVER_NAME = "server-name-configured.synapse.com"
