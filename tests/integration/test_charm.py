#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Synapse charm."""
import logging
import typing

import requests
from juju.application import Application

from charm_state import SYNAPSE_PORT

logger = logging.getLogger(__name__)


async def test_synapse_is_up(
    synapse_app: Application,
    get_unit_ips: typing.Callable[[str], typing.Awaitable[tuple[str, ...]]],
):
    """
    arrange: build and deploy the Synapse charm.
    act: send a request to the Synapse application managed by the Synapse charm.
    assert: the Synapse application should return a correct response.
    """
    for unit_ip in await get_unit_ips(synapse_app.name):
        response = requests.get(f"http://{unit_ip}:{SYNAPSE_PORT}/_matrix/static/", timeout=5)
        assert response.status_code == 200
        assert "Welcome to the Matrix" in response.text
