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
    root_validator,
    validator,
)

from exceptions import CharmConfigInvalidError

if typing.TYPE_CHECKING:
    from charm import SynapseCharm


KNOWN_CHARM_CONFIG = (
    "server_name",
    "report_stats",
)
SYNAPSE_CONTAINER_NAME = "synapse"
SYNAPSE_PORT = 8008


class SynapseConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Represent Synapse builtin configuration values.

    Attrs:
        server_name: server_name config.
        report_stats: report_stats config.
    """

    server_name: str | None = Field(None, min_length=0)
    report_stats: str | None = Field(None, min_length=2, regex="(?i)^(yes|no)$")

    class Config:  # pylint: disable=too-few-public-methods
        """Config class.

        Attrs:
            extra: extra configuration.
        """

        extra = Extra.allow

    @root_validator(skip_on_failure=True)
    # no-self-argument disabled due to cls usage as expected by validator
    def check_all_set(cls, values: dict) -> dict:  # pylint: disable=no-self-argument
        """Check all values from configuration.

        Args:
            values: values to be validated.

        Raises:
            ValueError: Raised if values are not valid.

        Returns:
            values if they are as expected.
        """
        if all(not field for field in list(values.values())):
            raise ValueError("Configuration is not valid, please review your charm configuration")
        return values

    @validator("server_name")
    # no-self-argument disabled due to cls usage as expected by validator
    def check_server_name_empty(cls, value: str) -> str:  # pylint: disable=no-self-argument
        """Check if server name is empty.

        Args:
            value: server_name value.

        Raises:
            ValueError: Raised if server_name is empty.

        Returns:
            server_name value.
        """
        if not value:
            raise ValueError("The server_name is empty, please review your charm configuration")
        return value


class CharmState:
    """State of the Charm.

    Attrs:
        server_name: server_name config.
        report_stats: report_stats config.
        synapse_container_name: synapse container name.
        synapse_port: synapse port.
    """

    def __init__(
        self,
        *,
        synapse_config: SynapseConfig,
    ) -> None:
        """Construct.

        Args:
            synapse_config: The value of the synapse_config charm configuration.
        """
        self._synapse_config = synapse_config

    @property
    def server_name(self) -> typing.Optional[str]:
        """Return server_name config.

        Returns:
            str: server_name config.
        """
        return self._synapse_config.server_name

    @property
    def report_stats(self) -> typing.Optional[str]:
        """Return report_stats config.

        Returns:
            str: report_stats config.
        """
        return self._synapse_config.report_stats

    @property
    def synapse_container_name(self) -> str:
        """Return synapse container name.

        Returns:
            str: synapse container name.
        """
        return SYNAPSE_CONTAINER_NAME

    @property
    def synapse_port(self) -> int:
        """Return synapse port.

        Returns:
            str: synapse port.
        """
        return SYNAPSE_PORT

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
        return cls(synapse_config=valid_synapse_config)
