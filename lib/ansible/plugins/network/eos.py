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
import os
import time

from abc import abstractmethod

from ansible.plugins.network import NetworkBase
from ansible.module_utils.six import iteritems
from ansible.module_utils.network_common import to_list
from ansible.errors import AnsibleError


try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

class NetworkModule(NetworkBase):

    def __init__(self, *args, **kwargs):
        super(NetworkModule, self).__init__(*args, **kwargs)
        self.cache = {}

    @property
    def config(self):
        if 'config' in self.cache:
            return self.cache['config']
        rc, out, err = self.exec_command('show running-config')
        self.cache['config'] = str(out).strip()
        return str(out).strip()

    @abstractmethod
    def load_from_device(self):
        pass

    def get(self):
        objects = self.load_from_device()
        return to_list(objects)

    def set(self, data):
        commands = self.to_commands(data)
        return {'changed': False, 'commands': commands}
        #return self.load_to_device(commands)

    def to_commands(self, data):
        commands = list()
        for item in data:
            for (path, key, current_value, desired_value) in item:
                value = self.invoke('set_%s' % key, current_value, desired_value)
                if value:
                    if isinstance(value, list):
                        commands.extend(value)
                    else:
                        commands.append(value)
        return commands

    def exec_command(self, command):
        if isinstance(command, dict):
            command = self._module.jsonify(command)
        return self._connection.exec_command(command)

    def check_authorization(self):
        for cmd in ['show clock', 'prompt()']:
            rc, out, err = self.exec_command(cmd)
        return out.endswith('#')

    def supports_sessions(self):
        rc, out, err = self.exec_command('show configuration sessions')
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

            rc, out, err = self.exec_command(command)
            if rc != 0:
                raise AnsibleError(err)

    def configure(self, commands):
        if not self._play_context.check_mode:
            rc, out, err = self.exec_command('configure')
            if rc != 0:
                raise AnsibleError('unable to enter configuration mode', output=err)
            self.send_config(commands)
            self.exec_command('end')
        return {'commands': commands}

    def configure_session(self, commands):
        session = 'ansible_%s' % int(time.time())
        display.vvv('eos configuration session id %s' % session, self._connection._play_context.remote_addr)

        result = {'commands': commands}

        rc, out, err = self.exec_command('configure session %s' % session)
        if rc != 0:
            raise AnsibleError(str(err))

        try:
            self.send_config(commands)
        except AnsibleError:
            self.exec_command('abort')
            raise

        rc, out, err = self.exec_command('show session-config diffs')
        if rc == 0 and out:
            result['diff'] = {'prepared': out.strip()}
            result['changed'] = True

        if not self._play_context.check_mode:
            self.exec_command('commit')
        else:
            self.exec_command('abort')

        return result

    def load_config(self, request):
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


