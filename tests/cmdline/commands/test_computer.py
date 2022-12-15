# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
# pylint: disable=unused-argument,invalid-name
"""Tests for the 'verdi computer' command."""
from collections import OrderedDict
import os
import tempfile
import textwrap

import pytest

from aiida import orm
from aiida.cmdline.commands.cmd_computer import (
    computer_configure,
    computer_delete,
    computer_duplicate,
    computer_list,
    computer_relabel,
    computer_setup,
    computer_show,
    computer_test,
)


def generate_setup_options_dict(replace_args=None, non_interactive=True):
    """
    Return a OrderedDict with the key-value pairs for the command line.

    I use an ordered dict because for changing entries it's easier
    to have keys (so, a dict) but the commands might require a specific order,
    so I use an OrderedDict.

    This should be then passed to ``generate_setup_options()``.

    :param replace_args: a dictionary with the keys to replace, if needed
    :return: an OrderedDict with the command-line options
    """
    valid_noninteractive_options = OrderedDict()

    if non_interactive:
        valid_noninteractive_options['non-interactive'] = None
    valid_noninteractive_options['label'] = 'noninteractive_computer'
    valid_noninteractive_options['hostname'] = 'localhost'
    valid_noninteractive_options['description'] = 'my description'
    valid_noninteractive_options['transport'] = 'core.local'
    valid_noninteractive_options['scheduler'] = 'core.direct'
    valid_noninteractive_options['shebang'] = '#!/bin/bash'
    valid_noninteractive_options['work-dir'] = '/scratch/{username}/aiida_run'
    valid_noninteractive_options['mpirun-command'] = 'mpirun -np {tot_num_mpiprocs}'
    valid_noninteractive_options['mpiprocs-per-machine'] = '2'
    valid_noninteractive_options['default-memory-per-machine'] = '1000000'
    # Make them multiline to test also multiline options
    valid_noninteractive_options['prepend-text'] = "date\necho 'second line'"
    valid_noninteractive_options['append-text'] = "env\necho '444'\necho 'third line'"

    # I replace kwargs here, so that if they are known, they go at the right order
    if replace_args is not None:
        for k in replace_args:
            valid_noninteractive_options[k] = replace_args[k]

    return valid_noninteractive_options


def generate_setup_options(ordereddict):
    """
    Given an (ordered) dict, returns a list of options

    Note that at this moment the implementation only supports long options
    (i.e. --option=value) and not short ones (-o value).
    Set a value to None to avoid the '=value' part.

    :param ordereddict: as generated by ``generate_setup_options_dict()``
    :return: a list to be passed as command-line arguments.
    """
    options = []
    for key, value in ordereddict.items():
        if value is None:
            options.append(f'--{key}')
        else:
            options.append(f'--{key}={value}')
    return options


def generate_setup_options_interactive(ordereddict):
    """
    Given an (ordered) dict, returns a list of options

    Note that at this moment the implementation only supports long options
    (i.e. --option=value) and not short ones (-o value).
    Set a value to None to avoid the '=value' part.

    :param ordereddict: as generated by ``generate_setup_options_dict()``
    :return: a list to be passed as command-line arguments.
    """
    options = []
    for value in ordereddict.values():
        if value is None:
            options.append(True)
        else:
            options.append(value)
    return options


def test_help(run_cli_command):
    """Test the help of verdi computer setup."""
    run_cli_command(computer_setup, ['--help'])


def test_reachable():
    """Test if the verdi computer setup is reachable."""
    import subprocess as sp
    output = sp.check_output(['verdi', 'computer', 'setup', '--help'])
    assert b'Usage:' in output


