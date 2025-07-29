# Scripts

This folder contains utility scripts related to Matrix server maintenance and moderation.

## Available Scripts

### `reject-invites.py`

Script that reads Policy Rules from a given list of rooms and fetches banned users to reject any room invitations sent by them to your home server.

#### Usage

```bash
python3 reject-invites.py --server-url "https://chat.example.com" \
  --policy-rooms '!abcd1234:example.com,!wxyz5678:example.net'
```

#### Arguments

- `--server-url`: The base URL of your Matrix homeserver.
- `--policy-rooms`: Comma-separated list of room IDs containing the policy rules (ban lists).
