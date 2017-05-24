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
        re.compile(br"\[\w+\@[\w\-\.]+(?: [^\]])\] ?[>#\$] ?$"),
        re.compile(br']]>]]>[\r\n]?')
    ]

    terminal_stderr_re = [
        re.compile(br"% ?Error"),
        re.compile(br"% ?Bad secret"),
        re.compile(br"invalid input", re.I),
        re.compile(br"(?:incomplete|ambiguous) command", re.I),
        re.compile(br"connection timed out", re.I),
        re.compile(br"[^\r\n]+ not found", re.I),
        re.compile(br"'[^']' +returned error code: ?\d+"),
    ]

    def _on_open_shell(self):
        try:
            for cmd in (b'terminal length 0', b'terminal width 512', b'terminal exec prompt no-timestamp'):
                self.send_command(cmd)
        except AnsibleConnectionFailure:
            raise AnsibleConnectionFailure('unable to set terminal parameters')

    def get_device_info(self):
        device_info = {}

        device_info['network_os'] = 'iosxr'
        reply = self.get('show version brief')
        data = to_text(reply, errors='surrogate_or_strict').strip()

        match = re.search(r'Version (\S+)$', data, re.M)
        if match:
            device_info['network_os_version'] = match.group(1)

        match = re.search(r'image file is "(.+)"', data)
        if match:
            device_info['network_os_image'] = match.group(1)

        match = re.search(r'^Cisco (.+) \(revision', data, re.M)
        if match:
            device_info['network_os_model'] = match.group(1)

        match = re.search(r'^(.+) uptime', data, re.M)
        if match:
            device_info['network_hostname'] = match.group(1)

        return device_info

    @enable_mode
    def get_config(self, source='running'):
        lookup = {u'running': u'running-config'}
        return self.send_command(to_bytes('show %s' % lookup[source], errors='surrogate_or_strict'))


    @enable_mode
    def edit_config(self, commands):
        for command in chain([u'configure terminal'], to_list(commands), [u'end']):
            self.send_command(to_bytes(command, errors='surrogate_or_strict'))

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
        self.send_command(to_bytes('abort', errors='surrogate_or_strict'))

    def get_capabilities(self):
        result = {}
        base_rpc = self.get_supported_rpc()
        result[u'rpc'] = base_rpc.extend(['commit', 'discard_changes'])
        result[u'network_api'] = u'cliconf'
        result[u'device_info'] = self.get_device_info()
        return json.dumps(result)
