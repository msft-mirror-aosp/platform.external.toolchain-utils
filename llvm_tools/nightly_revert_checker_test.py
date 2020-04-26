#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for nightly_revert_checker."""

from __future__ import print_function

# pylint: disable=protected-access

import io
import unittest

import nightly_revert_checker
import revert_checker


class Test(unittest.TestCase):
  """Tests for nightly_revert_checker."""

  def test_email_rendering_works_for_singular_revert(self):
    email = nightly_revert_checker._generate_revert_email(
        friendly_name='${name}',
        sha='${sha}',
        new_reverts=[
            revert_checker.Revert(
                sha='${revert_sha}', reverted_sha='${reverted_sha}')
        ])

    expected_email = nightly_revert_checker._Email(
        subject='[revert-checker] new revert discovered across ${name}',
        body='\n'.join((
            'It looks like there may be a new revert across ${name} (${sha}).',
            '',
            'That is:',
            '\t- ${revert_sha} (appears to revert ${reverted_sha})',
            '',
            'PTAL and consider reverting them locally.',
        )))

    self.assertEqual(email, expected_email)

  def test_email_rendering_works_for_multiple_reverts(self):
    email = nightly_revert_checker._generate_revert_email(
        friendly_name='${name}',
        sha='${sha}',
        new_reverts=[
            revert_checker.Revert(
                sha='${revert_sha1}', reverted_sha='${reverted_sha1}'),
            revert_checker.Revert(
                sha='${revert_sha2}', reverted_sha='${reverted_sha2}'),
            # Keep this out-of-order to check that we sort based on SHAs
            revert_checker.Revert(
                sha='${revert_sha0}', reverted_sha='${reverted_sha0}'),
        ])

    expected_email = nightly_revert_checker._Email(
        subject='[revert-checker] new reverts discovered across ${name}',
        body='\n'.join((
            'It looks like there may be new reverts across ${name} (${sha}).',
            '',
            'These are:',
            '\t- ${revert_sha0} (appears to revert ${reverted_sha0})',
            '\t- ${revert_sha1} (appears to revert ${reverted_sha1})',
            '\t- ${revert_sha2} (appears to revert ${reverted_sha2})',
            '',
            'PTAL and consider reverting them locally.',
        )))

    self.assertEqual(email, expected_email)

  def test_llvm_ebuild_parsing_appears_to_function(self):
    llvm_ebuild = io.StringIO('\n'.join((
        'foo',
        '#LLVM_HASH="123"',
        'LLVM_HASH="123" # comment',
        'LLVM_NEXT_HASH="456"',
    )))

    shas = nightly_revert_checker._parse_llvm_ebuild_for_shas(llvm_ebuild)
    self.assertEqual(shas, [
        ('llvm', '123'),
        ('llvm-next', '456'),
    ])

  def test_llvm_ebuild_parsing_fails_if_both_hashes_arent_present(self):
    bad_bodies = [
        '',
        'LLVM_HASH="123" # comment',
        'LLVM_NEXT_HASH="123" # comment',
        'LLVM_NEXT_HASH="123" # comment\n#LLVM_HASH="123"',
    ]

    for bad in bad_bodies:
      with self.assertRaises(ValueError) as e:
        nightly_revert_checker._parse_llvm_ebuild_for_shas(io.StringIO(bad))

      self.assertIn('Failed to detect SHAs', str(e.exception))


if __name__ == '__main__':
  unittest.main()
