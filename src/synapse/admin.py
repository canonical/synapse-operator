#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage admin tasks involving Synapse API and Workload."""

import logging
import typing
from secrets import token_hex

import ops

from user import User

from .api import register_user
from .workload import get_registration_shared_secret

logger = logging.getLogger(__name__)


def create_admin_user(container: ops.Container) -> typing.Optional[User]:
    """Create admin user.

    Args:
        container: Container of the charm.

    Returns:
        Admin user with token to be used in Synapse API requests or None if fails.
    """
    # The username is random because if the user exists, register_user will try to get the
    # access_token.
    # But to do that it needs an admin user and we don't have one yet.
    # So, to be on the safe side, the user name is randomly generated and if for any reason
    # there is no access token on peer data/secret, another user will be created.
    #
    # Using 16 to create a random value but to  be secure against brute-force attacks,
    # please check the docs:
    # https://docs.python.org/3/library/secrets.html#how-many-bytes-should-tokens-use
    username = token_hex(16)
    return create_user(container, username=username, admin=True)


def create_user(
    container: ops.Container,
    username: str,
    admin: bool = False,
    admin_access_token: typing.Optional[str] = None,
    server: str = "",
) -> typing.Optional[User]:
    """Create user by using the registration shared secret and generating token via API.

    Args:
        container: Container of the charm.
        username: username to be registered.
        admin: if user is admin.
        server: to be used to create the user id.
        admin_access_token: server admin access token to get user's access token if it exists.

    Returns:
        User or none if the creation fails.
    """
    registration_shared_secret = get_registration_shared_secret(container=container)
    if registration_shared_secret is None:
        logger.error("registration_shared_secret was not found, please check the logs")
        return None
    user = User(username=username, admin=admin)
    user.access_token = register_user(
        registration_shared_secret=registration_shared_secret,
        user=user,
        admin_access_token=admin_access_token,
        server=server,
    )
    return user
