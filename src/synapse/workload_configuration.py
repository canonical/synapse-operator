#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage interactions with Synapse homeserver configuration."""

import logging

from charm_state import CharmState

from .workload import SYNAPSE_EXPORTER_PORT, EnableMetricsError, EnableSMTPError, WorkloadError

logger = logging.getLogger(__name__)


def _create_tuple_from_string_list(string_list: str) -> tuple[str, ...]:
    """Format IP range whitelist.

    Args:
        string_list: comma separated list configuration.

    Returns:
        Tuple as expected by Synapse.
    """
    return tuple(item.strip() for item in string_list.split(","))


def set_public_baseurl(current_yaml: dict, charm_state: CharmState) -> None:
    """Set the homeserver's public address.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.
    """
    current_yaml["public_baseurl"] = charm_state.synapse_config.public_baseurl


def disable_password_config(current_yaml: dict) -> None:
    """Change the Synapse configuration to disable password config.

    Args:
        current_yaml: current configuration.
    """
    current_yaml["password_config"] = {"enabled": False}


def disable_room_list_search(current_yaml: dict) -> None:
    """Change the Synapse configuration to disable room_list_search.

    Args:
        current_yaml: current configuration.
    """
    current_yaml["enable_room_list_search"] = False


def block_non_admin_invites(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to block non admin room invitations.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.
    """
    current_yaml["block_non_admin_invites"] = charm_state.synapse_config.block_non_admin_invites


def enable_allow_public_rooms_over_federation(current_yaml: dict) -> None:
    """Change the Synapse configuration to allow public rooms in federation.

    Args:
        current_yaml: current configuration.
    """
    current_yaml["allow_public_rooms_over_federation"] = True


def enable_federation_domain_whitelist(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable federation_domain_whitelist.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling configuration.
    """
    try:
        federation_domain_whitelist = charm_state.synapse_config.federation_domain_whitelist
        if federation_domain_whitelist is not None:
            current_yaml["federation_domain_whitelist"] = _create_tuple_from_string_list(
                federation_domain_whitelist
            )
    except KeyError as exc:
        raise WorkloadError(str(exc)) from exc


def enable_federation_sender(current_yaml: dict) -> None:
    """Change the Synapse configuration to federation sender config.

    Args:
        current_yaml: current configuration.
    """
    current_yaml["send_federation"] = True
    current_yaml["federation_sender_instances"] = ["federationsender1"]


def enable_forgotten_room_retention(current_yaml: dict) -> None:
    """Change the Synapse configuration to enable forgotten_room_retention_period.

    Args:
        current_yaml: current configuration.
    """
    current_yaml["forgotten_room_retention_period"] = "28d"


def enable_instance_map(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to instance_map config.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.
    """
    current_yaml["instance_map"] = charm_state.instance_map_config


def enable_ip_range_whitelist(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable ip_range_whitelist.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling configuration.
    """
    try:
        ip_range_whitelist = charm_state.synapse_config.ip_range_whitelist
        if ip_range_whitelist is None:
            logger.warning("enable_ip_range_whitelist called but config is empty")
            return
        current_yaml["ip_range_whitelist"] = _create_tuple_from_string_list(ip_range_whitelist)
    except KeyError as exc:
        raise WorkloadError(str(exc)) from exc


def enable_limit_remote_rooms_complexity(current_yaml: dict, charm_state: CharmState) -> None:
    """Enable limit_remote_rooms complexity.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.
    """
    limit_remote_rooms = {
        "enabled": True,
        "complexity": charm_state.synapse_config.limit_remote_rooms_complexity,
    }
    current_yaml["limit_remote_rooms"] = limit_remote_rooms


def enable_media(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable S3.

    Args:
        current_yaml: Current Configuration.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling S3.
    """
    try:
        if charm_state.media_config is None:
            raise WorkloadError(
                "Media Configuration not found. "
                "Please verify the integration between Media and Synapse."
            )
        current_yaml["media_storage_providers"] = [
            {
                "module": "s3_storage_provider.S3StorageProviderBackend",
                "store_local": True,
                "store_remote": True,
                "store_synchronous": True,
                "config": {
                    "bucket": charm_state.media_config["bucket"],
                    "region_name": charm_state.media_config["region_name"],
                    "endpoint_url": charm_state.media_config["endpoint_url"],
                    "access_key_id": charm_state.media_config["access_key_id"],
                    "secret_access_key": charm_state.media_config["secret_access_key"],
                    "prefix": charm_state.media_config["prefix"],
                },
            },
        ]
    except KeyError as exc:
        raise WorkloadError(str(exc)) from exc


def enable_media_retention(current_yaml: dict) -> None:
    """Change the Synapse configuration to enable media retention.

    Args:
        current_yaml: current configuration.
    """
    current_yaml["media_retention"] = {
        "remote_media_lifetime": "14d",
        "local_media_lifetime": "28d",
    }


def enable_metrics(current_yaml: dict) -> None:
    """Change the Synapse configuration to enable metrics.

    Args:
    current_yaml: current configuration.

    Raises:
        EnableMetricsError: something went wrong enabling metrics.
    """
    try:
        metric_listener = {
            "port": int(SYNAPSE_EXPORTER_PORT),
            "type": "metrics",
            "bind_addresses": ["::"],
        }
        current_yaml["listeners"].extend([metric_listener])
        current_yaml["enable_metrics"] = True
    except KeyError as exc:
        raise EnableMetricsError(str(exc)) from exc


def enable_rc_joins_remote_rate(current_yaml: dict, charm_state: CharmState) -> None:
    """Enable rc_joins remote rate.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.
    """
    rc_joins = {
        "remote": {
            "per_second": charm_state.synapse_config.rc_joins_remote_per_second,
            "burst_count": charm_state.synapse_config.rc_joins_remote_burst_count,
        }
    }
    current_yaml["rc_joins"] = rc_joins


def enable_redis(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable Redis.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling Redis.
    """
    try:
        current_yaml["redis"] = {}

        if charm_state.redis_config is None:
            raise WorkloadError(
                "Redis Configuration not found. "
                "Please verify the integration between Redis and Synapse."
            )

        redis_config = charm_state.redis_config
        current_yaml["redis"]["enabled"] = True
        current_yaml["redis"]["host"] = redis_config["host"]
        current_yaml["redis"]["port"] = redis_config["port"]
    except KeyError as exc:
        raise WorkloadError(str(exc)) from exc


def enable_registration_secrets(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable registration secrets.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling registration secrets.
    """
    try:
        if charm_state.registration_secrets is None:
            return
        current_yaml["app_service_config_files"] = [
            str(registration_secret.file_path)
            for registration_secret in charm_state.registration_secrets
        ]
    except KeyError as exc:
        raise WorkloadError(str(exc)) from exc


def enable_replication(current_yaml: dict) -> None:
    """Change the Synapse configuration to enable replication.

    Args:
        current_yaml: current configuration.

    Raises:
        WorkloadError: something went wrong enabling replication.
    """
    try:
        resources = {"names": ["replication"]}
        replication_listener = {
            "port": 8035,
            "type": "http",
            "bind_addresses": ["::"],
            "resources": [resources],
        }
        current_yaml["listeners"].extend([replication_listener])
    except KeyError as exc:
        raise WorkloadError(str(exc)) from exc


def enable_room_list_publication_rules(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable room_list_publication_rules.

    This configuration is based on publish_rooms_allowlist charm configuration.
    Once is set, a deny rule is added to prevent any other user to publish rooms.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling room_list_publication_rules.
    """
    room_list_publication_rules = []
    # checking publish_rooms_allowlist to fix union-attr mypy error
    publish_rooms_allowlist = charm_state.synapse_config.publish_rooms_allowlist
    if publish_rooms_allowlist:
        for user in publish_rooms_allowlist:
            rule = {"user_id": user, "alias": "*", "room_id": "*", "action": "allow"}
            room_list_publication_rules.append(rule)

    if len(room_list_publication_rules) == 0:
        raise WorkloadError("publish_rooms_allowlist has unexpected value. Please, verify it.")

    last_rule = {"user_id": "*", "alias": "*", "room_id": "*", "action": "deny"}
    room_list_publication_rules.append(last_rule)
    current_yaml["room_list_publication_rules"] = room_list_publication_rules


def enable_synapse_invite_checker(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable synapse_invite_checker.

    Args:
        current_yaml: Current Configuration.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling synapse_invite_checker.
    """
    try:
        if "modules" not in current_yaml:
            current_yaml["modules"] = []
        config = {}
        if charm_state.synapse_config.invite_checker_blocklist_allowlist_url:
            config["blocklist_allowlist_url"] = (
                charm_state.synapse_config.invite_checker_blocklist_allowlist_url
            )
        if charm_state.synapse_config.invite_checker_policy_rooms:
            config["policy_room_ids"] = charm_state.synapse_config.invite_checker_policy_rooms
        current_yaml["modules"].append(
            {"module": "synapse_invite_checker.InviteChecker", "config": config},
        )
    except KeyError as exc:
        raise WorkloadError(str(exc)) from exc


def enable_serve_server_wellknown(current_yaml: dict) -> None:
    """Change the Synapse configuration to enable server wellknown file.

    Args:
        current_yaml: current configuration.
    """
    current_yaml["serve_server_wellknown"] = True


def enable_smtp(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to enable SMTP.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.

    Raises:
        EnableSMTPError: something went wrong enabling SMTP.
    """
    try:
        current_yaml["email"] = {}
        current_yaml["email"]["enable_notifs"] = charm_state.synapse_config.enable_email_notifs
        current_yaml["email"]["notif_from"] = charm_state.synapse_config.notif_from

        if charm_state.smtp_config is None:
            raise EnableSMTPError(
                "SMTP Configuration not found. "
                "Please verify the integration between SMTP Integrator and Synapse."
            )

        smtp_config = charm_state.smtp_config
        current_yaml["email"]["smtp_host"] = smtp_config["host"]
        current_yaml["email"]["smtp_port"] = smtp_config["port"]
        if charm_state.smtp_config["user"] is not None:
            current_yaml["email"]["smtp_user"] = smtp_config["user"]
        if charm_state.smtp_config["password"] is not None:
            current_yaml["email"]["smtp_pass"] = smtp_config["password"]
        current_yaml["email"]["enable_tls"] = smtp_config["enable_tls"]
        current_yaml["email"]["force_tls"] = smtp_config["force_tls"]
        current_yaml["email"]["require_transport_security"] = smtp_config[
            "require_transport_security"
        ]
    except KeyError as exc:
        raise EnableSMTPError(str(exc)) from exc


def enable_stale_devices_deletion(current_yaml: dict) -> None:
    """Change the Synapse configuration to delete stale devices.

    Args:
        current_yaml: current configuration.
    """
    current_yaml["delete_stale_devices_after"] = "1y"


def enable_stream_writers(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to stream_writers config.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.
    """
    persisters = []
    if charm_state.instance_map_config is not None:
        persisters = [
            key
            for key in charm_state.instance_map_config.keys()
            if key not in ["main", "federationsender1"]
        ]
        persisters.sort()
    if persisters is not None:
        current_yaml["stream_writers"] = {"events": persisters}
    else:
        logger.error("Enable stream writers called but no persisters found. Verify peer relation.")


def enable_trusted_key_servers(current_yaml: dict, charm_state: CharmState) -> None:
    """Change the Synapse configuration to set trusted_key_servers.

    Args:
        current_yaml: current configuration.
        charm_state: Instance of CharmState.

    Raises:
        WorkloadError: something went wrong enabling configuration.
    """
    try:
        trusted_key_servers = charm_state.synapse_config.trusted_key_servers
        if trusted_key_servers is not None:
            current_yaml["trusted_key_servers"] = tuple(
                {"server_name": f"{item}"}
                for item in _create_tuple_from_string_list(trusted_key_servers)
            )
    except KeyError as exc:
        raise WorkloadError(str(exc)) from exc
