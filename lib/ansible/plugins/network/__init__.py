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
import sys
import time
import copy

from abc import ABCMeta, abstractmethod

from ansible.plugins import connection_loader
from ansible.module_utils.six import with_metaclass, iteritems
from ansible.utils.path import unfrackpath
from ansible.errors import AnsibleError, AnsibleConnectionFailure

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


DEFAULT_STATE_DELAY = os.getenv('ANSIBLE_NETWORK_DEFAULT_STATE_DELAY', 30)


class NetworkBase(with_metaclass(ABCMeta, object)):

    network_connection = None
    network_os = None

    def __init__(self, play_context):
        self._play_context = play_context
        self._connection = None

    @abstractmethod
    def load_from_device(self):
        pass

    @abstractmethod
    def load_to_device(self, data):
        pass

    @abstractmethod
    def check_state(self, data):
        pass

    def _connect(self):
        pc = copy.deepcopy(self._play_context)

        pc.connection = self.network_connection
        pc.network_os = self.network_os

        pc.remote_addr = self._play_context.remote_addr

        default_port = 830 if self.network_connection == 'netconf' else 22
        pc.port = self._play_context.port or default_port

        pc.remote_user = self._play_context.connection_user

        pc.password = self._play_context.password
        pc.private_key_file = self._play_context.private_key_file

        pc.timeout = self._play_context.timeout

        pc.become = True

        display.vvv('using connection plugin %s' % pc.connection, pc.remote_addr)
        connection = connection_loader.get('persistent', pc, sys.stdin)

        socket_path = self._get_socket_path(pc)
        display.vvvv('socket_path: %s' % socket_path, pc.remote_addr)

        if not os.path.exists(socket_path):
            # start the connection if it isn't started
            if self.network_connection == 'network_cli':
                rc, out, err = connection.exec_command('open_shell()')
            else:
                rc, out, err = connection.exec_command('open_session()')

            if rc != 0:
                raise AnsibleConnectionFailure('unable to open shell. Please see: https://docs.ansible.com/ansible/network_debug_troubleshooting.html#unable-to-open-shell')

        else:
            # called to reset the shell if its in an inconsistent state
            display.vvvv('calling reset_shell() on existing connection', pc.remote_addr)
            rc, out, err = connection.exec_command('reset_shell()')
            if rc != 0:
                raise AnsibleError('error calling reset_shell')

        return connection

    def run(self, data):

        self._connection = self._get_connection()

        if None in (self.network_connection, self.network_os):
            raise AnsibleError('both network_connection and network_os must be defined')

        result = {'changed': False}
        spec = data['spec']

        if 'config' in data:
            updates = self._exec_config(data)
            result.update(self.load_to_device(updates))

        disable_state_checks = os.getenv('ANSIBLE_NETWORK_DISABLE_STATE_CHECKS', False)
        if not disable_state_checks and 'state' in data:
            if result.get('changed'):
                delay = data.get('state_delay') or DEFAULT_STATE_DELAY
                time.sleep(delay)

            response = self.check_state(data)
            result.update(response)

        return result

    def invoke(self, name, *args, **kwargs):
        meth = getattr(self, name, None)
        if meth:
            return meth(*args, **kwargs)

    def _get_socket_path(self, play_context):
        """Returns the persistent socket path"""
        ssh = connection_loader.get('ssh', class_only=True)
        cp = ssh._create_control_path(play_context.remote_addr, play_context.port, play_context.remote_user)
        path = unfrackpath("$HOME/.ansible/pc")
        return cp % dict(directory=path)

