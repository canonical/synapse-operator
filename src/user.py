# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""The module for checking time ranges."""

import secrets
import string
import typing

from pydantic import BaseModel, Field, validator


class User(BaseModel):
    """Synapse user.

    Attributes:
        username: username to be registered.
        admin: if user is an admin.
        password: users password.
    """

    username: str
    admin: bool = Field(False)
    password: str = Field("")

    def __init__(self, **data: dict[str, typing.Any]) -> None:
        """Initialize a new User instance.

        Parameters:
            data: A dictionary containing the user data.
        """
        super().__init__(**data)
        self._set_password()

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

    def _set_password(self) -> None:
        """Set password to user. Extracted from postgresql-k8s charm."""
        choices = string.ascii_letters + string.digits
        password = "".join([secrets.choice(choices) for i in range(16)])
        self.password = password
