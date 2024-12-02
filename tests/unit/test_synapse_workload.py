# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse workload unit tests."""

# pylint: disable=protected-access, too-many-lines, duplicate-code


import io
import typing
from secrets import token_hex
from unittest.mock import MagicMock, Mock

import ops
import pytest
import yaml
from ops.testing import Harness
from pydantic.v1 import ValidationError

import synapse
from charm_types import SMTPConfiguration
from state.charm_state import CharmState, SynapseConfig


def test_allow_public_rooms_over_federation_sucess(config_content: dict[str, typing.Any]):
    """
    arrange: set mock container with file.
    act: call enable_allow_public_rooms_over_federation.
    assert: new configuration file is pushed and
        allow_public_rooms_over_federation is enabled.
    """
    current_yaml = config_content

    synapse.enable_allow_public_rooms_over_federation(current_yaml)

    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "allow_public_rooms_over_federation": True,
    }
    assert yaml.safe_dump(current_yaml) == yaml.safe_dump(expected_config_content)


@pytest.mark.parametrize(
    "trusted_key_servers,expected_trusted_key_servers",
    [
        pytest.param("", [], id="empty_list", marks=pytest.mark.xfail(strict=True)),
        pytest.param("ubuntu.com", [{"server_name": "ubuntu.com"}], id="single_item"),
        pytest.param(
            "ubuntu.com,canonical.com",
            [{"server_name": "ubuntu.com"}, {"server_name": "canonical.com"}],
            id="multiple_items",
        ),
        pytest.param(
            " ubuntu.com",
            [],
            id="single_item_leading_whitespace",
            marks=pytest.mark.xfail(strict=True),
        ),
        pytest.param(
            " ubuntu.com,canonical.com",
            [],
            id="multiple_items_leading_whitespace",
            marks=pytest.mark.xfail(strict=True),
        ),
        pytest.param(
            "ubuntu.com ",
            [],
            id="single_item_trailing_whitespace",
            marks=pytest.mark.xfail(strict=True),
        ),
        pytest.param(
            "ubuntu.com,canonical.com ",
            [],
            id="multiple_items_trailing_whitespace",
            marks=pytest.mark.xfail(strict=True),
        ),
        pytest.param("111,222", [], id="numbers", marks=pytest.mark.xfail(strict=True)),
        pytest.param(",,,", [], id="only_commas", marks=pytest.mark.xfail(strict=True)),
    ],
)
def test_enable_trusted_key_servers_success(
    trusted_key_servers: str,
    expected_trusted_key_servers: list[dict[str, str]],
    harness: Harness,
    config_content: dict[str, typing.Any],
):
    """
    arrange: set mock container with file.
    act: update trusted_key_servers config and call enable_trusted_key_servers.
    assert: new configuration file is pushed and trusted_key_servers is enabled.
    """
    config = config_content

    harness.update_config({"trusted_key_servers": trusted_key_servers})
    harness.begin()
    synapse.enable_trusted_key_servers(config, harness.charm.build_charm_state())

    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "trusted_key_servers": expected_trusted_key_servers,
    }
    assert yaml.safe_dump(config) == yaml.safe_dump(expected_config_content)


