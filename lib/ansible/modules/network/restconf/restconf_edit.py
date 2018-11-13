#!/usr/bin/python
# Copyright: Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function
__metaclass__ = type


ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'network'}


DOCUMENTATION = """
---
module: restconf_edit
version_added: "2.8"
author: "Ganesh Nalawade (@ganeshrn)"
short_description: Handles create, update, read and delete of configuration data on RESTCONF enabled devices.
description:
    - RESTCONF is a standard mechanisms to allow web applications to configure and manage
      data. RESTCONF is a IETF standard and documented on RFC 8040.
    - This module allows the user to configure data on RESTCONF enabled devices.
options:
  path:
    description:
      - URI being used to execute API calls.
    required: true
  content:
    description:
      - The configuration data in format as specififed in C(format) option.
  method:
    description:
      - The RESTCONF method to manage the configuration change on device. The value I(post) is used to
        create a data resource or invoke an operation resource, value I(put) is used to replace the
        target data resource and value I(delete) is used to delete the target resource.
    required: false
    default: post
    choices:['post', 'put', 'delete']
  format:
    fields:
      - The format of input configuration data.
    required: false
    default: json
    choices:['json', 'xml']
"""

EXAMPLES = """
- name: create l3vpn services
restconf_edit:
    path: /config/ietf-l3vpn-svc:l3vpn-svc/vpn-services
    content: |
          {
            "vpn-service":[
                            {
                              "vpn-id": "red_vpn2",
                              "customer-name": "blue",
                              "vpn-service-topology": "ietf-l3vpn-svc:any-to-any"
                            },
                            {
                              "vpn-id": "blue_vpn1",
                              "customer-name": "red",
                              "vpn-service-topology": "ietf-l3vpn-svc:any-to-any"
                            }
                          ]
           }
"""

RETURN = """
"""
import json

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import ConnectionError
from ansible.module_utils.network.common.utils import dict_diff
from ansible.module_utils.network.restconf import restconf
from ansible.module_utils.six import string_types


def main():
    """entry point for module execution
    """
    argument_spec = dict(
        path=dict(required=True),
        content=dict(required=True),
        method=dict(choices=['post', 'put', 'delete'], default='put'),
        format=dict(choices=['json', 'xml'], default='json'),
    )

    module = AnsibleModule(
        argument_spec=argument_spec,
        supports_check_mode=True
    )

    path = module.params['path']
    candidate = module.params['content']
    method = module.params['method']
    format = module.params['format']

    if isinstance(candidate, string_types):
        candidate = json.loads(candidate)

    warnings = list()
    result = {'changed': False, 'warnings': warnings}

    running = None
    response = None
    commit = not module.check_mode
    try:
        running = restconf.get(module, path, output=format)
        if running:
            key = path.split('/')[-1]
            running = running[key]
    except ConnectionError as exc:
        if exc.code == 404:
            running = None
        else:
            module.fail_json(msg=module.from_json(exc.message), code=exc.code)

    try:
        if method.lower() == 'delete':
            if running:
                if commit:
                    response = restconf.edit_config(module, path=path, method='DELETE')
                result['changed'] = True
            else:
                warnings.append("delete not executed as resource '%s' does not exist" % path)
        else:
            if running:
                if method.lower() == 'post':
                    module.fail_json(msg="resource '%s' already exist" % path, code=409)
                diff = dict_diff(running, candidate)
                result['candidate'] = candidate
                result['running'] = running
            else:
                method = 'POST'
                diff = candidate

            if diff:
                if module._diff:
                    result['diff'] = {'prepared': diff, 'before': candidate, 'after': running}

                if commit:
                    response = restconf.edit_config(module, path=path, content=diff, method=method.upper(), format=format)
                result['changed'] = True

    except ConnectionError as exc:
        module.fail_json(msg=module.from_json(exc.message), code=exc.code)

    result['response'] = response

    module.exit_json(**result)


if __name__ == '__main__':
    main()