def test_mixed(run_cli_command):
    """
    Test verdi computer setup in mixed mode.

    Some parts are given interactively and some non-interactively.
    """
    os.environ['VISUAL'] = 'sleep 1; vim -cwq'
    os.environ['EDITOR'] = 'sleep 1; vim -cwq'
    label = 'mixed_computer'

    options_dict = generate_setup_options_dict(replace_args={'label': label})
    options_dict_full = options_dict.copy()

    options_dict.pop('non-interactive', None)

    non_interactive_options_dict = {}
    non_interactive_options_dict['prepend-text'] = options_dict.pop('prepend-text')
    non_interactive_options_dict['append-text'] = options_dict.pop('append-text')
    non_interactive_options_dict['shebang'] = options_dict.pop('shebang')
    non_interactive_options_dict['scheduler'] = options_dict.pop('scheduler')

    # In any case, these would be managed by the visual editor
    user_input = '\n'.join(generate_setup_options_interactive(options_dict))
    options = generate_setup_options(non_interactive_options_dict)

    result = run_cli_command(computer_setup, options, user_input=user_input)
    assert result.exception is None, f'There was an unexpected exception. Output: {result.output}'

    new_computer = orm.Computer.collection.get(label=label)
    assert isinstance(new_computer, orm.Computer)

    assert new_computer.description == options_dict_full['description']
    assert new_computer.hostname == options_dict_full['hostname']
    assert new_computer.transport_type == options_dict_full['transport']
    assert new_computer.scheduler_type == options_dict_full['scheduler']
    assert new_computer.get_mpirun_command() == options_dict_full['mpirun-command'].split()
    assert new_computer.get_shebang() == options_dict_full['shebang']
    assert new_computer.get_workdir() == options_dict_full['work-dir']
    assert new_computer.get_default_mpiprocs_per_machine() == int(options_dict_full['mpiprocs-per-machine'])

    # default_memory_per_machine should not prompt and set
    assert new_computer.get_default_memory_per_machine() is None

    # For now I'm not writing anything in them
    assert new_computer.get_prepend_text() == options_dict_full['prepend-text']
    assert new_computer.get_append_text() == options_dict_full['append-text']


@pytest.mark.parametrize('non_interactive_editor', ('vim -cwq',), indirect=True)
def test_noninteractive(run_cli_command, aiida_localhost, non_interactive_editor):
    """
    Main test to check if the non-interactive command works
    """
    options_dict = generate_setup_options_dict()
    options = generate_setup_options(options_dict)

    result = run_cli_command(computer_setup, options)

    new_computer = orm.Computer.collection.get(label=options_dict['label'])
    assert isinstance(new_computer, orm.Computer)

    assert new_computer.description == options_dict['description']
    assert new_computer.hostname == options_dict['hostname']
    assert new_computer.transport_type == options_dict['transport']
    assert new_computer.scheduler_type == options_dict['scheduler']
    assert new_computer.get_mpirun_command() == options_dict['mpirun-command'].split()
    assert new_computer.get_shebang() == options_dict['shebang']
    assert new_computer.get_workdir() == options_dict['work-dir']
    assert new_computer.get_default_mpiprocs_per_machine() == int(options_dict['mpiprocs-per-machine'])
    assert new_computer.get_default_memory_per_machine() == int(options_dict['default-memory-per-machine'])
    assert new_computer.get_prepend_text() == options_dict['prepend-text']
    assert new_computer.get_append_text() == options_dict['append-text']

    # Test that I cannot generate twice a computer with the same label
    result = run_cli_command(computer_setup, options, raises=True)
    assert 'already exists' in result.output


def test_noninteractive_optional_default_mpiprocs(run_cli_command):
    """
    Check that if is ok not to specify mpiprocs-per-machine
    """
    options_dict = generate_setup_options_dict({'label': 'computer_default_mpiprocs'})
    options_dict.pop('mpiprocs-per-machine')
    options = generate_setup_options(options_dict)
    run_cli_command(computer_setup, options)

    new_computer = orm.Computer.collection.get(label=options_dict['label'])
    assert isinstance(new_computer, orm.Computer)
    assert new_computer.get_default_mpiprocs_per_machine() is None


