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

import sys
import os
import re
import copy

from abc import ABCMeta, abstractmethod

from ansible.module_utils.six import with_metaclass
from ansible.plugins.provider import ProviderBase
from ansible.plugins import PluginLoader, connection_loader
from ansible.errors import AnsibleConnectionFailure

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class ProviderModule(ProviderBase):

    network_os = 'eos'

    def create_connection(self, data):
        pc = copy.deepcopy(self._play_context)
        pc.connection = 'network_cli'
        pc.remote_user = self._play_context.connection_user
        pc.become = True

        self._connection = connection_loader.get('persistent', pc, sys.stdin)

        self.socket_path = self._get_socket_path(pc)
        display.vvvv('socket_path: %s' % self.socket_path, pc.remote_addr)

        if not os.path.exists(self.socket_path):
            # start the connection if it isn't started
            display.vvvv('calling open_shell()', pc.remote_addr)
            rc, out, err = self._connection.exec_command('open_shell()')
            if not rc == 0:
                raise AnsibleConnectionFailure('unable to open shell')
        else:
            display.vvvv('reuse existing control connection', pc.remote_addr)
            # make sure we are in the right cli context which should be
            # enable mode and not config module
            rc, out, err = self._connection.exec_command('prompt()')
            while str(out).strip().endswith(')#'):
                display.vvvv('wrong context, sending exit to device', self._play_context.remote_addr)
                self._connection.exec_command('exit')
                rc, out, err = self._connection.exec_command('prompt()')
