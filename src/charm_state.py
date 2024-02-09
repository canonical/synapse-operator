# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""State of the Charm."""
import dataclasses
import itertools
import os
import typing

import ops

# pydantic is causing this no-name-in-module problem
from pydantic import (  # pylint: disable=no-name-in-module,import-error
    AnyHttpUrl,
    BaseModel,
    Extra,
    Field,
    ValidationError,
    parse_obj_as,
    validator,
)

from charm_types import DatasourcePostgreSQL, SAMLConfiguration, SMTPConfiguration


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
        admin_access_token: admin_access_token to configure Mjolnir.
        allow_public_rooms_over_federation: allow_public_rooms_over_federation config.
        enable_mjolnir: enable_mjolnir config.
        enable_password_config: enable_password_config config.
        enable_room_list_search: enable_room_list_search config.
        federation_domain_whitelist: federation_domain_whitelist config.
        ip_range_whitelist: ip_range_whitelist config.
        notif_from: defines the "From" address to use when sending emails.
        public_baseurl: public_baseurl config.
        report_stats: report_stats config.
        server_name: server_name config.
        trusted_key_servers: trusted_key_servers config.
    """

    admin_access_token: str | None = Field(None)
    allow_public_rooms_over_federation: bool = False
    enable_mjolnir: bool = False
    enable_password_config: bool = True
    enable_room_list_search: bool = True
    federation_domain_whitelist: str | None = Field(None)
    ip_range_whitelist: str | None = Field(None, regex=r"^[\.:,/\d]+\d+(?:,[:,\d]+)*$")
    public_baseurl: str | None = Field(None)
    report_stats: str | None = Field(None)
    server_name: str = Field(..., min_length=2)
    notif_from: str | None = Field(None)
    trusted_key_servers: str | None = Field(
        None, regex=r"^[A-Za-z0-9][A-Za-z0-9-.]*(?:,[A-Za-z0-9][A-Za-z0-9-.]*)*\.\D{2,4}$"
    )

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


@dataclasses.dataclass(frozen=True)
class CharmState:
    """State of the Charm.

    Attributes:
        synapse_config: synapse configuration.
        datasource: datasource information.
        saml_config: saml configuration.
        smtp_config: smtp configuration.
        proxy: proxy information.
    """

    synapse_config: SynapseConfig
    datasource: typing.Optional[DatasourcePostgreSQL]
    saml_config: typing.Optional[SAMLConfiguration]
    smtp_config: typing.Optional[SMTPConfiguration]

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

    @classmethod
    def from_charm(
        cls,
        charm: ops.CharmBase,
        datasource: typing.Optional[DatasourcePostgreSQL],
        saml_config: typing.Optional[SAMLConfiguration],
        smtp_config: typing.Optional[SMTPConfiguration],
    ) -> "CharmState":
        """Initialize a new instance of the CharmState class from the associated charm.

        Args:
            charm: The charm instance associated with this state.
            datasource: datasource information to be used by Synapse.
            saml_config: saml configuration to be used by Synapse.
            smtp_config: SMTP configuration to be used by Synapse.

        Return:
            The CharmState instance created by the provided charm.

        Raises:
            CharmConfigInvalidError: if the charm configuration is invalid.
        """
        try:
            # ignoring because mypy fails with:
            # "has incompatible type "**dict[str, str]"; expected ...""
            valid_synapse_config = SynapseConfig(**dict(charm.config.items()))  # type: ignore
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
        )
