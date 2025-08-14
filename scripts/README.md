# Scripts

This folder contains utility scripts related to Matrix server maintenance and moderation.

## Available Scripts

### `reject-invites.py`

Script that reads Policy Rules from a given list of rooms and fetches banned users to reject any room invitations sent by them to your home server.

#### Usage

```bash
export ADMIN_ACCESS_TOKEN="syt_Y78hbmRhaGxh_LoAzT123toPqXJUhVPio_012345"
python3 reject-invites.py --server-url "https://chat.example.com" \
  --policy-rooms '!abcd1234:example.com,!wxyz5678:example.net'
```

#### Arguments

- `--server-url`: The base URL of your Matrix homeserver.
- `--policy-rooms`: Comma-separated list of room IDs containing the policy rules (ban lists).

### `upgrade-rooms.py`

Script that upgrade all public rooms as specific user defined by ADMIN_ACCESS_TOKEN environment variable.

#### Usage

```bash
export ADMIN_ACCESS_TOKEN="syt_Y78hbmRhaGxh_LoAzT123toPqXJUhVPio_012345"
python3 upgrade-rooms.py --server-url "https://chat.example.com" \
  --version 12
```

#### Arguments

- `--server-url`: The base URL of your Matrix homeserver.
- `--version`: New version for the public rooms.
- `--room-id`: [optional] Public room id to upgrade (default: upgrade all public rooms).
- `--dry-run`: [optional] Only list public rooms (default: false).
- `--limit`: [optional] Limit the number of public rooms returned in --dry-run (default: 30).`
