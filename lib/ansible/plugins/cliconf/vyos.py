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

import os
import re
import json

from itertools import chain

from ansible.errors import AnsibleConnectionFailure
from ansible.module_utils._text import to_bytes, to_text
from ansible.module_utils.network_common import to_list
from ansible.plugins.cliconf import CliconfBase, enable_mode


class Cliconf(CliconfBase):

    terminal_stdout_re = [
        re.compile(br"[\r\n]?[\w+\-\.:\/\[\]]+(?:\([^\)]+\)){,3}(?:>|#) ?$"),
        re.compile(br"\@[\w\-\.]+:\S+?[>#\$] ?$")
    ]

    terminal_stderr_re = [
        re.compile(br"\n\s*Invalid command:"),
        re.compile(br"\nCommit failed"),
        re.compile(br"\n\s+Set failed"),
    ]

    terminal_length = os.getenv('ANSIBLE_VYOS_TERMINAL_LENGTH', 10000)

    def _on_open_shell(self):
        try:
            for cmd in (b'set terminal length 0', b'set terminal width 512'):
                self._exec_cli_command(cmd)
            self._exec_cli_command(b'set terminal length %d' % self.terminal_length)
        except AnsibleConnectionFailure:
            raise AnsibleConnectionFailure('unable to set terminal parameters')

    def get_device_info(self):
        device_info = {}

        device_info['network_os'] = 'vyos'
        reply = self.get('show version')
        data = to_text(reply, errors='surrogate_or_strict').strip()

        match = re.search(r'Version:\s*(\S+)', data)
        if match:
            device_info['network_os_version'] = match.group(1)

        match = re.search(r'HW model:\s*(\S+)', data)
        if match:
            device_info['network_os_model'] = match.group(1)

        reply = self.get('show host name')
        device_info['network_hostname'] = to_text(reply, errors='surrogate_or_strict').strip()

        return device_info

    def get_config(self):
        return self.send_command('show configuration all')

    def edit_config(self, commands):
        for command in chain(['configure'], to_list(commands)):
            self.send_command(command)

    def get(self, *args, **kwargs):
        return self.send_command(*args, **kwargs)

    def commit(self, *args, **kwargs):
        comment = kwargs.get('comment')
        if comment:
            command = 'commit {0}'.format(comment)
        else:
            command = 'commit'
        self.send_command(to_bytes(command, errors='surrogate_or_strict'))

    def discard_changes(self, *args, **kwargs):
        self.send_command(to_bytes('discard', errors='surrogate_or_strict'))

    def get_capabilities(self):
        result = {}
        base_rpc = self.get_supported_rpc()
        result[u'rpc'] = base_rpc.extend(['commit', 'discard_changes'])
        result['network_api'] = 'cliconf'
        result['device_info'] = self.get_device_info()
        return json.dumps(result)
