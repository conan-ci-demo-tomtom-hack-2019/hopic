# Copyright (c) 2020 - 2020 TomTom N.V. (https://tomtom.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from io import StringIO
from textwrap import dedent
import typing

try:
    # Python >= 3.8
    from importlib import metadata
except ImportError:
    import importlib_metadata as metadata

import pytest

from .. import config_reader
from ..errors import ConfigurationError


def _config_file(s: str):
    f = StringIO(s)
    f.name = 'test-hopic-config.yaml'
    return f


@pytest.fixture
def mock_yaml_plugin(monkeypatch):
    class TestTemplate:
        name = 'example'

        def load(self):
            return self.example_template

        @staticmethod
        def example_template(
            volume_vars : typing.Mapping[str, str],
            *,
            required_param : str,
            optional_param: 'typing.Optional[str]' = None,
            defaulted_param : bool = False,
        ) -> typing.Sequence[typing.Mapping[str, typing.Any]]:
            val = {
                'required': required_param,
                'defaulted': defaulted_param,
            }
            if optional_param is not None:
                val['optional'] = optional_param
            return (val,)

    class TestKwargTemplate:
        name = 'kwarg'

        def load(self):
            return self.kwarg_template

        @staticmethod
        def kwarg_template(
            volume_vars : typing.Mapping[str, str],
            *,
            required_param : str,
            **kwargs,
        ) -> typing.Sequence[typing.Mapping[str, typing.Any]]:
            val = {
                'required': required_param,
                'defaulted': kwargs.get('defaulted-param', False),
            }
            optional = kwargs.pop('optional-param', None)
            if optional is not None:
                val['optional'] = optional
            val['kwargs'] = kwargs

            assert isinstance(val['required'], str)
            return (val,)

    class TestSimpleTemplate:
        name = 'simple'

        def load(self):
            return self.no_arg_template

        @staticmethod
        def no_arg_template(volume_vars):
            return ()

    class TestSequenceTemplate:
        name = 'sequence'

        def load(self):
            return self.sequence_template

        @staticmethod
        def sequence_template(
            volume_vars : typing.Mapping[str, str],
            *,
            sequence: typing.List[str] = [],
        ) -> typing.Sequence[typing.Mapping[str, typing.Any]]:
            assert isinstance(sequence, typing.List)
            for v in sequence:
                assert isinstance(v, str)
            return ({'sequence': sequence},)

    class TestWrongDefaultTemplate:
        name = 'wrong-default'

        def load(self):
            return self.wrong_default_template

        @staticmethod
        def wrong_default_template(
            volume_vars : typing.Mapping[str, str],
            *,
            defaulted_param : 'str' = None,
        ) -> typing.Sequence[typing.Mapping[str, typing.Any]]:
            return ({
                'defaulted': defaulted_param,
            },)

    class TestWrongReturnTemplate:
        name = "wrong-return"

        def load(self):
            return self.wrong_return_template

        @staticmethod
        def wrong_return_template(
            volume_vars : typing.Mapping[str, str],
        ) -> typing.List[typing.Dict[str, typing.Any]]:
            return [
                {43: None},
            ]

    class TestNonGeneratorTemplate:
        name = "non-generator"

        def load(self):
            return self.non_generator_template

        @staticmethod
        def non_generator_template(
            volume_vars : typing.Mapping[str, str],
        ) -> typing.Generator:
            return [
                {"sh": ["ls"]},
            ]

    class TestGeneratorTemplate:
        name = 'generator'

        def load(self):
            return self.generator_template

        @staticmethod
        def generator_template(
            volume_vars : typing.Mapping[str, str],
            *,
            cmds: typing.List[str] = [],
        ) -> typing.Generator:
            yield "echo setup"
            yield from cmds
            yield "echo cleanup"

    class TestBadGeneratorTemplate:
        name = "bad-generator"

        def load(self):
            unwrapped = self.bad_generator_template
            while (
                hasattr(unwrapped, '__wrapped__')
                and getattr(unwrapped.__wrapped__, '__annotations__', None) is not None
                and getattr(unwrapped, '__annotations__') is unwrapped.__wrapped__.__annotations__
            ):
                unwrapped = unwrapped.__wrapped__
            return unwrapped

        @staticmethod
        def bad_generator_template(
            volume_vars : typing.Mapping[str, str],
        ) -> typing.Generator[typing.Mapping[str, typing.Any], None, None]:
            yield {"sh": ["ls"]}
            yield False

    def mock_entry_points():
        return {
            'hopic.plugins.yaml': (
                TestTemplate(),
                TestKwargTemplate(),
                TestSimpleTemplate(),
                TestSequenceTemplate(),
                TestWrongDefaultTemplate(),
                TestWrongReturnTemplate(),
                TestNonGeneratorTemplate(),
                TestGeneratorTemplate(),
                TestBadGeneratorTemplate(),
            )
        }
    monkeypatch.setattr(metadata, 'entry_points', mock_entry_points)