@pytest.mark.parametrize(
    "ip_range_whitelist,expected_ip_range_whitelist",
    [
        pytest.param("", [], id="empty_list", marks=pytest.mark.xfail(strict=True)),
        pytest.param("10.10.10.10", ["10.10.10.10"], id="single_item"),
        pytest.param(",".join(["10.10.10.10"] * 100), ["10.10.10.10"] * 100, id="multiple_items"),
        pytest.param(
            " 10.10.10.10",
            [],
            id="single_item_leading_whitespace",
            marks=pytest.mark.xfail(strict=True),
        ),
        pytest.param(
            " 10.10.10.10,11.11.11.11",
            [],
            id="multiple_items_leading_whitespace",
            marks=pytest.mark.xfail(strict=True),
        ),
        pytest.param(
            "10.10.10.10 ",
            [],
            id="single_item_trailing_whitespace",
            marks=pytest.mark.xfail(strict=True),
        ),
        pytest.param(
            "10.10.10.10 ,11.11.11.11",
            [],
            id="multiple_items_trailing_whitespace",
            marks=pytest.mark.xfail(strict=True),
        ),
        pytest.param("abc,def", [], id="letters", marks=pytest.mark.xfail(strict=True)),
        pytest.param(",,,", [], id="only_commas", marks=pytest.mark.xfail(strict=True)),
    ],
)
def test_enable_ip_range_whitelist_success(
    ip_range_whitelist: str,
    expected_ip_range_whitelist: list[str],
    harness: Harness,
    config_content: dict[str, typing.Any],
):
    """
    arrange: set mock container with file.
    act: update ip_range_whitelist config and call enable_ip_range_whitelist.
    assert: new configuration file is pushed and ip_range_whitelist is enabled.
    """
    config = config_content

    harness.update_config({"ip_range_whitelist": ip_range_whitelist})
    harness.begin()
    synapse.enable_ip_range_whitelist(config, harness.charm.build_charm_state())

    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "ip_range_whitelist": expected_ip_range_whitelist,
    }
    assert yaml.safe_dump(config) == yaml.safe_dump(expected_config_content)


def test_enable_ip_range_whitelist_blocked(harness: Harness):
    """
    arrange: update the ip_range_whitelist with invalid value.
    act: start the charm.
    assert: charm is blocked due invalid configuration.
    """
    expected_first_domain = "foo1"
    expected_second_domain = "foo2"
    harness.update_config(
        {"ip_range_whitelist": f"{expected_first_domain},{expected_second_domain}"}
    )

    harness.begin_with_initial_hooks()

    assert isinstance(harness.model.unit.status, ops.BlockedStatus)


def test_enable_ip_range_whitelist_no_action(
    harness: Harness, config_content: dict[str, typing.Any]
):
    """
    arrange: set mock container with file.
    act: leave ip_range_whitelist config empty and call enable_ip_range_whitelist.
    assert: configuration file is not changed.
    """
    content = config_content

    harness.update_config({"server_name": "foo", "ip_range_whitelist": None})  # type: ignore
    harness.begin()
    synapse.enable_ip_range_whitelist(
        content,
        harness.charm.build_charm_state(),
    )

    assert yaml.safe_dump(content) == yaml.safe_dump(config_content)


def test_enable_federation_domain_whitelist_success(
    harness: Harness, config_content: dict[str, typing.Any]
):
    """
    arrange: set mock container with file.
    act: update federation_domain_whitelist config and call enable_federation_domain_whitelist.
    assert: new configuration file is pushed and federation_domain_whitelist is enabled.
    """
    content = config_content

    expected_first_domain = "foo1"
    expected_second_domain = "foo2"
    harness.update_config(
        {"federation_domain_whitelist": f"{expected_first_domain},{expected_second_domain}"}
    )
    harness.begin()
    synapse.enable_federation_domain_whitelist(content, harness.charm.build_charm_state())

    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "federation_domain_whitelist": [expected_first_domain, expected_second_domain],
    }
    assert yaml.safe_dump(content) == yaml.safe_dump(expected_config_content)


def test_enable_trusted_key_servers_no_action(config_content: dict[str, typing.Any]):
    """
    arrange: set mock container with file.
    act: call enable_trusted_key_servers without changing the configuration.
    assert: configuration is not changed.
    """
    content = config_content

    config = {
        "server_name": "foo",
        "public_baseurl": "https://foo",
    }
    synapse_config = SynapseConfig(**config)  # type: ignore[arg-type]

    synapse.enable_trusted_key_servers(
        content,
        CharmState(  # pylint: disable=duplicate-code
            datasource=None,
            smtp_config=None,
            media_config=None,
            redis_config=None,
            synapse_config=synapse_config,
            instance_map_config=None,
            registration_secrets=None,
        ),
    )

    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
    }
    assert yaml.safe_dump(content) == yaml.safe_dump(expected_config_content)