def test_noninteractive_optional_default_mpiprocs_2(run_cli_command):
    """
    Check that if is the specified value is zero, it means unspecified
    """
    options_dict = generate_setup_options_dict({'label': 'computer_default_mpiprocs_2'})
    options_dict['mpiprocs-per-machine'] = 0
    options = generate_setup_options(options_dict)
    run_cli_command(computer_setup, options)

    new_computer = orm.Computer.collection.get(label=options_dict['label'])
    assert isinstance(new_computer, orm.Computer)
    assert new_computer.get_default_mpiprocs_per_machine() is None


def test_noninteractive_optional_default_mpiprocs_3(run_cli_command):
    """
    Check that it fails for a negative number of mpiprocs
    """
    options_dict = generate_setup_options_dict({'label': 'computer_default_mpiprocs_3'})
    options_dict['mpiprocs-per-machine'] = -1
    options = generate_setup_options(options_dict)
    result = run_cli_command(computer_setup, options, raises=True)
    assert 'mpiprocs_per_machine, must be positive' in result.output


def test_noninteractive_optional_default_memory(run_cli_command):
    """
    Check that if is ok not to specify default-memory-per-machine
    """
    options_dict = generate_setup_options_dict({'label': 'computer_default_mem'})
    options_dict.pop('default-memory-per-machine')
    options = generate_setup_options(options_dict)
    run_cli_command(computer_setup, options)

    new_computer = orm.Computer.collection.get(label=options_dict['label'])
    assert isinstance(new_computer, orm.Computer)
    assert new_computer.get_default_memory_per_machine() is None


def test_noninteractive_optional_default_memory_invalid(run_cli_command):
    """
    Check that it fails for a negative number of default_memory.
    """
    options_dict = generate_setup_options_dict({'label': 'computer_default_memory_3'})
    options_dict['default-memory-per-machine'] = -1
    options = generate_setup_options(options_dict)
    result = run_cli_command(computer_setup, options, raises=True)
    assert 'Invalid value for def_memory_per_machine, must be a positive int, got: -1' in result.output


def test_noninteractive_wrong_transport_fail(run_cli_command):
    """
    Check that if fails as expected for an unknown transport
    """
    options_dict = generate_setup_options_dict(replace_args={'label': 'fail_computer'})
    options_dict['transport'] = 'unknown_transport'
    options = generate_setup_options(options_dict)
    result = run_cli_command(computer_setup, options, raises=True)
    assert "entry point 'unknown_transport' is not valid" in result.output


def test_noninteractive_wrong_scheduler_fail(run_cli_command):
    """
    Check that if fails as expected for an unknown transport
    """
    options_dict = generate_setup_options_dict(replace_args={'label': 'fail_computer'})
    options_dict['scheduler'] = 'unknown_scheduler'
    options = generate_setup_options(options_dict)
    result = run_cli_command(computer_setup, options, raises=True)
    assert "entry point 'unknown_scheduler' is not valid" in result.output


def test_noninteractive_invalid_shebang_fail(run_cli_command):
    """
    Check that if fails as expected for an unknown transport
    """
    options_dict = generate_setup_options_dict(replace_args={'label': 'fail_computer'})
    options_dict['shebang'] = '/bin/bash'  # Missing #! in front
    options = generate_setup_options(options_dict)
    result = run_cli_command(computer_setup, options, raises=True)
    assert 'The shebang line should start with' in result.output


def test_noninteractive_invalid_mpirun_fail(run_cli_command):
    """
    Check that if fails as expected for an unknown transport
    """
    options_dict = generate_setup_options_dict(replace_args={'label': 'fail_computer'})
    options_dict['mpirun-command'] = 'mpirun -np {unknown_key}'
    options = generate_setup_options(options_dict)
    result = run_cli_command(computer_setup, options, raises=True)
    assert "unknown replacement field 'unknown_key'" in result.output