@pytest.mark.parametrize('version_build', (
    '',
    123,
    '@invalidmetadata',
    [1, 2, 3],
    (1,),
    {'name': 'value'},
    '+invalid',
    '.invalid',
))
def test_version_build_handles_invalid_values(version_build):
    with pytest.raises(ConfigurationError, match=r'version.build'):
        config_reader.read_version_info({}, {'build': version_build})


@pytest.mark.parametrize('version_build', (
    '1.70.0',
    '-oddbutvalid',
))
def test_version_build(version_build):
    result = config_reader.read_version_info({}, {'build': version_build})
    assert result['build'] == version_build


def test_version_build_non_semver():
    with pytest.raises(ConfigurationError, match=r'version.build'):
        config_reader.read_version_info({}, {'format': 'carver', 'build': '1.0.0'})


def test_environment_without_cmd():
    with pytest.raises(ConfigurationError, match=r"set 'environment' member .* doesn't have 'sh'"):
        config_reader.read(
            _config_file(
                dedent(
                    '''\
                    phases:
                      test:
                        example:
                          - environment: {}
                    '''
                )
            ),
            {'WORKSPACE': None},
        )


def test_environment_type_mismatch():
    with pytest.raises(ConfigurationError, match=r"`environment\['sheep'\]` is not a string"):
        config_reader.read(
            _config_file(
                dedent(
                    '''\
                    phases:
                      test:
                        example:
                          - environment:
                              sheep: 1
                            sh:
                              - printenv
                    '''
                )
            ),
            {'WORKSPACE': None},
        )


def test_environment_from_prefix():
    cfg = config_reader.read(
        _config_file(
            dedent(
                '''\
                phases:
                  test:
                    example:
                      - SHEEP=1 EMPTY= ./command.sh
                '''
            )
        ),
        {'WORKSPACE': None},
    )
    (out,) = cfg['phases']['test']['example']
    assert out['sh'] == ['./command.sh']
    assert dict(out['environment']) == {'SHEEP': '1', 'EMPTY': ''}


def test_node_label_type_mismatch():
    with pytest.raises(ConfigurationError, match=r"`node-label` .*? string .*? bool"):
        config_reader.read(
            _config_file(
                dedent(
                    '''\
                    phases:
                      test:
                        example:
                          - node-label: true
                    '''
                )
            ),
            {'WORKSPACE': None},
        )


def test_node_label_mismatch():
    with pytest.raises(ConfigurationError, match=r"`node-label` .*?\bdiffers from .*?\bprevious.*?\bdefined"):
        config_reader.read(
            _config_file(
                dedent(
                    '''\
                    phases:
                      build:
                        example:
                          - node-label: first
                      test:
                        example:
                          - node-label: second
                    '''
                )
            ),
            {'WORKSPACE': None},
        )


