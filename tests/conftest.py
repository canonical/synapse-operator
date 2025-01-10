# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for Synapse charm tests."""

from pytest import Parser

SYNAPSE_IMAGE_PARAM = "--synapse-image"


def pytest_addoption(parser: Parser) -> None:
    """Parse additional pytest options.

    Args:
        parser: Pytest parser.
    """
    parser.addoption(SYNAPSE_IMAGE_PARAM, action="store", help="Synapse image to be deployed")
    parser.addoption("--charm-file", action="store", help="Charm file to be deployed")
    parser.addoption(
        "--use-existing",
        action="store_true",
        default=False,
        help="This parameter will skip deploy of Synapse and PostgreSQL",
    )
    parser.addoption("--localstack-address", action="store")
