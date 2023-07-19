#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage interactions with Synapse API."""

# pylint: disable=too-few-public-methods, too-many-arguments

import hashlib
import hmac
import logging
import typing

import ops
import requests
from ops.charm import CharmBase

from constants import SYNAPSE_CONTAINER_NAME
from user import User

logger = logging.getLogger(__name__)

SYNAPSE_URL = "http://localhost:8008"
REGISTER_URL = f"{SYNAPSE_URL}/_synapse/admin/v1/register"


class SynapseAPIError(Exception):
    """Exception raised when something fails while calling the API.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the RegisterUserError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


class RegisterUserError(SynapseAPIError):
    """Exception raised when registering user via API fails."""


class NetworkError(SynapseAPIError):
    """Exception raised when requesting API fails due network issues."""


class SynapseAPI:
    """The Synapse API handler."""

    def __init__(self, charm: CharmBase):
        """Initialize the handler.

        Args:
            charm: The parent charm to attach the observer to.
        """
        self._charm = charm

    def _get_nonce(self) -> str:
        """Get nonce.

        Returns:
            The nonce returned by Synapse API.

        Raises:
            NetworkError: if there was an error fetching the nonce.
        """
        try:
            res = requests.get(REGISTER_URL, timeout=5)
            res.raise_for_status()
            return res.json()["nonce"]
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError,
        ) as exc:
            logger.error("Failed to request %s : %s", REGISTER_URL, exc)
            raise NetworkError(f"Failed to request {REGISTER_URL}.") from exc

    def _generate_mac(
        self,
        shared_secret: str,
        nonce: str,
        user: str,
        password: str,
        admin: bool = False,
        user_type: typing.Optional[str] = None,
    ) -> str:
        """Generate mac to register user.

        Args:
            shared_secret: registration_shared_secret from configuration file.
            nonce: nonce generated.
            user: username.
            password: password.
            admin: if is admin. Default False.
            user_type: user type. Defaults to None.

        Returns:
            _type_: _description_
        """
        mac = hmac.new(key=shared_secret.encode("utf8"), digestmod=hashlib.sha1)
        mac.update(nonce.encode("utf8"))
        mac.update(b"\x00")
        mac.update(user.encode("utf8"))
        mac.update(b"\x00")
        mac.update(password.encode("utf8"))
        mac.update(b"\x00")
        mac.update(b"admin" if admin else b"notadmin")
        if user_type:
            mac.update(b"\x00")
            mac.update(user_type.encode("utf8"))

        return mac.hexdigest()

    def register_user(self, user: User) -> None:
        """Register user.

        Args:
            user: user to be registered.

        Raises:
            RegisterUserError: when registering user via API fails.
            NetworkError: if there was an error registering the user.
        """
        # get registration_shared_secret from config file
        container = self._charm.unit.get_container(SYNAPSE_CONTAINER_NAME)
        if not container.can_connect():
            self._charm.unit.status = ops.MaintenanceStatus("Waiting for pebble")
            return
        # Synapse is defined in the charm
        synapse = self._charm.synapse  # type: ignore[attr-defined]
        registration_shared_secret = synapse.get_configuration_field(
            container=container, fieldname="registration_shared_secret"
        )
        if registration_shared_secret is None:
            raise RegisterUserError("registration_shared_secret was not found")
        # get nonce
        nonce = self._get_nonce()

        # generate mac
        hex_mac = self._generate_mac(
            shared_secret=registration_shared_secret,
            nonce=nonce,
            user=user.username,
            password=user.password,
            admin=user.admin,
        )
        data = {
            "nonce": nonce,
            "username": user.username,
            "password": user.password,
            "mac": hex_mac,
            "admin": user.admin,
        }
        # finally register user
        try:
            res = requests.post(REGISTER_URL, json=data, timeout=5)
            res.raise_for_status()
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError,
        ) as exc:
            logger.error("Failed to request %s : %s", REGISTER_URL, exc)
            raise NetworkError(f"Failed to request {REGISTER_URL}.") from exc
