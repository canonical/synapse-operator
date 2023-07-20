# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse API unit tests."""

# pylint: disable=protected-access

import typing
from secrets import token_hex
from unittest import mock

import pytest
import requests

import synapse
from user import User


def test_register_user_success(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set User parameters.
    act: register the user.
    assert: parameters are passed correctly.
    """
    username = "any-user"
    user_data: dict[str, typing.Any] = {
        "username": username,
        "admin": "yes",
    }
    user = User(**user_data)
    get_nonce_return = "nonce"
    get_nonce_mock = mock.MagicMock(return_value=get_nonce_return)
    monkeypatch.setattr("synapse.api._get_nonce", get_nonce_mock)
    generate_mac_mock = mock.MagicMock(return_value="mac")
    monkeypatch.setattr("synapse.api._generate_mac", generate_mac_mock)
    mock_response = mock.Mock()
    mock_response.raise_for_status.return_value = None
    monkeypatch.setattr("synapse.api.requests.post", mock_response)
    shared_secret = token_hex(16)
    synapse.register_user(shared_secret, user)
    get_nonce_mock.assert_called_once()
    generate_mac_mock.assert_called_once_with(
        shared_secret=shared_secret,
        nonce=get_nonce_return,
        user=username,
        password=mock.ANY,
        admin=True,
    )


def test_register_user_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set User parameters.
    act: register the user.
    assert: NetworkError is raised.
    """
    username = "any-user"
    user_data: dict[str, typing.Any] = {
        "username": username,
        "admin": "yes",
    }
    user = User(**user_data)
    get_nonce_return = "nonce"
    get_nonce_mock = mock.MagicMock(return_value=get_nonce_return)
    monkeypatch.setattr("synapse.api._get_nonce", get_nonce_mock)
    generate_mac_mock = mock.MagicMock(return_value="mac")
    monkeypatch.setattr("synapse.api._generate_mac", generate_mac_mock)
    mock_response_error = requests.exceptions.ConnectionError("Connection error")
    mock_response = mock.Mock(side_effect=mock_response_error)
    monkeypatch.setattr("synapse.api.requests.post", mock_response)
    shared_secret = token_hex(16)
    with pytest.raises(synapse.NetworkError, match="Failed to request"):
        synapse.register_user(shared_secret, user)


def test_generate_mac():
    """
    arrange: set User parameters.
    act: generate mac.
    assert: Mac is generated accordingly to parameters.
    """
    mac = synapse.api._generate_mac(
        shared_secret="shared_secret",
        nonce="nonce",
        user="username",
        # changing this to a random value would affect the result to assert
        password="password",  # nosec
        admin=False,
    )
    assert mac == "56a99737dfe3739ed3e49a962f9cb178c81d6d12"


@mock.patch("synapse.api.requests")
def test_get_nonce_success(mock_requests):
    """
    arrange: set User parameters.
    act: register the user.
    assert: parameters are passed correctly.
    """
    nonce_value = "nonce_value"
    mock_response = mock.MagicMock()
    mock_response.json.return_value = {
        "nonce": nonce_value,
    }
    mock_requests.get.return_value = mock_response
    assert synapse.api._get_nonce() == nonce_value


def test_get_nonce_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set User parameters.
    act: register the user.
    assert: NetworkError is raised.
    """
    mock_response_error = requests.exceptions.ConnectionError("Connection error")
    mock_response = mock.Mock(side_effect=mock_response_error)
    monkeypatch.setattr("synapse.api.requests.get", mock_response)
    with pytest.raises(synapse.NetworkError, match="Failed to request"):
        synapse.api._get_nonce()
