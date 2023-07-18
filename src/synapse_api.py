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

logger = logging.getLogger(__name__)

SYNAPSE_URL = "http://localhost:8008"
URL_REGISTER = f"{SYNAPSE_URL}/_synapse/admin/v1/register"


class RegisterUserError(Exception):
    """Exception raised when registering user via API fails.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the RegisterUserError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


class NetworkError(Exception):
    """Exception raised when requesting API fails due network issues.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the NetworkError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


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
            res = requests.get(URL_REGISTER, timeout=5)
            res.raise_for_status()
            return res.json()["nonce"]
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError,
        ) as exc:
            logger.error("Failed to request %s : %s", URL_REGISTER, exc)
            raise NetworkError(f"Failed to request {URL_REGISTER}.") from exc

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

    def register_user(self, username: str, password: str, admin: bool) -> None:
        """Register user.

        Args:
            username: name to be registered.
            password: user's password.
            admin: if the user is admin or not.

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
            user=username,
            password=password,
            admin=admin,
        )
        data = {
            "nonce": nonce,
            "username": username,
            "password": password,
            "mac": hex_mac,
            "admin": admin,
        }
        # finally register user
        try:
            res = requests.post(URL_REGISTER, json=data, timeout=5)
            res.raise_for_status()
        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError,
        ) as exc:
            logger.error("Failed to request %s : %s", URL_REGISTER, exc)
            raise NetworkError(f"Failed to request {URL_REGISTER}.") from exc
