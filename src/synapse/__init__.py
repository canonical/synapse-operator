# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse package is used to interact with Synapse instance."""

# Exporting methods to be used for another modules
from .api import APIError, register_user  # noqa: F401
from .workload import (  # noqa: F401
    ExecResult,
    WorkloadError,
    check_ready,
    enable_metrics,
    execute_migrate_config,
    get_environment,
    get_registration_shared_secret,
    reset_instance,
)
