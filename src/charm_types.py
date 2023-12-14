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


class SMTPConfiguration(typing.TypedDict):
    """A named tuple representing SMTP configuration.

    Attributes:
        host: The hostname of the outgoing SMTP server.
        port: The port on the mail server for outgoing SMTP.
        user: Optional username for authentication.
        password: Optional password for authentication.
        enable_tls: If enabled, if the server supports TLS, it will be used.
        force_tls: If this option is set to true, TLS is used from the start (Implicit TLS)
            and the option require_transport_security is ignored.
        require_transport_security: Set to true to require TLS transport security for SMTP.
    """

    host: str
    port: int
    user: typing.Optional[str]
    password: typing.Optional[str]
    enable_tls: bool
    force_tls: bool
    require_transport_security: bool
