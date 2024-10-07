# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""State of the Charm."""
import dataclasses
import itertools
import logging
import os
import re
import typing
from abc import ABC, abstractmethod

import ops

# pydantic is causing this no-name-in-module problem
from pydantic.v1 import (  # pylint: disable=no-name-in-module,import-error
    AnyHttpUrl,
    BaseModel,
    Extra,
    Field,
    ValidationError,
    parse_obj_as,
    validator,
)

from charm_types import (
    DatasourcePostgreSQL,
    MediaConfiguration,
    RedisConfiguration,
    SAMLConfiguration,
    SMTPConfiguration,
)

logger = logging.getLogger(__name__)


class CharmBaseWithState(ops.CharmBase, ABC):
    """CharmBase than can build a CharmState."""

    @abstractmethod
    def build_charm_state(self) -> "CharmState":
        """Build charm state."""

    def get_charm(self) -> "CharmBaseWithState":
        """Return the current charm.

        Returns:
           The current charm
        """
        return self

    @abstractmethod
    def reconcile(self, charm_state: "CharmState") -> None:
        """Reconcile Synapse configuration.

        Args:
            charm_state: The charm state.
        """


class HasCharmWithState(typing.Protocol):  # pylint: disable=too-few-public-methods
    """Protocol that defines a class that returns a CharmBaseWithState."""

    def get_charm(self) -> CharmBaseWithState:
        """Get the charm that can build a state."""


C = typing.TypeVar("C", bound=HasCharmWithState)
E = typing.TypeVar("E", bound=ops.EventBase)


def inject_charm_state(  # pylint: disable=protected-access
    method: typing.Callable[[C, E, "CharmState"], None]
) -> typing.Callable[[C, E], None]:
    """Create a decorator that injects the argument charm_state to an observer hook.

    If the configuration is invalid, set the charm state to Blocked if it is
    a Hook or the event to failed if it is an Action and do not call the wrapped observer.

    This decorator can be used in a class that observes a hook/action
    and that defines de get_charm function to get a charm that implements
    CharmBaseWithState.

    Because of https://github.com/canonical/operator/issues/1129,
    @functools.wraps cannot be used yet to have a properly created
    decorator.

    Args:
        method: observer method to wrap and inject the charm_state

    Returns:
        the function wrapper
    """

    def wrapper(instance: C, event: E) -> None:
        """Add the charm_state argument to the function.

        If the configuration is invalid, set the charm state to Blocked if it is
        a Hook or the event to failed if it is an Action and do not call the wrapped observer.

        Args:
            instance: the instance of the class with the method to inject the charm state.
            event: the event for the observer

        Returns:
            The value returned from the original function. That is, None.
        """
        charm = instance.get_charm()

        try:
            charm_state = charm.build_charm_state()
        except CharmConfigInvalidError as exc:
            logger.exception("Error creating CharmConfig")
            # There are two main types of events, Hooks and Actions.
            # Each one of them should be treated differently.
            if isinstance(event, ops.charm.ActionEvent):
                event.fail(exc.msg)
            else:
                charm.model.unit.status = ops.BlockedStatus(exc.msg)
            return None
        return method(instance, event, charm_state)

    # This is necessary for ops to work
    setattr(wrapper, "__name__", method.__name__)
    return wrapper


class CharmConfigInvalidError(Exception):
    """Exception raised when a charm configuration is found to be invalid.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the CharmConfigInvalidError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


class ProxyConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Configuration for accessing Synapse through proxy.

    Attributes:
        http_proxy: The http proxy URL.
        https_proxy: The https proxy URL.
        no_proxy: Comma separated list of hostnames to bypass proxy.
    """

    http_proxy: typing.Optional[AnyHttpUrl]
    https_proxy: typing.Optional[AnyHttpUrl]
    no_proxy: typing.Optional[str]


class SynapseConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Represent Synapse builtin configuration values.

    Attributes:
        allow_public_rooms_over_federation: allow_public_rooms_over_federation config.
        block_non_admin_invites: block_non_admin_invites config.
        enable_email_notifs: enable_email_notifs config.
        enable_mjolnir: enable_mjolnir config.
        enable_password_config: enable_password_config config.
        enable_room_list_search: enable_room_list_search config.
        federation_domain_whitelist: federation_domain_whitelist config.
        invite_checker_blocklist_allowlist_url: invite_checker_blocklist_allowlist_url config.
        invite_checker_policy_rooms: invite_checker_policy_rooms config.
        ip_range_whitelist: ip_range_whitelist config.
        limit_remote_rooms_complexity: limit_remote_rooms_complexity config.
        notif_from: defines the "From" address to use when sending emails.
        public_baseurl: public_baseurl config.
        publish_rooms_allowlist: publish_rooms_allowlist config.
        experimental_alive_check: experimental_alive_check config.
        rc_joins_remote_burst_count: rc_join burst_count config.
        rc_joins_remote_per_second: rc_join per_second config.
        report_stats: report_stats config.
        server_name: server_name config.
        trusted_key_servers: trusted_key_servers config.
        workers_ignore_list: workers_ignore_list config.
    """

    allow_public_rooms_over_federation: bool = False
    block_non_admin_invites: bool = False
    enable_email_notifs: bool = False
    enable_mjolnir: bool = False
    enable_password_config: bool = True
    enable_room_list_search: bool = True
    experimental_alive_check: str | None = Field(None)
    federation_domain_whitelist: str | None = Field(None)
    invite_checker_blocklist_allowlist_url: str | None = Field(None)
    invite_checker_policy_rooms: str | None = Field(None)
    ip_range_whitelist: str | None = Field(None, regex=r"^[\.:,/\d]+\d+(?:,[:,\d]+)*$")
    limit_remote_rooms_complexity: float | None = Field(None)
    public_baseurl: str | None = Field(None)
    publish_rooms_allowlist: str | None = Field(None)
    rc_joins_remote_burst_count: int | None = Field(None)
    rc_joins_remote_per_second: float | None = Field(None)
    report_stats: str | None = Field(None)
    server_name: str = Field(..., min_length=2)
    # notif_from should be after server_name because of how the validator is set.
    notif_from: str | None = Field(None)
    trusted_key_servers: str | None = Field(
        None, regex=r"^[A-Za-z0-9][A-Za-z0-9-.]*(?:,[A-Za-z0-9][A-Za-z0-9-.]*)*\.\D{2,4}$"
    )
    workers_ignore_list: str | None = Field(None)

    class Config:  # pylint: disable=too-few-public-methods
        """Config class.

        Attrs:
            extra: extra configuration.
        """

        extra = Extra.allow

    @validator("notif_from", pre=True, always=True)
    @classmethod
    def get_default_notif_from(
        cls, notif_from: typing.Optional[str], values: dict
    ) -> typing.Optional[str]:
        """Set server_name as default value to notif_from.

        Args:
            notif_from: the notif_from current value.
            values: values already defined.

        Returns:
            The default value for notif_from if not defined.
        """
        server_name = values.get("server_name")
        if notif_from is None and server_name:
            return server_name
        return notif_from

    @validator("report_stats")
    @classmethod
    def to_yes_or_no(cls, value: str) -> str:
        """Convert the report_stats field to yes or no.

        Args:
            value: the input value.

        Returns:
            The string converted to yes or no.
        """
        if value == str(True):
            return "yes"
        return "no"

    @validator("invite_checker_policy_rooms")
    @classmethod
    def roomids_to_list(cls, value: str) -> typing.List[str]:
        """Convert a comma separated list of rooms to list.

        Args:
            value: the input value.

        Returns:
            The string converted to list.

        Raises:
            ValidationError: if rooms is not as expected.
        """
        # Based on documentation
        # https://spec.matrix.org/v1.10/appendices/#user-identifiers
        roomid_regex = r"![a-zA-Z0-9._=/+-]+:[a-zA-Z0-9-.]+"
        if value is None:
            return []
        value_list = ["!" + room_id.strip() for room_id in value.split(",")]
        for room_id in value_list:
            if not re.fullmatch(roomid_regex, room_id):
                raise ValidationError(f"Invalid room ID format: {room_id}", cls)
        return value_list

    @validator("publish_rooms_allowlist")
    @classmethod
    def userids_to_list(cls, value: str) -> typing.List[str]:
        """Convert a comma separated list of users to list.

        Args:
            value: the input value.

        Returns:
            The string converted to list.

        Raises:
            ValidationError: if user_id is not as expected.
        """
        # Based on documentation
        # https://spec.matrix.org/v1.10/appendices/#user-identifiers
        userid_regex = r"@[a-z0-9._=/+-]+:\w+\.\w+"
        if value is None:
            return []
        value_list = ["@" + user_id.strip() for user_id in value.split(",")]
        for user_id in value_list:
            if not re.fullmatch(userid_regex, user_id):
                raise ValidationError(f"Invalid user ID format: {user_id}", cls)
        return value_list

    @validator("experimental_alive_check")
    @classmethod
    def to_pebble_check(cls, value: str) -> typing.Dict[str, typing.Union[str, int]]:
        """Convert the experimental_alive_check field to pebble check.

        Args:
            value: the input value.

        Returns:
            The pebble check.

        Raises:
            ValidationError: if experimental_alive_check is invalid.
        """
        # expected
        # period,threshold,timeout
        config_values = value.split(",")
        if len(config_values) != 3:
            raise ValidationError(
                f"Invalid experimental_alive_check, less or more than 3 values: {value}", cls
            )
        try:
            period = config_values[0].strip().lower()
            if period[-1] not in ("s", "m", "h"):
                raise ValidationError(
                    f"Invalid experimental_alive_check, period should end in s/m/h: {value}", cls
                )
            threshold = int(config_values[1].strip())
            timeout = config_values[2].strip().lower()
            if timeout[-1] not in ("s", "m", "h"):
                raise ValidationError(
                    f"Invalid experimental_alive_check, timeout should end in s/m/h: {value}", cls
                )
            return {"period": period, "threshold": threshold, "timeout": timeout}
        except ValueError as exc:
            raise ValidationError(
                f"Invalid experimental_alive_check, threshold should be a number: {value}", cls
            ) from exc


@dataclasses.dataclass(frozen=True)
class CharmState:  # pylint: disable=too-many-instance-attributes
    """State of the Charm.

    Attributes:
        synapse_config: synapse configuration.
        datasource: datasource information.
        saml_config: saml configuration.
        smtp_config: smtp configuration.
        media_config: media configuration.
        redis_config: redis configuration.
        proxy: proxy information.
        instance_map_config: Instance map configuration with main and worker addresses.
    """

    synapse_config: SynapseConfig
    datasource: typing.Optional[DatasourcePostgreSQL]
    saml_config: typing.Optional[SAMLConfiguration]
    smtp_config: typing.Optional[SMTPConfiguration]
    media_config: typing.Optional[MediaConfiguration]
    redis_config: typing.Optional[RedisConfiguration]
    instance_map_config: typing.Optional[typing.Dict]

    @property
    def proxy(self) -> "ProxyConfig":
        """Get charm proxy information from juju charm environment.

        Returns:
            charm proxy information in the form of ProxyConfig.
        """
        http_proxy = os.environ.get("JUJU_CHARM_HTTP_PROXY")
        https_proxy = os.environ.get("JUJU_CHARM_HTTPS_PROXY")
        no_proxy = os.environ.get("JUJU_CHARM_NO_PROXY")
        return ProxyConfig(
            http_proxy=parse_obj_as(AnyHttpUrl, http_proxy) if http_proxy else None,
            https_proxy=parse_obj_as(AnyHttpUrl, https_proxy) if https_proxy else None,
            no_proxy=no_proxy,
        )

    # from_charm receives configuration from all integration so too many arguments.
    @classmethod
    def from_charm(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        cls,
        charm: ops.CharmBase,
        datasource: typing.Optional[DatasourcePostgreSQL],
        saml_config: typing.Optional[SAMLConfiguration],
        smtp_config: typing.Optional[SMTPConfiguration],
        media_config: typing.Optional[MediaConfiguration],
        redis_config: typing.Optional[RedisConfiguration],
        instance_map_config: typing.Optional[typing.Dict],
    ) -> "CharmState":
        """Initialize a new instance of the CharmState class from the associated charm.

        Args:
            charm: The charm instance associated with this state.
            datasource: datasource information to be used by Synapse.
            saml_config: saml configuration to be used by Synapse.
            smtp_config: SMTP configuration to be used by Synapse.
            media_config: Media configuration to be used by Synapse.
            redis_config: Redis configuration to be used by Synapse.
            instance_map_config: Instance map configuration with main and worker addresses.

        Return:
            The CharmState instance created by the provided charm.

        Raises:
            CharmConfigInvalidError: if the charm configuration is invalid.
        """
        try:
            # ignoring because mypy fails with:
            # "has incompatible type "**dict[str, str]"; expected ...""
            valid_synapse_config = SynapseConfig(**dict(charm.config.items()))  # type: ignore
            # remove workers from instance_map
            if instance_map_config and valid_synapse_config.workers_ignore_list:
                logger.debug(
                    "Removing %s from instance_map", valid_synapse_config.workers_ignore_list
                )
                workers_to_ignore = [
                    # due to pydantic bump, need to refactor
                    # pylint: disable=no-member
                    w.strip()
                    for w in valid_synapse_config.workers_ignore_list.split(",")
                ]
                for worker in workers_to_ignore:
                    if worker in instance_map_config:
                        del instance_map_config[worker]
                    else:
                        logger.warning(
                            "Worker %s in workers_ignore_list not found in instance_map", worker
                        )
        except ValidationError as exc:
            error_fields = set(
                itertools.chain.from_iterable(error["loc"] for error in exc.errors())
            )
            error_field_str = " ".join(f"{f}" for f in error_fields)
            raise CharmConfigInvalidError(f"invalid configuration: {error_field_str}") from exc
        return cls(
            synapse_config=valid_synapse_config,
            datasource=datasource,
            saml_config=saml_config,
            smtp_config=smtp_config,
            media_config=media_config,
            redis_config=redis_config,
            instance_map_config=instance_map_config,
        )
