# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse package is used to interact with Synapse instance."""

# Exporting methods to be used for another modules
from .api import (  # noqa: F401
    APIError,
    RoomNotFoundError,
    deactivate_user,
    get_access_token,
    get_room_id,
    get_version,
    make_room_admin,
    override_rate_limit,
    register_user,
)
from .workload import (  # noqa: F401
    ExecResult,
    WorkloadError,
    check_alive,
    check_mjolnir_ready,
    check_nginx_ready,
    check_ready,
    create_mjolnir_config,
    enable_metrics,
    enable_saml,
    execute_migrate_config,
    get_environment,
    get_registration_shared_secret,
    reset_instance,
)
