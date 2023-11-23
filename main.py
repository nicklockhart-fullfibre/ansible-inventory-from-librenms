"""
Pull device groups, locations, names and hostnames from LibreNMS, and push them
into an Ansible inventory YAML file.

Nick Lockhart, 2023-11-22
"""

import requests
import yaml
import os
import sys
import re

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

# Create file with just devices
devices_resp = SESSION.get(f"{API_ROOT}/devices")
if devices_resp.status_code != 200:
    error = devices_resp.json()["message"]
    print(f"Failed to get device info: {error} ({devices_resp.status_code})")
    sys.exit(1)

device_data = devices_resp.json()["devices"]

all_devices = {"ungrouped": {"hosts": dict()}}
names_by_id = dict()

print(f"Processing {len(device_data)} devices... ", end='')
for device in device_data: 
    if not device["sysName"]: # our Libre instance has a device with an empty name
        continue

    ansible_device = {
        "ansible_host": device["hostname"]
    }
    device_id = device["device_id"]

    device_name: str = device["sysName"]
    # Clean up hostname for Ansible
    device_name = device_name.lower()
    device_name = re.sub(r'[\W_]+', '_', device_name)

    if not device_name: # see above - safeguard
        continue
    else:
        all_devices["ungrouped"]["hosts"][device_name] = ansible_device
        names_by_id[device_id] = device_name

print("done.")

print(f"Writing device data to file... ", end='')
with open("inventory/00-hosts.yaml", "w") as hosts_file:
    yaml.dump(data=all_devices, stream=hosts_file, default_flow_style=False)
print("done.")

# Create a file with group definitions
all_groups = dict()

groups_data = SESSION.get(f"{API_ROOT}/devicegroups").json()["groups"]

print(f"Processing {len(groups_data)} groups...")
for group in groups_data:
    group_id = group["id"]
    group_name: str = group["name"]

    # Sanitise group name for Ansible
    group_name = group_name.lower()
    group_name = re.sub(r'[\W_]+', '_', group_name)

    all_groups[group_name] = {"hosts": dict()}

    print(f"Processing group {group_name}... ", end='')
    group_data = SESSION.get(f"{API_ROOT}/devicegroups/{group_id}").json()
    for device in group_data["devices"]:
        device_id = device["device_id"]
        if device_id in names_by_id:
            group_device_name = names_by_id[device_id]
            # Device already defined in 00-hosts, no need to put anything here
            # other than specify its existence
            all_groups[group_name]["hosts"][group_device_name] = None

    print("done.")

print("Finished processing groups.")

print("Writing group data to file... ", end='')
with open("inventory/01-groups.yaml", "w") as groups_file:
    yaml.dump(data=all_groups, stream=groups_file, default_flow_style=False)
print("done.")

# Create a file with location definitions

all_locations = dict()

print("Creating locations data... ", end='')
for device in device_data:
    device_id = device["device_id"]
    if device_id not in names_by_id:
        continue
    else:
        device_name = names_by_id[device_id] # presanitised, let's not stress regex

    device_location: str = device["location"]
    # You know the deal by now.
    device_location = device_location.lower()
    device_location = re.sub(r'[\W_]+', '_', device_location)

    if device_location not in all_locations.keys():
        all_locations[device_location] = {"hosts": dict()}
    
    # see earlier in the code - host already defined
    # just need to say it's in the group
    all_locations[device_location]["hosts"][device_name] = None

print("done.")

print("Writing locations data to file... ", end='')
with open("inventory/02-locations.yaml", "w") as locations_file:
    yaml.dump(data=all_locations, stream=locations_file, default_flow_style=False)
print("done.")