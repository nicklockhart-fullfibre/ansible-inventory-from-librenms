"""
Pull device groups, locations, names and hostnames from LibreNMS, and push them
into an Ansible inventory YAML file.

Nick Lockhart, 2023-11-22
"""

import requests
import yaml
import os
import sys

LNMS_HOST = os.environ.get("LNMS_HOST")
if not LNMS_HOST:
    print(
        "Please set LNMS_HOST in your environment variables.",
        "Make sure to include the protocol - i.e 'http://127.0.0.1'"
    )
    sys.exit(1)

LNMS_API_KEY = os.environ.get("LNMS_API_KEY")
if not LNMS_API_KEY:
    print("Please set LNMS_API_KEY in your environment variables.")
    sys.exit(1)

SESSION = requests.Session()
SESSION.headers = {"X-Auth-Token": LNMS_API_KEY}
API_ROOT = f"{LNMS_HOST}/api/v0"

# Initialise final structure
inventory = dict()
inventory["ungrouped"] = dict()
inventory["ungrouped"]["hosts"] = dict()

# Configure the YAML writer to not write "null" for empty tags
# This is what Ansible wants
def represent_none(self, _):
    return self.represent_scalar('tag:yaml.org,2002:null', '')

yaml.add_representer(type(None), represent_none)

devices_resp = SESSION.get(f"{API_ROOT}/devices")
if devices_resp.status_code != 200:
    error = devices_resp.json()["message"]
    print(f"Failed to get device info: {error} ({devices_resp.status_code})")
    sys.exit(1)

device_data = devices_resp.json()["devices"]

groups_data = SESSION.get(f"{API_ROOT}/devicegroups").json()

print(f"Processing {groups_data['count']} groups...")

grouped_ids = set()

for group in groups_data["groups"]:
    group_id = group["id"]

    # Clean up group name to fit Ansible standards
    group_name: str = group["name"]
    group_name = group_name.replace(" ", "_").replace("-", "_")

    print(f"Processing group {group_name}...", end='\r')

    inventory[group_name] = dict()
    inventory[group_name]["hosts"] = dict()

    group_data = SESSION.get(f"{API_ROOT}/devicegroups/{group_id}").json()

    devices = [device["device_id"] for device in group_data["devices"]]
    grouped_ids.update(devices) # add these to "grouped_ids" so they're not put in unsorted

    for device in devices:
        group_device_data = SESSION.get(f"{API_ROOT}/devices/{device}").json()["devices"][0]
        device_host = group_device_data["hostname"]
        device_name = group_device_data["sysName"]

        if device_name is None:
            # see later in the code - someone put an unnamed devices in our Libre
            continue    

        # Clean up device name for Ansible
        # Shouldn't be as nessecary as for group names, but won't hurt anything
        device_name = device_name.replace(" ", "_").replace("-", "_")

        ansible_device = {
            "ansible_host": device_host
        }

        inventory[group_name]["hosts"][device_name] = ansible_device
    
    print(f"Processing group {group_name}... done")

ungrouped_devices = [device for device in device_data if device["device_id"] not in grouped_ids]

for device in ungrouped_devices:
    ansible_device = {
        "ansible_host": device["hostname"]
    }
    device_name = device["sysName"]
    if not device_name:
        # dangit, who put an empty device name into Libre?
        continue
    else:
        inventory["ungrouped"]["hosts"][device_name] = ansible_device

with open("inventory.yaml", "w") as inventory_file:
    yaml.dump(data=inventory, stream=inventory_file, default_flow_style=False)