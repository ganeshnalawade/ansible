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
import time

from itertools import chain

from ansible.errors import AnsibleConnectionFailure
from ansible.module_utils._text import to_bytes, to_text
from ansible.module_utils.network_common import to_list
from ansible.plugins.cliconf import CliconfBase, enable_mode

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

class Cliconf(CliconfBase):

    terminal_stdout_re = [
        re.compile(br"[\r\n]?[\w+\-\.:\/\[\]]+(?:\([^\)]+\)){,3}(?:>|#) ?$"),
        re.compile(br"\[\w+\@[\w\-\.]+(?: [^\]])\] ?[>#\$] ?$")
    ]

    terminal_stderr_re = [
        re.compile(br"% ?Error"),
        # re.compile(br"^% \w+", re.M),
        re.compile(br"% ?Bad secret"),
        re.compile(br"invalid input", re.I),
        re.compile(br"(?:incomplete|ambiguous) command", re.I),
        re.compile(br"connection timed out", re.I),
        re.compile(br"[^\r\n]+ not found", re.I),
        re.compile(br"'[^']' +returned error code: ?\d+"),
    ]

    def get_device_info(self):
        device_info = {}

        device_info['network_os'] = 'ios'
        reply = self.get('show version')
        display.display("-- type(reply) -- %s" % type(reply), log_only=True)
        display.display("-- reply -- %s" % reply, log_only=True)
        data = to_text(reply, errors='surrogate_or_strict').strip()
        display.display("-- type(data) -- %s" % type(data), log_only=True)
        match = re.search(r'Version (\S+),', data)
        if match:
            device_info['network_os_version'] = match.group(1)

        match = re.search(r'^Cisco (.+) \(revision', data, re.M)
        if match:
            device_info['network_os_model'] = match.group(1)

        match = re.search(r'^(.+) uptime', data, re.M)
        if match:
            device_info['network_hostname'] = match.group(1)

        return device_info

    def _on_open_shell(self):
        display.display("-- _on_open_shell --")
        if not self._terminal_init_complete:
            try:
                for cmd in [b'terminal length 0', b'terminal width 512']:
                    self.send_command(cmd)
            except AnsibleConnectionFailure:
                raise AnsibleConnectionFailure('unable to set cliconf parameters')

    def _on_authorize(self, passwd=None):
        if self._get_prompt().endswith(b'#'):
            return

        cmd = {u'command': u'enable'}
        if passwd:
            # Note: python-3.5 cannot combine u"" and r"" together.  Thus make
            # an r string and use to_text to ensure it's text on both py2 and py3.
            cmd[u'prompt'] = to_text(r"[\r\n]?password: $", errors='surrogate_or_strict')
            cmd[u'answer'] = passwd

        try:
            self.send_command(to_bytes(json.dumps(cmd), errors='surrogate_or_strict'))
        except AnsibleConnectionFailure:
            raise AnsibleConnectionFailure('unable to elevate privilege to enable mode')

    def _on_deauthorize(self):
        prompt = self._get_prompt()
        if prompt is None:
            # if prompt is None most likely the cliconf is hung up at a prompt
            return

        if b'(config' in prompt:
            self.send_command(b'end')
            self.send_command(b'disable')

        elif prompt.endswith(b'#'):
            self.send_command(b'disable')

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

    @staticmethod
    def guess_network_os(channel):
        for cmd in [b'terminal length 0', b'terminal width 512', b'show version']:
            channel.send('%s\r' % cmd)

        # FIXME need to think this through more
        time.sleep(3)
        output = channel.recv(2048)
        if 'Cisco IOS Software' in output:
            return 'ios'
