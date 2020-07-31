#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for rust_uprev.py"""

# pylint: disable=cros-logging-import
import os
import shutil
import subprocess
import unittest
from unittest import mock

import rust_uprev
from llvm_tools import git


class RustVersionTest(unittest.TestCase):
  """Tests for RustVersion class"""

  def test_str(self):
    obj = rust_uprev.RustVersion(major=1, minor=2, patch=3)
    self.assertEqual(str(obj), '1.2.3')

  def test_parse_version_only(self):
    expected = rust_uprev.RustVersion(major=1, minor=2, patch=3)
    actual = rust_uprev.RustVersion.parse('1.2.3')
    self.assertEqual(expected, actual)

  def test_parse_ebuild_name(self):
    expected = rust_uprev.RustVersion(major=1, minor=2, patch=3)
    actual = rust_uprev.RustVersion.parse_from_ebuild('rust-1.2.3.ebuild')
    self.assertEqual(expected, actual)

  def test_parse_fail(self):
    with self.assertRaises(AssertionError) as context:
      rust_uprev.RustVersion.parse('invalid-rust-1.2.3')
    self.assertEqual("failed to parse 'invalid-rust-1.2.3'",
                     str(context.exception))


class PrepareUprevTest(unittest.TestCase):
  """Tests for prepare_uprev step in rust_uprev"""
  mock_equery = '/path/to/rust/rust-1.2.3.ebuild'
  mock_lsdir = ['rust-1.1.1.ebuild', 'rust-1.2.3.ebuild', 'an-unrelated-file']

  @mock.patch.object(subprocess, 'check_call')
  @mock.patch.object(git, 'CreateBranch')
  @mock.patch.object(rust_uprev, 'get_command_output')
  @mock.patch.object(os, 'listdir')
  def test_success(self, mock_ls, mock_command, mock_git, mock_reset):
    mock_ls.return_value = self.mock_lsdir
    mock_command.return_value = self.mock_equery
    input_version = rust_uprev.RustVersion(1, 3, 5)
    expected = ('/path/to/rust', rust_uprev.RustVersion(1, 2, 3),
                rust_uprev.RustVersion(1, 1, 1))
    actual = rust_uprev.prepare_uprev(input_version, True)
    self.assertEqual(expected, actual)
    mock_reset.assert_called_once_with(['git', 'reset', '--hard'],
                                       cwd='/path/to/rust')
    mock_git.assert_called_once_with('/path/to/rust', 'rust-to-1.3.5')

  @mock.patch.object(git, 'CreateBranch')
  @mock.patch.object(
      rust_uprev,
      'get_command_output',
      return_value='/path/to/rust/rust-1.2.3.ebuild')
  @mock.patch.object(os, 'listdir')
  def test_current_version_larger_failure(self, mock_ls, mock_command,
                                          mock_git):
    mock_command.return_value = self.mock_equery
    input_version = rust_uprev.RustVersion(1, 1, 1)
    rust_path, current, old = rust_uprev.prepare_uprev(input_version, False)
    self.assertEqual(rust_path, '')
    self.assertIsNone(current)
    self.assertIsNone(old)
    mock_ls.assert_not_called()
    mock_git.assert_not_called()

  @mock.patch.object(git, 'CreateBranch')
  @mock.patch.object(rust_uprev, 'get_command_output')
  @mock.patch.object(os, 'listdir')
  def test_more_than_two_ebuilds_fail(self, mock_ls, mock_command, mock_git):
    mock_command.return_value = self.mock_equery
    mock_ls.return_value = self.mock_lsdir + ['rust-1.0.0.ebuild']
    input_version = rust_uprev.RustVersion(1, 3, 5)
    with self.assertRaises(Exception) as context:
      rust_uprev.prepare_uprev(input_version, False)
    self.assertIn('Expect exactly 1 previous version ebuild',
                  str(context.exception))
    mock_git.assert_not_called()

  def test_prepare_uprev_from_json(self):
    json_result = [
        '/path/to/rust',
        [1, 44, 0],
        [1, 43, 0],
    ]
    expected = ('/path/to/rust', rust_uprev.RustVersion(1, 44, 0),
                rust_uprev.RustVersion(1, 43, 0))
    actual = rust_uprev.prepare_uprev_from_json(json_result)
    self.assertEqual(expected, actual)


