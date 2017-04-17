#
# (c) 2017 Red Hat, Inc.
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
from contextlib import contextmanager

from xml.etree.ElementTree import Element, SubElement

from ansible.module_utils.six import string_types
from ansible.plugins.network import NetworkBase
from ansible.plugins.network.netconf import Netconf
from ansible.errors import AnsibleError

ACTIONS = frozenset(['merge', 'override', 'replace', 'update', 'set'])
JSON_ACTIONS = frozenset(['merge', 'override', 'update'])
FORMATS = frozenset(['xml', 'text', 'json'])
CONFIG_FORMATS = frozenset(['xml', 'text', 'json', 'set'])


class NetworkModule(NetworkBase, Netconf):

    network_connection = 'netconf'
    network_os = 'junos'

    def _map_obj_to_element(self, data):
        raise NotImplementedError

    def load_from_device(self):
        pass

    def load_to_device(self, data):
        # FIXME removed for prototype, should be in final implementation
        #with locked_config(module):

        element = self._map_obj_to_element(data)

        self.load_configuration(element)

        #self.validate()
        diff = self._get_config_diff()

        if diff:
            diff = str(diff).strip()
            if not self._play_context.check_mode:
                self.commit_configuration()
            else:
                self.discard_changes()

        return {'changed': diff is not None}

    def check_state(self, data):
        pass
        # TBD: Check the device is in desired state.
        #raise NotImplementedError

    def _validate_rollback_id(self, value):
        try:
            if not 0 <= int(value) <= 49:
                raise ValueError
        except ValueError:
            raise AnsibleError('rollback must be between 0 and 49')

    def load_configuration(self, candidate=None, action='merge', rollback=None, format='xml'):

        if all((candidate is None, rollback is None)):
            raise AnsibleError('one of candidate or rollback must be specified')

        elif all((candidate is not None, rollback is not None)):
            raise AnsibleError('candidate and rollback are mutually exclusive')

        if format not in FORMATS:
            raise AnsibleError('invalid format specified')

        if format == 'json' and action not in JSON_ACTIONS:
            raise AnsibleError('invalid action for format json')
        elif format in ('text', 'xml') and action not in ACTIONS:
            raise AnsibleError('invalid action format %s' % format)
        if action == 'set' and not format == 'text':
            raise AnsibleError('format must be text when action is set')

        if rollback is not None:
            self._validate_rollback_id(rollback)
            xattrs = {'rollback': str(rollback)}
        else:
            xattrs = {'action': action, 'format': format}

        obj = Element('load-configuration', xattrs)

        if candidate is not None:
            lookup = {'xml': 'configuration', 'text': 'configuration-text',
                    'set': 'configuration-set', 'json': 'configuration-json'}

            if action == 'set':
                cfg = SubElement(obj, 'configuration-set')
            else:
                cfg = SubElement(obj, lookup[format])

            if isinstance(candidate, string_types):
                cfg.text = candidate
            else:
                cfg.append(candidate)

        return self.send_request(obj)

    def get_configuration(self, compare=False, format='xml', rollback='0'):
        if format not in CONFIG_FORMATS:
            raise AnsibleError('invalid config format specified')
        xattrs = {'format': format}
        if compare:
            self._validate_rollback_id(rollback)
            xattrs['compare'] = 'rollback'
            xattrs['rollback'] = str(rollback)
        return self.send_request(Element('get-configuration', xattrs))

    def commit_configuration(self, confirm=False, check=False, comment=None, confirm_timeout=None):
        obj = Element('commit-configuration')
        if confirm:
            SubElement(obj, 'confirmed')
        if check:
            SubElement(obj, 'check')
        if comment:
            subele = SubElement(obj, 'log')
            subele.text = str(comment)
        if confirm_timeout:
            subele = SubElement(obj, 'confirm-timeout')
            subele.text = int(confirm_timeout)
        return self.send_request(obj)

    def command(self, command, format='text', rpc_only=False):
        xattrs = {'format': format}
        if rpc_only:
            command += ' | display xml rpc'
            xattrs['format'] = 'text'
        return self.send_request(Element('command', xattrs, text=command))

    lock_configuration = lambda x: send_request(x, Element('lock-configuration'))
    unlock_configuration = lambda x: send_request(x, Element('unlock-configuration'))

    #@contextmanager
    def locked_config(self):
        try:
            lock_configuration()
            yield
        finally:
            unlock_configuration()

    def _get_config_diff(self):
        reply = self.get_configuration(compare=True, format='text')
        output = reply.find('.//configuration-output')
        if output is not None:
            return output.text
