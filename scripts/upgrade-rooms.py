# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

import argparse
import logging
import os
from typing import Any, Dict, Generator, List, Optional, Set

import requests

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s.%(msecs)03d %(levelname)s %(module)s - %(funcName)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class SynapseServerError(Exception):
    pass


class SynapseImpersonateError(Exception):
    pass


class SynapseWhoAmIError(Exception):
    pass


def get_headers(access_token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


def make_request(
    method: str, url: str, headers: Dict[str, str], **kwargs
) -> requests.Response:
    try:
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response
    except requests.exceptions.Timeout as exc:
        logger.error(f"Request to {url} timed out.")
        raise SynapseServerError(f"Request to {url} timed out.") from exc
    except requests.exceptions.RequestException as exc:
        logger.error(f"Request to {url} failed: {exc}")
        raise SynapseServerError(f"Request to {url} failed") from exc


def impersonate_user(
    admin_access_token: str, server_url: str, user_id: str
) -> Optional[str]:
    headers = get_headers(admin_access_token)
    url = f"{server_url}/_synapse/admin/v1/users/{user_id}/login"
    try:
        response = make_request("POST", url, headers=headers)
    except SynapseServerError as exc:
        logger.error(f"Failed to impersonate user {user_id}")
        raise SynapseImpersonateError(
            (f"Failed to impersonate user {user_id}")
        ) from exc
    access_token = response.json().get("access_token", "")
    return access_token


def get_current_user(admin_access_token: str, server_url: str) -> str:
    headers = get_headers(admin_access_token)
    whoami_url = f"{server_url}/_matrix/client/v3/account/whoami"
    try:
        response = make_request("GET", whoami_url, headers=headers)
    except SynapseServerError as exc:
        logger.error("Failed to identify the user linked to the Admin token.")
        raise SynapseWhoAmIError(
            "Failed to identify the user linked to the Admin token."
        ) from exc
    whoami_result = response.json()
    return whoami_result.get("user_id", "")


def print_public_rooms(admin_access_token: str, server_url: str, limit: int = 30) -> None:
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

    for room in public_rooms:
        name = room.get("name", "")
        room_id = room.get("room_id", "")
        num_joined = room.get("num_joined_members", 0)
        print(f"{name};{room_id};{num_joined}")


def is_room_version_missing(admin_access_token: str, server_url: str, version: str) -> None:
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
        logger.error(
            f"Room version '{version}' not found. Available versions: {list(versions.keys())}"
        )
        return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upgrade public rooms to a new version as a specific user."
    )
    parser.add_argument("--server-url", required=True, help="Matrix Synapse server URL")
    parser.add_argument("--version", required=True, help="New version for the public rooms")
    parser.add_argument("--room-id", help="Optional: Public room ID to upgrade. If omitted, upgrades all public rooms")
    parser.add_argument("--dry-run", action="store_true", help="Optional: Only list public rooms and their versions")
    parser.add_argument("--limit", type=int, default=30, help="Limit the number of public rooms returned in --dry-run (default: 30).")
    args = parser.parse_args()

    admin_access_token = os.environ.get("ADMIN_ACCESS_TOKEN")
    if not admin_access_token:
        logger.error("ADMIN_ACCESS_TOKEN environment variable not set.")
        exit(1)

    server_url = args.server_url

    current_user = get_current_user(admin_access_token, server_url)
    if not current_user:
        raise SynapseWhoAmIError("No user_id returned by Who Am I endpoint.")

    logger.info(f"Currently logged in user {current_user}")

    version = args.version
    if is_room_version_missing(admin_access_token, server_url, version):
        logger.error(
            f"Room version '{version}' not supported by server."
        )
        exit(1)

    logger.info(f"Room version '{version}' is supported by the server.")

    if args.dry_run:
        logger.info(f"[DRY-RUN] Listing up to {args.limit} public rooms from {server_url}")
        print_public_rooms(admin_access_token, server_url, limit=args.limit)
        return


if __name__ == "__main__":
    main()
