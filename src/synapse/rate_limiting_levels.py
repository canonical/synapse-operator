#!/usr/bin/env python3

# Copyright 2025 Canonical Ltd.
# See LICENSE file for licensing details.

"""Define values for rate_limiting_level."""

from charm_state import RateLimitingLevel

_DEFAULT = {
    "rc_message": {
        "per_second": 0.2,
        "burst_count": 10.0,
    },
    "rc_admin_redaction": {
        "per_second": 1.0,
        "burst_count": 50.0,
    },
    "rc_joins": {
        "local": {
            "per_second": 0.1,
            "burst_count": 10.0,
        },
        "remote": {
            "per_second": 0.01,
            "burst_count": 10.0,
        },
    },
    "rc_joins_per_room": {
        "per_second": 1.0,
        "burst_count": 10.0,
    },
    "rc_invites": {
        "per_room": {
            "per_second": 0.3,
            "burst_count": 10.0,
        },
        "per_user": {
            "per_second": 0.003,
            "burst_count": 5.0,
        },
        "per_issuer": {
            "per_second": 0.3,
            "burst_count": 10.0,
        },
    },
    "rc_presence": {
        "per_user": {
            "per_second": 0.1,
            "burst_count": 1.0,
        },
    },
    "rc_delayed_event_mgmt": {
        "per_second": 1.0,
        "burst_count": 5.0,
    },
    "rc_room_creation": {
        "per_second": 0.016,
        "burst_count": 10.0,
    },
    "federation_rr_transactions_per_room_per_second": 50,
}

_PERMISSIVE = {
    "rc_message": {
        "per_second": 0.5,
        "burst_count": 50.0,
    },
    "rc_admin_redaction": {
        "per_second": 0.5,
        "burst_count": 50.0,
    },
    "rc_joins": {
        "local": {
            "per_second": 0.5,
            "burst_count": 50.0,
        },
        "remote": {
            "per_second": 0.01,
            "burst_count": 50.0,
        },
    },
    "rc_joins_per_room": {
        "per_second": 0.5,
        "burst_count": 50.0,
    },
    "rc_invites": {
        "per_room": {
            "per_second": 0.1,
            "burst_count": 50.0,
        },
        "per_user": {
            "per_second": 0.1,
            "burst_count": 50.0,
        },
        "per_issuer": {
            "per_second": 0.1,
            "burst_count": 50.0,
        },
    },
    "rc_presence": {
        "per_user": {
            "per_second": 0.1,
            "burst_count": 20.0,
        },
    },
    "rc_delayed_event_mgmt": {
        "per_second": 0.5,
        "burst_count": 10.0,
    },
    "rc_room_creation": {
        "per_second": 0.016,
        "burst_count": 20.0,
    },
    "federation_rr_transactions_per_room_per_second": 100,
}

_UNLIMITED = {
    "rc_message": {
        "per_second": 9999,
        "burst_count": 9999,
    },
    "rc_admin_redaction": {
        "per_second": 9999,
        "burst_count": 9999,
    },
    "rc_joins": {
        "local": {
            "per_second": 9999,
            "burst_count": 9999,
        },
        "remote": {
            "per_second": 9999,
            "burst_count": 9999,
        },
    },
    "rc_joins_per_room": {
        "per_second": 9999,
        "burst_count": 9999,
    },
    "rc_invites": {
        "per_room": {
            "per_second": 1000,
            "burst_count": 1000,
        },
        "per_user": {
            "per_second": 1000,
            "burst_count": 1000,
        },
        "per_issuer": {
            "per_second": 1000,
            "burst_count": 1000,
        },
    },
    "rc_presence": {
        "per_user": {
            "per_second": 9999,
            "burst_count": 9999,
        },
    },
    "rc_delayed_event_mgmt": {
        "per_second": 9999,
        "burst_count": 9999,
    },
    "rc_room_creation": {
        "per_second": 9999,
        "burst_count": 9999,
    },
    "federation_rr_transactions_per_room_per_second": 9999,
}

RATE_LIMITING_CONFIG = {
    RateLimitingLevel.DEFAULT.value: _DEFAULT,
    RateLimitingLevel.PERMISSIVE.value: _PERMISSIVE,
    RateLimitingLevel.UNLIMITED.value: _UNLIMITED,
}
