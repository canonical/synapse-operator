# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Actions package is used to run actions provided by the charm."""

# Exporting methods to be used for another modules
from .register_user import RegisterUserError, register_user  # noqa: F401