def test_noninteractive_from_config(run_cli_command):
    """Test setting up a computer from a config file"""
    label = 'noninteractive_config'

    with tempfile.NamedTemporaryFile('w') as handle:
        handle.write(f"""---
label: {label}
hostname: myhost
transport: core.local
scheduler: core.direct
""")
        handle.flush()

        options = ['--non-interactive', '--config', os.path.realpath(handle.name)]
        run_cli_command(computer_setup, options)

    assert isinstance(orm.Computer.collection.get(label=label), orm.Computer)


class TestVerdiComputerConfigure:
    """Test the ``verdi computer configure`` command."""

    @pytest.fixture(autouse=True)
    def init_profile(self, run_cli_command):  # pylint: disable=unused-argument
        """Initialize the profile."""
        # pylint: disable=attribute-defined-outside-init
        from aiida.orm.utils.builders.computer import ComputerBuilder
        self.cli_runner = run_cli_command
        self.user = orm.User.collection.get_default()
        self.comp_builder = ComputerBuilder(label='test_comp_setup')
        self.comp_builder.hostname = 'localhost'
        self.comp_builder.description = 'Test Computer'
        self.comp_builder.scheduler = 'core.direct'
        self.comp_builder.work_dir = '/tmp/aiida'
        self.comp_builder.use_double_quotes = False
        self.comp_builder.prepend_text = ''
        self.comp_builder.append_text = ''
        self.comp_builder.mpiprocs_per_machine = 8
        self.comp_builder.default_memory_per_machine = 100000
        self.comp_builder.mpirun_command = 'mpirun'
        self.comp_builder.shebang = '#!xonsh'

    def test_top_help(self):
        """Test help option of verdi computer configure."""
        result = self.cli_runner(computer_configure, ['--help'])
        assert 'core.ssh' in result.output
        assert 'core.local' in result.output

    def test_reachable(self):  # pylint: disable=no-self-use
        """Test reachability of top level and sub commands."""
        import subprocess as sp
        sp.check_output(['verdi', 'computer', 'configure', '--help'])
        sp.check_output(['verdi', 'computer', 'configure', 'core.local', '--help'])
        sp.check_output(['verdi', 'computer', 'configure', 'core.ssh', '--help'])
        sp.check_output(['verdi', 'computer', 'configure', 'show', '--help'])

    def test_local_ni_empty(self):
        """
        Test verdi computer configure core.local <comp>

        Test twice, with comp setup for local or ssh.

         * with computer setup for local: should succeed
         * with computer setup for ssh: should fail
        """
        self.comp_builder.label = 'test_local_ni_empty'
        self.comp_builder.transport = 'core.local'
        comp = self.comp_builder.new()
        comp.store()

        options = ['core.local', comp.label, '--non-interactive', '--safe-interval', '0']
        result = self.cli_runner(computer_configure, options)
        assert comp.is_configured, result.output

        self.comp_builder.label = 'test_local_ni_empty_mismatch'
        self.comp_builder.transport = 'core.ssh'
        comp_mismatch = self.comp_builder.new()
        comp_mismatch.store()

        options = ['core.local', comp_mismatch.label, '--non-interactive']
        result = self.cli_runner(computer_configure, options, raises=True)
        assert 'core.ssh' in result.output
        assert 'core.local' in result.output

    def test_local_interactive(self):
        """Test computer configuration for local transports."""
        self.comp_builder.label = 'test_local_interactive'
        self.comp_builder.transport = 'core.local'
        comp = self.comp_builder.new()
        comp.store()

        invalid = 'n'
        valid = '1.0'
        result = self.cli_runner(computer_configure, ['core.local', comp.label], user_input=f'{invalid}\n{valid}\n')
        assert comp.is_configured, result.output

        new_auth_params = comp.get_authinfo(self.user).get_auth_params()
        assert new_auth_params['use_login_shell'] is False
        assert new_auth_params['use_login_shell'] == 1.0

    def test_ssh_interactive(self):
        """
        Check that the interactive prompt is accepting the correct values.

        Actually, even passing a shorter set of options should work:
        ``verdi computer configure ssh`` is able to provide sensible default
        parameters reading from the ssh config file.
        We are here therefore only checking some of them.
        """
        self.comp_builder.label = 'test_ssh_interactive'
        self.comp_builder.transport = 'core.ssh'
        comp = self.comp_builder.new()
        comp.store()

        remote_username = 'some_remote_user'
        port = 345
        look_for_keys = False
        key_filename = ''

        # I just pass the first four arguments:
        # the username, the port, look_for_keys, and the key_filename
        # This testing also checks that an empty key_filename is ok
        command_input = ('{remote_username}\n{port}\n{look_for_keys}\n{key_filename}\n').format(
            remote_username=remote_username,
            port=port,
            look_for_keys='yes' if look_for_keys else 'no',
            key_filename=key_filename
        )

        result = self.cli_runner(computer_configure, ['core.ssh', comp.label], user_input=command_input)
        assert comp.is_configured, result.output
        new_auth_params = comp.get_authinfo(self.user).get_auth_params()
        assert new_auth_params['username'] == remote_username
        assert new_auth_params['port'] == port
        assert new_auth_params['look_for_keys'] == look_for_keys
        assert new_auth_params['key_filename'] == key_filename
        assert new_auth_params['use_login_shell'] is True

    def test_local_from_config(self):
        """Test configuring a computer from a config file"""
        label = 'test_local_from_config'
        self.comp_builder.label = label
        self.comp_builder.transport = 'core.local'
        computer = self.comp_builder.new()
        computer.store()

        interval = 20
        use_login_shell = False

        with tempfile.NamedTemporaryFile('w') as handle:
            handle.write(
                textwrap.dedent(
                    f"""---
                    safe_interval: {interval}
                    use_login_shell: {use_login_shell}
                    """
                )
            )
            handle.flush()

            options = ['core.local', computer.label, '--config', os.path.realpath(handle.name)]
            self.cli_runner(computer_configure, options)

        assert computer.get_configuration()['safe_interval'] == interval
        assert computer.get_configuration()['use_login_shell'] == use_login_shell

    def test_ssh_ni_empty(self):
        """
        Test verdi computer configure core.ssh <comp>

        Test twice, with comp setup for ssh or local.

         * with computer setup for ssh: should succeed
         * with computer setup for local: should fail
        """
        self.comp_builder.label = 'test_ssh_ni_empty'
        self.comp_builder.transport = 'core.ssh'
        comp = self.comp_builder.new()
        comp.store()

        options = ['core.ssh', comp.label, '--non-interactive', '--safe-interval', '1']
        result = self.cli_runner(computer_configure, options)
        assert comp.is_configured, result.output

        self.comp_builder.label = 'test_ssh_ni_empty_mismatch'
        self.comp_builder.transport = 'core.local'
        comp_mismatch = self.comp_builder.new()
        comp_mismatch.store()

        options = ['core.ssh', comp_mismatch.label, '--non-interactive']
        result = self.cli_runner(computer_configure, options, raises=True)
        assert 'core.local' in result.output
        assert 'core.ssh' in result.output

    def test_ssh_ni_username(self):
        """Test verdi computer configure core.ssh <comp> --username=<username>."""
        self.comp_builder.label = 'test_ssh_ni_username'
        self.comp_builder.transport = 'core.ssh'
        comp = self.comp_builder.new()
        comp.store()

        username = 'TEST'
        options = ['core.ssh', comp.label, '--non-interactive', f'--username={username}', '--safe-interval', '1']
        result = self.cli_runner(computer_configure, options)
        auth_info = orm.AuthInfo.collection.get(dbcomputer_id=comp.pk, aiidauser_id=self.user.pk)
        assert comp.is_configured, result.output
        assert auth_info.get_auth_params()['username'] == username

    def test_show(self):
        """Test verdi computer configure show <comp>."""
        self.comp_builder.label = 'test_show'
        self.comp_builder.transport = 'core.ssh'
        comp = self.comp_builder.new()
        comp.store()

        result = self.cli_runner(computer_configure, ['show', comp.label])

        result = self.cli_runner(computer_configure, ['show', comp.label, '--defaults'])
        assert '* username' in result.output

        result = self.cli_runner(
            computer_configure, ['show', comp.label, '--defaults', '--as-option-string'], suppress_warnings=True
        )
        assert '--username=' in result.output

        config_cmd = ['core.ssh', comp.label, '--non-interactive']
        config_cmd.extend(result.output.replace("'", '').split(' '))
        result_config = self.cli_runner(computer_configure, config_cmd, suppress_warnings=True)
        assert comp.is_configured, result_config.output

        result_cur = self.cli_runner(
            computer_configure, ['show', comp.label, '--as-option-string'], suppress_warnings=True
        )
        assert '--username=' in result.output
        assert result_cur.output == result.output


