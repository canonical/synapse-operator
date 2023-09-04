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
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

from constants import SYNAPSE_URL
from user import User

logger = logging.getLogger(__name__)

REGISTER_URL = f"{SYNAPSE_URL}/_synapse/admin/v1/register"
VERSION_URL = f"{SYNAPSE_URL}/_synapse/admin/v1/server_version"
SYNAPSE_VERSION_REGEX = r"(\d+\.\d+\.\d+(?:\w+)?)\s?"


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


class GetNonceError(APIError):
    """Exception raised when getting nonce via API fails."""


class GetVersionError(APIError):
    """Exception raised when getting version via API fails."""


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
    # build data
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
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        logger.exception("Failed to connect to %s: %r", REGISTER_URL, exc)
        raise NetworkError(f"Failed to connect to {REGISTER_URL}.") from exc
    except requests.exceptions.HTTPError as exc:
        logger.exception("HTTP error from %s: %r", REGISTER_URL, exc)
        raise NetworkError(f"HTTP error from {REGISTER_URL}.") from exc


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


def _send_get_request(api_url: str, retry: bool = False) -> requests.Response:
    """Call Synapse API using requests.get with retry and timeout.

    Args:
        api_url: URL to be requested.
        retry: call URL with a retry. Default is False.

    Raises:
        NetworkError: if there was an error fetching the api_url.

    Returns:
        Response from calling the URL.
    """
    try:
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=3,
        )
        if retry:
            session.mount("http://", HTTPAdapter(max_retries=retries))
        res = session.get(api_url, timeout=10)
        res.raise_for_status()
        session.close()
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        logger.exception("Failed to connect to %s: %r", api_url, exc)
        raise NetworkError(f"Failed to connect to {api_url}.") from exc
    except requests.exceptions.HTTPError as exc:
        logger.exception("HTTP error from %s: %r", api_url, exc)
        raise NetworkError(f"HTTP error from {api_url}.") from exc
    return res


def _get_nonce() -> str:
    """Get nonce.

    Returns:
        The nonce returned by Synapse API.

    Raises:
        GetNonceError: if there was an error while reading nonce.
    """
    res = _send_get_request(REGISTER_URL)
    try:
        nonce = res.json()["nonce"]
    except (requests.exceptions.JSONDecodeError, TypeError, KeyError) as exc:
        logger.exception("Failed to decode nonce: %r. Received: %s", exc, res.text)
        raise GetNonceError(str(exc)) from exc

    return nonce


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
        GetVersionError: if there was an error while reading version.
        VersionUnexpectedContentError: if the version has unexpected content.
    """
    res = _send_get_request(VERSION_URL, retry=True)
    try:
        server_version = res.json()["server_version"]
    except (requests.exceptions.JSONDecodeError, KeyError, TypeError) as exc:
        logger.exception("Failed to decode version: %r. Received: %s", exc, res.text)
        raise GetVersionError(str(exc)) from exc
    version_match = re.search(SYNAPSE_VERSION_REGEX, server_version)
    if not version_match:
        raise VersionUnexpectedContentError(
            f"server_version has unexpected content: {server_version}"
        )
    return version_match.group(1)


def get_access_token(user: User) -> str:
    """Get access token.

    Args:
        user: user to be used for requesting access token.

    Returns:
        Access token.
    """
    return user.password


def override_rate_limit(user: User, access_token: str) -> None:
    """Override user's rate limit.

    Args:
        user: user to override the rate limit.
        access_token: access token to be used.
    """
    print(user, access_token)
    # curl --header "Authorization: Bearer <access_token>" -X DELETE
    # https://matrix.example.com/_synapse/admin/v1/users/@example:example.com/override_ratelimit
