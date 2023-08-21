# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for Synapse charm tests."""

from pytest import Parser


def pytest_addoption(parser: Parser) -> None:
    """Parse additional pytest options.

    Args:
        parser: Pytest parser.
    """
    parser.addoption("--synapse-image", action="store", help="Synapse image to be deployed")
    parser.addoption(
        "--synapse-nginx-image", action="store", help="Synapse NGINX image to be deployed"
    )
    parser.addoption("--charm-file", action="store", help="Charm file to be deployed")