class TestVerdiComputerCommands:
    """Testing verdi computer commands.

    Testing everything besides `computer setup`.
    """

    @pytest.fixture(autouse=True)
    def init_profile(self, aiida_computer, run_cli_command):  # pylint: disable=unused-argument
        """Initialize the profile."""
        # pylint: disable=attribute-defined-outside-init
        self.computer_name = 'comp_cli_test_computer'
        self.comp = aiida_computer(label=self.computer_name)
        self.comp.set_default_mpiprocs_per_machine(1)
        self.comp.set_default_memory_per_machine(1000000)
        self.comp.set_prepend_text('text to prepend')
        self.comp.set_append_text('text to append')
        self.comp.store()
        self.comp.configure()
        self.user = orm.User.collection.get_default()
        assert self.comp.is_configured, 'There was a problem configuring the test computer'
        self.cli_runner = run_cli_command

    def test_computer_test(self):
        """
        Test if the 'verdi computer test' command works

        It should work as it is a local connection
        """
        # Testing the wrong computer will fail
        self.cli_runner(computer_test, ['non-existent-computer'], raises=True)

        # Testing the right computer should pass locally
        self.cli_runner(computer_test, ['comp_cli_test_computer'])

    def test_computer_list(self):
        """
        Test if 'verdi computer list' command works
        """
        # Check the vanilla command works
        result = self.cli_runner(computer_list, [])
        # Something should be printed to stdout
        assert result.output is not None

        # Check all options run
        for opt in ['-r', '--raw', '-a', '--all']:
            result = self.cli_runner(computer_list, [opt])
            # Something should be printed to stdout
            assert result.output is not None

    def test_computer_show(self):
        """
        Test if 'verdi computer show' command works
        """
        # See if we can display info about the test computer.
        result = self.cli_runner(computer_show, ['comp_cli_test_computer'])
        # Something should be printed to stdout
        assert result.output is not None

        # See if a non-existent computer will raise an error.
        result = self.cli_runner(computer_show, 'non_existent_computer_name', raises=True)

    def test_computer_relabel(self):
        """
        Test if 'verdi computer relabel' command works
        """
        from aiida.common.exceptions import NotExistent

        # See if the command complains about not getting an invalid computer
        options = ['not_existent_computer_label']
        self.cli_runner(computer_relabel, options, raises=True)

        # See if the command complains about not getting both labels
        options = ['comp_cli_test_computer']
        self.cli_runner(computer_relabel, options, raises=True)

        # The new label must be different to the old one
        options = ['comp_cli_test_computer', 'comp_cli_test_computer']
        self.cli_runner(computer_relabel, options, raises=True)

        # Change a computer label successully.
        options = ['comp_cli_test_computer', 'relabeled_test_computer']
        self.cli_runner(computer_relabel, options)

        # Check that the label really was changed
        # The old label should not be available
        with pytest.raises(NotExistent):
            orm.Computer.collection.get(label='comp_cli_test_computer')
        # The new label should be available
        orm.Computer.collection.get(label='relabeled_test_computer')

        # Now change the label back
        options = ['relabeled_test_computer', 'comp_cli_test_computer']
        self.cli_runner(computer_relabel, options)

        # Check that the label really was changed
        # The old label should not be available
        with pytest.raises(NotExistent):
            orm.Computer.collection.get(label='relabeled_test_computer')
        # The new label should be available
        orm.Computer.collection.get(label='comp_cli_test_computer')

    def test_computer_delete(self):
        """
        Test if 'verdi computer delete' command works
        """
        from aiida.common.exceptions import NotExistent

        # Setup a computer to delete during the test
        label = 'computer_for_test_label'
        orm.Computer(
            label=label,
            hostname='localhost',
            transport_type='core.local',
            scheduler_type='core.direct',
            workdir='/tmp/aiida'
        ).store()
        # and configure it
        options = ['core.local', label, '--non-interactive', '--safe-interval', '0']
        self.cli_runner(computer_configure, options)

        # See if the command complains about not getting an invalid computer
        self.cli_runner(computer_delete, ['computer_that_does_not_exist'], raises=True)

        # Delete a computer name successully.
        self.cli_runner(computer_delete, [label])
        # Check that the computer really was deleted
        with pytest.raises(NotExistent):
            orm.Computer.collection.get(label=label)


