#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Type definitions for the Synapse charm."""

import typing


class ExecResult(typing.NamedTuple):
    """A named tuple representing the result of executing a command.

    Attributes:
        exit_code: The exit status of the command (0 for success, non-zero for failure).
        stdout: The standard output of the command as a string.
        stderr: The standard error output of the command as a string.
    """

    exit_code: int
    stdout: str
    stderr: str


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