class UpdateEbuildTest(unittest.TestCase):
  """Tests for update_ebuild step in rust_uprev"""
  ebuild_file_before = """
    STAGE0_DATE="2019-01-01"
    STAGE0_VERSION="any.random.(number)"
    STAGE0_VERSION_CARGO="0.0.0"
    """
  ebuild_file_after = """
    STAGE0_DATE="2020-01-01"
    STAGE0_VERSION="1.1.1"
    STAGE0_VERSION_CARGO="0.1.0"
    """

  def test_success(self):
    mock_open = mock.mock_open(read_data=self.ebuild_file_before)
    ebuild_file = '/path/to/rust/rust-1.3.5.ebuild'
    with mock.patch('builtins.open', mock_open):
      rust_uprev.update_ebuild(ebuild_file, ('2020-01-01', '1.1.1', '0.1.0'))
    mock_open.return_value.__enter__().write.assert_called_once_with(
        self.ebuild_file_after)

  def test_fail_when_ebuild_misses_a_variable(self):
    ebuild_file = 'STAGE0_DATE="2019-01-01"'
    mock_open = mock.mock_open(read_data=ebuild_file)
    ebuild_file = '/path/to/rust/rust-1.3.5.ebuild'
    with mock.patch('builtins.open', mock_open):
      with self.assertRaises(RuntimeError) as context:
        rust_uprev.update_ebuild(ebuild_file, ('2020-01-01', '1.1.1', '0.1.0'))
    self.assertEqual('STAGE0_VERSION not found in rust ebuild',
                     str(context.exception))


class UpdateManifestTest(unittest.TestCase):
  """Tests for update_manifest step in rust_uprev"""

  # pylint: disable=protected-access
  def _run_test_flip_mirror(self, before, after, add, expect_write):
    mock_open = mock.mock_open(read_data=f'RESTRICT="{before}"')
    with mock.patch('builtins.open', mock_open):
      rust_uprev.flip_mirror_in_ebuild('', add=add)
    if expect_write:
      mock_open.return_value.__enter__().write.assert_called_once_with(
          f'RESTRICT="{after}"')

  def test_add_mirror_in_ebuild(self):
    self._run_test_flip_mirror(
        before='variable1 variable2',
        after='variable1 variable2 mirror',
        add=True,
        expect_write=True)

  def test_remove_mirror_in_ebuild(self):
    self._run_test_flip_mirror(
        before='variable1 variable2 mirror',
        after='variable1 variable2',
        add=False,
        expect_write=True)

  def test_add_mirror_when_exists(self):
    self._run_test_flip_mirror(
        before='variable1 variable2 mirror',
        after='variable1 variable2 mirror',
        add=True,
        expect_write=False)

  def test_remove_mirror_when_not_exists(self):
    self._run_test_flip_mirror(
        before='variable1 variable2',
        after='variable1 variable2',
        add=False,
        expect_write=False)

  @mock.patch.object(rust_uprev, 'flip_mirror_in_ebuild')
  @mock.patch.object(rust_uprev, 'rust_ebuild_command')
  def test_update_manifest(self, mock_run, mock_flip):
    ebuild_file = '/path/to/rust/rust-1.1.1.ebuild'
    rust_uprev.update_manifest(ebuild_file)
    mock_run.assert_called_once_with('manifest')
    mock_flip.assert_has_calls(
        [mock.call(ebuild_file, add=True),
         mock.call(ebuild_file, add=False)])


