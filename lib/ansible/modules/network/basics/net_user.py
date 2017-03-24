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
    'supported_by': 'community'
}


DOCUMENTATION = """
"""

EXAMPLES = """
"""

RETURN = """
"""
from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.pycompat24 import get_exception
from ansible.module_utils.six import iteritems
from ansible.module_utils.network_common import ComplexList, to_list


def get_spec(module):
    args = frozenset(['username', 'password', 'nopassword', 'update_password',
                    'privilege', 'role', 'sshkey', 'state'])
    keys = frozenset(['username'])
    return ComplexList(module, args=args, keys=keys, from_argspec=True)

def parse_params(module):
    obj = {}
    for item in args:
        obj[item] = module.params[item]
    return [obj]

def parse(module, spec):
    objects = spec(module.params['collection'] or to_list(module.params), strict=False)
    for item in objects:
        for key, value in iteritems(item):
            if module.params[key] and not value:
                item[key] = module.params[key]
    return objects


def main():
    """ main entry point for module execution
    """
    argument_spec = dict(
        username=dict(),
        collection=dict(type='list'),

        password=dict(no_log=True),
        nopassword=dict(type='bool'),
        update_password=dict(default='always', choices=['on_create', 'always']),

        privilege=dict(type='int'),
        role=dict(),

        sshkey=dict(),

        purge=dict(type='bool', default=False),
        state=dict(default='present', choices=['present', 'absent'])
    )

    mutually_exclusive = [('username', 'collection')]

    module = AnsibleModule(argument_spec=argument_spec,
                           mutually_exclusive=mutually_exclusive,
                           supports_check_mode=True)

    spec = get_spec(module)
    result = {
        'config': parse(module, spec),
        'purge': module.params['purge'],
        'spec': spec.serialize()
    }

    module.exit_json(**result)

if __name__ == '__main__':
    main()
