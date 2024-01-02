#!/usr/bin/env python3

# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Exceptions used by the Synapse charm."""


class CharmDatabaseRelationNotFoundError(Exception):
    """Exception raised when there is no database relation.

    Attrs:
        msg (str): Explanation of the error.
    """

    def __init__(self, msg: str):
        """Initialize a new instance of the CharmDatabaseRelationNotFoundError exception.

        Args:
            msg (str): Explanation of the error.
        """
        self.msg = msg
