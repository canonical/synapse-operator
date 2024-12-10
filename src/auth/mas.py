# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""Helper module used to manage MAS-related workloads."""

import logging

from jinja2 import Environment, FileSystemLoader, select_autoescape

from state.charm_state import SynapseConfig
from state.mas import MASConfiguration

MAS_TEMPLATE_FILE_NAME = "mas_config.yaml.j2"

logger = logging.getLogger()


# pylint: disable=too-few-public-methods


def generate_mas_config(
    mas_configuration: MASConfiguration,
    synapse_configuration: SynapseConfig,
    main_unit_address: str,
) -> str:
    """Render the MAS configuration file.

    Args:
        mas_configuration: Path of the template to load.
        synapse_configuration: Context needed to render the template.
        main_unit_address: Address of synapse main unit.

    Returns:
        str: The rendered MAS configuration.
    """
    mas_context = mas_configuration.mas_context

    context = {
        "mas_prefix": mas_configuration.mas_prefix,
        "encryption_key": mas_context.encryption_key,
        "signing_key_id": mas_context.signing_key_id,
        "signing_key_rsa": mas_context.signing_key_rsa,
        "synapse_oidc_client_id": mas_context.synapse_oidc_client_id,
        "synapse_oidc_client_secret": mas_context.synapse_oidc_client_secret,
        "synapse_shared_secret": mas_context.synapse_shared_secret,
        "synapse_public_baseurl": synapse_configuration.public_baseurl,
        "mas_database_uri": mas_configuration.database_uri,
        "enable_password_config": synapse_configuration.enable_password_config,
        "synapse_server_name_config": synapse_configuration.server_name,
        "synapse_main_unit_address": main_unit_address,
    }
    env = Environment(
        loader=FileSystemLoader("./templates"),
        autoescape=select_autoescape(),
        keep_trailing_newline=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(MAS_TEMPLATE_FILE_NAME)
    return template.render(context)
