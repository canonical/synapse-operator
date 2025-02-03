# Copyright 2025 Canonical Ltd.
# Licensed under the Apache2.0. See LICENSE file in charm source for details.

"""Library to manage the plugin integrations with the Synapse charm.

This library contains the Requires and Provides classes for handling the integration
between an application and a charm providing the `matrix_plugin` integration.

### Requirer Charm

```python

from charms.synapse.v0.matrix_auth import MatrixAuthRequires

class MatrixAuthRequirerCharm(ops.CharmBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.plugin_auth = MatrixAuthRequires(self)
        self.framework.observe(self.matrix_auth.on.matrix_auth_request_processed, self._handler)
        ...

    def _handler(self, events: MatrixAuthRequestProcessed) -> None:
        ...

```

As shown above, the library provides a custom event to handle the scenario in
which a matrix authentication (homeserver and shared secret) has been added or updated.

The MatrixAuthRequires provides an `update_relation_data` method to update the relation data by
passing a `MatrixAuthRequirerData` data object, requesting a new authentication.

### Provider Charm

Following the previous example, this is an example of the provider charm.

```python
from charms.synapse.v0.matrix_auth import MatrixAuthProvides

class MatrixAuthProviderCharm(ops.CharmBase):
    def __init__(self, *args):
        super().__init__(*args)
        self.plugin_auth = MatrixAuthProvides(self)
        ...

```
The MatrixAuthProvides object wraps the list of relations into a `relations` property
and provides an `update_relation_data` method to update the relation data by passing
a `MatrixAuthRelationData` data object.

```python
class MatrixAuthProviderCharm(ops.CharmBase):
    ...

    def _on_config_changed(self, _) -> None:
        for relation in self.model.relations[self.plugin_auth.relation_name]:
            self.plugin_auth.update_relation_data(relation, self._get_matrix_auth_data())

```
"""

# The unique Charmhub library identifier, never change it
LIBID = "ff6788c89b204448b3b62ba6f93e2768"

# Increment this major API version when introducing breaking changes
LIBAPI = 1

# Increment this PATCH version before using `charmcraft publish-lib` or reset
# to 0 if you are raising the major API version
LIBPATCH = 5

# pylint: disable=wrong-import-position
import json
import logging
from typing import Dict, List, Optional, Tuple, cast
import secrets
import base64
from cryptography.fernet import Fernet

import ops
from pydantic import BaseModel, Field, SecretStr

logger = logging.getLogger(__name__)

APP_REGISTRATION_LABEL = "app-registration"
APP_REGISTRATION_CONTENT_LABEL = "app-registration-content"
DEFAULT_RELATION_NAME = "matrix-auth"
SHARED_SECRET_LABEL = "shared-secret"
SHARED_SECRET_CONTENT_LABEL = "shared-secret-content"
ENCRYPTION_KEY_SECRET_LABEL = "encryption-key-secret"
ENCRYPTION_KEY_SECRET_CONTENT_LABEL = "encryption-key-content"

def encrypt_string(key: bytes, plaintext: SecretStr) -> str:
        """Encrypt a string using Fernet.

        Args:
            key: encryption key in bytes.
            plaintext: text to encrypt.

        Returns:
            encrypted text.
        """
        plaintext = cast(SecretStr, plaintext)
        encryptor = Fernet(key)
        ciphertext = encryptor.encrypt(plaintext.get_secret_value().encode('utf-8'))
        return ciphertext.decode()

def decrypt_string(key: bytes, ciphertext: str) -> str:
    """Decrypt a string using Fernet.

    Args:
        key: encryption key in bytes.
        ciphertext: encrypted text.

    Returns:
        decrypted text.
    """
    decryptor = Fernet(key)
    plaintext = decryptor.decrypt(ciphertext.encode('utf-8'))
    return plaintext.decode()

