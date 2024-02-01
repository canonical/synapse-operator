#!/usr/bin/python3
# Copyright 2024 Canonical Ltd.
# See LICENSE file for licensing details.

"""
Synapse does not purge empty directories from its media content storage locations.
Those can accumulate and eat up inodes and space.
Related: https://github.com/matrix-org/synapse/issues/16229
Related: https://github.com/matrix-org/synapse/issues/7690
"""

import os
import json
import time

# We assume that pyyaml is present thanks to synapse
import yaml

"""
To make sure that we don't steal IOPS from the running synapse instance,
we need to throttle the walk/rmdir iterations.
Given the MAX_IOPS, the formula is:
    ITERATIONS_BEFORE_SLEEP = (TARGET_IOPS * SLEEP_TIME * MAX_IOPS)/(MAX_IOPS - TARGET_IOPS)
The values choosen here are for a TARGET_IOPS of 100 on a disk of 1600 MAX_IOPS.
Which is very conservative if using a SSD. Check the table at https://en.wikipedia.org/wiki/IOPS#Solid-state_devices
"""
ITERATIONS_BEFORE_SLEEP = 100
SLEEP_TIME = 1


# This function is meant to fail if the media_store_path can't be found
def load_media_store_path(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
        return data["media_store_path"]


def delete_empty_dirs(path: str) -> None:
    i = 0
    for root, dirs, _ in os.walk(path, topdown=False):
        i += 1
        if i > ITERATIONS_BEFORE_SLEEP:
            i = 0
            time.sleep(SLEEP_TIME)
        for dir in dirs:
            try:
                os.rmdir(os.path.join(root, dir))
            except OSError:
                continue


if __name__ == "__main__":
    # load the environment from the file produced by /usr/local/bin/run_cron.py
    if os.path.isfile("/var/local/cron/environment.json"):
        with open("/var/local/cron/environment.json", "r") as env_fd:
            env = json.load(env_fd)
        if os.path.isfile(env["SYNAPSE_CONFIG_PATH"]):
            path = load_media_store_path(env["SYNAPSE_CONFIG_PATH"])
            if path:
                delete_empty_dirs(path)