def test_node_label_mismatch_single_phase():
    with pytest.raises(ConfigurationError, match=r"`node-label` .*?\bdiffers from .*?\bprevious.*?\bdefined"):
        config_reader.read(
            _config_file(
                dedent(
                    '''\
                    phases:
                      build:
                        example:
                          - node-label: first
                          - node-label: second
                    '''
                )
            ),
            {'WORKSPACE': None},
        )


def test_node_label_default_override():
    with pytest.raises(ConfigurationError, match=r"`node-label` .*?\boverride default"):
        config_reader.read(
            _config_file(
                dedent(
                    '''\
                    phases:
                      build:
                        example: []
                      test:
                        example:
                          - node-label: second
                    '''
                )
            ),
            {'WORKSPACE': None},
        )


def test_post_submit_node_label_mismatch():
    with pytest.raises(ConfigurationError, match=r"`node-label` .*?\bdiffers from .*?\bprevious.*?\bdefined"):
        config_reader.read(
            _config_file(
                dedent(
                    '''\
                    post-submit:
                      build:
                        - node-label: first
                      test:
                        - node-label: second
                    '''
                )
            ),
            {'WORKSPACE': None},
        )


def test_node_label_match():
    config_reader.read(
        _config_file(
            dedent(
                '''\
                phases:
                  build:
                    example:
                      - node-label: first
                  test:
                    example:
                      - node-label: first
                '''
            )
        ),
        {'WORKSPACE': None},
    )


def test_post_submit_node_label_match():
    config_reader.read(
        _config_file(
            dedent(
                '''\
                post-submit:
                  build:
                    - node-label: first
                  test:
                    - node-label: first
                '''
            )
        ),
        {'WORKSPACE': None},
    )


def test_template_reserved_param(mock_yaml_plugin):
    with pytest.raises(ConfigurationError, match=r'(?i)trying to use reserved keyword `volume-vars` to instantiate template `.*?`'):
        config_reader.read(_config_file(dedent('''\
            phases:
              test:
                example: !template
                  name: example
                  required-param: PIPE
                  volume-vars: {}
        ''')), {'WORKSPACE': None})


def test_template_missing_param(mock_yaml_plugin):
    with pytest.raises(ConfigurationError, match=r'(?i)trying to instantiate template `.*?` without required parameter'):
        config_reader.read(_config_file(dedent('''\
            phases:
              test:
                example: !template "example"
        ''')), {'WORKSPACE': None})


def test_template_mismatched_param_simple_type(mock_yaml_plugin):
    with pytest.raises(ConfigurationError, match=r'(?i)trying to instantiate template `.*?`: type of required-param must be str; got bool instead'):
        config_reader.read(_config_file(dedent('''\
            phases:
              test:
                example: !template
                  name: example
                  required-param: yes
        ''')), {'WORKSPACE': None})


def test_template_mismatched_param_optional_type(mock_yaml_plugin):
    with pytest.raises(ConfigurationError, match=r'(?i)trying to instantiate template `.*?`: type of optional-param must be .*?; got bool instead'):
        config_reader.read(_config_file(dedent('''\
            phases:
              test:
                example: !template
                  name: example
                  optional-param: yes
        ''')), {'WORKSPACE': None})


def test_template_snake_param(mock_yaml_plugin):
    with pytest.raises(
        ConfigurationError,
        match=r'(?i)trying to instantiate template `.*?` with unexpected parameter `required_param`.*? mean `required-param`',
    ):
        config_reader.read(_config_file(dedent('''\
            phases:
              test:
                example: !template
                  name: example
                  required_param: PIPE
        ''')), {'WORKSPACE': None})


def test_template_unknown_param(mock_yaml_plugin):
    with pytest.raises(ConfigurationError, match=r'(?i)trying to instantiate template `.*?` with unexpected parameter `unknown-param`'):
        config_reader.read(_config_file(dedent('''\
            phases:
              test:
                example: !template
                  name: example
                  unknown-param: 42
        ''')), {'WORKSPACE': None})


