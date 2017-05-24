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
from ansible.module_utils._text import to_bytes, to_text
from ansible.module_utils.network_common import to_list
from ansible.plugins.cliconf import CliconfBase, enable_mode


class Cliconf(CliconfBase):

    terminal_stdout_re = [
        re.compile(br"[\r\n]?[\w+\-\.:\/\[\]]+(?:\([^\)]+\)){,3}(?:>|#) ?$"),
        re.compile(br"\[\w+\@[\w\-\.]+(?: [^\]])\] ?[>#\$] ?$")
    ]

    terminal_stderr_re = [
        re.compile(br"% ?Error"),
        # re.compile(br"^% \w+", re.M),
        re.compile(br"% User not present"),
        re.compile(br"% ?Bad secret"),
        re.compile(br"invalid input", re.I),
        re.compile(br"(?:incomplete|ambiguous) command", re.I),
        re.compile(br"connection timed out", re.I),
        re.compile(br"[^\r\n]+ not found", re.I),
        re.compile(br"'[^']' +returned error code: ?\d+"),
        re.compile(br"[^\r\n]\/bin\/(?:ba)?sh")
    ]

    def _on_open_shell(self):
        try:
            for cmd in (b'terminal length 0', b'terminal width 512'):
                self.send_command(cmd)
        except AnsibleConnectionFailure:
            raise AnsibleConnectionFailure('unable to set terminal parameters')

    def _on_authorize(self, passwd=None):
        if self._get_prompt().endswith(b'#'):
            return

        cmd = {u'command': u'enable'}
        if passwd:
            cmd[u'prompt'] = to_text(r"[\r\n]?password: $", errors='surrogate_or_strict')
            cmd[u'answer'] = passwd

        try:
            self.send_command(to_bytes(json.dumps(cmd), errors='surrogate_or_strict'))
        except AnsibleConnectionFailure:
            raise AnsibleConnectionFailure('unable to elevate privilege to enable mode')

    def _on_deauthorize(self):
        prompt = self._get_prompt()
        if prompt is None:
            # if prompt is None most likely the terminal is hung up at a prompt
            return

        if b'(config' in prompt:
            self.send_command(b'end')
            self.send_command(b'disable')

        elif prompt.endswith(b'#'):
            self.send_command(b'disable')

    def get_device_info(self):
        device_info = {}

        device_info['network_os'] = 'eos'
        reply = self.get('show version | json')
        data = json.loads(reply)

        device_info['network_os_version'] = data['version']
        device_info['network_os_model'] = data['modelName']

        reply = self.get('show hostname | json')
        data = json.loads(reply)

        device_info['network_hostname'] = data['hostname']

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
