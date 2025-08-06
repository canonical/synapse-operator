# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Upgrade rooms script."""

# pylint: disable=duplicate-code, line-too-long

import argparse
import logging
import os
import sys
from typing import Dict, Optional

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class SynapseServerError(Exception):
    """Synapse exception in the server."""


class SynapseImpersonateError(Exception):
    """Synapse exception during impersonate."""


class SynapseWhoAmIError(Exception):
    """Synapse exception during whoami."""


def get_headers(access_token: str) -> Dict[str, str]:
    """Get headers.

    Args:
        access_token (str): access token.

    Returns:
        Dict[str, str]: headers as a dict.
    """
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


# no type for kwargs
def make_request(method: str, url: str, headers: Dict[str, str], **kwargs) -> requests.Response:  # type: ignore[no-untyped-def] # noqa: E501
    """Request URL.

    Args:
        method (str): request method.
        url (str): url.
        headers (Dict[str, str]): headers to pass to the API.
        kwargs: arguments.

    Raises:
        SynapseServerError: if an error happens during the request.

    Returns:
        requests.Response: API response.
    """
    try:
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response
    except requests.exceptions.Timeout as exc:
        logger.error("Request to %s timed out.", url)
        raise SynapseServerError(f"Request to {url} timed out.") from exc
    except requests.exceptions.RequestException as exc:
        logger.error("Request to %s failed: %s", url, str(exc))
        raise SynapseServerError(f"Request to {url} failed") from exc


def impersonate_user(admin_access_token: str, server_url: str, user_id: str) -> Optional[str]:
    """Impersonate user.

    Args:
        admin_access_token (str): admin token.
        server_url (str): server url.
        user_id (str): user id.

    Raises:
        SynapseImpersonateError: error during login.

    Returns:
        Optional[str]: access token.
    """
    headers = get_headers(admin_access_token)
    url = f"{server_url}/_synapse/admin/v1/users/{user_id}/login"
    try:
        response = make_request("POST", url, headers=headers)
    except SynapseServerError as exc:
        logger.error("Failed to impersonate user %s", user_id)
        raise SynapseImpersonateError((f"Failed to impersonate user {user_id}")) from exc
    access_token = response.json().get("access_token", "")
    return access_token


def get_current_user(admin_access_token: str, server_url: str) -> str:
    """Get current user.

    Args:
        admin_access_token (str): admin token.
        server_url (str): server url.

    Raises:
        SynapseWhoAmIError: error getting user.

    Returns:
        str: user id.
    """
    headers = get_headers(admin_access_token)
    whoami_url = f"{server_url}/_matrix/client/v3/account/whoami"
    try:
        response = make_request("GET", whoami_url, headers=headers)
    except SynapseServerError as exc:
        logger.error("Failed to identify the user linked to the Admin token.")
        raise SynapseWhoAmIError("Failed to identify the user linked to the Admin token.") from exc
    whoami_result = response.json()
    return whoami_result.get("user_id", "")


def get_public_rooms(admin_access_token: str, server_url: str, limit: int = 30) -> list:
    """Get public rooms.

    Args:
        admin_access_token (str): admin token.
        server_url (str): server url.
        limit (int, optional): Limit rooms. Defaults to 30.

    Raises:
        SynapseServerError: error in Synapse server.

    Returns:
        list of public rooms.
    """
    headers = get_headers(admin_access_token)
    url = f"{server_url}/_matrix/client/r0/publicRooms?limit={limit}"
    try:
        response = make_request("GET", url, headers)
    except SynapseServerError as exc:
        logger.error("Failed to fetch public rooms.")
        raise SynapseServerError("Failed to fetch public rooms.") from exc

    data = response.json()
    public_rooms = data.get("chunk", [])
    total = data.get("total_room_count_estimate", len(public_rooms))
    print(f"Total public rooms (limit {limit}): {total}")
    return public_rooms


