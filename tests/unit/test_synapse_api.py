# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse API unit tests."""

# pylint: disable=protected-access

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
    # Set user parameters
    username = "any-user"
    user = User(username=username, admin=True)
    # Prepare mock to register the user
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
    # Check if parameters are correct.
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
    arrange: set User parameters and mock post to return connection and http errors.
    act: register the user.
    assert: NetworkError is raised.
    """
    username = "any-user"
    user = User(username=username, admin=True)
    get_nonce_return = "nonce"
    get_nonce_mock = mock.MagicMock(return_value=get_nonce_return)
    monkeypatch.setattr("synapse.api._get_nonce", get_nonce_mock)
    generate_mac_mock = mock.MagicMock(return_value="mac")
    monkeypatch.setattr("synapse.api._generate_mac", generate_mac_mock)
    mock_response_error = requests.exceptions.ConnectionError("Connection error")
    mock_response = mock.Mock(side_effect=mock_response_error)
    monkeypatch.setattr("synapse.api.requests.post", mock_response)
    shared_secret = token_hex(16)
    with pytest.raises(synapse.APIError, match="Failed to connect to"):
        synapse.register_user(shared_secret, user)
    mock_response_http_error = requests.exceptions.HTTPError
    mock_response = mock.Mock(side_effect=mock_response_http_error)
    monkeypatch.setattr("synapse.api.requests.post", mock_response)
    with pytest.raises(synapse.APIError, match="HTTP error from"):
        synapse.register_user(shared_secret, user)


def test_register_user_nonce_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set User parameters and mock once to return error.
    act: register the user.
    assert: NetworkError is raised.
    """
    username = "any-user"
    user = User(username=username, admin=True)
    msg = "Wrong nonce"
    mock_nonce_error = synapse.api.GetNonceError(msg)
    get_nonce_mock = mock.MagicMock(side_effect=mock_nonce_error)
    monkeypatch.setattr("synapse.api._get_nonce", get_nonce_mock)
    shared_secret = token_hex(16)
    with pytest.raises(synapse.APIError, match=msg):
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


@mock.patch("synapse.api.requests.Session")
def test_get_nonce_success(mock_session):
    """
    arrange: mock request to get nonce returning value.
    act: get nonce.
    assert: _get_nonce return the correct value.
    """
    nonce_value = "nonce_value"
    mock_response = mock.MagicMock()
    mock_response.json.return_value = {
        "nonce": nonce_value,
    }
    mock_requests = mock.MagicMock()
    mock_requests.get.return_value = mock_response
    mock_session.return_value = mock_requests
    assert synapse.api._get_nonce() == nonce_value


@mock.patch("synapse.api.requests.Session")
def test_get_nonce_requests_error(mock_session):
    """
    arrange: mock request to get nonce returning connection and http errors.
    act: get nonce.
    assert: NetworkError is raised.
    """
    mock_response_error = requests.exceptions.ConnectionError("Connection error")
    mock_requests = mock.MagicMock()
    mock_requests.get.side_effect = mock_response_error
    mock_session.return_value = mock_requests
    with pytest.raises(synapse.APIError, match="Failed to connect to"):
        synapse.api._get_nonce()
    mock_response_http_error = requests.exceptions.HTTPError
    mock_requests = mock.MagicMock()
    mock_requests.get.side_effect = mock_response_http_error
    mock_session.return_value = mock_requests
    with pytest.raises(synapse.APIError, match="HTTP error from"):
        synapse.api._get_nonce()
    mock_response = mock.MagicMock()
    mock_response.json.return_value = None
    mock_requests = mock.MagicMock()
    mock_requests.get.return_value = mock_response
    mock_session.return_value = mock_requests
    with pytest.raises(synapse.APIError, match="object is not subscriptable"):
        synapse.api._get_nonce()


@mock.patch("synapse.api.requests.Session")
def test_get_version_success(mock_session):
    """
    arrange: mock request to get version returning value.
    act: get version.
    assert: get_version return the correct value.
    """
    extracted_version = "0.99.2rc1"
    mock_session_instance = mock_session.return_value
    mock_response = mock.Mock()
    mock_response.json.return_value = {
        "server_version": f"{extracted_version} (b=develop, abcdef123)"
    }
    mock_session_instance.get.return_value = mock_response
    assert synapse.api.get_version() == extracted_version


@mock.patch("synapse.api.requests.Session")
def test_get_version_requests_error(mock_session):
    """
    arrange: mock request to get version returning error.
    act: get version.
    assert: NetworkError is raised.
    """
    mock_response_error = requests.exceptions.ConnectionError("Connection error")
    mock_requests = mock.MagicMock()
    mock_requests.get.side_effect = mock_response_error
    mock_session.return_value = mock_requests
    with pytest.raises(synapse.APIError, match="Failed to connect to"):
        synapse.api.get_version()
    mock_response_http_error = requests.exceptions.HTTPError
    mock_requests = mock.MagicMock()
    mock_requests.get.side_effect = mock_response_http_error
    mock_session.return_value = mock_requests
    with pytest.raises(synapse.APIError, match="HTTP error from"):
        synapse.api.get_version()
    mock_response = mock.MagicMock()
    mock_response.json.return_value = None
    mock_requests = mock.MagicMock()
    mock_requests.get.return_value = mock_response
    mock_session.return_value = mock_requests
    with pytest.raises(synapse.APIError, match="object is not subscriptable"):
        synapse.api.get_version()


@mock.patch("synapse.api.requests.Session")
def test_get_version_regex_error(mock_session):
    """
    arrange: mock request to get version returning invalid content.
    act: get version.
    assert: get_version return the correct value.
    """
    mock_session_instance = mock_session.return_value
    mock_response = mock.Mock()
    mock_response.json.return_value = {"server_version": "foo"}
    mock_session_instance.get.return_value = mock_response
    with pytest.raises(synapse.APIError, match="server_version has unexpected content"):
        synapse.api.get_version()
