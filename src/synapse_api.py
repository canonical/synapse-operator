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

        If doesn't exist, register operator user and return password.

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
        self._register_operator_user(password=password)
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

    def _register_operator_user(self, password: str) -> None:
        """Create operator admin user.

        Args:
            password: operator password.

        Raises:
            CommandRegisterNewMatrixUserError: if registering user fails.
        """
        container = self._charm.unit.get_container(SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for pebble")
            return
        try:
            self._synapse.execute_register_new_matrix_user(
                container, username=SYNAPSE_OPERATOR_USER, password=password, admin=True
            )
        except CommandRegisterNewMatrixUserError as exc:
            logger.error("Failed to create operator user: %s", str(exc))
            raise

    def _get_access_token(self) -> str:
        """Get access token.

        Returns:
            access token to be used in the requests.
        """
        password = self._get_operator_password()
        # do login with operator user and get the access token
        return password

    def register_user(self, username: str, password: str, admin: bool) -> None:
        """Register user.

        Args:
            username: name to be registered.
            password: user's password.
            admin: if the user is admin or not.
        """
        # get registration_shared_secret from config file
        # get nonce
        # generate mac
        # access_token = self._get_access_token()
        # finally register user
