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

from abc import ABCMeta, abstractmethod

from ansible.plugins import PluginLoader, connection_loader
from ansible.module_utils.six import with_metaclass
from ansible.utils.path import unfrackpath



class ProviderBase(with_metaclass(ABCMeta, object)):

    def __init__(self, play_context):
        self._play_context = play_context
        self._connection = None

    @abstractmethod
    def create_connection(self):
        """Loads and starts the connection plugin"""
        pass

    def run(self, data):
        result = {}

        self.create_connection(data)

        plugin = data['plugin']
        action = data['action']

        namespace = 'ansible.plugins.%s.%s' % (plugin, action)
        plugin_path = '%s_plugins/%s' % (plugin, action)

        loader = PluginLoader('NetworkModule', namespace, plugin_path, plugin_path)
        module = loader.get(self._play_context.network_os, self._play_context, self._connection)

        if 'config' in data:
            result.update(module.exec_config(data))

        if 'state' in data:
            if result.get('changed'):
                delay = data.get('state_delay') or 10
                time.sleep(delay)
            result.update(module.exec_state(data))

        if 'facts' in data:
            result.update(module.exec_facts(data))

        return result

    def _get_socket_path(self, play_context):
        """Returns the persistent socket path"""
        ssh = connection_loader.get('ssh', class_only=True)
        cp = ssh._create_control_path(play_context.remote_addr, play_context.port, play_context.remote_user)
        path = unfrackpath("$HOME/.ansible/pc")
        return cp % dict(directory=path)


