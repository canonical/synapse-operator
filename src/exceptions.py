#!/usr/bin/env python3

# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Exceptions used by the Synapse charm."""


class CommandMigrateConfigError(Exception):
    """Exception raised when a charm configuration is found to be invalid.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the CommandMigrateConfigError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg


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


class ServerNameModifiedError(Exception):
    """Exception raised while checking configuration file.

    Raised if server_name from state is different than the one in the configuration file.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the ServerNameModifiedError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg
