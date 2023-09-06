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

from charm_state import CharmState
from constants import MJOLNIR_MANAGEMENT_ROOM, SYNAPSE_URL
from user import User

logger = logging.getLogger(__name__)

# The API version that should be used is described in the documentation:
# https://matrix-org.github.io/synapse/latest/usage/administration/index.html
REGISTER_URL = f"{SYNAPSE_URL}/_synapse/admin/v1/register"
VERSION_URL = f"{SYNAPSE_URL}/_synapse/admin/v1/server_version"
LOGIN_URL = f"{SYNAPSE_URL}/_synapse/admin/v1/users"
LIST_ROOMS_URL = f"{SYNAPSE_URL}/_synapse/admin/v1/rooms"
LIST_USERS_URL = f"{SYNAPSE_URL}/_synapse/admin/v2/users?from=0&limit=10&name="
DEACTIVATE_ACCOUNT_URL = f"{SYNAPSE_URL}/_synapse/admin/v1/deactivate"
ADD_USER_ROOM_URL = f"{SYNAPSE_URL}/_synapse/admin/v1/join"
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
    """Exception raised when getting nonce fails."""


class GetVersionError(APIError):
    """Exception raised when getting version fails."""


class VersionUnexpectedContentError(GetVersionError):
    """Exception raised when output of getting version is unexpected."""


class GetRoomIDError(APIError):
    """Exception raised when getting room id fails."""


class RoomNotFoundError(APIError):
    """Exception raised when room was not found."""


class GetUserIDError(APIError):
    """Exception raised when getting user id fails."""


class UserExistsError(APIError):
    """Exception raised when checking if user exists fails."""


class GetAccessTokenError(APIError):
    """Exception raised when getting access token fails."""


class RegisterUserError(APIError):
    """Exception raised when registering user fails."""


# admin_access_token is not a password
def register_user(
    registration_shared_secret: str,
    user: User,
    server: str = "",
    admin_access_token: str = "",  # nosec
) -> str:
    """Register user.

    Args:
        registration_shared_secret: secret to be used to register the user.
        user: user to be registered.
        server: to be used to create the user id.
        admin_access_token: admin access token to get user's access token if it exists.

    Raises:
        RegisterUserError: if there was an error registering the user.

    Returns:
        Access token to be used by the user.
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
    res = _do_request("POST", REGISTER_URL, json=data)
    if "already taken" in res.text:
        logger.warning(
            "User %s already exists, no action was taken. Content: %s", user.username, res.text
        )
        return get_access_token(user=user, server=server, admin_access_token=admin_access_token)
    try:
        return res.json()["access_token"]
    except (requests.exceptions.JSONDecodeError, TypeError, KeyError) as exc:
        logger.exception("Failed to decode access_token: %r. Received: %s", exc, res.text)
        raise RegisterUserError(str(exc)) from exc


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
        GetNonceError: if there was an error while reading nonce.
    """
    res = _do_request("GET", REGISTER_URL)
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
    res = _do_request("GET", VERSION_URL, retry=True)
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


def get_access_token(user: User, server: str, admin_access_token: str) -> str:
    """Get an access token that can be used to authenticate as that user.

    This is a way to do actions on behalf of a user.

    Args:
        user: the user on behalf of whom you want to request the access token.
        server: to be used to create the user id. User ID example: @user:server.com.
        admin_access_token: a server admin access token to be used for the request.

    Returns:
        Access token.

    Raises:
        GetAccessTokenError: if there was an error while getting access token.
    """
    authorization_token = f"Bearer {admin_access_token}"
    headers = {"Authorization": authorization_token}
    # @user:server.com
    user_id = f"@{user.username}:{server}"
    res = _do_request("POST", f"{LOGIN_URL}/{user_id}/login", headers=headers)
    try:
        res_access_token = res.json()["access_token"]
    except (requests.exceptions.JSONDecodeError, KeyError, TypeError) as exc:
        logger.exception("Failed to decode access_token: %r. Received: %s", exc, res.text)
        raise GetAccessTokenError(str(exc)) from exc
    return res_access_token


def override_rate_limit(user: User, admin_access_token: str, charm_state: CharmState) -> None:
    """Override user's rate limit.

    Args:
        user: user to be used for requesting access token.
        admin_access_token: server admin access token to be used.
        charm_state: Instance of CharmState.
    """
    server_name = charm_state.server_name
    rate_limit_url = (
        f"{SYNAPSE_URL}/_synapse/admin/v1/users/"
        f"@{user.username}:{server_name}/override_ratelimit"
    )
    authorization_token = f"Bearer {admin_access_token}"
    headers = {"Authorization": authorization_token}
    _do_request("DELETE", rate_limit_url, headers=headers)


