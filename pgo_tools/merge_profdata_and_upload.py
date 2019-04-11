#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Download profdata from different arches, merge them and upload to gs."""

from __future__ import print_function

import argparse
import datetime
import distutils.spawn
import os
import os.path
import shutil
import subprocess
import sys
import tempfile

_LLVM_PROFDATA = '/usr/bin/llvm-profdata'
_GS_PREFIX = 'gs://'


def _get_gs_latest(remote_lastest):
  assert remote_lastest.startswith(_GS_PREFIX)
  try:
    return subprocess.check_output(['gsutil', 'cat', remote_lastest])
  except subprocess.CalledProcessError:
    raise RuntimeError('Lastest artifacts not found: %s' % remote_lastest)


def _fetch_gs_artifact(remote_name, local_name):
  assert remote_name.startswith(_GS_PREFIX)
  subprocess.check_call(['gsutil', 'cp', remote_name, local_name])


def _find_latest_profdata(arch):
  remote_latest = ('%schromeos-image-archive/%s-llvm-pgo-generate-toolchain/'
                   'LATEST-master' % (_GS_PREFIX, arch))
  version = _get_gs_latest(remote_latest)
  profdata = ('%s-llvm-pgo-generate-toolchain/%s/llvm_profdata.tar.xz' %
              (arch, version))
  return profdata


def _get_gs_profdata(profdata):
  remote_profdata = ('%schromeos-image-archive/%s' % (_GS_PREFIX, profdata))
  tar = 'llvm_profdata.tar.xz'
  print('Downloading single profdata for: %s' % profdata)
  _fetch_gs_artifact(remote_profdata, tar)
  extract_cmd = ['tar', '-xf', tar]

  print('Extracting profdata tarball.\nCMD: %s\n' % extract_cmd)
  subprocess.check_call(extract_cmd)
  profdata = profdata.replace('llvm_profdata.tar.xz', 'llvm.profdata')
  # Return directory to the llvm.profdata extracted.
  return 'b/s/w/ir/cache/cbuild/repository/buildbot_archive/%s' % profdata


def _merge_profdata(profdata_list, output_name):
  merge_cmd = [_LLVM_PROFDATA, 'merge', '-output', output_name] + profdata_list
  print('Merging PGO profiles.\nCMD: %s\n' % merge_cmd)
  subprocess.check_call(merge_cmd)


def _tar_and_upload_profdata(profdata):
  timestamp = datetime.datetime.strftime(datetime.datetime.now(), '%Y%m%d')
  tarball = 'llvm-profdata-%s.tar.xz' % timestamp
  print('Making profdata tarball: %s' % tarball)
  subprocess.check_call(
      ['tar', '--sparse', '-I', 'xz', '-cf', tarball, profdata])

  # TODO: it's better to create a subdir: distfiles/llvm_pgo_profile, but
  # now llvm could only recognize distfiles.
  upload_cmd = [
      'gsutil', '-m', 'cp', '-n', '-a', 'public-read', tarball,
      '%schromeos-localmirror/distfiles/%s' % (_GS_PREFIX, tarball)
  ]
  print('Uploading tarball to gs.\nCMD: %s\n' % upload_cmd)
  subprocess.check_call(upload_cmd)


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
      '-l',
      '--latest',
      default=[],
      action='append',
      help='User can specify the profdata from which architectures to '
      'download. By default, we merge profdata from arm, arm64, amd64.')
  parser.add_argument(
      '-t',
      '--tryjob',
      default=[],
      action='append',
      help='Extra pgo-generate-toolchain/tryjob results to be used. Format '
      'should be {arch}-llvm-pgo-generate-toolchain(-tryjob)/{VERSION}.')
  parser.add_argument(
      '-o',
      '--output',
      default='llvm.profdata',
      help='Where to put merged PGO profile. The default is to not save it '
      'anywhere.')
  args = parser.parse_args()

  # If no --latest specified, by default we collect from listed arches.
  latest = ['arm', 'arm64', 'amd64'] if not args.latest else args.latest

  if not distutils.spawn.find_executable(_LLVM_PROFDATA):
    sys.exit(_LLVM_PROFDATA + ' not found; are you in the chroot?')

  initial_dir = os.getcwd()
  temp_dir = tempfile.mkdtemp(prefix='merge_pgo')
  success = True
  try:
    os.chdir(temp_dir)
    profdata_list = []

    for arch in latest:
      profdata = _find_latest_profdata(arch)
      profdata_loc = _get_gs_profdata(profdata)
      profdata_list.append(profdata_loc)

    if args.tryjob:
      for tryjob in args.tryjob:
        profdata = os.path.join(tryjob, 'llvm_profdata.tar.xz')
        profdata_loc = _get_gs_profdata(profdata)
        profdata_list.append(profdata_loc)

    for profdata in profdata_list:
      if os.path.getsize(profdata_loc) < 512 * 1024:
        raise RuntimeError('The PGO profile in %s is suspiciously small. '
                           'Something might have gone wrong.' % profdata)

    _merge_profdata(profdata_list, args.output)
    print('Merged profdata locates at %s\n' % os.path.abspath(args.output))
    _tar_and_upload_profdata(args.output)
    print('Merged profdata uploaded successfully.')
  except:
    success = False
    raise
  finally:
    os.chdir(initial_dir)
    if success:
      print('Clearing temp directory.')
      shutil.rmtree(temp_dir, ignore_errors=True)
    else:
      print('Script fails, temp directory is at: %s' % temp_dir)


if __name__ == '__main__':
  sys.exit(main())
