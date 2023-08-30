# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for Synapse charm tests."""

from pytest import Parser

SYNAPSE_IMAGE_PARAM = "--synapse-image"
SYNAPSE_NGINX_IMAGE_PARAM = "--synapse-nginx-image"


def pytest_addoption(parser: Parser) -> None:
    """Parse additional pytest options.

    Args:
        parser: Pytest parser.
    """
    parser.addoption(SYNAPSE_IMAGE_PARAM, action="store", help="Synapse image to be deployed")
    parser.addoption(
        SYNAPSE_NGINX_IMAGE_PARAM, action="store", help="Synapse NGINX image to be deployed"
    )
    parser.addoption("--charm-file", action="store", help="Charm file to be deployed")
