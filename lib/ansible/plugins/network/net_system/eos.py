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

from ansible.plugins.network.eos import NetworkModule as _NetworkModule

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()

class NetworkModule(_NetworkModule):

    ATTRS = frozenset([
        'hostname',
        'domain_name',
        'domain_list',
        'name_servers'
    ])

    def set_hostname(self, current_value, desired_value):
        return 'hostname %s' %  desired_value

    def set_domain_name(self, current_value, desired_value):
        return 'ip domain-name %s' % desired_value

    def set_domain_search(self, current_value, desired_value):
        objects = list()
        for item, action in self.list_diff(current_value, desired_value):
            if action == 'remove':
                objects.append('no ip domain-list %s' % item)
            else:
                objects.append('ip domain-list %s' % item)
        return objects

    def set_name_servers(self, current_value, desired_value):
        objects = list()
        for item, action in self.list_diff(current_value, desired_value):
            if action == 'remove':
                objects.append('no ip name-server %s' % item)
            else:
                objects.append('ip name-server %s' % item)
        return objects

    def get_hostname(self):
        match = re.search('^hostname (\S+)', self.config, re.M)
        if match:
            return match.group(1)

    def get_domain_name(self):
        match = re.search('^ip domain-name (\S+)', self.config, re.M)
        if match:
            return match.group(1)

    def get_domain_search(self):
        objects = list()
        regex = r'^ip domain-list (\S+)'
        for item in re.findall(regex, self.config, re.M):
            objects.append(item)
        return objects

    def get_name_servers(self):
        objects = list()
        regex = r'^ip name-server vrf default (\S+)'
        for item in re.findall(regex, self.config, re.M):
            objects.append(item)
        return objects

    def load_from_device(self):
        obj = {}
        for item in self.ATTRS:
            value = self.invoke('get_%s' % item)
            obj[item] = value
        return obj