def is_room_version_missing(admin_access_token: str, server_url: str, version: str) -> bool:
    """Check if room version is missing.

    Args:
        admin_access_token (str): admin token.
        server_url (str): server url.
        version (str): version.

    Raises:
        SynapseServerError: error in Synapse server.

    Returns:
        if room version is missing or not.
    """
    headers = get_headers(admin_access_token)
    url = f"{server_url}/_matrix/client/r0/capabilities"
    try:
        response = make_request("GET", url, headers)
    except SynapseServerError as exc:
        logger.error("Failed to fetch server capabilities.")
        raise SynapseServerError("Failed to fetch server capabilities.") from exc

    data = response.json()
    versions = data.get("capabilities", {}).get("m.room_versions", {}).get("available", {})
    if version not in versions:
        versions = list(versions.keys())
        logger.error("Room version %s not found. Available versions: %s", version, versions)
        return True
    return False


def upgrade_room(admin_access_token: str, server_url: str, room_id: str, new_version: str) -> None:
    """Upgrade a Matrix room to a new version.

    Args:
        admin_access_token (str): Admin access token.
        server_url (str): Matrix server URL (e.g., https://matrix.example.org).
        room_id (str): The ID of the room to upgrade.
        new_version (str): The new version to upgrade the room to.

    Raises:
        SynapseServerError: If the upgrade fails.
    """
    headers = get_headers(admin_access_token)
    url = f"{server_url}/_matrix/client/v3/rooms/{room_id}/upgrade"
    body = {"new_version": new_version}

    try:
        response = make_request("POST", url, headers, json=body)
    except SynapseServerError as exc:
        logger.error("Request failed while upgrading room %s.", room_id)
        raise SynapseServerError("Failed to upgrade the room.") from exc

    if response.status_code == 200:
        replacement_room = response.json().get("replacement_room")
        logger.info(
            "Room %s successfully upgraded to %s. Replacement: %s",
            room_id,
            new_version,
            replacement_room,
        )

    elif response.status_code == 400:
        error = response.json()
        logger.error("Unsupported room version: %s", error.get("error"))
        raise SynapseServerError(error.get("error", "Unsupported room version"))

    elif response.status_code == 403:
        error = response.json()
        logger.error("Forbidden to upgrade room: %s", error.get("error"))
        raise SynapseServerError(error.get("error", "You cannot upgrade this room"))

    else:
        logger.error("Unexpected error upgrading room: HTTP %d", response.status_code)
        raise SynapseServerError(f"Unexpected error: HTTP {response.status_code}")


def main() -> None:
    """Main function.

    Raises:
        SynapseWhoAmIError: error getting user id.
    """
    parser = argparse.ArgumentParser(
        description="Upgrade public rooms to a new version as a specific user."
    )
    parser.add_argument("--server-url", required=True, help="Matrix Synapse server URL")
    parser.add_argument("--version", required=True, help="New version for the public rooms")
    parser.add_argument(
        "--room-id",
        help="Optional: Public room ID to upgrade. If omitted, upgrades all public rooms",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Optional: Only list public rooms and their versions",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="Limit the number of public rooms returned in --dry-run (default: 30).",
    )
    args = parser.parse_args()

    admin_access_token = os.environ.get("ADMIN_ACCESS_TOKEN")
    if not admin_access_token:
        logger.error("ADMIN_ACCESS_TOKEN environment variable not set.")
        sys.exit(1)

    server_url = args.server_url

    current_user = get_current_user(admin_access_token, server_url)
    if not current_user:
        raise SynapseWhoAmIError("No user_id returned by Who Am I endpoint.")

    logger.info("Currently logged in user %s", current_user)

    version = args.version
    if is_room_version_missing(admin_access_token, server_url, version):
        logger.error("Room version %s not supported by server.", version)
        sys.exit(1)

    logger.info("Room version %s is supported by the server.", version)

    public_rooms = get_public_rooms(admin_access_token, server_url, limit=args.limit)
    if args.dry_run:
        logger.info("[DRY-RUN] Listing up to %d public rooms from %s", args.limit, server_url)
        for room in public_rooms:
            name = room.get("name", "")
            room_id = room.get("room_id", "")
            num_joined = room.get("num_joined_members", 0)
            print(f"{name};{room_id};{num_joined}")
        return

    if args.room_id:
        logger.info("room-id is set, upgrading %s", args.room_id)
        upgrade_room(admin_access_token, server_url, args.room_id, version)
        return

    for room in public_rooms:
        room_id = room.get("room_id", "")
        upgrade_room(admin_access_token, server_url, args.room_id, version)


if __name__ == "__main__":
    main()