def test_disable_room_list_search_success(config_content: dict[str, typing.Any]):
    """
    arrange: set mock container with file.
    act: change the configuration file.
    assert: new configuration file is pushed and room_list_search is disabled.
    """
    config = config_content

    synapse.disable_room_list_search(config)

    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "enable_room_list_search": False,
    }
    assert yaml.safe_dump(config) == yaml.safe_dump(expected_config_content)


def test_validate_config_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: mock the validation command to fail.
    act: validate the configuration file.
    assert: WorkloadError is raised.
    """
    monkeypatch.setattr(
        synapse.workload, "_exec", MagicMock(return_value=synapse.ExecResult(1, "Fail", "Error"))
    )
    container_mock = MagicMock(spec=ops.Container)

    with pytest.raises(synapse.WorkloadError, match="Validate config failed"):
        synapse.validate_config(container_mock)


def test_enable_metrics_success(config_content: dict[str, typing.Any]):
    """
    arrange: set mock container with file.
    act: change the configuration file.
    assert: new configuration file is pushed and metrics are enabled.
    """
    content = config_content

    synapse.enable_metrics(content)

    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
            {"port": 9000, "type": "metrics", "bind_addresses": ["::"]},
        ],
        "enable_metrics": True,
    }
    assert yaml.safe_dump(content) == yaml.safe_dump(expected_config_content)


def test_enable_forgotten_room_success(config_content: dict[str, typing.Any]):
    """
    arrange: set mock container with file.
    act: change the configuration file.
    assert: new configuration file is pushed and forgotten_room_retention_period is enabled.
    """
    content = config_content

    synapse.enable_forgotten_room_retention(content)

    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "forgotten_room_retention_period": "28d",
    }
    assert yaml.safe_dump(content) == yaml.safe_dump(expected_config_content)


def test_get_mjolnir_config_success():
    """
    arrange: set access token and room id parameters.
    act: call _get_mjolnir_config.
    assert: config returns as expected.
    """
    access_token = token_hex(16)
    room_id = token_hex(16)

    config = synapse.workload._get_mjolnir_config(access_token=access_token, room_id=room_id)

    assert config["accessToken"] == access_token
    assert config["managementRoom"] == room_id


def test_generate_mjolnir_config_success(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set container, access token and room id parameters.
    act: call generate_mjolnir_config.
    assert: file is pushed as expected.
    """
    access_token = token_hex(16)
    room_id = token_hex(16)
    push_mock = MagicMock()
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "push", push_mock)

    synapse.generate_mjolnir_config(
        container=container_mock, access_token=access_token, room_id=room_id
    )

    expected_config = synapse.workload._get_mjolnir_config(
        access_token=access_token, room_id=room_id
    )
    push_mock.assert_called_once_with(
        synapse.MJOLNIR_CONFIG_PATH, yaml.safe_dump(expected_config), make_dirs=True
    )


SMTP_CONFIGURATION = SMTPConfiguration(
    enable_tls=True,
    force_tls=False,
    require_transport_security=True,
    host="smtp.example.com",
    port=25,
    user="username",
    password=token_hex(16),
)


def test_enable_smtp_success(config_content: dict[str, typing.Any]):
    """
    arrange: set mock container with config file.
    act: update smtp_host config and call enable_smtp.
    assert: new configuration file is pushed and SMTP is enabled.
    """
    synapse_with_notif_config = {
        "notif_from": "noreply@example.com",
        "server_name": "example.com",
        "public_baseurl": "https://example.com",
    }
    synapse_config = SynapseConfig(**synapse_with_notif_config)  # type: ignore[arg-type]
    charm_state = CharmState(
        datasource=None,
        smtp_config=SMTP_CONFIGURATION,
        media_config=None,
        redis_config=None,
        instance_map_config=None,
        synapse_config=synapse_config,
        registration_secrets=None,
    )

    synapse.enable_smtp(config_content, charm_state)

    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "email": {
            "enable_notifs": False,
            "enable_tls": True,
            "force_tls": False,
            "require_transport_security": True,
            "notif_from": "noreply@example.com",
            "smtp_host": "smtp.example.com",
            "smtp_port": 25,
            "smtp_user": "username",
            "smtp_pass": SMTP_CONFIGURATION["password"],
        },
    }
    assert yaml.safe_dump(config_content) == yaml.safe_dump(expected_config_content)


