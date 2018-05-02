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

ANSIBLE_METADATA = {'metadata_version': '1.1',
                    'status': ['preview'],
                    'supported_by': 'network'}


DOCUMENTATION = """
---
module: network_config
version_added: "2.6"
short_description: Manage Network configuration sections
description:
  - 
notes:
  - Abbreviated commands are NOT idempotent, see
    L(Network FAQ,../network/user_guide/faq.html#why-do-the-config-modules-always-return-changed-true-with-abbreviated-commands).
options:
  content:
    description:
      - The configuration in string format.
  format:
    description:
      - The I(format) argument specifies the format of the configuration
        found int I(content).  If the I(format) argument is not provided,
        the module will attempt to determine the format of the configuration
        based on default configuration for the particular remote host.
    choices: ['xml', 'set', 'text', 'json']
  match:
    description:
      - Instructs the module on the way to perform the matching of
        the set of commands against the current device config.  If
        match is set to I(line), commands are matched line by line.  If
        match is set to I(strict), command lines are matched with respect
        to position.  If match is set to I(exact), command lines
        must be an equal match.  Finally, if match is set to I(none), the
        module will not attempt to compare the source configuration with
        the running configuration on the remote device. The default value is I(line)
    choices: ['line', 'strict', 'exact', 'none']
  replace:
    description:
      - Instructs the module on the way to perform the configuration
        on the device.  If the replace argument is set to I(line) then
        the modified lines are pushed to the device in configuration
        mode.  If the replace argument is set to I(block) then the entire
        command block is pushed to the device in configuration mode if any
        line is not correct. If the replace argument is set to I(config)
        replace the entire running configuration with candidate configuration.
        The default value is I(line)
    choices: ['line', 'block', 'config']
  multiline_delimiter:
    description:
      - This argument is used when pushing a multiline configuration
        element to network device. It specifies the character to use
        as the delimiting character. This only applies to the
        configuration action on supported platforms. The default value is I(@)
  defaults:
    description:
      - This argument specifies whether or not to collect all defaults
        when getting the remote device running config.  When enabled,
        the module will get the current config by issuing with default
        flag. The default value is I(False)
    type: bool
  diff_ignore_lines:
    description:
      - Use this argument to specify one or more lines that should be
        ignored during the diff.  This is used for lines in the configuration
        that are automatically updated by the system.  This argument takes
        a list of regular expressions or exact line matches.
  nolog:
    description:
      - This argument specifies whether or not to log the commands output
        in the result. If the value is set to C(True) all the commands executed on
        remote host and it's response will be logged in the return result. 
        If the value is C(False) the response will contain all the executed commands
        only and the response will be redacted. The default value is I(False)
    default: False
    type: bool
"""

EXAMPLES = """
- name: configure interface settings
  network_config:
    content: "interface Ethernet1\ndescription test interface\nip address 172.31.1.1 255.255.255.0"
"""

RETURN = """
history:
  description: The set of commands that are executed on remote device. If nolog is set to True 
               it will also contain response
  returned: always
  type: list
  sample: [('hostname foo', ****), ('router ospf 1', ****)]
commands:
  description: The set of commands that will be pushed to the remote device
  returned: always
  type: list
  sample: ['hostname foo', 'router ospf 1', 'router-id 1.1.1.1']
diff:
  description: The diff between running and cadidate configuration
  returned: when --diff flag is enabled
  type: dict
  sample:  {'prepared': {'config_diff': 'hostname foo\nrouter ospf 1')
"""
import json

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.connection import Connection


def main():
    """main entry point for module execution
    """
    argument_spec = dict(
        content=dict(required=True),
        nolog=dict(default=False, type='bool'),
        match=dict(choices=['line', 'strict', 'exact', 'none']),
        replace=dict(choices=['line', 'block', 'config']),
        format=dict(choices=['xml', 'set', 'text', 'json']),
        defaults=dict(type='bool'),
        diff_ignore_lines=dict(type='list'),
        multiline_delimiter=dict()
    )

    module = AnsibleModule(argument_spec=argument_spec,
                           supports_check_mode=True)

    result = {'changed': False}

    connection = Connection(module._socket_path)
    capabilities = module.from_json(connection.get_capabilities())
    config_capabilities = capabilities['config_capability']

    # Fetch device config capability
    supports_replace = config_capabilities.get('supports_replace')
    supports_match = config_capabilities.get('supports_match')
    supports_generate_diff = config_capabilities['supports_generate_diff']
    supported_format = config_capabilities['format']

    # check if input options are supported for given device

    # check defaults support
    defaults = module.params['defaults']
    if not config_capabilities.get('supports_defaults') and defaults:
        module.fail_json(msg='Fetching configuration with defaults is not supported on this device')

    # check replace support
    replace = module.params['replace']
    if not supports_replace and replace:
        module.fail_json(msg='replace is not supported on this device')
    elif supports_replace and replace and replace not in config_capabilities['replace']:
        module.fail_json(msg='replace value %s is not supported on this device, valid values are %s' % (replace, config_capabilities['replace']))

    # check diff_ignore_lines support
    diff_ignore_lines = module.params['diff_ignore_lines']
    if not config_capabilities.get('supports_diff_ignore_lines') and diff_ignore_lines:
        module.fail_json(msg='diff_ignore_lines is not supported on this device')

    # check multiline_delimiter support
    multiline_delimiter = module.params['multiline_delimiter']
    if not config_capabilities.get('supports_multiline_delimiter') and multiline_delimiter:
        module.fail_json(msg='multiline_delimiter is not supported on this device')

    # check match support
    match = module.params['match']
    if not supports_match and match:
        module.fail_json(msg='match is not supported on this device')
    elif supports_match and match and match not in config_capabilities['match']:
        module.fail_json(msg='match value %s is not supported on this device, valid values are %s' % (match, config_capabilities['match']))

    # check format support
    format = module.params['format']
    if format and format not in supported_format:
        module.fail_json(msg='Invalid configuration format %s, valid values are %s' % (format, supported_format))

    nolog = module.params['nolog']
    candidate = module.params['content']

    commit = not module.check_mode

    # if onbox diff is not supported generate diff between candidate and running configuration
    if not config_capabilities['supports_onbox_diff']:

        # generate diff if supported
        if supports_generate_diff:
            running = connection.get_config(nolog=nolog)
            response = connection.get_diff(candidate=candidate, running=running, match=match, diff_ignore_lines=diff_ignore_lines, replace=replace)
            diff = json.loads(response)
        else:
            # since the device does not provide a diff function, assume
            # the config was changed and set changed to True
            diff = {'config_diff': candidate}
            module.warn('config diff is not supported on this device, '
                        'statically setting changed flag to True')

        if diff:
            commands = diff['config_diff'].split('\n')
            if commit:
                connection.edit_config(commands, nolog=nolog)

            if module._diff:
                result['diff'] = {'prepared': diff}

            result['changed'] = True

    else:

        diff = connection.edit_config(candidate, commit=commit, replace=replace, nolog=nolog)

        if not supports_generate_diff:
            # since the device does not provide a diff function, assume
            # the config was changed and set changed to True
            diff = {'config_diff': candidate}
            module.warn('config diff is not supported on this device, '
                        'statically setting changed flag to True')

        if diff:
            if module._diff:
                result['diff'] = {'prepared': diff}

            result['changed'] = True

    result['history'] = connection.get_history()

    module.exit_json(**result)
