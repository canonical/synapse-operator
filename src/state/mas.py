# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses
import typing

import ops

from charm_types import DatasourcePostgreSQL
from database_observer import DatabaseObserver
MAS_DATABASE_INTEGRATION_NAME = "mas-database"


class MASDatasourceMissingError(Exception):
    """Exception raised when the MAS datasource is not configured."""


@dataclasses.dataclass(frozen=True)
class MASConfiguration:
    """Information needed to configure MAS.

    Attributes:
        datasource: datasource information.
    """

    datasource: DatasourcePostgreSQL

    # from_charm receives configuration from all integration so too many arguments.
    @classmethod
    def from_charm(cls, charm: ops.CharmBase) -> "MASConfiguration":
        """State component containing MAS configuration information.

        Args:
            charm: The synapse charm

        Returns:
            MASConfiguration: The MAS configuration state component.
        """
        cls.validate(charm)
        # pylint: disable=protected-access
        database_observer = typing.cast(DatabaseObserver, charm._mas_database)  # type: ignore
        datasource = database_observer.get_relation_as_datasource()
        return cls(datasource=datasource)

    @classmethod
    def validate(cls, charm: ops.CharmBase) -> "MASConfiguration":
        """State component containing MAS configuration information.

        Args:
            charm: The synapse charm

        Raises:
            MASDatasourceMissingError: when mas-database integration is missing.
        """
        if not charm.model.relations.get(MAS_DATABASE_INTEGRATION_NAME):
            raise MASDatasourceMissingError("Waiting for mas-database integration.")