#### Data models for Provider and Requirer ####
class MatrixAuthProviderData(BaseModel):
    """Represent the MatrixAuth provider data.

    Attributes:
        homeserver: the homeserver URL.
        shared_secret: the Matrix shared secret.
        shared_secret_id: the shared secret Juju secret ID.
    """

    homeserver: str
    shared_secret: Optional[SecretStr] = Field(default=None, exclude=True)
    shared_secret_id: Optional[SecretStr] = Field(default=None)
    encryption_key_secret_id: Optional[SecretStr] = Field(default=None)

    def set_shared_secret_id(self, model: ops.Model, relation: ops.Relation) -> None:
        """Store the Matrix shared secret as a Juju secret.

        Args:
            model: the Juju model
            relation: relation to grant access to the secrets to.
        """
        # password is always defined since pydantic guarantees it
        password = cast(SecretStr, self.shared_secret)
        # pylint doesn't like get_secret_value
        secret_value = password.get_secret_value()  # pylint: disable=no-member
        try:
            secret = model.get_secret(label=SHARED_SECRET_LABEL)
            secret.set_content({SHARED_SECRET_CONTENT_LABEL: secret_value})
            # secret.id is not None at this point
            self.shared_secret_id = cast(str, secret.id)
        except ops.SecretNotFoundError:
            secret = relation.app.add_secret(
                {SHARED_SECRET_CONTENT_LABEL: secret_value}, label=SHARED_SECRET_LABEL
            )
            secret.grant(relation)
            self.shared_secret_id = cast(str, secret.id)

    def set_encryption_key_secret_id(self, model: ops.Model, relation: ops.Relation) -> None:
        """Store the encryption key to encrypt/decrypt appservice registrations.

        Args:
            model: the Juju model
            relation: relation to grant access to the secrets to.
        """
        key = Fernet.generate_key()
        encryption_key = key.decode('utf-8')
        try:
            secret = model.get_secret(label=ENCRYPTION_KEY_SECRET_LABEL)
            secret.set_content({ENCRYPTION_KEY_SECRET_CONTENT_LABEL: encryption_key})
            # secret.id is not None at this point
            self.encryption_key_secret_id = cast(str, secret.id)
        except ops.SecretNotFoundError:
            secret = relation.app.add_secret(
                {ENCRYPTION_KEY_SECRET_CONTENT_LABEL: encryption_key}, label=ENCRYPTION_KEY_SECRET_LABEL
            )
            secret.grant(relation)
            self.encryption_key_secret_id = cast(str, secret.id)

    @classmethod
    def get_shared_secret(
        cls, model: ops.Model, shared_secret_id: Optional[str]
    ) -> Optional[SecretStr]:
        """Retrieve the shared secret corresponding to the shared_secret_id.

        Args:
            model: the Juju model.
            shared_secret_id: the secret ID for the shared secret.

        Returns:
            the shared secret or None if not found.
        """
        if not shared_secret_id:
            return None
        try:
            secret = model.get_secret(id=shared_secret_id)
            password = secret.get_content(refresh=True).get(SHARED_SECRET_CONTENT_LABEL)
            if not password:
                return None
            return SecretStr(password)
        except ops.SecretNotFoundError:
            return None

    def to_relation_data(self, model: ops.Model, relation: ops.Relation) -> Dict[str, str]:
        """Convert an instance of MatrixAuthProviderData to the relation representation.

        Args:
            model: the Juju model.
            relation: relation to grant access to the secrets to.

        Returns:
            Dict containing the representation.
        """
        self.set_shared_secret_id(model, relation)
        self.set_encryption_key_secret_id(model, relation)
        return self.model_dump(exclude_unset=True)

    @classmethod
    def from_relation(cls, model: ops.Model, relation: ops.Relation) -> "MatrixAuthProviderData":
        """Initialize a new instance of the MatrixAuthProviderData class from the relation.

        Args:
            relation: the relation.

        Returns:
            A MatrixAuthProviderData instance.

        Raises:
            ValueError: if the value is not parseable.
        """
        app = cast(ops.Application, relation.app)
        relation_data = relation.data[app]
        shared_secret_id = (
            (relation_data["shared_secret_id"])
            if "shared_secret_id" in relation_data
            else None
        )
        shared_secret = MatrixAuthProviderData.get_shared_secret(model, shared_secret_id)
        homeserver = relation_data.get("homeserver")
        if shared_secret is None or homeserver is None:
            raise ValueError("Invalid relation data")
        return MatrixAuthProviderData(
            homeserver=homeserver,
            shared_secret=shared_secret,
        )


