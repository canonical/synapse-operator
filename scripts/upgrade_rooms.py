# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Upgrade rooms script."""

# pylint: disable=duplicate-code, line-too-long, too-many-branches
# pylint: disable=too-many-statements, too-many-locals

import argparse
import logging
import os
import sys
import time
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
def make_request(method: str, url: str, headers: Dict[str, str], **kwargs) -> requests.Response:  # type: ignore[no-untyped-def]
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
        logger.info("Requesting %s", url)
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response
    except requests.exceptions.Timeout as exc:
        logger.error("Request timed out.")
        raise SynapseServerError(f"Request to {url} timed out.") from exc
    except requests.exceptions.RequestException as exc:
        logger.error("Request failed: %s", str(exc))
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
        raise SynapseImpersonateError(f"Failed to impersonate user {user_id}") from exc
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
    """Get the public rooms list, ordered from smallest to largest.

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
    url = f"{server_url}/_matrix/client/v3/publicRooms?limit={limit}"
    try:
        response = make_request("GET", url, headers)
    except SynapseServerError as exc:
        logger.error("Failed to fetch public rooms.")
        raise SynapseServerError("Failed to fetch public rooms.") from exc

    data = response.json()
    public_rooms = data.get("chunk", [])
    total = data.get("total_room_count_estimate", len(public_rooms))
    logger.info("Total public rooms (limit %d): %d", limit, total)
    return public_rooms[::-1]


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
    url = f"{server_url}/_matrix/client/v3/capabilities"
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
    """
    headers = get_headers(admin_access_token)
    url = f"{server_url}/_matrix/client/v3/rooms/{room_id}/upgrade"
    body = {"new_version": new_version}

    response = make_request("POST", url, headers, json=body)

    replacement_room = response.json().get("replacement_room")
    logger.info(
        "%s - Room successfully upgraded to %s. Replacement: %s",
        room_id,
        new_version,
        replacement_room,
    )


def get_room_version(admin_access_token: str, server_url: str, room_id: str) -> str:
    """Get the room version from the m.room.create event in a Matrix room.

    Args:
        admin_access_token: Admin access token.
        server_url: Matrix server URL (e.g., https://matrix.example.org).
        room_id: The ID of the room to inspect.

    Returns:
        The room version (e.g., "11").

    Raises:
        SynapseServerError: If the API call fails or the room_version is not found.
    """
    start_time = time.time()
    headers = get_headers(admin_access_token)
    url = f"{server_url}/_matrix/client/v3/rooms/{room_id}/state"
    response = make_request("GET", url, headers)
    events = response.json()
    create_event = next((event for event in events if event.get("type") == "m.room.create"), None)
    if not create_event:
        raise SynapseServerError("m.room.create event not found in room state.")
    room_version = create_event.get("content", {}).get("room_version")
    if not room_version:
        raise SynapseServerError("room_version not found in m.room.create event content.")
    end_time = time.time()
    total_time = end_time - start_time
    logger.info("%s - %d seconds", room_id, total_time)
    return room_version


def main() -> None:  # noqa: C901
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
    parser.add_argument(
        "--ignore-errors",
        action="store_true",
        help="Optional: Don't ask for confirmation on retry and skip errors.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Automatically confirm upgrading each room without prompting.",
    )
    args = parser.parse_args()

    admin_access_token = os.environ.get("ADMIN_ACCESS_TOKEN")
    if not admin_access_token:
        logger.error("ADMIN_ACCESS_TOKEN environment variable not set.")
        sys.exit(1)

    homeserver = os.environ.get("HOMESERVER")
    if not homeserver:
        logger.error("HOMESERVER environment variable not set.")
        sys.exit(1)

    server_url = args.server_url

    current_user = get_current_user(admin_access_token, server_url)
    if not current_user:
        raise SynapseWhoAmIError("No user_id returned by Who Am I endpoint.")

    logger.info("Currently logged in %s with user %s", homeserver, current_user)

    version = args.version
    if is_room_version_missing(admin_access_token, server_url, version):
        logger.error("Room version %s not supported by server.", version)
        sys.exit(1)

    logger.info("Room version %s is supported by the server.", version)

    if not args.room_id:
        public_rooms = get_public_rooms(admin_access_token, server_url, limit=args.limit)
        if args.dry_run:
            logger.info("[DRY-RUN] Listing up to %d public rooms from %s", args.limit, server_url)
            print("room_id;name;total_members;version;error")
            for room in public_rooms:
                name = room.get("name", "")
                room_id = room.get("room_id", "")
                num_joined = room.get("num_joined_members", 0)
                error = ""
                if homeserver not in room_id:
                    continue
                try:
                    room_version = get_room_version(admin_access_token, server_url, room_id)
                except SynapseServerError:
                    error = "Failed"
                print(f"{name};{room_id};{num_joined};{room_version};{error}")
            return

    if args.room_id:
        logger.info("%s - upgrading using room_id", args.room_id)
        current_room_version = get_room_version(admin_access_token, server_url, args.room_id)
        if current_room_version == version:
            logger.warning("%s - room already is version %s, no action", args.room_id, version)
            return
        if args.dry_run:
            logger.info(
                "[DRY-RUN] room %s is version %s and will be upgraded to %s",
                args.room_id,
                current_room_version,
                version,
            )
            return
        upgrade_room(admin_access_token, server_url, args.room_id, version)
        return

    logger.info("all public rooms will be upgraded")
    for room in public_rooms:
        room_id = room.get("room_id", "")
        try:
            current_room_version = get_room_version(admin_access_token, server_url, room_id)
            if current_room_version == version:
                logger.warning("%s - room already is version %s, no action", room_id, version)
                continue
            logger.info("%s - upgrading", room_id)
            upgrade_room(admin_access_token, server_url, room_id, version)
            if args.yes:
                continue
            user_input = input("Next? [y]es / [f]inish ").strip().lower()
            if user_input in {"y", "yes"}:
                continue
            logger.info("Finishing process by user request.")
            sys.exit(1)
        except SynapseServerError:
            logger.info("%s - failed, action required", room_id)
            if args.ignore_errors:
                continue
            while True:
                user_input = (
                    input(
                        f"{room_id} - failed, action required. What do you want to do? [r]etry / [s]kip / [f]inish: "
                    )
                    .strip()
                    .lower()
                )
                if user_input in {"r", "retry"}:
                    try:
                        upgrade_room(admin_access_token, server_url, room_id, version)
                        break  # success, move to next room
                    except SynapseServerError:
                        logger.info("%s - retry failed", room_id)
                        continue
                if user_input in {"s", "skip"}:
                    logger.info("%s - skipped by user", room_id)
                    break
                if user_input in {"f", "finish"}:
                    logger.info("Finishing process by user request.")
                    sys.exit(1)
                else:
                    print("Invalid input. Please type 'r' to retry or 's' to skip.")


if __name__ == "__main__":
    main()
