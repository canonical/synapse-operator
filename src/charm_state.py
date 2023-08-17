#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""State of the Charm."""
import itertools
import typing

# pydantic is causing this no-name-in-module problem
from pydantic import (  # pylint: disable=no-name-in-module,import-error
    BaseModel,
    Extra,
    Field,
    ValidationError,
    validator,
)

from charm_types import DatasourcePostgreSQL, SAMLConfiguration

if typing.TYPE_CHECKING:
    from charm import SynapseCharm


KNOWN_CHARM_CONFIG = (
    "server_name",
    "report_stats",
    "public_baseurl",
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
    """

    server_name: str | None = Field(..., min_length=2)
    report_stats: str | None = Field(None)
    public_baseurl: str | None = Field(None)

    class Config:  # pylint: disable=too-few-public-methods
        """Config class.

        Attrs:
            extra: extra configuration.
        """

        extra = Extra.allow

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


class CharmState:
    """State of the Charm.

    Attrs:
        server_name: server_name config.
        report_stats: report_stats config.
        public_baseurl: public_baseurl config.
        datasource: datasource information.
        saml_config: saml configuration.
    """

    def __init__(
        self,
        *,
        synapse_config: SynapseConfig,
        datasource: typing.Optional[DatasourcePostgreSQL],
        saml_config: typing.Optional[SAMLConfiguration],
    ) -> None:
        """Construct.

        Args:
            synapse_config: The value of the synapse_config charm configuration.
            datasource: Datasource information.
            saml_config: SAML configuration.
        """
        self._synapse_config = synapse_config
        self._datasource = datasource
        self._saml_config = saml_config

    @property
    def server_name(self) -> typing.Optional[str]:
        """Return server_name config.

        Returns:
            str: server_name config.
        """
        return self._synapse_config.server_name

    @property
    def report_stats(self) -> typing.Union[str, bool, None]:
        """Return report_stats config.

        Returns:
            str: report_stats config as yes or no.
        """
        return self._synapse_config.report_stats

    @property
    def public_baseurl(self) -> typing.Optional[str]:
        """Return public_baseurl config.

        Returns:
            str: public_baseurl config.
        """
        return self._synapse_config.public_baseurl

    @property
    def datasource(self) -> typing.Union[DatasourcePostgreSQL, None]:
        """Return datasource.

        Returns:
            datasource or None.
        """
        return self._datasource

    @property
    def saml_config(self) -> typing.Union[SAMLConfiguration, None]:
        """Return SAML configuration.

        Returns:
            SAMLConfiguration or None.
        """
        return self._saml_config

    @classmethod
    def from_charm(cls, charm: "SynapseCharm") -> "CharmState":
        """Initialize a new instance of the CharmState class from the associated charm.

        Args:
            charm: The charm instance associated with this state.

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
            datasource=charm.database.get_relation_as_datasource(),
            saml_config=charm.saml.get_relation_as_saml_conf(),
        )