def test_enable_serve_server_wellknown_success(config_content: dict[str, typing.Any]):
    """
    arrange: set mock container with file.
    act: call enable_serve_server_wellknown.
    assert: new configuration file is pushed and serve_server_wellknown is enabled.
    """
    content = config_content

    synapse.enable_serve_server_wellknown(content)

    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "serve_server_wellknown": True,
    }
    assert yaml.safe_dump(content) == yaml.safe_dump(expected_config_content)


def test_disable_password_config_success():
    """
    arrange: set mock container with file.
    act: call disable_password_config.
    assert: new configuration file is pushed and password_config is disabled.
    """
    config_content = """
    password_config:
        enabled: true
    """
    config = yaml.safe_load(config_content)

    synapse.disable_password_config(config)

    expected_config_content = {
        "password_config": {
            "enabled": False,
        },
    }
    assert yaml.safe_dump(config) == yaml.safe_dump(expected_config_content)


def test_get_registration_shared_secret_success(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: call get_registration_shared_secret.
    assert: registration_shared_secret is returned.
    """
    expected_secret = token_hex(16)
    config_content = f"registration_shared_secret: {expected_secret}"
    text_io_mock = io.StringIO(config_content)
    pull_mock = Mock(return_value=text_io_mock)
    push_mock = MagicMock()
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "pull", pull_mock)
    monkeypatch.setattr(container_mock, "push", push_mock)

    received_secret = synapse.get_registration_shared_secret(container_mock)

    assert pull_mock.call_args[0][0] == synapse.SYNAPSE_CONFIG_PATH
    assert received_secret == expected_secret


def test_get_registration_shared_secret_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set mock container with file.
    act: call get_registration_shared_secret.
    assert: raise WorkloadError.
    """
    error_message = "Error pulling file"
    path_error = ops.pebble.PathError(kind="fake", message=error_message)
    pull_mock = MagicMock(side_effect=path_error)
    container_mock = MagicMock()
    monkeypatch.setattr(container_mock, "pull", pull_mock)

    with pytest.raises(ops.pebble.PathError, match=error_message):
        synapse.get_registration_shared_secret(container_mock)


HTTP_PROXY_TEST_PARAMS = [
    pytest.param({}, {}, id="no_env"),
    pytest.param({"JUJU_CHARM_NO_PROXY": "127.0.0.1"}, {"no_proxy": "127.0.0.1"}, id="no_proxy"),
    pytest.param(
        {"JUJU_CHARM_HTTP_PROXY": "http://proxy.test"},
        {"http_proxy": "http://proxy.test"},
        id="http_proxy",
    ),
    pytest.param(
        {"JUJU_CHARM_HTTPS_PROXY": "http://proxy.test"},
        {"https_proxy": "http://proxy.test"},
        id="https_proxy",
    ),
    pytest.param(
        {
            "JUJU_CHARM_HTTP_PROXY": "http://proxy.test",
            "JUJU_CHARM_HTTPS_PROXY": "http://proxy.test",
        },
        {"http_proxy": "http://proxy.test", "https_proxy": "http://proxy.test"},
        id="http_https_proxy",
    ),
]


@pytest.mark.parametrize(
    "set_env, expected",
    HTTP_PROXY_TEST_PARAMS,
)
def test_http_proxy(
    set_env: typing.Dict[str, str],
    expected: typing.Dict[str, str],
    monkeypatch,
    harness: Harness,
):
    """
    arrange: set juju charm http proxy related environment variables.
    act: generate a Synapse environment.
    assert: environment generated should contain proper proxy environment variables.
    """
    for set_env_name, set_env_value in set_env.items():
        monkeypatch.setenv(set_env_name, set_env_value)

    harness.begin()
    env = synapse.get_environment(harness.charm.build_charm_state())

    expected_env: typing.Dict[str, typing.Optional[str]] = {
        "http_proxy": None,
        "https_proxy": None,
        "no_proxy": None,
    }
    expected_env.update(expected)
    for env_name, env_value in expected_env.items():
        assert env.get(env_name) == env.get(env_name.upper()) == env_value


def test_block_non_admin_invites(config_content: dict[str, typing.Any]):
    """
    arrange: set mock container with file.
    act: update block_non_admin_invites config to true.
    assert: new configuration file is pushed and block_non_admin_invites is enabled.
    """
    block_non_admin_invites = {
        "block_non_admin_invites": True,
        "server_name": "example.com",
        "public_baseurl": "https://example.com",
    }
    synapse_config = SynapseConfig(**block_non_admin_invites)  # type: ignore[arg-type]
    charm_state = CharmState(
        datasource=None,
        smtp_config=SMTP_CONFIGURATION,
        redis_config=None,
        synapse_config=synapse_config,
        media_config=None,
        instance_map_config=None,
        registration_secrets=None,
    )

    synapse.block_non_admin_invites(config_content, charm_state)

    expected_config_content = {
        "block_non_admin_invites": True,
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
    }

    assert yaml.safe_dump(config_content) == yaml.safe_dump(expected_config_content)


def test_publish_rooms_allowlist_success(config_content: dict[str, typing.Any]):
    """
    arrange: mock Synapse current configuration with config_content and
        add publish_rooms_allowlist to the charm configuration.
    act: call enable_room_list_publication_rules.
    assert: new configuration file is pushed and room_list_publication_rules is set.
    """
    synapse_with_notif_config = {
        "publish_rooms_allowlist": "user1:domainX.com,user2:domainY.com",
        "server_name": "example.com",
        "public_baseurl": "https://example.com",
    }
    synapse_config = SynapseConfig(**synapse_with_notif_config)  # type: ignore[arg-type]
    charm_state = CharmState(
        datasource=None,
        smtp_config=SMTP_CONFIGURATION,
        redis_config=None,
        synapse_config=synapse_config,
        media_config=None,
        instance_map_config=None,
        registration_secrets=None,
    )

    synapse.enable_room_list_publication_rules(config_content, charm_state)

    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "room_list_publication_rules": [
            {"action": "allow", "alias": "*", "room_id": "*", "user_id": "@user1:domainX.com"},
            {"action": "allow", "alias": "*", "room_id": "*", "user_id": "@user2:domainY.com"},
            {"action": "deny", "alias": "*", "room_id": "*", "user_id": "*"},
        ],
    }
    assert yaml.safe_dump(config_content) == yaml.safe_dump(expected_config_content)


