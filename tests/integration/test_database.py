#!/usr/bin/env python3
# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Integration tests for Database."""
import typing

import pytest
from juju.model import Model
from ops.model import ActiveStatus
from pytest_operator.plugin import OpsTest

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore


@pytest.mark.usefixtures("synapse_app")
async def test_with_database(
    ops_test: OpsTest, model: Model, synapse_app_name: str, postgresql_app_name: str
):
    """
    arrange: build and deploy the Synapse charm, and deploy the postgresql-k8s.
    act: relate the postgresql-k8s charm with the Synapse charm.
    assert: Synapse is active.
    """
    async with ops_test.fast_forward():
        await model.deploy(postgresql_app_name, trust=True)
        await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
        await model.add_relation(synapse_app_name, postgresql_app_name)
        await model.wait_for_idle(status=ACTIVE_STATUS_NAME)
    assert model.applications[synapse_app_name].units[0].workload_status == ACTIVE_STATUS_NAME
