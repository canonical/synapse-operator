# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Send message to room script."""

# pylint: disable=duplicate-code, line-too-long, too-many-branches
# pylint: disable=too-many-statements

import argparse
import logging
import os
import random
import sys
import time
from typing import Dict

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


class SynapsePinMessageError(Exception):
    """Synapse exception during pin message."""


class SynapseSendMessageError(Exception):
    """Synapse exception during send message."""


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
        logger.info("Requesting %s", url)
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        response.raise_for_status()
        return response
    except requests.exceptions.Timeout as exc:
        logger.error("Request timed out.")
        raise SynapseServerError(f"Request to {url} timed out.") from exc
    except requests.exceptions.RequestException as exc:
        print(response.text)
        logger.error("Request failed: %s", str(exc))
        raise SynapseServerError(f"Request to {url} failed") from exc


def impersonate_user(admin_access_token: str, server_url: str, user_id: str) -> str:
    """Impersonate user.

    Args:
        admin_access_token (str): admin token.
        server_url (str): server url.
        user_id (str): user id.

    Raises:
        SynapseImpersonateError: error during login.

    Returns:
        str: access token.
    """
    headers = get_headers(admin_access_token)
    url = f"{server_url}/_synapse/admin/v1/users/{user_id}/login"
    try:
        response = make_request("POST", url, headers=headers)
    except SynapseServerError as exc:
        logger.error("Failed to impersonate user %s", user_id)
        raise SynapseImpersonateError(f"Failed to impersonate user {user_id}") from exc
    access_token = response.json().get("access_token", "")
    if not access_token:
        raise SynapseImpersonateError(f"Failed to get access token for user {user_id}")
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
    user_id = whoami_result.get("user_id", "")
    if not user_id:
        raise SynapseWhoAmIError("No user_id returned by Who Am I endpoint.")
    return user_id


def send_message(
    access_token: str, server_url: str, room_id: str, message: str, message_type: str = "m.text"
) -> str:
    """Send message to room.

    Args:
        access_token (str): access token.
        server_url (str): server url.
        room_id (str): room id.
        message (str): message to send.
        message_type (str): message type (default: m.text).

    Raises:
        SynapseSendMessageError: error during send message.

    Returns:
        str: event id of the sent message.
    """
    headers = get_headers(access_token)
    # Generate a transaction ID to ensure idempotency
    txn_id = f"m{int(time.time() * 1000)}_{random.randint(1000, 9999)}"

    url = f"{server_url}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}"

    message_data = {"msgtype": message_type, "body": message}

    try:
        response = make_request("PUT", url, headers=headers, json=message_data)
    except SynapseServerError as exc:
        logger.error("Failed to send message to room %s", room_id)
        raise SynapseSendMessageError(f"Failed to send message to room {room_id}") from exc

    event_id = response.json().get("event_id", "")
    if not event_id:
        raise SynapseSendMessageError(f"Failed to get event_id for message sent to room {room_id}")

    return event_id


def get_pinned_events(access_token: str, server_url: str, room_id: str) -> list:
    """Get currently pinned events in room.

    Args:
        access_token (str): access token.
        server_url (str): server url.
        room_id (str): room id.

    Returns:
        list: list of currently pinned event IDs.
    """
    headers = get_headers(access_token)
    url = f"{server_url}/_matrix/client/v3/rooms/{room_id}/state/m.room.pinned_events"

    try:
        response = make_request("GET", url, headers=headers)
        pinned_data = response.json()
        return pinned_data.get("pinned", [])
    except SynapseServerError:
        # If no pinned events exist, return empty list
        return []


def pin_message(access_token: str, server_url: str, room_id: str, event_id: str) -> None:
    """Pin a message in the room.

    Args:
        access_token (str): access token.
        server_url (str): server url.
        room_id (str): room id.
        event_id (str): event id of the message to pin.

    Raises:
        SynapsePinMessageError: error during pin message.
    """
    headers = get_headers(access_token)
    url = f"{server_url}/_matrix/client/v3/rooms/{room_id}/state/m.room.pinned_events/"

    # Get current pinned events
    current_pinned = get_pinned_events(access_token, server_url, room_id)

    # Add the new event to the pinned list if not already pinned
    if event_id not in current_pinned:
        current_pinned.append(event_id)

    pin_data = {"pinned": current_pinned}

    try:
        make_request("PUT", url, headers=headers, json=pin_data)
    except SynapseServerError as exc:
        logger.error("Failed to pin message %s in room %s", event_id, room_id)
        raise SynapsePinMessageError(
            f"Failed to pin message {event_id} in room {room_id}"
        ) from exc


