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

  def setUp(self):
    self.version_old = rust_uprev.RustVersion(1, 2, 3)
    self.version_new = rust_uprev.RustVersion(1, 3, 5)

  @mock.patch.object(os.path, 'exists')
  @mock.patch.object(rust_uprev, 'get_command_output')
  def test_success_with_template(self, mock_command, mock_exists):
    mock_exists.return_value = True
    expected = self.version_old
    actual = rust_uprev.prepare_uprev(
        rust_version=self.version_new, template=self.version_old)
    self.assertEqual(expected, actual)
    mock_command.assert_not_called()

  @mock.patch.object(os.path, 'exists')
  @mock.patch.object(rust_uprev, 'get_command_output')
  def test_fail_with_template_not_exist(self, mock_command, mock_exists):
    mock_exists.return_value = False
    with self.assertRaises(ValueError) as context:
      rust_uprev.prepare_uprev(
          rust_version=self.version_new, template=self.version_old)
    self.assertEqual(f'Template ebuild file {self.version_old} does not exist',
                     str(context.exception))
    mock_command.assert_not_called()

  @mock.patch.object(os.path, 'exists')
  @mock.patch.object(rust_uprev, 'get_command_output')
  def test_return_none_with_template_larger_than_input(self, mock_command,
                                                       mock_exists):
    mock_exists.return_value = True
    ret = rust_uprev.prepare_uprev(
        rust_version=self.version_old, template=self.version_new)
    self.assertIsNone(ret)
    mock_command.assert_not_called()

  @mock.patch.object(os.path, 'exists')
  @mock.patch.object(rust_uprev, 'get_command_output')
  def test_success_without_template(self, mock_command, mock_exists):
    mock_command.return_value = f'/path/to/rust/rust-{self.version_old}.ebuild'
    expected = self.version_old
    actual = rust_uprev.prepare_uprev(
        rust_version=self.version_new, template=None)
    self.assertEqual(expected, actual)
    mock_command.assert_called_once_with(['equery', 'w', 'rust'])
    mock_exists.assert_not_called()

  @mock.patch.object(os.path, 'exists')
  @mock.patch.object(rust_uprev, 'get_command_output')
  def test_return_none_with_ebuild_larger_than_input(self, mock_command,
                                                     mock_exists):
    mock_command.return_value = f'/path/to/rust/rust-{self.version_new}.ebuild'
    ret = rust_uprev.prepare_uprev(rust_version=self.version_old, template=None)
    self.assertIsNone(ret)
    mock_exists.assert_not_called()

  def test_prepare_uprev_from_json(self):
    json_result = list(self.version_new)
    expected = self.version_new
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


class UpdateRustPackagesTests(unittest.TestCase):
  """Tests for update_rust_packages step."""

  def setUp(self):
    self.old_version = rust_uprev.RustVersion(1, 1, 0)
    self.current_version = rust_uprev.RustVersion(1, 2, 3)
    self.new_version = rust_uprev.RustVersion(1, 3, 5)
    self.ebuild_file = os.path.join(rust_uprev.RUST_PATH,
                                    'rust-{self.new_version}.ebuild')

  def test_add_new_rust_packages(self):
    package_before = (f'dev-lang/rust-{self.old_version}\n'
                      f'dev-lang/rust-{self.current_version}')
    package_after = (f'dev-lang/rust-{self.old_version}\n'
                     f'dev-lang/rust-{self.current_version}\n'
                     f'dev-lang/rust-{self.new_version}')
    mock_open = mock.mock_open(read_data=package_before)
    with mock.patch('builtins.open', mock_open):
      rust_uprev.update_rust_packages(self.new_version, add=True)
    mock_open.return_value.__enter__().write.assert_called_once_with(
        package_after)

  def test_remove_old_rust_packages(self):
    package_before = (f'dev-lang/rust-{self.old_version}\n'
                      f'dev-lang/rust-{self.current_version}\n'
                      f'dev-lang/rust-{self.new_version}')
    package_after = (f'dev-lang/rust-{self.current_version}\n'
                     f'dev-lang/rust-{self.new_version}')
    mock_open = mock.mock_open(read_data=package_before)
    with mock.patch('builtins.open', mock_open):
      rust_uprev.update_rust_packages(self.old_version, add=False)
    mock_open.return_value.__enter__().write.assert_called_once_with(
        package_after)


class RustUprevOtherStagesTests(unittest.TestCase):
  """Tests for other steps in rust_uprev"""

  def setUp(self):
    self.old_version = rust_uprev.RustVersion(1, 1, 0)
    self.current_version = rust_uprev.RustVersion(1, 2, 3)
    self.new_version = rust_uprev.RustVersion(1, 3, 5)
    self.ebuild_file = os.path.join(rust_uprev.RUST_PATH,
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
    rust_uprev.copy_patches(self.current_version, self.new_version)
    mock_copy.assert_has_calls([
        mock.call(
            os.path.join(rust_uprev.RUST_PATH, 'files',
                         f'rust-{self.current_version}-patch-1.patch'),
            os.path.join(rust_uprev.RUST_PATH, 'files',
                         f'rust-{self.new_version}-patch-1.patch'),
        ),
        mock.call(
            os.path.join(rust_uprev.RUST_PATH, 'files',
                         f'rust-{self.current_version}-patch-2-new.patch'),
            os.path.join(rust_uprev.RUST_PATH, 'files',
                         f'rust-{self.new_version}-patch-2-new.patch'))
    ])
    mock_call.assert_called_once_with(
        ['git', 'add', f'files/rust-{self.new_version}-*.patch'],
        cwd=rust_uprev.RUST_PATH)

  @mock.patch.object(shutil, 'copyfile')
  @mock.patch.object(subprocess, 'check_call')
  def test_create_ebuild(self, mock_call, mock_copy):
    rust_uprev.create_ebuild(self.current_version, self.new_version)
    mock_copy.assert_called_once_with(
        os.path.join(rust_uprev.RUST_PATH,
                     f'rust-{self.current_version}.ebuild'),
        os.path.join(rust_uprev.RUST_PATH, f'rust-{self.new_version}.ebuild'))
    mock_call.assert_called_once_with(
        ['git', 'add', f'rust-{self.new_version}.ebuild'],
        cwd=rust_uprev.RUST_PATH)

  @mock.patch.object(os.path, 'exists', return_value=True)
  @mock.patch.object(shutil, 'copyfile')
  @mock.patch.object(subprocess, 'check_call')
  def test_update_virtual_rust(self, mock_call, mock_copy, mock_exists):
    virtual_rust_dir = os.path.join(rust_uprev.RUST_PATH, '../../virtual/rust')
    rust_uprev.update_virtual_rust(self.current_version, self.new_version)
    mock_call.assert_called_once_with(
        ['git', 'add', f'rust-{self.new_version}.ebuild'], cwd=virtual_rust_dir)
    mock_copy.assert_called_once_with(
        os.path.join(virtual_rust_dir, f'rust-{self.current_version}.ebuild'),
        os.path.join(virtual_rust_dir, f'rust-{self.new_version}.ebuild'))
    mock_exists.assert_called_once_with(virtual_rust_dir)

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