class MatrixAuthRequirerData(BaseModel):
    """Represent the MatrixAuth requirer data.

    Attributes:
        registration: a generated app registration file.
    """

    registration: Optional[SecretStr] = Field(default=None, exclude=True)

    @classmethod
    def get_encryption_key_secret(
        cls, model: ops.Model, encryption_key_secret_id: Optional[str]
    ) -> Optional[bytes]:
        """Retrieve the encryption key secret corresponding to the encryption_key_secret_id.

        Args:
            model: the Juju model.
            encryption_key_secret_id: the secret ID for the encryption key secret.

        Returns:
            the encryption key secret  as bytes or None if not found.
        """
        try:
            if not encryption_key_secret_id:
                # then its the provider and we can get using label
                secret = model.get_secret(label=ENCRYPTION_KEY_SECRET_LABEL)
            else:
                secret = model.get_secret(id=encryption_key_secret_id)
            encryption_key = secret.get_content(refresh=True).get(ENCRYPTION_KEY_SECRET_CONTENT_LABEL)
            if not encryption_key:
                return None
            return encryption_key.encode('utf-8')
        except ops.SecretNotFoundError:
            return None

    def to_relation_data(self, model: ops.Model, relation: ops.Relation) -> Dict[str, str]:
        """Convert an instance of MatrixAuthRequirerData to the relation representation.

        Args:
            model: the Juju model.
            relation: relation to grant access to the secrets to.

        Returns:
            Dict containing the representation.

        Raises:
            ValueError if encryption key not found.
        """
        # get encryption key
        app = cast(ops.Application, relation.app)
        relation_data = relation.data[app]
        encryption_key_secret_id = relation_data.get("encryption_key_secret_id")
        encryption_key = MatrixAuthRequirerData.get_encryption_key_secret(model, encryption_key_secret_id)
        if not encryption_key:
            raise ValueError("Invalid relation data: encryption_key_secret_id not found")
        # encrypt content
        content = encrypt_string(key=encryption_key, plaintext=self.registration)
        dumped_data = {
            "registration_secret": content,
        }
        return dumped_data

    @classmethod
    def from_relation(cls, model: ops.Model, relation: ops.Relation) -> "MatrixAuthRequirerData":
        """Get a MatrixAuthRequirerData from the relation data.

        Args:
            model: the Juju model.
            relation: the relation.

        Returns:
            the relation data and the processed entries for it.

        Raises:
            ValueError: if the value is not parseable.
        """
        # get encryption key
        app = cast(ops.Application, relation.app)
        relation_data = relation.data[app]
        encryption_key_secret_id = relation_data.get("encryption_key_secret_id")
        encryption_key = MatrixAuthRequirerData.get_encryption_key_secret(model, encryption_key_secret_id)
        if not encryption_key:
            logger.warning("Invalid relation data: encryption_key_secret_id not found")
            return None
        # decrypt content
        registration_secret = relation_data.get("registration_secret")
        if not registration_secret:
            return MatrixAuthRequirerData()
        return MatrixAuthRequirerData(
            registration=decrypt_string(key=encryption_key, ciphertext=registration_secret),
        )


#### Events ####
class MatrixAuthRequestProcessed(ops.RelationEvent):
    """MatrixAuth event emitted when a new request is processed."""

    def get_matrix_auth_provider_relation_data(self) -> MatrixAuthProviderData:
        """Get a MatrixAuthProviderData for the relation data.

        Returns:
            the MatrixAuthProviderData for the relation data.
        """
        return MatrixAuthProviderData.from_relation(self.framework.model, self.relation)


class MatrixAuthRequestReceived(ops.RelationEvent):
    """MatrixAuth event emitted when a new request is made."""


class MatrixAuthRequiresEvents(ops.CharmEvents):
    """MatrixAuth requirer events.

    This class defines the events that a MatrixAuth requirer can emit.

    Attributes:
        matrix_auth_request_processed: the MatrixAuthRequestProcessed.
    """

    matrix_auth_request_processed = ops.EventSource(MatrixAuthRequestProcessed)


class MatrixAuthProvidesEvents(ops.CharmEvents):
    """MatrixAuth provider events.

    This class defines the events that a MatrixAuth provider can emit.

    Attributes:
        matrix_auth_request_received: the MatrixAuthRequestReceived.
    """

    matrix_auth_request_received = ops.EventSource(MatrixAuthRequestReceived)


