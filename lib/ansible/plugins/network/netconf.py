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
import sys
import copy

from contextlib import contextmanager
from xml.etree.ElementTree import Element, SubElement
from xml.etree.ElementTree import tostring, fromstring

from ansible.plugins import connection_loader
from ansible.errors import AnsibleError

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


NS_MAP = {'nc': "urn:ietf:params:xml:ns:netconf:base:1.0"}


class Netconf:

    def _create_connection(self, play_context):
        pc = copy.deepcopy(self._play_context)
        pc.network_os = 'junos'
        pc.connection = 'netconf'

        pc.remote_addr = self._play_context.remote_addr
        pc.port = self._play_context.port or 830
        pc.remote_user = self._play_context.connection_user
        pc.password = self._play_context.password
        pc.private_key_file = self._play_context.private_key_file
        pc.timeout = self._play_context.timeout

        display.vvv('using connection plugin %s' % pc.connection, pc.remote_addr)
        connection = connection_loader.get('persistent', pc, sys.stdin)

        socket_path = self._get_socket_path(pc)
        display.vvvv('socket_path: %s' % socket_path, pc.remote_addr)

        if not os.path.exists(socket_path):
            # start the connection if it isn't started
            rc, out, err = connection.exec_command('open_session()')
            if rc != 0:
                return {'failed': True,
                        'msg': 'unable to open shell. Please see: ' +
                               'https://docs.ansible.com/ansible/network_debug_troubleshooting.html#unable-to-open-shell',
                        'rc': rc}

        return connection


    def send_request(self, obj, check_rc=True):
        request = tostring(obj)
        rc, out, err = self._connection.exec_command(request)
        if rc != 0 and check_rc:
            error_root = fromstring(err)
            fake_parent = Element('root')
            fake_parent.append(error_root)

            error_list = fake_parent.findall('.//nc:rpc-error', NS_MAP)
            if not error_list:
                module.fail_json(msg=str(err))

            warnings = []
            for rpc_error in error_list:
                message = rpc_error.find('./nc:error-message', NS_MAP).text
                severity = rpc_error.find('./nc:error-severity', NS_MAP).text

                if severity == 'warning':
                    warnings.append(message)
                else:
                    module.fail_json(msg=str(err))
            return warnings
        return fromstring(out)

    def children(root, iterable):
        for item in iterable:
            try:
                ele = SubElement(ele, item)
            except NameError:
                ele = SubElement(root, item)

    def lock(self, target='candidate'):
        obj = Element('lock')
        self.children(obj, ('target', target))
        return self.send_request(obj)

    def unlock(self, target='candidate'):
        obj = Element('unlock')
        self.children(obj, ('target', target))
        return self.send_request(obj)

    def commit(self):
        return self.send_request(Element('commit'))

    def discard_changes(self):
        return self.send_request(Element('discard-changes'))

    def validate(self):
        obj = Element('validate')
        self.children(obj, ('source', 'candidate'))
        return self.send_request(obj)

    def get_config(self, source='running', filter=None):
        obj = Element('get-config')
        self.children(obj, ('source', source))
        self.children(obj, ('filter', filter))
        return self.send_request(obj)

    @contextmanager
    def locked_config(self):
        try:
            self.lock()
            yield
        finally:
            self.unlock()
