# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper functions for integration tests."""

import typing

import requests
from juju.application import Application
from juju.model import Model

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, "active")  # type: ignore


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


async def wait_for_deployment(
    model: Model,
    apps: typing.List[str],
    status: str = ACTIVE_STATUS_NAME,
    idle_period: int = 10,
    timeout: int = 300,
) -> None:
    """Optimized wait for deployment with reasonable defaults.

    Args:
        model: Juju model
        apps: List of application names to wait for
        status: Expected status (default: active)
        idle_period: Time to wait for idle state (default: 10s)
        timeout: Maximum timeout (default: 5min)
    """
    await model.wait_for_idle(apps=apps, status=status, idle_period=idle_period, timeout=timeout)


async def setup_s3_integration(
    model: Model,
    synapse_app: Application,
    s3_integrator_app: Application,
    relation_name: str = "backup",
) -> None:
    """Helper to set up S3 integration with optimized waits.

    Args:
        model: Juju model
        synapse_app: Synapse application
        s3_integrator_app: S3 integrator application
        relation_name: Relation name (backup or s3-media)
    """
    await model.add_relation(s3_integrator_app.name, f"{synapse_app.name}:{relation_name}")
    await wait_for_deployment(model, [s3_integrator_app.name])
    await wait_for_deployment(model, [synapse_app.name, s3_integrator_app.name], idle_period=15)


async def register_user(
    unit: typing.Any,
    username: str,
    password: str,
    admin: bool,
) -> typing.Dict[str, typing.Any]:
    """Register a new user in Synapse.

    Args:
        unit: Unit to connect to.
        username: username to register.
        password: password for the user.
        admin: whether user should be admin.

    Returns:
        The response of the register user action.
    """
    action = await unit.run_action(
        "register-user",
        username=username,
        password=password,
        admin=admin,
    )
    await action.wait()
    return action.results
