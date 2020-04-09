#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unittests for running tryjobs after updating packages."""

from __future__ import print_function

import json
import unittest
import unittest.mock as mock

from test_helpers import ArgsOutputTest
from test_helpers import CreateTemporaryFile
from update_chromeos_llvm_hash import CommitContents
import update_chromeos_llvm_hash
import update_packages_and_run_tryjobs


class UpdatePackagesAndRunTryjobsTest(unittest.TestCase):
  """Unittests when running tryjobs after updating packages."""

  def testNoLastTestedFile(self):
    self.assertEqual(
        update_packages_and_run_tryjobs.UnchangedSinceLastRun(None, {}), False)

  def testEmptyLastTestedFile(self):
    with CreateTemporaryFile() as temp_file:
      self.assertEqual(
          update_packages_and_run_tryjobs.UnchangedSinceLastRun(temp_file, {}),
          False)

  def testLastTestedFileDoesNotExist(self):
    # Simulate 'open()' on a lasted tested file that does not exist.
    mock.mock_open(read_data='')

    self.assertEqual(
        update_packages_and_run_tryjobs.UnchangedSinceLastRun(
            '/some/file/that/does/not/exist.txt', {}), False)

  def testMatchedLastTestedFile(self):
    with CreateTemporaryFile() as last_tested_file:
      arg_dict = {
          'svn_version':
              1234,
          'ebuilds': [
              '/path/to/package1-r2.ebuild',
              '/path/to/package2/package2-r3.ebuild'
          ],
          'builders': [
              'kevin-llvm-next-toolchain-tryjob',
              'eve-llvm-next-toolchain-tryjob'
          ],
          'extra_cls': [10, 1],
          'tryjob_options': ['latest-toolchain', 'hwtest']
      }

      with open(last_tested_file, 'w') as f:
        f.write(json.dumps(arg_dict, indent=2))

      self.assertEqual(
          update_packages_and_run_tryjobs.UnchangedSinceLastRun(
              last_tested_file, arg_dict), True)

  def testGetTryJobCommandWithNoExtraInformation(self):
    test_change_list = 1234

    test_builder = 'nocturne'

    expected_tryjob_cmd_list = [
        'cros', 'tryjob', '--yes', '--json', '-g',
        '%d' % test_change_list, test_builder
    ]

    self.assertEqual(
        update_packages_and_run_tryjobs.GetTryJobCommand(
            test_change_list, None, None, test_builder),
        expected_tryjob_cmd_list)

  def testGetTryJobCommandWithExtraInformation(self):
    test_change_list = 4321
    test_extra_cls = [1000, 10]
    test_options = ['report_error', 'delete_tryjob']
    test_builder = 'kevin'

    expected_tryjob_cmd_list = [
        'cros',
        'tryjob',
        '--yes',
        '--json',
        '-g',
        '%d' % test_change_list,
        '-g',
        '%d' % test_extra_cls[0],
        '-g',
        '%d' % test_extra_cls[1],
        test_builder,
        '--%s' % test_options[0],
        '--%s' % test_options[1],
    ]

    self.assertEqual(
        update_packages_and_run_tryjobs.GetTryJobCommand(
            test_change_list, test_extra_cls, test_options, test_builder),
        expected_tryjob_cmd_list)

  @mock.patch.object(
      update_packages_and_run_tryjobs,
      'GetCurrentTimeInUTC',
      return_value='2019-09-09')
  @mock.patch.object(update_packages_and_run_tryjobs, 'AddTryjobLinkToCL')
  @mock.patch.object(update_packages_and_run_tryjobs, 'ChrootRunCommand')
  def testSuccessfullySubmittedTryJob(
      self, mock_chroot_cmd, mock_add_tryjob_link_to_cl, mock_launch_time):

    expected_tryjob_cmd_list = [
        'cros', 'tryjob', '--yes', '--json', '-g',
        '%d' % 900, '-g',
        '%d' % 1200, 'builder1', '--some_option'
    ]

    buildbucket_id = '1234'
    url = 'https://some_tryjob_url.com'

    tryjob_launch_contents = [{'buildbucket_id': buildbucket_id, 'url': url}]

    mock_chroot_cmd.return_value = json.dumps(tryjob_launch_contents)

    extra_cls = [1200]
    tryjob_options = ['some_option']
    builder_list = ['builder1']
    chroot_path = '/some/path/to/chroot'
    cl_to_launch_tryjob = 900
    verbose = False

    tryjob_results_list = update_packages_and_run_tryjobs.RunTryJobs(
        cl_to_launch_tryjob, extra_cls, tryjob_options, builder_list,
        chroot_path, verbose)

    expected_tryjob_dict = {
        'launch_time': '2019-09-09',
        'link': url,
        'buildbucket_id': int(buildbucket_id),
        'extra_cls': extra_cls,
        'options': tryjob_options,
        'builder': builder_list
    }

    self.assertEqual(tryjob_results_list, [expected_tryjob_dict])

    mock_chroot_cmd.assert_called_once_with(
        chroot_path, expected_tryjob_cmd_list, verbose=False)

    mock_add_tryjob_link_to_cl.assert_called_once()

    mock_launch_time.assert_called_once()

  @mock.patch.object(
      update_packages_and_run_tryjobs,
      'ExecCommandAndCaptureOutput',
      return_value=None)
  def testSuccessfullyAddedTryjobLinkToCL(self, mock_exec_cmd):
    chroot_path = '/abs/path/to/chroot'

    test_cl_number = 1000

    tryjob_result = [{'link': 'https://some_tryjob_link.com'}]

    update_packages_and_run_tryjobs.AddTryjobLinkToCL(
        tryjob_result, test_cl_number, chroot_path)

    expected_gerrit_message = [
        '%s/chromite/bin/gerrit' % chroot_path, 'message',
        str(test_cl_number),
        'Started the following tryjobs:\n%s' % tryjob_result[0]['link']
    ]

    mock_exec_cmd.assert_called_once_with(expected_gerrit_message)

  @mock.patch.object(update_packages_and_run_tryjobs, 'RunTryJobs')
  @mock.patch.object(update_chromeos_llvm_hash, 'UpdatePackages')
  @mock.patch.object(update_packages_and_run_tryjobs, 'GetCommandLineArgs')
  @mock.patch.object(update_packages_and_run_tryjobs,
                     'GetLLVMHashAndVersionFromSVNOption')
  @mock.patch.object(
      update_packages_and_run_tryjobs, 'VerifyOutsideChroot', return_value=True)
  @mock.patch.object(update_chromeos_llvm_hash, 'GetChrootBuildPaths')
  def testUpdatedLastTestedFileWithNewTestedRevision(
      self, mock_get_chroot_build_paths, mock_outside_chroot,
      mock_get_hash_and_version, mock_get_commandline_args,
      mock_update_packages, mock_run_tryjobs):

    # Create a temporary file to simulate the last tested file that contains a
    # revision.
    with CreateTemporaryFile() as last_tested_file:
      builders = [
          'kevin-llvm-next-toolchain-tryjob', 'eve-llvm-next-toolchain-tryjob'
      ]
      extra_cls = [10, 1]
      tryjob_options = ['latest-toolchain', 'hwtest']
      ebuilds = [
          '/path/to/package1/package1-r2.ebuild',
          '/path/to/package2/package2-r3.ebuild'
      ]

      arg_dict = {
          'svn_version': 100,
          'ebuilds': ebuilds,
          'builders': builders,
          'extra_cls': extra_cls,
          'tryjob_options': tryjob_options
      }
      # Parepared last tested file
      with open(last_tested_file, 'w') as f:
        json.dump(arg_dict, f, indent=2)

      # Call with a changed LLVM svn version
      args_output = ArgsOutputTest()
      args_output.builders = builders
      args_output.extra_change_lists = extra_cls
      args_output.options = tryjob_options
      args_output.last_tested = last_tested_file

      mock_get_commandline_args.return_value = args_output

      mock_get_chroot_build_paths.return_value = ebuilds

      mock_get_hash_and_version.return_value = ('a123testhash2', 200)

      mock_update_packages.return_value = CommitContents(
          url='https://some_cl_url.com', cl_number=12345)

      mock_run_tryjobs.return_value = [{
          'link': 'https://some_tryjob_url.com',
          'buildbucket_id': 1234
      }]

      update_packages_and_run_tryjobs.main()

      # Verify that the lasted tested file has been updated to the new LLVM
      # revision.
      with open(last_tested_file) as f:
        arg_dict = json.load(f)

        self.assertEqual(arg_dict['svn_version'], 200)

    mock_outside_chroot.assert_called_once()

    mock_get_commandline_args.assert_called_once()

    mock_get_hash_and_version.assert_called_once()

    mock_run_tryjobs.assert_called_once()

    mock_update_packages.assert_called_once()


if __name__ == '__main__':
  unittest.main()
