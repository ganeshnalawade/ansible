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

from xml.etree.ElementTree import Element, SubElement

from ansible.plugins.network.netconf.junos import NetworkModule as _NetworkModule

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


class NetworkModule(_NetworkModule):

    def set_hostname(self, element, value):
        subele = SubElement(element, 'host-name')
        subele.text = value

    def set_domain_name(self, element, value):
        subele = SubElement(element, 'domain-name')
        subele.text = value

    def set_name_servers(self, element, values):
        for item in values:
            subele = SubElement(element, 'name-server')
            subele.text = item

    def set_domain_search(self, element, values):
        for item in values:
            subele = SubElement(element, 'domain-search')
            subele.text = item

    def _map_obj_to_element(self, obj):

        element = Element('system')

        for _, key, value, _ in obj[0]:
            if value is not None:
                self.invoke('set_%s' % key, element, value)

        return element



