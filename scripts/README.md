# Scripts

This folder contains utility scripts related to Matrix server maintenance, moderation, and administration.

## Environment Variables

All scripts require the following environment variables:

- `ADMIN_ACCESS_TOKEN`: Admin access token for your Matrix homeserver
- `HOMESERVER`: (Optional) Homeserver name for logging purposes

## Available Scripts

### `reject_invites.py`

Script that reads Policy Rules from a given list of rooms and fetches banned users to reject any room invitations sent by them to your home server.

#### reject_invites.py Usage

```bash
export ADMIN_ACCESS_TOKEN="syt_Y78hbmRhaGxh_LoAzT123toPqXJUhVPio_012345"
export HOMESERVER="example.com"
python3 reject_invites.py --server-url "https://chat.example.com" \
  --policy-rooms '!abcd1234:example.com,!wxyz5678:example.net'
```

#### reject_invites.py Arguments

- `--server-url`: The base URL of your Matrix homeserver (required)
- `--policy-rooms`: Comma-separated list of room IDs containing the policy rules (ban lists) (required)

### `upgrade_rooms.py`

Script that upgrades all public rooms to a new room version. Can upgrade all public rooms or a specific room.

#### upgrade_rooms.py Usage

```bash
export ADMIN_ACCESS_TOKEN="syt_Y78hbmRhaGxh_LoAzT123toPqXJUhVPio_012345"
export HOMESERVER="example.com"
python3 upgrade_rooms.py --server-url "https://chat.example.com" \
  --version 10
```

#### upgrade_rooms.py Arguments

- `--server-url`: The base URL of your Matrix homeserver (required)
- `--version`: New room version for the public rooms (required)
- `--room-id`: (Optional) Specific public room ID to upgrade. If omitted, upgrades all public rooms
- `--dry-run`: (Optional) Only list public rooms and their versions without upgrading
- `--limit`: (Optional) Limit the number of public rooms returned in --dry-run (default: 30)
- `--ignore-errors`: (Optional) Don't ask for confirmation on retry and skip errors
- `--yes`: (Optional) Automatically confirm upgrading each room without prompting

### `send_message.py`

Script that sends a message to a Matrix room. Can send as admin user or impersonate another user. Optionally pins the message after sending.

#### send_message.py Usage

```bash
export ADMIN_ACCESS_TOKEN="syt_Y78hbmRhaGxh_LoAzT123toPqXJUhVPio_012345"
export HOMESERVER="example.com"

# Send message as admin user
python3 send_message.py --server-url "https://chat.example.com" \
  --room-id "!room:example.com" \
  --message "Hello, world!"

# Send message as specific user
python3 send_message.py --server-url "https://chat.example.com" \
  --room-id "!room:example.com" \
  --user-id "@user:example.com" \
  --message "Hello from user!"

# Send and pin a message
python3 send_message.py --server-url "https://chat.example.com" \
  --room-id "!room:example.com" \
  --message "Important announcement!" \
  --pin
```

#### send_message.py Arguments

- `--server-url`: The base URL of your Matrix homeserver (required)
- `--room-id`: Room ID to send message to (required)
- `--user-id`: (Optional) User ID to send message as. If not provided, uses admin user
- `--message`: (Optional) Message to send. If not provided, will be read from stdin
- `--message-type`: (Optional) Message type (default: m.text). Options: m.text, m.emote, m.notice
- `--pin`: (Optional) Pin the message after sending it
- `--dry-run`: (Optional) Only verify room access without sending message


## Security Considerations

- Store admin access tokens securely
- Use environment variables instead of command-line arguments for sensitive data
- Test scripts with --dry-run before executing potentially destructive operations
- Ensure proper permissions are set on script files and environment variable files`
