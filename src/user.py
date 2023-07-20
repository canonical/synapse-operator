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
    admin: bool
    password: str = Field(None)

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

    @validator("admin")
    #  pylint don't quite understand that this is a classmethod using Pydantic
    def admin_value_must_be_true_for_yes(  # pylint: disable=no-self-argument,  invalid-name
        cls: "User", v: bool, values: dict
    ) -> bool:
        """Check admin value.

        Args:
            v: value received.
            values: value keys of the model.

        Raises:
            ValueError: if was set with something different than yes or no.

        Returns:
            if is admin or not.
        """
        admin = values.get("admin")
        if admin is not None and admin.lower() == "yes" and v is not True:
            raise ValueError("Admin should be set as yes or no.")
        return v

    def _set_password(self) -> None:
        """Set password to user. Extracted from postgresql-k8s charm."""
        choices = string.ascii_letters + string.digits
        password = "".join([secrets.choice(choices) for i in range(16)])
        self.password = password