class RustUprevOtherTests(unittest.TestCase):
  """Tests for other steps in rust_uprev"""

  def setUp(self):
    self.rust_path = '/path/to/rust'
    self.old_version = rust_uprev.RustVersion(1, 1, 0)
    self.current_version = rust_uprev.RustVersion(1, 2, 3)
    self.new_version = rust_uprev.RustVersion(1, 3, 5)
    self.ebuild_file = os.path.join(self.rust_path,
                                    'rust-{self.new_version}.ebuild')

  @mock.patch.object(rust_uprev, 'get_command_output')
  def test_parse_stage0_file(self, mock_get):
    stage0_file = """
    unrelated stuff before
    date: 2020-01-01
    rustc: 1.1.1
    cargo: 0.1.0
    unrelated stuff after
    """
    mock_get.return_value = stage0_file
    expected = '2020-01-01', '1.1.1', '0.1.0'
    rust_version = rust_uprev.RustVersion(1, 2, 3)
    actual = rust_uprev.parse_stage0_file(rust_version)
    self.assertEqual(expected, actual)
    mock_get.assert_called_once_with([
        'curl', '-f', 'https://raw.githubusercontent.com/rust-lang/rust/'
        f'{rust_version}/src/stage0.txt'
    ])

  @mock.patch.object(shutil, 'copyfile')
  @mock.patch.object(os, 'listdir')
  @mock.patch.object(subprocess, 'check_call')
  def test_copy_patches(self, mock_call, mock_ls, mock_copy):
    mock_ls.return_value = [
        f'rust-{self.old_version}-patch-1.patch',
        f'rust-{self.old_version}-patch-2-old.patch',
        f'rust-{self.current_version}-patch-1.patch',
        f'rust-{self.current_version}-patch-2-new.patch'
    ]
    rust_uprev.copy_patches(self.rust_path, self.old_version,
                            self.current_version, self.new_version)
    mock_copy.assert_has_calls([
        mock.call(
            os.path.join(self.rust_path, 'files',
                         f'rust-{self.current_version}-patch-1.patch'),
            os.path.join(self.rust_path, 'files',
                         f'rust-{self.new_version}-patch-1.patch'),
        ),
        mock.call(
            os.path.join(self.rust_path, 'files',
                         f'rust-{self.current_version}-patch-2-new.patch'),
            os.path.join(self.rust_path, 'files',
                         f'rust-{self.new_version}-patch-2-new.patch'))
    ])
    mock_call.assert_has_calls([
        mock.call(['git', 'add', f'files/rust-{self.new_version}-*.patch'],
                  cwd=self.rust_path),
        mock.call(['git', 'rm', f'files/rust-{self.old_version}-*.patch'],
                  cwd=self.rust_path)
    ])

  @mock.patch.object(shutil, 'copyfile')
  @mock.patch.object(subprocess, 'check_call')
  def test_rename_ebuild(self, mock_call, mock_copy):
    rust_uprev.rename_ebuild(self.rust_path, self.old_version,
                             self.current_version, self.new_version)
    mock_copy.assert_called_once_with(
        os.path.join(self.rust_path, f'rust-{self.current_version}.ebuild'),
        os.path.join(self.rust_path, f'rust-{self.new_version}.ebuild'))
    mock_call.assert_has_calls([
        mock.call(['git', 'add', f'rust-{self.new_version}.ebuild'],
                  cwd=self.rust_path),
        mock.call(['git', 'rm', f'rust-{self.old_version}.ebuild'],
                  cwd=self.rust_path)
    ])

  def test_upgrade_rust_packages(self):
    package_before = (f'dev-lang/rust-{self.old_version}\n'
                      f'dev-lang/rust-{self.current_version}')
    package_after = (f'dev-lang/rust-{self.current_version}\n'
                     f'dev-lang/rust-{self.new_version}')
    mock_open = mock.mock_open(read_data=package_before)
    with mock.patch('builtins.open', mock_open):
      rust_uprev.upgrade_rust_packages(self.ebuild_file, self.old_version,
                                       self.current_version, self.new_version)
    mock_open.return_value.__enter__().write.assert_called_once_with(
        package_after)

  @mock.patch.object(os.path, 'exists', return_value=True)
  @mock.patch.object(subprocess, 'check_call')
  def test_update_virtual_rust(self, mock_call, _):
    rust_uprev.update_virtual_rust(self.ebuild_file, self.old_version,
                                   self.new_version)
    mock_call.assert_called_once_with([
        'git', 'mv', f'rust-{self.old_version}.ebuild',
        f'rust-{self.new_version}.ebuild'
    ],
                                      cwd=os.path.join(self.rust_path,
                                                       '../../virtual/rust'))

  @mock.patch.object(subprocess, 'check_call')
  def test_upload_to_localmirror(self, mock_call):
    tempdir = '/tmp/any/dir'
    rust_uprev.upload_to_localmirror(tempdir, self.new_version)

    tarfile_name = f'rustc-{self.new_version}-src.tar.gz'
    rust_src = f'https://static.rust-lang.org/dist/{tarfile_name}'
    gsurl = f'gs://chromeos-localmirror/distfiles/{tarfile_name}'
    local_file = os.path.join(tempdir, tarfile_name)
    mock_call.assert_has_calls([
        mock.call(['curl', '-f', '-o', local_file, rust_src]),
        mock.call(
            ['gsutil', 'cp', '-n', '-a', 'public-read', local_file, gsurl])
    ])


if __name__ == '__main__':
  unittest.main()
