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

from exceptions import CharmConfigInvalidError

if typing.TYPE_CHECKING:
    from charm import SynapseCharm


KNOWN_CHARM_CONFIG = (
    "server_name",
    "report_stats",
)


class SynapseConfig(BaseModel):  # pylint: disable=too-few-public-methods
    """Represent Synapse builtin configuration values.

    Attrs:
        server_name: server_name config.
        report_stats: report_stats config.
    """

    server_name: str | None = Field(..., min_length=2)
    report_stats: str | None = Field(None)

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
        database_data: database data from database relation.
    """

    def __init__(
        self, *, synapse_config: SynapseConfig, database_data: typing.Optional[typing.Dict]
    ) -> None:
        """Construct.

        Args:
            synapse_config: The value of the synapse_config charm configuration.
            database_data: Database observer relation data.
        """
        self._synapse_config = synapse_config
        self._database_data: typing.Optional[typing.Dict] = database_data

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
    def database_data(self) -> typing.Optional[typing.Dict]:
        """Return database data from database relation.

        Returns:
            Dict: Information needed for setting connection with database.
        """
        return self._database_data

    @classmethod
    def from_charm(
        cls, charm: "SynapseCharm", database_data: typing.Optional[typing.Dict]
    ) -> "CharmState":
        """Initialize a new instance of the CharmState class from the associated charm.

        Args:
            charm: The charm instance associated with this state.
            database_data: database data from database relation.

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
        return cls(synapse_config=valid_synapse_config, database_data=database_data)
