import secrets
from pathlib import Path

import yaml
from charms.synapse.v0.matrix_auth import (
    MatrixAuthProviderData,
    MatrixAuthProvides,
    MatrixAuthRequirerData,
)
from ops import CharmBase, RelationChangedEvent, RelationJoinedEvent

from .synapse.workload import (
    SYNAPSE_CONFIG_DIR,
    SYNAPSE_CONFIG_PATH,
    WorkloadError,
    _exec,
    _get_configuration_field,
)


class MatrixAuthProvider(CharmBase):
    def __init__(self, *args, relation_name: str = "matrix-auth"):
        super().__init__(*args)
        self.relation_name = relation_name
        self.matrix_auth = MatrixAuthProvides(self, relation_name=self.relation_name)

        self.framework.observe(
            self.on[self.relation_name].relation_joined, self._on_relation_joined
        )
        self.framework.observe(
            self.matrix_auth.on.matrix_auth_request_received, self._on_matrix_auth_request_received
        )

    def _on_relation_joined(self, event: RelationJoinedEvent):
        container = self.unit.get_container("synapse")

        server_name = _get_configuration_field(container, "server_name")
        if not server_name:
            event.defer()
            return

        homeserver = f"https://{server_name}"

        shared_secret = _get_configuration_field(container, "registration_shared_secret")
        if not shared_secret:
            shared_secret = secrets.token_urlsafe(32)
            self._update_homeserver_config({"registration_shared_secret": shared_secret})

        provider_data = MatrixAuthProviderData(homeserver=homeserver, shared_secret=shared_secret)

        self.matrix_auth.update_relation_data(event.relation, provider_data)

    def _on_matrix_auth_request_received(self, event: RelationChangedEvent):
        requirer_data = MatrixAuthRequirerData.from_relation(self.model, event.relation)

        if requirer_data and requirer_data.registration_secret_id:
            registration_secret = requirer_data.get_registration(
                self.model, requirer_data.registration_secret_id
            )

            if registration_secret:
                # Create a file with the content of the registration secret
                registration_file_path = (
                    Path(SYNAPSE_CONFIG_DIR) / f"appservice-registration-{self.relation_name}.yaml"
                )
                registration_file_path.write_text(registration_secret.get_secret_value())

                # Update the homeserver.yaml config file
                self._update_homeserver_config(
                    {"app_service_config_files": [str(registration_file_path)]}
                )

    def _update_homeserver_config(self, new_config: dict):
        container = self.unit.get_container("synapse")

        try:
            # Read existing config
            config = yaml.safe_load(_get_configuration_field(container, ""))
            if not config:
                config = {}

            # Update config
            for key, value in new_config.items():
                if key not in config:
                    config[key] = value
                elif key == "app_service_config_files":
                    if isinstance(config[key], list):
                        for item in value:
                            if item not in config[key]:
                                config[key].append(item)
                    else:
                        config[key] = value
                else:
                    config[key] = value

            # Write updated config
            container.push(SYNAPSE_CONFIG_PATH, yaml.dump(config), make_dirs=True)

            # Validate the config
            result = _exec(
                container, ["/usr/bin/python3", "-m", "synapse.config", "-c", SYNAPSE_CONFIG_PATH]
            )
            if result.exit_code != 0:
                raise WorkloadError(f"Failed to validate config: {result.stderr}")

        except Exception as e:
            raise WorkloadError(f"Failed to update homeserver config: {str(e)}")
