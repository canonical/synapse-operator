# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Matrix data that must survive changes to the deployment, and the checks that it did."""

import logging
import time
import typing
import urllib.parse
import uuid
from secrets import token_hex

import requests
from juju.application import Application

from tests.integration.helpers import get_access_token, register_user

logger = logging.getLogger(__name__)

CLIENT = "/_matrix/client/v3"
MEDIA_CONTENT = b"media that must survive " + bytes(range(256))
ROOM_NAME = "Nothing here may be lost"
ROOM_TOPIC = "Messages, state, receipts and media"
TIMEOUT = 30


class MatrixData:  # pylint: disable=too-many-instance-attributes
    """Users, a room and its content, created through the client API of the Synapse units.

    Everything here is stored in PostgreSQL or in the media store, never in Redis or Valkey.
    So it must be the same on every unit after any change to the cache, to the units or to their
    addresses. A new message must also still reach /sync on every other unit, which only works
    while the units can talk to each other through the cache.

    Attributes:
        alice: user name, user ID and access token of the room's creator, a server admin.
        bob: user name, user ID and access token of the second member.
        room_id: the room that both users are in.
        messages: the body of every message sent so far, by event ID.
        receipt_event_id: the event that bob's read receipt points at.
        media_uri: the content URI of the uploaded media file.
        account_data: the content of alice's lab.migration account data.
    """

    def __init__(self) -> None:
        """Initialize an empty data set."""
        self.alice: dict[str, str] = {}
        self.bob: dict[str, str] = {}
        self.room_id = ""
        self.messages: dict[str, str] = {}
        self.receipt_event_id = ""
        self.media_uri = ""
        self.account_data = {"marker": token_hex(8)}

    @staticmethod
    def _call(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        unit_ip: str,
        method: str,
        path: str,
        token: str,
        json: typing.Optional[dict] = None,
        prefix: str = CLIENT,
    ) -> dict:
        """Call the Matrix API through the NGINX of one unit.

        Args:
            unit_ip: the unit's address.
            method: the HTTP method.
            path: the path under the prefix.
            token: the access token.
            json: the request body.
            prefix: the API prefix.

        Returns:
            The decoded response.
        """
        response = requests.request(
            method,
            f"http://{unit_ip}:8080{prefix}{path}",
            headers={"Authorization": f"Bearer {token}"},
            json=json,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        return response.json()

    def _room(self, rest: str) -> str:
        """Get a client API path under the room.

        Args:
            rest: the path under the room.

        Returns:
            The path.
        """
        return f"/rooms/{urllib.parse.quote(self.room_id)}{rest}"

    def send(self, unit_ip: str, sender: dict[str, str]) -> str:
        """Send a message through one unit and remember it.

        Args:
            unit_ip: the unit's address.
            sender: the user that sends the message.

        Returns:
            The event ID.
        """
        body = f"message {uuid.uuid4().hex}"
        event_id = self._call(
            unit_ip,
            "PUT",
            self._room(f"/send/m.room.message/{uuid.uuid4().hex}"),
            sender["token"],
            {"msgtype": "m.text", "body": body},
        )["event_id"]
        self.messages[event_id] = body
        return event_id

    @classmethod
    async def create(
        cls, synapse_app: Application, unit_ips: typing.Sequence[str]
    ) -> "MatrixData":
        """Create the users, the room and its content.

        Args:
            synapse_app: the Synapse application.
            unit_ips: the address of every Synapse unit.

        Returns:
            The data that was created.
        """
        data = cls()
        for index, user in enumerate((data.alice, data.bob)):
            user["name"] = f"user{token_hex(8)}"
            password = await register_user(synapse_app, user["name"])
            user["token"] = get_access_token(
                unit_ips[index % len(unit_ips)], user["name"], password
            )
            user["id"] = cls._call(unit_ips[0], "GET", "/account/whoami", user["token"])["user_id"]
        for user in (data.alice, data.bob):
            # Without this, Synapse answers 429 to the messages that the checks send.
            cls._call(
                unit_ips[0],
                "POST",
                f"/users/{urllib.parse.quote(user['id'])}/override_ratelimit",
                data.alice["token"],
                {"messages_per_second": 0, "burst_count": 0},
                prefix="/_synapse/admin/v1",
            )
        data.room_id = cls._call(
            unit_ips[0],
            "POST",
            "/createRoom",
            data.alice["token"],
            {
                "name": ROOM_NAME,
                "topic": ROOM_TOPIC,
                "preset": "private_chat",
                "invite": [data.bob["id"]],
            },
        )["room_id"]
        cls._call(
            unit_ips[-1],
            "POST",
            f"/join/{urllib.parse.quote(data.room_id)}",
            data.bob["token"],
            {},
        )
        for number in range(10):
            data.send(unit_ips[number % len(unit_ips)], (data.alice, data.bob)[number % 2])
        data.receipt_event_id = list(data.messages)[-1]
        cls._call(
            unit_ips[-1],
            "POST",
            data._room(f"/receipt/m.read/{urllib.parse.quote(data.receipt_event_id)}"),
            data.bob["token"],
            {},
        )
        cls._call(
            unit_ips[0],
            "PUT",
            f"/user/{urllib.parse.quote(data.alice['id'])}/account_data/lab.migration",
            data.alice["token"],
            data.account_data,
        )
        upload = requests.post(
            f"http://{unit_ips[0]}:8080/_matrix/media/v3/upload?filename=check.bin",
            headers={
                "Authorization": f"Bearer {data.alice['token']}",
                "Content-Type": "application/octet-stream",
            },
            data=MEDIA_CONTENT,
            timeout=TIMEOUT,
        )
        upload.raise_for_status()
        data.media_uri = upload.json()["content_uri"]
        return data

    def _stored_messages(self, unit_ip: str) -> dict[str, list[str]]:
        """Get every message in the room as one unit returns them.

        Args:
            unit_ip: the unit's address.

        Returns:
            The bodies found for each event ID.
        """
        found: dict[str, list[str]] = {}
        start = None
        while True:
            query = {"dir": "b", "limit": "500"}
            if start:
                query["from"] = start
            page = self._call(
                unit_ip,
                "GET",
                self._room(f"/messages?{urllib.parse.urlencode(query)}"),
                self.alice["token"],
            )
            for event in page.get("chunk", []):
                if event.get("type") == "m.room.message":
                    found.setdefault(event["event_id"], []).append(event["content"].get("body"))
            start = page.get("end")
            if not start or not page.get("chunk"):
                return found

    def check_stored(self, unit_ip: str) -> None:
        """Check that one unit still returns everything that was created, exactly once.

        Args:
            unit_ip: the unit's address.
        """
        for user in (self.alice, self.bob):
            whoami = self._call(unit_ip, "GET", "/account/whoami", user["token"])
            assert whoami["user_id"] == user["id"], f"{unit_ip}: the session of {user['id']}"
        self._check_room(unit_ip)
        self._check_user_data(unit_ip)

    def _check_room(self, unit_ip: str) -> None:
        """Check the room's messages, members and state on one unit.

        Args:
            unit_ip: the unit's address.
        """
        token = self.alice["token"]
        found = self._stored_messages(unit_ip)
        missing = [event_id for event_id in self.messages if event_id not in found]
        assert not missing, f"{unit_ip}: {len(missing)} of {len(self.messages)} messages are gone"
        changed = [e for e, body in self.messages.items() if found[e] != [body]]
        assert not changed, f"{unit_ip}: {len(changed)} messages changed or are duplicated"
        members = self._call(unit_ip, "GET", self._room("/joined_members"), token)
        assert set(members["joined"]) == {self.alice["id"], self.bob["id"]}, f"{unit_ip}: members"
        name = self._call(unit_ip, "GET", self._room("/state/m.room.name"), token)
        assert name.get("name") == ROOM_NAME, f"{unit_ip}: room name"
        topic = self._call(unit_ip, "GET", self._room("/state/m.room.topic"), token)
        assert topic.get("topic") == ROOM_TOPIC, f"{unit_ip}: room topic"

    def _check_user_data(self, unit_ip: str) -> None:
        """Check the account data, the read receipt and the media file on one unit.

        Args:
            unit_ip: the unit's address.
        """
        token = self.alice["token"]
        account_data = self._call(
            unit_ip,
            "GET",
            f"/user/{urllib.parse.quote(self.alice['id'])}/account_data/lab.migration",
            token,
        )
        assert account_data == self.account_data, f"{unit_ip}: account data"
        sync = self._call(unit_ip, "GET", "/sync?timeout=0", token)
        ephemeral = sync["rooms"]["join"][self.room_id].get("ephemeral", {}).get("events", [])
        readers = [
            user_id
            for event in ephemeral
            if event.get("type") == "m.receipt"
            for user_id in event["content"].get(self.receipt_event_id, {}).get("m.read", {})
        ]
        assert self.bob["id"] in readers, f"{unit_ip}: the read receipt of {self.bob['id']}"
        server, media_id = self.media_uri.removeprefix("mxc://").split("/", 1)
        media = requests.get(
            f"http://{unit_ip}:8080/_matrix/client/v1/media/download/{server}/{media_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
        )
        media.raise_for_status()
        assert media.content == MEDIA_CONTENT, f"{unit_ip}: the media file"

    def check_delivery(self, sender_ip: str, reader_ip: str) -> None:
        """Check that a new message sent through one unit reaches /sync on another unit.

        A unit only learns about an event written through another unit over Redis or Valkey.

        Args:
            sender_ip: the address of the unit to send through.
            reader_ip: the address of the unit to read from.

        Raises:
            AssertionError: if the message doesn't reach the other unit in time.
        """
        since = self._call(reader_ip, "GET", "/sync?timeout=0", self.bob["token"])["next_batch"]
        event_id = self.send(sender_ip, self.alice)
        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            query = urllib.parse.urlencode({"timeout": 5000, "since": since})
            sync = self._call(reader_ip, "GET", f"/sync?{query}", self.bob["token"])
            since = sync["next_batch"]
            room = sync.get("rooms", {}).get("join", {}).get(self.room_id, {})
            if any(e["event_id"] == event_id for e in room.get("timeline", {}).get("events", [])):
                return
        raise AssertionError(f"a message sent through {sender_ip} never reached {reader_ip}")

    def check(self, unit_ips: typing.Sequence[str], wait: int = 300) -> None:
        """Check every unit, and delivery between every pair of units.

        After a change, a unit can take a moment to serve requests again and to reconnect to the
        cache. So a failed check is repeated until it passes or the time is up. Nothing that was
        acknowledged may be missing once the units have settled.

        Args:
            unit_ips: the address of every Synapse unit.
            wait: how long to keep trying, in seconds.

        Raises:
            AssertionError: if a check still fails when the time is up.
            RequestException: if a unit still doesn't answer when the time is up.
        """
        deadline = time.monotonic() + wait
        while True:
            try:
                for unit_ip in unit_ips:
                    self.check_stored(unit_ip)
                for sender_ip in unit_ips:
                    for reader_ip in unit_ips:
                        if sender_ip != reader_ip:
                            self.check_delivery(sender_ip, reader_ip)
                for unit_ip in unit_ips:
                    self.check_stored(unit_ip)
                return
            except (AssertionError, requests.RequestException) as exc:
                if time.monotonic() > deadline:
                    raise
                logger.info("data check failed, trying again: %s", exc)
                time.sleep(10)
