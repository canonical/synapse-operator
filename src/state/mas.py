# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""State of the Charm."""

import dataclasses

from charm_types import DatasourcePostgreSQL


@dataclasses.dataclass(frozen=True)
class MASConfiguration:
    """Information needed to configure MAS.

    Attributes:
        datasource: datasource information.
    """

    datasource: DatasourcePostgreSQL
