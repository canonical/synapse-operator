#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Module to interact with Change User Admin action."""

import logging
import typing

import synapse
from user import User

logger = logging.getLogger(__name__)


class ChangeUserAdminError(Exception):
    """Exception raised when something fails while running change-user-admin.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the ChangeUserAdminError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


# admin_access_token is not a password
def change_user_admin(
    username: str, server: typing.Optional[str], admin_access_token: typing.Optional[str]
) -> None:
    """Run register user action.

    Args:
        username: username to be changed.
        server: to be used to create the user id.
        admin_access_token: server admin access token to call API.

    Raises:
        ChangeUserAdminError: if something goes wrong while changing the user to
            be an admin.
    """
    try:
        user = User(username=username, admin=True)
        synapse.change_user_admin(user=user, server=server, admin_access_token=admin_access_token)
    except synapse.APIError as exc:
        raise ChangeUserAdminError(str(exc)) from exc
