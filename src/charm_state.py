#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""State of the Charm."""
import dataclasses
import itertools
import typing

import ops

# pydantic is causing this no-name-in-module problem
from pydantic import (  # pylint: disable=no-name-in-module,import-error
    BaseModel,
    Extra,
    Field,
    ValidationError,
    validator,
)

from charm_types import DatasourcePostgreSQL, SAMLConfiguration

KNOWN_CHARM_CONFIG = (
    "enable_mjolnir",
    "enable_password_config",
    "public_baseurl",
    "report_stats",
    "server_name",
    "smtp_enable_tls",
    "smtp_host",
    "smtp_notif_from",
    "smtp_pass",
    "smtp_port",
    "smtp_user",
)


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


class SynapseConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Represent Synapse builtin configuration values.

    Attrs:
        server_name: server_name config.
        report_stats: report_stats config.
        public_baseurl: public_baseurl config.
        enable_mjolnir: enable_mjolnir config.
        enable_password_config: enable_password_config config.
        smtp_enable_tls: enable tls while connecting to SMTP server.
        smtp_host: SMTP host.
        smtp_notif_from: defines the "From" address to use when sending emails.
        smtp_pass: password to authenticate to SMTP host.
        smtp_port: SMTP port.
        smtp_user: username to autehtncate to SMTP host.
    """

    server_name: str | None = Field(..., min_length=2)
    report_stats: str | None = Field(None)
    public_baseurl: str | None = Field(None)
    enable_mjolnir: bool = False
    enable_password_config: bool = True
    smtp_enable_tls: bool = True
    smtp_host: str | None = Field(None)
    smtp_notif_from: str | None = Field(None)
    smtp_pass: str | None = Field(None)
    smtp_port: int | None = Field(None)
    smtp_user: str | None = Field(None)

    class Config:  # pylint: disable=too-few-public-methods
        """Config class.

        Attrs:
            extra: extra configuration.
        """

        extra = Extra.allow

    @validator("smtp_notif_from", pre=True, always=True)
    @classmethod
    def set_default_smtp_notif_from(
        cls, smtp_notif_from: typing.Optional[str], values: dict
    ) -> typing.Optional[str]:
        """Set server_name as default value to smtp_notif_from.

        Args:
            smtp_notif_from: the smtp_notif_from current value.
            values: values already defined.

        Returns:
            The default value for smtp_notif_from if not defined.
        """
        server_name = values.get("server_name")
        if smtp_notif_from is None and server_name:
            return server_name
        return smtp_notif_from

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
    """

    synapse_config: SynapseConfig
    datasource: typing.Optional[DatasourcePostgreSQL]
    saml_config: typing.Optional[SAMLConfiguration]

    @classmethod
    def from_charm(
        cls,
        charm: ops.CharmBase,
        datasource: typing.Optional[DatasourcePostgreSQL],
        saml_config: typing.Optional[SAMLConfiguration],
    ) -> "CharmState":
        """Initialize a new instance of the CharmState class from the associated charm.

        Args:
            charm: The charm instance associated with this state.
            datasource: datasource information to be used by Synapse.
            saml_config: saml configuration to be used by Synapse.

        Return:
            The CharmState instance created by the provided charm.

        Raises:
            CharmConfigInvalidError: if the charm configuration is invalid.
        """
        synapse_config = {k: v for k, v in charm.config.items() if k in KNOWN_CHARM_CONFIG}
        try:
            valid_synapse_config = SynapseConfig(**synapse_config)  # type: ignore
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
        )
