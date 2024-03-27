# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Exceptions unit tests."""


from exceptions import CharmDatabaseRelationNotFoundError


def test_charm_database_relation_not_found_error():
    """
    arrange: set error message.
    act: create CharmDatabaseRelationNotFoundError instance.
    assert: error message is set correctly.
    """
    error_message = "Database relation not found"
    error = CharmDatabaseRelationNotFoundError(error_message)
    assert error.msg == error_message
