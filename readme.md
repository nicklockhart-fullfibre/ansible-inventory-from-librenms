# Generate an Ansible inventory from a LibreNMS host
This script uses a LibreNMS host's REST API to generate a set of Ansible inventory files.

It generates three files:
    - `00-hosts.yaml`, a file contianing hostnames for all hosts known by Libre
    - `01-groups.yaml`, a file containing all groups created in LibreNMS
    - `02-locations.yaml`, a file containing all locations created in LibreNMS.

This script depends on PyYAML and Requests. In addition, you must set `LNMS_HOST` and `LNMS_API_KEY` in your environment variables - see the source for more details.