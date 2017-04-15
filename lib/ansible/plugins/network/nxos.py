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
import sys
import time
import copy

from abc import abstractmethod

from ansible.plugins import connection_loader
from ansible.plugins.network import NetworkBase
from ansible.plugins.network.cli import Cli
from ansible.module_utils.six import iteritems
from ansible.module_utils.network_common import to_list
from ansible.errors import AnsibleError


try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

class NetworkModule(NetworkBase):

    network_connection = 'network_cli'
    network_os = 'nxos'

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

    def load_from_device(self):
        raise NotImplementedError

    def load_to_device(self, data):
        commands = self.to_commands(data)

        result = {'changed': False}

        if commands:
            result['changed'] = True
            result['commands']  = commands

        if self._play_context.check_mode:
            return result

        rc, out, err = self.exec_command('configure')
        if rc != 0:
            self._module.fail_json(msg='unable to enter configuration mode', output=err)

        for cmd in config:
            rc, out, err = self.exec_command(cmd)
            if rc != 0:
                self._module.fail_json(msg=err)

        self.exec_command('end')

    def check_state(self, data):
        raise NotImplementedError

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