def test_template_without_optional_param(mock_yaml_plugin):
    cfg = config_reader.read(_config_file(dedent('''\
        phases:
          test:
            example: !template
              name: example
              required-param: PIPE
    ''')), {'WORKSPACE': None})
    out, = cfg['phases']['test']['example']
    assert 'optional' not in out


def test_template_with_explicitly_null_param(mock_yaml_plugin):
    cfg = config_reader.read(_config_file(dedent('''\
        phases:
          test:
            example: !template
              name: example
              required-param: PIPE
              optional-param: null
    ''')), {'WORKSPACE': None})
    out, = cfg['phases']['test']['example']
    assert 'optional' not in out


def test_template_with_optional_param(mock_yaml_plugin):
    cfg = config_reader.read(_config_file(dedent('''\
        phases:
          test:
            example: !template
              name: example
              required-param: PIPE
              optional-param: Have you ever seen the rain?
    ''')), {'WORKSPACE': None})
    out, = cfg['phases']['test']['example']
    assert 'optional' in out
    assert out['optional'] == 'Have you ever seen the rain?'


def test_template_kwargs_required_snake_param(mock_yaml_plugin):
    with pytest.raises(
        ConfigurationError,
        match=r'(?i)trying to instantiate template `.*?` with unexpected parameter `required_param`.*? mean `required-param`',
    ):
        config_reader.read(_config_file(dedent('''\
            phases:
              test:
                example: !template
                  name: kwarg
                  required_param: PIPE
        ''')), {'WORKSPACE': None})


def test_template_kwargs_snake_param_in_kwarg(mock_yaml_plugin):
    cfg = config_reader.read(_config_file(dedent('''\
        phases:
          test:
            example: !template
              name: kwarg
              required-param: PIPE
              something_extra-that_is-ridiculous: yes
    ''')), {'WORKSPACE': None})
    out, = cfg['phases']['test']['example']
    assert out['kwargs'] == {'something_extra-that_is-ridiculous': True}


def test_template_kwargs_missing_param(mock_yaml_plugin):
    with pytest.raises(ConfigurationError, match=r'(?i)trying to instantiate template `.*?` without required parameter'):
        config_reader.read(_config_file(dedent('''\
            phases:
              test:
                example: !template "kwarg"
        ''')), {'WORKSPACE': None})


def test_template_kwargs_type_mismatch(mock_yaml_plugin):
    with pytest.raises(ConfigurationError, match=r'(?i)trying to instantiate template `.*?`: type of required-param must be str; got NoneType instead'):
        config_reader.read(_config_file(dedent('''\
            phases:
              test:
                example: !template
                  name: kwarg
                  required-param: null
        ''')), {'WORKSPACE': None})


def test_template_simple_unknown_param(mock_yaml_plugin):
    with pytest.raises(ConfigurationError, match=r'(?i)trying to instantiate template `.*?` with unexpected parameter `unknown-param`'):
        config_reader.read(_config_file(dedent('''\
            phases:
              test:
                example: !template
                  name: simple
                  unknown-param: 42
        ''')), {'WORKSPACE': None})


def test_template_simple_without_param(mock_yaml_plugin):
    cfg = config_reader.read(_config_file(dedent('''\
        phases:
          test:
            example: !template "simple"
    ''')), {'WORKSPACE': None})
    out = cfg['phases']['test']['example']
    assert out == []


def test_template_sequence_without_param(mock_yaml_plugin):
    cfg = config_reader.read(_config_file(dedent('''\
        phases:
          test:
            example: !template "sequence"
    ''')), {'WORKSPACE': None})
    out = cfg['phases']['test']['example'][0]['sequence']
    assert out == []


