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

import signal

from abc import ABCMeta, abstractmethod
from functools import wraps

from ansible.errors import AnsibleError, AnsibleConnectionFailure
from ansible.module_utils._text import to_bytes, to_text
from ansible.module_utils.six import with_metaclass

try:
    from scp import SCPClient
    HAS_SCP = True
except ImportError:
    HAS_SCP = False

try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


def enable_mode(func):
    @wraps(func)
    def wrapped(self, *args, **kwargs):
        prompt = self._connection.get_prompt()
        if not to_text(prompt, errors='surrogate_or_strict').strip().endswith('#'):
            raise AnsibleError('operation requires privilege escalation')
        return func(self, *args, **kwargs)
    return wrapped


class CliconfBase(with_metaclass(ABCMeta, object)):
    """
    A base class for implementing cli connections

    .. note:: String inputs to :meth:`send_command` will be cast to byte strings
         within this method and as such are not required to be made byte strings
         beforehand.  Please avoid using literal byte strings (``b'string'``) in
         :class:`CliConfBase` plugins as this can lead to unexpected errors when
         running on Python 3

    List of supported rpc's:
        :get_config: Retrieves the specified configuration from the device
        :edit_config: Loads the specified commands into the remote device
        :get: Execute specified command on remote device
        :get_capabilities: Retrieves device information and supported rpc methods
        :commit: Load configuration from candidate to running
        :discard_changes: Discard changes to candidate datastore

    Note: List of supported rpc's for remote device can be extracted from
          output of get_capabilities()

    :returns: Returns output received from remote device as byte string

            Usage:
            from ansible.module_utils.connection import Connection

            conn = Connection()
            conn.get('show lldp neighbors detail'')
            conn.get_config('running')
            conn.edit_config(['hostname test', 'netconf ssh'])
    """

    def __init__(self, connection):
        self._connection = connection
        self.history = list()

    def _alarm_handler(self, signum, frame):
        """Alarm handler raised in case of command timeout """
        display.display('closing shell due to command timeout (%s seconds).' % self._connection._play_context.timeout, log_only=True)
        self.close()

    def send_command(self, command, prompt=None, answer=None, sendonly=False, newline=True, prompt_retry_check=False, nolog=True):
        """Executes a cli command and returns the results
        This method will execute the CLI command on the connection and return
        the results to the caller.  The command output will be returned as a
        string
        """
        kwargs = {'command': to_bytes(command), 'sendonly': sendonly,
                  'newline': newline, 'prompt_retry_check': prompt_retry_check}

        if nolog not in (True, False):
            nolog = True

        if prompt is not None:
            kwargs['prompt'] = to_bytes(prompt)
        if answer is not None:
            kwargs['answer'] = to_bytes(answer)

        resp = self._connection.send(**kwargs)

        if nolog:
            self.history.append((kwargs['command'], '*****'))
        else:
            self.history.append((kwargs['command'], resp))
        return resp

    def get_base_rpc(self):
        """Returns list of base rpc method supported by remote device"""
        return ['get_config', 'edit_config', 'get_capabilities', 'get']

    @abstractmethod
    def get_config(self, source='running', format='text'):
        """Retrieves the specified configuration from the device
        This method will retrieve the configuration specified by source and
        return it to the caller as a string.  Subsequent calls to this method
        will retrieve a new configuration from the device
        :args:
            arg[0] source: Datastore from which configuration should be retrieved eg: running/candidate/startup. (optional)
                           default is running.
            arg[1] format: Output format in which configuration is retrieved
                           Note: Specified datastore should be supported by remote device.
        :kwargs:
          Keywords supported
            :command: the command string to execute
            :source: Datastore from which configuration should be retrieved
            :format: Output format in which configuration is retrieved
        :returns: Returns output received from remote device as byte string
        """
        pass

    @abstractmethod
    def edit_config(self, candidate, replace=False, commit=False, format='text', nolog=True):
        """
        Edit the configuration on the remote device.
        :param candidate: The device configuration as a string to apply on remote host
        :param replace: Boolean flag to indicate if the running configuration should be entirely
                        replaced by candidate configuration.
        :param commit: Bool flag to indicate if the check mode is enabled or not
        :param format: Format of the candidate configuration
        :param nolog: Boolean value to indicate response received from remote host should be logged
                      or not.
        :return: Response received for remote host in string format
        """
        pass

    @abstractmethod
    def get(self, command=None, prompt=None, answer=None, sendonly=False, newline=True):
        """Execute specified command on remote device
        This method will retrieve the specified data and
        return it to the caller as a string.
        :args:
             command: command in string format to be executed on remote device
             prompt: the expected prompt generated by executing command.
                            This can be a string or a list of strings (optional)
             answer: the string to respond to the prompt with (optional)
             sendonly: bool to disable waiting for response, default is false (optional)
        :returns: Returns output received from remote device as byte string
        """
        pass

    @abstractmethod
    def get_capabilities(self):
        """Retrieves device information, supported
        rpc methods and device capabilities supported by the network platform and return result
        as a string.
        :returns: Returns output received from remote device as byte string
        eg:
            {

                'rpc': ['get_config', 'edit_config', 'get_capabilities', 'get', 'commit'],
                'network_api': 'cliconf',
                'device_info': {
                    'network_os': '',
                    'network_os_version': '',
                    'network_os_model': '',
                    'network_os_hostname': '',
                    'network_os_image': '',
                    'network_os_platform': '',
                },
                'config_capability': {
                    'format': ['text', 'json', 'xml', 'set'], # format of configuration supported on given platform
                    'match': ['line', 'strict', 'exact', 'none'],
                    'supports_replace': True/False,            # Boolean value to identify if config should be merged or replaced
                    'supports_commit': True/False,             # Boolean value to identify if commit is supported by device or not
                    'supports_rollback': True/False,           # Boolean value to identify if rollback is supported or not
                    'supports_defaults': True/False,           # Boolean value to identify if fetching running config with default is supported
                    'supports_commit_comment': True/False,     # Boolean value to identify if adding comment to commit is supported of not
                    'supports_diff: True/False,                # Boolean value to identify if on box diff capability is supported or not
                    'supports_sessions: True/False,            # Boolean value to identify if sessions is supported or not
                }
            }

        """
        pass

    def commit(self, comment=None):
        """Commit configuration changes"""
        return self._connection.method_not_found("commit is not supported by network_os %s" % self._play_context.network_os)

    def discard_changes(self):
        "Discard changes in candidate datastore"
        return self._connection.method_not_found("discard_changes is not supported by network_os %s" % self._play_context.network_os)

    def copy_file(self, source=None, destination=None, proto='scp'):
        """Copies file over scp/sftp to remote device"""
        ssh = self._connection.paramiko_conn._connect_uncached()
        if proto == 'scp':
            if not HAS_SCP:
                self._connection.internal_error("Required library scp is not installed.  Please install it using `pip install scp`")
            with SCPClient(ssh.get_transport()) as scp:
                scp.put(source, destination)
        elif proto == 'sftp':
            with ssh.open_sftp() as sftp:
                sftp.put(source, destination)

    def get_file(self, source=None, destination=None, proto='scp'):
        """Fetch file over scp/sftp from remote device"""
        ssh = self._connection.paramiko_conn._connect_uncached()
        if proto == 'scp':
            if not HAS_SCP:
                self._connection.internal_error("Required library scp is not installed.  Please install it using `pip install scp`")
            with SCPClient(ssh.get_transport()) as scp:
                scp.get(source, destination)
        elif proto == 'sftp':
            with ssh.open_sftp() as sftp:
                sftp.get(source, destination)
