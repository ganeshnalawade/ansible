# Copyright (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division)
__metaclass__ = type

import pytest
from os.path import expanduser

from ansible.module_utils import basic

@pytest.fixture
def am(mocker):
    def fake_init(self, *args, **kwargs):
        self.argument_spec = 'Fake'
        self.params = 'Fake'
        self.check_invalid_arguments = True
        self.check_mode = False
        self.bypass_checks = False
        self._options_context = []
        self._legal_inputs = []
        self.fail_json = mocker.MagicMock()
        self._CHECK_ARGUMENT_TYPES_DISPATCHER = {
            'str': self._check_type_str,
            'list': self._check_type_list,
            'dict': self._check_type_dict,
            'bool': self._check_type_bool,
            'int': self._check_type_int,
            'float': self._check_type_float,
            'path': self._check_type_path,
            'raw': self._check_type_raw,
            'jsonarg': self._check_type_jsonarg,
            'json': self._check_type_jsonarg,
            'bytes': self._check_type_bytes,
            'bits': self._check_type_bits,
        }

    AM__init__ = basic.AnsibleModule.__init__
    basic.AnsibleModule.__init__ = fake_init
    am = basic.AnsibleModule()

    yield am

    basic.AnsibleModule.__init__ = AM__init__


# First element: argspec
# Second element: parameters passed in
# Third element expected transformation
OPTIONS = (
        ({'data': {'type': 'list', 'elements': 'int', 'default': [], 'required': False}}, {'data': ['21', 42, '17']}, {'data': [21, 42, 17]}),
        ({'data': {'type': 'list', 'elements': 'int', 'default': [], 'required': False}}, {}, {'data': []}),
        ({'data': {'type': 'list', 'elements': 'int', 'default': None, 'required': False}}, {'data': None}, {'data': None}),
        )


@pytest.mark.parametrize("spec, params, expected", OPTIONS)
def test__check_argument_types(am, spec, params, expected):
    am.argument_spec = spec
    am.params = params
    am._set_defaults(pre=True, spec=spec, param=params)
    am._check_argument_types(spec, params)
    assert expected == am.params
