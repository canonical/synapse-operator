#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage interactions with Synapse API."""

# pylint: disable=too-few-public-methods

import logging
import secrets
import string

import ops
from ops.charm import CharmBase

from constants import SYNAPSE_CONTAINER_NAME, SYNAPSE_OPERATOR_USER
from synapse import CommandRegisterNewMatrixUserError, Synapse

logger = logging.getLogger(__name__)


class SynapseAPI:
    """The Synapse API handler."""

    def __init__(self, charm: CharmBase, synapse: Synapse):
        """Initialize the handler.

        Args:
            charm: The parent charm to attach the observer to.
            synapse: Synapse instance to interact with commands.
        """
        self._charm = charm
        self._synapse = synapse

    def _get_operator_password(self) -> str:
        """Get operator password from peer data.

        If doesn't exist, create operator user and return password.

        Returns:
            operator password.
        """
        peer_relation = self._charm.model.get_relation("synapse-peers")
        assert peer_relation is not None  # nosec
        peer_key = "operator-password"
        peer_password = peer_relation.data[self._charm.app].get(peer_key)
        if peer_password:
            return peer_password
        password = self._get_random_password()
        self._create_operator_user(password=password)
        peer_relation.data[self._charm.app].update({peer_key: password})
        return password

    def _get_random_password(self) -> str:
        """Get random password. Extracted from postgresql-k8s charm.

        Returns:
            random password.
        """
        choices = string.ascii_letters + string.digits
        password = "".join([secrets.choice(choices) for i in range(16)])
        return password

    def _create_operator_user(self, password: str) -> None:
        """Create operator admin user.

        Args:
            password: operator password.
        """
        container = self._charm.unit.get_container(SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for pebble")
            return
        self._charm.model.unit.status = ops.MaintenanceStatus("Creating Synapse operator user")
        try:
            self._synapse.execute_register_new_matrix_user(
                container, username=SYNAPSE_OPERATOR_USER, password=password, admin=True
            )
        except CommandRegisterNewMatrixUserError as exc:
            self._charm.model.unit.status = ops.BlockedStatus(str(exc))
            return
        self._charm.model.unit.status = ops.ActiveStatus()
