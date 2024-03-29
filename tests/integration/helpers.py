# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper functions for integration tests."""

import requests
from juju.action import Action
from juju.application import Application


def create_moderators_room(
    synapse_ip: str,
    access_token: str,
):
    """Create "moderators" room in Synapse

    Args:
        synapse_ip: Synapse IP
        access_token: Access token for Synapse to create the room

    """
    authorization_token = f"Bearer {access_token}"
    headers = {"Authorization": authorization_token}
    room_body = {
        "creation_content": {"m.federate": False},
        "name": "moderators",
        "preset": "public_chat",
        "room_alias_name": "moderators",
        "room_version": "1",
        "topic": "moderators",
    }
    res = requests.post(
        f"http://{synapse_ip}:8080/_matrix/client/v3/createRoom",
        json=room_body,
        headers=headers,
        timeout=5,
    )
    res.raise_for_status()


def get_access_token(synapse_ip, user_username, user_password) -> str:
    """Get Access Token for Synapse given user and password

    Args:
        synapse_ip: Synapse IP
        user_username: username of the user to get the access_token
        user_password: password of the user to get the access_token

    Returns:
        The access token
    """
    sess = requests.session()
    res = sess.post(
        f"http://{synapse_ip}:8080/_matrix/client/r0/login",
        json={
            "identifier": {"type": "m.id.user", "user": user_username},
            "password": user_password,
            "type": "m.login.password",
        },
        timeout=5,
    )
    res.raise_for_status()
    access_token = res.json().get("access_token")
    assert access_token
    return access_token


async def register_user(synapse_app: Application, user_username: str) -> str:
    """Register a new user with admin permissions

    Args:
        synapse_app: Synapse App Model
        user_username: username to register

    Returns:
        The new password for the user
    """
    action_register_user: Action = await synapse_app.units[0].run_action(
        "register-user", username=user_username, admin=True
    )
    await action_register_user.wait()
    assert action_register_user.status == "completed"
    assert action_register_user.results.get("register-user")
    password = action_register_user.results.get("user-password")
    assert password
    return password
