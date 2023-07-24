#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage interactions with Synapse API."""

# pylint: disable=too-few-public-methods, too-many-arguments

import hashlib
import hmac
import logging
import typing

import requests

from user import User

logger = logging.getLogger(__name__)

SYNAPSE_URL = "http://localhost:8008"
REGISTER_URL = f"{SYNAPSE_URL}/_synapse/admin/v1/register"


class APIError(Exception):
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


class RegisterUserError(APIError):
    """Exception raised when registering user via API fails."""


class NetworkError(APIError):
    """Exception raised when requesting API fails due network issues."""


def register_user(registration_shared_secret: str, user: User) -> None:
    """Register user.

    Args:
        registration_shared_secret: secret to be used to register the user.
        user: user to be registered.

    Raises:
        NetworkError: if there was an error registering the user.
    """
    # get nonce
    nonce = _get_nonce()

    # generate mac
    hex_mac = _generate_mac(
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


def _generate_mac(
    shared_secret: str,
    nonce: str,
    user: str,
    password: str,
    admin: str | bool = False,
    user_type: typing.Optional[str] = None,
) -> str:
    """Generate mac to register user.

    "The MAC is the hex digest output of the HMAC-SHA1 algorithm, with the key being the shared
    secret and the content being the nonce, user, password, either the string "admin" or
    "notadmin", and optionally the user_type each separated by NULs.".
    Extracted from: https://matrix-org.github.io/synapse/latest/admin_api/register_api.html

    Args:
        shared_secret: registration_shared_secret from configuration file.
        nonce: nonce generated.
        user: username for the new user.
        password: password used for authentication.
        admin: if is admin. Default False.
        user_type: user type. Defaults to None.

    Returns:
        User in HMAC format as a string of hexadecimals.
        This format is expected by the Synapse API.
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


def _get_nonce() -> str:
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
