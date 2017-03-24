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

from ansible.module_utils.six import with_metaclass, iteritems
from ansible.module_utils.network_common import to_list


class NetworkBase(with_metaclass(ABCMeta, object)):

    def __init__(self, play_context, connection):
        self._play_context = play_context
        self._connection = connection

    def exec_config(self, data):
        spec = data['spec']

        current = to_list(self.get())
        key = next((k for k, v in iteritems(spec) if v.get('key')), None)

        result = {'changed': False}
        updates = list()

        for config in to_list(data['config']):
            item = next((i for i in current if i.get(key) == config.get(key)), None)
            item = self.json_diff((item or current[0]), config)
            updates.append(item)

        result.update(self.set(updates))
        return result

    def exec_state(self, data):
        result =  {}
        #response = self.check(data)
        #result.update(response)
        return result

    def sort(self, val):
        if isinstance(val, list):
            return sorted(val)
        return val

    def invoke(self, name, *args, **kwargs):
        meth = getattr(self, name, None)
        if meth:
            return meth(*args, **kwargs)

    def json_diff(self, current, desired, path=None):
        """Diff two data structures and return updated keys

        This will diff to dict objects and return a list of objects that
        represent the updates.  The list of updates is in the form of
        (path, key, current_value, desired_value)
        """
        updates = list()
        path = path or list()

        for key, value in iteritems(current):
            if key not in desired:
                desired_value = desired.get(key)
                updates.append((list(path), key, value, desired_value))
            else:
                if isinstance(current[key], dict):
                    path.append(key)
                    updates.extend(self.json_diff(current[key], desired[key], list(path)))
                    path.pop()
                else:
                    desired_value = desired.get(key)
                    if desired_value is not None:
                        if self.sort(current[key]) != self.sort(desired_value):
                            updates.append((list(path), key, value, desired_value))

        return updates

    def list_diff(self, current, desired):
        objects = list()
        for item in set(current).difference(desired):
            objects.append((item, 'remove'))
        for item in set(desired).difference(current):
            objects.append((item, 'add'))
        return objects





