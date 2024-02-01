#!/usr/bin/env python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""
The goal of this script is to serialize the environment passed by pebble to a file
and then to start the cron service. We're doing that because the environment of the cron service
is not passed to the commands started by it.
An alternative would have been to write to /etc/profile and start the called cron scripts with a login shell.
But we wanted to use python scripts and not pollute the environment of the users
(Creating a specific user for the cron service would be an added complexity).
"""

import json
import os

if __name__ == "__main__":
    file_path = "/var/local/cron/environment.json"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    with open(file_path, "w") as file:
        json.dump(dict(os.environ), file)

    os.execv("/usr/sbin/cron", ["/usr/sbin/cron", "-f", "-P"])
