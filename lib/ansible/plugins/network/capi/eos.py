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
import time

from ansible.plugins.network.capi import NetworkModule as _NetworkModule
from ansible.module_utils.network_common import to_list
from ansible.errors import AnsibleError


try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

class NetworkModule(_NetworkModule):

    network_connection = 'network_cli'
    network_os = 'eos'

    def __init__(self, *args, **kwargs):
        super(NetworkModule, self).__init__(*args, **kwargs)
        self.cache = {}

    @property
    def config(self):
        if 'config' in self.cache:
            return self.cache['config']
        rc, out, err = self.send_command('show running-config')
        self.cache['config'] = str(out).strip()
        return str(out).strip()

    def load_from_device(self):
        raise NotImplementedError

    def load_to_device(self, data):
        commands = list()

        for item in data:
            for (path, key, current_value, desired_value) in item:
                value = self.invoke('set_%s' % key, current_value, desired_value)
                if value:
                    if isinstance(value, list):
                        commands.extend(value)
                    else:
                        commands.append(value)

        result = {'changed': False}

        if not self.check_authorization():
            raise AnsibleError('configuration operations require privilege escalation')

        use_session = os.getenv('ANSIBLE_EOS_USE_SESSIONS', True)
        try:
            use_session = int(use_session)
        except ValueError:
            pass

        if not all((bool(use_session), self.supports_sessions())):
            return self.configure(commands)

        return self.configure_session(commands)

    def check_state(self, data):
        raise NotImplementedError

    def check_authorization(self):
        for cmd in ['show clock', 'prompt()']:
            rc, out, err = self.send_command(cmd)
        return out.endswith('#')

    def supports_sessions(self):
        rc, out, err = self.send_command('show configuration sessions')
        return rc == 0

    def send_config(self, commands):
        multiline = False
        rc = 0
        for command in to_list(commands):
            if command == 'end':
                pass

            if command.startswith('banner') or multiline:
                multiline = True
                command = self._module.jsonify({'command': command, 'sendonly': True})
            elif command == 'EOF' and multiline:
                multiline = False

            rc, out, err = self.send_command(command)
            if rc != 0:
                raise AnsibleError(err)

    def configure(self, commands):
        if not self._play_context.check_mode and commands:
            rc, out, err = self.send_command('configure')
            if rc != 0:
                raise AnsibleError('unable to enter configuration mode', output=err)
            self.send_config(commands)
            self.send_command('end')

        return {
            'changed': len(commands) > 0,
            'commands': commands
        }

    def configure_session(self, commands):
        session = 'ansible_%s' % int(time.time())
        display.vvv('eos configuration session id %s' % session, self._connection._play_context.remote_addr)

        result = {'changed': False, 'commands': commands}

        rc, out, err = self.send_command('configure session %s' % session)
        if rc != 0:
            raise AnsibleError(str(err))

        try:
            self.send_config(commands)
        except AnsibleError:
            self.send_command('abort')
            raise

        rc, out, err = self.send_command('show session-config diffs')
        if rc == 0 and out:
            result['diff'] = {'prepared': out.strip()}
            result['changed'] = True

        if not self._play_context.check_mode:
            self.send_command('commit')
        else:
            self.send_command('abort')

        return result
