# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Fixtures for Synapse charm tests."""

import os

from pytest import Parser

SYNAPSE_IMAGE_PARAM = "--synapse-image"


def pytest_addoption(parser: Parser) -> None:
    """Parse additional pytest options.

    Args:
        parser: Pytest parser.
    """
    parser.addoption(
        SYNAPSE_IMAGE_PARAM,
        action="store",
        default=os.getenv("ROCK_IMAGE"),
        help="Synapse image to be deployed",
    )
    parser.addoption(
        "--charm-file",
        action="store",
        default=os.getenv("CHARM_FILE"),
        help="Charm file to be deployed",
    )
    parser.addoption(
        "--use-existing",
        action="store_true",
        default=False,
        help="This parameter will skip deploy of Synapse and PostgreSQL",
    )
    parser.addoption(
        "--s3-address",
        action="store",
        default=os.getenv("S3_ADDRESS"),
        help="Address of the S3-compatible service (MicroCeph radosgw) to be used in tests",
    )