def get_room_id(
    room_name: str,
    admin_access_token: str,
) -> str:
    """Get room id.

    Args:
        room_name: room name.
        admin_access_token: server admin access token to be used.

    Returns:
        The room id.

    Raises:
        GetRoomIDError: if there was an error while getting room id.
        RoomNotFoundError: if the room was not found.
    """
    authorization_token = f"Bearer {admin_access_token}"
    headers = {"Authorization": authorization_token}
    res = _do_request("GET", LIST_ROOMS_URL, headers=headers)
    try:
        rooms = res.json()["rooms"]
        for room in rooms:
            if room["name"].upper() == room_name.upper():
                return room["room_id"]
    except (requests.exceptions.JSONDecodeError, TypeError, KeyError) as exc:
        logger.exception("Failed to decode rooms: %r. Received: %s", exc, res.text)
        raise GetRoomIDError(str(exc)) from exc

    raise RoomNotFoundError(f"Room {room_name} not found. Please, verify if the room exists.")


def deactivate_user(
    user: User,
    server: str,
    admin_access_token: str,
) -> None:
    """Deactivate user.

    Args:
        user: user to be deactivated.
        server: to be used to create the user id.
        admin_access_token: server admin access token to be used.
    """
    authorization_token = f"Bearer {admin_access_token}"
    headers = {"Authorization": authorization_token}
    data = {
        "erase": True,
    }
    user_id = f"@{user.username}:{server}"
    url = f"{DEACTIVATE_ACCOUNT_URL}/{user_id}"
    _do_request("POST", url, headers=headers, json=data)


def create_management_room(admin_access_token: str) -> str:
    """Create the management room to be used by Mjolnir.

    Args:
        admin_access_token: server admin access token to be used.

    Raises:
        GetRoomIDError: if there was an error while getting room id.

    Returns:
        Room id.
    """
    authorization_token = f"Bearer {admin_access_token}"
    headers = {"Authorization": authorization_token}
    data = {"room_alias_name": f"{MJOLNIR_MANAGEMENT_ROOM}"}
    url = f"{SYNAPSE_URL}/_matrix/client/r0/createRoom?access_token={admin_access_token}"
    res = _do_request("POST", url, headers=headers, json=data)
    try:
        return res.json()["room_id"]
    except (requests.exceptions.JSONDecodeError, TypeError, KeyError) as exc:
        logger.exception("Failed to decode room_id: %r. Received: %s", exc, res.text)
        raise GetRoomIDError(str(exc)) from exc


def make_room_admin(user: User, server: str, admin_access_token: str, room_id: str) -> None:
    """Make user a room's admin.

    Args:
        user: user to add to the room as admin.
        server: to be used to create the user id.
        admin_access_token: server admin access token to be used for the request.
        room_id: room id to add the user.
    """
    authorization_token = f"Bearer {admin_access_token}"
    headers = {"Authorization": authorization_token}
    user_id = f"@{user.username}:{server}"
    data = {"user_id": user_id}
    url = f"{SYNAPSE_URL}/_synapse/admin/v1/rooms/{room_id}/make_room_admin"
    _do_request("POST", url, headers=headers, json=data)


def _do_request(
    method: str,
    url: str,
    headers: typing.Optional[typing.Dict] = None,
    json: typing.Optional[typing.Dict] = None,
    retry: bool = False,
) -> requests.Response:
    """Offer a generic request.

    Args:
        method: HTTP method.
        url: url to request.
        headers: header to be used in the request. Defaults to None.
        json: json data to be sent in the request. Defaults to None.
        retry: if the request should be retried. Defaults to False.

    Raises:
        NetworkError: if there was an error fetching the api_url.

    Returns:
        Response from the request.
    """
    try:
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=3,
        )
        if retry:
            session.mount("http://", HTTPAdapter(max_retries=retries))
        response = session.request(method, url, headers=headers, json=json, timeout=5)
        response.raise_for_status()
        session.close()
        return response
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        logger.exception("Failed to connect to %s: %r", url, exc)
        raise NetworkError(f"Failed to connect to {url}.") from exc
    except requests.exceptions.HTTPError as exc:
        logger.exception("HTTP error from %s: %r", url, exc)
        raise NetworkError(f"HTTP error from {url}.") from exc