@pytest.mark.parametrize('non_interactive_editor', ('vim -cwq',), indirect=True)
def test_computer_duplicate_interactive(run_cli_command, aiida_localhost, non_interactive_editor):
    """Test 'verdi computer duplicate' in interactive mode."""
    label = 'computer_duplicate_interactive'
    computer = aiida_localhost
    user_input = f'{label}\n\n\n\n\n\n\n\n\n\n'
    result = run_cli_command(computer_duplicate, [str(computer.pk)], user_input=user_input)
    assert result.exception is None, result.output

    new_computer = orm.Computer.collection.get(label=label)
    assert new_computer.description == computer.description
    assert new_computer.hostname == computer.hostname
    assert new_computer.transport_type == computer.transport_type
    assert new_computer.scheduler_type == computer.scheduler_type
    assert new_computer.get_shebang() == computer.get_shebang()
    assert new_computer.get_workdir() == computer.get_workdir()
    assert new_computer.get_mpirun_command() == computer.get_mpirun_command()
    assert new_computer.get_default_mpiprocs_per_machine() == computer.get_default_mpiprocs_per_machine()
    assert new_computer.get_prepend_text() == computer.get_prepend_text()
    assert new_computer.get_append_text() == computer.get_append_text()


@pytest.mark.parametrize('non_interactive_editor', ('vim -cwq',), indirect=True)
def test_computer_duplicate_non_interactive(run_cli_command, aiida_localhost, non_interactive_editor):
    """Test if 'verdi computer duplicate' in non-interactive mode."""
    label = 'computer_duplicate_noninteractive'
    computer = aiida_localhost
    result = run_cli_command(computer_duplicate, ['--non-interactive', f'--label={label}', str(computer.pk)])
    assert result.exception is None, result.output

    new_computer = orm.Computer.collection.get(label=label)
    assert new_computer.description == computer.description
    assert new_computer.hostname == computer.hostname
    assert new_computer.transport_type == computer.transport_type
    assert new_computer.scheduler_type == computer.scheduler_type
    assert new_computer.get_shebang() == computer.get_shebang()
    assert new_computer.get_workdir() == computer.get_workdir()
    assert new_computer.get_mpirun_command() == computer.get_mpirun_command()
    assert new_computer.get_default_mpiprocs_per_machine() == computer.get_default_mpiprocs_per_machine()
    assert new_computer.get_prepend_text() == computer.get_prepend_text()
    assert new_computer.get_append_text() == computer.get_append_text()


