#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""User class."""

import logging
import secrets
import string

# pydantic is causing this no-name-in-module problem
from pydantic import BaseModel, Field, validator  # pylint: disable=no-name-in-module,import-error

logger = logging.getLogger(__name__)


def _generate_password() -> str:
    """Set password to user. Extracted from postgresql-k8s charm.

    Returns:
        random password.
    """
    choices = string.ascii_letters + string.digits
    password = "".join([secrets.choice(choices) for i in range(16)])
    return password


class User(BaseModel):
    """Synapse user.

    Attributes:
        username: username to be registered.
        admin: if user is an admin.
        password: users password.
        access_token: obtained when the user is registered.
    """

    username: str
    admin: bool = Field(False)
    password: str = Field("")
    access_token: str = Field("")

    def __init__(self, username: str, admin: bool) -> None:
        """Initialize the User.

        Args:
            username: username to be registered.
            admin: if is admin.
        """
        data = {"username": username, "admin": admin}
        super().__init__(**data)
        self.password = _generate_password()

    @validator("username")
    #  pylint don't quite understand that this is a classmethod using Pydantic
    def username_must_not_be_empty(  # pylint: disable=no-self-argument, invalid-name
        cls: "User", v: str
    ) -> str:
        """Check if username is empty.

        Args:
            v: value received.

        Raises:
            ValueError: if username is empty

        Returns:
            username.
        """
        if not v.strip():
            raise ValueError("Username must not be empty.")
        return v
