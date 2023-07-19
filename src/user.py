# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""The module for checking time ranges."""

from pydantic import BaseModel, validator


class User(BaseModel):
    """Synapse user.

    Attributes:
        username: username to be registered.
        admin: if user is an admin.
        password: users password.
    """

    username: str
    admin: bool
    password: str

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
