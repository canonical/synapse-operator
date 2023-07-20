# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse package is used to interact with Synapse instance."""

# Exporting methods to be used for another modules
from .api import register_user  # noqa: F401
from .api import NetworkError, RegisterUserError, SynapseAPIError  # noqa: F401
from .workload import (  # noqa: F401
    CommandMigrateConfigError,
    ExecResult,
    ServerNameModifiedError,
    check_ready,
    execute_migrate_config,
    get_environment,
    get_registration_shared_secret,
    reset_instance,
)
