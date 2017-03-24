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
from xml.etree.ElementTree import Element, SubElement

from ansible.plugins.netconf.junos import NetconfModule as _NetconfModule
from ansible.module_utils.six import with_metaclass

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class NetconfModule(_NetconfModule):

    def _map_obj_to_element(self, obj):
        element = Element('system')

        if obj['hostname']:
            subele = SubElement(element, 'host-name')
            subele.text = obj['hostname']

        if obj['domain_name']:
            subele = SubElement(element, 'domain-name')
            subele.text = obj['domain_name']

        if obj['name_servers']:
            for item in obj['name_servers']:
                subele = SubElement(element, 'name-server')
                subele.text = obj['name_servers']

        if obj['domain_search']:
            for item in obj['domain_search']:
                subele = SubElement(element, 'domain-search')
                subele.text = obj['name_servers']

        return element



