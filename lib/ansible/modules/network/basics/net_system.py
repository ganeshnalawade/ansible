#!/usr/bin/python
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'core'
}


DOCUMENTATION = """
"""

EXAMPLES = """
"""

RETURN = """
"""
from ansible.module_utils.basic import AnsibleModule

def main():
    """ main entry point for module execution
    """
    argument_spec = dict(
        hostname=dict(),

        domain_name=dict(),
        domain_search=dict(type='list'),
        name_servers=dict(type='list'),
        vrf=dict(),

        state=dict(default='present', choices=['present', 'absent'])
    )

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=True)

    config = {
        'hostname': module.params['hostname'],
        'domain_name': module.params['domain_name'],
        'domain_search': module.params['domain_search'],
        'name_servers': module.params['name_servers'],
        'vrf': module.params['vrf']
    }

    module.exit_json(config=config, spec=argument_spec)

if __name__ == '__main__':
    main()
