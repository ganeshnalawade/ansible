#
# (c) 2016 Red Hat Inc.
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
import sys
import copy

from ansible.plugins import network_loader
from ansible.plugins.action.normal import ActionModule as _ActionModule
from ansible.errors import AnsibleError

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class ActionModule(_ActionModule):

    def run(self, tmp=None, task_vars=None):
        if self._play_context.connection != 'local':
            return dict(
                failed=True,
                msg='invalid connection specified, expected connection=local, '
                    'got %s' % self._play_context.connection
            )

        try:
            network = network_loader.get(self._play_context.network_os, self._play_context)
            if not network:
                return {'failed': True, 'msg': 'network_os %s is not supported' % self._play_context.network_os}
        except AnsibleError as exc:
            return {'failed': True, 'msg': str(exc)}

        result = super(ActionModule, self).run(tmp, task_vars)

        request = {
            'spec': result['spec'],
            'config': result['config'],
            'resource': self._task.action
        }

        response = network.run(request)

        if 'diff' in result and not self._play_context.diff:
            del response['diff']

        return response