@pytest.mark.parametrize('non_interactive_editor', ('sleep 1; vim -cwq',), indirect=True)
def test_direct_interactive(run_cli_command, non_interactive_editor):
    """Test verdi computer setup in interactive mode."""
    label = 'interactive_computer'

    options_dict = generate_setup_options_dict(replace_args={'label': label}, non_interactive=False)
    # default-memory-per-machine will not prompt for direct
    options_dict.pop('default-memory-per-machine')

    # In any case, these would be managed by the visual editor
    options_dict.pop('prepend-text')
    options_dict.pop('append-text')
    user_input = '\n'.join(generate_setup_options_interactive(options_dict))

    result = run_cli_command(computer_setup, user_input=user_input)
    assert result.exception is None, f'There was an unexpected exception. Output: {result.output}'

    new_computer = orm.Computer.collection.get(label=label)
    assert isinstance(new_computer, orm.Computer)

    assert new_computer.description == options_dict['description']
    assert new_computer.hostname == options_dict['hostname']
    assert new_computer.transport_type == options_dict['transport']
    assert new_computer.scheduler_type == options_dict['scheduler']
    assert new_computer.get_mpirun_command() == options_dict['mpirun-command'].split()
    assert new_computer.get_shebang() == options_dict['shebang']
    assert new_computer.get_workdir() == options_dict['work-dir']
    assert new_computer.get_default_mpiprocs_per_machine() == int(options_dict['mpiprocs-per-machine'])
    # For now I'm not writing anything in them
    assert new_computer.get_prepend_text() == ''
    assert new_computer.get_append_text() == ''


