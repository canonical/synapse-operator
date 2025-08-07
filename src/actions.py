#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Actions for Synapse charm."""

import logging

import ops

from auth.mas import (
    MASDeactivateUserFailedError,
    MASRegisterUserFailedError,
    MASVerifyUserEmailFailedError,
    deactivate_user,
    register_user,
    verify_user_email,
)

logger = logging.getLogger(__name__)


def register_user_action(container: ops.Container, event: ops.ActionEvent) -> None:
    """Register user and report action result.

    Args:
        container: workload container.
        event: Event triggering the register user instance action.
    """
    if not container.can_connect():
        event.fail("Failed to connect to the container")
        return
    try:
        password = register_user(
            container=container,
            username=event.params["username"],
            is_admin=event.params["admin"],
        )
    except MASRegisterUserFailedError as exc:
        event.fail(str(exc))
        return
    results = {"register-user": True, "user-password": password}
    event.set_results(results)


def verify_user_email_action(container: ops.Container, event: ops.ActionEvent) -> None:
    """Register user and report action result.

    Args:
        container: workload container.
        event: Event triggering the register user instance action.
    """
    if not container.can_connect():
        event.fail("Failed to connect to the container")
        return
    try:
        verify_user_email(
            container=container,
            username=event.params["username"],
            email=event.params["email"],
        )
    except MASVerifyUserEmailFailedError as exc:
        event.fail(str(exc))
        return
    results = {"verify-user-email": True}
    event.set_results(results)


def anonymize_user_action(container: ops.Container, event: ops.ActionEvent) -> None:
    """Anonymize user and report action result.

    Args:
        container: workload container.
        event: Event triggering the anonymize user action.
    """
    if not container.can_connect():
        event.fail("Failed to connect to the container")
        return

    try:
        deactivate_user(container=container, username=event.params["username"])
    except MASDeactivateUserFailedError as exc:
        logger.exception("Error deactivating user.")
        event.fail(str(exc))

    event.set_results(
        {
            "anonymize-user": True,
        }
    )
