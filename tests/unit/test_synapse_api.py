# Copyright 2023 Canonical Ltd.
# See LICENSE file for licensing details.

"""Synapse API unit tests."""

# pylint: disable=protected-access

from secrets import token_hex
from unittest import mock

import pytest
import requests

import synapse
from charm_state import CharmState, SynapseConfig
from user import User


@mock.patch("synapse.api.requests.Session")
def test_register_user_success(mock_session, monkeypatch: pytest.MonkeyPatch):
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
    mock_response = mock.MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_requests = mock.MagicMock()
    mock_requests.post.return_value = mock_response
    mock_session.return_value = mock_requests
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


@mock.patch("synapse.api.requests.Session")
def test_register_user_error(mock_session, monkeypatch: pytest.MonkeyPatch):
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
    mock_request = mock.Mock()
    mock_request.request.side_effect = mock_response_error
    mock_session.return_value = mock_request
    shared_secret = token_hex(16)
    with pytest.raises(synapse.APIError, match="Failed to connect to"):
        synapse.register_user(shared_secret, user)

    mock_response_exception = mock.MagicMock()
    mock_response_exception.text = "Fail"
    mock_response_http_error = requests.exceptions.HTTPError(response=mock_response_exception)
    mock_request = mock.Mock()
    mock_request.request.side_effect = mock_response_http_error
    mock_session.return_value = mock_request

    with pytest.raises(synapse.APIError, match="HTTP error from"):
        synapse.register_user(shared_secret, user)


