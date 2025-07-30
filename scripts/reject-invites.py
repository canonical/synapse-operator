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


def get_banned_users(
    admin_access_token: str, server_url: str, policy_rooms: List[str]
) -> Set[str]:
    headers = get_headers(admin_access_token)
    banned_users: Set[str] = set()
    for room_id in policy_rooms:
        url = f"{server_url}/_synapse/admin/v1/rooms/{room_id}/state"
        try:
            response = make_request("GET", url, headers=headers)
        except SynapseServerError as exc:
            logger.error(f"Failed to fetch state for room {room_id}")
            continue
        state_events = response.json()
        for event in state_events.get("state", {}):
            if event.get("type", "") != "m.policy.rule.user":
                continue
            entity = event.get("content", {}).get("entity", "")
            if entity:
                banned_users.add(entity)
    return banned_users


def get_all_users(
    admin_access_token: str, server_url: str
) -> Generator[Dict[str, Any], None, None]:
    headers = get_headers(admin_access_token)
    url = f"{server_url}/_synapse/admin/v3/users"
    params = {
        "limit": 100,
        "deactivated": "false",
    }
    next_token = 0
    while True:
        try:
            response = make_request("GET", url, headers=headers, params=params)
        except SynapseServerError:
            logger.error(f"Failed to fetch users from {next_token}")
            break
        result = response.json()
        users = result.get("users", [])
        for user in users:
            yield user
        next_token = result.get("next_token")
        if not next_token:
            break
        params["from"] = next_token


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


def get_user_invites(
    server_url: str, user_access_token: str, user_id: str
) -> Dict[str, Any]:
    headers = get_headers(user_access_token)
    sync_url = f"{server_url}/_matrix/client/v3/sync"
    params = {
        "account_data": {"not_types": ["*"]},
        "presence": {"not_types": ["*"]},
        "room": {
            "timeline": {"not_types": ["*"]},
            "ephemeral": {"not_types": ["*"]},
            "account_data": {"not_types": ["*"]},
            "state": {"types": ["m.room.create"]},
        },
    }
    try:
        response = make_request("GET", sync_url, headers=headers, params=params)
    except SynapseServerError:
        logger.error(f"Failed to sync for user: {user_id}")
        return {}

    sync_result = response.json()
    invites = sync_result.get("rooms", {}).get("invite", {})
    return invites


def reject_invite(server_url: str, user_access_token: str, room_id: str) -> None:
    headers = get_headers(user_access_token)
    url = f"{server_url}/_matrix/client/v3/rooms/{room_id}/leave"
    try:
        response = make_request("POST", url, headers=headers)
    except SynapseServerError:
        logger.error(f"Failed to reject invite to {room_id}")
    logger.info(f"Successfully rejected invite to {room_id}")


def process_invites_for_user(
    admin_access_token: str, server_url: str, user_id: str, banned_users: Set[str]
) -> None:
    user_access_token = impersonate_user(admin_access_token, server_url, user_id)
    if not user_access_token:
        raise SynapseImpersonateError("No token retrieved for user_id: {user_id}")
    invites = get_user_invites(server_url, user_access_token, user_id)
    for room_id, room_data in invites.items():
        invite_events = room_data.get("invite_state", {}).get("events", [])
        inviter = None
        for event in invite_events:
            if event.get("type") == "m.room.create":
                inviter = event.get("sender")
                break
        if inviter and inviter in banned_users:
            logger.info(
                f"Rejecting invite from inviter: {inviter}, to room ID: {room_id}"
            )
            reject_invite(server_url, user_access_token, room_id)


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reject pending invitations from banned users."
    )
    parser.add_argument("--server-url", required=True, help="Matrix Synapse server URL")
    parser.add_argument(
        "--policy-rooms",
        required=True,
        help="Comma-separated list of room IDs where banned users are defined",
    )
    args = parser.parse_args()

    admin_access_token = os.environ.get("ADMIN_ACCESS_TOKEN")
    if not admin_access_token:
        logger.error("ADMIN_ACCESS_TOKEN environment variable not set.")
        exit(1)

    policy_rooms = args.policy_rooms.split(",")
    server_url = args.server_url

    banned_users = get_banned_users(admin_access_token, server_url, policy_rooms)
    logger.info(f"Banned users: {len(banned_users)}")

    current_user = get_current_user(admin_access_token, server_url)
    if not current_user:
        raise SynapseWhoAmIError("No user_id returned by Who Am I endpoint.")
    logger.info(f"Currently logged in user {current_user}")

    total_users = 0
    for user in get_all_users(admin_access_token, server_url):
        user_id = user.get("name")
        if not user_id:
            logger.error("Skipping user {user} no name found")
            continue
        if user_id == current_user:
            logger.info(f"Skipping currently logged in user {current_user}")
            continue
        total_users += 1
        logger.info(f"Processing user {user_id}")
        process_invites_for_user(admin_access_token, server_url, user_id, banned_users)
    logger.info(f"Processed {total_users} users.")


if __name__ == "__main__":
    main()
