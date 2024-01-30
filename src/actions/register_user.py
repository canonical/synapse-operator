#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module to interact with Register User action."""

import logging
import typing

import ops

# pydantic is causing this no-name-in-module problem
from pydantic import ValidationError  # pylint: disable=no-name-in-module,import-error

import synapse
from user import User

logger = logging.getLogger(__name__)


class RegisterUserError(Exception):
    """Exception raised when something fails while running register-user.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the RegisterUserError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


# access_token is not a password
def register_user(
    container: ops.Container,
    username: str,
    admin: bool,
    admin_access_token: typing.Optional[str] = None,
    server: str = "",
) -> User:
    """Run register user action.

    Args:
        container: Container of the charm.
        username: username to be registered.
        admin: if user is admin.
        server: to be used to create the user id.
        admin_access_token: server admin access token to get user's access token if it exists.

    Raises:
        RegisterUserError: if something goes wrong while registering the user.

    Returns:
        User with password registered.
    """
    try:
        user = synapse.create_user(
            container=container,
            username=username,
            admin=admin,
            admin_access_token=admin_access_token,
            server=server,
        )
        if not user:
            raise RegisterUserError(f"Failed to register user {username}")
        return user
    except (ValidationError, synapse.APIError) as exc:
        raise RegisterUserError(str(exc)) from exc