@pytest.mark.parametrize(
    "invalid_config",
    [
        "userinvaliddomainX.com",
        "user*:domainX.com",
        "user1:domainX.com,user$:domainX.com",
        "user1:domainX.com,user#:domainX.com,user2:domainX.com",
        "user1:domainX.com;user2:domainX.com",
        ":domainX.com;@user2:domainX.com",
    ],
)
def test_publish_rooms_allowlist_error(invalid_config):
    """
    arrange: set configuration with invalid value for publish_rooms_allowlist.
    act: set SynapseConfig.
    assert: ValidationError is raised.
    """
    synapse_with_notif_config = {
        "publish_rooms_allowlist": invalid_config,
        "server_name": "example.com",
        "public_baseurl": "https://example.com",
    }
    with pytest.raises(ValidationError):
        # Prevent mypy error:
        # Argument 1 to "SynapseConfig" has incompatible type "**dict[str, str]"; expected "bool"
        SynapseConfig(**synapse_with_notif_config)  # type: ignore[arg-type]


def test_enable_rc_joins_remote_rate(
    harness: Harness,
    config_content: dict[str, typing.Any],
):
    """
    arrange: set mock container with file.
    act: update rc_joins_remote_rate config and call rc_joins_remote_rate.
    assert: new configuration file is pushed and rc_joins_remote_rate is enabled.
    """
    config = config_content

    harness.update_config({"rc_joins_remote_burst_count": 10, "rc_joins_remote_per_second": 0.2})
    harness.begin()
    synapse.enable_rc_joins_remote_rate(config, harness.charm.build_charm_state())

    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "rc_joins": {"remote": {"burst_count": 10, "per_second": 0.2}},
    }
    assert yaml.safe_dump(config) == yaml.safe_dump(expected_config_content)


