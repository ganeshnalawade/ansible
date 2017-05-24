#
# (c) 2017 Red Hat Inc.
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
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import re
import json

from itertools import chain

from ansible.errors import AnsibleConnectionFailure
from ansible.module_utils.network_common import to_list
from ansible.plugins.cliconf import CliconfBase, enable_mode


class Cliconf(CliconfBase):

    terminal_stdout_re = [
        re.compile(br'[\r\n]?[a-zA-Z]{1}[a-zA-Z0-9-]*[>|#|%](?:\s*)$'),
        re.compile(br'[\r\n]?[a-zA-Z]{1}[a-zA-Z0-9-]*\(.+\)#(?:\s*)$')
    ]

    terminal_stderr_re = [
        re.compile(br"% ?Error"),
        re.compile(br"^% \w+", re.M),
        re.compile(br"% ?Bad secret"),
        re.compile(br"invalid input", re.I),
        re.compile(br"(?:incomplete|ambiguous) command", re.I),
        re.compile(br"connection timed out", re.I),
        re.compile(br"[^\r\n]+ not found", re.I),
        re.compile(br"'[^']' +returned error code: ?\d+"),
        re.compile(br"syntax error"),
        re.compile(br"unknown command"),
        re.compile(br"user not present")
    ]

    def _on_open_shell(self):
        try:
            for cmd in (b'terminal length 0', b'terminal width 511'):
                self.send_command(cmd)
        except AnsibleConnectionFailure:
            raise AnsibleConnectionFailure('unable to set terminal parameters')

    def get_device_info(self):
        device_info = {}

        device_info['network_os'] = 'nxos'
        reply = self.get('show version | json')
        data = json.loads(reply)

        device_info['network_os_version'] = data['sys_ver_str']
        device_info['network_os_model'] = data['chassis_id']
        device_info['network_hostname'] = data['host_name']
        device_info['network_os_image'] = data['isan_file_name']

        return device_info


    @enable_mode
    def get_config(self, source='running'):
        lookup = {'running': 'running-config', 'startup': 'startup-config'}
        return self.send_command('show %s' % lookup[source])


    @enable_mode
    def edit_config(self, commands):
        for command in chain(['configure'], to_list(commands), ['end']):
            self.send_command(command)

    def get(self, *args, **kwargs):
        return self.send_command(*args, **kwargs)

    def get_capabilities(self):
        result = {}
        result['rpc'] = self.get_supported_rpc()
        result['network_api'] = 'cliconf'
        result['device_info'] = self.get_device_info()
        return json.dumps(result)
