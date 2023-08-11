#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage interactions with Synapse API."""

# pylint: disable=too-few-public-methods, too-many-arguments

import hashlib
import hmac
import logging
import re
import typing

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from user import User

logger = logging.getLogger(__name__)

SYNAPSE_URL = "http://localhost:8008"
REGISTER_URL = f"{SYNAPSE_URL}/_synapse/admin/v1/register"
VERSION_URL = f"{SYNAPSE_URL}/_synapse/admin/v1/server_version"


class APIError(Exception):
    """Exception raised when something fails while calling the API.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the APIError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


class NetworkError(APIError):
    """Exception raised when requesting API fails due network issues."""


class GetVersionError(APIError):
    """Exception raised when getting version via API fails."""


class VersionNotFoundError(GetVersionError):
    """Exception raised when version is not found."""


class VersionUnexpectedContentError(GetVersionError):
    """Exception raised when output of getting version is unexpected."""


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
        logger.exception("Failed to request %s : %r", REGISTER_URL, exc)
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
        logger.exception("Failed to request %s : %r", REGISTER_URL, exc)
        raise NetworkError(f"Failed to request {REGISTER_URL}.") from exc


def get_version() -> str:
    """Get version.

    Expected API output:
    {
        "server_version": "0.99.2rc1 (b=develop, abcdef123)",
        "python_version": "3.7.8"
    }

    We're using retry here because after the config change, Synapse is restarted.

    Returns:
        The version returned by Synapse API.

    Raises:
        NetworkError: if there was an error fetching the version.
        GetVersionError: if there was an error while reading version.
    """
    try:
        session = Session()
        retries = Retry(
            total=3,
            backoff_factor=3,
        )
        session.mount("http://", HTTPAdapter(max_retries=retries))
        res = session.get(VERSION_URL, timeout=10)
        res.raise_for_status()
        res_json = res.json()
        logger.error("res_json: %s", res_json)
        server_version = res_json.get("server_version", None)
        if server_version is None:
            # Exception not in docstring because is captured.
            raise VersionNotFoundError(  # noqa: DCO053
                f"There is no server_version in JSON output: {res_json}"
            )
        version_match = re.search(r"(\d+\.\d+\.\d+(?:\w+)?)\s", server_version)
        if not version_match:
            # Exception not in docstring because is captured.
            raise VersionUnexpectedContentError(  # noqa: DCO053
                f"server_version has unexpected content: {server_version}"
            )
        return version_match.group(1)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        logger.exception("Failed to connect to %s: %r", VERSION_URL, exc)
        raise NetworkError(f"Failed to connect to {VERSION_URL}.") from exc
    except requests.exceptions.HTTPError as exc:
        logger.exception("HTTP error from %s: %r", VERSION_URL, exc)
        raise NetworkError(f"HTTP error from {VERSION_URL}.") from exc
    except GetVersionError as exc:
        logger.exception("Failed to get version: %r", exc)
        raise GetVersionError(str(exc)) from exc