def test_enable_limit_remote_rooms_complexity(
    harness: Harness,
    config_content: dict[str, typing.Any],
):
    """
    arrange: set mock container with file.
    act: update limit_remote_rooms_complexity config and call limit_remote_rooms_complexity.
    assert: new configuration file is pushed and limit_remote_rooms_complexity is enabled.
    """
    config = config_content

    harness.update_config({"limit_remote_rooms_complexity": 0.2})
    harness.begin()
    synapse.enable_limit_remote_rooms_complexity(config, harness.charm.build_charm_state())

    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "limit_remote_rooms": {"enabled": True, "complexity": 0.2},
    }
    assert yaml.safe_dump(config) == yaml.safe_dump(expected_config_content)


def test_invite_checker_policy_rooms(config_content: dict[str, typing.Any]):
    """
    arrange: set mock container with file.
    act: update invite_checker_policy_rooms config.
    assert: new configuration file is pushed and invite_checker_policy_rooms is enabled.
    """
    invite_checker_policy_rooms = {
        "invite_checker_policy_rooms": "foo:foo.com,foo1:foo1.com,foo2:foo2.foo1.com",
        "server_name": "example.com",
        "public_baseurl": "https://example.com",
    }
    synapse_config = SynapseConfig(**invite_checker_policy_rooms)  # type: ignore[arg-type]
    charm_state = CharmState(
        datasource=None,
        smtp_config=SMTP_CONFIGURATION,
        redis_config=None,
        synapse_config=synapse_config,
        media_config=None,
        instance_map_config=None,
        registration_secrets=None,
    )

    synapse.enable_synapse_invite_checker(config_content, charm_state)

    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "modules": [
            {
                "config": {
                    "policy_room_ids": ["!foo:foo.com", "!foo1:foo1.com", "!foo2:foo2.foo1.com"]
                },
                "module": "synapse_invite_checker.InviteChecker",
            }
        ],
    }

    assert yaml.safe_dump(config_content) == yaml.safe_dump(expected_config_content)


def test_invite_checker_blocklist_allowlist_url(config_content: dict[str, typing.Any]):
    """
    arrange: set mock container with file.
    act: update invite_checker_blocklist_allowlist_url config.
    assert: new configuration file is pushed and invite_checker_blocklist_allowlist_url is enabled.
    """
    invite_checker_blocklist_allowlist_url = {
        "invite_checker_blocklist_allowlist_url": "https://example.com/file",
        "server_name": "example.com",
        "public_baseurl": "https://example.com",
    }
    # pylint: disable=line-too-long
    synapse_config = SynapseConfig(**invite_checker_blocklist_allowlist_url)  # type: ignore[arg-type] # noqa: E501
    charm_state = CharmState(
        datasource=None,
        smtp_config=SMTP_CONFIGURATION,
        redis_config=None,
        synapse_config=synapse_config,
        media_config=None,
        instance_map_config=None,
        registration_secrets=None,
    )

    synapse.enable_synapse_invite_checker(config_content, charm_state)

    expected_config_content = {
        "listeners": [
            {"type": "http", "port": 8080, "bind_addresses": ["::"]},
        ],
        "modules": [
            {
                "config": {"blocklist_allowlist_url": "https://example.com/file"},
                "module": "synapse_invite_checker.InviteChecker",
            }
        ],
    }

    assert yaml.safe_dump(config_content) == yaml.safe_dump(expected_config_content)