@mock.patch("synapse.api.requests.Session")
def test_register_user_keyerror(mock_session, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set User parameters and mock post to return empty content.
    act: register the user.
    assert: KeyError is raised.
    """
    username = "any-user"
    user = User(username=username, admin=True)
    get_nonce_return = "nonce"
    get_nonce_mock = mock.MagicMock(return_value=get_nonce_return)
    monkeypatch.setattr("synapse.api._get_nonce", get_nonce_mock)
    generate_mac_mock = mock.MagicMock(return_value="mac")
    monkeypatch.setattr("synapse.api._generate_mac", generate_mac_mock)
    mock_response = mock.MagicMock()
    mock_response.json.return_value = {}
    mock_requests = mock.MagicMock()
    mock_requests.request.return_value = mock_response
    mock_session.return_value = mock_requests
    shared_secret = token_hex(16)

    with pytest.raises(synapse.APIError, match="access_token"):
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


@mock.patch("synapse.api.requests.Session")
def test_register_user_exists_error(mock_session, monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set User parameters and mock post to return UserExistsError.
    act: register the user.
    assert: exception is raised because there is no server/admin access token.
    """
    username = "any-user"
    user = User(username=username, admin=True)
    get_nonce_return = "nonce"
    get_nonce_mock = mock.MagicMock(return_value=get_nonce_return)
    monkeypatch.setattr("synapse.api._get_nonce", get_nonce_mock)
    generate_mac_mock = mock.MagicMock(return_value="mac")
    monkeypatch.setattr("synapse.api._generate_mac", generate_mac_mock)
    shared_secret = token_hex(16)
    mock_response_exception = mock.MagicMock()
    mock_response_exception.text = "User ID already taken"
    mock_response_http_error = requests.exceptions.HTTPError(response=mock_response_exception)
    mock_request = mock.Mock()
    mock_request.request.side_effect = mock_response_http_error
    mock_session.return_value = mock_request

    with pytest.raises(synapse.APIError, match="exists but there is no"):
        synapse.register_user(shared_secret, user)


@mock.patch("synapse.api.requests.Session")
def test_access_token_success(mock_session):
    """
    arrange: set User, admin_token and server parameters.
    act: get access token.
    assert: token is returned as expected.
    """
    # Set user parameters
    username = "any-user"
    user = User(username=username, admin=True)
    # Prepare mock to get the access token
    mock_response = mock.MagicMock()
    expected_token = token_hex(16)
    mock_response = mock.MagicMock()
    mock_response.json.return_value = {"access_token": expected_token}
    mock_requests = mock.MagicMock()
    mock_requests.request.return_value = mock_response
    mock_session.return_value = mock_requests
    server = token_hex(16)
    admin_access_token = token_hex(16)

    result = synapse.get_access_token(user, server=server, admin_access_token=admin_access_token)

    assert result == expected_token


@mock.patch("synapse.api.requests.Session")
def test_access_token_error(mock_session):
    """
    arrange: set User, admin_token and server parameters.
    act: get access token.
    assert: API error is raised.
    """
    # Set user parameters
    username = "any-user"
    user = User(username=username, admin=True)
    # Prepare mock to get the access token
    mock_response = mock.MagicMock()
    mock_response.json.return_value = {}
    mock_requests = mock.MagicMock()
    mock_requests.request.return_value = mock_response
    mock_session.return_value = mock_requests
    server = token_hex(16)
    admin_access_token = token_hex(16)

    with pytest.raises(synapse.APIError, match="access_token"):
        synapse.get_access_token(user, server=server, admin_access_token=admin_access_token)


def test_override_rate_limit_success(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set User, admin_token and charm_state parameters.
    act: call override_rate_limit.
    assert: request is called as expected.
    """
    username = "any-user"
    user = User(username=username, admin=True)
    admin_access_token = token_hex(16)
    server = token_hex(16)
    synapse_config = SynapseConfig(server_name=server, report_stats="False", public_baseurl="")
    charm_state = CharmState(synapse_config=synapse_config, datasource=None, saml_config=None)
    expected_url = (
        f"http://localhost:8008/_synapse/admin/v1/users/@any-user:{server}/override_ratelimit"
    )
    expected_authorization = f"Bearer {admin_access_token}"
    do_request_mock = mock.MagicMock(return_value=mock.MagicMock())
    monkeypatch.setattr("synapse.api._do_request", do_request_mock)

    synapse.override_rate_limit(
        user, admin_access_token=admin_access_token, charm_state=charm_state
    )

    do_request_mock.assert_called_once_with(
        "DELETE", expected_url, headers={"Authorization": expected_authorization}
    )


def test_override_rate_limit_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set User, admin_token and charm_state parameters, mock request to raise exception.
    act: call override_rate_limit.
    assert: exception is raised as expected.
    """
    username = "any-user"
    user = User(username=username, admin=True)
    admin_access_token = token_hex(16)
    server = token_hex(16)
    synapse_config = SynapseConfig(server_name=server, report_stats="False", public_baseurl="")
    charm_state = CharmState(synapse_config=synapse_config, datasource=None, saml_config=None)
    expected_error_msg = "Failed to connect"
    do_request_mock = mock.MagicMock(side_effect=synapse.APIError(expected_error_msg))
    monkeypatch.setattr("synapse.api._do_request", do_request_mock)

    with pytest.raises(synapse.APIError, match=expected_error_msg):
        synapse.override_rate_limit(
            user, admin_access_token=admin_access_token, charm_state=charm_state
        )


def test_get_room_id_success(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set room_name and admin_token parameters.
    act: get room id.
    assert: room id is returned as expected.
    """
    admin_access_token = token_hex(16)
    room_name = token_hex(16)
    expected_url = f"http://localhost:8008/_synapse/admin/v1/rooms?search_term={room_name}"
    expected_authorization = f"Bearer {admin_access_token}"
    expected_room_id = token_hex(16)
    expected_room_res = [{"name": room_name, "room_id": expected_room_id}]
    mock_response = mock.MagicMock()
    mock_response.json.return_value = {"rooms": expected_room_res}
    do_request_mock = mock.MagicMock(return_value=mock_response)
    monkeypatch.setattr("synapse.api._do_request", do_request_mock)

    room_id = synapse.get_room_id(room_name=room_name, admin_access_token=admin_access_token)

    assert room_id == expected_room_id
    do_request_mock.assert_called_once_with(
        "GET", expected_url, headers={"Authorization": expected_authorization}
    )


def test_get_room_id_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set room_name and admin_token parameters,
        mock request to raise exception by removing expected field "room_id".
    act: get room id.
    assert: an error is returned.
    """
    admin_access_token = token_hex(16)
    room_name = token_hex(16)
    expected_room_res = [{"name": room_name}]
    mock_response = mock.MagicMock()
    mock_response.json.return_value = {"rooms": expected_room_res}
    do_request_mock = mock.MagicMock(return_value=mock_response)
    monkeypatch.setattr("synapse.api._do_request", do_request_mock)

    with pytest.raises(synapse.APIError, match="room_id"):
        synapse.get_room_id(room_name=room_name, admin_access_token=admin_access_token)


def test_deactivate_user_success(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set User, admin_token and server parameters.
    act: deactivate user.
    assert: request is called as expected.
    """
    username = "any-user"
    user = User(username=username, admin=True)
    admin_access_token = token_hex(16)
    server = token_hex(16)
    expected_url = f"http://localhost:8008/_synapse/admin/v1/deactivate/@{username}:{server}"
    expected_authorization = f"Bearer {admin_access_token}"
    do_request_mock = mock.MagicMock(return_value=mock.MagicMock())
    monkeypatch.setattr("synapse.api._do_request", do_request_mock)

    synapse.deactivate_user(user, admin_access_token=admin_access_token, server=server)

    do_request_mock.assert_called_once_with(
        "POST",
        expected_url,
        headers={"Authorization": expected_authorization},
        json={"erase": True},
    )


def test_deactivate_user_error(monkeypatch: pytest.MonkeyPatch):
    """
    arrange: set User, admin_token and server parameters.
    act: deactivate user.
    assert: exception is raised as expected.
    """
    username = "any-user"
    user = User(username=username, admin=True)
    admin_access_token = token_hex(16)
    server = token_hex(16)
    expected_error_msg = "Failed to connect"
    do_request_mock = mock.MagicMock(side_effect=synapse.APIError(expected_error_msg))
    monkeypatch.setattr("synapse.api._do_request", do_request_mock)

    with pytest.raises(synapse.APIError, match=expected_error_msg):
        synapse.deactivate_user(user, admin_access_token=admin_access_token, server=server)


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
    mock_requests.request.return_value = mock_response
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
    mock_request = mock.Mock()
    mock_request.request.side_effect = mock_response_error
    mock_session.return_value = mock_request

    with pytest.raises(synapse.APIError, match="Failed to connect to"):
        synapse.api._get_nonce()
    mock_response_exception = mock.MagicMock()
    mock_response_exception.text = "Fail"
    mock_response_http_error = requests.exceptions.HTTPError(response=mock_response_exception)
    mock_request = mock.Mock()
    mock_request.request.side_effect = mock_response_http_error
    mock_session.return_value = mock_request

    with pytest.raises(synapse.APIError, match="HTTP error from"):
        synapse.api._get_nonce()
    mock_response = mock.MagicMock()
    mock_response.json.return_value = None
    mock_request = mock.MagicMock()
    mock_request.request.return_value = mock_response
    mock_session.return_value = mock_request

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
    mock_session_instance.request.return_value = mock_response

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
    mock_requests.request.side_effect = mock_response_error
    mock_session.return_value = mock_requests
    with pytest.raises(synapse.APIError, match="Failed to connect to"):
        synapse.api.get_version()

    mock_response_exception = mock.MagicMock()
    mock_response_exception.text = "Fail"
    mock_response_http_error = requests.exceptions.HTTPError(response=mock_response_exception)
    mock_requests = mock.MagicMock()
    mock_requests.request.side_effect = mock_response_http_error
    mock_session.return_value = mock_requests
    with pytest.raises(synapse.APIError, match="HTTP error from"):
        synapse.api.get_version()

    mock_response = mock.MagicMock()
    mock_response.json.return_value = None
    mock_requests = mock.MagicMock()
    mock_requests.request.return_value = mock_response
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
    mock_session_instance.request.return_value = mock_response

    with pytest.raises(synapse.APIError, match="server_version has unexpected content"):
        synapse.api.get_version()