#### Provides and Requires ####
class MatrixAuthProvides(ops.Object):
    """Provider side of the MatrixAuth relation.

    Attributes:
        on: events the provider can emit.
    """

    on = MatrixAuthProvidesEvents()

    def __init__(self, charm: ops.CharmBase, relation_name: str = DEFAULT_RELATION_NAME) -> None:
        """Construct.

        Args:
            charm: the provider charm.
            relation_name: the relation name.
        """
        super().__init__(charm, relation_name)
        self.relation_name = relation_name
        self.framework.observe(charm.on[relation_name].relation_changed, self._on_relation_changed)

    def get_remote_relation_data(self) -> Optional[MatrixAuthRequirerData]:
        """Retrieve the remote relation data.

        Returns:
            MatrixAuthRequirerData: the relation data.
        """
        relation = self.model.get_relation(self.relation_name)
        return MatrixAuthRequirerData.from_relation(self.model, relation=relation) if relation else None

    def _is_remote_relation_data_valid(self, relation: ops.Relation) -> bool:
        """Validate the relation data.

        Args:
            relation: the relation to validate.

        Returns:
            true: if the relation data is valid.
        """
        try:
            _ = MatrixAuthRequirerData.from_relation(self.model, relation=relation)
            return True
        except ValueError as ex:
            logger.warning("Error validating the relation data %s", ex)
            return False

    def _on_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Event emitted when the relation has changed.

        Args:
            event: event triggering this handler.
        """
        assert event.relation.app
        relation_data = event.relation.data[event.relation.app]
        if relation_data and self._is_remote_relation_data_valid(event.relation):
            self.on.matrix_auth_request_received.emit(
                event.relation, app=event.app, unit=event.unit
            )

    def update_relation_data(
        self, relation: ops.Relation, matrix_auth_provider_data: MatrixAuthProviderData
    ) -> None:
        """Update the relation data. Since provider values should not be changed
            while instance exists, this method updates relation data only if
            invalid or empty.

        Args:
            relation: the relation for which to update the data.
            matrix_auth_provider_data: a MatrixAuthProviderData instance wrapping the data to be
                updated.
        """
        try:
            MatrixAuthProviderData.from_relation(self.model, relation=relation)
            logger.warning("Matrix Provider relation data is already set, skipping")
        except ValueError:
            logger.warning("Matrix Provider relation data is invalid or empty, updating")
            relation_data = matrix_auth_provider_data.to_relation_data(self.model, relation)
            relation.data[self.model.app].update(relation_data)


class MatrixAuthRequires(ops.Object):
    """Requirer side of the MatrixAuth requires relation.

    Attributes:
        on: events the provider can emit.
    """

    on = MatrixAuthRequiresEvents()

    def __init__(self, charm: ops.CharmBase, relation_name: str = DEFAULT_RELATION_NAME) -> None:
        """Construct.

        Args:
            charm: the provider charm.
            relation_name: the relation name.
        """
        super().__init__(charm, relation_name)
        self.relation_name = relation_name
        self.framework.observe(charm.on[relation_name].relation_changed, self._on_relation_changed)

    def get_remote_relation_data(self) -> Optional[MatrixAuthProviderData]:
        """Retrieve the remote relation data.

        Returns:
            MatrixAuthProviderData: the relation data.
        """
        relation = self.model.get_relation(self.relation_name)
        return MatrixAuthProviderData.from_relation(self.model, relation=relation) if relation else None

    def _is_remote_relation_data_valid(self, relation: ops.Relation) -> bool:
        """Validate the relation data.

        Args:
            relation: the relation to validate.

        Returns:
            true: if the relation data is valid.
        """
        try:
            _ = MatrixAuthProviderData.from_relation(self.model, relation=relation)
            return True
        except ValueError as ex:
            logger.warning("Error validating the relation data %s", ex)
            return False

    def _on_relation_changed(self, event: ops.RelationChangedEvent) -> None:
        """Event emitted when the relation has changed.

        Args:
            event: event triggering this handler.
        """
        assert event.relation.app
        relation_data = event.relation.data[event.relation.app]
        if relation_data and self._is_remote_relation_data_valid(event.relation):
            self.on.matrix_auth_request_processed.emit(
                event.relation, app=event.app, unit=event.unit
            )

    def update_relation_data(
        self,
        relation: ops.Relation,
        matrix_auth_requirer_data: MatrixAuthRequirerData,
    ) -> None:
        """Update the relation data.

        Args:
            relation: the relation for which to update the data.
            matrix_auth_requirer_data: MatrixAuthRequirerData wrapping the data to be updated.
        """
        relation_data = matrix_auth_requirer_data.to_relation_data(self.model, relation)
        relation.data[self.model.app].update(relation_data)
