# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses

import ops

from charm_types import DatasourcePostgreSQL

MAS_DATABASE_INTEGRATION_NAME = "mas-database"
MAS_DATABASE_NAME = "mas"


class MASDatasourceMissingError(Exception):
    """Exception raised when the MAS datasource is not configured."""


@dataclasses.dataclass(frozen=True)
class MASConfiguration:
    """Information needed to configure MAS.

    Attributes:
        datasource: datasource information.
        database_uri: The database URI used in MAS config.
    """

    datasource: DatasourcePostgreSQL

    @property
    def database_uri(self) -> str:
        """Build the database uri from datasource.

        Returns:
            str: The database uri
        """
        user = self.datasource["user"]
        password = self.datasource["password"]
        host = self.datasource["host"]
        port = self.datasource["port"]
        return f"postgresql://{user}:{password}@{host}:{port}/{MAS_DATABASE_NAME}"

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
        datasource = charm._mas_database.get_relation_as_datasource()  # type: ignore
        return cls(datasource=datasource)

    @classmethod
    def validate(cls, charm: ops.CharmBase) -> None:
        """State component containing MAS configuration information.

        Args:
            charm: The synapse charm

        Raises:
            MASDatasourceMissingError: when mas-database integration is missing.
        """
        if not charm.model.relations.get(MAS_DATABASE_INTEGRATION_NAME):
            raise MASDatasourceMissingError("Waiting for mas-database integration.")