def verify_room_exists(access_token: str, server_url: str, room_id: str) -> bool:
    """Verify if room exists and user has access.

    Args:
        access_token (str): access token.
        server_url (str): server url.
        room_id (str): room id.

    Returns:
        bool: True if room exists and user has access, False otherwise.
    """
    headers = get_headers(access_token)
    url = f"{server_url}/_matrix/client/v3/rooms/{room_id}/state"

    try:
        make_request("GET", url, headers=headers)
        return True
    except SynapseServerError:
        return False


def main() -> None:  # noqa: C901
    """Send message to room."""
    parser = argparse.ArgumentParser(
        description="Send a message to a Matrix room using admin token."
    )
    parser.add_argument("--server-url", required=True, help="Matrix Synapse server URL")
    parser.add_argument("--room-id", required=True, help="Room ID to send message to")
    parser.add_argument(
        "--user-id", help="Optional: User ID to send message as (if not provided, uses admin user)"
    )
    parser.add_argument(
        "--message", help="Message to send (if not provided, will be read from stdin)"
    )
    parser.add_argument(
        "--message-type",
        default="m.text",
        help="Message type (default: m.text). Options: m.text, m.emote, m.notice",
    )
    parser.add_argument("--pin", action="store_true", help="Pin the message after sending it")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Optional: Only verify room access without sending message",
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
    room_id = args.room_id
    user_id = args.user_id

    # Verify admin token works
    current_admin_user = get_current_user(admin_access_token, server_url)
    logger.info("Currently logged in %s with admin user %s", homeserver, current_admin_user)

    # Use impersonation if user_id is provided, otherwise use admin token
    if user_id:
        user_access_token = impersonate_user(admin_access_token, server_url, user_id)
        logger.info("Successfully impersonated user %s", user_id)
        acting_user = user_id
    else:
        user_access_token = admin_access_token
        acting_user = current_admin_user
        logger.info("Using admin user %s to send message", acting_user)

    # Verify room access
    if not verify_room_exists(user_access_token, server_url, room_id):
        logger.error(
            "Room %s does not exist or user %s does not have access to it", room_id, acting_user
        )
        sys.exit(1)

    logger.info("User %s has access to room %s", acting_user, room_id)

    if args.dry_run:
        if args.pin:
            logger.info(
                "[DRY-RUN] Would send and pin message to room %s as user %s", room_id, acting_user
            )
        else:
            logger.info("[DRY-RUN] Would send message to room %s as user %s", room_id, acting_user)
        return

    # Get message content
    if args.message:
        message = args.message
    else:
        logger.info("No message provided via --message, reading from stdin...")
        try:
            message = sys.stdin.read().strip()
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            sys.exit(1)

        if not message:
            logger.error("No message content provided")
            sys.exit(1)

    # Send the message
    try:
        event_id = send_message(user_access_token, server_url, room_id, message, args.message_type)
        logger.info("Message sent successfully to room %s as user %s", room_id, acting_user)
        logger.info("Event ID: %s", event_id)

        # Pin the message if requested
        if args.pin:
            try:
                pin_message(user_access_token, server_url, room_id, event_id)
                logger.info("Message pinned successfully in room %s", room_id)
                print(f"Message sent and pinned successfully. Event ID: {event_id}")
            except SynapsePinMessageError as pin_exc:
                logger.error("Message sent but failed to pin: %s", str(pin_exc))
                print(f"Message sent successfully but failed to pin. Event ID: {event_id}")
                print(f"Pin error: {str(pin_exc)}")
        else:
            print(f"Message sent successfully. Event ID: {event_id}")
    except SynapseSendMessageError as exc:
        logger.error("Failed to send message: %s", str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
