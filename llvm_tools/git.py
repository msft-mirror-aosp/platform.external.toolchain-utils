#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Git helper functions."""

from __future__ import print_function

import collections
import os
import re
import subprocess
import tempfile

CommitContents = collections.namedtuple('CommitContents', ['url', 'cl_number'])


def InChroot():
  """Returns True if currently in the chroot."""
  return 'CROS_WORKON_SRCROOT' in os.environ


def VerifyOutsideChroot():
  """Checks whether the script invoked was executed in the chroot.

  Raises:
    AssertionError: The script was run inside the chroot.
  """

  assert not InChroot(), 'Script should be run outside the chroot.'


def CreateBranch(repo, branch):
  """Creates a branch in the given repo.

  Args:
    repo: The absolute path to the repo.
    branch: The name of the branch to create.

  Raises:
    ValueError: Failed to create a repo in that directory.
  """

  if not os.path.isdir(repo):
    raise ValueError('Invalid directory path provided: %s' % repo)

  subprocess.check_output(['git', '-C', repo, 'reset', 'HEAD', '--hard'],
                          encoding='utf-8')

  subprocess.check_output(['repo', 'start', branch], cwd=repo, encoding='utf-8')


def DeleteBranch(repo, branch):
  """Deletes a branch in the given repo.

  Args:
    repo: The absolute path of the repo.
    branch: The name of the branch to delete.

  Raises:
    ValueError: Failed to delete the repo in that directory.
  """

  if not os.path.isdir(repo):
    raise ValueError('Invalid directory path provided: %s' % repo)

  subprocess.check_output(['git', '-C', repo, 'checkout', 'cros/master'],
                          encoding='utf-8')

  subprocess.check_output(['git', '-C', repo, 'reset', 'HEAD', '--hard'],
                          encoding='utf-8')

  subprocess.check_output(['git', '-C', repo, 'branch', '-D', branch],
                          encoding='utf-8')


def UploadChanges(repo, branch, commit_messages):
  """Uploads the changes in the specifed branch of the given repo for review.

  Args:
    repo: The absolute path to the repo where changes were made.
    branch: The name of the branch to upload.
    commit_messages: A string of commit message(s) (i.e. '[message]'
    of the changes made.

  Returns:
    A nametuple that has two (key, value) pairs, where the first pair is the
    Gerrit commit URL and the second pair is the change list number.

  Raises:
    ValueError: Failed to create a commit or failed to upload the
    changes for review.
  """

  if not os.path.isdir(repo):
    raise ValueError('Invalid path provided: %s' % repo)

  # Create a git commit.
  with tempfile.NamedTemporaryFile(mode='w+t') as f:
    f.write('\n'.join(commit_messages))
    f.flush()

    subprocess.check_output(['git', 'commit', '-F', f.name],
                            cwd=repo,
                            encoding='utf-8')

  # Upload the changes for review.
  # Pylint currently doesn't lint things in py3 mode, and py2 didn't allow
  # users to specify `encoding`s for Popen. Hence, pylint is "wrong" here.
  # pylint: disable=unexpected-keyword-arg
  # The CL URL is sent to 'stderr', so need to redirect 'stderr' to 'stdout'.
  upload_changes_obj = subprocess.Popen(
      ['repo', 'upload', '--yes', '--ne', '--no-verify',
       '--br=%s' % branch],
      cwd=repo,
      stdout=subprocess.PIPE,
      stderr=subprocess.STDOUT,
      encoding='utf-8')

  out, _ = upload_changes_obj.communicate()

  if upload_changes_obj.returncode:  # Failed to upload changes.
    print(out)
    raise ValueError('Failed to upload changes for review')

  found_url = re.search(
      r'https://chromium-review.googlesource.com/c/'
      r'chromiumos/overlays/chromiumos-overlay/\+/([0-9]+)', out.rstrip())

  if not found_url:
    raise ValueError('Failed to find change list URL.')

  return CommitContents(
      url=found_url.group(0), cl_number=int(found_url.group(1)))