def test_computer_test_stderr(run_cli_command, aiida_localhost, monkeypatch):
    """Test `verdi computer test` where tested command returns non-empty stderr."""
    from aiida.transports.plugins.local import LocalTransport

    aiida_localhost.configure()
    stderr = 'spurious output in standard error'

    def exec_command_wait(self, command, **kwargs):
        return 0, '', stderr

    monkeypatch.setattr(LocalTransport, 'exec_command_wait', exec_command_wait)

    result = run_cli_command(computer_test, [aiida_localhost.label], use_subprocess=False)
    assert 'Warning: 1 out of 6 tests failed' in result.output
    assert stderr in result.output


def test_computer_test_stdout(run_cli_command, aiida_localhost, monkeypatch):
    """Test `verdi computer test` where tested command returns non-empty stdout."""
    from aiida.transports.plugins.local import LocalTransport

    aiida_localhost.configure()
    stdout = 'spurious output in standard output'

    def exec_command_wait(self, command, **kwargs):
        return 0, stdout, ''

    monkeypatch.setattr(LocalTransport, 'exec_command_wait', exec_command_wait)

    result = run_cli_command(computer_test, [aiida_localhost.label], use_subprocess=False)
    assert 'Warning: 1 out of 6 tests failed' in result.output
    assert stdout in result.output


def test_computer_test_use_login_shell(run_cli_command, aiida_localhost, monkeypatch):
    """Test ``verdi computer test`` where ``use_login_shell=True`` is much slower."""
    from aiida.cmdline.commands import cmd_computer

    aiida_localhost.configure()

    def time_use_login_shell(authinfo, auth_params, use_login_shell, iterations) -> float:  # pylint: disable=unused-argument
        if use_login_shell:
            return 0.21
        return 0.10

    monkeypatch.setattr(cmd_computer, 'time_use_login_shell', time_use_login_shell)

    result = run_cli_command(computer_test, [aiida_localhost.label], use_subprocess=False)
    assert 'Warning: 1 out of 6 tests failed' in result.output
    assert 'computer is configured to use a login shell, which is slower compared to a normal shell' in result.output
