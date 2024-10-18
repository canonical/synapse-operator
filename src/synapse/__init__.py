# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse package is used to interact with Synapse instance."""

# Exporting methods to be used for another modules
from .admin import create_admin_user, create_user  # noqa: F401
from .api import (  # noqa: F401
    ADD_USER_ROOM_URL,
    CREATE_ROOM_URL,
    DEACTIVATE_ACCOUNT_URL,
    LIST_ROOMS_URL,
    LIST_USERS_URL,
    LOGIN_URL,
    MJOLNIR_MANAGEMENT_ROOM,
    MJOLNIR_MEMBERSHIP_ROOM,
    REGISTER_URL,
    SYNAPSE_PORT,
    SYNAPSE_URL,
    SYNAPSE_VERSION_REGEX,
    VERSION_URL,
    APIError,
    create_management_room,
    deactivate_user,
    get_access_token,
    get_room_id,
    get_version,
    is_token_valid,
    make_room_admin,
    override_rate_limit,
    promote_user_admin,
    register_user,
)
from .workload import (  # noqa: F401
    CHECK_ALIVE_NAME,
    CHECK_MJOLNIR_READY_NAME,
    CHECK_NGINX_READY_NAME,
    CHECK_READY_NAME,
    COMMAND_MIGRATE_CONFIG,
    MJOLNIR_CONFIG_PATH,
    MJOLNIR_HEALTH_PORT,
    MJOLNIR_SERVICE_NAME,
    STATS_EXPORTER_PORT,
    SYNAPSE_COMMAND_PATH,
    SYNAPSE_CONFIG_DIR,
    SYNAPSE_CONFIG_PATH,
    SYNAPSE_CONTAINER_NAME,
    SYNAPSE_CRON_SERVICE_NAME,
    SYNAPSE_DATA_DIR,
    SYNAPSE_DB_RELATION_NAME,
    SYNAPSE_EXPORTER_PORT,
    SYNAPSE_FEDERATION_SENDER_SERVICE_NAME,
    SYNAPSE_GROUP,
    SYNAPSE_NGINX_PORT,
    SYNAPSE_NGINX_SERVICE_NAME,
    SYNAPSE_PEER_RELATION_NAME,
    SYNAPSE_SERVICE_NAME,
    SYNAPSE_USER,
    SYNAPSE_WORKER_CONFIG_PATH,
    ExecResult,
    WorkloadError,
    execute_migrate_config,
    generate_mjolnir_config,
    generate_nginx_config,
    generate_worker_config,
    get_environment,
    get_media_store_path,
    get_registration_shared_secret,
    validate_config,
)
from .workload_configuration import (  # noqa: F401
    block_non_admin_invites,
    disable_password_config,
    disable_room_list_search,
    enable_allow_public_rooms_over_federation,
    enable_federation_domain_whitelist,
    enable_federation_sender,
    enable_forgotten_room_retention,
    enable_instance_map,
    enable_ip_range_whitelist,
    enable_limit_remote_rooms_complexity,
    enable_media,
    enable_media_retention,
    enable_metrics,
    enable_rc_joins_remote_rate,
    enable_redis,
    enable_registration_secrets,
    enable_replication,
    enable_room_list_publication_rules,
    enable_saml,
    enable_serve_server_wellknown,
    enable_smtp,
    enable_stale_devices_deletion,
    enable_stream_writers,
    enable_synapse_invite_checker,
    enable_trusted_key_servers,
)
