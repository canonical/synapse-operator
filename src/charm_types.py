#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Type definitions for the Synapse charm."""

import typing


class DatasourcePostgreSQL(typing.TypedDict):
    """A named tuple representing a Datasource PostgreSQL.

    Attributes:
        user: User.
        password: Password.
        host: Host (IP or DNS without port or protocol).
        port: Port.
        db: Database name.
    """

    user: str
    password: str
    host: str
    port: str
    db: str


class SAMLConfiguration(typing.TypedDict):
    """A named tuple representing a SAML configuration.

    Attributes:
        entity_id: SAML entity ID.
        metadata_url: URL to the metadata.
    """

    entity_id: str
    metadata_url: str
