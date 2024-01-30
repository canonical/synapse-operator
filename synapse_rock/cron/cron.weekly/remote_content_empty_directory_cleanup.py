#!/usr/bin/python3

"""
Synapse does not purge empty directories from its media content storage locations.
Those can accumulate and eat up inodes and space.
Related: https://github.com/matrix-org/synapse/issues/16229
Related: https://github.com/matrix-org/synapse/issues/7690
"""

import os
import json

# We assume that pyyaml is present thanks to synapse
import yaml

# This function is meant to fail if the media_store_path can't be found
def load_media_store_path(file_path: str) -> str:
    with open(file_path, 'r', encoding='utf-8') as file:
        data = yaml.safe_load(file)
        return data['media_store_path']

def delete_empty_dirs(path: str) -> None:
    for root, dirs, _ in os.walk(path, topdown=False):
        for dir in dirs:
            try:
                os.rmdir(os.path.join(root, dir))
            except OSError:
                continue

if __name__ == '__main__':
    # load the environment from the file produced by /usr/local/bin/run_cron.py
    if os.path.isfile("/var/local/cron/environment.json"):
        with open("/var/local/cron/environment.json", "r") as env_fd:
            env = json.load(env_fd)
        if os.path.isfile(env["SYNAPSE_CONFIG_PATH"]):
            path = load_media_store_path(env["SYNAPSE_CONFIG_PATH"])
            if path:
                delete_empty_dirs(path)
