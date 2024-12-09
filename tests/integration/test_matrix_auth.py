#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Matrix-auth integration tests for Synapse charm."""
import json
import logging
import pathlib
import typing

from juju.application import Application
from juju.controller import Controller  # type: ignore
from juju.model import Model
from juju.unit import Unit
from ops.model import ActiveStatus
from pytest_operator.plugin import OpsTest

# caused by pytest fixtures, mark does not work in fixtures
# pylint: disable=too-many-arguments, unused-argument

# mypy has trouble to inferred types for variables that are initialized in subclasses.
ACTIVE_STATUS_NAME = typing.cast(str, ActiveStatus.name)  # type: ignore

logger = logging.getLogger(__name__)


async def test_synapse_cmr_matrix_auth(
    ops_test: OpsTest,
    model: Model,
    synapse_app: Application,
):
    """
    arrange: deploy the Synapse charm, create offer, deploy any-charm as consumer
        in a different model and consume offer.
    act: integrate them via matrix-auth offer.
    assert: Synapse set the registration file received via matrix-auth.
    """
    await model.wait_for_idle(idle_period=10, status=ACTIVE_STATUS_NAME)
    # This workaround was extracted from prometheus-k8s charm.
    # Without it, the offer creation fails.
    # https://github.com/canonical/prometheus-k8s-operator/blob/5779ecc749ee1582c6be20030a83472d024cd24f/tests/integration/test_remote_write_with_zinc.py#L103
    controller = Controller()
    await controller.connect()
    await controller.create_offer(
        model.uuid,
        f"{synapse_app.name}:matrix-auth",
    )
    offers = await controller.list_offers(model.name)
    await model.block_until(
        lambda: all(offer.application_name == synapse_app.name for offer in offers.results)
    )
    await model.wait_for_idle(idle_period=10, status=ACTIVE_STATUS_NAME)
    await ops_test.track_model(
        "consumer",
    )
    with ops_test.model_context("consumer") as consumer_model:
        any_charm_content = pathlib.Path("tests/integration/any_charm.py").read_text(
            encoding="utf-8"
        )
        matrix_auth_content = pathlib.Path("lib/charms/synapse/v1/matrix_auth.py").read_text(
            encoding="utf-8"
        )
        any_charm_src_overwrite = {
            "any_charm.py": any_charm_content,
            "matrix_auth.py": matrix_auth_content,
        }
        any_charm_app = await consumer_model.deploy(
            "any-charm",
            application_name="any-charm1",
            channel="beta",
            config={
                "python-packages": "pydantic\ncryptography",
                "src-overwrite": json.dumps(any_charm_src_overwrite),
            },
        )
        await consumer_model.wait_for_idle(apps=[any_charm_app.name])
        await consumer_model.consume(f"admin/{ops_test.model_name}.{synapse_app.name}", "synapse")

        await consumer_model.relate(any_charm_app.name, "synapse")
        await consumer_model.wait_for_idle(idle_period=30, status=ACTIVE_STATUS_NAME)

    unit: Unit = synapse_app.units[0]
    ret_code, _, stderr = await ops_test.juju(
        "exec",
        "--unit",
        unit.name,
        "grep appservice-irc /data/appservice-registration-matrix-auth-*.yaml",
    )
    assert not ret_code, f"Failed to check for application service file, {stderr}"