def test_template_with_wrong_default(mock_yaml_plugin):
    with pytest.raises(ConfigurationError, match=r'(?i)\bwrong default of parameter for template `.*?`: type of defaulted-param must be str; got .*? instead'):
        config_reader.read(_config_file(dedent('''\
            phases:
              test:
                example: !template
                  name: wrong-default
                  defaulted-param: mooh
        ''')), {'WORKSPACE': None})


def test_template_sequence_with_single_entry(mock_yaml_plugin):
    cfg = config_reader.read(_config_file(dedent('''\
        phases:
          test:
            example: !template
              name: "sequence"
              sequence:
                - mooh
    ''')), {'WORKSPACE': None})
    out = cfg['phases']['test']['example'][0]['sequence']
    assert out == ['mooh']


def test_template_sequence_with_str_instead_of_list(mock_yaml_plugin):
    with pytest.raises(ConfigurationError, match=r'(?i)trying to instantiate template `.*?`: type of sequence must be\b.*?\blist; got str instead'):
        config_reader.read(
            _config_file(
                dedent(
                    """\
                    phases:
                      test:
                        example: !template
                          name: "sequence"
                          sequence: mooh
                    """
                )
            ),
            {'WORKSPACE': None},
        )


def test_template_sequence_with_type_mismatched_entry(mock_yaml_plugin):
    with pytest.raises(ConfigurationError, match=r'(?i)trying to instantiate template `.*?`: type of sequence\[1\] must be str; got bool instead'):
        config_reader.read(_config_file(dedent('''\
            phases:
              test:
                example: !template
                  name: "sequence"
                  sequence:
                    - mooh
                    - false
                    - sheep
        ''')), {'WORKSPACE': None})


def test_template_wrong_return(mock_yaml_plugin):
    with pytest.raises((ConfigurationError, TypeError), match=r"(?i)return value(?:\[.*?\])? must be .*?; got .*? instead"):
        config_reader.read(_config_file(dedent('''\
            phases:
              test:
                example: !template wrong-return
        ''')), {'WORKSPACE': None})


def test_template_non_generator(mock_yaml_plugin):
    with pytest.raises((ConfigurationError, TypeError), match=r"(?i)return value must be \S*\bGenerator; got list instead"):
        config_reader.read(_config_file(dedent('''\
            phases:
              test:
                example: !template non-generator
        ''')), {'WORKSPACE': None})


def test_template_generator(mock_yaml_plugin):
    cfg = config_reader.read(_config_file(dedent('''\
        phases:
          test:
            example: !template
              name: generator
              cmds:
                - echo "do something"
    ''')), {'WORKSPACE': None})
    cmds = [cmd["sh"] for cmd in cfg["phases"]["test"]["example"]]
    assert cmds == [
        ["echo", "setup"],
        ["echo", "do something"],
        ["echo", "cleanup"],
    ]


def test_bad_generator_template(mock_yaml_plugin):
    with pytest.raises((ConfigurationError, TypeError), match=r"(?i)value yielded from generator\b.*?\bmust be (?:dict|\S*\bMapping); got bool instead"):
        config_reader.read(_config_file(dedent('''\
            phases:
              test:
                example: !template bad-generator
        ''')), {'WORKSPACE': None})


def test_nested_command_list_flattening():
    cfg = config_reader.read(
        _config_file(
            dedent(
                """\
                phases:
                  test:
                    example:
                      - run-on-change: always
                      -
                        - description: something happening here
                        -
                            - echo "Tada!"
                            - sh: echo "Tada!"
                            - sh: [echo, "Tada!"]
                """
            )
        ),
        {'WORKSPACE': None},
    )
    out = [dict(cmd) for cmd in cfg['phases']['test']['example']]
    assert out == [
        {"run-on-change": config_reader.RunOnChange.always},
        {"description": "something happening here"},
        {"environment": {}, "sh": ["echo", "Tada!"]},
        {"environment": {}, "sh": ["echo", "Tada!"]},
        {"environment": {}, "sh": ["echo", "Tada!"]},
    ]