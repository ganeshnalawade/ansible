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

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import os
import sys
import json
import socket
import struct
import signal
import traceback
import datetime
import fcntl
import time

from abc import ABCMeta, abstractmethod, abstractproperty
from functools import partial

from ansible import constants as C
from ansible.plugins import connection_loader
from ansible.plugins import PluginLoader
from ansible.module_utils.connection import send_data, recv_data
from ansible.module_utils.six import with_metaclass, iteritems
from ansible.module_utils._text import to_bytes, to_native
from ansible.utils.path import unfrackpath, makedirs_safe
from ansible.errors import AnsibleConnectionFailure
from ansible.utils.display import Display


try:
    from __main__ import display
except ImportError:
    from ansible.utils.display import Display
    display = Display()


def do_fork():
    '''
    Does the required double fork for a daemon process. Based on
    http://code.activestate.com/recipes/66012-fork-a-daemon-process-on-unix/
    '''
    try:
        pid = os.fork()
        if pid > 0:
            return pid

        #os.chdir("/")
        os.setsid()
        os.umask(0)

        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)

            if C.DEFAULT_LOG_PATH != '':
                out_file = file(C.DEFAULT_LOG_PATH, 'a+')
                err_file = file(C.DEFAULT_LOG_PATH, 'a+', 0)
            else:
                out_file = file('/dev/null', 'a+')
                err_file = file('/dev/null', 'a+', 0)

            os.dup2(out_file.fileno(), sys.stdout.fileno())
            os.dup2(err_file.fileno(), sys.stderr.fileno())
            os.close(sys.stdin.fileno())

            return pid
        except OSError as e:
            sys.exit(1)
    except OSError as e:
        sys.exit(1)


class Persistable:

    def __init__(self, play_context, new_stdin, *args, **kwargs):
        super(Persistable, self).__init__(play_context, new_stdin, *args, **kwargs)
        self._state = 'stopped'
        self._socket_path = None

    def connect(self, socket_path):
        self._socket_path = socket_path

        if self._state == 'running':
            display.display('provider socket is already running', log_only=True)
            return

        display.display('starting persistent connection (timeout=%s)' % self._play_context.timeout, log_only=True)

        self._state = 'connecting'
        self._start_time = datetime.datetime.now()

        try:
            self._connect()
        except AnsibleConnectionFailure as exc:
            self._state = 'stopped'
            raise

        connection_time = datetime.datetime.now() - self._start_time
        display.display('connection established to %s in %s' % (self._play_context.remote_addr, connection_time), log_only=True)

        if self._state == 'connecting':
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.bind(self._socket_path)
            self.socket.listen(1)
            self._state = 'running'
            display.display('local socket is set to listening', log_only=True)

        display.display('persistent connection completed successfully', log_only=True)
        display.display('  state is %s' % self._state, log_only=True)

    def is_alive(self):
        return self._state == 'running'

    def connect_timeout(self, signum, frame):
        display.display('timeout trying to connect to remote device', log_only=True)
        self.terminate()

    def terminate(self):
        display.display('terminate persistent connection requested', log_only=True)

        if self._state not in ('connecting', 'running'):
            display.display('persistent connection is not active', log_only=True)
            return

        self._state = 'closing'
        try:
            if self.socket:
                display.display('closing local listener', log_only=True)
                self.socket.close()

            if self.connected:
                display.display('closing the connection', log_only=True)
                self.close()

        except Exception as e:
            pass

        finally:
            if os.path.exists(self._socket_path):
                display.display('removing the local control socket', log_only=True)
                os.remove(self._socket_path)

        self._state = 'shutdown'

    @staticmethod
    def set_play_context_overrides(play_context):
        return play_context

    @classmethod
    def start(cls, play_context):
        #play_context = cls.set_play_context_overrides(play_context)

        # create the persistent connection dir if need be and create the paths
        # which we will be using later
        tmp_path = unfrackpath(C.PERSISTENT_CONTROL_PATH_DIR)
        makedirs_safe(tmp_path)
        lk_path = unfrackpath("%s/.ansible_pc_lock" % tmp_path)

        ssh = connection_loader.get('ssh', class_only=True)
        cp = ssh._create_control_path(play_context.remote_addr, play_context.connection, play_context.connection_user)
        socket_path = unfrackpath(cp % dict(directory=tmp_path))
        display.vvvv('connection socket_path is %s' % socket_path, play_context.remote_addr)

        lock_fd = os.open(lk_path, os.O_RDWR|os.O_CREAT, 0o600)
        fcntl.lockf(lock_fd, fcntl.LOCK_EX)

        if os.path.exists(socket_path):
            display.vvvv('connecting to existing socket %s' % socket_path, play_context.remote_addr)
        else:
            pid = do_fork()
            if pid == 0:
                try:
                    conn = cls(play_context, '/dev/null')
                    conn.connect(socket_path)
                except:
                    display.display(traceback.format_exc(), log_only=True)
                else:
                    fcntl.lockf(lock_fd, fcntl.LOCK_UN)
                    os.close(lock_fd)
                    if not conn.is_alive():
                        os.remove(socket_path)
                    else:
                        conn.run()

            else:
                timeout = play_context.timeout
                # make sure the server is running before continuing
                while bool(timeout):
                    if os.path.exists(socket_path):
                        display.display('local socket found', log_only=True)
                        break
                    time.sleep(1)
                    timeout -= 1
                else:
                    raise AnsibleConnectionFailure('timeout waiting for socket to start')

        return socket_path

    def run(self):
        display.display('inside run() on local socket', log_only=True)

        try:
            while True:
                signal.signal(signal.SIGALRM, self.connect_timeout)
                signal.alarm(C.PERSISTENT_CONNECT_TIMEOUT)

                try:
                    (s, addr) = self.socket.accept()
                    display.display('incoming request accepted on persistent socket', log_only=True)
                except:
                    break

                signal.alarm(0)

                while True:
                    data = recv_data(s)
                    if not data:
                        break

                    signal.alarm(self._play_context.timeout)

                    rc = 255

                    try:
                        if data.startswith(b'EXEC: '):
                            display.display("socket operation is EXEC", log_only=True)
                            cmd = data.split(b'EXEC: ')[1]
                            (rc, stdout, stderr) = self.exec_command(cmd)

                        elif data.startswith(b'PUT: ') or data.startswith(b'FETCH: '):
                            (op, src, dst) = shlex.split(to_native(data))
                            stdout = stderr = ''

                            try:
                                if op == 'FETCH:':
                                    display.display("socket operation is FETCH", log_only=True)
                                    self.fetch_file(src, dst)

                                elif op == 'PUT:':
                                    display.display("socket operation is PUT", log_only=True)
                                    self.put_file(src, dst)

                                rc = 0

                            except:
                                pass

                        else:
                            display.display("socket operation is UNKNOWN", log_only=True)
                            stdout = ''
                            stderr = 'Invalid action specified'
                    except:
                        stdout = ''
                        stderr = traceback.format_exc()

                    signal.alarm(0)

                    display.display("socket operation completed with rc %s" % rc, log_only=True)

                    send_data(s, to_bytes(rc))
                    send_data(s, to_bytes(stdout))
                    send_data(s, to_bytes(stderr))

                s.close()

        except Exception as e:
            display.display(traceback.format_exc(), log_only=True)

        finally:
            # when done, close the connection properly and cleanup
            # the socket file so it can be recreated
            self.terminate()
            end_time = datetime.datetime.now()
            delta = end_time - self._start_time
            display.display('provider socket shutdown completed successfully, provider was active for %s secs' % delta, log_only=True)
